"""Curses-based full-width switcher terminal UI application."""
import curses
import os
import sys
import json
import time
import hashlib
from typing import Optional, List, Dict, Tuple
from scripts.switcher.model import LayoutInfo, Window, SessionGroup
from scripts.switcher.state import AppState, Mode
from scripts.switcher.render import compute_layout, format_path, str_cell_width, truncate_cell
from scripts.switcher.canvas import render_panes_to_canvas, sanitize_text_line
from scripts.switcher.tmux import TmuxAdapter

# Exit code signalling the launcher to reopen the popup at the new client size.
RESIZE_EXIT_CODE = 42
# Fast poll interval (ms) for responsive debounce without noticeable latency.
RESIZE_POLL_MS = 100


def state_file_path(client_target: str) -> str:
    h = hashlib.sha256((client_target or "default").encode()).hexdigest()[:16]
    return f"/tmp/.tmux_switch_state_{h}.json"


def save_transient_state(client_target: str, data: dict):
    if not client_target:
        return
    path = state_file_path(client_target)
    try:
        tmp_path = path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(tmp_path, path)
    except Exception:
        pass


def load_transient_state(client_target: str) -> Optional[dict]:
    if not client_target:
        return None
    path = state_file_path(client_target)
    if not os.path.exists(path):
        return None
    try:
        if time.time() - os.path.getmtime(path) > 5.0:
            os.remove(path)
            return None
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        os.remove(path)
        return data
    except Exception:
        return None


def compute_frame_box(total_w: int, total_h: int, scale: float) -> Tuple[int, int, int, int]:
    scale = max(0.1, min(1.0, scale))
    w = max(10, int(total_w * scale))
    h = max(4, int(total_h * scale))
    x = max(0, (total_w - w) // 2)
    y = max(0, (total_h - h) // 2)
    return x, y, w, h


def play_opening_animation(stdscr, target_w: int, target_h: int):
    """Play a lightweight, smooth 2-frame scale-out animation on initial open (~40ms)."""
    if target_w < 40 or target_h < 12:
        return
    if os.environ.get("TMUX_SWITCH_NO_ANIM") == "1":
        return

    border_attr = curses.color_pair(1) if curses.has_colors() else curses.A_NORMAL
    steps = [0.65, 0.88]
    for scale in steps:
        bx, by, bw, bh = compute_frame_box(target_w, target_h, scale)
        stdscr.erase()
        try:
            stdscr.addstr(by, bx, "╭" + "─" * (bw - 2) + "╮", border_attr)
            for row in range(1, bh - 1):
                stdscr.addstr(by + row, bx, "│", border_attr)
                stdscr.addstr(by + row, bx + bw - 1, "│", border_attr)
            stdscr.addstr(by + bh - 1, bx, "╰" + "─" * (bw - 2) + "╯", border_attr)
        except curses.error:
            pass
        stdscr.refresh()
        curses.napms(20)


def popup_size_for_client(client_w: int, client_h: int) -> Tuple[int, int]:
    """Popup (w, h) for a client size; mirrors the thresholds in switch.sh."""
    if client_w >= 220:
        popup_w = client_w * 55 // 100
        popup_w = min(popup_w, 165)
        popup_w = max(popup_w, 135)
    elif client_w >= 140:
        popup_w = client_w * 75 // 100
    else:
        popup_w = client_w * 90 // 100

    if client_h >= 60:
        popup_h = client_h * 72 // 100
    elif client_h >= 35:
        popup_h = client_h * 78 // 100
    else:
        popup_h = client_h - 2
        popup_h = max(popup_h, 14)
    return (popup_w, popup_h)


class SwitcherApp:
    def __init__(self, adapter: TmuxAdapter):
        self.adapter = adapter
        self.state: Optional[AppState] = None
        self.pane_cache: Dict[str, List[str]] = {}
        # Popup size this process was launched with; None disables resize polling.
        self.popup_size: Optional[Tuple[int, int]] = None
        self.is_resumed: bool = False
        self.pending_resize_target: Optional[Tuple[int, int]] = None
        self.has_played_open_anim: bool = False

    def _handle_resize(self) -> bool:
        """True when the client was resized, stabilized (debounced), and should reopen."""
        if self.popup_size is None:
            return False
        cw, ch = self.adapter.get_client_size()
        if cw <= 0 or ch <= 0:
            return False
        new_target = popup_size_for_client(cw, ch)
        if new_target == self.popup_size:
            self.pending_resize_target = None
            return False

        # Debounce: wait for client dimension to stabilize across 2 consecutive polls (~100-200ms)
        if self.pending_resize_target == new_target:
            # Dimension stabilized: save state to RAM and signal launcher to reopen smoothly
            if self.state and self.adapter.client_target:
                save_transient_state(self.adapter.client_target, self.state.dump_state())
            return True
        else:
            self.pending_resize_target = new_target
            return False

    def init_state(self):
        groups, src_wid = self.adapter.get_snapshot()
        return_id = self.adapter.get_return_window_id() if self.adapter.client_target else None
        self.state = AppState.create(groups, source_window_id=src_wid, return_window_id=return_id)
        # Restore transient state if reopening from a window resize
        if self.adapter.client_target:
            saved = load_transient_state(self.adapter.client_target)
            if saved:
                self.state.restore_state(saved)
                self.is_resumed = True

    def run(self, stdscr):
        curses.curs_set(0) # Hide cursor
        stdscr.keypad(True)
        curses.use_default_colors()
        # Poll client size while idle so the popup can follow client resize.
        if self.popup_size is not None:
            stdscr.timeout(RESIZE_POLL_MS)

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

        # Play smooth open scale animation only on fresh launch, not during resize transitions
        if not self.is_resumed and not self.has_played_open_anim:
            init_h, init_w = stdscr.getmaxyx()
            play_opening_animation(stdscr, init_w, init_h)
            self.has_played_open_anim = True

        while True:
            # Avoid stdscr.clear() to eliminate full-terminal flicker; redraw lines cleanly
            stdscr.erase()
            h, w = stdscr.getmaxyx()
            if h < 8 or w < 20:
                stdscr.addstr(0, 0, "Terminal too small")
                stdscr.refresh()
                ch = stdscr.getch()
                if ch in (ord('q'), 27):
                    break
                if ch == -1 and self._handle_resize():
                    sys.exit(RESIZE_EXIT_CODE)
                continue

            layout = compute_layout(w, h, preview_pct=60, show_preview=self.state.show_preview)
            self._render_frame(stdscr, layout)
            stdscr.refresh()

            ch = stdscr.getch()
            if ch == -1:
                # Idle timeout: check whether the client was resized; if so,
                # exit with RESIZE_EXIT_CODE so the launcher reopens the popup
                # at the new size (tmux popups never follow client resize).
                if self._handle_resize():
                    sys.exit(RESIZE_EXIT_CODE)
                continue

            # Process key
            if self._handle_input(ch):
                break

    def _render_frame(self, stdscr, layout: LayoutInfo):
        # 1. Outer Border with rounded corners (╭, ╮, ╰, ╯)
        w = layout.total_w
        h = layout.total_h
        border_attr = curses.color_pair(1)

        try:
            # Top line: ╭ + ─*(w-2) + ╮
            stdscr.addstr(0, 0, "╭" + "─" * (w - 2) + "╮", border_attr)
            # Side lines: │
            for y in range(1, h - 1):
                stdscr.addstr(y, 0, "│", border_attr)
                stdscr.addstr(y, w - 1, "│", border_attr)
            # Bottom line: ╰ + ─*(w-2)
            stdscr.addstr(h - 1, 0, "╰" + "─" * (w - 2), border_attr)
            try:
                # Bottom right corner (last cell of screen may raise curses error if auto-advance)
                stdscr.addstr(h - 1, w - 1, "╯", border_attr)
            except curses.error:
                pass
        except Exception:
            try:
                stdscr.border()
            except Exception:
                pass

        # Title at top border
        title = " tmux window switcher "
        try:
            stdscr.addstr(0, max(2, (w - len(title)) // 2), title, curses.A_BOLD | curses.color_pair(2))
        except Exception:
            pass

        # 2. Top Mode and Input line (y=1)
        mode_label = {Mode.BROWSE: "浏览", Mode.SEARCH: "搜索", Mode.LOCATE: "定位"}[self.state.mode]
        mode_str = f"[{mode_label}] "
        if self.state.mode == Mode.SEARCH:
            input_content = f"/ {self.state.query}"
        elif self.state.mode == Mode.LOCATE:
            input_content = self.state.locate_buf
        else:
            if self.state.query:
                input_content = f"过滤: {self.state.query}  (Ctrl-u 清除)"
            else:
                input_content = "/ 搜索 · 数字或 : 定位 · ? 帮助"

        count = len(self.state.get_eligible_windows())
        badge = f"{count} 项"
        avail_w = max(0, layout.input_w - str_cell_width(badge) - 1)
        left_str = truncate_cell(f" {mode_str}{input_content}", avail_w)
        pad = " " * max(0, layout.input_w - str_cell_width(left_str) - str_cell_width(badge))
        line1 = f"{left_str}{pad}{badge}"
        try:
            stdscr.addstr(layout.input_y, layout.input_x, line1, curses.A_BOLD)
        except Exception:
            pass

        # Horizontal separator below input (y=2)
        try:
            stdscr.addstr(2, 1, "─" * layout.inner_w, curses.color_pair(1))
        except Exception:
            pass

        # 3. Body: Window List (left)
        self._render_list(stdscr, layout)

        # 4. Body: Preview (right)
        if layout.show_preview and layout.preview_w > 0:
            self._render_preview(stdscr, layout)

        # Divider between list and preview (with neat T-junctions ┬ and ┴)
        if layout.show_preview and layout.divider_x > 0:
            # Top junction with input separator line (y=2)
            try:
                stdscr.addstr(2, layout.divider_x, "┬", curses.color_pair(1))
            except Exception:
                pass
            # Vertical line through body
            for y in range(layout.divider_top_y, layout.divider_bottom_y + 1):
                try:
                    stdscr.addstr(y, layout.divider_x, "│", curses.color_pair(1))
                except Exception:
                    pass
            # Bottom junction with footer separator line (y = layout.help_y - 1)
            try:
                stdscr.addstr(layout.help_y - 1, layout.divider_x, "┴", curses.color_pair(1))
            except Exception:
                pass

        # Place body separator outside body, immediately above the full-width help.
        sep_y = layout.help_y - 1
        try:
            stdscr.addstr(sep_y, 1, "─" * layout.inner_w, curses.color_pair(1))
            # Restore ┴ if separator line overwrote it
            if layout.show_preview and layout.divider_x > 0:
                stdscr.addstr(sep_y, layout.divider_x, "┴", curses.color_pair(1))
        except Exception:
            pass

        # 5. Full-width single help line OUTSIDE both body boxes (y = layout.help_y)
        # Spec clause 17:
        # "full-width final single help line OUTSIDE both body boxes; divider ends ABOVE help.
        # Footer text adaptive abbreviated for narrow screens; ? complete help. Entire help line never clipped mid-word"
        if self.state.show_help:
            help_text = " 帮助视图  ·  ? / Esc 返回 "
        elif self.state.status_msg:
            help_text = f" ! {self.state.status_msg} "
        elif self.state.mode == Mode.SEARCH:
            if layout.help_w >= 80:
                help_text = " [Enter] 确认切换  [↑/↓] 选择结果  [Backspace] 修改  [Esc] 返回浏览 "
            else:
                help_text = " Enter:切换 ↑/↓:选择 Backspace:修改 Esc:返回 "
        elif self.state.mode == Mode.LOCATE:
            if layout.help_w >= 80:
                help_text = " [Enter] 确认跳转  [2.2/:bios:2] 精确定位  [Backspace] 修改  [Esc] 取消定位 "
            else:
                help_text = " Enter:跳转 2.2/:name:idx 定位 Esc:取消 "
        else:
            if layout.help_w >= 100:
                help_text = " Enter 切换  J/K 跨会话  j/k 逐窗  / 搜索  ^x 直接删除  ? 帮助  q 退出 "
            elif layout.help_w >= 60:
                help_text = " Enter切换 J/K跨会话 j/k逐窗 /搜索 ^x删除 ?帮助 q退出 "
            else:
                help_text = " Enter切换 J/K会话 ?:帮助 q:退出 "

        try:
            stdscr.addstr(layout.help_y, layout.help_x, truncate_cell(help_text, layout.help_w), curses.color_pair(5))
        except Exception:
            pass

        if self.state.show_help:
            self._render_help(stdscr, layout)

    def _render_help(self, stdscr, layout: LayoutInfo):
        """Use the body as a readable help page; keep the footer full-width."""
        lines = [
            "操作帮助  ·  ? / Esc 返回",
            "j/k 或 ↑/↓    逐个窗口循环",
            "J/K             跨 Session；优先活动窗口",
            "Enter           切换选中窗口；直接返回上次位置",
            "/               搜索；Esc 保留过滤词",
            "数字 / :         精确定位：2.2 / :bios:2",
            "Ctrl-x          立即删除非源窗口；移动后可再次删除",
            "Ctrl-p / v      显隐预览 / 单 Pane 详情",
            "[ / ]           切换预览 Pane（不影响真实 Pane）",
            "Ctrl-r / Ctrl-u 刷新快照 / 清除过滤",
            "● 源窗口   ↩ 返回窗口   Tab 未绑定",
            "q / Esc         退出浏览",
        ]
        for i, text in enumerate(lines[:layout.body_bottom_y - layout.body_top_y + 1]):
            y = layout.body_top_y + i
            clipped = truncate_cell(text, layout.inner_w)
            stdscr.addstr(y, layout.inner_x,
                          clipped + " " * (layout.inner_w - str_cell_width(clipped)),
                          curses.color_pair(5))

    def _render_list(self, stdscr, layout: LayoutInfo):
        # The row above help is reserved for a full-width separator.
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

            header_str = f"[{g.session_alias}] {g.session_name}  ·  {len(g.windows)} windows"
            display_lines.append(('HEADER', header_str, False, False, None))

            for w in g.windows:
                if w not in eligible and not w.is_current:
                    continue
                is_sel = (w.window_id == selected_wid)
                focus_mark = "›" if is_sel else " "
                marker = "●" if w.is_current else ("↩" if w.window_id == self.state.return_window_id else " ")
                coord = f"{w.session_alias}.{w.window_index}"
                pane_label = f"{len(w.panes)}P"
                name_budget = max(8, min(18, layout.list_w // 4))
                name = truncate_cell(sanitize_text_line(w.window_name, name_budget), name_budget)
                fixed = f"{focus_mark}{marker} {coord:<6} {name:<{name_budget}} "
                path_budget = max(0, layout.list_w - str_cell_width(fixed) - str_cell_width(pane_label) - 2)
                path_text = format_path(sanitize_text_line(w.active_pane_path, 300), path_budget)
                w_str = f"{fixed}{path_text:<{path_budget}} {pane_label}"
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
            if self.state.show_help:
                self.state.show_help = False
            elif self.state.mode in (Mode.SEARCH, Mode.LOCATE):
                self.state.handle_key("ESC")
            else:
                return True
            return False

        if self.state.show_help:
            if ch == ord('?'):
                self.state.show_help = False
            return False

        if ch == ord('q') and self.state.mode == Mode.BROWSE:
            return True

        elif ch in (curses.KEY_ENTER, 10, 13):
            if self.state.mode == Mode.LOCATE:
                target = self.state.resolve_locate_target()
            else:
                target = self.state.selected_window if self.state.selected_window_id in {
                    w.window_id for w in self.state.get_eligible_windows()} else None
            if not target or target.window_id == self.state.source_window_id:
                self.state.status_msg = "No switchable target selected"
                return False
            ok, err = self.adapter.switch_client(target.window_id)
            if not ok:
                self.state.status_msg = f"Switch failed: {err}"
                return False
            try:
                if self.adapter.client_target:
                    self.adapter.set_return_window_id(self.state.source_window_id)
            except RuntimeError as exc:
                # The client already switched: report honestly, do not claim history was saved.
                self.state.status_msg = f"Switched, but return target was not saved: {exc}"
            return True

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
                        try:
                            fresh, src = self.adapter.get_snapshot()
                            if src != self.state.source_window_id:
                                self.state.status_msg = "Source changed; close and reopen"
                            else:
                                self.state.replace_groups(fresh)
                                self.pane_cache.clear()
                        except RuntimeError as exc:
                            self.state.status_msg = f"Deleted; refresh failed: {exc}"
                    else:
                        self.state.status_msg = f"Kill error: {err}"
                else:
                    self.state.status_msg = "Delete disabled. Move selection first."
            return False

        if ch == 16 and self.state.mode == Mode.BROWSE: # Ctrl-p
            self.state.show_preview = not self.state.show_preview
            return False

        if ch == 18 and self.state.mode == Mode.BROWSE: # Ctrl-r
            try:
                fresh, src = self.adapter.get_snapshot()
                if src != self.state.source_window_id:
                    self.state.status_msg = "Source changed; close and reopen"
                else:
                    self.state.replace_groups(fresh)
                    self.pane_cache.clear()
            except RuntimeError as exc:
                self.state.status_msg = f"Refresh failed: {exc}"
            return False

        if ch == 21 and self.state.mode == Mode.BROWSE: # Ctrl-u
            self.state.query = ""
            self.state.reconcile_selection()
            return False

        # Convert to string key for state handler
        if ch == curses.KEY_DOWN:
            k = "KEY_DOWN"
        elif ch == curses.KEY_UP:
            k = "KEY_UP"
        elif ch == 9 or ch == curses.KEY_BTAB: # Tab is intentionally unbound
            return False
        elif ch in (curses.KEY_BACKSPACE, 127, 8):
            k = "KEY_BACKSPACE"
        elif 32 <= ch <= 0x10ffff:
            try:
                k = chr(ch)
            except ValueError:
                k = ""
        else:
            k = ""

        if k:
            self.state.handle_key(k)

        return False

class SwitcherArgs:
    def __init__(self, socket: Optional[str] = None, client: Optional[str] = None,
                 popup_size: Optional[Tuple[int, int]] = None):
        self.socket = socket
        self.client = client
        self.popup_size = popup_size


def parse_args(argv: List[str]) -> SwitcherArgs:
    """Lightweight zero-dependency CLI argument parser (replaces heavy argparse)."""
    socket = None
    client = None
    popup_size = None

    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--socket" and i + 1 < len(argv):
            socket = argv[i + 1]
            i += 2
        elif arg == "--client" and i + 1 < len(argv):
            client = argv[i + 1]
            i += 2
        elif arg == "--popup-size" and i + 1 < len(argv):
            raw = argv[i + 1]
            try:
                pw, ph = raw.lower().split("x", 1)
                popup_size = (int(pw), int(ph))
            except ValueError:
                raise ValueError(f"Invalid --popup-size '{raw}', must look like 120x40")
            i += 2
        else:
            i += 1

    return SwitcherArgs(socket=socket, client=client, popup_size=popup_size)


def main():
    try:
        args = parse_args(sys.argv[1:])
    except ValueError as exc:
        sys.stderr.write(f"Error: {exc}\n")
        sys.exit(2)

    sock = args.socket or os.environ.get("TMUX_SOCKET")
    if not sock and "TMUX" in os.environ:
        sock = os.environ["TMUX"].split(",")[0]

    client = args.client or os.environ.get("TMUX_SWITCH_CLIENT")
    if not client:
        sys.stderr.write("Error: Explicit --client is required for per-client switch history\n")
        sys.exit(2)

    adapter = TmuxAdapter(socket_path=sock, client_target=client)
    app = SwitcherApp(adapter)
    if args.popup_size:
        app.popup_size = args.popup_size
    curses.wrapper(app.run)

if __name__ == "__main__":
    main()
