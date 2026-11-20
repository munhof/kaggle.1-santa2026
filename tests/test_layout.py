"""Public entry points must work when invoked from outside the repository."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class LayoutTests(unittest.TestCase):
    def test_cli_and_validator(self):
        with tempfile.TemporaryDirectory() as cwd:
            for path, args in [
                ('elf_baselines.py', ['--algorithm', 'multirings-reuse', '--a4', '--demo']),
                ('scripts/validate_submission.py', ['--help']),
                ('validate_submission.py', ['--help']),
            ]:
                with self.subTest(path=path):
                    result = subprocess.run([sys.executable, ROOT/path, *args], cwd=cwd,
                                            capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stderr)
