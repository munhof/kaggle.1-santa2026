import unittest
from elf_calculator.constructors.elf_baselines import Puzzle, validate
from scripts.compare_offsets import optimize

class OffsetTests(unittest.TestCase):
    def test_two_offsets_replace_five_steps(self):
        p = Puzzle('pair',[13,256,17,21014,7,128,1106,11,2],[24325,24460],30000)
        base = [['*',0,1,9],['-',9,2,10],['+',10,3,11],['+',4,5,12],['+',11,12,13]]
        code,moves = optimize(p,base)
        self.assertLessEqual(validate(p,code)['steps'],4)
        self.assertTrue(moves)
