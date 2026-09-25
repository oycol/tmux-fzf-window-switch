#!/usr/bin/env bash
# action.sh — 处理 fzf 快捷操作（如 Ctrl-x 销毁窗口）
set -euo pipefail

action="${1:-}"
target="${2:-}"
row_type="${3:-}"
self_window="${4:-}"
list_file="${5:-}"
scripts_dir="${6:-}"

if [[ "$action" == "kill" ]]; then
    # 禁止销毁当前所在窗口或 Session 行
    if [[ "$row_type" == "SESSION" || "$row_type" == "CURRENT" || -z "$target" ]]; then
        exit 0
    fi
    # 销毁目标窗口
    tmux kill-window -t "$target" 2>/dev/null || true
    
    # 重新生成列表文件以供 reload
    if [[ -n "$list_file" && -n "$scripts_dir" && -x "$scripts_dir/list.sh" ]]; then
        "$scripts_dir/list.sh" "$self_window" > "$list_file" 2>/dev/null || true
    fi
fi
