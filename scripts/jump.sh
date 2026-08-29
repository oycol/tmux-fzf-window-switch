#!/usr/bin/env bash
# jump.sh — j/k 跳过不可选行，输出 pos(N) 或 ignore
# 用法: jump.sh <up|down> <list_file>
# 依赖 fzf 导出的 FZF_POS(1-based光标) 和 FZF_MATCH_COUNT(总行数)
# 不可选行: field1 为空(SESSION标题) 或 field3 为 CURRENT
# fzf 通过 transform 调用本脚本，stdout 作为 fzf action

dir="$1"
list="$2"
pos="${FZF_POS:-1}"
total="${FZF_MATCH_COUNT:-1}"

# 沿方向找下一个可选行(field1非空 且 field3非CURRENT)
if [[ "$dir" == "down" ]]; then
    p=$((pos + 1))
    while ((p <= total)); do
        line=$(sed -n "${p}p" "$list")
        f1=$(printf '%s' "$line" | cut -f1)
        f3=$(printf '%s' "$line" | cut -f3)
        [[ -n "$f1" && "$f3" != "CURRENT" ]] && { echo "pos($p)"; exit 0; }
        ((p++))
    done
    echo "ignore"
else
    p=$((pos - 1))
    while ((p >= 1)); do
        line=$(sed -n "${p}p" "$list")
        f1=$(printf '%s' "$line" | cut -f1)
        f3=$(printf '%s' "$line" | cut -f3)
        [[ -n "$f1" && "$f3" != "CURRENT" ]] && { echo "pos($p)"; exit 0; }
        ((p--))
    done
    echo "ignore"
fi
