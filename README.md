# gen_utils

Common utility scripts: command-line tools for stopping runaway processes,
inspecting netCDF files, and switching MyST notebook execution on and off.

| Command         | What it does                                                       |
|-----------------|--------------------------------------------------------------------|
| `killprocs`     | Stop every process whose **command line** contains some text       |
| `killjobs`      | Stop every process whose **executable path** contains some text    |
| `pyncdump`      | Print the metadata of a netCDF file, like `ncdump -h`              |
| `set_execution` | Turn MyST execution on/off for jupytext-paired `.md`/`.ipynb` files |

Every command prints its full help with `-h` or `--help`.

## Installation

Install the commands globally with [pixi](https://pixi.sh), from the
anaconda.org channel that tagged releases are uploaded to:

```bash
pixi global install -c phaustin -c conda-forge gen_utils
```

Or from a local build of this repository:

```bash
pixi run build-conda
pixi global install -c file://$PWD/output -c conda-forge gen_utils
```

Run `pixi global install` from a shell where no pixi or conda environment is
active; otherwise the launchers in `~/.pixi/bin` remember that environment's
variables.

The package is `noarch: python` and works on Linux, macOS and Windows with
Python 3.10 or later.

## Commands

### killprocs

```
killprocs SNIP
```

Terminates every process whose command line contains `SNIP`. The match is a
plain substring test against the full command line (program plus arguments,
joined with spaces), so `SNIP` can match a script name or an argument as well
as the program itself.

```bash
killprocs jupyter       # stop all jupyter servers and kernels
killprocs my_model.py   # stop runs of a particular script
killprocs python        # stop every python process (careful!)
```

### killjobs

```
killjobs SNIP
```

Terminates every process whose executable path contains `SNIP`. Unlike
`killprocs`, only the full path of the running program is checked (e.g.
`/Users/me/miniforge3/bin/python3.12`), not its arguments. That makes it handy
for stopping everything launched from one installation or environment.

```bash
killjobs miniforge3     # stop everything run from ~/miniforge3
killjobs envs/work      # stop everything run from the "work" env
```

### How killprocs and killjobs stop processes

- Each match is sent SIGTERM; anything still running after 3 seconds is sent
  SIGKILL.
- A process whose command line contains the tool's own name (`killprocs` or
  `killjobs`) or `elpy` is never touched, so neither tool stops itself.
- Processes you aren't allowed to inspect (for example, other users'
  processes) are skipped, as are processes that exit before they can be
  stopped.
- **On Windows**, matching ignores case and treats `/` and `\` as the same
  (`envs\work` and `ENVS/Work` both work). There is no gentle SIGTERM:
  each match is stopped immediately, because psutil's `terminate()` and
  `kill()` both call `TerminateProcess`.

### pyncdump

```
pyncdump NCFILE
```

Prints the metadata of a netCDF file: global attributes, dimensions (with
sizes) and variables (with dimensions, sizes, types and attributes), similar
to `ncdump -h`. No data values are printed. If the file has groups, variables
are listed for each top-level group; otherwise they are listed for the root
group.

```bash
pyncdump data/era5_2020.nc
pyncdump output.nc | less
```

Adapted from
<http://schubert.atmos.colostate.edu/~cslocum/netcdf_example.html>.

### set_execution

```
set_execution [--dry-run] [--no-sync] {on|off|status} FILES...
```

Turns [MyST](https://mystmd.org) notebook execution on or off for
jupytext-paired MyST markdown files, then syncs the paired `.ipynb` files.

Execution is controlled by the page frontmatter key `execute.skip`. Jupytext
copies the markdown frontmatter into the notebook's top-level metadata, which
is where mystmd looks when it builds from the `.ipynb` files.

```bash
set_execution off courseware/*.md      # add execute: {skip: true}
set_execution on  courseware/clouds.md # remove execute.skip
set_execution status courseware/*.md   # report current state
set_execution off courseware/a.ipynb   # .ipynb paths are mapped to .md
```

| Option      | Effect                                  |
|-------------|-----------------------------------------|
| `--dry-run` | Show changes without writing anything   |
| `--no-sync` | Don't update the paired `.ipynb` files  |

## Development

```bash
pixi run pytest        # run the tests
pixi run build-conda   # build and test the conda package into output/
```

## License

BSD-3-Clause; see [LICENSE](LICENSE).
