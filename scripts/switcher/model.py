"""Switcher core data models and layout definitions."""


class Pane:
    __slots__ = ("pane_id", "pane_index", "pane_title", "pane_current_command",
                 "pane_current_path", "pane_pid", "pane_active", "pane_width",
                 "pane_height", "pane_left", "pane_top")

    def __init__(self, pane_id: str = "", pane_index: int = 0, pane_title: str = "",
                 pane_current_command: str = "", pane_current_path: str = "",
                 pane_pid: int = 0, pane_active: bool = False, pane_width: int = 80,
                 pane_height: int = 24, pane_left: int = 0, pane_top: int = 0):
        self.pane_id = pane_id
        self.pane_index = pane_index
        self.pane_title = pane_title
        self.pane_current_command = pane_current_command
        self.pane_current_path = pane_current_path
        self.pane_pid = pane_pid
        self.pane_active = pane_active
        self.pane_width = pane_width
        self.pane_height = pane_height
        self.pane_left = pane_left
        self.pane_top = pane_top


class Window:
    __slots__ = ("session_name", "session_id", "session_alias", "window_id",
                 "window_index", "window_name", "is_active", "is_last", "is_current",
                 "active_pane_id", "active_pane_command", "active_pane_path", "panes")

    def __init__(self, session_name="", session_id="", session_alias="",
                 window_id="", window_index=0, window_name="",
                 is_active=False, is_last=False, is_current=False,
                 active_pane_id="", active_pane_command="",
                 active_pane_path="", panes=None):
        self.session_name = session_name
        self.session_id = session_id
        self.session_alias = session_alias
        self.window_id = window_id
        self.window_index = window_index
        self.window_name = window_name
        self.is_active = is_active
        self.is_last = is_last
        self.is_current = is_current
        self.active_pane_id = active_pane_id
        self.active_pane_command = active_pane_command
        self.active_pane_path = active_pane_path
        self.panes = panes if panes is not None else []


class SessionGroup:
    __slots__ = ("session_name", "session_id", "session_alias", "windows")

    def __init__(self, session_name="", session_id="",
                 session_alias="", windows=None):
        self.session_name = session_name
        self.session_id = session_id
        self.session_alias = session_alias
        self.windows = windows if windows is not None else []


class LayoutInfo:
    __slots__ = ("total_w", "total_h", "inner_x", "inner_y", "inner_w", "inner_h",
                 "input_y", "input_x", "input_w", "body_top_y", "body_bottom_y",
                 "list_x", "list_w", "preview_x", "preview_w", "divider_x",
                 "divider_top_y", "divider_bottom_y", "help_y", "help_x", "help_w",
                 "show_preview")

    def __init__(self, **kw):
        for key in self.__slots__:
            setattr(self, key, kw.get(key, 0))
        self.show_preview = bool(kw.get("show_preview", False))
