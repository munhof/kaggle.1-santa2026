import csv
import io
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch
import elf_calculator.constructors.elf_baselines as elf_baselines
import random
import unittest
from elf_calculator.constructors.elf_baselines import Puzzle, ConstructionError, incremental, rings, validate, main

class BaselineTests(unittest.TestCase):
    def test_official_example(self):
        p = Puzzle('example_0001', [3], [1, 2, 5, 8], 9)
        for algorithm in (incremental, rings):
            self.assertTrue(validate(p, algorithm(p))['valid'])

    def test_initial_targets(self):
        p = Puzzle('synthetic', [1, 2, 3], [1, 2, 3], 10)
        self.assertEqual(incremental(p), [])
        self.assertEqual(rings(p), [])

    def test_many_small_random(self):
        rng = random.Random(42)
        for k in range(200):
            limit = rng.randint(10, 400)
            starts = rng.sample(range(1, limit+1), rng.randint(1, 4))
            targets = sorted(rng.sample(range(1, limit+1), rng.randint(1, 8)))
            p = Puzzle(str(k), starts, targets, limit)
            for algorithm in (incremental, rings):
                self.assertTrue(validate(p, algorithm(p))['valid'])

    def test_fail_gracefully_on_step_budget(self):
        p = Puzzle('synthetic', [1], [8000], 8000)
        with self.assertRaises(ConstructionError): incremental(p)

class BisectionTests(unittest.TestCase):
    def test_integer_midpoints_toward_target(self):
        midpoint = elf_baselines._midpoint_toward
        self.assertEqual([midpoint(a, b, 73) for a, b in
                          [(60, 80), (70, 80), (70, 75), (72, 75), (72, 74)]],
                         [70, 75, 72, 74, 73])

    def test_program_constructs_grid_points(self):
        p = Puzzle('grid', [20], [73], 80)
        program = elf_baselines.bisection(p)
        self.assertTrue(validate(p, program)['valid'])
        memory = [20] + [None] * 47
        values = []
        for op, i, j, d in program:
            a, b = memory[i], memory[j]
            memory[d] = {'+': lambda: a+b, '-': lambda: a-b,
                         '*': lambda: a*b, '/': lambda: a//b}[op]()
            values.append(memory[d])
        cursor = 0
        for point in [70, 75, 72, 74]:
            cursor = values.index(point, cursor) + 1
        self.assertIn(73, values)  # An arithmetic intermediate already covers it.

    def test_boundaries_reuse_and_register_pressure(self):
        cases = [
            Puzzle('covered', [1], [1], 1),
            Puzzle('low', [20], [1, 2, 19], 20),
            Puzzle('upper', [20], [73, 74, 75, 79, 81], 81),
            Puzzle('full', list(range(2, 50)), [73, 99], 100),
            Puzzle('many', [20], list(range(1, 150)), 150),
        ]
        rng = random.Random(73)
        for i in range(100):
            limit = rng.randint(2, 500)
            cases.append(Puzzle(str(i), [rng.randint(1, limit)],
                                rng.sample(range(1, limit+1), min(8, limit)), limit))
        for p in cases:
            with self.subTest(p=p.id):
                self.assertTrue(validate(p, elf_baselines.bisection(p))['valid'])

class RunnerTests(unittest.TestCase):
    def run_batch(self, rows, algorithm=None):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'input.csv'
            output = Path(directory) / 'results.csv'
            with source.open('w', newline='') as fp:
                writer = csv.DictWriter(fp, fieldnames=['id', 'starting_values', 'targets', 'value_limit'])
                writer.writeheader()
                writer.writerows(rows)
            argv = ['elf_baselines.py', '--algorithm', 'rings', '--input', str(source), '--output', str(output)]
            with patch('sys.argv', argv), redirect_stdout(io.StringIO()):
                if algorithm is None:
                    main()
                else:
                    with patch('elf_calculator.constructors.elf_baselines.rings', side_effect=algorithm):
                        main()
            with output.open() as fp:
                results = list(csv.DictReader(fp))
            with output.with_name('results_failures.csv').open() as fp:
                failures = list(csv.DictReader(fp))
            return results, failures

    def test_bad_row_does_not_stop_later_solution(self):
        rows = [
            dict(id='bad', starting_values='invalid json', targets='[2]', value_limit=10),
            dict(id='good', starting_values='[1]', targets='[2]', value_limit=10),
        ]
        results, failures = self.run_batch(rows)
        self.assertEqual([r['id'] for r in results], ['good'])
        self.assertEqual([r['id'] for r in failures], ['bad'])
        self.assertTrue(failures[0]['reason'])

    def test_assertion_does_not_stop_later_solution(self):
        rows = [dict(id=name, starting_values='[1]', targets='[1]', value_limit=10)
                for name in ('bad', 'good')]
        results, failures = self.run_batch(rows, [AssertionError(), []])
        self.assertEqual([r['id'] for r in results], ['good'])
        self.assertEqual([r['id'] for r in failures], ['bad'])
        self.assertIn('AssertionError', failures[0]['reason'])

if __name__ == '__main__':
    unittest.main()
