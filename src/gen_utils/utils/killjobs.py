#!/usr/bin/env python
"""
Terminate every process whose executable path contains SNIP.

Unlike killprocs, SNIP is matched only against the full path of the
running executable (e.g. /Users/me/miniforge3/bin/python3.12), not
against its arguments.  That makes it handy for stopping everything
launched from one installation or environment.  Each match is sent
SIGTERM; anything still running after 3 seconds is sent SIGKILL.

Processes whose command line contains "killjobs" or "elpy" are never
touched, and processes you are not allowed to inspect are skipped.

Examples:
    killjobs miniforge3     # stop everything run from ~/miniforge3
    killjobs envs/work      # stop everything run from the "work" env
"""
import psutil
from .helper_funs import make_tuple

import argparse
import textwrap


def on_terminate(proc):
    print("process {} terminated with exit code {}".format(
               proc, proc.returncode))

def make_parser():
    linebreaks = argparse.RawTextHelpFormatter
    descrip = textwrap.dedent(globals()['__doc__'])
    parser = argparse.ArgumentParser(formatter_class=linebreaks,
                                     description=descrip)
    parser.add_argument('snip', type=str,
                        help='text to look for in the executable path')
    return parser


def main(args=None):
    """
    args: optional -- if missing then args will be taken from command line
          or pass [h5_file] -- list with name of h5_file to open
    """
    parser = make_parser()
    args = parser.parse_args(args)
    keepit = {}
    keys = ['time', 'name', 'cmdline', 'proc']
    for proc in psutil.process_iter():
        try:
            the_dict = dict(zip(keys, (proc.create_time(), proc.exe(),
                                       proc.cmdline(), proc)))
            keepit[proc.pid] = make_tuple(the_dict)
        except (psutil.ZombieProcess, psutil.AccessDenied,
                psutil.NoSuchProcess, FileNotFoundError):
            pass  # can't inspect this process; skip it
    print('in killjobs.py, looking for {}'.format(args.snip))
    #
    # don't kill this process or the emacs python parser
    #
    proclist = []
    for the_tup in keepit.values():
        string_cmd = ' '.join(the_tup.cmdline)
        if the_tup.name.find(args.snip) > -1 and \
           string_cmd.find('killjobs') == -1 and \
           string_cmd.find('elpy') == -1:
            proclist.append(the_tup)

    # a process can exit (or turn out to be off-limits) between being listed
    # above and being signalled here, so skip any that fail instead of crashing
    good_procs = []
    for item in proclist:
        try:
            item.proc.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
        good_procs.append(item.proc)
        print('terminating: {}'.format(' '.join(item.cmdline)))

    gone, alive = psutil.wait_procs(good_procs, timeout=3, callback=on_terminate)

    for p in alive:
        try:
            p.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass


if __name__ == "__main__":

    main()
    
