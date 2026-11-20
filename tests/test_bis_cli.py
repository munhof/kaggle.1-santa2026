"""CLI integration for the two independent A3 bis variants."""
import subprocess
import sys
import unittest
from pathlib import Path


class BisCliTests(unittest.TestCase):
    def test_both_variants_demo(self):
        for algorithm in ('multirings', 'bisection-reuse', 'multirings-reuse'):
            with self.subTest(algorithm=algorithm):
                run = subprocess.run(
                    [sys.executable, str(Path(__file__).resolve().parents[1] / 'elf_baselines.py'),
                     '--algorithm', algorithm, '--demo'],
                    capture_output=True, text=True)
                self.assertEqual(run.returncode, 0, run.stderr)
                self.assertIn('1 solved, 0 failed, 1 total', run.stdout)


if __name__ == '__main__':
    unittest.main()
