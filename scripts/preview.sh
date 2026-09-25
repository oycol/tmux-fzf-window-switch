#!/usr/bin/env bash
# preview.sh — 窗口与会话预览器包装脚本（零闪烁、多布局自适应）
target="$1"
[[ -z "$target" ]] && exit 0

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
lines="${FZF_PREVIEW_LINES:-40}"
cols="${FZF_PREVIEW_COLUMNS:-80}"

exec python3 "$SCRIPT_DIR/preview.py" "$target" "$lines" "$cols"
