import unittest
from scripts.switcher.model import Window, SessionGroup

class TestNavigation(unittest.TestCase):
    def setUp(self):
        # Setup 2 sessions
        # s1: win0 (active/source/current @0), win1 (eligible @1), win2 (last eligible @2)
        # s2: win0 (eligible @3), win1 (eligible @4)
        self.w0 = Window(
            session_name="s1", session_id="$1", session_alias="1",
            window_id="@0", window_index=0, window_name="bash",
            is_active=True, is_last=False, is_current=True,
            active_pane_id="%0", active_pane_command="bash", active_pane_path="/home/user"
        )
        self.w1 = Window(
            session_name="s1", session_id="$1", session_alias="1",
            window_id="@1", window_index=1, window_name="vim",
            is_active=False, is_last=False, is_current=False,
            active_pane_id="%1", active_pane_command="vim", active_pane_path="/home/user/project"
        )
        self.w2 = Window(
            session_name="s1", session_id="$1", session_alias="1",
            window_id="@2", window_index=2, window_name="top",
            is_active=False, is_last=True, is_current=False,
            active_pane_id="%2", active_pane_command="top", active_pane_path="/home/user"
        )
        self.w3 = Window(
            session_name="s2", session_id="$2", session_alias="2",
            window_id="@3", window_index=0, window_name="make",
            is_active=True, is_last=False, is_current=False,
            active_pane_id="%3", active_pane_command="make", active_pane_path="/tmp"
        )
        self.w4 = Window(
            session_name="s2", session_id="$2", session_alias="2",
            window_id="@4", window_index=1, window_name="gdb",
            is_active=False, is_last=False, is_current=False,
            active_pane_id="%4", active_pane_command="gdb", active_pane_path="/tmp"
        )
        self.g1 = SessionGroup(session_name="s1", session_id="$1", session_alias="1", windows=[self.w0, self.w1, self.w2])
        self.g2 = SessionGroup(session_name="s2", session_id="$2", session_alias="2", windows=[self.w3, self.w4])
        self.groups = [self.g1, self.g2]

    def test_navigation_cycles_and_skips_source_and_headers(self):
        from scripts.switcher.state import AppState, Mode

        state = AppState.create(self.groups, source_window_id="@0")
        # Native session-last is not a global return target.
        self.assertEqual(state.selected_window.window_id, "@1")
        state.handle_key("j")
        self.assertEqual(state.selected_window.window_id, "@2")
        state.handle_key("j")
        self.assertEqual(state.selected_window.window_id, "@3")
        state.handle_key("j")
        self.assertEqual(state.selected_window.window_id, "@4")
        state.handle_key("j")
        self.assertEqual(state.selected_window.window_id, "@1")
        state.handle_key("k")
        self.assertEqual(state.selected_window.window_id, "@4")

    def test_session_jump_J_K(self):
        from scripts.switcher.state import AppState

        state = AppState.create(self.groups, source_window_id="@0")
        # Initially at @2 (in s1)
        # J jumps to first eligible window in next session (s2): @3
        state.handle_key("J")
        self.assertEqual(state.selected_window.window_id, "@3")

        # J from s2 wraps to first eligible window in s1: @1 (skipping source @0)
        state.handle_key("J")
        self.assertEqual(state.selected_window.window_id, "@1")

        # K from s1 wraps to first eligible window in s2: @3
        state.handle_key("K")
        self.assertEqual(state.selected_window.window_id, "@3")

        # K from s2 jumps to first eligible window in s1: @1
        state.handle_key("K")
        self.assertEqual(state.selected_window.window_id, "@1")

    def test_tab_is_unbound(self):
        from scripts.switcher.state import AppState
        state = AppState.create(self.groups, source_window_id="@0")
        before = state.selected_window_id
        state.handle_key("\t")
        self.assertEqual(state.selected_window_id, before)
        state.handle_key("KEY_BTAB")
        self.assertEqual(state.selected_window_id, before)

if __name__ == '__main__':
    unittest.main()
