import unittest
from elf_calculator.constructors.elf_baselines import Puzzle, validate
from elf_calculator.optimizers.elf_nested import nested_windows

class NestedTests(unittest.TestCase):
    def test_share_between_children(self):
        p = Puzzle('shared',[1,3,10],[97,99],100)
        code = [['*',2,2,3],['-',3,1,4],['*',2,2,5],['-',5,0,4]]
        out = nested_windows(p,code,width=2,levels=1)
        self.assertEqual(len(out),3)
        validate(p,out)

    def test_dependency_and_targets(self):
        p = Puzzle('live',[1,3,10],[97,99,100],101)
        code = [['*',2,2,3],['-',3,1,4],['*',2,2,5],['-',5,0,4],['+',4,0,5]]
        validate(p,nested_windows(p,code,width=2,levels=2))
