import unittest
from scripts.switcher.model import Pane

class TestCanvas2D(unittest.TestCase):
    def test_fixed_canvas_asymmetric_L_layout(self):
        # We test rendering multiple panes into a 2D canvas without row-wise redistribution
        # Window size: 80x24 (terminal coords)
        # Pane 0: left half (w=40, h=24, x=0, y=0)
        # Pane 1: right top (w=40, h=12, x=40, y=0)
        # Pane 2: right bottom (w=40, h=12, x=40, y=12)
        p0 = Pane("%0", 0, "main", "bash", "/home", 100, True, 40, 24, 0, 0)
        p1 = Pane("%1", 1, "top", "top", "/tmp", 101, False, 40, 12, 40, 0)
        p2 = Pane("%2", 2, "gdb", "gdb", "/tmp", 102, False, 40, 12, 40, 12)

        from scripts.switcher.canvas import render_panes_to_canvas

        # Target canvas size in switcher preview area: width=50, height=20
        canvas = render_panes_to_canvas(
            panes=[p0, p1, p2],
            canvas_w=50,
            canvas_h=20,
            pane_contents={
                "%0": ["p0 line 1\n", "p0 line 2\n"],
                "%1": ["p1 top\n"],
                "%2": ["p2 bottom\n"]
            }
        )

        # Canvas must be exactly 20 lines of 50 characters
        self.assertEqual(len(canvas), 20)
        for row in canvas:
            self.assertEqual(len(row), 50)

        # Check divider characters are present
        divider_found = any('│' in row or '|' in row for row in canvas)
        self.assertTrue(divider_found)

    def test_strip_ansi_and_cjk_clamp(self):
        from scripts.switcher.canvas import sanitize_text_line
        # ANSI escape sequence must be stripped
        s = "\x1b[31;1mHello\x1b[0m \x1b[32mWorld\x1b[0m"
        clean = sanitize_text_line(s, max_w=10)
        self.assertEqual(clean, "Hello Worl")

        # CJK characters width clamp: "你好" is 4 cells wide
        cjk = "你好世界"
        clamped = sanitize_text_line(cjk, max_w=5)
        # 5 cells can only fit "你好" (4 cells) + 1 space or 4 cells without overflow
        from scripts.switcher.render import str_cell_width
        self.assertLessEqual(str_cell_width(clamped), 5)

if __name__ == '__main__':
    unittest.main()
