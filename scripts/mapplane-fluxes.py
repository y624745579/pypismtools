#!/usr/bin/env python

import numpy as np
import pylab as plt
from skimage import measure
from argparse import ArgumentParser

from netCDF4 import Dataset as NC

try:
    import PyPISMTools.PyPISMTools as ppt
except:
    import PyPISMTools as ppt


class DischargeAnalysis(object):
    '''
    A container class for mapplane discharge objects.

    Does calculations.
    '''
    
    def __init__(self, file_names, **kwargs):
        
        for ikey in kwargs.keys():
            setattr(self, ikey, kwargs[ikey])

        analysis = []
        nt = len(file_names)
        self.nt = nt
        for k in range(0, nt):
            file_name = file_names[k]
            d = Discharge(file_name)
            analysis.append(d)
        self.analysis = analysis
            
    def icethk_cum(self):
        nt = self.nt
        icethk = np.zeros((nt))
        for k in range(0, nt):
            icethk[k] = self.analysis[k].icethk_avg.sum()
        return icethk

    def area_cum(self):
        nt = self.nt
        area = np.zeros((nt))
        for k in range(0, nt):
            area[k] = self.analysis[k].area.sum()
        return area

class Discharge(object):
    '''
    A class for a mapplane discharge object
    '''
    
    def __init__(self, file_name, **kwargs):
        
        for ikey in kwargs.keys():
            setattr(self, ikey, kwargs[ikey])

        print("  opening NetCDF file %s ..." % file_name)
        try:
            # open netCDF file in 'append' mode
            nc = NC(file_name, 'r')
        except:
            print(("ERROR:  file '%s' not found or not NetCDF format ... ending ..."
                  % file_name))
            import sys
            sys.exit(1)

        # get the dimensions
        xdim, ydim, zdim, tdim = ppt.get_dims(nc)
        # set up dimension ordering
        dim_order = (tdim, zdim, ydim, xdim)
        # add lat/lon values
        x = (np.squeeze(ppt.permute(nc.variables[xdim], dim_order)))
        x_units = nc.variables[xdim].units
        y = (np.squeeze(ppt.permute(nc.variables[ydim], dim_order)))
        y_units = nc.variables[ydim].units

        var = 'topg'
        print(("    - reading variable %s" % var))
        try:
            topg = np.squeeze(ppt.permute(nc.variables[var], dim_order))
            topg_units = nc.variables[var].units
        except:
            print(("ERROR:  unknown or not-found variable '%s' in file %s ... ending ..."
                  % (var, file_name)))
            import sys
            sys.exit(1)

        topg = ppt.unit_converter(topg, topg_units, 'm')
        mask = (topg >= 0)
        topg = np.ma.array(topg, mask = mask)

        var = 'thk'
        print(("    - reading variable %s" % var))
        try:
            thk = np.squeeze(ppt.permute(nc.variables[var], dim_order))
            thk_units = nc.variables[var].units
        except:
            print(("ERROR:  unknown or not-found variable '%s' in file %s ... ending ..."
                  % (var, file_name)))
            import sys
            sys.exit(1)

        thk = ppt.unit_converter(thk, topg_units, 'm')

        speed_units = 'm year-1'

        var = 'ubar'
        print(("    - reading variable %s" % var))
        try:
            ubar = np.squeeze(ppt.permute(nc.variables[var], dim_order))
            ubar_units = nc.variables[var].units
        except:
            print(("ERROR:  unknown or not-found variable '%s' in file %s ... ending ..."
                  % (var, file_name)))
            import sys
            sys.exit(1)

        ubar = ppt.unit_converter(ubar, ubar_units, speed_units)

        var = 'vbar'
        print(("    - reading variable %s" % var))
        try:
            vbar = np.squeeze(ppt.permute(nc.variables[var], dim_order))
            vbar_units = nc.variables[var].units
        except:
            print(("ERROR:  unknown or not-found variable '%s' in file %s ... ending ..."
                  % (var, file_name)))
            import sys
            sys.exit(1)

        vbar = ppt.unit_converter(vbar, vbar_units, speed_units)

        print(("    - reading variable %s" % var_name))
        try:
            data = np.squeeze(ppt.permute(nc.variables[var_name], dim_order))
        except:
            print(("ERROR:  unknown or not-found variable '%s' in file %s ... ending ..."
                  % (var_name, file_name)))
            import sys
            sys.exit(1)

        try:
            inunit = str(nc.variables[var_name].units)
        except:
            print(("ERROR:  units not found in variable '%s' in file %s ... ending ..."
                  % (var_name, file_name)))
            import sys
            sys.exit(1)

        if outunit is not None:
            data = ppt.unit_converter(data, inunit, outunit)

        mask = (data >= min_discharge)
        data = np.ma.array(data, mask = mask)

        outdimunits = 'm'
        dx = ppt.unit_converter(np.abs(x[1] - x[0]), x_units, outdimunits)
        dy = ppt.unit_converter(np.abs(y[1] - y[0]), y_units, outdimunits)

        velbar = np.sqrt(ubar ** 2 + vbar ** 2)

        is_discharge = data.nonzero()
        self.is_discharge = is_discharge
        
        # get number of non-zero non-masked cells
        n_cells = data[is_discharge].data.shape[0]
        self.n_cells = n_cells

        # stencil width
        n = 3

        nx, ny = thk.shape
        ii, jj = np.indices((n,n))

        icethk_avg = np.zeros((n_cells))
        gatethk_avg = np.zeros((n_cells))
        velbar_avg = np.zeros((n_cells))

        for k in range(0, n_cells):
            r = (ii + is_discharge[0][k]) % (nx - 1)  # periodic stencil
            c = (jj + is_discharge[1][k]) % (ny - 1)  # periodic stencil
            icethk_avg[k] = thk[r,c].sum() / len(thk[r,c].nonzero())
            gatethk_avg[k] = np.abs(topg[r,c]).sum() / len(np.abs(topg[r,c]).nonzero())
            velbar_avg[k] = velbar[r,c].sum() / len(velbar[r,c].nonzero())

        self.icethk_avg = icethk_avg
        self.gatethk_avg = gatethk_avg
        self.velbar_avg = velbar_avg

        area = icethk_avg * dx

        nc.close()

    

# Set up the argument parser
parser = ArgumentParser()
parser.description = '''Calculate mapplane fluxes, cross-sectional areas, etc.'''
parser.add_argument("FILE", nargs='*')

options = parser.parse_args()
file_names = options.FILE
var_name = 'ocean_kill_flux_cumulative'
outunit = 'Gt'
min_discharge = -1

d_analysis = DischargeAnalysis(file_names)
print d_analysis.icethk_cum()

# print ppt.unit_converter(cum_areas,'m2','km2')