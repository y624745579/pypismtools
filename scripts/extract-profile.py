#!/usr/bin/env python
# Copyright (C) 2012 Andy Aschwanden
#

import time
from argparse import ArgumentParser
import numpy as np
from scipy.interpolate import RectBivariateSpline
from pyproj import Proj
from sys import stderr

try:
    from netCDF4 import Dataset as NC
except:
    from netCDF3 import Dataset as NC

try:
    import pypismtools.pypismtools as ppt
except:
    import pypismtools as ppt


def piecewise_bilinear(x, y, fl_i, fl_j, A, B, C, D):
    '''
    Returns a piece-wise bilinear interpolation.

      ^ y
      |
      |
      B-----C
      |     |
      | *   |   x
    --A-----D---->
      |

    Parameters
    ----------
    x, y: 1d coordinate arrays
    fl_i, fl_j: 1d indices arrays
    A, B, C, D: array_like containing corner values

    Returns
    -------
    pw_linear: array with shape like fl_i containing interpolated values
    
    '''

    delta_x = fl_x - x[fl_i]
    delta_y = fl_y - y[fl_j]

    alpha = 1./dx * delta_x
    beta  = 1./dy * delta_y

    pw_bilinear = ((1-alpha) * (1-beta) * A + (1-alpha) * beta * B +
                   alpha * beta * C + alpha * (1-beta) * D)

    return pw_bilinear


def read_textfile(filename):
    '''
    Reads lat / lon from an ascii file.

    Paramters
    ----------
    filename: filename of ascii file.

    Returns
    -------
    lat, lon: array_like coordinates
    
    '''

    try:
        lat, lon = np.loadtxt(filename, usecols=(0,1), unpack=True)
    except:
        lat, lon = np.loadtxt(filename, skiprows=1, usecols=(0,1), unpack=True)

    return lat, lon

def read_shapefile(filename):
    '''
    Reads lat / lon from a ESRI shape file.

    Paramters
    ----------
    filename: filename of ESRI shape file.

    Returns
    -------
    lat, lon: array_like coordinates
    
    '''
    import ogr
    driver = ogr.GetDriverByName('ESRI Shapefile')
    data_source = driver.Open(filename, 0)
    layer = data_source.GetLayer(0)
    srs=layer.GetSpatialRef()
    # Make sure we use lat/lon coordinates.
    # Fixme: allow reprojection onto lat/lon if needed.
    if not srs.IsGeographic():
        print('''Spatial Reference System in % s is not lat/lon. Exiting.'''
              % filename)
        import sys
        sys.exit(0)
    cnt = layer.GetFeatureCount()
    x = []
    y = []
    for pt in range(0, cnt):
        feature = layer.GetFeature(pt)
        geometry = feature.GetGeometryRef()
        x.append(geometry.GetX())
        y.append(geometry.GetY())

    return np.asarray(y), np.asarray(x)

def create_profile_axis(filename, projection, flip):
    '''
    Create a profile axis.

    Parameters
    -----------
    filename: filename of ascii file
    projection: proj4 projection object

    Returns
    -------
    x: array_like along-profile axis
    lat: array_like latitudes
    lon: array_like longitudes
    
    '''

    try:
        fl_lat, fl_lon = read_shapefile(filename)
    except:
        fl_lat, fl_lon = read_textfile(filename)
    if flip:
        fl_lat = fl_lat[::-1]
        fl_lon = fl_lon[::-1]
    fl_x, fl_y = projection(fl_lon, fl_lat)

    x = np.zeros_like(fl_x)
    x[1::] = np.sqrt(np.diff(fl_x)**2 + np.diff(fl_y)**2)
    x = x.cumsum()

    return x, fl_x, fl_y, fl_lon, fl_lat


def dim_permute(
    values, input_order=('time', 'z', 'zb', 'y', 'x'),
    output_order=('time', 'z', 'zb', 'y', 'x')):
    '''
    Permute dimensions of an array_like object.

    Parameters
    ----------
    values : array_like
    input_order : dimension tuple
    output_order: dimension tuple (optional)
                  default ordering is ('time', 'z', 'zb', 'y', 'x')

    Returns
    -------
    values_perm : array_like
    
    '''

    # filter out irrelevant dimensions
    dimensions = filter(lambda(x): x in input_order,
                        output_order)

    # create the mapping
    mapping = map(lambda(x): dimensions.index(x),
                  input_order)

    if mapping:
        return np.transpose(values, mapping)
    else:
        return values  # so that it does not break processing "mapping"

        
# Set up the option parser

description = '''A script to extract data along a given profile using
piece-wise constant or bilinear interpolation.
The profile must be given in an ascii file with col(0)=lat, col(1)=lon.
The file may have a header in row(0).'''

parser = ArgumentParser()
parser.description = description
parser.add_argument("FILE", nargs='*')
parser.add_argument(
    "-b", "--bilinear",dest="bilinear",action="store_true",
    help='''Piece-wise bilinear interpolation, Default=False''',
    default=False)
parser.add_argument(
    "-f", "--flip",dest="flip",action="store_true",
    help='''Flip profile direction, Default=False''',
    default=False)

options = parser.parse_args()
bilinear = options.bilinear
args = options.FILE
flip = options.flip
fill_value = -2e33

n_args = len(args)
required_no_args = 2
max_no_args = 3
if (n_args < required_no_args):
    print(("received $i arguments, at least %i expected"
          % (n_args, required_no_args)))
    import sys.exit
    sys.exit
elif (n_args > max_no_args):
    print(("received $i arguments, no more thant %i accepted"
          % (n_args, max_no_args)))
    import sys.exit
    sys.exit
else:
    profile_filename = args[0]
    in_filename = args[1]
    if (n_args == 2):
        out_filename = 'profile.nc'
    else:
        out_filename = args[2]

print("Opening NetCDF file %s ..." % in_filename)
try:
    # open netCDF file in 'read' mode
    nc_in = NC(in_filename, 'r')
except:
    print(("ERROR:  file '%s' not found or not NetCDF format ... ending ..."
          % in_filename))
    import sys
    sys.exit()

# get the dimensions
xdim, ydim, zdim, tdim = ppt.get_dims(nc_in)
x = nc_in.variables[xdim][:]
y = nc_in.variables[ydim][:]
x0 = x[0]
y0 = y[0]
dx = x[1] - x[0]
dy = y[1] - y[0]
# set up dimension ordering
dim_order = (xdim, ydim, zdim, tdim)
projection = ppt.get_projection_from_file(nc_in)


# Read in profile data
print("Reading profile from %s" % profile_filename)
fl, fl_x, fl_y, fl_lon, fl_lat = create_profile_axis(
    profile_filename, projection, flip)

# indices (i,j)
fl_i = (np.floor((fl_x-x0) / dx)).astype('int') + 1
fl_j = (np.floor((fl_y-y0) / dy)).astype('int') + 1

# Filter out double entries                                                 
duplicates_idx = np.zeros(len(fl_i))
for n, x_idx in enumerate(fl_i):
    if (n+1) < len(fl_i):
        if x_idx == fl_i[n+1] and fl_j[n] == fl_j[n+1]:
            duplicates_idx[n] = fl_j[n]

fl_i = fl_i[duplicates_idx == 0]
fl_j = fl_j[duplicates_idx == 0]
fl_x = fl_x[duplicates_idx == 0]
fl_y = fl_y[duplicates_idx == 0]
fl_lat = fl_lat[duplicates_idx == 0]
fl_lon = fl_lon[duplicates_idx == 0]

A_i, A_j = fl_i, fl_j
B_i, B_j = fl_i, fl_j + 1
C_i, C_j = fl_i + 1, fl_j + 1
D_i, D_j = fl_i + 1, fl_j

mapplane_dim_names = (xdim, ydim)

# create dimensions. Check for unlimited dim.
print("Creating dimensions") 
unlimdimname = False
unlimdim = None
# create global attributes.
nc = NC(out_filename, 'w', format='NETCDF4')
# copy global attributes
for attname in nc_in.ncattrs():
    setattr(nc, attname,getattr(nc_in, attname))
# create dimensions
fldim = "profile"    
nc.createDimension(fldim, len(fl_x))
var_out = nc.createVariable(fldim, 'f', dimensions=(fldim))
fldim_values = np.zeros_like(fl_x)
fldim_values[1::] = np.cumsum(np.sqrt(np.diff(fl_x)**2 + np.diff(fl_y)**2))
var_out[:] = fldim_values
var_out.long_name = 'distance along profile'
var_out.units = 'm'

for dim_name, dim in nc_in.dimensions.iteritems():
    if dim_name not in (mapplane_dim_names or nc.dimensions):
        if dim.isunlimited():
            unlimdimname = dim_name
            unlimdim = dim
            nc.createDimension(dim_name, None)
        else:
            nc.createDimension(dim_name, len(dim))


# figure out which variables not need to be copied to the new file.
# mapplane coordinate variables
vars_not_copied = ['lat', 'lon', xdim, ydim, tdim]
for var_name in nc_in.variables:
    var = nc_in.variables[var_name]
    if hasattr(var, 'grid_mapping'):
        mapping_var_name = var.grid_mapping
        vars_not_copied.append(mapping_var_name)
    if hasattr(var, 'bounds'):
        bounds_var_name = var.bounds
        vars_not_copied.append(bounds_var_name)

vars_not_copied.sort()
last = vars_not_copied[-1]
for i in range(len(vars_not_copied)-2, -1, -1):
    if last == vars_not_copied[i]:
        del vars_not_copied[i]
    else:
        last = vars_not_copied[i]


var_name = tdim
try:
    var_in = nc_in.variables[tdim]
    dimensions = var_in.dimensions
    datatype = var_in.dtype
    if hasattr(var_in, 'bounds'):
        time_bounds = var_in.bounds
    var_out = nc.createVariable(
        var_name, datatype, dimensions=dimensions, fill_value=fill_value)
    var_out[:] = var_in[:]
    for att in var_in.ncattrs():
        if att == '_FillValue':
            continue
        else:
            setattr(var_out, att, getattr(var_in, att))
except:
    time_bounds = None

if time_bounds:
    var_name = time_bounds
    var_in = nc_in.variables[var_name]
    dimensions = var_in.dimensions
    datatype = var_in.dtype
    if hasattr(var, 'bounds'):
        time_bounds = var_in.bounds
    var_out = nc.createVariable(
        var_name, datatype, dimensions=dimensions, fill_value=fill_value)
    var_out[:] = var_in[:]
    for att in var_in.ncattrs():
        if att == '_FillValue':
            continue
        else:
            setattr(var_out, att, getattr(var_in, att))

var = 'lon'
var_out = nc.createVariable(var, 'f', dimensions=(fldim))
var_out.units = "degrees_east";
var_out.valid_range = -180., 180.
var_out.standard_name = "longitude"
var_out[:] = fl_lon

var = 'lat'
var_out = nc.createVariable(var, 'f', dimensions=(fldim))
var_out.units = "degrees_north";
var_out.valid_range = -90., 90.
var_out.standard_name = "latitude"
var_out[:] = fl_lat

print("Copying variables")
for var_name in nc_in.variables:
    if var_name not in vars_not_copied:
        var_in = nc_in.variables[var_name]
        if var_name == 'csurf':
            csurf = var_in[:]
        datatype = var_in.dtype
        in_dimensions = var_in.dimensions
        if hasattr(var_in, '_FillValue'):
            fill_value = var_in._FillValue
        else:
            fill_value = None
        if ((xdim in in_dimensions) and (ydim in in_dimensions) and
            (zdim in in_dimensions) and (tdim in in_dimensions)):
            in_values = ppt.permute(var_in, dim_order)
            dimensions = (tdim, fldim, zdim)
            input_order = (fldim, zdim, tdim)
            # Create variable
            var_out = nc.createVariable(
                var_name, datatype, dimensions=dimensions,
                fill_value=fill_value)
            if bilinear:
                A_values = dim_permute(
                    in_values[A_i,A_j,::],input_order=input_order,
                    output_order=dimensions)
                B_values = dim_permute(
                    in_values[B_i,B_j,::],input_order=input_order,
                    output_order=dimensions)
                C_values = dim_permute(
                    in_values[C_i,C_j,::],input_order=input_order,
                    output_order=dimensions)
                D_values = dim_permute(
                    in_values[D_i,D_j,::],input_order=input_order,
                    output_order=dimensions)
                var_out[:] = piecewise_bilinear(
                    x, y, fl_i, fl_j, A_values, B_values, C_values, D_values)
            else:
                fl_values = dim_permute(
                    in_values[fl_i,fl_j,::],input_order=input_order,
                    output_order=dimensions)
                var_out[:] = fl_values
        elif ((xdim in in_dimensions) and (ydim in in_dimensions) and
              (tdim in in_dimensions)):
            in_values = ppt.permute(var_in, dim_order)
            dimensions = (tdim, fldim)
            input_order = (fldim, tdim)
            # Create variable
            var_out = nc.createVariable(
                var_name, datatype, dimensions=dimensions, fill_value=fill_value)
            if bilinear:
                A_values = dim_permute(
                    in_values[A_i,A_j,::], input_order=input_order,
                    output_order=dimensions)
                B_values = dim_permute(
                    in_values[B_i,B_j,::],input_order=input_order,
                    output_order=dimensions)
                C_values = dim_permute(
                    in_values[C_i,C_j,::],input_order=input_order,
                    output_order=dimensions)
                D_values = dim_permute(
                    in_values[D_i,D_j,::],input_order=input_order,
                    output_order=dimensions)
                var_out[:] = piecewise_bilinear(
                    x, y, fl_i, fl_j, A_values, B_values, C_values,
                    D_values)
            else:
                fl_values = dim_permute(
                    in_values[fl_i,fl_j,::], input_order=input_order,
                    output_order=dimensions)
                var_out[:] = fl_values
        elif (xdim in in_dimensions and ydim in in_dimensions):
            in_values = np.squeeze(ppt.permute(var_in, dim_order))
            dimensions = (fldim)
            input_order = (fldim)
            # Create variable
            var_out = nc.createVariable(
                var_name, datatype, dimensions=dimensions,
                fill_value=fill_value)
            if bilinear:
                A_values = in_values[A_i,A_j]
                B_values = in_values[B_i,B_j]
                C_values = in_values[C_i,C_j]
                D_values = in_values[D_i,D_j]
                var_out[:] = piecewise_bilinear(
                    x, y, fl_i, fl_j, A_values, B_values,
                    C_values, D_values)
            else:
                var_out[:] = in_values[fl_i,fl_j]
        else:
            dimensions = in_dimensions
            # Create variable
            var_out = nc.createVariable(
                var_name, datatype, dimensions=dimensions,
                fill_value=fill_value)
            dimensions = in_dimensions
            if (dimensions > 0):
                in_values = nc.variables[var_name][:]
                var_out[:] = in_values
        for att in var_in.ncattrs():
            if att == '_FillValue':
                continue
            else:
                setattr(var_out, att, getattr(var_in, att))
        print("  - done with %s" % var_name)


# writing global attributes
script_command = ' '.join([time.ctime(), ':', __file__.split('/')[-1],
                           ' '.join([str(l) for l in args])])
if nc.history:
    history = nc.history
    nc.history = script_command + '\n ' + history
else:
    nc.history = script_command

nc_in.close()
nc.close()
print("Done")