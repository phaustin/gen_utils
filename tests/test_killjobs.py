import glob
import ntpath
import os
import shutil
import signal
import subprocess
import sys
import time
import uuid

import psutil
import pytest

from gen_utils.utils import helper_funs, killjobs, killprocs

WINDOWS = sys.platform == "win32"


def start_sleeper(tmp_path_factory):
    """Start a long-running process whose executable lives in a uniquely
    named directory, so killjobs can match its path without touching
    anything else.  Returns (Popen, directory name)."""
    # the path must not contain "killjobs" (killjobs skips those on purpose),
    # so don't use tmp_path: it includes the test's name
    bindir = tmp_path_factory.mktemp("kj_test_bin")
    if WINDOWS:
        # a copied python.exe runs if its DLLs come along and PYTHONHOME
        # points back at the real install for the standard library
        home = os.path.dirname(sys.executable)
        exe = bindir / "python.exe"
        shutil.copy(sys.executable, exe)
        for dll in glob.glob(os.path.join(home, "*.dll")):
            shutil.copy(dll, bindir)
        env = dict(os.environ, PYTHONHOME=sys.base_prefix)
        cmd = [str(exe), "-c", "import time; time.sleep(60)"]
    else:
        sleep = shutil.which("sleep")
        if sleep is None:
            pytest.skip("no sleep executable")
        exe = bindir / "sleep"
        shutil.copy(sleep, exe)
        if sys.platform == "darwin":
            # macOS kills copied system binaries unless they are re-signed
            subprocess.run(["codesign", "-s", "-", "-f", str(exe)],
                           check=True, capture_output=True)
        env = None
        cmd = [str(exe), "60"]
    proc = subprocess.Popen(cmd, env=env)
    # wait until the child is really running its own executable
    target = os.path.normcase(str(exe))
    for _ in range(100):
        try:
            if os.path.normcase(psutil.Process(proc.pid).exe()) == target:
                break
        except psutil.Error:
            pass
        time.sleep(0.05)
    return proc, bindir.name


def assert_stopped(proc, out):
    """killjobs/killprocs reported the kill and the process is gone.

    psutil.wait_procs reaps our own child on POSIX, so Popen may see no
    exit status; check the tool's report instead."""
    assert "terminating:" in out
    if not WINDOWS:
        assert f"exit code {-signal.SIGTERM}" in out
    proc.wait(timeout=5)


def test_match_key_windows_rules(monkeypatch):
    # run the Windows normalisation on any platform
    monkeypatch.setattr(helper_funs.os.path, "normcase", ntpath.normcase)
    key = helper_funs.match_key
    assert key("C:/Users/Me/Miniforge3") == key(r"c:\users\me\miniforge3")
    assert key("envs/work") in key(r"C:\Users\Me\Miniforge3\ENVS\Work\python.exe")


def test_killjobs_kills_matching_process(tmp_path_factory, capsys):
    proc, snip = start_sleeper(tmp_path_factory)
    if WINDOWS:
        snip = snip.upper()  # matching is case-insensitive on Windows
    try:
        assert proc.poll() is None  # still running before killjobs
        killjobs.main([snip])
        assert_stopped(proc, capsys.readouterr().out)
    finally:
        proc.kill()


def test_killjobs_process_vanishing_before_terminate(tmp_path_factory,
                                                    monkeypatch, capsys):
    # a process that exits between being listed and being signalled used to
    # crash killjobs with NoSuchProcess
    proc, snip = start_sleeper(tmp_path_factory)

    def gone(self):
        raise psutil.NoSuchProcess(self.pid)

    monkeypatch.setattr(psutil.Process, "terminate", gone)
    try:
        killjobs.main([snip])  # must not raise
        assert "terminating" not in capsys.readouterr().out
        assert proc.poll() is None  # left alone, since terminate "failed"
    finally:
        proc.kill()
        proc.wait()


def test_killprocs_kills_by_command_line(capsys):
    # killprocs matches the command line, so a unique argument is enough
    token = f"kp_token_{uuid.uuid4().hex}"
    proc = subprocess.Popen(
        [sys.executable, "-c", "import sys, time; time.sleep(60)", token])
    try:
        for _ in range(100):  # wait until the command line is visible
            try:
                if token in " ".join(psutil.Process(proc.pid).cmdline()):
                    break
            except psutil.Error:
                pass
            time.sleep(0.05)
        snip = token.upper() if WINDOWS else token
        killprocs.main([snip])
        out = capsys.readouterr().out
        assert "terminating:" in out and token in out
        if not WINDOWS:
            assert f"exit code {-signal.SIGTERM}" in out
        proc.wait(timeout=5)
    finally:
        proc.kill()
