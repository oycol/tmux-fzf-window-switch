#!/usr/bin/env bash
# switch.sh — fzf 选择 window（树状 session/window）
# ► 三角标记 session 名称（不可选标题行，j/k 自动跳过）
# * 固定标记当前所在 window（显示但不可选，j/k 自动跳过，dimmed）
# → 箭头跟随光标（fzf --pointer，行首）
# j/k 移动 | Ctrl-p 预览开关 | q 退出
#
# 跳过逻辑：j/k 用 jump.sh 扫描列表，pos(N) 跳到下一个可选行
#   不可选行: SESSION(field1空) 和 CURRENT(field3=CURRENT)
#   可能有连续不可选行（CURRENT 后紧跟 SESSION），单步 transform 跳不过
#   jump.sh 逐行扫描，跳过所有连续不可选行

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

self_window=$(tmux display-message -p "#{session_name}:#{window_index}" 2>/dev/null)
tmp_list=$(mktemp)

# 生成树状列表：
#   field1 = target（空=session标题行）
#   field2 = 显示文本（含 ANSI 颜色，--with-nth=2 只显示此字段）
#   field3 = 类型标记（SESSION / CURRENT / 空）
tmux list-sessions -F '#{session_name}' 2>/dev/null | while IFS= read -r sname; do
    printf '\t\x1b[1;38;5;111m► %s\x1b[0m\tSESSION\t%s\n' "$sname" "$sname"
    tmux list-windows -t "$sname" -F "${sname}:#{window_index}|#{window_activity_flag}" 2>/dev/null | while IFS='|' read -r target activity; do
        widx="${target##*:}"
        wname=$(tmux display-message -t "$target" -p '#{window_name}' 2>/dev/null)
        if [[ "$target" == "$self_window" ]]; then
            printf '%s\t    \x1b[90m* %s %s\x1b[0m\tCURRENT\t\n' "$target" "$widx" "$wname"
        else
            if [[ "$activity" == "1" ]]; then
                printf '%s\t    \x1b[38;5;111m%s\x1b[0m %s \x1b[38;5;150m●\x1b[0m\t\t\n' "$target" "$widx" "$wname"
            else
                printf '%s\t    \x1b[38;5;111m%s\x1b[0m %s\t\t\n' "$target" "$widx" "$wname"
            fi
        fi
    done
done > "$tmp_list"

# 检查是否有可切换的 window
if ! awk -F'\t' '$1!="" && $3!="CURRENT" && $3!="SESSION"{found=1} END{exit !found}' "$tmp_list" 2>/dev/null; then
    rm -f "$tmp_list"
    tmux display-popup -b rounded -w 30 -h 3 -T "没有其他窗口" \
        -S "fg=#82aaff" -s "bg:#222436,fg:#c8d3f5" \
        -E "bash -c 'read -rsn1'" 2>/dev/null
    exit 0
fi

# 定位到第一个可切换 window
first_window_pos=$(awk -F'\t' '$1!="" && $3!="CURRENT" && $3!="SESSION"{print NR; exit}' "$tmp_list")
tmpfile=$(mktemp)

# fzf 子脚本（quoted heredoc，位置参数传变量避免转义地狱）
fzf_script=$(mktemp)
cat > "$fzf_script" << 'FZFEOF'
#!/usr/bin/env bash
export SD="$1"    # scripts 目录
export BL="$2"    # 基础列表文件
OUT="$3"   # 输出文件
POS="${4:-1}"  # 初始光标位置

cat "$BL" | fzf \
    --reverse \
    --no-cycle \
    --pointer='→' \
    --prompt='' \
    --header='' \
    --delimiter=$'\t' \
    --with-nth=2 \
    --no-info \
    --ansi \
    --color="bg:#222436,bg+:#2f334d,fg:#c8d3f5,fg+:#82aaff,hl:#82aaff,hl+:#ffc777,info:#636da6,border:#82aaff,header:#636da6,prompt:#82aaff,pointer:#ffc777" \
    --border=rounded \
    --preview-window='right:75%' \
    --preview="$SD/preview.sh {1}" \
    --bind="load:pos(${POS})" \
    --bind='ctrl-p:toggle-preview' \
    --bind='q:abort' \
    --bind='j:transform("$SD/jump.sh" down "$BL")' \
    --bind='k:transform("$SD/jump.sh" up "$BL")' \
    --bind='enter:transform(grep -qP "^\t|\tCURRENT\t" <<< {} && echo ignore || echo accept)' \
    > "$OUT" 2>/dev/null
FZFEOF
chmod +x "$fzf_script"

tmux display-popup -b none -w 80% -h 80% -E "$fzf_script '$SCRIPT_DIR' '$tmp_list' '$tmpfile' '$first_window_pos'" 2>/dev/null

rm -f "$fzf_script"
line=$(cat "$tmpfile")
rm -f "$tmpfile" "$tmp_list"

# 解析选中行
if [[ -n "$line" ]]; then
    target=$(printf '%s' "$line" | cut -f1)
    [[ -n "$target" && "$target" != "$self_window" ]] && tmux switch-client -t "$target"
fi
