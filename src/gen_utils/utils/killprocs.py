#!/usr/bin/env python
"""
Terminate every process whose command line contains SNIP.

SNIP is matched as a plain substring against the full command line
(program plus arguments, joined with spaces), so it can match a script
name or an argument as well as the program itself.  Each match is sent
SIGTERM; anything still running after 3 seconds is sent SIGKILL.

On Windows, matching ignores case and treats / and \\ as the same, and
there is no gentle SIGTERM: each match is stopped immediately (psutil's
terminate() and kill() both call TerminateProcess).

Processes whose command line contains "killprocs" or "elpy" are never
touched, and processes you are not allowed to inspect are skipped.

Examples:
    killprocs jupyter       # stop all jupyter servers and kernels
    killprocs my_model.py   # stop runs of a particular script
    killprocs python        # stop every python process (careful!)
"""
import psutil
from .helper_funs import make_tuple, match_key

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
                        help='text to look for in the command line')
    return parser

def main(args=None):
    """
    args: optional -- if missing then args will be taken from command line
          or pass [snippet] -- string to search for in processes
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
                psutil.NoSuchProcess):
            pass
        except FileNotFoundError:
            pass
    print(f'in killprocs, looking for {args.snip}')
    #
    # don't kill this process or the emacs python parser
    #
    snip = match_key(args.snip)
    proclist = []
    cmdlist = []
    for the_tup in keepit.values():
        string_cmd = ' '.join(the_tup.cmdline)
        key = match_key(string_cmd)
        if snip in key and 'killprocs' not in key and 'elpy' not in key:
            proclist.append(the_tup)
            cmdlist.append(string_cmd)

    # a process can exit (or turn out to be off-limits) between being listed
    # above and being signalled here, so skip any that fail instead of crashing
    good_procs = []
    for the_tup, the_cmd in zip(proclist, cmdlist):
        try:
            the_tup.proc.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
        good_procs.append(the_tup.proc)
        print(f'terminating: {the_cmd}')

    gone, alive = psutil.wait_procs(good_procs, timeout=3, callback=on_terminate)

    for p in alive:
        try:
            p.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass


if __name__ == "__main__":

    main()
    
