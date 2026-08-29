#!/usr/bin/env bash
# switch.sh — fzf 选择 window（树状 session/window）
# session 为不可选标题行，Enter 在标题上自动跳到该 session 第一个 window
# Enter 确认 | j/k 移动 | Ctrl-p 预览开关 | q 退出

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

self_window=$(tmux display-message -p "#{session_name}:#{window_index}" 2>/dev/null)
tmp_list=$(mktemp)

# 生成树状列表：session 名为标题行（field1 空），window 为可选行
# 圈圈数字映射
circles=(① ② ③ ④ ⑤ ⑥ ⑦ ⑧ ⑨ ⑩ ⑪ ⑫ ⑬ ⑭ ⑮ ⑯ ⑰ ⑱ ⑲ ⑳)

tmux list-sessions -F '#{session_name}' 2>/dev/null | while IFS= read -r sname; do
    printf '\t\x1b[1;38;5;111m► %s\x1b[0m\t%s\n' "$sname" "$sname"
    tmux list-windows -t "$sname" -F "${sname}:#{window_index}" 2>/dev/null | while IFS= read -r target; do
        [[ "$target" == "$self_window" ]] && continue
        widx="${target##*:}"
        wname=$(tmux display-message -t "$target" -p '#{window_name}' 2>/dev/null)
        active=$(tmux display-message -t "$target" -p '#{?window_active,*,}' 2>/dev/null)
        if [[ "$widx" -ge 0 && "$widx" -le 19 ]] 2>/dev/null; then
            circ="${circles[$widx]}"
        else
            circ="($widx)"
        fi
        printf '%s\t    \x1b[38;5;111m%s\x1b[0m %s %s\n' "$target" "$circ" "$wname" "$active"
    done
done > "$tmp_list"

# 检查是否有 window 行
if ! awk -F'\t' '$1!=""{found=1} END{exit !found}' "$tmp_list" 2>/dev/null; then
    rm -f "$tmp_list"
    tmux display-popup -b rounded -w 30 -h 3 -T "没有其他窗口" \
        -S "fg=#82aaff" -s "bg=#222436,fg=#c8d3f5" \
        -E "bash -c 'read -rsn1'" 2>/dev/null
    exit 0
fi

# 多 window：用 display-popup 包裹 fzf
first_window_pos=$(awk -F'\t' '$1!=""{print NR; exit}' "$tmp_list")
tmpfile=$(mktemp)

# 把 fzf 命令写成子脚本，用 display-popup -E 执行
fzf_script=$(mktemp)
cat > "$fzf_script" << FZFEOF
#!/usr/bin/env bash
cat "$tmp_list" | fzf \
    --reverse \
    --no-cycle \
    --prompt='' \
    --header='' \
    --delimiter=\$'\\t' \
    --with-nth=2 \
    --no-info \
    --ansi \
    --color="bg:#222436,bg+:#2f334d,fg:#c8d3f5,fg+:#82aaff,hl:#82aaff,hl+:#ffc777,info:#636da6,border:#82aaff,header:#636da6,prompt:#82aaff" \
    --border=rounded \
    --preview-window='right:75%' \
    --preview="$SCRIPT_DIR/preview.sh {1}" \
    --bind="load:pos(${first_window_pos:-1})" \
    --bind='ctrl-p:toggle-preview' \
    --bind='q:abort' \
    --bind='j:down,k:up' \
    --bind='j:+transform:[[ -z {1} ]] && { [[ \$FZF_POS -eq \$FZF_MATCH_COUNT ]] && echo up || echo down; }' \
    --bind='k:+transform:[[ -z {1} ]] && { [[ \$FZF_POS -eq 1 ]] && echo down || echo up; }' \
    > "$tmpfile" 2>/dev/null
FZFEOF
chmod +x "$fzf_script"

tmux display-popup -b none -w 80% -h 80% -E "$fzf_script" 2>/dev/null

rm -f "$fzf_script" "$tmp_list"
line=$(cat "$tmpfile")
rm -f "$tmpfile"

# 解析选中行
if [[ -n "$line" ]]; then
    target=$(echo "$line" | cut -f1)
    if [[ -z "$target" ]]; then
        sname=$(echo "$line" | cut -f3)
        target=$(tmux list-windows -t "$sname" -F "${sname}:#{window_index}" 2>/dev/null \
            | while IFS= read -r w; do
                [[ "$w" != "$self_window" ]] && { echo "$w"; break; }
            done)
    fi
    [[ -n "$target" ]] && tmux switch-client -t "$target"
fi
