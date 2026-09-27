import unittest
import os
from scripts.switcher.model import Window, SessionGroup
from scripts.switcher.state import AppState, BROWSE as Mode_BROWSE, SEARCH as Mode_SEARCH, LOCATE as Mode_LOCATE

class TestLocateAndSearch(unittest.TestCase):
    def setUp(self):
        # Setup sessions:
        # s1 (alias 1): win0 (source @0), win1 (name bash @1), win2 (name 20 @2)
        # s2 (alias 2): win0 (name bash @3), win1 (name gdb @4), win2 (name top @5), win20 (name doc @6)
        # s12 (alias 3): win2 (name test @7)
        self.w0 = Window("s1", "$1", "1", "@0", 0, "bash", True, False, True, "%0", "bash", "/home/huangwenxuan")
        self.w1 = Window("s1", "$1", "1", "@1", 1, "bash", False, False, False, "%1", "bash", "/home/huangwenxuan/src")
        self.w2 = Window("s1", "$1", "1", "@2", 2, "20", False, True, False, "%2", "bash", "/tmp")
        self.w3 = Window("s2", "$2", "2", "@3", 0, "bash", True, False, False, "%3", "bash", "/var")
        self.w4 = Window("s2", "$2", "2", "@4", 1, "gdb", False, False, False, "%4", "gdb", "/var/log")
        self.w5 = Window("s2", "$2", "2", "@5", 2, "top", False, False, False, "%5", "top", "/root")
        self.w6 = Window("s2", "$2", "2", "@6", 20, "doc", False, False, False, "%6", "vim", "/home/huangwenxuan/docs")
        self.w7 = Window("s12", "$3", "3", "@7", 2, "test", False, False, False, "%7", "sh", "/opt")

        self.g1 = SessionGroup("s1", "$1", "1", [self.w0, self.w1, self.w2])
        self.g2 = SessionGroup("s2", "$2", "2", [self.w3, self.w4, self.w5, self.w6])
        self.g3 = SessionGroup("s12", "$3", "3", [self.w7])
        self.state = AppState.create([self.g1, self.g2, self.g3], source_window_id="@0")

    def test_exact_coordinate_locate_2_2_vs_12_2_and_2_20(self):
        # In BROWSE, typing '2' enters LOCATE
        self.state.handle_key("2")
        self.assertEqual(self.state.mode, Mode_LOCATE)
        self.assertEqual(self.state.locate_buf, "2")

        # Type '.' then '2'
        self.state.handle_key(".")
        self.state.handle_key("2")
        self.assertEqual(self.state.locate_buf, "2.2")

        # Resolve locate target: exactly session alias 2, window index 2 -> should be @5!
        target = self.state.resolve_locate_target()
        self.assertIsNotNone(target)
        self.assertEqual(target.window_id, "@5")
        self.assertEqual(target.session_alias, "2")
        self.assertEqual(target.window_index, 2)
        # Must NOT match @6 (which is 2.20) and must NOT match @7 (which is 3.2, even though session is s12)
        self.assertNotEqual(target.window_id, "@6")
        self.assertNotEqual(target.window_id, "@7")

    def test_locate_by_session_name_colon(self):
        # Locate format :<session_name>:<window_index>
        # e.g. :s2:1 -> should resolve to @4
        self.state.handle_key(":")
        for ch in "s2:1":
            self.state.handle_key(ch)
        self.assertEqual(self.state.locate_buf, ":s2:1")

        target = self.state.resolve_locate_target()
        self.assertIsNotNone(target)
        self.assertEqual(target.window_id, "@4")
        self.assertEqual(target.session_name, "s2")
        self.assertEqual(target.window_index, 1)

    def test_search_mode_literal_keys_and_escape(self):
        # Enter search mode with '/'
        self.state.handle_key("/")
        self.assertEqual(self.state.mode, Mode_SEARCH)

        # Type 'j', 'k', 'q' - in SEARCH mode they MUST be treated as query characters, not navigation/quit
        self.state.handle_key("j")
        self.state.handle_key("k")
        self.state.handle_key("q")
        self.assertEqual(self.state.query, "jkq")

        # Esc in SEARCH returns to BROWSE while retaining query filter
        self.state.handle_key("ESC")
        self.assertEqual(self.state.mode, Mode_BROWSE)
        self.assertEqual(self.state.query, "jkq")

    def test_search_by_coordinate_2_1(self):
        # In SEARCH mode, searching '2.1' should match the window with coordinate 2.1
        self.state.handle_key("/")
        self.state.query = ""
        for ch in "2.1":
            self.state.handle_key(ch)
        matched = self.state.get_eligible_windows()
        # In setUp: s2 (alias 2) has w3 (2.0), w4 (2.1), w5 (2.2), w6 (2.20)
        # Only w4 should match 2.1
        self.assertTrue(any(w.window_id == "@4" for w in matched))

    def test_format_path_home_boundary(self):
        from scripts.switcher.render import format_path
        home = os.path.expanduser("~")
        # Exact HOME -> ~
        self.assertEqual(format_path(home, max_w=20), "~")
        # HOME + /foo -> ~/foo
        self.assertEqual(format_path(home + "/project", max_w=20), "~/project")
        # Path not under HOME
        self.assertEqual(format_path("/var/log/nginx", max_w=20), "/var/log/nginx")
        # Prefix collision without boundary: /home/huangwenxuan_other/abc -> must NOT be ~/abc
        fake_user = home + "_other"
        self.assertFalse(format_path(fake_user + "/abc", max_w=30).startswith("~"))

if __name__ == '__main__':
    unittest.main()
