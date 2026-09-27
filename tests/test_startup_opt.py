"""Tests for fast startup optimizations and lightweight argument parsing."""
import os
import sys
import unittest
from scripts.switcher.app import parse_args, SwitcherApp


class FastArgParsingTest(unittest.TestCase):
    def test_parse_args_all_fields(self):
        args = parse_args(["--socket", "/tmp/s", "--client", "/dev/pts/1", "--popup-size", "120x40"])
        self.assertEqual(args.socket, "/tmp/s")
        self.assertEqual(args.client, "/dev/pts/1")
        self.assertEqual(args.popup_size, (120, 40))

    def test_parse_args_defaults(self):
        args = parse_args(["--client", "client1"])
        self.assertIsNone(args.socket)
        self.assertEqual(args.client, "client1")
        self.assertIsNone(args.popup_size)

    def test_parse_args_invalid_popup_size(self):
        with self.assertRaises(ValueError):
            parse_args(["--client", "client1", "--popup-size", "bad_format"])

    def test_no_argparse_imported(self):
        """Ensure argparse is not imported when loading app or running switcher."""
        import subprocess
        proc = subprocess.run([
            sys.executable, "-c",
            "import scripts.switcher.app\n"
            "import sys\n"
            "assert 'argparse' not in sys.modules, 'argparse was imported'\n"
        ], env={**os.environ, "PYTHONPATH": "."}, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, f"argparse was imported: {proc.stderr}")


if __name__ == "__main__":
    unittest.main()
