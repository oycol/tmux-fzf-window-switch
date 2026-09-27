"""The popup must be compact without touching a running tmux server."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'switch.sh'


class PopupSizing(unittest.TestCase):
    def popup_height(self, client_width, client_height, window_count, session_count,
                     expect_notice=False):
        with tempfile.TemporaryDirectory(prefix='popup-size-') as directory:
            tmux = Path(directory) / 'tmux'
            tmux.write_text('''#!/usr/bin/env python3
import os, sys
cmd = sys.argv[1]
if cmd == 'display-message':
    expression = sys.argv[-1]
    if expression == '#{client_name}': print('/dev/pts/fake')
    elif expression == '#{client_width}': print(os.environ['TEST_W'])
    elif expression == '#{client_height}': print(os.environ['TEST_H'])
    elif os.environ.get('TEST_LOG'):
        with open(os.environ['TEST_LOG'], 'a') as f:
            f.write(' '.join(sys.argv[1:]) + '\\n')
elif cmd == 'list-windows':
    print('\\n'.join('window' for _ in range(int(os.environ['TEST_WINDOWS']))))
elif cmd == 'list-sessions':
    print('\\n'.join('session' for _ in range(int(os.environ['TEST_SESSIONS']))))
elif cmd == 'display-popup':
    print(sys.argv[sys.argv.index('-h') + 1])
else:
    if os.environ.get('TEST_LOG'):
        with open(os.environ['TEST_LOG'], 'a') as f:
            f.write(cmd + ' ' + ' '.join(sys.argv[2:]) + '\\n')
''')
            tmux.chmod(0o755)
            env = {**os.environ, 'PATH': directory + os.pathsep + os.environ['PATH'],
                   'TMUX': directory + '/sock,123,0', 'TEST_W': str(client_width),
                   'TEST_H': str(client_height), 'TEST_WINDOWS': str(window_count),
                   'TEST_SESSIONS': str(session_count), 'TEST_LOG': directory + '/messages'}
            result = subprocess.run(['bash', str(SCRIPT)], env=env, capture_output=True,
                                    text=True, check=True)
            if expect_notice:
                log = Path(env['TEST_LOG'])
                self.assertTrue(log.is_file() and log.read_text().strip(),
                                'Small-terminal notice must reach the tmux client')
                self.assertIn('终端空间不足', log.read_text())
            return int(result.stdout.strip()) if result.stdout.strip() else -1

    def test_small_collection_does_not_create_tall_empty_popup(self):
        self.assertLessEqual(self.popup_height(140, 40, 4, 2), 17)

    def test_popup_never_exceeds_small_client(self):
        self.assertLessEqual(self.popup_height(80, 12, 2, 1), 10)

    def test_tiny_client_does_not_launch_unusable_popup(self):
        for height in (8, 9):
            self.assertEqual(self.popup_height(120, height, 4, 2, expect_notice=True), -1)
        self.assertGreaterEqual(self.popup_height(120, 10, 4, 2), 8)
        self.assertGreaterEqual(self.popup_height(120, 12, 4, 2), 8)

    def test_tiny_width_does_not_launch_unusable_popup(self):
        self.assertEqual(self.popup_height(20, 20, 4, 2, expect_notice=True), -1)
        self.assertGreaterEqual(self.popup_height(26, 20, 4, 2), 8)

    def test_many_windows_keep_room_to_browse(self):
        self.assertGreaterEqual(self.popup_height(140, 40, 25, 4), 25)


if __name__ == '__main__':
    unittest.main()
