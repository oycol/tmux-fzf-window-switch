"""Switcher core data models and layout definitions."""
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class Pane:
    pane_id: str          # e.g. %0
    pane_index: int       # e.g. 0
    pane_title: str
    pane_current_command: str
    pane_current_path: str
    pane_pid: int
    pane_active: bool
    pane_width: int
    pane_height: int
    pane_left: int
    pane_top: int

@dataclass
class Window:
    session_name: str     # e.g. "s1"
    session_id: str       # e.g. "$0"
    session_alias: str    # e.g. "1" (fixed per session for popup duration)
    window_id: str        # e.g. "@0" (stable identifier)
    window_index: int     # e.g. 0
    window_name: str
    is_active: bool
    is_last: bool
    is_current: bool      # source client's current window
    active_pane_id: str
    active_pane_command: str
    active_pane_path: str
    panes: List[Pane] = field(default_factory=list)

@dataclass
class SessionGroup:
    session_name: str
    session_id: str
    session_alias: str
    windows: List[Window] = field(default_factory=list)

@dataclass
class LayoutInfo:
    total_w: int
    total_h: int
    inner_x: int
    inner_y: int
    inner_w: int
    inner_h: int
    input_y: int
    input_x: int
    input_w: int
    body_top_y: int
    body_bottom_y: int
    list_x: int
    list_w: int
    preview_x: int
    preview_w: int
    divider_x: int
    divider_top_y: int
    divider_bottom_y: int
    help_y: int
    help_x: int
    help_w: int
    show_preview: bool
