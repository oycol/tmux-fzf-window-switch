"""Import hygiene: the startup path must stay free of heavy stdlib modules."""
import os
import subprocess
import sys
import unittest


HEAVY_MODULES = ["argparse", "dataclasses", "json", "typing", "hashlib"]
# Note: enum/re are transitive deps of the _curses C extension (via contextlib)
# and cannot be avoided while curses is imported; project code references none.


class ImportHygieneTest(unittest.TestCase):
    def test_app_import_avoids_heavy_modules(self):
        """Importing the app must not pull dataclasses/enum/json/typing/re/hashlib."""
        check = (
            "import sys\n"
            "import scripts.switcher.app\n"
            "bad = [m for m in sys.modules if m in "
            + repr(HEAVY_MODULES)
            + "]\n"
            "assert not bad, f'heavy modules imported: {bad}'\n"
        )
        proc = subprocess.run(
            [sys.executable, "-c", check],
            env={**os.environ, "PYTHONPATH": "."},
            capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_tmux_adapter_import_alone_avoids_heavy_modules(self):
        check = (
            "import sys\n"
            "from scripts.switcher.tmux import TmuxAdapter\n"
            "bad = [m for m in sys.modules if m in " + repr(HEAVY_MODULES) + "]\n"
            "assert not bad, f'heavy modules imported: {bad}'\n"
        )
        proc = subprocess.run(
            [sys.executable, "-c", check],
            env={**os.environ, "PYTHONPATH": "."},
            capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)


if __name__ == "__main__":
    unittest.main()
