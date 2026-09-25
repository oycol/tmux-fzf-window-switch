#!/usr/bin/env bash
# jump.sh — 控制 fzf 光标导航（跳过不可选行、跨 Session 飞跃、跳转上次窗口）
# 用法: jump.sh <down|up|next-session|prev-session|last|session-N> <list_file>

action="$1"
list="$2"
pos="${FZF_POS:-1}"
total="${FZF_MATCH_COUNT:-1}"
query="${FZF_QUERY:-}"

[[ ! -f "$list" ]] && { echo "ignore"; exit 0; }

awk -F'\t' -v action="$action" -v pos="$pos" -v total="$total" -v query="$query" '
BEGIN {
    if (query != "") {
        if (action == "down" || action == "next-session") print "down";
        else if (action == "up" || action == "prev-session") print "up";
        else print "ignore";
        exit;
    }
}
{
    type[NR] = $3;
}
END {
    if (query != "") exit;
    
    if (action == "down") {
        for (p = pos + 1; p <= total; p++) {
            if (type[p] != "SESSION" && type[p] != "CURRENT") {
                print "pos(" p ")";
                exit;
            }
        }
        print "ignore";
    } else if (action == "up") {
        for (p = pos - 1; p >= 1; p--) {
            if (type[p] != "SESSION" && type[p] != "CURRENT") {
                print "pos(" p ")";
                exit;
            }
        }
        print "ignore";
    } else if (action == "next-session") {
        found_sess = 0;
        for (p = pos + 1; p <= total; p++) {
            if (type[p] == "SESSION") {
                found_sess = 1;
            } else if (found_sess && type[p] != "SESSION" && type[p] != "CURRENT") {
                print "pos(" p ")";
                exit;
            }
        }
        # 循环回滚至第一个 Session
        found_sess = 0;
        for (p = 1; p <= total; p++) {
            if (type[p] == "SESSION") {
                found_sess = 1;
            } else if (found_sess && type[p] != "SESSION" && type[p] != "CURRENT") {
                print "pos(" p ")";
                exit;
            }
        }
        print "ignore";
    } else if (action == "prev-session") {
        cur_sess = 0;
        for (p = pos; p >= 1; p--) {
            if (type[p] == "SESSION") {
                cur_sess = p;
                break;
            }
        }
        prev_sess = 0;
        if (cur_sess > 1) {
            for (p = cur_sess - 1; p >= 1; p--) {
                if (type[p] == "SESSION") {
                    prev_sess = p;
                    break;
                }
            }
        }
        if (prev_sess > 0) {
            for (p = prev_sess + 1; p <= total; p++) {
                if (type[p] != "SESSION" && type[p] != "CURRENT") {
                    print "pos(" p ")";
                    exit;
                }
            }
        }
        # 循环回滚至最后一个 Session
        last_sess = 0;
        for (p = total; p >= 1; p--) {
            if (type[p] == "SESSION") {
                last_sess = p;
                break;
            }
        }
        if (last_sess > 0) {
            for (p = last_sess + 1; p <= total; p++) {
                if (type[p] != "SESSION" && type[p] != "CURRENT") {
                    print "pos(" p ")";
                    exit;
                }
            }
        }
        print "ignore";
    } else if (action == "last") {
        last_p = 0;
        first_win = 0;
        for (p = 1; p <= total; p++) {
            if (first_win == 0 && type[p] != "SESSION" && type[p] != "CURRENT") {
                first_win = p;
            }
            if (type[p] == "LAST") {
                last_p = p;
            }
        }
        if (last_p > 0) {
            if (pos == last_p && first_win > 0 && first_win != last_p) {
                print "pos(" first_win ")";
            } else {
                print "pos(" last_p ")";
            }
            exit;
        }
        print "ignore";
    } else if (action ~ /^session-[0-9]+$/) {
        split(action, arr, "-");
        target_s = arr[2] + 0;
        sess_count = 0;
        for (p = 1; p <= total; p++) {
            if (type[p] == "SESSION") {
                sess_count++;
                if (sess_count == target_s) {
                    for (w = p + 1; w <= total; w++) {
                        if (type[w] == "SESSION") break;
                        if (type[w] != "SESSION" && type[w] != "CURRENT") {
                            print "pos(" w ")";
                            exit;
                        }
                    }
                }
            }
        }
        print "ignore";
    } else {
        print "ignore";
    }
}
' "$list"
