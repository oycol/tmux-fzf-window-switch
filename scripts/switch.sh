#!/usr/bin/env bash
# switch.sh — TPM launcher invoking Python curses switcher with explicit context
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOCKET_PATH="${TMUX%%,*}"
CLIENT_TARGET="$(tmux display-message -p '#{client_name}' 2>/dev/null || true)"

# Compute popup size from the current client dimensions (percent-based).
compute_popup_size() {
    local client_w client_h popup_w popup_h
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

    if [[ "$client_h" -ge 60 ]]; then
        popup_h=$(( client_h * 72 / 100 ))
    elif [[ "$client_h" -ge 35 ]]; then
        popup_h=$(( client_h * 78 / 100 ))
    else
        popup_h=$(( client_h - 2 ))
        [[ "$popup_h" -lt 14 ]] && popup_h=14
    fi
    echo "$popup_w $popup_h"
}

# tmux popups never follow client resize; the in-popup app detects a resized
# client and exits 42, so we reopen the popup at the new size in a loop.
while true; do
    read -r popup_w popup_h <<< "$(compute_popup_size)"
    cmd="PYTHONPATH=\"$SCRIPT_DIR/..\" ESCDELAY=25 python3 -m scripts.switcher.app --socket '$SOCKET_PATH' --client '$CLIENT_TARGET' --popup-size ${popup_w}x${popup_h}"
    set +e
    tmux display-popup -b none -w "$popup_w" -h "$popup_h" -E "$cmd"
    rc=$?
    set -e
    # 42 = client resized, reopen at the new size; anything else ends here.
    [[ "$rc" == "42" ]] || break
done
