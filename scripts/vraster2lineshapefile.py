#!/usr/bin/env python
# Copyright (C) 2015-17 Bob McNabb, Andy Aschwanden

import gdal
from argparse import ArgumentParser
import fiona
import numpy as np
from fiona.crs import from_epsg
from shapely.geometry import LineString, mapping
import sys


class GeoImg:

    def __init__(self, in_filename, in_dir='.'):
        self.filename = in_filename
        self.in_dir_path = in_dir
        try:
            print("\n  opening GeoTIFF file %s" % self.filename)
            self.gd = gdal.Open(self.filename)
        except:
            print("could not open file %s" % self.filename)

        self.gt = self.gd.GetGeoTransform()
        self.proj = self.gd.GetProjection()
        self.npix_x = self.gd.RasterXSize
        self.npix_y = self.gd.RasterYSize
        self.xmin = self.gt[0]
        self.xmax = self.gt[0] + self.npix_x * \
            self.gt[1] + self.npix_y * self.gt[2]
        self.ymin = self.gt[3] + self.npix_x * \
            self.gt[4] + self.npix_y * self.gt[5]
        self.ymax = self.gt[3]
        self.dx = self.gt[1]
        self.dy = self.gt[5]
        self.nodatavalue = self.gd.GetRasterBand(1).GetNoDataValue()
        self.img = self.gd.ReadAsArray().astype(np.float32)
        self.RasterCount = self.gd.RasterCount


parser = ArgumentParser(
    description="Convert rasters containing (U,V) components of velocity field to vector line data.")
parser.add_argument("FILE", nargs=1)
parser.add_argument("-U", "--Udata", dest="Udata",
                    help="Raster containing x components of velocity")
parser.add_argument("-V", "--Vdata", dest="Vdata",
                    help="Raster containing y components of velocity")
parser.add_argument("--Uerror", dest="Uerror",
                    help="Raster containing x components of error", default=None)
parser.add_argument("--Verror", dest="Verror",
                    help="Raster containing y components of error", default=None)
parser.add_argument("--epsg",
                    dest="epsg", help="EPSG code of project. Overrides input projection", default=None)
parser.add_argument("-s", "--scale_factor", type=float,
                    dest="scale_factor", help="Scales length of line. Default=1.", default=1.)
parser.add_argument("-p", "--prune_factor", type=int,
                    dest="prune_factor", help="Pruning. Only use every x-th value. Default=1", default=1)
parser.add_argument("-t", "--threshold", type=float,
                    dest="threshold", help="Magnitude values smaller or equal than threshold will be masked. Default=None",
                    default=None)
args = parser.parse_args()
prune_factor = args.prune_factor
scale_factor = args.scale_factor
threshold = args.threshold

# create the schema (fields) and get the EPSG information for the dataset
schema = {
    'properties': [('ux', 'float'), ('uy', 'float'), ('speed', 'float')], 'geometry': 'LineString'}

Ux = GeoImg(args.Udata)
Uy = GeoImg(args.Vdata)

assert Ux.RasterCount == Uy.RasterCount
RasterCount = Ux.RasterCount

x = np.linspace(Ux.xmin, Ux.xmax, Ux.npix_x)
y = np.linspace(Ux.ymin, Ux.ymax, Ux.npix_y)

X, Y = np.meshgrid(x, np.flipud(y))
X = np.squeeze(np.tile(X, (RasterCount, 1, 1)))[::prune_factor,::prune_factor]
Y = np.squeeze(np.tile(Y, (RasterCount, 1, 1)))[::prune_factor,::prune_factor]

ux = Ux.img[::prune_factor,::prune_factor]
uy = Uy.img[::prune_factor,::prune_factor]
fill_value = Ux.nodatavalue
mask = ((ux != fill_value) & (uy != fill_value)) | (np.abs(ux) < threshold)

x = X[mask]
y = Y[mask]

prop_dict = {}
ux = ux[mask]
prop_dict['ux'] = ux
uy = uy[mask]
prop_dict['uy'] = uy
speed = np.sqrt(ux**2 + uy**2)
prop_dict['speed'] = speed

# Read and  add error of U component
if args.Uerror is not None:
    Ex = GeoImg(args.Uerror)
    schema['properties'].append(('ex', 'float'))
    ex = Ex.img
    ex = ex[mask]
    prop_dict['ex'] = ex
# Read and  add error of V component
if args.Verror is not None:
    Ey = GeoImg(args.Verror)
    schema['properties'].append(('ey', 'float'))
    ey = Ey.img
    ey = ey[mask]
    prop_dict['ey'] = ey
    
if args.epsg is None:
    epsg = int(Ux.proj.split(',')[-1].translate(None, '[]"'''))
else:
    epsg = args.epsg


# open the shapefile
with fiona.open(args.FILE[0], 'w', crs=from_epsg(
    epsg), driver='ESRI Shapefile', schema=schema) as output:

    # create features for each x,y pair, and give them the right properties
    m = 0
    for i, tmp in enumerate(ux):
        if (ux[i] != fill_value) & (uy[i] != fill_value) & (speed[i] > threshold):
            m += 1
            sys.stdout.write('\r')
            # Center cooridinates
            x_c, y_c = x[i], y[i]
            # Start point
            x_a, y_a = x[i] - scale_factor * ux[i] / 2, y[i] - scale_factor * uy[i] / 2
            # End point
            x_e, y_e = x[i] + scale_factor * ux[i] / 2, y[i] + scale_factor * uy[i] / 2
            # Create LineString
            line = LineString([[x_a, y_a], [x_c, y_c], [x_e, y_e]])
            line_dict = dict([(k, float(v[i])) for (k, v) in prop_dict.iteritems()])
            output.write(
                {'properties': line_dict, 'geometry': mapping(line)})

    print "{} points found and written to {}".format(str(m), args.FILE[0])

# close the shapefile now that we're all done
output.close()

