import importlib.util
import unittest

from scripts.public_cp import improve
from scripts.tail_cross import Puzzle, validate


@unittest.skipUnless(importlib.util.find_spec('ortools'), 'requires OR-Tools')
class PublicCrossTests(unittest.TestCase):
    def test_donors_supply_complementary_recipes(self):
        puzzle = Puzzle('pair', [2], [16, 27], 50)
        # Each donor wastes a step in a different branch.
        shared = [['/',0,0,1], ['+',0,1,2], ['*',2,2,3]]
        first = shared + [['+',3,3,4], ['+',4,3,5], ['*',0,0,6], ['*',6,6,7]]
        other = shared + [['*',3,2,4], ['*',0,0,5], ['+',5,5,6], ['+',6,6,7]]
        code, stats = improve(puzzle, first, other, 4)
        self.assertLessEqual(validate(puzzle, code)['steps'], 6)
        self.assertLessEqual(stats['cp'], 6)
        self.assertEqual(stats['final'], len(code))
