"""
Print the metadata of a netCDF file: global attributes, dimensions
(with sizes) and variables (with dimensions, sizes, types and
attributes), similar to "ncdump -h".  No data values are printed.

If the file has groups, variables are listed for each top-level group;
otherwise they are listed for the root group.

Adapted from:
    http://schubert.atmos.colostate.edu/~cslocum/netcdf_example.html

Examples:
    pyncdump data/era5_2020.nc
    pyncdump output.nc | less
"""

import argparse
from netCDF4 import Dataset
import textwrap

def ncdump(nc_fid, verb=True):
    '''
    ncdump outputs dimensions, variables and their attribute information.
    The information is similar to that of NCAR's ncdump utility.
    ncdump requires a valid instance of Dataset.

    Parameters
    ----------
    nc_fid : netCDF4.Dataset
        A netCDF4 dateset object
    verb : Boolean
        whether or not nc_attrs, nc_dims, and nc_vars are printed

    Returns
    -------
    nc_attrs : list
        A Python list of the NetCDF file global attributes
    nc_dims : list
        A Python list of the NetCDF file dimensions
    nc_vars : list
        Names of the variables in each top-level group (or in the root
        group if the file has no groups)
    '''

    def print_ncattr(key, group=None):
        """
        Prints the NetCDF file attributes for a given key

        Parameters
        ----------
        key : unicode
            a valid netCDF4.Dataset.variables key
        group : netCDF4.Group, optional
            group holding the variable; defaults to the root group
        """
        variables = (nc_fid if group is None else group).variables
        try:
            print("\t\ttype:", repr(variables[key].dtype))
            for ncattr in variables[key].ncattrs():
                print('\t\t%s:' % ncattr,\
                      repr(variables[key].getncattr(ncattr)))
        except KeyError:
            print("\t\tWARNING: %s does not contain variable attributes" % key)

    # NetCDF global attributes
    nc_attrs = nc_fid.ncattrs()
    if verb:
        print("NetCDF Global Attributes:")
        for nc_attr in nc_attrs:
            print('\t%s:' % nc_attr, repr(nc_fid.getncattr(nc_attr)))
    nc_dims = [dim for dim in nc_fid.dimensions]  # list of nc dimensions
    # Dimension shape information.
    if verb:
        print("NetCDF dimension information:")
        for dim in nc_dims:
            print("\tName:", dim)
            print("\t\tsize:", len(nc_fid.dimensions[dim]))
            print_ncattr(dim)
    # Variable information: one entry per top-level group, or the root group
    # if there are none.  nc_vars collects the variable names from all of them.
    groups = list(nc_fid.groups.items())
    if not groups:
        groups = [("root", nc_fid)]
    nc_vars = []
    for group_name, group in groups:
        group_vars = list(group.variables)
        nc_vars.extend(group_vars)
        if verb:
            print(f"NetCDF variable information for group {group_name}:")
            for var in group_vars:
                if var not in nc_dims:
                    print('\tName:', var)
                    print("\t\tdimensions:", group.variables[var].dimensions)
                    print("\t\tsize:", group.variables[var].size)
                    print_ncattr(var, group)
    return nc_attrs, nc_dims, nc_vars

def make_parser():
    linebreaks = argparse.RawTextHelpFormatter
    descrip = textwrap.dedent(__doc__)
    parser = argparse.ArgumentParser(formatter_class=linebreaks,
                                     description=descrip)
    parser.add_argument('ncfile', type=str, help='path to netcdf file to dump')
    return parser

def main(args=None):
    parser = make_parser()
    args=parser.parse_args(args)
    with Dataset(args.ncfile) as nc_in:
        ncdump(nc_in)
    

if __name__ == "__main__":
    main()
    
