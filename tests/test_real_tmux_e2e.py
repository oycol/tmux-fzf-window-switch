#!/usr/bin/env python3
# test_real_tmux_e2e.py — 100% 真实终端客户端环境下的 tmux + display-popup 全链路端到端自动化测试
import os, sys, subprocess, tempfile, time, pty, fcntl, struct, termios

SCRIPT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../scripts'))

class RealTmuxHarness:
    def __init__(self, sock_path='/tmp/tmux_ci_test.sock'):
        self.sock = sock_path
        self.master = None
        self.client_p = None

    def start(self, client_w=160, client_h=50):
        # 1. 确保旧 server 清理
        subprocess.run(['tmux', '-S', self.sock, 'kill-server'], stderr=subprocess.DEVNULL)
        time.sleep(0.3)

        # 2. 启动基础会话与窗口
        # 会话 s1: win0 (0), win1 (1)
        subprocess.run(['tmux', '-S', self.sock, '-f', '/dev/null', 'new-session', '-d', '-s', 's1', '-x', str(client_w), '-y', str(client_h), '-n', 'win0', 'sleep 300'], check=True)
        subprocess.run(['tmux', '-S', self.sock, 'new-window', '-t', 's1:1', '-n', 'win1', 'sleep 300'], check=True)
        # 会话 s2: win0 (0), win1 (1)
        subprocess.run(['tmux', '-S', self.sock, 'new-session', '-d', '-s', 's2', '-x', str(client_w), '-y', str(client_h), '-n', 'win0', 'sleep 300'], check=True)
        subprocess.run(['tmux', '-S', self.sock, 'new-window', '-t', 's2:1', '-n', 'win1', 'sleep 300'], check=True)

        # 3. 注册 prefix + w 绑定至真实 switch.sh
        subprocess.run([
            'tmux', '-S', self.sock, 'bind-key', 'w',
            'run-shell', '-t', '#{session_id}', f'{SCRIPT_DIR}/switch.sh'
        ], check=True)

        # 4. 启动真实的 Linux 伪终端客户端 attach 到 tmux
        master, slave = pty.openpty()
        winsize = struct.pack('HHHH', client_h, client_w, 0, 0)
        fcntl.ioctl(slave, termios.TIOCSWINSZ, winsize)

        env = {
            **os.environ,
            'TMUX': f'{self.sock},1000,0',
            'TERM': 'xterm-256color',
            'COLORTERM': 'truecolor',
        }
        self.client_p = subprocess.Popen(
            ['tmux', '-S', self.sock, 'attach-session', '-t', 's1:0'],
            stdin=slave, stdout=slave, stderr=slave, env=env
        )
        os.close(slave)
        self.master = master

        # 等待 client 握手就绪
        for _ in range(20):
            time.sleep(0.2)
            r = subprocess.run(['tmux', '-S', self.sock, 'list-clients'], capture_output=True, text=True)
            if 'attached' in r.stdout:
                break
        else:
            raise RuntimeError("Tmux attached client failed to initialize!")

    def send_keys(self, key_bytes, delay=0.15):
        assert self.master is not None
        for b in key_bytes:
            if isinstance(b, int):
                os.write(self.master, bytes([b]))
            elif isinstance(b, bytes):
                os.write(self.master, b)
            time.sleep(delay)

    def trigger_popup(self):
        # 发送 tmux 默认前缀键 C-b (0x02) 然后输入 'w'
        self.send_keys([b'\x02', b'w'], delay=0.25)
        # 等待 popup 渲染完毕
        time.sleep(0.6)

    def get_current_window(self):
        r = subprocess.run([
            'tmux', '-S', self.sock, 'display-message', '-p', '#{session_name}:#{window_index}'
        ], capture_output=True, text=True)
        return r.stdout.strip()

    def get_windows(self, session_name):
        r = subprocess.run([
            'tmux', '-S', self.sock, 'list-windows', '-t', session_name, '-F', '#{window_index}:#{window_name}'
        ], capture_output=True, text=True)
        return [l.strip() for l in r.stdout.strip().split('\n') if l.strip()]

    def switch_to(self, target):
        subprocess.run(['tmux', '-S', self.sock, 'select-window', '-t', target], check=True)
        time.sleep(0.2)

    def close(self):
        if self.client_p:
            self.client_p.terminate()
            try:
                self.client_p.wait(timeout=1)
            except Exception:
                pass
        if self.master:
            try:
                os.close(self.master)
            except Exception:
                pass
        subprocess.run(['tmux', '-S', self.sock, 'kill-server'], stderr=subprocess.DEVNULL)
        time.sleep(0.2)

def run_all_e2e_tests():
    print("=" * 70)
    print("RUNNING REAL TMUX CLIENT END-TO-END TERMINAL TESTS")
    print("=" * 70)

    harness = RealTmuxHarness('/tmp/tmux_real_ci.sock')
    try:
        harness.start(client_w=160, client_h=50)

        # -------------------------------------------------------------
        # Test 1: S.W 坐标盲打直达 (输入 '2.1' -> 回车 -> 切换到 s2:1)
        # -------------------------------------------------------------
        print("\n[Test 1] S.W Coordinate Direct Jump ('2.1' -> s2:1)...")
        assert harness.get_current_window() == 's1:0'
        harness.trigger_popup()
        # 盲打 2.1 敲回车
        harness.send_keys([b'2', b'.', b'1', b'\r'], delay=0.15)
        time.sleep(0.5)
        cur = harness.get_current_window()
        assert cur == 's2:1', f"Test 1 Failed: Expected s2:1, got {cur}"
        print(f"✓ Test 1 Passed! Current window is {cur}")

        # -------------------------------------------------------------
        # Test 2: 跨 Session 快捷键 J 飞跃 (从 s2:1 按 J -> 跳至 s1:0)
        # -------------------------------------------------------------
        print("\n[Test 2] Cross-Session Jump J (from s2:1 -> s1:0)...")
        # 从 s2:1 按 J 循环到下一个 Session (s1) 的第一个窗口 s1:0
        harness.trigger_popup()
        harness.send_keys([b'J', b'\r'], delay=0.2)
        time.sleep(0.5)
        cur = harness.get_current_window()
        assert cur == 's1:0', f"Test 2 Failed: Expected s1:0, got {cur}"
        print(f"✓ Test 2 Passed! Current window is {cur}")

        # -------------------------------------------------------------
        # Test 3: 跨 Session 快捷键 K 循环飞跃 (从 s1:0 按 K -> 循环到 s2:0)
        # -------------------------------------------------------------
        print("\n[Test 3] Cross-Session Jump K with Cycling (from s1:0 -> s2:0)...")
        harness.trigger_popup()
        harness.send_keys([b'K', b'\r'], delay=0.2)
        time.sleep(0.5)
        cur = harness.get_current_window()
        assert cur == 's2:0', f"Test 3 Failed: Expected s2:0, got {cur}"
        print(f"✓ Test 3 Passed! Current window is {cur}")

        # -------------------------------------------------------------
        # Test 4: Tab 键吸附全局唯一 [-] 上次活跃窗口
        # -------------------------------------------------------------
        print("\n[Test 4] Tab Key Snap to Unique Last Window [-]...")
        # 当前在 s2:0，切到 s2:1（使得 s2:0 成为该 Session 的上次窗口 [-]）
        harness.switch_to('s2:1')
        assert harness.get_current_window() == 's2:1'

        harness.trigger_popup()
        # 光标先移动到其他 Session 的窗口（按 K 飞到 s1:0）
        harness.send_keys([b'K'], delay=0.2)
        time.sleep(0.3)
        # 按 Tab 键瞬间吸附回当前会话的唯一 LAST 窗口 [-] (s2:0)
        harness.send_keys([b'\t'], delay=0.2)
        time.sleep(0.3)
        # 按回车确认切换
        harness.send_keys([b'\r'], delay=0.2)
        time.sleep(0.5)
        cur = harness.get_current_window()
        assert cur == 's2:0', f"Test 4 Failed: Expected s2:0, got {cur}"
        print(f"✓ Test 4 Passed! Current window successfully switched to {cur}")

        # -------------------------------------------------------------
        # Test 5: Esc 键安全退出 (不产生任何副作用，保持原窗口)
        # -------------------------------------------------------------
        print("\n[Test 5] Esc Key Abort Safety...")
        assert harness.get_current_window() == 's2:0'
        harness.trigger_popup()
        harness.send_keys([b'\x1b'], delay=0.2) # Esc
        time.sleep(0.4)
        cur = harness.get_current_window()
        assert cur == 's2:0', f"Test 5 Failed: Window changed unexpectedly to {cur}"
        print(f"✓ Test 5 Passed! Window remains {cur}")

        # -------------------------------------------------------------
        # Test 6: Ctrl-x 销毁非当前窗口
        # -------------------------------------------------------------
        print("\n[Test 6] Ctrl-x Kill Window via Real Popup...")
        # 当前在 s2:0，s2 下有 win0 和 win1。我们在弹窗里定位到 s2:1 并按 Ctrl-x (0x18) 销毁它
        harness.trigger_popup()
        # 搜索 2.1 锁定它
        harness.send_keys([b'2', b'.', b'1'], delay=0.15)
        time.sleep(0.3)
        # 发送 Ctrl-x 销毁
        harness.send_keys([b'\x18'], delay=0.3)
        time.sleep(0.4)
        # 按 Esc 退出弹窗
        harness.send_keys([b'\x1b'], delay=0.2)
        time.sleep(0.4)

        # 验证 s2 现在的窗口列表：s2:1 应该已经从真实 tmux 服务端消失
        wins = harness.get_windows('s2')
        assert '1:win1' not in wins, f"Test 6 Failed: Window s2:1 still exists! Current windows: {wins}"
        print(f"✓ Test 6 Passed! Window s2:1 was killed. Remaining: {wins}")

        print("\n" + "=" * 70)
        print("ALL 6 REAL TMUX CLIENT END-TO-END TESTS PASSED!")
        print("=" * 70)

    finally:
        harness.close()

if __name__ == '__main__':
    run_all_e2e_tests()
