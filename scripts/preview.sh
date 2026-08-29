#!/usr/bin/env bash
# tmux-fzf-preview.sh — 实时预览目标 window 画面（保留 pane 布局）
# 用法: tmux-fzf-preview.sh <target>

target="$1"
[[ -z "$target" ]] && exit 0

lines="${FZF_PREVIEW_LINES:-40}"
cols="${FZF_PREVIEW_COLUMNS:-82}"

np=$(tmux list-panes -t "$target" -F '#{pane_index}' 2>/dev/null | wc -l)

if [[ "$np" -le 1 ]]; then
    while true; do
        printf '\033[2J\033[H'
        tmux capture-pane -t "$target" -p -e -J 2>/dev/null \
            | sed -e :a -e '/^\n*$/{$d;N;ba}' | tail -n "$lines"
        sleep 3
    done
fi

PYSCRIPT=$(mktemp)
cat > "$PYSCRIPT" << 'PYEOF'
import subprocess, re, unicodedata, sys
from collections import defaultdict

target = sys.argv[1]
max_lines = int(sys.argv[2])
cols = int(sys.argv[3])

raw = subprocess.run(['tmux', 'list-panes', '-t', target, '-F',
    '#{pane_index}\t#{pane_left}\t#{pane_top}\t#{pane_width}\t#{pane_height}'],
    capture_output=True, text=True).stdout.strip()

if not raw:
    print('(no preview)')
    sys.exit()

panes = []
for line in raw.split('\n'):
    parts = line.split('\t')
    panes.append({
        'idx': parts[0], 'left': int(parts[1]), 'top': int(parts[2]),
        'w': int(parts[3]), 'h': int(parts[4])
    })

rows = defaultdict(list)
for p in panes:
    rows[p['top']].append(p)
sorted_tops = sorted(rows.keys())
num_rows = len(sorted_tops)

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

def capture(pane_idx):
    r = subprocess.run(['tmux', 'capture-pane', '-t', f'{target}.{pane_idx}',
        '-p', '-e', '-J'], capture_output=True, text=True)
    lines = r.stdout.split('\n')
    while lines and not lines[-1].strip():
        lines.pop()
    return lines

sep_v = '\033[90m│\033[0m'
sep_h = '\033[90m' + '─' * cols + '\033[0m'

def get_pane_widths(row_panes, cols):
    n = len(row_panes)
    if n == 1:
        return [cols]
    total_w = sum(p['w'] for p in row_panes)
    pane_widths = []
    for p in row_panes:
        pw = (cols - (n - 1)) * p['w'] // total_w
        pane_widths.append(pw)
    diff = cols - (n - 1) - sum(pane_widths)
    if diff:
        widest = pane_widths.index(max(pane_widths))
        pane_widths[widest] += diff
    return pane_widths

def render_row(row_panes, alloc, cols):
    n = len(row_panes)
    if n == 1:
        cap = capture(row_panes[0]['idx'])
        result = [truncate(line, cols) for line in cap[-alloc:]]
        while len(result) < alloc:
            result.append(' ' * cols)
        return result
    
    pane_widths = get_pane_widths(row_panes, cols)
    caps = [capture(p['idx']) for p in row_panes]
    
    # 底部对齐
    max_cap = max(len(c) for c in caps)
    for i in range(len(caps)):
        while len(caps[i]) < max_cap:
            caps[i].insert(0, '')
    
    merged = []
    for i in range(max_cap):
        parts = []
        for j, cap in enumerate(caps):
            line = cap[i] if i < len(cap) else ''
            parts.append(truncate(line, pane_widths[j]))
        merged.append(sep_v.join(parts))
    
    result = merged[-alloc:]
    while len(result) < alloc:
        result.append(sep_v.join(' ' * pw for pw in pane_widths))
    return result

# ── 分配行数 ──
row_max_h = {}
for top in sorted_tops:
    row_max_h[top] = max(p['h'] for p in rows[top])

total_h = sum(row_max_h.values())
sep_count = num_rows - 1
available = max_lines - sep_count

row_alloc = {}
for top in sorted_tops:
    row_alloc[top] = max(1, int(available * row_max_h[top] / total_h))

allocated = sum(row_alloc.values())
if allocated < available:
    tallest = max(sorted_tops, key=lambda t: row_max_h[t])
    row_alloc[tallest] += available - allocated

output = []
for ri, top in enumerate(sorted_tops):
    if ri > 0:
        output.append(sep_h)
    
    row_panes = sorted(rows[top], key=lambda p: p['left'])
    alloc = row_alloc[top]
    output.extend(render_row(row_panes, alloc, cols))

print('\n'.join(output))
PYEOF

while true; do
    printf '\033[2J\033[H'
    python3 "$PYSCRIPT" "$target" "$lines" "$cols" 2>/dev/null
    sleep 3
done
