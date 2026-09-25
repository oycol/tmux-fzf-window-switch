import unittest
import os
import subprocess
import time
import pty
import fcntl
import struct
import termios
import tempfile

class TestTmuxE2E(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix='tmux-switcher-e2e-')
        self.sock = os.path.join(self._tmp.name, 'socket')
        # Each case owns a unique server; never touch another test's socket.
        # s1: win0 (0), win1 (1)
        # s2: win0 (0), win1 (1)
        subprocess.run(["tmux", "-S", self.sock, "-f", "/dev/null", "new-session", "-d", "-s", "s1", "-x", "120", "-y", "35", "-n", "win0", "sleep 300"], check=True)
        subprocess.run(["tmux", "-S", self.sock, "new-window", "-t", "s1:1", "-n", "win1", "sleep 300"], check=True)
        subprocess.run(["tmux", "-S", self.sock, "new-session", "-d", "-s", "s2", "-x", "120", "-y", "35", "-n", "win0", "sleep 300"], check=True)
        subprocess.run(["tmux", "-S", self.sock, "new-window", "-t", "s2:1", "-n", "win1", "sleep 300"], check=True)

    def tearDown(self):
        subprocess.run(["tmux", "-S", self.sock, "kill-server"], stderr=subprocess.DEVNULL)
        self._tmp.cleanup()

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
            # Wait for the one client attached to this isolated server.
            cname = ""
            for _ in range(20):
                time.sleep(0.1)
                res = subprocess.run(["tmux", "-S", self.sock, "list-clients", "-F", "#{client_name}"], capture_output=True, text=True)
                if res.stdout.strip():
                    cname = res.stdout.strip().splitlines()[0]
                    break
            self.assertTrue(cname)

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

            # Verify explicit client switched and the next popup will return to s1:0.
            res = subprocess.run(["tmux", "-S", self.sock, "display-message", "-c", cname, "-p", "#{session_name}:#{window_index}"], capture_output=True, text=True)
            self.assertEqual(res.stdout.strip(), "s2:1")
            from scripts.switcher.tmux import TmuxAdapter
            adapter = TmuxAdapter(self.sock, cname)
            source_id = subprocess.run(["tmux", "-S", self.sock, "display-message", "-p", "-t", "s1:0", "#{window_id}"], capture_output=True, text=True).stdout.strip()
            self.assertEqual(adapter.get_return_window_id(), source_id)
            os.write(master, b'\x02w')
            time.sleep(0.8)
            os.write(master, b'\r')
            time.sleep(0.8)
            self.assertEqual(adapter.get_source_window_id(), source_id)
            target_id = subprocess.run(["tmux", "-S", self.sock, "display-message", "-p", "-t", "s2:1", "#{window_id}"], capture_output=True, text=True).stdout.strip()
            self.assertEqual(adapter.get_return_window_id(), target_id)
        finally:
            client_p.kill()
            client_p.wait()
            os.close(master)

    def test_popup_ctrl_x_deletes_only_selected_once(self):
        from scripts.switcher.tmux import TmuxAdapter
        repo_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        subprocess.run(["tmux", "-S", self.sock, "bind-key", "w", "run-shell", "-t", "#{session_id}",
                        os.path.join(repo_dir, "scripts", "switch.sh")], check=True)
        master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 35, 120, 0, 0))
        env = {**os.environ, "TERM": "xterm-256color", "TMUX": f"{self.sock},1000,0"}
        client = subprocess.Popen(["tmux", "-S", self.sock, "attach-session", "-t", "s1:0"],
                                  stdin=slave, stdout=slave, stderr=slave, env=env)
        os.close(slave)
        try:
            cname = ''
            for _ in range(30):
                res = subprocess.run(["tmux", "-S", self.sock, "list-clients", "-F", "#{client_name}"], capture_output=True, text=True)
                if res.stdout.strip():
                    cname = res.stdout.strip().splitlines()[0]
                    break
                time.sleep(.1)
            self.assertTrue(cname)
            target = subprocess.run(["tmux", "-S", self.sock, "display-message", "-p", "-t", "s1:1", "#{window_id}"], capture_output=True, text=True).stdout.strip()
            adapter = TmuxAdapter(self.sock, cname)
            os.write(master, b'\x02w')
            time.sleep(.8)
            os.write(master, b'\x18\x18')
            time.sleep(.5)
            remaining = subprocess.run(["tmux", "-S", self.sock, "list-windows", "-a", "-F", "#{window_id}"], capture_output=True, text=True).stdout.splitlines()
            self.assertNotIn(target, remaining)
            self.assertEqual(len(remaining), 3)
            self.assertEqual(adapter.get_source_window_id(), subprocess.run(["tmux", "-S", self.sock, "display-message", "-p", "-t", "s1:0", "#{window_id}"], capture_output=True, text=True).stdout.strip())
            os.write(master, b'q')
        finally:
            client.terminate()
            try:
                client.wait(timeout=2)
            except subprocess.TimeoutExpired:
                client.kill()
                client.wait(timeout=2)
            os.close(master)

    def test_production_entry_run(self):
        # Verify app starts and exits cleanly on 'q'
        master, slave = pty.openpty()
        winsize = struct.pack('HHHH', 35, 120, 0, 0)
        fcntl.ioctl(slave, termios.TIOCSWINSZ, winsize)

        # Start client attached to s1:0, then drive the app in a separate PTY.
        client_master, client_slave = pty.openpty()
        fcntl.ioctl(client_slave, termios.TIOCSWINSZ, winsize)
        client = subprocess.Popen(["tmux", "-S", self.sock, "attach-session", "-t", "s1:0"],
                                  stdin=client_slave, stdout=client_slave, stderr=client_slave,
                                  env={**os.environ, "TERM": "xterm-256color"})
        os.close(client_slave)
        cname = ""
        for _ in range(30):
            res = subprocess.run(["tmux", "-S", self.sock, "list-clients", "-F", "#{client_name}"], capture_output=True, text=True)
            if res.stdout.strip():
                cname = res.stdout.strip().splitlines()[0]
                break
            time.sleep(.1)
        self.assertTrue(cname)
        env = {
            **os.environ,
            "TERM": "xterm-256color",
            "TMUX_SOCKET": self.sock,
            "TMUX": f"{self.sock},1000,0",
            "TMUX_SWITCH_CLIENT": cname
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
            client.terminate()
            client.wait(timeout=2)
            os.close(client_master)

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

if __name__ == '__main__':
    unittest.main()
