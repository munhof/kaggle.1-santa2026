import importlib.util
import tempfile
import unittest
from pathlib import Path
from elf_calculator.constructors.elf_baselines import Puzzle, validate
from scripts.compare_four import joint, repair, dictionary_source, dashboard, winner

class FourTests(unittest.TestCase):
    def test_joint_and_shared_branch(self):
        p = Puzzle('x', [2, 3, 10], [17, 40], 100)
        a = [['+',2,2,3],['-',3,1,4],['+',3,3,5]]
        b = [['-',2,1,3],['+',3,2,4],['+',2,2,3],['+',3,3,5]]
        self.assertLessEqual(validate(p,repair(p,b)[0])['steps'],3)

    @unittest.skipUnless(importlib.util.find_spec('ortools'), 'requires experiment environment')
    def test_joint_combines_two_banks(self):
        p = Puzzle('joint',[2,3,10],[17,37],100)
        first = [['-',2,1,3],['+',3,2,4],['+',2,2,5],['+',5,5,6],['-',6,1,7]]
        second = [['+',2,2,3],['-',3,1,4],['-',2,1,5],['*',2,1,6],['+',6,5,7]]
        self.assertEqual(validate(p,joint(p,[first,second])[0])['steps'],4)

    def test_dictionary(self):
        self.assertIn('leaves.size() < 72',dictionary_source(52))

    def test_resume_and_selection(self):
        p = {'E1':[1,2], 'hist':[1]}
        self.assertEqual(winner(p),'hist')
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'diario.ipynb'
            path.write_text('{"cells":[]}')
            dashboard(path,'1 listo, 1 pendiente')
            dashboard(path,'2 listos')
            import json
            self.assertEqual(len(json.loads(path.read_text())['cells']),1)
