#!/usr/bin/env bash
# list.sh — 生成窗口/会话列表
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/list.py" "$@"
