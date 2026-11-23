import numpy as np
from netCDF4 import Dataset

from gen_utils.utils import ncdump as nd


def make_flat(path):
    with Dataset(path, "w") as nc:
        nc.title = "flat test"
        nc.createDimension("x", 3)
        x = nc.createVariable("x", "f4", ("x",))
        x[:] = np.arange(3)
        t = nc.createVariable("temp", "f8", ("x",))
        t.units = "K"
        t[:] = [280.0, 281.0, 282.0]


def make_grouped(path):
    with Dataset(path, "w") as nc:
        nc.createDimension("x", 2)
        g = nc.createGroup("obs")
        p = g.createVariable("pres", "f4", ("x",))
        p.units = "hPa"
        p[:] = [1000.0, 900.0]


def test_ncdump_quiet_returns_lists(tmp_path):
    # verb=False used to raise NameError on nc_vars
    path = tmp_path / "flat.nc"
    make_flat(path)
    with Dataset(path) as nc:
        attrs, dims, nc_vars = nd.ncdump(nc, verb=False)
    assert attrs == ["title"]
    assert dims == ["x"]
    assert nc_vars == ["x", "temp"]


def test_ncdump_prints_group_variable_attributes(tmp_path, capsys):
    # group variables used to print a WARNING instead of their type/attributes
    path = tmp_path / "grouped.nc"
    make_grouped(path)
    with Dataset(path) as nc:
        _, _, nc_vars = nd.ncdump(nc)
    out = capsys.readouterr().out
    assert nc_vars == ["pres"]
    assert "group obs" in out
    assert "units: 'hPa'" in out
    assert "type: dtype('float32')" in out
    assert "WARNING: pres" not in out


def test_main_cli(tmp_path, capsys):
    path = tmp_path / "flat.nc"
    make_flat(path)
    nd.main([str(path)])
    out = capsys.readouterr().out
    assert "title: 'flat test'" in out
    assert "units: 'K'" in out
