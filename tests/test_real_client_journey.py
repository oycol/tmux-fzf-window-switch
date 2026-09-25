"""Isolated real tmux client journeys; never touches the default server."""
import fcntl
import os
import pty
import struct
import subprocess
import tempfile
import termios
import time
import unittest
from scripts.switcher.app import SwitcherApp
from scripts.switcher.tmux import TmuxAdapter


class RealClientJourney(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='switcher-real-')
        self.sock = os.path.join(self.tmp.name, 'socket')
        self.tmux('-f', '/dev/null', 'new-session', '-d', '-s', 'one', '-n', 'A', 'sleep 120')
        self.tmux('new-window', '-d', '-t', 'one:1', '-n', 'oldA', 'sleep 120')
        self.tmux('new-session', '-d', '-s', 'two', '-n', 'B', 'sleep 120')
        self.tmux('new-window', '-d', '-t', 'two:1', '-n', 'oldB', 'sleep 120')
        self.tmux('select-window', '-t', 'one:1')
        self.tmux('select-window', '-t', 'one:0')
        self.tmux('select-window', '-t', 'two:1')
        self.tmux('select-window', '-t', 'two:0')
        self.master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 30, 120, 0, 0))
        env = {**os.environ, 'TERM': 'xterm-256color'}
        env.pop('TMUX', None)
        self.client = subprocess.Popen(['tmux', '-S', self.sock, 'attach-session', '-t', 'one:0'],
                                       stdin=slave, stdout=slave, stderr=slave, env=env)
        os.close(slave)
        self.name = ''
        for _ in range(40):
            p = subprocess.run(['tmux', '-S', self.sock, 'list-clients', '-F', '#{client_name}'],
                               capture_output=True, text=True)
            if p.stdout.strip():
                self.name = p.stdout.strip().splitlines()[0]
                break
            time.sleep(.05)
        self.assertTrue(self.name)
        self.adapter = TmuxAdapter(self.sock, self.name)

    def tmux(self, *args):
        return subprocess.run(['tmux', '-S', self.sock, *args], check=True,
                              capture_output=True, text=True).stdout.strip()

    def tearDown(self):
        self.client.terminate()
        try:
            self.client.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.client.kill()
            self.client.wait(timeout=2)
        os.close(self.master)
        subprocess.run(['tmux', '-S', self.sock, 'kill-server'], capture_output=True)
        self.tmp.cleanup()

    def app(self):
        app = SwitcherApp(self.adapter)
        app.init_state()
        return app

    def test_cross_session_A_B_A_and_client_history(self):
        a_id = self.tmux('display-message', '-p', '-t', 'one:0', '#{window_id}')
        b_id = self.tmux('display-message', '-p', '-t', 'two:0', '#{window_id}')
        app = self.app()
        app.state.move_to(b_id)
        self.assertTrue(app._handle_input(10))
        self.assertEqual(self.adapter.get_source_window_id(), b_id)
        self.assertEqual(self.adapter.get_return_window_id(), a_id)
        app = self.app()
        self.assertEqual(app.state.selected_window_id, a_id)
        self.assertTrue(app._handle_input(10))
        self.assertEqual(self.adapter.get_source_window_id(), a_id)
        self.assertEqual(self.adapter.get_return_window_id(), b_id)
        self.assertEqual(self.app().state.selected_window_id, b_id)

    def test_new_client_on_same_tty_does_not_inherit_return_target(self):
        self.adapter.set_return_window_id(self.adapter.get_source_window_id())
        first_key = self.adapter._return_option()
        original_cmd = self.adapter._cmd
        def replaced_identity(args):
            if args[:3] == ['display-message', '-c', self.name] and args[-1] == '#{client_tty}\t#{client_pid}\t#{client_created}':
                return 0, self.name + '\t999999\t999999\n', ''
            return original_cmd(args)
        self.adapter._cmd = replaced_identity
        self.assertNotEqual(self.adapter._return_option(), first_key)
        self.assertIsNone(self.adapter.get_return_window_id())

    def test_delete_selected_window_and_repeat_guard(self):
        app = self.app()
        target = app.state.selected_window_id
        self.assertTrue(app.state.can_delete_selected())
        self.assertFalse(app._handle_input(24))
        self.assertNotIn(target, self.tmux('list-windows', '-a', '-F', '#{window_id}').splitlines())
        remaining = self.tmux('list-windows', '-a', '-F', '#{window_id}').splitlines()
        self.assertTrue(app.state.delete_blocked)
        self.assertFalse(app._handle_input(24))
        self.assertEqual(remaining, self.tmux('list-windows', '-a', '-F', '#{window_id}').splitlines())
        self.assertEqual(self.adapter.get_source_window_id(), self.tmux('display-message', '-p', '-t', 'one:0', '#{window_id}'))


if __name__ == '__main__':
    unittest.main()
