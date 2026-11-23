import shutil
import signal
import subprocess
import sys

import psutil
import pytest

from gen_utils.utils import killjobs

pytestmark = pytest.mark.skipif(
    sys.platform == "win32" or shutil.which("sleep") is None,
    reason="needs a copyable 'sleep' executable",
)


def start_sleeper(tmp_path):
    """Run a copy of sleep from a uniquely named directory, so killjobs can
    match its executable path without touching anything else."""
    # the name must not contain "killjobs": killjobs skips those on purpose
    bindir = tmp_path / "kj_test_bin"
    bindir.mkdir()
    exe = bindir / "sleep"
    shutil.copy(shutil.which("sleep"), exe)
    if sys.platform == "darwin":
        # macOS kills copied system binaries unless they are re-signed
        subprocess.run(["codesign", "-s", "-", "-f", str(exe)],
                       check=True, capture_output=True)
    proc = subprocess.Popen([str(exe), "60"])
    return proc, bindir.name


def test_kills_matching_process(tmp_path, capsys):
    proc, snip = start_sleeper(tmp_path)
    try:
        assert proc.poll() is None  # still running before killjobs
        killjobs.main([snip])
        # psutil.wait_procs reaps our child itself, so Popen sees no exit
        # status; check killjobs' report and that the process is gone instead
        out = capsys.readouterr().out
        assert f"terminating: {tmp_path}" in out
        assert f"exit code {-signal.SIGTERM}" in out
        proc.wait(timeout=5)
    finally:
        proc.kill()


def test_process_vanishing_before_terminate(tmp_path, monkeypatch, capsys):
    # a process that exits between being listed and being signalled used to
    # crash killjobs with NoSuchProcess
    proc, snip = start_sleeper(tmp_path)

    def gone(self):
        raise psutil.NoSuchProcess(self.pid)

    monkeypatch.setattr(psutil.Process, "terminate", gone)
    try:
        killjobs.main([snip])  # must not raise
        out = capsys.readouterr().out
        assert "terminating" not in out
        assert proc.poll() is None  # left alone, since terminate "failed"
    finally:
        proc.kill()
        proc.wait()
