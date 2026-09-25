"""State machine and reducers for switcher."""
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional, Dict
from scripts.switcher.model import Window, SessionGroup

class Mode(Enum):
    BROWSE = auto()
    SEARCH = auto()
    LOCATE = auto()

@dataclass
class AppState:
    groups: List[SessionGroup]
    source_window_id: str
    mode: Mode = Mode.BROWSE
    query: str = ""
    locate_buf: str = ""
    show_preview: bool = True
    preview_detail_mode: bool = False # False = layout 2D, True = single-pane detail
    selected_pane_idx: int = 0
    show_help: bool = False
    status_msg: str = ""
    selected_window_id: Optional[str] = None
    pinned_last_window_id: Optional[str] = None
    delete_armed_window_id: Optional[str] = None # For Ctrl-x repeat guard

    # Session alias mapping preserved across filters
    session_aliases: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def create(cls, groups: List[SessionGroup], source_window_id: str) -> "AppState":
        state = cls(groups=groups, source_window_id=source_window_id)

        # Build stable session aliases: 1, 2, 3...
        for idx, g in enumerate(groups, start=1):
            state.session_aliases[g.session_name] = str(idx)
            g.session_alias = str(idx)
            for w in g.windows:
                w.session_alias = str(idx)

        # Pin last window from source session
        for g in groups:
            for w in g.windows:
                if w.is_last and w.session_id == getattr(state.source_group, "session_id", None):
                    state.pinned_last_window_id = w.window_id

        # Find initial selected window: pinned last window if switchable, else first switchable
        eligible = state.get_eligible_windows()
        if state.pinned_last_window_id:
            for w in eligible:
                if w.window_id == state.pinned_last_window_id:
                    state.selected_window_id = w.window_id
                    break
        if not state.selected_window_id and eligible:
            state.selected_window_id = eligible[0].window_id

        return state

    @property
    def source_group(self) -> Optional[SessionGroup]:
        for g in self.groups:
            for w in g.windows:
                if w.window_id == self.source_window_id:
                    return g
        return None

    def get_eligible_windows(self) -> List[Window]:
        """Return all switchable windows (excluding source window), matching query if filtered."""
        from scripts.switcher.fzf import fzf_filter_windows
        return fzf_filter_windows(self.groups, self.query, self.source_window_id)

    @property
    def selected_window(self) -> Optional[Window]:
        if not self.selected_window_id:
            return None
        for g in self.groups:
            for w in g.windows:
                if w.window_id == self.selected_window_id:
                    return w
        return None

    def handle_key(self, key: str):
        """Process a key event in current mode."""
        if self.mode == Mode.BROWSE:
            self._handle_browse_key(key)
        elif self.mode == Mode.SEARCH:
            self._handle_search_key(key)
        elif self.mode == Mode.LOCATE:
            self._handle_locate_key(key)

    def _handle_browse_key(self, key: str):
        eligible = self.get_eligible_windows()
        if not eligible:
            return

        cur_idx = -1
        for i, w in enumerate(eligible):
            if w.window_id == self.selected_window_id:
                cur_idx = i
                break

        if key in ("j", "KEY_DOWN"):
            next_idx = (cur_idx + 1) % len(eligible)
            self.selected_window_id = eligible[next_idx].window_id
            self.delete_armed_window_id = self.selected_window_id
        elif key in ("k", "KEY_UP"):
            prev_idx = (cur_idx - 1 + len(eligible)) % len(eligible)
            self.selected_window_id = eligible[prev_idx].window_id
            self.delete_armed_window_id = self.selected_window_id
        elif key in ("J", "]"):
            # Jump to first eligible window in next session group
            cur_sess = self.selected_window.session_name if self.selected_window else None
            unique_sessions = []
            for w in eligible:
                if w.session_name not in unique_sessions:
                    unique_sessions.append(w.session_name)
            if len(unique_sessions) > 1:
                cur_s_idx = unique_sessions.index(cur_sess) if cur_sess in unique_sessions else 0
                next_s = unique_sessions[(cur_s_idx + 1) % len(unique_sessions)]
                for w in eligible:
                    if w.session_name == next_s:
                        self.selected_window_id = w.window_id
                        self.delete_armed_window_id = self.selected_window_id
                        break
        elif key in ("K", "["):
            # Jump to first eligible window in prev session group
            cur_sess = self.selected_window.session_name if self.selected_window else None
            unique_sessions = []
            for w in eligible:
                if w.session_name not in unique_sessions:
                    unique_sessions.append(w.session_name)
            if len(unique_sessions) > 1:
                cur_s_idx = unique_sessions.index(cur_sess) if cur_sess in unique_sessions else 0
                prev_s = unique_sessions[(cur_s_idx - 1 + len(unique_sessions)) % len(unique_sessions)]
                for w in eligible:
                    if w.session_name == prev_s:
                        self.selected_window_id = w.window_id
                        self.delete_armed_window_id = self.selected_window_id
                        break
        elif key == "/":
            self.mode = Mode.SEARCH
            self.status_msg = ""
        if key in ("1", "2", "3", "4", "5", "6", "7", "8", "9", ":"):
            self.mode = Mode.LOCATE
            self.locate_buf = key
            self.status_msg = ""
            # Auto-preview target immediately upon typing coordinate
            matched = self.resolve_locate_target()
            if matched:
                self.selected_window_id = matched.window_id
        elif key in ("\t", "KEY_BTAB"):
            # Tab in BROWSE: toggle between pinned last window and source (current) window
            if self.pinned_last_window_id:
                if self.selected_window_id == self.pinned_last_window_id:
                    # Currently on last window -> toggle back to source (current) window
                    self.selected_window_id = self.source_window_id
                    self.delete_armed_window_id = None
                else:
                    # Currently on source or another window -> toggle to last window
                    self.selected_window_id = self.pinned_last_window_id
                    self.delete_armed_window_id = self.selected_window_id
        elif key == "?":
            self.show_help = not self.show_help

    def _handle_search_key(self, key: str):
        if key in ("KEY_BACKSPACE", "\b", "\x7f"):
            self.query = self.query[:-1]
        elif key in ("\x1b", "ESC"): # Escape
            # Retain filter, return to BROWSE
            self.mode = Mode.BROWSE
        elif len(key) == 1 and key.isprintable():
            self.query += key

    def resolve_locate_target(self) -> Optional[Window]:
        """
        Resolve exact target from locate_buf.
        Supports:
          - S.W (e.g. "2.1"): exact session alias S and window index W
          - :S:W (e.g. ":bios:2"): exact session name bios and window index 2
        Never fuzzy matches or permits prefix collisions.
        """
        buf = self.locate_buf.strip()
        if not buf:
            return None

        # Format 1: :<session_name>:<window_index>
        if buf.startswith(":"):
            parts = buf[1:].split(":")
            if len(parts) == 2:
                sname, widx_str = parts
                if widx_str.isdigit():
                    widx = int(widx_str)
                    for g in self.groups:
                        if g.session_name == sname:
                            for w in g.windows:
                                if w.window_index == widx:
                                    return w
            return None

        # Format 2: <session_alias>.<window_index>
        if "." in buf:
            parts = buf.split(".")
            if len(parts) == 2:
                s_alias, widx_str = parts
                if widx_str.isdigit():
                    widx = int(widx_str)
                    for g in self.groups:
                        if g.session_alias == s_alias:
                            for w in g.windows:
                                if w.window_index == widx:
                                    return w
            return None

        return None

    def can_delete_selected(self) -> bool:
        """Check if currently selected window is armed for deletion."""
        if not self.selected_window_id:
            return False
        if self.selected_window_id == self.source_window_id:
            return False
        return self.delete_armed_window_id == self.selected_window_id

    def on_window_deleted(self, deleted_window_id: str):
        """Update state after a window is deleted: focus adjacent and disarm."""
        # Find adjacent eligible window
        eligible_before = self.get_eligible_windows()
        next_focus_id = None
        for i, w in enumerate(eligible_before):
            if w.window_id == deleted_window_id:
                if i + 1 < len(eligible_before):
                    next_focus_id = eligible_before[i + 1].window_id
                elif i - 1 >= 0:
                    next_focus_id = eligible_before[i - 1].window_id
                break

        # Remove deleted window from groups
        for g in self.groups:
            g.windows = [w for w in g.windows if w.window_id != deleted_window_id]
        self.groups = [g for g in self.groups if g.windows]

        self.selected_window_id = next_focus_id
        # Disarm repeated deletion until explicit navigation!
        self.delete_armed_window_id = None

    def _handle_locate_key(self, key: str):
        if key in ("KEY_BACKSPACE", "\b", "\x7f"):
            self.locate_buf = self.locate_buf[:-1]
            if not self.locate_buf:
                self.mode = Mode.BROWSE
        elif key in ("\x1b", "ESC"):
            self.locate_buf = ""
            self.mode = Mode.BROWSE
        elif len(key) == 1 and key.isprintable():
            self.locate_buf += key

        # Dynamically focus target if locate_buf resolves to a valid window
        matched = self.resolve_locate_target()
        if matched:
            self.selected_window_id = matched.window_id
