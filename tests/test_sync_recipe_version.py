import shutil
import subprocess

import pytest
from click.testing import CliRunner

from gen_utils.utils import sync_recipe_version as srv

RECIPE = """\
context:
  name: demo
  version: "0.3.1"        # set by sync_recipe_version
  python_min: "3.10"

package:
  name: ${{ name }}
  version: ${{ version }}
"""


@pytest.mark.parametrize(
    "tag, version",
    [("v0.3.1", "0.3.1"), ("v1.0", "1.0"), ("v2.0.0rc1", "2.0.0rc1"), ("v1.2.3.post1", "1.2.3.post1")],
)
def test_version_from_tag(tag, version):
    assert srv.version_from_tag(tag) == version


@pytest.mark.parametrize("tag", ["0.3.1", "release-1", "v", "vfoo"])
def test_version_from_bad_tag(tag):
    with pytest.raises(ValueError):
        srv.version_from_tag(tag)


def test_get_and_set_version_keeps_layout():
    assert srv.get_recipe_version(RECIPE) == "0.3.1"
    new = srv.set_recipe_version(RECIPE, "0.4.0")
    assert new == RECIPE.replace('"0.3.1"', '"0.4.0"')
    assert "version: ${{ version }}" in new  # package.version untouched


def test_unquoted_version_gets_quoted():
    text = "context:\n  version: 1.2\n"
    assert srv.set_recipe_version(text, "1.10") == 'context:\n  version: "1.10"\n'


def test_missing_context_version():
    with pytest.raises(ValueError):
        srv.get_recipe_version("package:\n  version: 1.0\n")


def test_cli_with_tag(tmp_path):
    recipe = tmp_path / "recipe.yaml"
    recipe.write_text(RECIPE)
    runner = CliRunner()

    result = runner.invoke(srv.main, ["--recipe", str(recipe), "--tag", "v0.4.0", "--check"])
    assert result.exit_code == 1
    assert recipe.read_text() == RECIPE

    result = runner.invoke(srv.main, ["--recipe", str(recipe), "--tag", "v0.4.0"])
    assert result.exit_code == 0
    assert srv.get_recipe_version(recipe.read_text()) == "0.4.0"

    result = runner.invoke(srv.main, ["--recipe", str(recipe), "--tag", "v0.4.0", "--check"])
    assert result.exit_code == 0


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
def test_cli_uses_latest_tag(tmp_path, monkeypatch):
    def run(*args):
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    (tmp_path / "recipe").mkdir()
    (tmp_path / "recipe" / "recipe.yaml").write_text(RECIPE)
    run("init", "-q")
    run("-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-q", "--allow-empty", "-m", "a")
    run("tag", "v0.5.0")
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(srv.main, [])
    assert result.exit_code == 0, result.output
    assert srv.get_recipe_version((tmp_path / "recipe" / "recipe.yaml").read_text()) == "0.5.0"
