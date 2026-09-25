"""Fixed 2D canvas preview for multi-pane tmux windows."""
import re
from typing import List, Dict, Tuple
from scripts.switcher.model import Pane
from scripts.switcher.render import wcwidth_char, str_cell_width, truncate_cell

ANSI_ESCAPE_RE = re.compile(r'\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

def strip_ansi(s: str) -> str:
    """Remove ANSI SGR and terminal escape codes safely."""
    return ANSI_ESCAPE_RE.sub('', s)

def sanitize_text_line(s: str, max_w: int) -> str:
    """Strip ANSI escapes and clamp length to max_w terminal display cells."""
    clean = strip_ansi(s).replace('\r', '').replace('\n', '').replace('\t', '    ')
    # Filter non-printable control characters
    filtered = "".join(c for c in clean if c.isprintable() or c == ' ')
    return truncate_cell(filtered, max_w)

def render_panes_to_canvas(
    panes: List[Pane],
    canvas_w: int,
    canvas_h: int,
    pane_contents: Dict[str, List[str]]
) -> List[str]:
    """
    Render multiple panes onto a fixed 2D canvas of size canvas_w x canvas_h.
    Uses proportional geometry without row redistribution.
    """
    if canvas_w <= 0 or canvas_h <= 0:
        return []

    if not panes:
        return [" " * canvas_w for _ in range(canvas_h)]

    # If single pane, direct render
    if len(panes) == 1:
        p = panes[0]
        lines = pane_contents.get(p.pane_id, [])
        result = []
        for y in range(canvas_h):
            line_str = lines[y] if y < len(lines) else ""
            sanitized = sanitize_text_line(line_str, canvas_w)
            pad = " " * max(0, canvas_w - str_cell_width(sanitized))
            result.append(sanitized + pad)
        return result

    # Find total bounding box of window from pane geometries
    max_orig_w = max(p.pane_left + p.pane_width for p in panes)
    max_orig_h = max(p.pane_top + p.pane_height for p in panes)
    max_orig_w = max(1, max_orig_w)
    max_orig_h = max(1, max_orig_h)

    # Scale pane boxes to canvas coordinates
    # We allocate a 2D grid of character cells
    grid = [[" " for _ in range(canvas_w)] for _ in range(canvas_h)]

    # Map each pane to canvas box (box_x, box_y, box_w, box_h)
    pane_boxes = []
    for p in panes:
        bx = int((p.pane_left / max_orig_w) * canvas_w)
        by = int((p.pane_top / max_orig_h) * canvas_h)
        bw = int((p.pane_width / max_orig_w) * canvas_w)
        bh = int((p.pane_height / max_orig_h) * canvas_h)
        bw = max(1, min(canvas_w - bx, bw))
        bh = max(1, min(canvas_h - by, bh))
        pane_boxes.append((p, bx, by, bw, bh))

    # Draw pane contents
    for p, bx, by, bw, bh in pane_boxes:
        # Pane header at top row of pane
        title = f" [{p.pane_index}:{p.pane_current_command}] "
        clean_title = sanitize_text_line(title, bw)

        lines = pane_contents.get(p.pane_id, [])
        for row_idx in range(bh):
            gy = by + row_idx
            if gy >= canvas_h:
                break
            if row_idx == 0 and bh > 1:
                # header line
                content_line = clean_title
            else:
                line_idx = (row_idx - 1) if bh > 1 else row_idx
                content_line = lines[line_idx] if line_idx < len(lines) else ""
            
            sanitized = sanitize_text_line(content_line, bw)
            # place characters into grid
            gx = bx
            for ch in sanitized:
                w = wcwidth_char(ch)
                if gx + w > bx + bw or gx >= canvas_w:
                    break
                grid[gy][gx] = ch
                if w == 2 and gx + 1 < canvas_w:
                    grid[gy][gx + 1] = "" # placeholder for 2nd cell of wide char
                gx += w

    # Draw dividers between adjacent panes
    for i in range(len(pane_boxes)):
        for j in range(i + 1, len(pane_boxes)):
            p1, x1, y1, w1, h1 = pane_boxes[i]
            p2, x2, y2, w2, h2 = pane_boxes[j]
            # Vertical seam check
            if x1 + w1 == x2:
                # Vertical border along x2
                seam_y_start = max(y1, y2)
                seam_y_end = min(y1 + h1, y2 + h2)
                for gy in range(seam_y_start, seam_y_end):
                    if 0 <= gy < canvas_h and 0 <= x2 < canvas_w:
                        grid[gy][x2] = "│"
            elif x2 + w2 == x1:
                seam_y_start = max(y1, y2)
                seam_y_end = min(y1 + h1, y2 + h2)
                for gy in range(seam_y_start, seam_y_end):
                    if 0 <= gy < canvas_h and 0 <= x1 < canvas_w:
                        grid[gy][x1] = "│"

            # Horizontal seam check
            if y1 + h1 == y2:
                seam_x_start = max(x1, x2)
                seam_x_end = min(x1 + w1, x2 + w2)
                for gx in range(seam_x_start, seam_x_end):
                    if 0 <= y2 < canvas_h and 0 <= gx < canvas_w:
                        if grid[y2][gx] == "│":
                            grid[y2][gx] = "┼"
                        else:
                            grid[y2][gx] = "─"

    # Assemble rows, taking care of wide characters and padding
    result = []
    for row in grid:
        line_chars = []
        cur_w = 0
        for ch in row:
            if ch == "":
                continue
            w = wcwidth_char(ch)
            if cur_w + w > canvas_w:
                break
            line_chars.append(ch)
            cur_w += w
        if cur_w < canvas_w:
            line_chars.append(" " * (canvas_w - cur_w))
        result.append("".join(line_chars))

    return result
