import copy
import random
import unittest
from elf_calculator.constructors.elf_baselines import Puzzle, validate
from elf_calculator.optimizers.elf_postprocess import postprocess


class PostprocessTests(unittest.TestCase):
    def check(self, p, program):
        original = copy.deepcopy(program)
        result = postprocess(p, program)
        self.assertEqual(program, original)
        self.assertTrue(validate(p, result)['valid'])
        self.assertLessEqual(len(result), len(program))
        return result

    def test_sum_chain_with_temporary_registers(self):
        p = Puzzle('sums', [10, 3, 4], [22], 100)
        program = [['+', 0, 1, 3], ['+', 3, 1, 4],
                   ['+', 4, 1, 5], ['+', 5, 1, 6]]
        # 3*4 then 10+12 needs two instructions, not a free constant.
        result = self.check(p, program)
        self.assertLess(len(result), 4)

    def test_multiplication_chain(self):
        p = Puzzle('products', [2, 3, 9], [18], 100)
        self.assertEqual(len(self.check(p, [['*',0,1,3], ['*',3,1,4]])), 1)

    def test_intermediate_target_and_overwrite(self):
        p = Puzzle('targets', [2, 3, 9], [6, 18], 100)
        result = self.check(p, [['*',0,1,0], ['*',0,1,0]])
        self.assertEqual(len(result), 2)

    def test_live_intermediate_preserved(self):
        p = Puzzle('live', [2, 3, 9], [18, 15], 100)
        self.check(p, [['*',0,1,3], ['*',3,1,4], ['+',3,2,5]])

    def test_dead_instructions_and_initial_coverage(self):
        p = Puzzle('dead', [2,3], [2], 100)
        self.assertEqual(self.check(p, [['+',0,1,2]]), [])

class GeneratedProgramTests(unittest.TestCase):
    def test_seeded_generated_programs(self):
        from elf_calculator.constructors.elf_baselines import incremental, rings
        from elf_calculator.constructors.elf_multirings_reuse import multirings_reuse
        rng = random.Random(2026)
        for k in range(100):
            limit = rng.randint(10, 100)
            p = Puzzle(str(k), rng.sample(range(1, limit+1), 3),
                       rng.sample(range(1, limit+1), 5), limit)
            for algorithm in (incremental, rings, multirings_reuse):
                with self.subTest(case=k, algorithm=algorithm.__name__):
                    original = algorithm(p)
                    result = postprocess(p, original)
                    self.assertTrue(validate(p, result)['valid'])
                    self.assertLessEqual(len(result), len(original))
