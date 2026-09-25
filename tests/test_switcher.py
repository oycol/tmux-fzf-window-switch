#!/usr/bin/env python3
# test_switcher.py — 包含 Tabby PTY 仿真与 2D 边框网格断言的全面自动化测试套件
import os, sys, subprocess, tempfile, time, pty, fcntl, struct, termios

SCRIPT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../scripts'))

def run_cmd(cmd, env=None):
    return subprocess.run(cmd, capture_output=True, text=True, env=env)

def test_list_generation_and_tabby_safety():
    print("1. Testing list.py generation & Tabby compatibility...")
    r = subprocess.run(['tmux', 'display-message', '-p', '#{session_name}:#{window_index}'],
                       capture_output=True, text=True)
    cur_win = r.stdout.strip()
    res = subprocess.run([os.path.join(SCRIPT_DIR, 'list.py'), cur_win], capture_output=True, text=True)
    assert res.returncode == 0, f"list.py failed: {res.stderr}"

    # Tabby 安全断言：严禁包含任何 \x1b[8m (Conceal) 隐藏字符，防止在 Tabby 等终端被当成普通文本泄露
    assert '\x1b[8m' not in res.stdout, "FATAL: Found \\x1b[8m in list output! Tabby does not support conceal!"

    lines = res.stdout.strip().split('\n')
    assert len(lines) >= 3, f"Expected at least 3 lines, got {len(lines)}"

    last_count = 0
    current_count = 0
    session_count = 0

    for l in lines:
        parts = l.split('\t')
        assert len(parts) == 4, f"Line must have 4 fields: {l}"
        target, disp, row_type, sname = parts
        if row_type == 'SESSION':
            session_count += 1
            assert target.startswith('SESSION:')
        elif row_type == 'CURRENT':
            current_count += 1
            assert '*' in disp
        elif row_type == 'LAST':
            last_count += 1
            assert '-' in disp

    # 全局唯一 [-] 校验：全屏最多只能有 1 个 [-]（只属于当前会话）
    assert last_count <= 1, f"Found {last_count} LAST windows! There must be at most 1 unique LAST window!"
    assert current_count == 1, "There must be exactly 1 CURRENT window!"
    print("✓ list.py Tabby safety & unique [-] verified")

def test_jump_logic():
    print("2. Testing jump.sh logic matrix...")
    jump_sh = os.path.join(SCRIPT_DIR, 'jump.sh')

    # 构造两个 Session 的混合测试数据
    test_content = (
        "SESSION:s1\t► [1] s1 (3 windows)\tSESSION\ts1\n"
        "s1:0\t     1.0  bash          ~\tWINDOW\ts1\n"
        "s1:1\t  *  1.1  bash          ~\tCURRENT\ts1\n"
        "s1:2\t  -  1.2  bash          ~\tLAST\ts1\n"
        "SESSION:s2\t► [2] bios (2 windows)\tSESSION\ts2\n"
        "s2:0\t     2.0  make          ~\tWINDOW\ts2\n"
        "s2:1\t     2.1  gdb           ~\tWINDOW\ts2\n"
    )

    with tempfile.NamedTemporaryFile('w', delete=False) as f:
        f.write(test_content)
        list_path = f.name

    try:
        # Case 1: down from pos 1 (SESSION) skips CURRENT(3) to pos 2 (1.0)
        env = {**os.environ, 'FZF_POS': '1', 'FZF_MATCH_COUNT': '7', 'FZF_QUERY': ''}
        r = run_cmd([jump_sh, 'down', list_path], env=env)
        assert r.stdout.strip() == 'pos(2)', f"Expected pos(2), got {r.stdout.strip()}"

        # Case 2: down from pos 2 skips CURRENT(3) to LAST(4)
        env = {**os.environ, 'FZF_POS': '2', 'FZF_MATCH_COUNT': '7', 'FZF_QUERY': ''}
        r = run_cmd([jump_sh, 'down', list_path], env=env)
        assert r.stdout.strip() == 'pos(4)', f"Expected pos(4), got {r.stdout.strip()}"

        # Case 3: down from pos 4 skips SESSION(5) to pos 6 (2.0)
        env = {**os.environ, 'FZF_POS': '4', 'FZF_MATCH_COUNT': '7', 'FZF_QUERY': ''}
        r = run_cmd([jump_sh, 'down', list_path], env=env)
        assert r.stdout.strip() == 'pos(6)', f"Expected pos(6), got {r.stdout.strip()}"

        # Case 4: down at bottom (pos 7) ignores
        env = {**os.environ, 'FZF_POS': '7', 'FZF_MATCH_COUNT': '7', 'FZF_QUERY': ''}
        r = run_cmd([jump_sh, 'down', list_path], env=env)
        assert r.stdout.strip() == 'ignore'

        # Case 5: up from pos 6 skips SESSION(5) to pos 4 (1.2)
        env = {**os.environ, 'FZF_POS': '6', 'FZF_MATCH_COUNT': '7', 'FZF_QUERY': ''}
        r = run_cmd([jump_sh, 'up', list_path], env=env)
        assert r.stdout.strip() == 'pos(4)', f"Expected pos(4), got {r.stdout.strip()}"

        # Case 6: next-session (J / ]) from pos 2 (in s1) jumps directly to pos 6 (first window in s2)
        env = {**os.environ, 'FZF_POS': '2', 'FZF_MATCH_COUNT': '7', 'FZF_QUERY': ''}
        r = run_cmd([jump_sh, 'next-session', list_path], env=env)
        assert r.stdout.strip() == 'pos(6)', f"Expected pos(6), got {r.stdout.strip()}"

        # Case 6b: next-session (J / ]) from pos 6 (in s2, last session) CYCLES back to pos 2 (first window in s1)
        env = {**os.environ, 'FZF_POS': '6', 'FZF_MATCH_COUNT': '7', 'FZF_QUERY': ''}
        r = run_cmd([jump_sh, 'next-session', list_path], env=env)
        assert r.stdout.strip() == 'pos(2)', f"Expected cycling pos(2), got {r.stdout.strip()}"

        # Case 7: prev-session (K / [) from pos 7 (in s2) jumps back to pos 2 (first window in s1)
        env = {**os.environ, 'FZF_POS': '7', 'FZF_MATCH_COUNT': '7', 'FZF_QUERY': ''}
        r = run_cmd([jump_sh, 'prev-session', list_path], env=env)
        assert r.stdout.strip() == 'pos(2)', f"Expected pos(2), got {r.stdout.strip()}"

        # Case 7b: prev-session (K / [) from pos 2 (in s1, first session) CYCLES to pos 6 (first window in s2)
        env = {**os.environ, 'FZF_POS': '2', 'FZF_MATCH_COUNT': '7', 'FZF_QUERY': ''}
        r = run_cmd([jump_sh, 'prev-session', list_path], env=env)
        assert r.stdout.strip() == 'pos(6)', f"Expected cycling pos(6), got {r.stdout.strip()}"

        # Case 8: Tab (last) jumps to pos 4 (LAST window)
        env = {**os.environ, 'FZF_POS': '6', 'FZF_MATCH_COUNT': '7', 'FZF_QUERY': ''}
        r = run_cmd([jump_sh, 'last', list_path], env=env)
        assert r.stdout.strip() == 'pos(4)', f"Expected pos(4), got {r.stdout.strip()}"

        # Case 9: When FZF_QUERY is not empty, down outputs down, up outputs up
        env = {**os.environ, 'FZF_POS': '1', 'FZF_MATCH_COUNT': '2', 'FZF_QUERY': '2.2'}
        r = run_cmd([jump_sh, 'down', list_path], env=env)
        assert r.stdout.strip() == 'down'
        r = run_cmd([jump_sh, 'up', list_path], env=env)
        assert r.stdout.strip() == 'up'

    finally:
        os.remove(list_path)

    print("✓ jump.sh test passed")

def test_preview_bordered_grid():
    print("3. Testing preview.py 2D bordered grid...")
    r_sess = subprocess.run(['tmux', 'display-message', '-p', '#{session_name}'], capture_output=True, text=True)
    sess_name = r_sess.stdout.strip()

    # Session 概览测试
    r = subprocess.run([os.path.join(SCRIPT_DIR, 'preview.py'), f'SESSION:{sess_name}', '20', '80'],
                       capture_output=True, text=True)
    assert r.returncode == 0
    assert f'Session: {sess_name}' in r.stdout

    # Window 头部卡片与边框测试
    r = subprocess.run([os.path.join(SCRIPT_DIR, 'preview.py'), f'{sess_name}:0', '20', '80'],
                       capture_output=True, text=True)
    assert r.returncode == 0
    assert f'[ {sess_name}:0' in r.stdout, f"Missing window header card: {r.stdout[:200]}"
    assert '─' in r.stdout, "Missing divider lines in preview"

    print("✓ preview.py 2D grid test passed")

def test_tabby_interactive_pty_scenarios():
    print("4. Testing Tabby PTY terminal interactive suite (10 scenarios)...")
    test_content = (
        "SESSION:s1\t► [1] s1 (3 windows)\tSESSION\ts1\n"
        "s1:0\t     1.0  bash          ~\tWINDOW\ts1\n"
        "s1:1\t  *  1.1  bash          ~\tCURRENT\ts1\n"
        "s1:2\t  -  1.2  bash          ~\tLAST\ts1\n"
        "SESSION:s2\t► [2] bios (2 windows)\tSESSION\ts2\n"
        "s2:0\t     2.0  make          ~\tWINDOW\ts2\n"
        "s2:1\t     2.1  gdb           ~\tWINDOW\ts2\n"
    )

    def run_tabby_pty(keys_to_send, start_pos='4'):
        with tempfile.NamedTemporaryFile('w', delete=False) as f:
            f.write(test_content)
            list_file = f.name

        out_file = tempfile.mktemp()
        master, slave = pty.openpty()

        # 模拟 Tabby 典型高分屏窗口尺寸 (40x140)
        winsize = struct.pack('HHHH', 40, 140, 0, 0)
        fcntl.ioctl(slave, termios.TIOCSWINSZ, winsize)

        env = {
            **os.environ,
            'TERM': 'xterm-256color',
            'COLORTERM': 'truecolor',
            'SD': SCRIPT_DIR,
            'BL': list_file,
            'POS': start_pos,
            'SELF_WINDOW': 's1:1'
        }

        fzf_script_content = f"""#!/usr/bin/env bash
export TAB=$'\\t'
cat "{list_file}" | fzf \\
    --sync \\
    --reverse --no-cycle --pointer='→' \\
    --footer=' [Enter] 切换  [Tab] 上次窗口(-)  [J/K] 跨会话  [^x] 关闭窗口  [^p] 预览  [q] 退出' \\
    -d $'\\t' --with-nth=2 --no-info --ansi \\
    --preview='{os.path.join(SCRIPT_DIR, "preview.sh")} {{1}}' \\
    --bind='start:pos({start_pos})' \\
    --bind='load:pos({start_pos})' \\
    --bind='j:transform("{os.path.join(SCRIPT_DIR, "jump.sh")}" down "{list_file}")' \\
    --bind='down:transform("{os.path.join(SCRIPT_DIR, "jump.sh")}" down "{list_file}")' \\
    --bind='k:transform("{os.path.join(SCRIPT_DIR, "jump.sh")}" up "{list_file}")' \\
    --bind='up:transform("{os.path.join(SCRIPT_DIR, "jump.sh")}" up "{list_file}")' \\
    --bind='J:transform("{os.path.join(SCRIPT_DIR, "jump.sh")}" next-session "{list_file}")' \\
    --bind=']:transform("{os.path.join(SCRIPT_DIR, "jump.sh")}" next-session "{list_file}")' \\
    --bind='K:transform("{os.path.join(SCRIPT_DIR, "jump.sh")}" prev-session "{list_file}")' \\
    --bind='[:transform("{os.path.join(SCRIPT_DIR, "jump.sh")}" prev-session "{list_file}")' \\
    --bind='tab,ctrl-i:transform("{os.path.join(SCRIPT_DIR, "jump.sh")}" last "{list_file}")' \\
    --bind='q:abort' \\
    --bind='esc:abort' \\
    --bind='enter:transform([[ {{}} == *"$TAB"CURRENT"$TAB"* ]] && echo ignore || echo accept)' \\
    > "{out_file}"
"""
        with tempfile.NamedTemporaryFile('w', delete=False) as sf:
            sf.write(fzf_script_content)
            sf.flush()
            script_path = sf.name
        os.chmod(script_path, 0o755)

        p = subprocess.Popen([script_path], stdin=slave, stdout=slave, stderr=slave, env=env)
        os.close(slave)

        time.sleep(0.3)
        for k in keys_to_send:
            os.write(master, k)
            time.sleep(0.12)
        time.sleep(0.2)
        p.wait(timeout=5)

        with open(out_file) as f:
            chosen = f.read().strip()

        os.remove(list_file)
        os.remove(script_path)
        if os.path.exists(out_file):
            os.remove(out_file)

        return chosen.split('\t')[0] if chosen else ''

    # Scenario 1: S.W 坐标盲打跳转（输入 '2.1' 回车直达 s2:1）
    res1 = run_tabby_pty([b'2', b'.', b'1', b'\r'], start_pos='4')
    assert res1 == 's2:1', f"Scenario 1 failed: expected s2:1, got {res1}"

    # Scenario 2: 跨 Session 快捷键 J 飞跃（从 s1:0 跳到 s2:0）
    res2 = run_tabby_pty([b'J', b'\r'], start_pos='2')
    assert res2 == 's2:0', f"Scenario 2 failed: expected s2:0, got {res2}"

    # Scenario 3: Tabby Tab 键（\t）唯一定位到 LAST 窗口 (s1:2)
    res3 = run_tabby_pty([b'\t', b'\r'], start_pos='6')
    assert res3 == 's1:2', f"Scenario 3 failed: expected s1:2, got {res3}"

    # Scenario 4: J 循环跨 Session（从底部 s2 循环飞回顶部 s1:0）
    res4 = run_tabby_pty([b'J', b'\r'], start_pos='6')
    assert res4 == 's1:0', f"Scenario 4 failed: expected s1:0, got {res4}"

    # Scenario 5: K 循环跨 Session（从顶部 s1:0 循环飞回底部 s2:0）
    res5 = run_tabby_pty([b'K', b'\r'], start_pos='2')
    assert res5 == 's2:0', f"Scenario 5 failed: expected s2:0, got {res5}"

    # Scenario 6: Vim 中括号成对跳转（] 等同于 J 循环向下一会话）
    res6 = run_tabby_pty([b']', b'\r'], start_pos='2')
    assert res6 == 's2:0', f"Scenario 6 failed: expected s2:0, got {res6}"

    # Scenario 7: 方向键 Down 避让非可选行（从 1.0 避让 CURRENT(1.1) 直达 1.2）
    res7 = run_tabby_pty([b'\x1b[B', b'\r'], start_pos='2')
    assert res7 == 's1:2', f"Scenario 7 failed: expected s1:2, got {res7}"

    # Scenario 8: 方向键 Up 避让非可选行（从 2.0 避让 SESSION 标题直达 1.2）
    res8 = run_tabby_pty([b'\x1b[A', b'\r'], start_pos='6')
    assert res8 == 's1:2', f"Scenario 8 failed: expected s1:2, got {res8}"

    # Scenario 9: 模糊搜索窗口名（输入 'gdb' 回车直达 s2:1）
    res9 = run_tabby_pty([b'g', b'd', b'b', b'\r'], start_pos='2')
    assert res9 == 's2:1', f"Scenario 9 failed: expected s2:1, got {res9}"

    # Scenario 10: 按 Esc 键正常退出（返回空）
    res10 = run_tabby_pty([b'\x1b'], start_pos='4')
    assert res10 == '', f"Scenario 10 failed: expected empty, got {res10}"

    print("✓ Tabby PTY terminal interactive suite (10 scenarios) passed")

if __name__ == '__main__':
    test_list_generation_and_tabby_safety()
    test_jump_logic()
    test_preview_bordered_grid()
    test_tabby_interactive_pty_scenarios()
    print("\nALL SWITCHER & TABBY PTY CI TESTS PASSED SUCCESSFULLY!")
