import unittest

from elf_calculator.constructors.elf_baselines import Puzzle, validate
from elf_calculator.optimizers.elf_dag import optimize_dag


class DagTests(unittest.TestCase):
    def test_share_overwritten_value_between_targets(self):
        puzzle = Puzzle('shared', [3, 10], [97, 107], 110)
        code = [['*', 1, 1, 2], ['-', 2, 0, 2], ['*', 1, 1, 3],
                ['+', 3, 1, 3], ['-', 3, 0, 3]]
        result = optimize_dag(puzzle, code)
        self.assertEqual(validate(puzzle, result)['steps'], 4)
