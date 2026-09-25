#!/usr/bin/env python3
# list.py — 生成带有 S.W 坐标系统、全局唯一 [-] 与 Pane 拓扑的列表
import sys, os, subprocess, unicodedata

def str_w(s):
    return sum(2 if unicodedata.east_asian_width(c) in ('W', 'F') else 1 for c in s)

def fit(s, width, align='left'):
    if not s:
        return ' ' * width
    w = 0
    res = []
    for ch in s:
        cw = 2 if unicodedata.east_asian_width(ch) in ('W', 'F') else 1
        if w + cw > width:
            break
        res.append(ch)
        w += cw
    pad = ' ' * max(0, width - w)
    return (''.join(res) + pad) if align == 'left' else (pad + ''.join(res))

def compact_path(p, home, max_len=18):
    if home and p.startswith(home):
        p = '~' + p[len(home):]
    if len(p) <= max_len:
        return fit(p, max_len)
    parts = p.split('/')
    if len(parts) >= 3:
        short = f'{parts[0]}/.../{parts[-1]}'
        if len(short) <= max_len:
            return fit(short, max_len)
    return fit(p[:max_len-3] + '...', max_len)

def main():
    self_window = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] else ''
    if not self_window:
        r = subprocess.run(['tmux', 'display-message', '-p', '#{session_name}:#{window_index}'],
                           capture_output=True, text=True)
        self_window = r.stdout.strip()

    self_session = self_window.split(':')[0] if ':' in self_window else ''
    home = os.environ.get('HOME', '')

    # 1. 批量获取所有 pane 列表
    panes_raw = subprocess.run([
        'tmux', 'list-panes', '-a', '-F',
        '#{session_name}:#{window_index}\t#{pane_index}\t#{pane_active}\t#{pane_current_command}'
    ], capture_output=True, text=True).stdout.strip().split('\n')

    panes_map = {}
    for line in panes_raw:
        if not line:
            continue
        parts = line.split('\t')
        if len(parts) >= 4:
            key, pidx, pact, pcmd = parts[0], parts[1], parts[2], parts[3]
            if key not in panes_map:
                panes_map[key] = []
            panes_map[key].append((pidx, pact == '1', pcmd))

    # 2. 批量获取所有 window 列表
    raw = subprocess.run([
        'tmux', 'list-windows', '-a', '-F',
        '#{session_name}|#{window_index}|#{window_name}|#{window_active}|#{window_last_flag}|#{window_activity_flag}|#{window_zoomed_flag}|#{window_panes}|#{pane_current_command}|#{pane_current_path}'
    ], capture_output=True, text=True).stdout.strip().split('\n')

    sessions = {}
    for line in raw:
        if not line:
            continue
        parts = line.split('|')
        sname = parts[0]
        if sname not in sessions:
            sessions[sname] = []
        sessions[sname].append(parts)

    out_lines = []
    sess_idx = 1
    for sname, wins in sessions.items():
        s_disp = f'\x1b[1;38;5;111m► [{sess_idx}] {sname}\x1b[0m \x1b[38;5;244m({len(wins)} windows)\x1b[0m'
        out_lines.append(f'SESSION:{sname}\t{s_disp}\tSESSION\t{sname}')

        for w in wins:
            sname, widx, wname, active, last_flag, act_flag, zoomed, n_panes, cmd_name, path = w
            target = f'{sname}:{widx}'
            is_current = (target == self_window)
            # 严格保证全局唯一 [-]：只有当前 Session 内部的上一活跃窗口才标注 [-]
            is_last = (sname == self_session and last_flag == '1' and not is_current)

            coord = f'{sess_idx}.{widx}'
            coord_fmt = fit(coord, 4, 'right')
            p_comp = compact_path(path, home, 18)

            # 多 Pane 概要标签
            p_list = panes_map.get(target, [])
            if len(p_list) > 1:
                pane_cmds = []
                for pidx, pact, pcmd in p_list:
                    pane_cmds.append(f'{pcmd}*' if pact else pcmd)
                pane_tag = f'{len(p_list)}p: ' + ','.join(pane_cmds[:3])
            else:
                pane_tag = cmd_name

            if is_current:
                row_type = 'CURRENT'
                flag = '\x1b[38;5;244m* \x1b[0m'
                c_str = f'\x1b[38;5;244m{coord_fmt}\x1b[0m'
                n_str = f'\x1b[38;5;244m{fit(wname, 12)}\x1b[0m'
                p_str = f'\x1b[38;5;240m{p_comp}\x1b[0m'
                t_str = f'\x1b[38;5;240m{fit(pane_tag, 16)}\x1b[0m'
                s_tag = f'\x1b[38;5;236m[{sname}]\x1b[0m'
            else:
                if is_last:
                    row_type = 'LAST'
                    flag = '\x1b[38;5;111m- \x1b[0m'
                elif act_flag == '1':
                    row_type = 'WINDOW'
                    flag = '\x1b[38;5;150m● \x1b[0m'
                elif zoomed == '1':
                    row_type = 'WINDOW'
                    flag = '\x1b[38;5;214mZ \x1b[0m'
                else:
                    row_type = 'WINDOW'
                    flag = '  '

                c_str = f'\x1b[38;5;111m{coord_fmt}\x1b[0m'
                n_str = f'\x1b[38;5;253m{fit(wname, 12)}\x1b[0m'
                p_str = f'\x1b[38;5;244m{p_comp}\x1b[0m'
                t_str = f'\x1b[38;5;216m{fit(pane_tag, 16)}\x1b[0m'
                s_tag = f'\x1b[38;5;238m[{sname}]\x1b[0m'

            disp = f'  {flag}{c_str}  {n_str}  {p_str}  {t_str}  {s_tag}'
            out_lines.append(f'{target}\t{disp}\t{row_type}\t{sname}')

        sess_idx += 1

    for l in out_lines:
        print(l)

if __name__ == '__main__':
    main()
