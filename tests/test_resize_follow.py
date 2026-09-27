"""Resize-follow behavior: popup content process detects client resize and exits 42."""
import os
import pty
import struct
import fcntl
import termios
import time
import unittest
from scripts.switcher.tmux import TmuxAdapter
from scripts.switcher.app import SwitcherApp


class FakeAdapter(TmuxAdapter):
    """Adapter stub that reports a mutable client size without touching tmux."""
    def __init__(self, size):
        super().__init__(socket_path=None, client_target="fake-client")
        self._size = size

    def get_client_size(self):
        return self._size


class ResizeDetection(unittest.TestCase):
    def test_get_client_size_signature(self):
        """TmuxAdapter must expose get_client_size() -> (w, h)."""
        self.assertTrue(hasattr(TmuxAdapter, "get_client_size"))

    def test_resize_mismatch_returns_restart(self):
        """_handle_resize returns True when client size differs from popup size."""
        app = SwitcherApp(FakeAdapter((200, 60)))
        app.popup_size = (90, 30)
        self.assertTrue(app._handle_resize())

    def test_no_resize_returns_false(self):
        app = SwitcherApp(FakeAdapter((120, 40)))
        app.popup_size = (108, 31)  # 90% of 120w, 78% of 40h per switch.sh
        self.assertFalse(app._handle_resize())

    def test_resize_scale_consistent_with_launcher(self):
        """popup_size_for_client mirrors switch.sh thresholds."""
        from scripts.switcher.app import popup_size_for_client
        self.assertEqual(popup_size_for_client(120, 40), (108, 31))  # 90%/78%
        self.assertEqual(popup_size_for_client(160, 40), (120, 31))  # 75%/78%
        self.assertEqual(popup_size_for_client(200, 60), (150, 43))  # 75%/72%
        self.assertEqual(popup_size_for_client(300, 80), (165, 57))  # 55% capped at 165 / 72%
        self.assertEqual(popup_size_for_client(100, 30), (90, 28))   # 90% / h-2
        self.assertEqual(popup_size_for_client(80, 20), (72, 18))    # 90% / h-2
        self.assertEqual(popup_size_for_client(80, 14), (72, 14))    # h-2 floored at 14


if __name__ == "__main__":
    unittest.main()
