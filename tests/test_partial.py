import unittest

from elf_calculator.constructors.elf_baselines import Puzzle, validate
from elf_calculator.optimizers.elf_postprocess import postprocess
from elf_calculator.optimizers.elf_partial import recipes, candidates


class PartialTests(unittest.TestCase):
    def test_equal_length_recipe_exposes_intermediate(self):
        p = Puzzle('tie', [2, 3, 10], [17, 70], 100)
        base = [['+', 2, 2, 3], ['-', 3, 1, 4], ['*', 2, 2, 5],
                ['*', 1, 2, 6], ['-', 5, 6, 7]]
        donor = [['-', 2, 1, 3], ['+', 3, 2, 4], *base[2:]]
        options = candidates(p, base, [recipes(p, donor)])
        self.assertIs(min(options, key=len), base)
        self.assertTrue(any(len(c) == len(base) and
                            len(postprocess(p, c)) < len(postprocess(p, base))
                            for c in options))

    def test_preserves_shared_dependency(self):
        p = Puzzle('shared', [2, 3, 10], [17, 40], 100)
        base = [['+', 2, 2, 3], ['-', 3, 1, 4], ['+', 3, 3, 5]]
        donor = [['-', 2, 1, 3], ['+', 3, 2, 4], *base[:1], base[-1]]
        options = candidates(p, base, [recipes(p, donor)])
        self.assertEqual([validate(p, c)['steps'] for c in options], [3, 4])
