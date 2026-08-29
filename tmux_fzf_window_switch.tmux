#!/usr/bin/env bash
# tmux_fzf_window_switch.tmux — 入口点，TPM 加载时执行
# 注册 prefix+w 绑定（可通过 TMUX_WINDOW_SWITCH_KEY 环境变量自定义）
#
# 自定义绑定的两种方式：
#   方式1 (推荐): tmux.conf 中设置环境变量
#     set -g @window_switch_key 'x'
#     或直接: TMUX_WINDOW_SWITCH_KEY='x'
#   方式2: 直接用 tmux bind-key 覆盖
#     tmux bind-key x run-shell -t "#{session_id}" "$CURRENT_DIR/scripts/switch.sh"

CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 默认 prefix+w，可通过 TMUX_WINDOW_SWITCH_KEY 环境变量自定义
key="${TMUX_WINDOW_SWITCH_KEY:-w}"

tmux bind-key "$key" run-shell -t "#{session_id}" "$CURRENT_DIR/scripts/switch.sh"
