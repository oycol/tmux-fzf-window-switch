#!/usr/bin/env bash
# switch.sh — TPM launcher invoking Python curses switcher with explicit context
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOCKET_PATH="${TMUX%%,*}"
CLIENT_TARGET="$(tmux display-message -p '#{client_name}' 2>/dev/null || true)"

# Dynamic popup sizing based on client dimensions
client_w=$(tmux display-message -p "#{client_width}" 2>/dev/null || echo 120)
client_h=$(tmux display-message -p "#{client_height}" 2>/dev/null || echo 40)
[[ -z "$client_w" || "$client_w" -le 0 ]] && client_w=120
[[ -z "$client_h" || "$client_h" -le 0 ]] && client_h=40

if [[ "$client_w" -ge 220 ]]; then
    popup_w=$(( client_w * 55 / 100 ))
    [[ "$popup_w" -gt 165 ]] && popup_w=165
    [[ "$popup_w" -lt 135 ]] && popup_w=135
elif [[ "$client_w" -ge 140 ]]; then
    popup_w=$(( client_w * 75 / 100 ))
else
    popup_w=$(( client_w * 90 / 100 ))
fi

# Height follows the visible list; reserve 5 rows for frame, input and footer,
# plus a little breathing room. The help page scrolls on shorter popups.
window_count=$(tmux list-windows -a -F '#{window_id}' 2>/dev/null | wc -l)
session_count=$(tmux list-sessions -F '#{session_id}' 2>/dev/null | wc -l)
content_h=$(( window_count + session_count + 7 ))
if [[ "$client_h" -ge 60 ]]; then
    max_h=$(( client_h * 72 / 100 ))
elif [[ "$client_h" -ge 35 ]]; then
    max_h=$(( client_h * 78 / 100 ))
else
    max_h=$(( client_h - 2 ))
fi
[[ "$max_h" -gt "$((client_h - 2))" ]] && max_h=$((client_h - 2))
[[ "$content_h" -lt 10 ]] && content_h=10
popup_h=$(( content_h < max_h ? content_h : max_h ))
if [[ "$popup_h" -lt 8 || "$popup_w" -lt 20 ]]; then
    # curses needs at least 8x20 cells. Keep the client untouched instead
    # of launching a popup that cannot show controls or be dismissed.
    message="窗口切换：终端空间不足（至少 8×20，当前弹窗 ${popup_h}×${popup_w}）"
    tmux display-message -c "$CLIENT_TARGET" "$message"
    exit 0
fi

# Run python switcher inside display-popup with ESCDELAY=25 for instant ESC response
cmd="PYTHONPATH=\"$SCRIPT_DIR/..\" ESCDELAY=25 python3 -m scripts.switcher.app --socket '$SOCKET_PATH' --client '$CLIENT_TARGET'"
tmux display-popup -b none -w "$popup_w" -h "$popup_h" -E "$cmd"
