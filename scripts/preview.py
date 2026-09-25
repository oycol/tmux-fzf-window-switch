#!/usr/bin/env python3
# preview.py — 零闪烁、四方边框自适应网格的 tmux 窗口与会话预览器
import sys, os, subprocess, re, time, unicodedata
from collections import defaultdict

ansi_re = re.compile(r'(\x1b\[[0-9;]*m)')

def disp_w(ch):
    return 2 if unicodedata.east_asian_width(ch) in ('W', 'F') else 1

def truncate(line, width):
    if width <= 0:
        return ''
    out = ''
    w = 0
    for part in ansi_re.split(line):
        if part.startswith('\x1b'):
            out += part
        else:
            for ch in part:
                cw = disp_w(ch)
                if w + cw > width:
                    out += '\x1b[0m'
                    w = width
                    break
                out += ch
                w += cw
            if w >= width:
                break
    out += '\x1b[0m'
    if w < width:
        out += ' ' * (width - w)
    return out

def render_session(sname, max_lines, cols):
    r = subprocess.run([
        'tmux', 'display-message', '-t', f'{sname}:', '-p',
        '#{session_name}|#{session_windows}|#{session_created}|#{session_attached}'
    ], capture_output=True, text=True)
    if r.returncode != 0 or not r.stdout.strip():
        print(f'\x1b[38;5;244m(Session {sname} not found)\x1b[0m')
        return

    parts = r.stdout.strip().split('|')
    name, n_win, created, attached = parts[0], parts[1], parts[2], int(parts[3]) if parts[3].isdigit() else 0
    created_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(created))) if created.isdigit() else created
    att_str = '\x1b[38;5;150mAttached (active)\x1b[0m' if attached > 0 else '\x1b[38;5;244mDetached\x1b[0m'

    out = []
    out.append(f'\x1b[1;38;5;111m► Session: {name}\x1b[0m')
    out.append(f'  \x1b[38;5;244mStatus:\x1b[0m   {att_str}')
    out.append(f'  \x1b[38;5;244mWindows:\x1b[0m  {n_win}')
    out.append(f'  \x1b[38;5;244mCreated:\x1b[0m  {created_str}')
    out.append('')
    sep = '─' * min(cols, 60)
    out.append(f'\x1b[38;5;240m{sep}\x1b[0m')
    out.append('\x1b[1;38;5;253mWindows in this session:\x1b[0m')

    wins = subprocess.run([
        'tmux', 'list-windows', '-t', sname, '-F',
        '#{window_index}|#{window_name}|#{window_active}|#{window_panes}|#{pane_current_command}|#{pane_current_path}'
    ], capture_output=True, text=True).stdout.strip().split('\n')

    home = os.environ.get('HOME', '')
    for w in wins:
        if not w:
            continue
        p = w.split('|')
        widx, wname, active, panes, cmd, path = p[0], p[1], p[2], p[3], p[4], p[5]
        p_comp = path.replace(home, '~') if home and path.startswith(home) else path
        marker = '\x1b[38;5;150m*\x1b[0m' if active == '1' else ' '
        panes_tag = f'({panes}p)' if int(panes) > 1 else ''
        line = f'  {marker} \x1b[38;5;111m{widx:>2}\x1b[0m: \x1b[38;5;253m{wname:<12}\x1b[0m \x1b[38;5;216m[{cmd}]\x1b[0m \x1b[38;5;244m{p_comp}\x1b[0m {panes_tag}'
        out.append(truncate(line, cols))
        if len(out) >= max_lines:
            break

    print('\n'.join(out[:max_lines]))

def capture_pane_lines(target, pane_idx):
    pane_target = f'{target}.{pane_idx}' if pane_idx is not None else target
    r = subprocess.run(['tmux', 'capture-pane', '-t', pane_target, '-p', '-e', '-J'],
                       capture_output=True, text=True)
    lines = r.stdout.split('\n')
    while lines and not lines[-1].strip():
        lines.pop()
    return lines

def render_window_header(target, cols):
    winfo = subprocess.run([
        'tmux', 'display-message', '-t', target, '-p',
        '#{session_name}|#{window_index}|#{window_name}|#{window_panes}|#{pane_current_command}|#{pane_current_path}'
    ], capture_output=True, text=True).stdout.strip().split('|')

    if len(winfo) >= 6:
        sname, widx, wname, n_panes, cmd, path = winfo[0], winfo[1], winfo[2], winfo[3], winfo[4], winfo[5]
        home = os.environ.get('HOME', '')
        p_comp = path.replace(home, '~') if home and path.startswith(home) else path
        p_tag = f'{n_panes} panes' if int(n_panes) > 1 else '1 pane'
        title = f'\x1b[1;38;5;111m[ {sname}:{widx} {wname} ]\x1b[0m \x1b[38;5;244m({p_tag}, {cmd}, {p_comp})\x1b[0m'
        sep = '\x1b[38;5;240m' + '─' * cols + '\x1b[0m'
        return [truncate(title, cols), sep]
    return []

def render_single_pane(target, max_lines, cols):
    headers = render_window_header(target, cols)
    avail_lines = max_lines - len(headers)
    if avail_lines <= 0:
        print('\n'.join(headers[:max_lines]))
        return

    lines = capture_pane_lines(target, None)
    if not lines:
        output = headers + ['\x1b[38;5;244m(empty pane)\x1b[0m']
        print('\n'.join(output[:max_lines]))
        return

    visible = lines[-avail_lines:]
    output = headers + [truncate(l, cols) for l in visible]
    print('\n'.join(output[:max_lines]))

def render_multi_panes(target, max_lines, cols):
    headers = render_window_header(target, cols)
    avail_lines = max_lines - len(headers)
    if avail_lines <= 0:
        print('\n'.join(headers[:max_lines]))
        return

    raw = subprocess.run(['tmux', 'list-panes', '-t', target, '-F',
        '#{pane_index}\t#{pane_left}\t#{pane_top}\t#{pane_width}\t#{pane_height}\t#{pane_active}\t#{pane_current_command}\t#{pane_current_path}'],
        capture_output=True, text=True).stdout.strip()
    if not raw:
        print('\n'.join(headers + ['\x1b[38;5;244m(no panes)\x1b[0m']))
        return

    panes = []
    for line in raw.split('\n'):
        parts = line.split('\t')
        panes.append({
            'idx': parts[0],
            'left': int(parts[1]),
            'top': int(parts[2]),
            'w': int(parts[3]),
            'h': int(parts[4]),
            'active': (parts[5] == '1'),
            'cmd': parts[6] if len(parts) > 6 else '',
            'path': parts[7] if len(parts) > 7 else '',
            'lines': capture_pane_lines(target, parts[0])
        })

    orig_w = max(p['left'] + p['w'] for p in panes)
    orig_h = max(p['top'] + p['h'] for p in panes)
    if orig_w == 0 or orig_h == 0:
        render_single_pane(target, max_lines, cols)
        return

    for p in panes:
        x0 = int(p['left'] * cols / orig_w)
        x1 = int((p['left'] + p['w']) * cols / orig_w)
        y0 = int(p['top'] * avail_lines / orig_h)
        y1 = int((p['top'] + p['h']) * avail_lines / orig_h)
        p['box'] = (x0, y0, max(1, x1 - x0), max(1, y1 - y0))

    sep_v = '\x1b[38;5;240m│\x1b[0m'

    grid_output = []
    for y in range(avail_lines):
        starting_panes = [p for p in panes if p['box'][1] == y and y > 0]
        row_panes = [p for p in panes if p['box'][1] <= y < p['box'][1] + p['box'][3]]
        if not row_panes:
            grid_output.append(' ' * cols)
            continue
        row_panes.sort(key=lambda p: p['box'][0])

        parts = []
        n_panes = len(row_panes)
        avail_w = cols - (n_panes - 1)
        total_bw = sum(p['box'][2] for p in row_panes)

        for i, p in enumerate(row_panes):
            pw = max(4, int(avail_w * p['box'][2] / total_bw)) if total_bw > 0 else avail_w
            bx, by, bw, bh = p['box']
            local_y = y - by

            act_star = '*' if p['active'] else ''
            title_tag = f'[ {p["idx"]}: {p["cmd"]}{act_star} ]'

            # 如果当前行是该 pane 的起始行且不在最顶端，绘制横向分隔线
            if local_y == 0 and y > 0 and p in starting_panes:
                tag_color = '\x1b[1;38;5;111m' if p['active'] else '\x1b[38;5;244m'
                fill_len = max(0, pw - len(title_tag) - 1)
                h_line = '─' * fill_len
                line_content = truncate(f'\x1b[38;5;240m─{tag_color}{title_tag}\x1b[38;5;240m{h_line}\x1b[0m', pw)
            elif local_y == 0:
                tag_color = '\x1b[1;38;5;111m' if p['active'] else '\x1b[38;5;244m'
                line_content = truncate(f'{tag_color}{title_tag}\x1b[0m', pw)
            else:
                content_idx = len(p['lines']) - (bh - local_y)
                raw_txt = p['lines'][content_idx] if 0 <= content_idx < len(p['lines']) else ''
                line_content = truncate(raw_txt, pw)

            parts.append(line_content)

        grid_output.append(sep_v.join(parts))

    full_output = headers + grid_output
    print('\n'.join(full_output[:max_lines]))

def main():
    if len(sys.argv) < 2:
        return
    target = sys.argv[1]
    if not target:
        return

    max_lines = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 40
    cols = int(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3].isdigit() else 80

    if target.startswith('SESSION:'):
        sname = target[len('SESSION:'):]
        render_session(sname, max_lines, cols)
        return

    r = subprocess.run(['tmux', 'list-panes', '-t', target, '-F', '#{pane_index}'],
                       capture_output=True, text=True)
    if r.returncode != 0 or not r.stdout.strip():
        print(f'\x1b[38;5;244m(window {target} closed or not found)\x1b[0m')
        return

    panes = r.stdout.strip().split('\n')
    if len(panes) <= 1:
        render_single_pane(target, max_lines, cols)
    else:
        render_multi_panes(target, max_lines, cols)

if __name__ == '__main__':
    main()
