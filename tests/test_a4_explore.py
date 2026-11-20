import unittest
from elf_calculator.constructors.elf_baselines import Puzzle, validate
from elf_calculator.optimizers.elf_a4 import optimize_a4

class CorrectionTests(unittest.TestCase):
    def test_shorter_exact_corrections(self):
        for mode, starts, target, ops in [
            ('additive',[1,3,10],97,['*','-']),
            ('division',[2,3,10],150,['*','*','/']),
            ('mixed',[1,2,3,10],149,['*','*','/','-'])]:
            p = Puzzle(mode, starts, [target], 300)
            n = len(starts)-1
            program = [['*',n,n,10], ['*',10,1 if mode=='division' else 2,10],
                       ['/',10,0 if mode=='division' else 1,10]]
            if mode=='mixed': program.append(['-',10,0,10])
            if mode=='additive': program = [['*',n,n,10],['-',10,1,10]]
            program = [['+',0,0,11]]*3 + program
            result, stats = optimize_a4(p,program,mode=mode,return_stats=True)
            self.assertTrue(validate(p,result)['valid'])
            self.assertGreater(stats[mode],0)
            self.assertLess(len(result),len(program))

    def test_shared_checkpoint_and_live_register(self):
        p = Puzzle('shared',[1,3,10],[97,99,101,103,6],150)
        source = [['+',1,1,8], ['*',2,2,4], ['-',4,1,5],
                  ['-',4,0,5], ['+',4,0,5], ['+',4,1,5], ['+',8,8,7]]
        original = [i.copy() for i in source]
        result = optimize_a4(p,source)
        self.assertTrue(validate(p,result)['valid'])
        self.assertEqual(source,original)
        self.assertLessEqual(len(result),len(source))
