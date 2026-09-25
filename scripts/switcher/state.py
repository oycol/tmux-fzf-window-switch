"""Window switcher state; navigation is independent of tmux per-session history."""
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
    preview_detail_mode: bool = False
    selected_pane_idx: int = 0
    show_help: bool = False
    status_msg: str = ""
    selected_window_id: Optional[str] = None
    return_window_id: Optional[str] = None
    delete_blocked: bool = False
    locate_previous_id: Optional[str] = None
    session_aliases: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def create(cls, groups: List[SessionGroup], source_window_id: str,
               return_window_id: Optional[str] = None) -> "AppState":
        state = cls(groups=groups, source_window_id=source_window_id,
                    return_window_id=return_window_id)
        state.replace_groups(groups)
        candidates = state.get_eligible_windows()
        if return_window_id and any(w.window_id == return_window_id for w in candidates):
            state.selected_window_id = return_window_id
        elif candidates:
            source = state.source_group
            local = next((w for w in candidates if source and w.session_id == source.session_id), None)
            state.selected_window_id = (local or candidates[0]).window_id
        if return_window_id and state.selected_window_id != return_window_id:
            state.status_msg = "Return window no longer available"
        state.delete_blocked = False
        return state

    def replace_groups(self, groups: List[SessionGroup]):
        self.groups = groups
        for g in groups:
            if g.session_id not in self.session_aliases:
                self.session_aliases[g.session_id] = str(len(self.session_aliases) + 1)
            g.session_alias = self.session_aliases[g.session_id]
            for w in g.windows:
                w.session_alias = g.session_alias
        self.reconcile_selection()

    @property
    def source_group(self) -> Optional[SessionGroup]:
        return next((g for g in self.groups if any(w.window_id == self.source_window_id for w in g.windows)), None)

    def get_eligible_windows(self) -> List[Window]:
        from scripts.switcher.fzf import fzf_filter_windows
        return fzf_filter_windows(self.groups, self.query, self.source_window_id)

    @property
    def selected_window(self) -> Optional[Window]:
        return next((w for g in self.groups for w in g.windows if w.window_id == self.selected_window_id), None)

    def reconcile_selection(self):
        eligible = self.get_eligible_windows()
        if self.selected_window_id not in {w.window_id for w in eligible}:
            self.selected_window_id = eligible[0].window_id if eligible else None
            self.delete_blocked = True

    def move_to(self, wid: str):
        if wid != self.selected_window_id:
            self.selected_window_id = wid
            self.selected_pane_idx = 0
            self.delete_blocked = False

    def handle_key(self, key: str):
        if self.mode == Mode.SEARCH:
            if key == "KEY_BACKSPACE":
                self.query = self.query[:-1]
            elif key == "ESC":
                self.mode = Mode.BROWSE
                return
            elif key in ("KEY_UP", "KEY_DOWN"):
                self._navigate("k" if key == "KEY_UP" else "j")
                return
            elif len(key) == 1 and key.isprintable():
                self.query += key
            self.reconcile_selection()
            return
        if self.mode == Mode.LOCATE:
            if key == "ESC":
                self.mode = Mode.BROWSE
                self.locate_buf = ""
                self.selected_window_id = self.locate_previous_id
                self.reconcile_selection()
                return
            if key == "KEY_BACKSPACE":
                self.locate_buf = self.locate_buf[:-1]
                if not self.locate_buf:
                    self.mode = Mode.BROWSE
                    self.selected_window_id = self.locate_previous_id
                    self.reconcile_selection()
                    return
            elif len(key) == 1 and key.isprintable():
                self.locate_buf += key
            target = self.resolve_locate_target()
            if target and target.window_id != self.source_window_id:
                self.move_to(target.window_id)
            return
        if key == "/":
            self.mode = Mode.SEARCH
            self.status_msg = ""
        elif len(key) == 1 and key in "123456789:":
            self.mode = Mode.LOCATE
            self.locate_previous_id = self.selected_window_id
            self.locate_buf = key
            self.status_msg = ""
        elif key == "?":
            self.show_help = not self.show_help
        else:
            self._navigate(key)

    def _navigate(self, key: str):
        eligible = self.get_eligible_windows()
        if not eligible:
            return
        ids = [w.window_id for w in eligible]
        pos = ids.index(self.selected_window_id) if self.selected_window_id in ids else -1
        if key in ("j", "KEY_DOWN"):
            self.move_to(ids[(pos + 1) % len(ids)])
        elif key in ("k", "KEY_UP"):
            self.move_to(ids[(pos - 1) % len(ids)])
        elif key in ("J", "K"):
            sids = list(dict.fromkeys(w.session_id for w in eligible))
            if len(sids) < 2:
                return
            current = self.selected_window.session_id if self.selected_window else None
            idx = sids.index(current) if current in sids else 0
            dest = sids[(idx + (1 if key == "J" else -1)) % len(sids)]
            options = [w for w in eligible if w.session_id == dest]
            self.move_to(next((w.window_id for w in options if w.is_active), options[0].window_id))

    def resolve_locate_target(self) -> Optional[Window]:
        buf = self.locate_buf.strip()
        if buf.startswith(":"):
            parts = buf[1:].rsplit(":", 1)
            if len(parts) != 2 or not parts[1].isascii() or not parts[1].isdigit():
                return None
            return next((w for g in self.groups if g.session_name == parts[0]
                         for w in g.windows if w.window_index == int(parts[1])), None)
        parts = buf.split(".")
        if len(parts) != 2 or not parts[0].isascii() or not parts[0].isdigit() or not parts[1].isascii() or not parts[1].isdigit():
            return None
        return next((w for g in self.groups if g.session_alias == parts[0]
                     for w in g.windows if w.window_index == int(parts[1])), None)

    def can_delete_selected(self) -> bool:
        return (self.mode == Mode.BROWSE and not self.delete_blocked and
                self.selected_window_id is not None and
                self.selected_window_id != self.source_window_id and
                self.selected_window_id in {w.window_id for w in self.get_eligible_windows()})

    def on_window_deleted(self, deleted_window_id: str):
        before = [w.window_id for w in self.get_eligible_windows()]
        idx = before.index(deleted_window_id) if deleted_window_id in before else 0
        self.selected_window_id = None
        for g in self.groups:
            g.windows = [w for w in g.windows if w.window_id != deleted_window_id]
        self.groups = [g for g in self.groups if g.windows]
        after = [w.window_id for w in self.get_eligible_windows()]
        self.selected_window_id = after[min(idx, len(after)-1)] if after else None
        self.delete_blocked = True
