import unittest
from scripts.switcher.model import Window, SessionGroup
from scripts.switcher.state import AppState

class TestFzfFilter(unittest.TestCase):
    def setUp(self):
        # 3 sessions:
        # s1: win0 (source @0), win1 (vim on /proj/frontend @1), win2 (make on /proj/backend @2)
        # s2: win0 (vim on /proj/docs @3), win1 (top on /var @4)
        # s3: win0 (vim on /home @5)
        self.w0 = Window("s1", "$1", "1", "@0", 0, "bash", True, False, True, "%0", "bash", "/home")
        self.w1 = Window("s1", "$1", "1", "@1", 1, "frontend", False, False, False, "%1", "vim", "/proj/frontend")
        self.w2 = Window("s1", "$1", "1", "@2", 2, "backend", False, False, False, "%2", "make", "/proj/backend")
        self.w3 = Window("s2", "$2", "2", "@3", 0, "docs", True, False, False, "%3", "vim", "/proj/docs")
        self.w4 = Window("s2", "$2", "2", "@4", 1, "top", False, False, False, "%4", "top", "/var")
        self.w5 = Window("s3", "$3", "3", "@5", 0, "home_vim", True, False, False, "%5", "vim", "/home")

        self.g1 = SessionGroup("s1", "$1", "1", [self.w0, self.w1, self.w2])
        self.g2 = SessionGroup("s2", "$2", "2", [self.w3, self.w4])
        self.g3 = SessionGroup("s3", "$3", "3", [self.w5])
        self.state = AppState.create([self.g1, self.g2, self.g3], source_window_id="@0")

    def test_filter_windows_preserves_session_grouping_order(self):
        # Search for "vim" using fzf --filter
        from scripts.switcher.fzf import fzf_filter_windows

        results = fzf_filter_windows(self.state.groups, query="vim", source_window_id="@0")
        # Eligible windows matching vim are:
        # s1: @1 (vim)
        # s2: @3 (vim)
        # s3: @5 (vim)
        # In fzf score order, s3 might score higher or lower depending on query.
        # But switcher MUST retain session grouping order: s1 windows first, then s2, then s3!
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0].window_id, "@1")
        self.assertEqual(results[0].session_name, "s1")
        self.assertEqual(results[1].window_id, "@3")
        self.assertEqual(results[1].session_name, "s2")
        self.assertEqual(results[2].window_id, "@5")
        self.assertEqual(results[2].session_name, "s3")

if __name__ == '__main__':
    unittest.main()
