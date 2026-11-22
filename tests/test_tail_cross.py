import unittest
from scripts.tail_cross import cuts, compile_graph, cross_recipes, victim, joint_graph
import importlib.util
from elf_calculator.constructors.elf_baselines import Puzzle, validate

class TailTests(unittest.TestCase):
    def test_prefix_register(self):
        p=Puzzle('p',[2,3],[6,12],20)
        code=[['*',0,1,7],['+',7,7,4]]
        stop,bank,left=cuts(p,code,[1])[0]
        tail,_=compile_graph(bank,left,{12:('+',6,6)},False,False)
        self.assertEqual(validate(p,code[:stop]+tail)['steps'],2)

    def test_cross_recipe(self):
        bank={4:{('+',2,2)},8:{('+',4,4)},16:{('+',8,8)}}
        cross_recipes(bank,[2])
        self.assertIn(('*',4,4),bank[16])

    @unittest.skipUnless(importlib.util.find_spec("ortools"), "requires experiment environment")
    def test_cross_beats_observed_graph(self):
        p=Puzzle('cross',[2],[16],16)
        donor=[['+',0,0,1],['+',1,1,2],['+',2,2,3]]
        lengths=[]
        for cross in (False,True):
            graph,status=joint_graph(p,[donor],cross)
            code,_=compile_graph([2]+[None]*47,[16],graph,False,False)
            lengths.append(validate(p,code)['steps'])
        self.assertEqual(lengths,[3,2])

    def test_eviction(self):
        self.assertEqual(victim([(0,8,8),(1,1,4)],True),1)
        self.assertEqual(victim([(0,8,8),(1,1,4)],False),0)
