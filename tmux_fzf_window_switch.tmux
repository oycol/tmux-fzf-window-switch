#!/usr/bin/env bash
# tmux-fzf-window-switch.tmux — 入口点，TPM 加载时执行
# 注册 prefix+w 绑定（可通过 @window_switch_key 自定义）

CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 默认绑定 prefix+w，可通过 set -g @window_switch_key 'x' 自定义
key="${TMUX_WINDOW_SWITCH_KEY:-w}"

tmux bind-key "$key" run-shell -t "#{session_id}" "$CURRENT_DIR/scripts/switch.sh"
