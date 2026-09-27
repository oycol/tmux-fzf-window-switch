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

    def test_selection_arrow_and_return_marker_are_separate(self):
        from unittest.mock import Mock, patch
        from scripts.switcher.app import SwitcherApp
        from scripts.switcher.model import Window, Pane, SessionGroup
        from scripts.switcher.state import AppState
        from scripts.switcher.render import compute_layout
        p = Pane('%1', 0, '', 'bash', '/tmp', 1, True, 80, 20, 0, 0)
        src = Window('main', '$1', '1', '@1', 0, 'shell', True, False, True, '%1', 'bash', '/tmp', [p])
        ret = Window('main', '$1', '1', '@2', 1, 'editor', False, False, False, '%1', 'bash', '/tmp', [p])
        other = Window('main', '$1', '1', '@3', 2, 'logs', False, False, False, '%1', 'bash', '/tmp', [p])
        app = SwitcherApp(Mock())
        # Return window is @2, selected is @2 -> arrow '›' and marker '↩' both present
        app.state = AppState.create([SessionGroup('main', '$1', '1', [src, ret, other])], '@1', return_window_id='@2')
        screen = Mock()
        with patch('scripts.switcher.app.curses.color_pair', return_value=0):
            app._render_list(screen, compute_layout(80, 20))
        rows = [c.args[2] for c in screen.addstr.call_args_list]
        selected_ret_row = next(r for r in rows if '1.1' in r)
        self.assertTrue(selected_ret_row.startswith('›↩ 1.1'), selected_ret_row)

        # Move selection to @3 -> @2 is unselected return window (' ↩'), @3 is selected ('› ')
        app.state.move_to('@3')
        screen2 = Mock()
        with patch('scripts.switcher.app.curses.color_pair', return_value=0):
            app._render_list(screen2, compute_layout(80, 20))
        rows2 = [c.args[2] for c in screen2.addstr.call_args_list]
        ret_row2 = next(r for r in rows2 if '1.1' in r)
        selected_other_row = next(r for r in rows2 if '1.2' in r)
        self.assertTrue(ret_row2.startswith(' ↩ 1.1'), ret_row2)
        self.assertTrue(selected_other_row.startswith('›  1.2'), selected_other_row)

    def test_top_bar_shows_chinese_mode_and_count_badge(self):
        from unittest.mock import Mock, patch
        from scripts.switcher.app import SwitcherApp
        from scripts.switcher.state import AppState, Mode
        from scripts.switcher.render import compute_layout
        app = SwitcherApp(Mock())
        app.state = AppState.create([], '@1')
        screen = Mock()
        layout = compute_layout(80, 20)
        with patch('scripts.switcher.app.curses.color_pair', return_value=0):
            app._render_frame(screen, layout)
        top_line = next(c.args[2] for c in screen.addstr.call_args_list if c.args[:2] == (layout.input_y, layout.input_x))
        self.assertIn('[浏览]', top_line)
        self.assertIn('0 项', top_line)

        # Mode SEARCH
        app.state.mode = Mode.SEARCH
        app.state.query = 'test'
        screen_search = Mock()
        with patch('scripts.switcher.app.curses.color_pair', return_value=0):
            app._render_frame(screen_search, layout)
        top_search = next(c.args[2] for c in screen_search.addstr.call_args_list if c.args[:2] == (layout.input_y, layout.input_x))
        self.assertIn('[搜索]', top_search)
        self.assertIn('/ test', top_search)

    def test_footer_adapts_to_current_mode(self):
        from unittest.mock import Mock, patch
        from scripts.switcher.app import SwitcherApp
        from scripts.switcher.state import AppState, Mode
        from scripts.switcher.render import compute_layout
        app = SwitcherApp(Mock())
        app.state = AppState.create([], '@1')
        layout = compute_layout(100, 20)

        # Browse mode footer
        screen_browse = Mock()
        with patch('scripts.switcher.app.curses.color_pair', return_value=0):
            app._render_frame(screen_browse, layout)
        footer_browse = next(c.args[2] for c in screen_browse.addstr.call_args_list if c.args[:2] == (layout.help_y, layout.help_x))
        self.assertIn('跨会话', footer_browse)

        # Search mode footer
        app.state.mode = Mode.SEARCH
        screen_search = Mock()
        with patch('scripts.switcher.app.curses.color_pair', return_value=0):
            app._render_frame(screen_search, layout)
        footer_search = next(c.args[2] for c in screen_search.addstr.call_args_list if c.args[:2] == (layout.help_y, layout.help_x))
        self.assertIn('选择结果', footer_search)
        self.assertIn('返回浏览', footer_search)

        # Locate mode footer
        app.state.mode = Mode.LOCATE
        screen_locate = Mock()
        with patch('scripts.switcher.app.curses.color_pair', return_value=0):
            app._render_frame(screen_locate, layout)
        footer_locate = next(c.args[2] for c in screen_locate.addstr.call_args_list if c.args[:2] == (layout.help_y, layout.help_x))
        self.assertIn('精确定位', footer_locate)
        self.assertIn('取消定位', footer_locate)

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
