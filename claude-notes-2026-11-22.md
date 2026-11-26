# gen_utils session notes — 2026-11-22

Notes from a Claude Code session on the `gen_utils` repo. It covers the
test layout, packaging fixes, the conda recipe, GitHub Actions CI,
uploading to anaconda.org and keeping the API key safe.

---

## Current state and outstanding items

**Branch `conda-recipe-ci`** (pushed to GitHub, PR not yet opened):

- Commit `638c796`: the conda recipe, CI workflow, dependency and platform changes.
- **Not committed yet:** the `upload` job added to
  `.github/workflows/conda-build.yml`.

**To do:**

1. Commit and push the upload job to `conda-recipe-ci`.
2. Open the PR at https://github.com/phaustin/gen_utils/pull/new/conda-recipe-ci.
   CI runs only on PRs, pushes to `main` and `v*` tags, so pushing a branch
   doesn't start it.
3. Add the repository secret `ANACONDA_API_KEY` (Settings → Secrets and
   variables → Actions). Optionally set the variable `ANACONDA_OWNER` if the
   anaconda.org channel isn't `phaustin`.
4. Merge, then release with `git tag v0.2.0 && git push origin v0.2.0`.
5. Optional: put the token in a GitHub environment (`environment: anaconda`)
   restricted to `v*` tags.
6. Optional: add pixi environments for each Python version (3.10 to 3.14) so
   pytest runs on every supported Python version, not just the latest.

**Known issues in the code (not changed):**

- `helper_funs.nudge` changes the array you pass in (`newVec = Vec` isn't a copy).
- The `nudge` docstring example is wrong (3 becomes 3.003, not 3.001) and
  calls `np.alltrue`, which was removed in NumPy 2.
- `helper_funs.test_scalar` starts with `test_`, so pytest collects it if
  it's imported by name. The tests import the module instead.

---

## 1. Where should test functions go?

The project uses a `src/` layout built with hatchling, so the standard
place is a top-level `tests/` directory next to `src/`:

```
gen_utils/
├── pyproject.toml
├── src/gen_utils/...
└── tests/
    └── test_helper_funs.py
```

- Tests aren't included in the wheel.
- Tests import the installed package (editable install via pixi), not
  local files.
- `tests/` doesn't need an `__init__.py`.

Run them with `pixi run pytest`. The setting
`[tool.pytest.ini_options] testpaths = ["tests"]` is in `pyproject.toml`.

## 2. Packaging fixes and the tests folder

- **Removed `src/__init__.py`.** It made the editable install point at the
  repo root, so the package was only importable as `src.gen_utils`.
- **Added `src/gen_utils/__init__.py`** and declared the package path for
  hatch:
  ```toml
  [tool.hatch.build.targets.wheel]
  packages = ["src/gen_utils"]
  ```
- **Fixed the entry point:** `set_execution = "gen_utils.utils.set_execution:main"`.
- **Added `tests/test_helper_funs.py`**, with a test for each of
  `formatvar`, `test_scalar`, `make_tuple`, `find_centers` and `nudge`
  (5 passing).
- **Added `pytest`** to the pixi dependencies.

You committed most of this yourself as `0cd8538 add tests`.

## 3. Should `_version.py` be in `.gitignore`?

Yes. hatch-vcs regenerates it from git on every build or install, so
tracking it leaves the working tree dirty. Nothing imports it, and a fresh
clone gets it on `pixi install`.

```bash
echo "src/gen_utils/_version.py" >> .gitignore
git rm --cached src/gen_utils/_version.py   # stop tracking; file stays on disk
```

Committed as `92b2470 Stop tracking generated _version.py`. That commit
also picked up a `setuptools_scm` pixi dependency that hadn't been
committed yet.

## 4. Conda recipe (macOS, Windows, Linux)

The package is pure Python and all its dependencies are on conda-forge, so
one `noarch: python` package installs on all three platforms. The recipe
is at `recipe/recipe.yaml` (rattler-build format) and builds with:

```bash
pixi run build-conda
# → output/noarch/gen_utils-0.2.0-pyh4616a5c_0.conda
```

Key points:

- **Version:** set in the recipe (`0.2.0`) and passed to hatch-vcs with
  `SETUPTOOLS_SCM_PRETEND_VERSION`. Keep it in step with the git tag.
- **Commands:** listed under `build.python.entry_points` so conda creates
  the right launcher on each platform (for example `killprocs.exe` on
  Windows). Keep this list in step with `[project.scripts]`.
- **Recipe tests:** imports and `pip check` on Python 3.10, `--help` for
  every command, and the pytest suite run against the installed package.
  All passed locally.
- **Runtime dependencies** were added to `[project]` in `pyproject.toml`,
  which previously listed none: numpy, psutil, netCDF4, click, nbformat,
  pyyaml, jupytext.
- `rattler-build` was added to pixi, with the task
  `build-conda = "rattler-build build --recipe recipe/recipe.yaml --output-dir output"`.
- `output/` was added to `.gitignore`.

## 5. GitHub Actions workflow

File: `.github/workflows/conda-build.yml`

- **Triggers:** pushes to `main`, `v*` tags, pull requests, and manual runs
  (`workflow_dispatch`).
- **`build` job:** runs on ubuntu, macos and windows with
  `fail-fast: false`. It checks out the repo (`fetch-depth: 0` for
  hatch-vcs), installs pixi v0.84.1 with caching and `locked: true`, runs
  `pixi run pytest` and `pixi run build-conda`, and uploads the `.conda`
  file from Linux as the artifact `gen_utils-conda`.
- **Pixi platforms** were extended to
  `["osx-arm64", "linux-64", "win-64"]` and `pixi.lock` was re-solved.
- **Action versions:** `actions/checkout@v7`,
  `prefix-dev/setup-pixi@v0.11.3`, `actions/upload-artifact@v7`,
  `actions/download-artifact@v8`.
- **Speed:** CI installs the full environment, including jupyter-book and
  mystmd. A smaller CI-only environment would make it faster.

Committed as `638c796` on `conda-recipe-ci` and pushed.

## 6. nox or pytest?

nox doesn't replace pytest. It's a session runner that runs pytest in
fresh virtualenvs, mainly to test against several Python or dependency
versions. pixi already provides isolated, lock-pinned environments and
tasks, and works with conda-forge (which matters for netCDF4), so nox would
add a second environment system without much benefit.

The real gap is that pytest only runs on one Python version. pixi can
cover this with one environment per version:

```toml
[tool.pixi.feature.py310.dependencies]
python = "3.10.*"

[tool.pixi.environments]
py310 = ["py310"]
```

Then run `pixi run -e py310 pytest`.

## 7. Uploading to an anaconda.org channel

You upload the built package, not the recipe.

1. Create a token on anaconda.org (Settings → Access) with permission to
   upload.
2. Build from a tagged commit:
   ```bash
   git tag v0.2.0 && git push origin v0.2.0
   pixi run build-conda
   ```
3. Upload:
   ```bash
   export ANACONDA_API_KEY=$(security find-generic-password -s anaconda-api-key -w)
   pixi run rattler-build upload anaconda --owner eoas_ubc output/noarch/*.conda
   ```
   Or use `anaconda login` and then `anaconda upload output/noarch/*.conda`.
4. Install anywhere:
   ```bash
   conda install -c <channel> -c conda-forge gen_utils
   ```

You can't re-upload the same name, version and build. For each release,
bump `version`, or `build.number` if only the recipe changed.

## 8. Automatic upload on tags (not committed yet)

An `upload` job added to the workflow:

- runs only for `refs/tags/v*`, and only after all three platform builds pass
  (`needs: build`);
- fails if the tag (for example `v0.2.0`) doesn't match the recipe's `version`;
- downloads the `gen_utils-conda` artifact;
- uploads with `pixi exec rattler-build upload anaconda --owner
  ${{ vars.ANACONDA_OWNER || github.repository_owner }} dist/*.conda`,
  reading `ANACONDA_API_KEY` from the repository secret.

Setup needed: the secret `ANACONDA_API_KEY`, and optionally the variable
`ANACONDA_OWNER`.

Not yet tested: whether `upload-artifact@v7` and `download-artifact@v8`
work together. The first tagged release will show.

## 9. Keeping the API key secure

- **Keep it out of the repo** (`pyproject.toml`, workflows, `.env` files,
  commit messages) and out of chat sessions.
- **In CI**, store it as a GitHub Actions secret. Better still, store it in
  a GitHub environment restricted to `v*` tags and add
  `environment: anaconda` to the upload job.
- **Locally**, use the macOS Keychain, not a file or shell profile:
  ```bash
  security add-generic-password -a "$USER" -s anaconda-api-key -w   # prompts; stays out of history
  export ANACONDA_API_KEY=$(security find-generic-password -s anaconda-api-key -w)
  ```
  Don't type `export ANACONDA_API_KEY=<literal>`, because it lands in shell
  history.
- **Limit each token:** give it only upload permission and an expiry date,
  and use separate tokens for CI and local use.
- **If a token leaks**, including in a commit you deleted, revoke it on
  anaconda.org right away and create a new one.
