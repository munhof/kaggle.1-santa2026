import unittest
from elf_calculator.constructors.elf_baselines import Puzzle, validate
from scripts.compare_shared_greedy import search

class SharedGreedyTests(unittest.TestCase):
    def test_new_helper_serves_three_targets(self):
        p = Puzzle('three', [1,3,7,10,23], [69,71,210], 300)
        base = [['+',4,4,5],['+',5,4,5],['+',3,0,6],['*',6,2,6],
                ['+',1,1,7],['-',6,7,6],['*',3,1,7],['*',7,2,7]]
        code, moves = search(p,base,'coverage')
        self.assertLess(validate(p,code)['steps'],len(base))
        self.assertGreaterEqual(moves[0][0],3)
