"""Curses-based full-width switcher terminal UI application."""
import curses
import os
import sys
import argparse
from typing import Optional, List, Dict
from scripts.switcher.model import LayoutInfo, Window, SessionGroup
from scripts.switcher.state import AppState, Mode
from scripts.switcher.render import compute_layout, format_path, str_cell_width, truncate_cell
from scripts.switcher.canvas import render_panes_to_canvas, sanitize_text_line
from scripts.switcher.tmux import TmuxAdapter

class SwitcherApp:
    def __init__(self, adapter: TmuxAdapter):
        self.adapter = adapter
        self.state: Optional[AppState] = None
        self.pane_cache: Dict[str, List[str]] = {}

    def init_state(self):
        groups, src_wid = self.adapter.get_snapshot()
        self.state = AppState.create(groups, source_window_id=src_wid)

    def run(self, stdscr):
        curses.curs_set(0) # Hide cursor
        stdscr.keypad(True)
        curses.use_default_colors()

        # Initialize color pairs
        # 1: Normal border/dim
        # 2: Highlight/active
        # 3: Selected row
        # 4: Current window (dimmed)
        # 5: Help/footer
        # 6: Header / Mode label
        try:
            curses.init_pair(1, curses.COLOR_BLUE, -1)
            curses.init_pair(2, curses.COLOR_CYAN, -1)
            curses.init_pair(3, curses.COLOR_BLACK, curses.COLOR_CYAN)
            curses.init_pair(4, curses.COLOR_WHITE, -1)
            curses.init_pair(5, curses.COLOR_MAGENTA, -1)
            curses.init_pair(6, curses.COLOR_YELLOW, -1)
        except Exception:
            pass

        self.init_state()

        while True:
            stdscr.clear()
            h, w = stdscr.getmaxyx()
            if h < 8 or w < 20:
                stdscr.addstr(0, 0, "Terminal too small")
                stdscr.refresh()
                ch = stdscr.getch()
                if ch in (ord('q'), 27):
                    break
                continue

            layout = compute_layout(w, h, preview_pct=55, show_preview=self.state.show_preview)
            self._render_frame(stdscr, layout)
            stdscr.refresh()

            ch = stdscr.getch()
            if ch == -1:
                continue

            # Process key
            if self._handle_input(ch):
                break

    def _render_frame(self, stdscr, layout: LayoutInfo):
        # 1. Outer Border
        try:
            stdscr.border()
        except Exception:
            pass

        # Title at top border
        title = " tmux window switcher "
        try:
            stdscr.addstr(0, max(2, (layout.total_w - len(title)) // 2), title, curses.A_BOLD | curses.color_pair(2))
        except Exception:
            pass

        # 2. Top Mode and Input line (y=1)
        mode_str = f"[{self.state.mode.name}] "
        if self.state.mode == Mode.SEARCH:
            input_content = f"🔍 / {self.state.query}"
        elif self.state.mode == Mode.LOCATE:
            input_content = f"🎯 : {self.state.locate_buf}"
        else:
            if self.state.query:
                input_content = f"Filter: {self.state.query}  (Ctrl-u to clear)"
            else:
                input_content = "Type '/' to search, '1-9' or ':' to locate, '?' for help"

        line1 = f" {mode_str}{input_content}"
        line1_truncated = truncate_cell(line1, layout.input_w)
        try:
            stdscr.addstr(layout.input_y, layout.input_x, line1_truncated, curses.A_BOLD)
        except Exception:
            pass

        # Horizontal separator below input (y=2)
        try:
            stdscr.addstr(2, 1, "─" * layout.inner_w, curses.color_pair(1))
        except Exception:
            pass

        # 3. Body: Window List (left)
        self._render_list(stdscr, layout)

        # Divider between list and preview
        if layout.show_preview and layout.divider_x > 0:
            for y in range(layout.divider_top_y, layout.divider_bottom_y + 1):
                try:
                    stdscr.addch(y, layout.divider_x, '│', curses.color_pair(1))
                except Exception:
                    pass

        # 4. Body: Preview (right)
        if layout.show_preview and layout.preview_w > 0:
            self._render_preview(stdscr, layout)

        # Separator above help line (y = layout.help_y - 1)
        sep_y = layout.help_y - 1
        try:
            stdscr.addstr(sep_y, 1, "─" * layout.inner_w, curses.color_pair(1))
        except Exception:
            pass

        # 5. Full-width single help line OUTSIDE both body boxes (y = layout.help_y)
        # Spec clause 17:
        # "full-width final single help line OUTSIDE both body boxes; divider ends ABOVE help.
        # Footer text adaptive abbreviated for narrow screens; ? complete help. Entire help line never clipped mid-word"
        if self.state.show_help:
            help_text = " [Enter]Switch [Tab]Last [-] [J/K]Session [^x]Kill [^p]Preview [v]Detail [/]Search [Esc]Back [q]Exit "
        elif self.state.status_msg:
            help_text = f" ! {self.state.status_msg} "
        else:
            if layout.help_w >= 100:
                help_text = " [Enter] Switch  [Tab] Last [-]  [j/k] Nav  [J/K] Session  [^x] Kill  [^p] Preview  [?] Help  [q] Exit "
            elif layout.help_w >= 60:
                help_text = " [Enter]Switch [Tab]Last [j/k]Nav [J/K]Sess [^x]Kill [?]Help [q]Exit "
            else:
                help_text = " Enter:Go Tab:Last J/K:Sess ?:Help q:Exit "

        try:
            stdscr.addstr(layout.help_y, layout.help_x, truncate_cell(help_text, layout.help_w), curses.color_pair(5))
        except Exception:
            pass

    def _render_list(self, stdscr, layout: LayoutInfo):
        # Render sessions and windows within body_top_y..body_bottom_y
        max_rows = layout.body_bottom_y - layout.body_top_y + 1
        if max_rows <= 0:
            return

        eligible = self.state.get_eligible_windows()
        selected_wid = self.state.selected_window_id

        # Build display lines
        # Each line: (type, text, is_selected, is_current, window_obj)
        display_lines = []
        for g in self.state.groups:
            # Check if this group has any eligible or current windows
            matching_in_g = [w for w in g.windows if w in eligible or w.is_current]
            if not matching_in_g:
                continue

            header_str = f"► [{g.session_alias}] {g.session_name} ({len(g.windows)} win)"
            display_lines.append(('HEADER', header_str, False, False, None))

            for w in g.windows:
                if w not in eligible and not w.is_current:
                    continue
                # Marker: * current, - last, space otherwise
                marker = "*" if w.is_current else ("-" if w.is_last else " ")
                # Format: coordinate (alias.index), name, path
                coord = f"{w.session_alias}.{w.window_index}"
                # Path formatted
                p_path = format_path(w.active_pane_path, 20)
                w_str = f" {marker}  {coord:<5} {w.window_name:<12} {p_path}"
                is_sel = (w.window_id == selected_wid)
                display_lines.append(('WINDOW', w_str, is_sel, w.is_current, w))

        # Viewport scrolling: keep selected line in view
        sel_idx = 0
        for i, item in enumerate(display_lines):
            if item[2]: # is_selected
                sel_idx = i
                break

        scroll_offset = 0
        if sel_idx >= max_rows:
            scroll_offset = sel_idx - max_rows + 1

        for r in range(max_rows):
            line_idx = scroll_offset + r
            if line_idx >= len(display_lines):
                break
            l_type, l_text, is_sel, is_cur, _ = display_lines[line_idx]
            y = layout.body_top_y + r
            x = layout.list_x
            text_to_draw = truncate_cell(l_text, layout.list_w)
            # Pad
            text_to_draw = text_to_draw + " " * max(0, layout.list_w - str_cell_width(text_to_draw))

            attr = curses.A_NORMAL
            if l_type == 'HEADER':
                attr = curses.A_BOLD | curses.color_pair(2)
            elif is_sel:
                attr = curses.A_BOLD | curses.color_pair(3)
            elif is_cur:
                attr = curses.A_DIM | curses.color_pair(4)

            try:
                stdscr.addstr(y, x, text_to_draw, attr)
            except Exception:
                pass

    def _render_preview(self, stdscr, layout: LayoutInfo):
        w = self.state.selected_window
        if not w:
            return

        h = layout.body_bottom_y - layout.body_top_y + 1
        cw = layout.preview_w

        # Ensure pane contents cached
        for p in w.panes:
            if p.pane_id not in self.pane_cache:
                self.pane_cache[p.pane_id] = self.adapter.capture_pane(p.pane_id, num_lines=h + 10)

        # Header of preview: window info card
        header = f"[{w.session_name}:{w.window_index} - {w.window_name}] ({len(w.panes)} panes)"
        try:
            stdscr.addstr(layout.body_top_y, layout.preview_x, truncate_cell(header, cw), curses.A_BOLD | curses.color_pair(6))
        except Exception:
            pass

        canvas_h = max(1, h - 1)
        # Check if single pane detail mode is requested
        if self.state.preview_detail_mode and w.panes:
            # Render only selected pane
            idx = self.state.selected_pane_idx % len(w.panes)
            p = w.panes[idx]
            canvas_lines = render_panes_to_canvas([p], cw, canvas_h, self.pane_cache)
        else:
            canvas_lines = render_panes_to_canvas(w.panes, cw, canvas_h, self.pane_cache)

        for r, cline in enumerate(canvas_lines):
            y = layout.body_top_y + 1 + r
            if y > layout.body_bottom_y:
                break
            try:
                stdscr.addstr(y, layout.preview_x, cline)
            except Exception:
                pass

    def _handle_input(self, ch: int) -> bool:
        """Handle key input. Returns True if application should exit."""
        # Key conversions
        if ch == 27: # Escape
            if self.state.mode == Mode.SEARCH:
                self.state.mode = Mode.BROWSE
            elif self.state.mode == Mode.LOCATE:
                self.state.locate_buf = ""
                self.state.mode = Mode.BROWSE
            else:
                return True # Quit from browse
            return False

        if ch == ord('q') and self.state.mode == Mode.BROWSE:
            return True

        if ch in (curses.KEY_ENTER, 10, 13):
            # Accept selection
            if self.state.mode == Mode.LOCATE:
                target = self.state.resolve_locate_target()
                if target:
                    if target.window_id == self.state.source_window_id:
                        self.state.status_msg = "Cannot switch to source window"
                    else:
                        self.adapter.switch_client(target.window_id)
                        return True
                else:
                    self.state.status_msg = f"Target not found: {self.state.locate_buf}"
                return False
            else:
                target = self.state.selected_window
                if target and target.window_id != self.state.source_window_id:
                    self.adapter.switch_client(target.window_id)
                    return True
                return False

        # Detail mode toggle: 'v'
        if ch == ord('v') and self.state.mode == Mode.BROWSE:
            self.state.preview_detail_mode = not self.state.preview_detail_mode
            return False

        # Cycle preview pane in BROWSE: '[' / ']' when preview is active
        # Spec clause 14:
        # "[/] cycles preview pane in BROWSE without switching target active pane."
        if self.state.mode == Mode.BROWSE:
            if ch == ord('['):
                if self.state.selected_window and self.state.selected_window.panes:
                    n_panes = len(self.state.selected_window.panes)
                    self.state.selected_pane_idx = (self.state.selected_pane_idx - 1 + n_panes) % n_panes
                return False
            elif ch == ord(']'):
                if self.state.selected_window and self.state.selected_window.panes:
                    n_panes = len(self.state.selected_window.panes)
                    self.state.selected_pane_idx = (self.state.selected_pane_idx + 1) % n_panes
                return False

        # Ctrl-x (kill window)
        if ch == 24: # Ctrl-x
            if self.state.mode == Mode.BROWSE:
                if self.state.can_delete_selected():
                    wid_to_del = self.state.selected_window_id
                    ok, err = self.adapter.kill_window(wid_to_del, self.state.source_window_id)
                    if ok:
                        self.state.on_window_deleted(wid_to_del)
                    else:
                        self.state.status_msg = f"Kill error: {err}"
                else:
                    self.state.status_msg = "Delete disabled. Move selection first."
            return False

        # Ctrl-p (toggle preview)
        if ch == 16: # Ctrl-p
            self.state.show_preview = not self.state.show_preview
            return False

        # Ctrl-r (refresh)
        if ch == 18: # Ctrl-r
            self.init_state()
            self.pane_cache.clear()
            return False

        # Ctrl-u (clear query in browse)
        if ch == 21: # Ctrl-u
            self.state.query = ""
            return False

        # Convert to string key for state handler
        if ch == curses.KEY_DOWN:
            k = "KEY_DOWN"
        elif ch == curses.KEY_UP:
            k = "KEY_UP"
        elif ch == 9: # Tab
            k = "\t"
        elif ch in (curses.KEY_BACKSPACE, 127, 8):
            k = "KEY_BACKSPACE"
        elif 32 <= ch <= 126:
            k = chr(ch)
        else:
            k = ""

        if k:
            self.state.handle_key(k)

        return False

def main():
    parser = argparse.ArgumentParser(description="tmux window switcher")
    parser.add_argument("--socket", help="tmux socket path")
    parser.add_argument("--client", help="tmux client target")
    args = parser.parse_args()

    sock = args.socket or os.environ.get("TMUX_SOCKET")
    if not sock and "TMUX" in os.environ:
        sock = os.environ["TMUX"].split(",")[0]

    adapter = TmuxAdapter(socket_path=sock, client_target=args.client)
    app = SwitcherApp(adapter)
    curses.wrapper(app.run)

if __name__ == "__main__":
    main()
