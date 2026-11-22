#!/usr/bin/env python
"""Turn MyST notebook execution on/off for jupytext-paired MyST markdown files,
then sync the paired .ipynb files.

Execution is controlled by the page frontmatter key ``execute.skip`` (mystmd).
Jupytext copies the md frontmatter into the notebook's top-level metadata, which
is where mystmd looks when building from the .ipynb files.

\b
Usage:
    python set_execution.py off courseware/*.md      # add execute: {skip: true}
    python set_execution.py on  courseware/clouds.md # remove execute.skip
    python set_execution.py status courseware/*.md   # report current state
    python set_execution.py off courseware/a.ipynb   # .ipynb paths are mapped to .md

"""

import json
import subprocess
import sys
from pathlib import Path

import click
import nbformat
import yaml

DELIM = "---\n"


def split_frontmatter(text):
    """Return (frontmatter_dict, body). Raise ValueError if no frontmatter."""
    if not text.startswith(DELIM):
        raise ValueError("no YAML frontmatter")
    end = text.find("\n" + DELIM, len(DELIM) - 1)
    if end == -1:
        raise ValueError("unterminated YAML frontmatter")
    header = text[len(DELIM) : end + 1]
    body = text[end + 1 + len(DELIM) :]
    return yaml.safe_load(header) or {}, body


def join_frontmatter(meta, body):
    header = yaml.safe_dump(meta, sort_keys=False, default_flow_style=False, allow_unicode=True)
    return DELIM + header + DELIM + body


def is_skipped(meta):
    execute = meta.get("execute")
    if isinstance(execute, dict) and "skip" in execute:
        return bool(execute["skip"])
    return bool(meta.get("skip_execution", False))


def set_skip(meta, skip):
    """Mutate meta so that execution is skipped (skip=True) or enabled. Return True if changed."""
    before = json.dumps(meta, sort_keys=True)
    meta.pop("skip_execution", None)  # deprecated key; normalise to execute.skip
    execute = meta.get("execute")
    if skip:
        if not isinstance(execute, dict):
            execute = {}
        execute["skip"] = True
        meta["execute"] = execute
    elif isinstance(execute, dict):
        execute.pop("skip", None)
        if not execute:
            meta.pop("execute")
    return json.dumps(meta, sort_keys=True) != before


def sync_ipynb(md_path, skip, dry_run):
    """Regenerate the paired .ipynb from the .md, keeping existing outputs.

    ``jupytext --update`` preserves notebook-level metadata already in the ipynb,
    so a stale ``execute.skip`` would survive; apply the same edit to the ipynb.
    """
    ipynb = md_path.with_suffix(".ipynb")
    cmd = [sys.executable, "-m", "jupytext", "--quiet", "--to", "ipynb"]
    if ipynb.exists():
        cmd.append("--update")  # preserve outputs already stored in the ipynb
    cmd.append(str(md_path))
    if dry_run:
        print("    would run:", " ".join(cmd[1:]))
        return True
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"    jupytext failed for {md_path}:\n{result.stderr}", file=sys.stderr)
        return False
    nb = nbformat.read(ipynb, as_version=nbformat.NO_CONVERT)
    if set_skip(nb.metadata, skip):
        nbformat.write(nb, ipynb)
    return True


def ipynb_skip(ipynb):
    return is_skipped(nbformat.read(ipynb, as_version=nbformat.NO_CONVERT).metadata)


def resolve(paths):
    seen = []
    for p in paths:
        md = Path(p).with_suffix(".md")
        if not md.is_file():
            print(f"skip {p}: {md} not found", file=sys.stderr)
            continue
        if md not in seen:
            seen.append(md)
    return seen


@click.command(help=__doc__, context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("action", type=click.Choice(["on", "off", "status"]))
@click.argument("files", nargs=-1, required=True)
@click.option("--dry-run", is_flag=True, help="Show changes without writing.")
@click.option("--no-sync", is_flag=True, help="Don't update the paired .ipynb files.")
def main(action, files, dry_run, no_sync):
    failures = 0
    for md in resolve(files):
        text = md.read_text(encoding="utf-8")
        try:
            meta, body = split_frontmatter(text)
        except ValueError as err:
            print(f"skip {md}: {err}", file=sys.stderr)
            failures += 1
            continue

        if action == "status":
            print(f"{'off' if is_skipped(meta) else 'on ':3}  {md}")
            continue

        skip = action == "off"
        changed = set_skip(meta, skip)
        prefix = "would set" if dry_run else "set"
        print(f"{prefix} execution {action:3} {md}" + ("" if changed else "  (unchanged)"))
        if changed and not dry_run:
            md.write_text(join_frontmatter(meta, body), encoding="utf-8")
        if not no_sync:
            ipynb = md.with_suffix(".ipynb")
            if changed or not ipynb.exists() or ipynb_skip(ipynb) != skip:
                if not sync_ipynb(md, skip, dry_run):
                    failures += 1

    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
