#!/usr/bin/env python

# Copyright (C) 2011 Andy Aschwanden

import numpy as np
import pylab as plt
from argparse import ArgumentParser
import matplotlib.transforms as transforms
import matplotlib.colors as colors
import matplotlib.cm as cmx

from datetime import datetime

from netcdftime import utime
try:
    from netCDF4 import Dataset as NC
except:
    from netCDF3 import Dataset as NC

try:
    from pypismtools import unit_converter, set_mode, colorList, get_golden_mean, permute
except:
    from pypismtools.pypismtools import unit_converter, set_mode, colorList, get_golden_mean, permute


# Set up the option parser
parser = ArgumentParser()
parser.description = "A script for profile plots using pylab/matplotlib."
parser.add_argument("FILE", nargs='*')
parser.add_argument("--bounds", dest="bounds", nargs=2, type=float,
                    help="lower and upper bound for ordinate, eg. -1 1", default=None)
parser.add_argument("--x_bounds", dest="x_bounds", nargs=2, type=int,
                    help="lower and upper bound for abscissa, eg. 0 200", default=None)
parser.add_argument("-l", "--labels", dest="labels",
                    help="comma-separated list with labels, put in quotes like 'label 1,label 2'", default=None)
parser.add_argument("--labelbar_title", dest="labelbar_title",
                    help='''Label bar title''', default=None)
parser.add_argument("--figure_title", dest="figure_title",
                    help='''Figure title''', default=None)
parser.add_argument("--index_ij", dest="index_ij", nargs=2, type=float,
                    help="i and j index for spatial fields, eg. 10 10", default=[36, 92])
parser.add_argument("-f", "--output_format", dest="out_formats",
                    help="Comma-separated list with output graphics suffix, default = pdf", default='pdf')
parser.add_argument("-n", "--normalize", dest="normalize", action="store_true",
                    help="Normalize to beginning of time series, Default=False", default=False)
parser.add_argument("-o", "--output_file", dest="outfile",
                    help="output file name without suffix, i.e. ts_control -> ts_control_variable", default='foo')
parser.add_argument("-p", "--print_size", dest="print_mode",
                    choices=['onecol', 'medium', 'twocol',
                             'height', 'presentation', 'small_font'],
                    help="sets figure size and font size. Default=medium", default="medium")
parser.add_argument("--show", dest="show", action="store_true",
                    help="show figure (in addition to save), Default=False", default=False)
parser.add_argument("--shadow", dest="shadow", action="store_true",
                    help='''add drop shadow to line plots, Default=False''',
                    default=False)
parser.add_argument("--rotate_xticks", dest="rotate_xticks", action="store_true",
                    help="rotate x-ticks by 30 degrees, Default=False",
                    default=False)
parser.add_argument("-r", "--output_resolution", dest="out_res",
                    help='''Resolution ofoutput graphics in dots per
                  inch (DPI), default = 300''', default=300)
parser.add_argument("-s", "--split", dest="split", type=int,
                    help='''Split data set''', default=None)
parser.add_argument("-t", "--twinx", dest="twinx", action="store_true",
                    help='''adds a second ordinate with units mmSLE,
                  Default=False''', default=False)
parser.add_argument("-v", "--variable", dest="variables",
                    help="comma-separated list with variables", default='velsurf_mag')

options = parser.parse_args()
args = options.FILE
no_args = len(args)
if options.labels != None:
    labels = options.labels.split(',')
else:
    labels = None
bounds = options.bounds
figure_title = options.figure_title
index_i, index_j = options.index_ij[0], options.index_ij[1]
x_bounds = options.x_bounds
golden_mean = get_golden_mean()
labelbar_title = options.labelbar_title
normalize = options.normalize
out_res = options.out_res
outfile = options.outfile
out_formats = options.out_formats.split(',')
print_mode = options.print_mode
rotate_xticks = options.rotate_xticks
shadow = options.shadow
show = options.show
twinx = options.twinx
variables = options.variables.split(',')
dashes = ['-', '--', '-.', ':', '-', '--', '-.', ':']
output_order = ('profile', 'time')
# stupid CDO changes dimension names...
output_order_cdo = ('ncells', 'time')
split = options.split

dx, dy = 4. / out_res, -4. / out_res

# Conversion between giga tons (Gt) and millimeter sea-level equivalent (mmSLE)
gt2mmSLE = 1. / 365


# Plotting styles
axisbg = '0.9'
shadow_color = '0.25'
numpoints = 1

aspect_ratio = golden_mean

# set the print mode
lw, pad_inches = set_mode(print_mode, aspect_ratio=aspect_ratio)

plt.rcParams['legend.fancybox'] = True

lines = []
profile = []
var_values = []
var_ylabels = []
var_longnames = []

# FIXME:
# If a list of variables is given, only do first in list.

var = variables[0]

for k in range(no_args):
    file_name = args[k]
    print("opening file %s" % file_name)
    nc = NC(file_name, 'r')

    profile = nc.variables["profile"]
    profile_units = profile.units
    profile_outunits = 'km'
    profile_axis = np.squeeze(
        unit_converter(profile[:], profile_units, profile_outunits))

    var_units = nc.variables[var].units
    var_longname = nc.variables[var].long_name
    var_longnames.append(var_longname)
    if var in ("ivol"):
        scale_exponent = 6
        scale = 10 ** scale_exponent
        out_units = "km3"
        var_units_str = ("10$^{%i}$ km$^{3}$" % scale_exponent)
        ylabel = ("volume change [%s]" % var_units_str)
    elif var in ("imass", "mass", "ocean_kill_flux_cumulative",
                 "surface_ice_flux_cumulative", "nonneg_flux_cumulative",
                 "climatic_mass_balance_cumulative",
                 "effective_climatic_mass_balance_cumulative",
                 "effective_ice_discharge_cumulative"):
        out_units = "Gt"
        var_units_str = "Gt"
        ylabel = ("mass change [%s]" % var_units_str)
    elif var in ("ocean_kill_flux"):
        out_units = "Gt year-1"
        var_units_str = "Gt a$^{-1}$"
        ylabel = ("mass change [%s]" % var_units_str)
    elif var in ("usurf", "topg"):
        out_units = "m"
        var_units_str = "m a.s.l"
        ylabel = ("elevation [%s]" % var_units_str)
    elif var in ("eigen1", "eigen2"):
        out_units = "year-1"
        var_units_str = "a$^{-1}$"
        ylabel = ("strain rate [%s]" % var_units_str)
    elif var in ("slope_mag", "grad_h"):
        out_units = "1"
        var_units_str = "-"
        ylabel = ("surface slope [%s]" % var_units_str)
    elif var in ("usurf_float_relative"):
        out_units = "1"
        var_units_str = "-"
        ylabel = ("relative flotation [%s]" % var_units_str)
    elif var in ("taud", "taud_mag", "taud_x", "taud_y", "bwp", "tauc"):
        out_units = "Pa"
        var_units_str = "Pa"
        ylabel = ("pressure [%s]" % var_units_str)
    elif var in ("csurf", "cbase", "cbar", "velsurf_mag", "velsurf_base"):
        out_units = "m year-1"
        var_units_str = "m a$^{-1}$"
        ylabel = ("speed [%s]" % var_units_str)
    else:
        print("unit %s not recognized" % var_units)
    var_ylabels.append(ylabel)

    try:
        var_vals = unit_converter(
            np.squeeze(permute(nc.variables[var],
                               output_order=output_order)), var_units, out_units)
    except:
        var_vals = unit_converter(
            np.squeeze(permute(nc.variables[var],
                               output_order=output_order_cdo)), var_units, out_units)
    if normalize:
        var_vals -= var_vals[0]

    var_values.append(var_vals)

    nc.close()


aspect_ratio = golden_mean

# set the print mode
lw, pad_inches = set_mode(print_mode, aspect_ratio=aspect_ratio)

plt.rcParams['legend.fancybox'] = True

my_colors = colorList()

fig = plt.figure()
ax = fig.add_subplot(111)

lines = []
line_styles = ['-', '-.', ':']
if split:
    for k in range(split):
        for idx in range(no_args / split):
            line = var_values[idx + k * (no_args / split)][:]
            retLine, = ax.plot(profile_axis, line, line_styles[k],
                               color=my_colors[idx % len(my_colors)])
            lines.append(retLine)
else:
    for idx in range(no_args):
        line = var_values[idx][:]
        retLine, = ax.plot(
            profile_axis, line, color=my_colors[idx % len(my_colors)])
        lines.append(retLine)
ax.set_xlabel("distance along profile [%s]" % profile_outunits)
ax.set_ylabel(var_ylabels[k])
if x_bounds:
    ax.set_xlim(x_bounds[0], x_bounds[1])
if labels:
    ax.legend(labels, title=labelbar_title, loc='best')
plt.title(figure_title)
for out_format in out_formats:
    out_file = outfile + '_' + var + '.' + out_format
    print "  - writing image %s ..." % out_file
    fig.savefig(out_file, bbox_inches='tight', dpi=out_res)