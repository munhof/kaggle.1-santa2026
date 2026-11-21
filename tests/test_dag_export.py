import unittest

from scripts.compare_dag import compare, Puzzle, validate


class ExportTests(unittest.TestCase):
    def test_export_matches_shortest_reported_route(self):
        puzzle = Puzzle('p', [3, 10], [97, 107], 110)
        def constructor(p):
            return [['*', 1, 1, 2], ['-', 2, 0, 2], ['*', 1, 1, 3],
                    ['+', 3, 1, 3], ['-', 3, 0, 3]]
        rows, program = compare(puzzle, constructor, export=True)
        self.assertEqual(validate(puzzle, program)['steps'],
                         min(min(row[5:7]) for row in rows))
