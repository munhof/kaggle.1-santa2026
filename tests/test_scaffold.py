import unittest
from scripts.blind_scaffold import rebuild
from scripts.compare_four import Puzzle,validate

class ScaffoldTest(unittest.TestCase):
    def test_joint_helpers_reach_distinct_targets(self):
        p=Puzzle('joint',[2,3,5],[7,9,11,25],100)
        # Produce every odd value from seven to twenty-five.
        base=[['+',0,2,3]] + [['+',i,0,i+1] for i in range(3,12)]
        code,stats=rebuild(p,base)
        self.assertLess(validate(p,code)['steps'],len(base))
        self.assertLess(len(code),stats['single'])
        self.assertGreaterEqual(len(stats['helpers']),2)
        self.assertEqual(stats['targets'],4)
