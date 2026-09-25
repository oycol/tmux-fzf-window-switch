#!/usr/bin/env bash
# switch.sh — fzf 极速选择与切换 tmux 窗口与会话
# ► 标记 session 名称（标题行，可预览会话详情，Enter 跳转该会话首个窗口）
# * 固定标记当前所在 window（灰度只读显示）
# - 标记当前会话上一次活跃的 window（Tab 键快速直达）
# ● 标记有后台活动/警报的 window
# Z 标记全屏放大的 window
# 导航: j/k 或 ↓/↑ 移动 | J/K 或 ]/[ 跨 Session 飞跃 | Tab 切到上次窗口(-)
# 管理: Ctrl-x 快速销毁窗口 | Ctrl-p 开关预览 | Ctrl-r 刷新 | q/Esc 退出

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

self_window=$(tmux display-message -p "#{session_name}:#{window_index}" 2>/dev/null)
tmp_list=$(mktemp)

# 生成窗口列表
"$SCRIPT_DIR/list.sh" "$self_window" > "$tmp_list"

# 检查是否有可切换的 window
if ! awk -F'\t' '$1!="" && $3!="CURRENT" && $3!="SESSION"{found=1} END{exit !found}' "$tmp_list" 2>/dev/null; then
    rm -f "$tmp_list"
    tmux display-popup -b rounded -w 30 -h 3 -T "没有其他窗口" \
        -S "fg=#82aaff" -s "bg=#222436,fg=#c8d3f5" \
        -E "echo ''; echo '  当前只有一个窗口'; sleep 0.8" 2>/dev/null
    exit 0
fi

# 初始光标位置：优先停在当前会话的上次活跃窗口(LAST)，若无则停在第一个可选窗口
first_window_pos=$(awk -F'\t' '$3=="LAST"{print NR; exit}' "$tmp_list")
if [[ -z "$first_window_pos" ]]; then
    first_window_pos=$(awk -F'\t' '$1!="" && $3!="CURRENT" && $3!="SESSION"{print NR; exit}' "$tmp_list")
fi
[[ -z "$first_window_pos" ]] && first_window_pos=1

# 智能动态视口与缩放自适应算法：兼顾超宽屏聚焦与右侧多 Pane 垂直视野
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

if [[ "$popup_w" -ge 140 ]]; then
    preview_pct=60
elif [[ "$popup_w" -ge 100 ]]; then
    preview_pct=55
else
    preview_pct=50
fi

tmpfile=$(mktemp)
fzf_script=$(mktemp)

cat > "$fzf_script" << 'FZFEOF'
#!/usr/bin/env bash
export SD="$1"           # scripts 目录
export BL="$2"           # 基础列表文件
OUT="$3"                 # 选定输出文件
POS="${4:-1}"            # 初始光标位置
export SELF_WINDOW="$5"  # 当前窗口 ID
export PREV_PCT="${6:-60}"
export TAB=$'\t'

cat "$BL" | fzf \
    --sync \
    --reverse \
    --no-cycle \
    --pointer='→' \
    --prompt='🔍 过滤/跳转 > ' \
    --footer=' [Enter] 切换  [Tab] 上次窗口(-)  [J/K] 跨会话  [^x] 关闭窗口  [^p] 预览  [q] 退出' \
    -d "\t" \
    --with-nth=2 \
    --no-info \
    --ansi \
    --color="bg:#222436,bg+:#2f334d,fg:#c8d3f5,fg+:#82aaff,hl:#82aaff,hl+:#ffc777,info:#636da6,border:#82aaff,prompt:#82aaff,pointer:#ffc777,footer:#636da6" \
    --border=rounded \
    --preview-window="right:${PREV_PCT}%" \
    --preview="$SD/preview.sh {1}" \
    --bind="start:pos(${POS})" \
    --bind="load:pos(${POS})" \
    --bind='ctrl-p:toggle-preview' \
    --bind='q:abort' \
    --bind='esc:abort' \
    --bind='j:transform("$SD/jump.sh" down "$BL")' \
    --bind='down:transform("$SD/jump.sh" down "$BL")' \
    --bind='k:transform("$SD/jump.sh" up "$BL")' \
    --bind='up:transform("$SD/jump.sh" up "$BL")' \
    --bind='J:transform("$SD/jump.sh" next-session "$BL")' \
    --bind=']:transform("$SD/jump.sh" next-session "$BL")' \
    --bind='K:transform("$SD/jump.sh" prev-session "$BL")' \
    --bind='[:transform("$SD/jump.sh" prev-session "$BL")' \
    --bind='tab,ctrl-i:transform("$SD/jump.sh" last "$BL")' \
    --bind='btab:transform("$SD/jump.sh" last "$BL")' \
    --bind='ctrl-r:reload("$SD/list.sh" "$SELF_WINDOW" | tee "$BL")' \
    --bind='ctrl-x:execute-silent("$SD/action.sh" kill {1} {3} "$SELF_WINDOW" "$BL" "$SD")+reload(cat "$BL")' \
    --bind='enter:transform([[ {} == *"$TAB"CURRENT"$TAB"* ]] && echo ignore || echo accept)' \
    > "$OUT"
FZFEOF

chmod +x "$fzf_script"

tmux display-popup -b none -w "$popup_w" -h "$popup_h" -E "$fzf_script '$SCRIPT_DIR' '$tmp_list' '$tmpfile' '$first_window_pos' '$self_window' '$preview_pct'" 2>/dev/null

rm -f "$fzf_script"
line=$(cat "$tmpfile" 2>/dev/null || true)
rm -f "$tmpfile" "$tmp_list"

# 解析并执行切换
if [[ -n "$line" ]]; then
    target=$(printf '%s' "$line" | cut -f1)
    # 如果选中了 Session 标题行，解析跳转该 Session 首个可用窗口
    if [[ "$target" =~ ^SESSION:(.*) ]]; then
        sname="${BASH_REMATCH[1]}"
        target=$(tmux list-windows -t "$sname" -F "${sname}:#{window_index}" 2>/dev/null | while IFS= read -r w; do
            [[ "$w" != "$self_window" ]] && { echo "$w"; break; }
        done)
        # 若该 Session 只有当前窗口，允许切过去
        [[ -z "$target" ]] && target=$(tmux list-windows -t "$sname" -F "${sname}:#{window_index}" 2>/dev/null | head -n1)
    fi

    if [[ -n "$target" && "$target" != "$self_window" ]]; then
        tmux switch-client -t "$target"
    fi
fi
