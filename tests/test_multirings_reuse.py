import random
import unittest
from elf_calculator.constructors.elf_baselines import Builder, Puzzle, validate
from elf_calculator.constructors.elf_multirings_reuse import multirings_reuse, _trial


class MultiReuseTests(unittest.TestCase):
    def test_valid_deterministic_boundaries_and_full_registers(self):
        cases = [Puzzle('covered', [1], [1], 1),
                 Puzzle('full', list(range(2, 50)), [73, 99], 100),
                 Puzzle('edges', [3, 20], [1, 19, 73, 81], 81)]
        rng = random.Random(314)
        for i in range(100):
            limit = rng.randint(5, 500)
            cases.append(Puzzle(str(i), rng.sample(range(1, limit+1), 3),
                                rng.sample(range(1, limit+1), 5), limit))
        for p in cases:
            with self.subTest(id=p.id):
                program = multirings_reuse(p)
                self.assertTrue(validate(p, program)['valid'])
                self.assertEqual(program, multirings_reuse(p))

    def test_trials_isolated_and_select_cheapest(self):
        p = Puzzle('trial', [7, 20], [73], 100)
        state = Builder(p)
        original = (state.memory.copy(), state.program.copy(), state.covered.copy())
        trials = [_trial(state, 73, base) for base in [7, 20]]
        self.assertEqual((state.memory, state.program, state.covered), original)
        program = multirings_reuse(p)
        self.assertEqual(len(program), min(len(t.program) for t in trials))
        self.assertTrue(validate(p, program)['valid'])

    def test_reuses_adjacent_endpoints(self):
        p = Puzzle('reuse', [20], [73, 93, 113], 140)
        from elf_calculator.constructors.elf_multirings import multirings
        self.assertLess(len(multirings_reuse(p)), len(multirings(p)))


if __name__ == '__main__':
    unittest.main()
