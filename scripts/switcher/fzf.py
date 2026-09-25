"""FZF integration for fuzzy searching full window metadata while preserving session grouping."""
import subprocess
from typing import List, Set
from scripts.switcher.model import Window, SessionGroup

def fzf_filter_windows(groups: List[SessionGroup], query: str, source_window_id: str) -> List[Window]:
    """
    Filter windows across session groups using real fzf --filter,
    but preserving original session and window ordering (not fzf score order).
    """
    if not query.strip():
        # Return all eligible windows in session order
        res = []
        for g in groups:
            for w in g.windows:
                if w.window_id != source_window_id:
                    res.append(w)
        return res

    # Build metadata lines for fzf:
    # window_id \t metadata_string
    lines = []
    for g in groups:
        for w in g.windows:
            if w.window_id == source_window_id:
                continue
            meta = f"{w.session_name} {w.session_alias} {w.window_index} {w.session_alias}.{w.window_index} {w.window_name} {w.active_pane_command} {w.active_pane_path}"
            lines.append(f"{w.window_id}\t{meta}")

    if not lines:
        return []

    input_text = "\n".join(lines)
    try:
        proc = subprocess.run(
            ["fzf", "--filter", query, "-d", "\t", "--with-nth", "2"],
            input=input_text,
            capture_output=True,
            text=True,
            check=False
        )
        matched_output = proc.stdout.strip()
    except Exception:
        # Fallback to simple substring match if fzf execution fails
        matched_output = ""
        for line in lines:
            if query.lower() in line.lower():
                matched_output += line + "\n"

    matched_ids: Set[str] = set()
    for line in matched_output.splitlines():
        if line.strip():
            wid = line.split("\t")[0].strip()
            matched_ids.add(wid)

    # Re-order matching windows by session grouping order
    ordered_matched: List[Window] = []
    for g in groups:
        for w in g.windows:
            if w.window_id in matched_ids and w.window_id != source_window_id:
                ordered_matched.append(w)

    return ordered_matched
