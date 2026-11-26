import os
import socket

import pytest

from gen_utils.utils import ports_in_use as piu


@pytest.fixture
def listener():
    """A TCP socket listening on a free localhost port."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    sock.listen()
    yield sock.getsockname()[1]
    sock.close()


def test_finds_own_listening_port(listener, capsys):
    rows = piu.main(["--listen", "--port", str(listener)])
    assert len(rows) == 1
    row = rows[0]
    assert row.proto == "TCP"
    assert row.port == str(listener)
    assert row.laddr == "127.0.0.1"
    assert row.state == "LISTEN"
    assert row.pid == str(os.getpid())
    out = capsys.readouterr().out
    assert "APPLICATION" in out
    assert "1 socket(s)" in out


def test_listen_filter_excludes_connected_sockets(listener):
    client = socket.create_connection(("127.0.0.1", listener))
    try:
        all_rows = piu.make_rows(piu.get_connections())
        listen_rows = piu.make_rows(piu.get_connections(), listen=True)
        client_port = str(client.getsockname()[1])
        assert any(r.port == client_port for r in all_rows)
        assert not any(r.port == client_port for r in listen_rows)
    finally:
        client.close()


def test_format_table_empty():
    table = piu.format_table([])
    assert table.splitlines()[0].split()[0] == "PROTO"
    assert len(table.splitlines()) == 2
