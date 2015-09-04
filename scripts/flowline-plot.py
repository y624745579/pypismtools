#!/usr/bin/env python

# Copyright (C) 2011 Andy Aschwanden

from unidecode import unidecode
import numpy as np
import pylab as plt
from argparse import ArgumentParser
import matplotlib.transforms as transforms
import matplotlib.colors as colors
import matplotlib.cm as cmx

from datetime import datetime

from netcdftime import utime
from netCDF4 import Dataset as NC

try:
    import pypismtools.pypismtools as ppt
except:
    import pypismtools as ppt
    
from udunits2 import Converter, System, Unit


# Set up the option parser
parser = ArgumentParser()
parser.description = "A script for profile plots using pylab/matplotlib."
parser.add_argument("FILE", nargs='*')
parser.add_argument("--x_bounds", dest="x_bounds", nargs=2, type=int,
                    help="lower and upper bound for abscissa, eg. 0 200", default=None)
parser.add_argument("--y_bounds", dest="y_bounds", nargs=2, type=int,
                    help="lower and upper bound for ordinate, eg. 0 200", default=None)
parser.add_argument("--colormap", dest="colormap",
                    help='''path to a cpt colormap, or a pylab colormap,
                  e.g. Blues''', default='jet')
parser.add_argument("-f", "--output_format", dest="out_formats",
                    help="Comma-separated list with output graphics suffix, default = pdf", default='pdf')
parser.add_argument("-o", "--output_file", dest="outfile",
                    help="output file name without suffix, i.e. ts_control -> ts_control_variable", default='foo')
parser.add_argument("-p", "--print_size", dest="print_mode",
                    choices=['onecol', 'medium', 'twocol',
                             'height', 'presentation', 'small_font'],
                    help="sets figure size and font size. Default=small_font", default="small_font")
parser.add_argument("-r", "--output_resolution", dest="out_res",
                    help='''Resolution ofoutput graphics in dots per
                  inch (DPI), default = 300''', default=300)
parser.add_argument("-v", "--variable", dest="variables",
                    help="comma-separated list with variables", default='velsurf_mag')
parser.add_argument("--obs_file", dest="obs_file",
                    help='''Profile file with observations. Default is None''', default=None)

options = parser.parse_args()
args = options.FILE
no_args = len(args)
x_bounds = options.x_bounds
y_bounds = options.y_bounds
colormap = options.colormap
golden_mean = ppt.get_golden_mean()
obs_file = options.obs_file
out_res = options.out_res
outfile = options.outfile
out_formats = options.out_formats.split(',')
print_mode = options.print_mode
variables = options.variables.split(',')
dashes = ['-', '--', '-.', ':', '-', '--', '-.', ':']
output_order = ('station', 'time', 'profile', 'z')
alpha = 0.5
my_colors = ppt.colorList()


try:
    cdict = plt.cm.datad[colormap]
except:
    # import and convert colormap
    cdict = ppt.gmtColormap(colormap)
cmap = colors.LinearSegmentedColormap('my_colormap', cdict)

# Init Unit system
sys = System()

# Plotting styles
axisbg = '0.9'
shadow_color = '0.25'
numpoints = 1

aspect_ratio = golden_mean

# set the print mode
lw, pad_inches = ppt.set_mode(print_mode, aspect_ratio=aspect_ratio)

plt.rcParams['legend.fancybox'] = True


ne = len(args)
cNorm = colors.Normalize(vmin=0, vmax=ne)
scalarMap = cmx.ScalarMappable(norm=cNorm, cmap=cmap)


profile_axis_o_units = 'm'

filename = args[0]
try:
    nc0 = NC(filename, 'r')
except:
    print(("ERROR:  file '%s' not found or not NetCDF format ... ending ..."
           % filename))
    import sys
    sys.exit(1)
profile_names = nc0.variables['profile_name'][:]
profile_axis_name = nc0.variables['profile'].long_name
nc0.close()

for in_varname in variables:

    if in_varname in ('velsurf_mag', 'velsurf_base'):
        o_units = 'm year-1'
        o_units_str = 'm/yr'
    elif in_varname in ('land_ice_thickness', 'thickness', 'thk'):
        o_units = 'm'
        o_units_str = 'm'
    else:
        print("variable {} not supported".format(in_varname))

    # filename = args[0]
    # print("  opening NetCDF file %s ..." % filename)
    # try:
    #     nc = NC(filename, 'r')
    # except:
    #     print(("ERROR:  file '%s' not found or not NetCDF format ... ending ..."
    #            % filename))
    #     import sys
    #     sys.exit(1)


    for profile_id, profile_name in enumerate(profile_names):

        fig = plt.figure()
        ax = fig.add_subplot(111)

        nt= len(args)
        for idx, filename in enumerate(args):

            print("  opening NetCDF file %s ..." % filename)
            try:
                nc = NC(filename, 'r')
            except:
                print(("ERROR:  file '%s' not found or not NetCDF format ... ending ..."
                       % filename))
                import sys
                sys.exit(1)
            varname = in_varname
            for name in nc.variables:
                v = nc.variables[name]
                if getattr(v, "standard_name", "") == in_varname:
                    print("variabe {0} found by its standard_name {1}".format(name,
                                                                              in_varname))
                    varname = name
            
            profile_axis = nc.variables['profile'][profile_id]
            profile_axis_units = nc.variables['profile'].units
            profile_axis_name = nc.variables['profile'].long_name

            profile_axis_out_units = 'km'
            profile_axis = np.squeeze(
                ppt.unit_converter(profile_axis[:], profile_axis_units, profile_axis_out_units))
            x = profile_axis

            my_var = nc.variables[varname]
            my_var_units = my_var.units
            my_var_p = ppt.permute(my_var, output_order=output_order)
            xdim, ydim, zdim, tdim = ppt.get_dims(nc)

            if tdim:
                data = np.squeeze(my_var_p[profile_id, 0, Ellipsis])
            else:
                data = np.squeeze(my_var_p[profile_id, Ellipsis])                
            data = ppt.unit_converter(data, my_var_units, o_units)


            colorVal = scalarMap.to_rgba(idx)
            if nt > len(my_colors):
                retLine, = ax.plot(
                    x, data, color=colorVal)
            else:
                retLine, = ax.plot(x, data, color=my_colors[idx])

            nc.close()

        if obs_file:
            nc = NC(obs_file, 'r')
            varname = in_varname
            for name in nc.variables:
                v = nc.variables[name]
                if getattr(v, "standard_name", "") == in_varname:
                    print("variabe {0} found by its standard_name {1}".format(name,
                                                                              in_varname))
                    varname = name
            
            profile_axis = nc.variables['profile'][profile_id]
            profile_axis_units = nc.variables['profile'].units
            profile_axis_name = nc.variables['profile'].long_name

            profile_axis_out_units = 'km'
            profile_axis = np.squeeze(
                ppt.unit_converter(profile_axis[:], profile_axis_units, profile_axis_out_units))
            x = profile_axis

            my_var = nc.variables[varname]
            my_var_units = my_var.units
            my_var_p = ppt.permute(my_var, output_order=output_order)
            xdim, ydim, zdim, tdim = ppt.get_dims(nc)

            if tdim:
                data = np.squeeze(my_var_p[profile_id, 0, Ellipsis])
            else:
                data = np.squeeze(my_var_p[profile_id, Ellipsis])                
            data = ppt.unit_converter(data, my_var_units, o_units)


            ax.plot(x, data, color='k', linewidth=2)

            nc.close()            
            
        if x_bounds:
            ax.set_xlim(x_bounds[0], x_bounds[-1])
        else:
            xmin = np.min(x)
            xmax = np.max(x)
            ax.set_xlim(xmin, xmax)

        if y_bounds:
            ax.set_ylim(y_bounds[0], y_bounds[-1])

        xlabel = "{0} ({1})".format(profile_axis_name, profile_axis_out_units)
        ylabel = "{0} ({1})".format(varname, o_units_str)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)

        for out_format in out_formats:

            profile_name = '_'.join(
                [outfile, 'profile', unidecode(profile_name), varname])
            out_name = '.'.join([profile_name, out_format]).replace(' ', '_')
            print "  - writing image %s ..." % out_name
            fig.tight_layout()
            fig.savefig(out_name, bbox_inches='tight', dpi=out_res)

        plt.close()
