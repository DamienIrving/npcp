"""Command line program for NPCP intercomparison data pre-processing."""

import argparse

import numpy as np
import xcdat
import xclim
import xarray as xr
import cmdline_provenance as cmdprov


var_to_cmor_name = {
    'tmax': 'tasmax',
    'mx2t': 'tasmax',
    'tmin': 'tasmin',
    'mn2t': 'tasmin',
    'precip': 'pr',
    'tp': 'pr',
    'latitude': 'lat',
    'longitude': 'lon',
    'wind': 'wsp',
    'sfcWind': 'wsp',
    'solar_exposure_day': 'rsds',
}

cmor_var_attrs = {
    'tasmax': {
        'long_name': 'Daily Maximum Near-Surface Air Temperature',
        'standard_name': 'air_temperature',
    },
    'tasmin': {
        'long_name': 'Daily Minimum Near-Surface Air Temperature',
        'standard_name': 'air_temperature',
    },
    'pr': {
        'long_name': 'Precipitation',
        'standard_name': 'precipitation_flux',
    },
    'rsds': {
        'long_name': 'Surface Downwelling Shortwave Radiation',
        'standard_name': 'surface_downwelling_shortwave_flux_in_air',
    },
    'wsp': {
        'long_name': 'Daily Average 10m Wind Speed',
        'standard_name': 'wind_speed',
    },
    'lat': {
        'long_name': 'latitude',
        'standard_name': 'latitude',
        'axis': 'Y',
        'units': 'degrees_north',
        'bounds': 'lat_bnds'
    },
    'lon': {
        'long_name': 'longitude',
        'standard_name': 'longitude',
        'axis': 'X',
        'units': 'degrees_east',
        'bounds': 'lon_bnds'
    },

}

output_units = {
    'tasmax': 'degC',
    'tasmin': 'degC',
    'pr': 'mm d-1',
    'wsp': 'm s-1',
    'rsds': 'W m-2',
}


def convert_units(da, target_units):
    """Convert units.

    Parameters
    ----------
    da : xarray DataArray
        Input array containing a units attribute
    target_units : str
        Units to convert to

    Returns
    -------
    da : xarray DataArray
       Array with converted units
    """

    xclim_unit_check = {
        'degrees_Celsius': 'degC',
        'deg_k': 'degK',
        'kg/m2/s': 'kg m-2 s-1',
        'mm': 'mm d-1',
    }

    if da.attrs["units"] in xclim_unit_check:
        da.attrs["units"] = xclim_unit_check[da.units]

    try:
        with xr.set_options(keep_attrs=True):
            da = xclim.units.convert_units_to(da, target_units)
    except Exception as e:
        if (da.attrs['units'] == 'kg m-2 s-1') and (target_units in ['mm d-1', 'mm day-1']):
            da = da * 86400
            da.attrs["units"] = target_units
        elif (da.attrs['units'] == 'MJ m^-2') and target_units == 'W m-2':
            da = da * (1e6 / 86400)
            da.attrs["units"] = target_units
        else:
            raise e
    
    if target_units == 'degC':
        da.attrs['units'] = 'degC'

    return da


def fix_metadata(ds, var):
    "Apply metadata fixes."""

    dims = list(ds[var].dims)
    dims.remove('time')
    units = ds[var].attrs['units']
    for varname in dims + [var]:
        if varname in var_to_cmor_name:
            cmor_var = var_to_cmor_name[var]
            ds = ds.rename({varname: cmor_var})
        else:
            cmor_var = varname
        ds[cmor_var].attrs = cmor_var_attrs[cmor_var]
    ds[cmor_var].attrs['units'] = units
    del ds['lat_bnds'].attrs['xcdat_bounds']
    del ds['lon_bnds'].attrs['xcdat_bounds']
    try:
        del ds['time_bnds'].attrs['xcdat_bounds']
    except KeyError:
        pass

    return ds
    

def main(args):
    """Run the program."""
    
    input_ds = xcdat.open_dataset(args.infile)

    # 20i (0.2 degree) grid with AWRA bounds
    lats = np.round(np.arange(-44, -9.99, 0.2), decimals=1)
    lons = np.round(np.arange(112, 154.01, 0.2), decimals=1)
    npcp_grid = xcdat.create_grid(lats, lons)
    output_ds = input_ds.regridder.horizontal(
        args.var,
        npcp_grid,
        tool='xesmf',
        method='conservative'
    )

    cmor_var = args.var if args.var in var_to_cmor_name.values() else var_to_cmor_name[args.var]     
    output_ds[args.var] = convert_units(output_ds[args.var], output_units[cmor_var])
    output_ds = fix_metadata(output_ds, args.var)
    output_ds.attrs['geospatial_lat_min'] = f'{lats[0]:.1f}'
    output_ds.attrs['geospatial_lat_max'] = f'{lats[-1]:.1f}'
    output_ds.attrs['geospatial_lon_min'] = f'{lons[0]:.1f}'
    output_ds.attrs['geospatial_lon_max'] = f'{lons[-1]:.1f}'
    infile_log = {}
    if 'history' in input_ds.attrs:
        infile_log[args.infile] = input_ds.attrs['history']
    output_ds.attrs['history'] = cmdprov.new_log(infile_logs=infile_log)
    output_ds.to_netcdf(args.outfile)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )     
    parser.add_argument("infile", type=str, help="input file")
    parser.add_argument("var", type=str, help="input variable")
    parser.add_argument("outfile", type=str, help="output file")
    args = parser.parse_args()
    main(args)
