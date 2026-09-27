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

    def test_compact_layout_keeps_the_window_list_readable(self):
        from scripts.switcher.render import compute_layout
        compact = compute_layout(80, 24, preview_pct=52, show_preview=True)
        self.assertFalse(compact.show_preview)
        self.assertEqual(compact.list_w, compact.inner_w)
        wide = compute_layout(120, 30, preview_pct=52, show_preview=True)
        self.assertTrue(wide.show_preview)
        self.assertGreaterEqual(wide.list_w, 46)

    def test_selected_return_window_has_explicit_focus_and_role(self):
        from unittest.mock import Mock, patch
        from scripts.switcher.app import SwitcherApp
        from scripts.switcher.model import Window, Pane, SessionGroup
        from scripts.switcher.state import AppState
        from scripts.switcher.render import compute_layout, str_cell_width
        p = Pane('%2', 0, '', 'bash', '/tmp', 1, True, 80, 20, 0, 0)
        src = Window('main', '$1', '1', '@1', 0, 'shell', True, False, True, '%1', 'bash', '/tmp', [p])
        dst = Window('other', '$2', '2', '@2', 2, 'build', True, False, False, '%2', 'bash', '/tmp', [p, p, p])
        app = SwitcherApp(Mock())
        app.state = AppState.create([SessionGroup('main', '$1', '1', [src]), SessionGroup('other', '$2', '2', [dst])], '@1', '@2')
        screen = Mock()
        layout = compute_layout(80, 24, preview_pct=52)
        with patch('scripts.switcher.app.curses.color_pair', return_value=0):
            app._render_list(screen, layout)
        rows = [c.args[2] for c in screen.addstr.call_args_list]
        focus = next(row for row in rows if '2.2' in row)
        self.assertIn('›', focus)
        self.assertIn('↩', focus)
        self.assertIn('3P', focus)
        self.assertLessEqual(str_cell_width(focus), layout.list_w)

    def test_header_shows_mode_and_latest_query_without_emoji(self):
        from unittest.mock import Mock, patch
        from scripts.switcher.app import SwitcherApp
        from scripts.switcher.state import AppState, Mode
        from scripts.switcher.render import compute_layout
        app = SwitcherApp(Mock())
        app.state = AppState.create([], '@source')
        app.state.mode = Mode.SEARCH
        app.state.query = 'prefix-' * 15 + 'last'
        layout = compute_layout(60, 20)
        screen = Mock()
        with patch('scripts.switcher.app.curses.color_pair', return_value=0):
            app._render_frame(screen, layout)
        header = ' '.join(c.args[2] for c in screen.addstr.call_args_list if c.args[0] == layout.input_y)
        self.assertIn('搜索', header)
        self.assertIn('last', header)
        self.assertNotIn('🔍', header)

    def test_empty_results_have_actionable_state(self):
        from unittest.mock import Mock, patch
        from scripts.switcher.app import SwitcherApp
        from scripts.switcher.state import AppState, Mode
        from scripts.switcher.render import compute_layout
        app = SwitcherApp(Mock())
        app.state = AppState.create([], '@source')
        app.state.mode = Mode.SEARCH
        app.state.query = 'not-found'
        layout = compute_layout(80, 20)
        screen = Mock()
        with patch('scripts.switcher.app.curses.color_pair', return_value=0):
            app._render_list(screen, layout)
        body = ' '.join(c.args[2] for c in screen.addstr.call_args_list)
        self.assertIn('没有匹配窗口', body)
        self.assertIn('Esc', body)

    def test_narrow_empty_state_never_cuts_a_shortcut(self):
        from unittest.mock import Mock, patch
        from scripts.switcher.app import SwitcherApp
        from scripts.switcher.state import AppState, Mode
        from scripts.switcher.render import compute_layout
        app = SwitcherApp(Mock())
        app.state = AppState.create([], '@source')
        app.state.query = 'ZZZ'
        for width in (36, 40):
            layout = compute_layout(width, 10)
            for mode, expected in ((Mode.SEARCH, 'Backspace 修改'),
                                   (Mode.BROWSE, 'Ctrl-u 清除过滤')):
                app.state.mode = mode
                screen = Mock()
                with patch('scripts.switcher.app.curses.color_pair', return_value=0):
                    app._render_list(screen, layout)
                message = ' '.join(c.args[2] for c in screen.addstr.call_args_list)
                self.assertIn('没有匹配窗口', message, (width, mode, message))
                self.assertIn(expected, message, (width, mode, message))
                self.assertNotIn('·  ', message)

    def test_narrow_help_page_has_complete_actions(self):
        from unittest.mock import Mock, patch
        from scripts.switcher.app import SwitcherApp
        from scripts.switcher.state import AppState
        from scripts.switcher.render import compute_layout, str_cell_width
        app = SwitcherApp(Mock())
        app.state = AppState.create([], '@source')
        app.state.show_help = True
        for width in (36, 40):
            layout = compute_layout(width, 12)
            for offset in (0, 12):
                app.help_offset = offset
                screen = Mock()
                with patch('scripts.switcher.app.curses.color_pair', return_value=0):
                    app._render_help(screen, layout)
                lines = [c.args[2].rstrip() for c in screen.addstr.call_args_list]
                self.assertTrue(all(str_cell_width(line) <= layout.inner_w for line in lines))
                self.assertTrue(all(not line.endswith(('；', '·', '：', '/', 'E', 'Ent', 'Ctrl-'))
                                    for line in lines), (width, offset, lines))
                if offset == 0:
                    self.assertTrue(any('跨会话' in line for line in lines), lines)
                else:
                    self.assertTrue(any('清除过滤' in line for line in lines), lines)

    def test_no_results_hint_matches_available_keys_in_each_mode(self):
        from unittest.mock import Mock, patch
        from scripts.switcher.app import SwitcherApp
        from scripts.switcher.state import AppState, Mode
        from scripts.switcher.render import compute_layout
        app = SwitcherApp(Mock())
        app.state = AppState.create([], '@source')
        app.state.query = 'ZZZ'
        layout = compute_layout(80, 15)
        def message():
            screen = Mock()
            with patch('scripts.switcher.app.curses.color_pair', return_value=0):
                app._render_list(screen, layout)
            return ' '.join(c.args[2] for c in screen.addstr.call_args_list)
        app.state.mode = Mode.SEARCH
        self.assertIn('Backspace', message())
        app._handle_input(27)  # Esc keeps query but returns to browse
        self.assertEqual(app.state.mode, Mode.BROWSE)
        self.assertIn('Ctrl-u', message())
        self.assertNotIn('Backspace', message())
        self.assertFalse(app._handle_input(21))
        self.assertEqual(app.state.query, '')

    def test_cjk_window_name_keeps_pane_count_inside_list(self):
        from unittest.mock import Mock, patch
        from scripts.switcher.app import SwitcherApp
        from scripts.switcher.model import Window, Pane, SessionGroup
        from scripts.switcher.state import AppState
        from scripts.switcher.render import compute_layout, str_cell_width
        pane = Pane('%2', 0, '', 'bash', '/tmp', 1, True, 80, 20, 0, 0)
        src = Window('main', '$1', '1', '@1', 0, 'shell', True, False, True, '%1', 'bash', '/tmp', [pane])
        dst = Window('测试组', '$2', '2', '@2', 2, '测试中文窗名称很长', True, False, False,
                     '%2', 'bash', '/home/user/很长的目录名称', [pane, pane, pane])
        app = SwitcherApp(Mock())
        app.state = AppState.create([SessionGroup('main', '$1', '1', [src]),
                                     SessionGroup('测试组', '$2', '2', [dst])], '@1', '@2')
        layout = compute_layout(40, 20)
        screen = Mock()
        with patch('scripts.switcher.app.curses.color_pair', return_value=0):
            app._render_list(screen, layout)
        row = next(c.args[2] for c in screen.addstr.call_args_list if '2.2' in c.args[2])
        self.assertIn('3P', row)
        self.assertLessEqual(str_cell_width(row), layout.list_w)
        self.assertEqual(str_cell_width(row[:row.index('3P')]), layout.list_w - 3)
        for columns in (36, 40, 80, 100, 120):
            current_layout = compute_layout(columns, 20)
            current_screen = Mock()
            with patch('scripts.switcher.app.curses.color_pair', return_value=0):
                app._render_list(current_screen, current_layout)
            drawn = next(c.args[2] for c in current_screen.addstr.call_args_list if '2.2' in c.args[2])
            self.assertTrue(drawn.strip().endswith('3P'), (columns, drawn))
            self.assertLessEqual(str_cell_width(drawn), current_layout.list_w)

    def test_wide_content_is_scaled_to_canvas_with_ellipsis(self):
        # Long lines must be narrowed to fit, keeping line endings visible,
        # instead of being hard-truncated so half the pane content disappears.
        from unittest.mock import Mock
        from scripts.switcher.canvas import render_panes_to_canvas
        from scripts.switcher.model import Pane
        pane = Pane('%1', 0, '', 'bash', '/tmp', 1, True, 200, 10, 0, 0)
        content = {pane.pane_id: [f'README-{n}-abcdefghijklmnopqrstuvwxyz0123456789' for n in range(10)]}
        canvas = render_panes_to_canvas([pane], 40, 10, content)
        self.assertEqual(len(canvas), 10)
        self.assertTrue(all(len(row) == 40 for row in canvas))
        # Right edge keeps the tail of each line.
        self.assertTrue(all(row.rstrip().endswith('89') for row in canvas), canvas[0])
        # Nothing beyond the canvas width leaks.
        self.assertTrue(all(len(row) <= 40 for row in canvas))

    def test_preview_header_identifies_target_and_mode(self):
        from unittest.mock import Mock, patch
        from scripts.switcher.app import SwitcherApp
        from scripts.switcher.model import Window, Pane, SessionGroup
        from scripts.switcher.state import AppState
        from scripts.switcher.render import compute_layout
        pane = Pane('%5', 5, '', 'bash', '/tmp', 1, True, 80, 20, 0, 0)
        src = Window('main', '$1', '1', '@1', 0, 'shell', True, False, True, '%1', 'bash', '/tmp', [pane])
        dst = Window('other', '$2', '2', '@2', 2, 'build', True, False, False, '%5', 'bash', '/tmp', [pane])
        app = SwitcherApp(Mock())
        app.adapter.capture_pane.return_value = []
        app.state = AppState.create([SessionGroup('main', '$1', '1', [src]),
                                     SessionGroup('other', '$2', '2', [dst])], '@1', '@2')
        layout = compute_layout(120, 30, preview_pct=52)
        screen = Mock()
        with patch('scripts.switcher.app.curses.color_pair', return_value=0):
            app._render_preview(screen, layout)
        header = ' '.join(c.args[2] for c in screen.addstr.call_args_list if c.args[0] == layout.body_top_y)
        self.assertIn('2.2', header)
        self.assertIn('build', header)
        self.assertIn('1 Pane', header)
        app.state.preview_detail_mode = True
        detail = Mock()
        with patch('scripts.switcher.app.curses.color_pair', return_value=0):
            app._render_preview(detail, layout)
        header = ' '.join(c.args[2] for c in detail.addstr.call_args_list if c.args[0] == layout.body_top_y)
        self.assertIn('Pane 5', header)

    def test_narrow_footer_keeps_complete_shortcuts_in_each_mode(self):
        from unittest.mock import Mock, patch
        from scripts.switcher.app import SwitcherApp
        from scripts.switcher.state import AppState, Mode
        from scripts.switcher.render import compute_layout, str_cell_width
        app = SwitcherApp(Mock())
        app.state = AppState.create([], '@source')
        for width in (36, 40):
            layout = compute_layout(width, 12)
            for mode, is_help, expected in (
                (Mode.SEARCH, False, ('搜索', 'Esc 返回')),
                (Mode.LOCATE, False, ('定位', 'Esc 取消')),
                (Mode.BROWSE, True, ('帮助', 'Esc 返回')),
            ):
                app.state.mode = mode
                app.state.show_help = is_help
                screen = Mock()
                with patch('scripts.switcher.app.curses.color_pair', return_value=0):
                    app._render_frame(screen, layout)
                footer = ''.join(c.args[2] for c in screen.addstr.call_args_list
                                 if c.args[:2] == (layout.help_y, layout.help_x))
                self.assertLessEqual(str_cell_width(footer), layout.help_w)
                for phrase in expected:
                    self.assertIn(phrase, footer, (width, mode, footer))

    def test_hidden_preview_keys_report_why_and_do_not_mutate_detail(self):
        from unittest.mock import Mock
        from scripts.switcher.app import SwitcherApp
        from scripts.switcher.model import Window, Pane, SessionGroup
        from scripts.switcher.state import AppState
        from scripts.switcher.render import compute_layout
        pane = Pane('%2', 0, '', 'bash', '/tmp', 1, True, 80, 20, 0, 0)
        src = Window('s1', '$1', '1', '@1', 0, 'source', True, False, True, '%1', 'bash', '/tmp', [pane])
        dst = Window('s2', '$2', '2', '@2', 1, 'target', True, False, False, '%2', 'bash', '/tmp', [pane, pane])
        app = SwitcherApp(Mock())
        app.state = AppState.create([SessionGroup('s1', '$1', '1', [src]),
                                     SessionGroup('s2', '$2', '2', [dst])], '@1', '@2')
        app.current_layout = compute_layout(80, 20, show_preview=True)
        self.assertFalse(app.current_layout.show_preview)
        for key in (ord('v'), ord('['), ord(']')):
            self.assertFalse(app._handle_input(key))
            self.assertIn('预览', app.state.status_msg)
            self.assertFalse(app.state.preview_detail_mode)
            self.assertEqual(app.state.selected_pane_idx, 0)

    def test_footer_guides_current_mode_and_prioritizes_errors(self):
        from unittest.mock import Mock, patch
        from scripts.switcher.app import SwitcherApp
        from scripts.switcher.state import AppState, Mode
        from scripts.switcher.render import compute_layout, str_cell_width
        app = SwitcherApp(Mock())
        app.state = AppState.create([], '@source')
        layout = compute_layout(80, 20)

        def footer():
            screen = Mock()
            with patch('scripts.switcher.app.curses.color_pair', return_value=0):
                app._render_frame(screen, layout)
            text = ' '.join(c.args[2] for c in screen.addstr.call_args_list
                            if c.args[0] == layout.help_y)
            self.assertLessEqual(str_cell_width(text.strip()), layout.help_w)
            return text

        app.state.mode = Mode.SEARCH
        self.assertIn('Esc', footer())
        self.assertIn('Backspace', footer())
        app.state.mode = Mode.LOCATE
        self.assertIn('精确', footer())
        app.state.mode = Mode.BROWSE
        app.state.status_msg = '目标窗口已被删除，请刷新列表'
        self.assertIn('目标窗口已被删除', footer())

    def test_blank_preview_explains_snapshot_and_preserves_target(self):
        from unittest.mock import Mock, patch
        from scripts.switcher.app import SwitcherApp
        from scripts.switcher.model import Window, Pane, SessionGroup
        from scripts.switcher.state import AppState
        from scripts.switcher.render import compute_layout
        pane = Pane('%5', 0, '', 'bash', '/tmp', 1, True, 80, 20, 0, 0)
        src = Window('main', '$1', '1', '@1', 0, 'shell', True, False, True, '%1', 'bash', '/tmp', [pane])
        dst = Window('other', '$2', '2', '@2', 2, 'build', True, False, False, '%5', 'bash', '/tmp', [pane])
        app = SwitcherApp(Mock())
        app.adapter.capture_pane.return_value = []
        app.state = AppState.create([SessionGroup('main', '$1', '1', [src]),
                                     SessionGroup('other', '$2', '2', [dst])], '@1', '@2')
        layout = compute_layout(120, 20, preview_pct=52)
        screen = Mock()
        with patch('scripts.switcher.app.curses.color_pair', return_value=0):
            app._render_preview(screen, layout)
        text = ' '.join(c.args[2] for c in screen.addstr.call_args_list)
        self.assertIn('当前没有可显示的终端输出', text)
        self.assertIn('Enter', text)

    def test_empty_preview_never_draws_outside_body_at_short_heights(self):
        from unittest.mock import Mock, patch
        from scripts.switcher.app import SwitcherApp
        from scripts.switcher.model import Window, Pane, SessionGroup
        from scripts.switcher.state import AppState
        from scripts.switcher.render import compute_layout, str_cell_width
        pane = Pane('%2', 0, '', 'bash', '/tmp', 1, True, 80, 20, 0, 0)
        src = Window('one', '$1', '1', '@1', 0, 'shell', True, False, True, '%1', 'bash', '/tmp', [pane])
        dst = Window('two', '$2', '2', '@2', 1, 'build', True, False, False, '%2', 'bash', '/tmp', [pane])
        app = SwitcherApp(Mock())
        app.adapter.capture_pane.return_value = []
        app.state = AppState.create([SessionGroup('one', '$1', '1', [src]),
                                     SessionGroup('two', '$2', '2', [dst])], '@1', '@2')
        for height in (8, 9, 10, 11, 15):
            layout = compute_layout(108, height, preview_pct=60)
            screen = Mock()
            with patch('scripts.switcher.app.curses.color_pair', return_value=0):
                app._render_preview(screen, layout)
            for call in screen.addstr.call_args_list:
                y, x, text = call.args[:3]
                self.assertLessEqual(layout.body_top_y, y, (height, text))
                self.assertLessEqual(y, layout.body_bottom_y, (height, text))
                self.assertLessEqual(layout.preview_x, x, (height, text))
                self.assertLessEqual(x + str_cell_width(text), layout.preview_x + layout.preview_w,
                                     (height, text))

    def test_short_help_page_scrolls_to_hidden_commands(self):
        from unittest.mock import Mock, patch
        from scripts.switcher.app import SwitcherApp
        from scripts.switcher.state import AppState
        from scripts.switcher.render import compute_layout
        app = SwitcherApp(Mock())
        app.state = AppState.create([], '@source')
        app.state.show_help = True
        layout = compute_layout(70, 11)
        def help_lines():
            screen = Mock()
            with patch('scripts.switcher.app.curses.color_pair', return_value=0):
                app._render_help(screen, layout)
            return ' '.join(c.args[2] for c in screen.addstr.call_args_list)
        self.assertNotIn('Ctrl-r / Ctrl-u', help_lines())
        for _ in range(8):
            self.assertFalse(app._handle_input(ord('j')))
        self.assertIn('Ctrl-r / Ctrl-u', help_lines())
        self.assertFalse(app._handle_input(27))
        self.assertFalse(app.state.show_help)

    def test_frame_lines_join_at_outer_border(self):
        from unittest.mock import Mock, patch
        from scripts.switcher.app import SwitcherApp
        from scripts.switcher.state import AppState
        from scripts.switcher.render import compute_layout
        app = SwitcherApp(Mock())
        app.state = AppState.create([], '@source')
        layout = compute_layout(120, 20)
        screen = Mock()
        with patch('scripts.switcher.app.curses.color_pair', return_value=0):
            app._render_frame(screen, layout)
        top_y, bottom_y = 2, layout.help_y - 1
        for y in (top_y, bottom_y):
            drawn = [c.args[2] for c in screen.addstr.call_args_list if c.args[:2] == (y, 0)]
            self.assertIn('├', drawn)
            drawn = [c.args[2] for c in screen.addstr.call_args_list if c.args[:2] == (y, layout.total_w - 1)]
            self.assertIn('┤', drawn)

    def test_search_query_shows_newest_characters_in_top_line(self):
        from unittest.mock import Mock, patch
        from scripts.switcher.app import SwitcherApp
        from scripts.switcher.state import AppState, Mode
        from scripts.switcher.render import compute_layout
        app = SwitcherApp(Mock())
        app.state = AppState.create([], '@source')
        app.state.mode = Mode.SEARCH
        app.state.query = 'abcdefghijklmnopq' * 5 + '终点'
        layout = compute_layout(40, 15)
        screen = Mock()
        with patch('scripts.switcher.app.curses.color_pair', return_value=0):
            app._render_frame(screen, layout)
        line = ' '.join(c.args[2] for c in screen.addstr.call_args_list if c.args[0] == layout.input_y)
        self.assertIn('终点', line)
        self.assertIn('搜索', line)

    def test_help_open_does_not_navigate_or_delete_underneath(self):
        from unittest.mock import Mock
        from scripts.switcher.app import SwitcherApp
        from scripts.switcher.model import Window, SessionGroup
        from scripts.switcher.state import AppState
        src = Window('main', '$1', '1', '@1', 0, 'source', True, False, True, '%1', 'bash', '/tmp')
        a = Window('main', '$1', '1', '@2', 1, 'A', False, False, False, '%2', 'bash', '/tmp')
        b = Window('main', '$1', '1', '@3', 2, 'B', False, False, False, '%3', 'bash', '/tmp')
        adapter = Mock()
        app = SwitcherApp(adapter)
        app.state = AppState.create([SessionGroup('main', '$1', '1', [src, a, b])], '@1', '@2')
        app.state.show_help = True
        for ch in (ord('j'), ord('k'), 24, 10):
            self.assertFalse(app._handle_input(ch))
        self.assertEqual(app.state.selected_window_id, '@2')
        adapter.kill_window.assert_not_called()
        adapter.switch_client.assert_not_called()

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
