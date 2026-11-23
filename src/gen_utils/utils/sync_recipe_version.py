#!/usr/bin/env python
"""Keep the version in a rattler-build recipe.yaml in step with a git v* tag.

Rewrites the ``version:`` entry in the recipe's ``context:`` block, leaving
the rest of the file (comments, quoting, layout) untouched.  By default the
version comes from the most recent v* tag reachable from HEAD; use --tag to
set it before you create the tag.

\b
Usage:
    sync_recipe_version                  # use latest v* tag on this branch
    sync_recipe_version --tag v0.4.0     # set 0.4.0, then commit and tag
    sync_recipe_version --check          # exit 1 if recipe and tag differ
    sync_recipe_version --recipe path/to/recipe.yaml

\b
Release workflow:
    sync_recipe_version --tag v0.4.0
    git commit -am "Set recipe version to 0.4.0"
    git tag v0.4.0 && git push origin main v0.4.0

"""

import re
import subprocess
import sys
from pathlib import Path

import click

TAG_RE = re.compile(r"^v(\d+(?:\.\d+)*(?:[.+-]?[0-9A-Za-z.+-]+)?)$")

# an indented "version:" line inside the top-level context: block
VERSION_LINE_RE = re.compile(
    r"^(?P<lead>[ \t]+version:[ \t]*)"
    r"(?P<quote>[\"']?)(?P<value>[^\"'\s#]+)(?P=quote)"
    r"(?P<rest>.*)$"
)


def version_from_tag(tag):
    """Return the version for a v* tag, e.g. 'v0.3.1' -> '0.3.1'."""
    match = TAG_RE.match(tag.strip())
    if not match:
        raise ValueError(f"tag {tag!r} doesn't look like v<version>, e.g. v0.3.1")
    return match.group(1)


def git(*args, cwd=None):
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout.strip()


def latest_tag(cwd=None):
    """Return the most recent v* tag reachable from HEAD."""
    try:
        return git("describe", "--tags", "--abbrev=0", "--match", "v*", cwd=cwd)
    except RuntimeError as err:
        raise RuntimeError(f"no v* tag found on this branch ({err})") from None


def default_recipe(cwd=None):
    return Path(git("rev-parse", "--show-toplevel", cwd=cwd)) / "recipe" / "recipe.yaml"


def find_version_line(lines):
    """Return the index of the version line in the context: block."""
    in_context = False
    for i, line in enumerate(lines):
        if re.match(r"^context:\s*(#.*)?$", line):
            in_context = True
            continue
        if in_context:
            if line.strip() and not line[0].isspace():
                break  # next top-level key: context block is over
            if VERSION_LINE_RE.match(line):
                return i
    raise ValueError("no 'version:' entry found in the recipe's context: block")


def get_recipe_version(text):
    lines = text.splitlines(keepends=True)
    return VERSION_LINE_RE.match(lines[find_version_line(lines)]).group("value")


def set_recipe_version(text, version):
    """Return text with the context version replaced by version."""
    lines = text.splitlines(keepends=True)
    i = find_version_line(lines)
    body = lines[i].rstrip("\r\n")
    ending = lines[i][len(body) :]
    m = VERSION_LINE_RE.match(body)
    quote = m.group("quote") or '"'  # quote it so 1.10 isn't read as a float
    lines[i] = f"{m.group('lead')}{quote}{version}{quote}{m.group('rest')}{ending}"
    return "".join(lines)


@click.command(help=__doc__, context_settings={"help_option_names": ["-h", "--help"]})
@click.option("--tag", help="Tag to take the version from (default: latest v* tag on HEAD).")
@click.option(
    "--recipe",
    type=click.Path(dir_okay=False, path_type=Path),
    help="Recipe to update (default: recipe/recipe.yaml in the git repo root).",
)
@click.option("--check", is_flag=True, help="Don't write; exit 1 if the versions differ.")
def main(tag, recipe, check):
    try:
        tag = tag or latest_tag()
        version = version_from_tag(tag)
        recipe = recipe or default_recipe()
        text = recipe.read_text(encoding="utf-8")
        current = get_recipe_version(text)
    except (RuntimeError, ValueError, OSError) as err:
        click.echo(f"error: {err}", err=True)
        sys.exit(2)

    if current == version:
        click.echo(f"{recipe}: version {current} matches {tag}")
        return
    if check:
        click.echo(f"{recipe}: version {current} does not match {tag}", err=True)
        sys.exit(1)
    recipe.write_text(set_recipe_version(text, version), encoding="utf-8")
    click.echo(f"{recipe}: version {current} -> {version} (from {tag})")


if __name__ == "__main__":
    main()
