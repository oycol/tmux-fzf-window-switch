import unittest

class TestRenderLayout(unittest.TestCase):
    def test_list_draws_pane_count_and_return_marker(self):
        from unittest.mock import Mock
        from scripts.switcher.app import SwitcherApp
        from scripts.switcher.model import Window, Pane, SessionGroup
        from scripts.switcher.state import AppState
        from scripts.switcher.render import compute_layout
        p = Pane('%1', 0, '', 'bash', '/tmp', 1, True, 80, 20, 0, 0)
        src = Window('main', '$1', '1', '@1', 0, 'shell', True, False, True, '%1', 'bash', '/tmp', [p])
        dst = Window('other', '$2', '2', '@2', 2, 'build', True, False, False, '%1', 'bash', '/tmp', [p, p, p])
        app = SwitcherApp(Mock())
        app.state = AppState.create([SessionGroup('main', '$1', '1', [src]), SessionGroup('other', '$2', '2', [dst])], '@1', '@2')
        screen = Mock()
        from unittest.mock import patch
        with patch('scripts.switcher.app.curses.color_pair', return_value=0):
            app._render_list(screen, compute_layout(120, 30, preview_pct=60))
        rows = [c.args[2] for c in screen.addstr.call_args_list]
        self.assertTrue(any('↩' in row and '2.2' in row and '3P' in row for row in rows), rows)
        narrow = Mock()
        with patch('scripts.switcher.app.curses.color_pair', return_value=0):
            app._render_list(narrow, compute_layout(60, 30, preview_pct=60))
        narrow_rows = [c.args[2] for c in narrow.addstr.call_args_list]
        self.assertTrue(any('2.2' in row and '3P' in row for row in narrow_rows), narrow_rows)
        tiny = Mock()
        with patch('scripts.switcher.app.curses.color_pair', return_value=0):
            app._render_list(tiny, compute_layout(40, 20, preview_pct=60))
        self.assertTrue(any('2.2' in c.args[2] and '3P' in c.args[2]
                            for c in tiny.addstr.call_args_list))

    def test_layout_footer_at_bottom_outside_body_frames(self):
        # We wish to import layout from scripts.switcher.render
        from scripts.switcher.render import compute_layout

        width = 120
        height = 30
        layout = compute_layout(width, height, preview_pct=50, show_preview=True)

        # Footer must be at height - 2 (or bottom line inside border / full width at bottom)
        # Spec says:
        # "Outer border/title, full-width top mode/input line, split body with session list and preview,
        # full-width final single help line OUTSIDE both body boxes; divider ends ABOVE help."
        # If terminal height is 30:
        # y=0: top mode/input line or top border/title
        # Let's inspect layout coordinates:
        self.assertEqual(layout.total_w, 120)
        self.assertEqual(layout.total_h, 30)

        # Help line is at y = height - 2 (with outer border at height - 1)
        # Help line full width spans inner width
        self.assertEqual(layout.help_y, 28)
        self.assertEqual(layout.help_x, 1)
        self.assertEqual(layout.help_w, 118)

        # Body must end strictly ABOVE help line
        self.assertLess(layout.body_bottom_y, layout.help_y)
        self.assertEqual(layout.body_bottom_y, 26)
        self.assertEqual(layout.help_y - 1, 27)  # dedicated separator

        # Split body: list on left, preview on right, divider ending above help
        self.assertGreater(layout.preview_w, 0)
        self.assertGreater(layout.list_w, 0)
        self.assertEqual(layout.divider_bottom_y, layout.body_bottom_y)

if __name__ == '__main__':
    unittest.main()
