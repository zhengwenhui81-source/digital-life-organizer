"""Loopback port/startup regression; only sockets and fixtures owned by this test.

Run with Python -B. Does not touch port 8765, proxies, or any existing process.
"""
import contextlib
import io
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import threading
import unittest
from unittest.mock import patch
from urllib.parse import urlparse
from urllib.request import ProxyHandler, build_opener

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "demo"))
import run_offline_browser as harness
import uvicorn


class StartupTests(unittest.TestCase):
    def test_os_port_is_loopback_and_stays_reserved(self):
        with harness.bind_listener() as occupied, harness.bind_listener() as listener:
            self.assertEqual(listener.getsockname()[0], "127.0.0.1")
            self.assertNotEqual(listener.getsockname()[1], occupied.getsockname()[1])
            with self.assertRaises(OSError):
                harness.bind_listener(listener.getsockname()[1])
            self.assertGreaterEqual(occupied.fileno(), 0)
            self.assertEqual(listener.getsockopt(socket.SOL_SOCKET, socket.SO_ACCEPTCONN), 1)

    def test_explicit_occupied_port_leaves_owner_untouched(self):
        with harness.bind_listener() as occupied, patch.object(harness.webbrowser, "open") as browser, patch.object(harness, "prepare_workspaces") as fixtures, contextlib.redirect_stderr(io.StringIO()) as errors:
            address = occupied.getsockname()
            with self.assertRaises(SystemExit) as raised:
                harness.main(["--port", str(address[1])])
            self.assertEqual(raised.exception.code, 1)
            self.assertIn("Cannot bind 127.0.0.1", errors.getvalue())
            browser.assert_not_called()
            fixtures.assert_not_called()
            # Connect only to our own still-listening sentinel socket.
            with socket.create_connection(address, timeout=2):
                occupied.settimeout(2)
                connection, _ = occupied.accept()
                connection.close()

    def test_browser_url_uses_same_socket_only_after_ready_and_cleans_up(self):
        roots, opened, listeners = [], [], []
        browser_opened = threading.Event()
        prepare = harness.prepare_workspaces

        def fixtures(root):
            roots.append(root)
            return prepare(root)

        class Server:
            started = False
            should_exit = False

            def __init__(self, config):
                self.config = config

            def run(server, sockets):
                listener = sockets[0]
                listeners.append(listener)
                self.assertEqual(listener.getsockname(), ("127.0.0.1", server.config.port))
                self.assertFalse(browser_opened.wait(0.15))
                server.started = True
                self.assertTrue(browser_opened.wait(3))
                self.assertEqual(opened, [f"http://127.0.0.1:{listener.getsockname()[1]}"])
                raise KeyboardInterrupt  # Uvicorn's post-shutdown SIGINT behavior.

        def open_browser(url):
            opened.append(url)
            browser_opened.set()

        with patch.object(harness, "prepare_workspaces", side_effect=fixtures), patch.object(uvicorn, "Server", Server), patch.object(harness.webbrowser, "open", side_effect=open_browser):
            harness.main([])
        self.assertFalse(roots[0].exists())
        self.assertEqual(listeners[0].fileno(), -1)

    def test_startup_exception_cleans_up_without_opening_browser(self):
        roots, listeners = [], []
        prepare = harness.prepare_workspaces

        def fixtures(root):
            roots.append(root)
            return prepare(root)

        class Server:
            started = False
            should_exit = False

            def __init__(self, config):
                pass

            def run(self, sockets):
                listeners.extend(sockets)
                raise RuntimeError("synthetic startup failure")

        with patch.object(harness, "prepare_workspaces", side_effect=fixtures), patch.object(uvicorn, "Server", Server), patch.object(harness.webbrowser, "open") as browser:
            with self.assertRaisesRegex(RuntimeError, "synthetic startup failure"):
                harness.main([])
            browser.assert_not_called()
        self.assertFalse(roots[0].exists())
        self.assertEqual(listeners[0].fileno(), -1)

    def test_real_server_sigint_and_temporary_directory_cleanup(self):
        # Isolate signal delivery to a test-owned Python process, never send any
        # control event to another application's process/group.
        result = subprocess.run([sys.executable, "-B", str(Path(__file__).resolve()), "--signal-child"], capture_output=True, text=True, encoding="utf-8", env={**os.environ, "PYTHONIOENCODING": "utf-8"}, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASS actual loopback HTTP, matching browser URL, SIGINT cleanup", result.stdout)
        self.assertIn("Application shutdown complete", result.stderr)


def signal_child():
    roots, opened, errors = [], [], []
    prepare = harness.prepare_workspaces

    def fixtures(root):
        roots.append(root)
        return prepare(root)

    def open_browser(url):
        try:
            opened.append(url)
            assert urlparse(url).hostname == "127.0.0.1" and urlparse(url).port > 0
            # A direct loopback request only; do not consult/change proxy config.
            with build_opener(ProxyHandler({})).open(url, timeout=3) as response:
                assert response.status == 200 and b'offlineContext' in response.read()
        except BaseException as exc:
            errors.append(repr(exc))
        finally:
            # Python delivers SIGINT to the main thread, where Uvicorn installed
            # its graceful shutdown handler. No other process is signalled.
            signal.raise_signal(signal.SIGINT)

    with patch.object(harness, "prepare_workspaces", side_effect=fixtures), patch.object(harness.webbrowser, "open", side_effect=open_browser):
        harness.main(["--step-delay", "0"])
    assert opened and not errors, errors
    assert roots and not roots[0].exists()
    print("PASS actual loopback HTTP, matching browser URL, SIGINT cleanup")


if __name__ == "__main__":
    if sys.argv[1:] == ["--signal-child"]:
        signal_child()
    else:
        unittest.main(verbosity=2)
