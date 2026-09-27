import unittest
from unittest.mock import patch, MagicMock
from scripts.switcher.model import Window, SessionGroup
from scripts.switcher.state import AppState, BROWSE, SEARCH, LOCATE

class TestTmuxAdapter(unittest.TestCase):
    def setUp(self):
        self.w0 = Window("s1", "$1", "1", "@0", 0, "bash", True, False, True, "%0", "bash", "/home")
        self.w1 = Window("s1", "$1", "1", "@1", 1, "vim", False, False, False, "%1", "vim", "/home/proj")
        self.w2 = Window("s1", "$1", "1", "@2", 2, "top", False, True, False, "%2", "top", "/tmp")
        self.g1 = SessionGroup("s1", "$1", "1", [self.w0, self.w1, self.w2])
        self.state = AppState.create([self.g1], source_window_id="@0")

    def test_source_deletion_strictly_forbidden(self):
        from scripts.switcher.tmux import TmuxAdapter

        adapter = TmuxAdapter(socket_path="/tmp/test.sock")
        # Try to delete source window @0
        success, msg = adapter.kill_window(target_window_id="@0", source_window_id="@0")
        self.assertFalse(success)
        self.assertIn("forbidden", msg.lower())

    def test_ctrl_x_disarmed_until_explicit_navigation(self):
        # Spec clause 13:
        # "After deletion, refresh, adjacent eligible focus, disarm repeated deletion
        # until explicit navigation to a different eligible target. No-op navigation/refresh must not rearm."
        self.state.selected_window_id = "@1"
        self.state.delete_blocked = False

        # Simulate deletion of @1:
        # After deletion, state should focus @2, and disarm deletion
        self.state.on_window_deleted("@1")
        self.assertEqual(self.state.selected_window_id, "@2")
        self.assertTrue(self.state.delete_blocked)

        # Attempting deletion again when disarmed must fail
        can_delete = self.state.can_delete_selected()
        self.assertFalse(can_delete)

        # A no-op navigation (e.g. k when already at top or invalid) must NOT rearm
        self.state.handle_key("invalid_key")
        self.assertFalse(self.state.can_delete_selected())

        # A single remaining candidate cannot rearm deletion by no-op navigation.
        self.state.handle_key("j")
        self.assertFalse(self.state.can_delete_selected())

if __name__ == '__main__':
    unittest.main()
