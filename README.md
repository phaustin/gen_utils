# gen_utils

Common utility scripts: command-line tools for stopping runaway processes,
inspecting netCDF files, switching MyST notebook execution on and off,
converting PDF pages to MyST markdown, and listing network ports in use.

| Command         | What it does                                                       |
|-----------------|--------------------------------------------------------------------|
| `killprocs`     | Stop every process whose **command line** contains some text       |
| `killjobs`      | Stop every process whose **executable path** contains some text    |
| `pyncdump`      | Print the metadata of a netCDF file, like `ncdump -h`              |
| `set_execution` | Turn MyST execution on/off for jupytext-paired `.md`/`.ipynb` files |
| `sync_recipe_version` | Set the version in `recipe/recipe.yaml` from a git `v*` tag |
| `pdf2myst`      | Convert PDF pages to MyST markdown                                 |
| `ports_in_use`  | List network ports in use and the program using each one           |

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

### sync_recipe_version

```
sync_recipe_version [--tag vX.Y.Z] [--recipe PATH] [--check]
```

Sets the `version:` entry in the `context:` block of a rattler-build recipe
from a git `v*` tag, leaving the rest of the file unchanged. Without `--tag`
it uses the most recent `v*` tag reachable from HEAD; without `--recipe` it
edits `recipe/recipe.yaml` in the repository root.

```bash
sync_recipe_version --tag v0.4.0   # set the version before tagging
git commit -am "Set recipe version to 0.4.0"
git tag v0.4.0 && git push origin main v0.4.0

sync_recipe_version --check        # exit 1 if recipe and latest tag differ
```

| Option     | Effect                                                      |
|------------|-------------------------------------------------------------|
| `--tag`    | Take the version from this tag instead of the latest one    |
| `--recipe` | Recipe file to update                                       |
| `--check`  | Don't write; exit 1 if the versions differ (2 on errors)    |

### pdf2myst

```
pdf2myst PDF --pages PAGES [-o OUT.md] [--backend {pymupdf|marker}]
         [--title TITLE] [--img-dir DIR]
```

Converts PDF pages to [MyST](https://mystmd.org) markdown. `PAGES` are
1-based, as a PDF viewer shows them: `3`, `3-5` or `3-5,8`. Without `-o` the
output is `<pdf>_p<pages>.md` next to the PDF; images go in
`<output>_images/`.

The output gets a frontmatter block (with `title:` if `--title` is given),
display math in `{math}` directives, and images in `{figure}` directives
named `fig-<output stem>-<n>`.

```bash
pdf2myst notes.pdf --pages 3 -o pages/notes_p3.md --title "Notes"
pdf2myst notes.pdf --pages 3-5,8 --backend marker -o out.md
```

| Backend             | Library       | Notes                                                        |
|---------------------|---------------|--------------------------------------------------------------|
| `pymupdf` (default) | `pymupdf4llm` | Fast, no ML models. Equations come out as images/plain text. |
| `marker`            | `marker-pdf`  | ML-based; converts equations to LaTeX. Slow, needs PyTorch.  |

Neither backend is on conda-forge, so neither is installed with the conda
package. Install the one you want with pip, into the same environment:

```bash
pip install pymupdf4llm      # or: pip install "gen_utils[pdf]"
pip install marker-pdf       # or: pip install "gen_utils[marker]"
```

For a `pixi global` install, run
`~/.pixi/envs/gen_utils/bin/python -m pip install pymupdf4llm`.

### ports_in_use

```
ports_in_use [--listen] [--port PORT]
```

Lists every TCP and UDP socket (IPv4 and IPv6) with its local port and
address, the remote end if connected, the TCP state, and the PID, user and
name of the program that owns it.

```bash
ports_in_use                # every TCP/UDP socket
ports_in_use --listen       # only listening TCP ports and UDP sockets
ports_in_use --port 8888    # who is using port 8888?
sudo ports_in_use --listen  # include system services
```

| Option     | Meaning                                              |
|------------|------------------------------------------------------|
| `--listen` | Show only listening TCP sockets and UDP sockets      |
| `--port`   | Show only sockets whose local port is `PORT`         |

Without admin rights you may only see your own processes (on macOS, other
users' sockets are hidden). Run it with `sudo`, or from an administrator
prompt on Windows, to see everything.

## Development

```bash
pixi run pytest          # run the tests
pixi run -e pdf pytest   # also run the pdf2myst conversion test
pixi run build-conda     # build and test the conda package into output/
```

The `pdf` environment adds pymupdf4llm, which pip installs from PyPI. It uses
an older Python than the default environment (onnxruntime, a pymupdf
dependency, has no Python 3.15 wheels yet) and needs macOS 14 or later.

## License

BSD-3-Clause; see [LICENSE](LICENSE).
