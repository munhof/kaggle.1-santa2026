import random
import unittest

from elf_calculator.constructors.elf_baselines import Builder, Puzzle, validate, bisection
from elf_calculator.constructors.elf_multirings import multirings, _trial


class MultiRingsTests(unittest.TestCase):
    def test_nonmaximum_base_can_save_instructions(self):
        p = Puzzle('base-choice', [3, 20], [9], 100)
        program = multirings(p)
        self.assertTrue(validate(p, program)['valid'])
        self.assertLess(len(program), len(bisection(p)))
        self.assertEqual(program, multirings(p))

    def test_trials_do_not_leak_state(self):
        p = Puzzle('isolated', [3, 20], [9], 100)
        builder = Builder(p)
        original_memory = builder.memory.copy()
        candidates = [_trial(builder, 9, base) for base in (3, 20)]
        self.assertEqual(builder.memory, original_memory)
        self.assertEqual(builder.program, [])
        self.assertEqual(builder.covered, set())
        self.assertEqual(len(multirings(p)), min(len(c.program) for c in candidates))

    def test_boundaries_and_full_registers(self):
        cases = [
            Puzzle('one', [1], [1], 1),
            Puzzle('small', [20], [1, 2, 19], 20),
            Puzzle('clipped', [7, 20], [73, 74, 81], 81),
            Puzzle('full', list(range(2, 50)), [73, 99], 100),
            Puzzle('many', [3, 20], list(range(1, 150)), 150),
        ]
        for p in cases:
            with self.subTest(p=p.id):
                self.assertTrue(validate(p, multirings(p))['valid'])

    def test_seeded_random(self):
        rng = random.Random(141)
        for index in range(100):
            limit = rng.randint(3, 400)
            p = Puzzle(str(index),
                       rng.sample(range(1, limit + 1), min(4, limit)),
                       rng.sample(range(1, limit + 1), min(8, limit)), limit)
            with self.subTest(p=p.id):
                self.assertTrue(validate(p, multirings(p))['valid'])


if __name__ == '__main__':
    unittest.main()
