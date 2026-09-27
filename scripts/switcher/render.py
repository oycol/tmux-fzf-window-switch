"""Rendering and layout computation for the switcher."""
import unicodedata
from scripts.switcher.model import LayoutInfo

def wcwidth_char(ch: str) -> int:
    """Return display width of a single character in terminal cells."""
    if not ch:
        return 0
    cat = unicodedata.category(ch)
    # Zero-width characters (combining marks, format, etc.)
    if cat in ('Mn', 'Me', 'Cf'):
        return 0
    w = unicodedata.east_asian_width(ch)
    if w in ('W', 'F'):
        return 2
    return 1

def str_cell_width(s: str) -> int:
    """Return total terminal cell width of string s."""
    return sum(wcwidth_char(c) for c in s)

def truncate_cell(s: str, max_w: int) -> str:
    """Truncate string s so its terminal display width <= max_w."""
    if max_w <= 0:
        return ""
    cur_w = 0
    res = []
    for c in s:
        w = wcwidth_char(c)
        if cur_w + w > max_w:
            break
        res.append(c)
        cur_w += w
    return "".join(res)

def truncate_cell_middle(s: str, max_w: int) -> str:
    """Scale text down to max_w cells, keeping the head and the tail.

    Split the ellipsis budget in half so the end of the line survives:
    paths and command output tails matter as much as the prefix.
    """
    if max_w <= 0:
        return ""
    if str_cell_width(s) <= max_w:
        return s
    if max_w <= 3:
        return truncate_cell(s, max_w)
    budget = max_w - 1  # one cell for the ellipsis
    head_budget = budget // 2
    tail_budget = budget - head_budget
    head = truncate_cell(s, head_budget)
    tail = truncate_cell_middle_tail(s, tail_budget)
    return head + "…" + tail


def truncate_cell_middle_tail(s: str, max_w: int) -> str:
    """Keep the widest suffix of s that fits max_w terminal cells."""
    if max_w <= 0:
        return ""
    chars = []
    used = 0
    for c in reversed(s):
        w = wcwidth_char(c)
        if used + w > max_w:
            break
        chars.append(c)
        used += w
    return "".join(reversed(chars))


def format_path(path: str, max_w: int) -> str:
    """Format file path with exact HOME boundary and middle ellipsis if needed."""
    if not path:
        return ""
    import os
    home = os.path.expanduser("~")
    display_path = path
    if path == home:
        display_path = "~"
    elif path.startswith(home + "/"):
        display_path = "~" + path[len(home):]

    if str_cell_width(display_path) <= max_w:
        return display_path

    # Need middle ellipsis
    if max_w < 5:
        return truncate_cell(display_path, max_w)

    basename = os.path.basename(display_path.rstrip("/"))
    base_w = str_cell_width(basename)
    if base_w + 4 <= max_w:
        prefix_budget = max_w - base_w - 3  # for '...'
        prefix = ""
        cur_w = 0
        for c in display_path:
            w = wcwidth_char(c)
            if cur_w + w > prefix_budget:
                break
            prefix += c
            cur_w += w
        return f"{prefix}...{basename}"
    else:
        # Just truncate the end or fit basename
        return truncate_cell(display_path, max_w - 3) + "..."


def compute_layout(width: int, height: int, preview_pct: int = 50, show_preview: bool = True) -> LayoutInfo:
    """
    Compute layout dimensions:
    - Outer border at 0..height-1, 0..width-1
    - Inner area: x=1, y=1, w=width-2, h=height-2
    - Top mode/input line: y=1, x=1, w=width-2
    - Separator line below input: y=2 (optional, or body starts at y=2)
      Spec:
      "Outer border/title, full-width top mode/input line, split body with session list and preview,
       full-width final single help line OUTSIDE both body boxes; divider ends ABOVE help."
    - Bottom help line: y=height-2, x=1, w=width-2
    - Body area: y from 3 to height-4; height-3 is the help separator
      or y from 2 to height-3 (if border below input).
      Let's use:
      y=0: top outer border
      y=1: full-width input/mode line
      y=2: horizontal divider between input and body
      y=3 .. height-4: split body (list | divider | preview)
      y=height-3: full-width separator
      y=height-2: full-width help line outside body boxes
      y=height-1: bottom outer border
    """
    total_w = max(width, 20)
    total_h = max(height, 8)

    inner_x = 1
    inner_y = 1
    inner_w = total_w - 2
    inner_h = total_h - 2

    input_y = 1
    input_x = 1
    input_w = inner_w

    help_y = total_h - 2
    help_x = 1
    help_w = inner_w

    # Body ends above its dedicated full-width separator.
    body_top_y = 3
    body_bottom_y = max(body_top_y, total_h - 4)

    # Determine preview visibility based on width
    # Small terminal degrades optional cols -> single pane -> no preview
    # Reserve enough room for coordinate, window, path and pane count.
    actual_show_preview = show_preview and (total_w >= 100)

    list_w = inner_w
    preview_w = 0
    divider_x = -1
    preview_x = -1

    if actual_show_preview:
        calc_preview_w = int(inner_w * (preview_pct / 100.0))
        calc_list_w = inner_w - calc_preview_w - 1
        if calc_list_w < 46:
            calc_list_w = 46
            calc_preview_w = max(0, inner_w - calc_list_w - 1)
        if calc_preview_w < 15:
            actual_show_preview = False
        else:
            list_w = calc_list_w
            preview_w = calc_preview_w
            divider_x = inner_x + list_w
            preview_x = divider_x + 1

    return LayoutInfo(
        total_w=total_w,
        total_h=total_h,
        inner_x=inner_x,
        inner_y=inner_y,
        inner_w=inner_w,
        inner_h=inner_h,
        input_y=input_y,
        input_x=input_x,
        input_w=input_w,
        body_top_y=body_top_y,
        body_bottom_y=body_bottom_y,
        list_x=inner_x,
        list_w=list_w,
        preview_x=preview_x if actual_show_preview else inner_x + inner_w,
        preview_w=preview_w,
        divider_x=divider_x,
        divider_top_y=body_top_y,
        divider_bottom_y=body_bottom_y,
        help_y=help_y,
        help_x=help_x,
        help_w=help_w,
        show_preview=actual_show_preview
    )
