"""Tests for smooth resize transitions, state persistence, and animation frame interpolation."""
import os
import json
import tempfile
import unittest
from scripts.switcher.model import Window, SessionGroup
from scripts.switcher.state import AppState, Mode
from scripts.switcher.app import (
    SwitcherApp,
    compute_frame_box,
    state_file_path,
    save_transient_state,
    load_transient_state
)
from scripts.switcher.tmux import TmuxAdapter


class SmoothStatePersistenceTest(unittest.TestCase):
    def setUp(self):
        w1 = Window(session_name="s1", session_id="$1", session_alias="1", window_id="@1", window_index=0,
                    window_name="bash", is_active=True, is_last=False, is_current=False,
                    active_pane_id="%1", active_pane_command="bash", active_pane_path="/home")
        w2 = Window(session_name="s1", session_id="$1", session_alias="1", window_id="@2", window_index=1,
                    window_name="vim", is_active=False, is_last=True, is_current=True,
                    active_pane_id="%2", active_pane_command="vim", active_pane_path="/home")
        self.groups = [SessionGroup(session_name="s1", session_id="$1", session_alias="1", windows=[w1, w2])]

    def test_state_dump_and_restore(self):
        state = AppState.create(self.groups, source_window_id="@2")
        state.mode = Mode.SEARCH
        state.query = "ba"  # matches w1 (bash)
        state.selected_window_id = "@1"
        state.show_preview = False

        data = state.dump_state()
        self.assertEqual(data["mode"], "SEARCH")
        self.assertEqual(data["query"], "ba")
        self.assertEqual(data["selected_window_id"], "@1")
        self.assertFalse(data["show_preview"])

        # Create new state and restore
        new_state = AppState.create(self.groups, source_window_id="@2")
        new_state.restore_state(data)
        self.assertEqual(new_state.mode, Mode.SEARCH)
        self.assertEqual(new_state.query, "ba")
        self.assertEqual(new_state.selected_window_id, "@1")
        self.assertFalse(new_state.show_preview)

    def test_transient_state_file_lifecycle(self):
        client = "/dev/pts/99"
        path = state_file_path(client)
        payload = {"selected_window_id": "@1", "query": "abc"}
        save_transient_state(client, payload)
        self.assertTrue(os.path.exists(path))

        loaded = load_transient_state(client)
        self.assertEqual(loaded, payload)
        # Should be consumed and deleted after load
        self.assertFalse(os.path.exists(path))


class SmoothAnimationInterpolationTest(unittest.TestCase):
    def test_compute_frame_box_center_scaling(self):
        # Full box: total_w=100, total_h=40
        # Scale 0.6 -> w=60, h=24, centered at x=(100-60)//2=20, y=(40-24)//2=8
        x, y, w, h = compute_frame_box(100, 40, 0.6)
        self.assertEqual(w, 60)
        self.assertEqual(h, 24)
        self.assertEqual(x, 20)
        self.assertEqual(y, 8)

    def test_compute_frame_box_scale_1(self):
        x, y, w, h = compute_frame_box(120, 50, 1.0)
        self.assertEqual(w, 120)
        self.assertEqual(h, 50)
        self.assertEqual(x, 0)
        self.assertEqual(y, 0)


if __name__ == "__main__":
    unittest.main()
