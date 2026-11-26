#!/usr/bin/env python
"""
List the network ports currently in use and the program using each one.

Shows every TCP and UDP socket (IPv4 and IPv6) with its local port and
address, the remote end if connected, the TCP state, and the PID, user
and name of the process that owns it.

Without admin rights you may only see your own processes (on macOS,
sockets of other users' processes are hidden).  Run it with sudo, or
from an administrator prompt on Windows, to see everything.

Examples:
    ports_in_use                # every TCP/UDP socket
    ports_in_use --listen       # only listening TCP ports and UDP sockets
    ports_in_use --port 8888    # who is using port 8888?
    sudo ports_in_use --listen  # include system services
"""
import argparse
import socket
import textwrap
from collections import namedtuple

import psutil

Row = namedtuple("Row", "proto port laddr raddr state pid user name")

HEADERS = ("PROTO", "PORT", "LOCAL ADDR", "REMOTE", "STATE",
           "PID", "USER", "APPLICATION")


def make_parser():
    linebreaks = argparse.RawTextHelpFormatter
    descrip = textwrap.dedent(globals()['__doc__'])
    parser = argparse.ArgumentParser(formatter_class=linebreaks,
                                     description=descrip)
    parser.add_argument('--listen', action='store_true',
                        help='show only listening TCP sockets and UDP sockets')
    parser.add_argument('--port', type=int, default=None,
                        help='show only sockets whose local port is PORT')
    return parser


def get_connections():
    """
    Return a list of (connection, pid) for every inet socket we can see.

    psutil.net_connections() lists the whole system in one call, but on
    macOS (and for some sockets on Linux) it needs root.  When it is
    refused, ask each process for its own sockets instead, skipping the
    processes we aren't allowed to inspect.
    """
    try:
        return [(c, c.pid) for c in psutil.net_connections(kind='inet')]
    except psutil.AccessDenied:
        pass
    conns = []
    for proc in psutil.process_iter():
        try:
            conns.extend((c, proc.pid)
                         for c in proc.net_connections(kind='inet'))
        except (psutil.AccessDenied, psutil.NoSuchProcess,
                psutil.ZombieProcess):
            pass
    return conns


def proc_info(pid, cache):
    """Return (user, name) for pid, or ('', '') if it can't be read."""
    if pid is None:
        return '', ''
    if pid not in cache:
        try:
            proc = psutil.Process(pid)
            name = proc.name()
            try:
                user = proc.username()
            except (psutil.AccessDenied, KeyError):
                user = ''
            cache[pid] = (user, name)
        except (psutil.AccessDenied, psutil.NoSuchProcess,
                psutil.ZombieProcess):
            cache[pid] = ('', '')
    return cache[pid]


def make_rows(conns, listen=False, port=None):
    """Turn (connection, pid) pairs into sorted, de-duplicated Rows."""
    cache = {}
    rows = set()
    for conn, pid in conns:
        proto = 'TCP' if conn.type == socket.SOCK_STREAM else 'UDP'
        if conn.family == socket.AF_INET6:
            proto += '6'
        state = conn.status if conn.status != psutil.CONN_NONE else ''
        if listen and not (state == psutil.CONN_LISTEN
                           or proto.startswith('UDP')):
            continue
        lport = conn.laddr.port if conn.laddr else None
        if port is not None and lport != port:
            continue
        laddr = conn.laddr.ip if conn.laddr else ''
        raddr = ('{}:{}'.format(conn.raddr.ip, conn.raddr.port)
                 if conn.raddr else '')
        user, name = proc_info(pid, cache)
        rows.add(Row(proto, '' if lport is None else str(lport), laddr,
                     raddr, state, '' if pid is None else str(pid),
                     user, name))
    return sorted(rows, key=lambda r: (r.proto,
                                       int(r.port) if r.port else -1,
                                       r.name, r.raddr))


def format_table(rows):
    """Return the rows as a column-aligned text table."""
    widths = [max([len(h)] + [len(r[i]) for r in rows])
              for i, h in enumerate(HEADERS)]
    fmt = '  '.join('{{:<{}}}'.format(w) for w in widths)
    lines = [HEADERS, ['-' * w for w in widths]] + list(rows)
    return '\n'.join(fmt.format(*line).rstrip() for line in lines)


def main(args=None):
    """
    args: optional -- if missing then args will be taken from command line
          or pass a list such as ['--listen']
    """
    parser = make_parser()
    args = parser.parse_args(args)
    rows = make_rows(get_connections(), listen=args.listen, port=args.port)
    print(format_table(rows))
    print('\n{} socket(s)'.format(len(rows)))
    return rows


if __name__ == "__main__":

    main()
