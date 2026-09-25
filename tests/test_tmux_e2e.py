import unittest
import os
import subprocess
import time
import pty
import fcntl
import struct
import termios

class TestTmuxE2E(unittest.TestCase):
    sock = "/tmp/tmux_test_e2e_isolated.sock"

    def setUp(self):
        # Ensure cleanup of any old server on this isolated socket
        subprocess.run(["tmux", "-S", self.sock, "kill-server"], stderr=subprocess.DEVNULL)
        time.sleep(0.2)

        # Create isolated tmux server with sessions:
        # s1: win0 (0), win1 (1)
        # s2: win0 (0), win1 (1)
        subprocess.run(["tmux", "-S", self.sock, "-f", "/dev/null", "new-session", "-d", "-s", "s1", "-x", "120", "-y", "35", "-n", "win0", "sleep 300"], check=True)
        subprocess.run(["tmux", "-S", self.sock, "new-window", "-t", "s1:1", "-n", "win1", "sleep 300"], check=True)
        subprocess.run(["tmux", "-S", self.sock, "new-session", "-d", "-s", "s2", "-x", "120", "-y", "35", "-n", "win0", "sleep 300"], check=True)
        subprocess.run(["tmux", "-S", self.sock, "new-window", "-t", "s2:1", "-n", "win1", "sleep 300"], check=True)

    def tearDown(self):
        subprocess.run(["tmux", "-S", self.sock, "kill-server"], stderr=subprocess.DEVNULL)
        time.sleep(0.2)

    def test_switch_sh_tpm_entry_e2e(self):
        # Register prefix+w binding to switch.sh and trigger via prefix+w in attached client
        repo_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        switch_sh = os.path.join(repo_dir, "scripts", "switch.sh")
        subprocess.run([
            "tmux", "-S", self.sock, "bind-key", "w",
            "run-shell", "-t", "#{session_id}", switch_sh
        ], check=True)

        master, slave = pty.openpty()
        winsize = struct.pack('HHHH', 35, 120, 0, 0)
        fcntl.ioctl(slave, termios.TIOCSWINSZ, winsize)

        env = {
            **os.environ,
            "TERM": "xterm-256color",
            "TMUX": f"{self.sock},1000,0",
            "PYTHONPATH": repo_dir
        }

        # Start client attached to s1:0
        client_p = subprocess.Popen(
            ["tmux", "-S", self.sock, "attach-session", "-t", "s1:0"],
            stdin=slave,
            stdout=slave,
            stderr=slave,
            env=env
        )
        os.close(slave)

        try:
            # Wait for client attach
            for _ in range(20):
                time.sleep(0.1)
                res = subprocess.run(["tmux", "-S", self.sock, "list-clients", "-F", "#{client_name}"], capture_output=True, text=True)
                if res.stdout.strip():
                    break

            # Send prefix C-b then w to trigger popup
            os.write(master, b'\x02w')
            time.sleep(0.8)

            # Inside popup, locate 2.1 and press Enter
            os.write(master, b'2')
            time.sleep(0.1)
            os.write(master, b'.')
            time.sleep(0.1)
            os.write(master, b'1')
            time.sleep(0.1)
            os.write(master, b'\r')
            time.sleep(0.8)

            # Verify client switched to s2:1
            res = subprocess.run(["tmux", "-S", self.sock, "display-message", "-p", "#{session_name}:#{window_index}"], capture_output=True, text=True)
            self.assertEqual(res.stdout.strip(), "s2:1")
        finally:
            client_p.kill()
            client_p.wait()
            os.close(master)

    def test_production_entry_run(self):
        # Verify app starts and exits cleanly on 'q'
        master, slave = pty.openpty()
        winsize = struct.pack('HHHH', 35, 120, 0, 0)
        fcntl.ioctl(slave, termios.TIOCSWINSZ, winsize)

        env = {
            **os.environ,
            "TERM": "xterm-256color",
            "TMUX_SOCKET": self.sock,
            "TMUX": f"{self.sock},1000,0"
        }

        proc = subprocess.Popen(
            ["python3", "-m", "scripts.switcher.app", "--socket", self.sock],
            stdin=slave,
            stdout=slave,
            stderr=slave,
            env=env,
            close_fds=True
        )
        os.close(slave)

        try:
            time.sleep(0.5)
            os.write(master, b'q')
            proc.wait(timeout=3)
            self.assertEqual(proc.returncode, 0)
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=1)
                except Exception:
                    pass
            os.close(master)

    def test_locate_switch_e2e(self):
        # In isolated server, attach client to s1:0, launch app, locate 2.1, press Enter -> client switches to s2:1
        master, slave = pty.openpty()
        winsize = struct.pack('HHHH', 35, 120, 0, 0)
        fcntl.ioctl(slave, termios.TIOCSWINSZ, winsize)

        env = {
            **os.environ,
            "TERM": "xterm-256color",
            "TMUX": f"{self.sock},1000,0"
        }

        # Start client attached to s1:0
        client_p = subprocess.Popen(
            ["tmux", "-S", self.sock, "attach-session", "-t", "s1:0"],
            stdin=slave,
            stdout=slave,
            stderr=slave,
            env=env
        )
        os.close(slave)

        try:
            # Wait for client attach
            cname = ""
            for _ in range(20):
                time.sleep(0.1)
                res = subprocess.run(["tmux", "-S", self.sock, "list-clients", "-F", "#{client_name}"], capture_output=True, text=True)
                lines = res.stdout.strip().splitlines()
                if lines:
                    cname = lines[0]
                    break
            self.assertTrue(cname, "Client failed to attach in time")

            # In another PTY, run app for that client
            app_m, app_s = pty.openpty()
            fcntl.ioctl(app_s, termios.TIOCSWINSZ, winsize)

            app_proc = subprocess.Popen(
                ["python3", "-m", "scripts.switcher.app", "--socket", self.sock, "--client", cname],
                stdin=app_s,
                stdout=app_s,
                stderr=app_s,
                env=env
            )
            os.close(app_s)

            try:
                time.sleep(0.5)
                # Type '2', '.', '1', '\r'
                os.write(app_m, b'2')
                time.sleep(0.1)
                os.write(app_m, b'.')
                time.sleep(0.1)
                os.write(app_m, b'1')
                time.sleep(0.1)
                os.write(app_m, b'\r')
                app_proc.wait(timeout=3)
                self.assertEqual(app_proc.returncode, 0)

                # Verify client is now viewing s2:1!
                time.sleep(0.3)
                cur_res = subprocess.run(["tmux", "-S", self.sock, "display-message", "-c", cname, "-p", "#{session_name}:#{window_index}"], capture_output=True, text=True)
                self.assertEqual(cur_res.stdout.strip(), "s2:1")
            finally:
                os.close(app_m)
                if app_proc.poll() is None:
                    app_proc.terminate()
                    app_proc.wait(timeout=1)
        finally:
            client_p.terminate()
            try:
                client_p.wait(timeout=1)
            except Exception:
                pass
            os.close(master)

    def test_kill_window_ctrl_x_e2e(self):
        # Target window to kill: s2:1
        # Create an extra window s2:2 so killing 1 leaves s2 alive
        subprocess.run(["tmux", "-S", self.sock, "new-window", "-t", "s2:2", "-n", "win2", "sleep 300"], check=True)

        master, slave = pty.openpty()
        winsize = struct.pack('HHHH', 35, 120, 0, 0)
        fcntl.ioctl(slave, termios.TIOCSWINSZ, winsize)

        env = {
            **os.environ,
            "TERM": "xterm-256color",
            "TMUX": f"{self.sock},1000,0"
        }

        # Start app with client on s1:0
        app_proc = subprocess.Popen(
            ["python3", "-m", "scripts.switcher.app", "--socket", self.sock],
            stdin=slave,
            stdout=slave,
            stderr=slave,
            env=env
        )
        os.close(slave)

        try:
            time.sleep(0.5)
            # Navigate to an eligible window: j
            os.write(master, b'j')
            time.sleep(0.1)
            # Send Ctrl-x (0x18)
            os.write(master, b'\x18')
            time.sleep(0.2)
            # Send 'q' to exit
            os.write(master, b'q')
            app_proc.wait(timeout=3)
            self.assertEqual(app_proc.returncode, 0)
        finally:
            if app_proc.poll() is None:
                app_proc.terminate()
                try:
                    app_proc.wait(timeout=1)
                except Exception:
                    pass
            os.close(master)

if __name__ == '__main__':
    unittest.main()
