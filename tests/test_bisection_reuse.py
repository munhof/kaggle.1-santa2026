import random
import unittest

from elf_calculator.constructors.elf_baselines import Puzzle, bisection, validate


class BisectionReuseTests(unittest.TestCase):
    def solve(self, puzzle):
        from elf_calculator.constructors.elf_bisection_reuse import bisection_reuse
        program = bisection_reuse(puzzle)
        self.assertTrue(validate(puzzle, program)['valid'])
        return program

    def test_adjacent_ring_endpoints_reuse(self):
        p = Puzzle('reuse', [20], [73, 93, 113], 120)
        self.assertLess(len(self.solve(p)), len(bisection(p)))

    def test_clipped_boundaries_and_full_registers(self):
        for p in (Puzzle('one', [1], [1], 1),
                  Puzzle('clipped', [20], [1, 19, 73, 81], 81),
                  Puzzle('full', list(range(2, 50)), [73, 99], 100)):
            with self.subTest(p=p.id):
                self.solve(p)

    def test_many_targets_and_deterministic_random(self):
        self.solve(Puzzle('many', [20], list(range(1, 150)), 150))
        rng = random.Random(348)
        for i in range(100):
            limit = rng.randint(2, 1000)
            p = Puzzle(str(i), rng.sample(range(1, limit+1), min(4, limit)),
                       rng.sample(range(1, limit+1), min(10, limit)), limit)
            with self.subTest(p=p.id):
                self.solve(p)


if __name__ == '__main__':
    unittest.main()
