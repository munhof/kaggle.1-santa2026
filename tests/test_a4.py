import unittest
from elf_calculator.constructors.elf_baselines import Puzzle, validate
from elf_calculator.optimizers.elf_a4 import _candidates, optimize_a4

class A4Tests(unittest.TestCase):
 def test_overshoot_candidates_arithmetic(self):
  p=Puzzle('97',[1,3,10],[97],300)
  seqs=list(_candidates(p,p.starting_values+[None]*45,97,1000,3))
  # includes 10*10=100 then subtract 3
  self.assertTrue(any(len(s)==2 and s[0][0]=='*' and s[1][0]=='-' for s,_ in seqs))
 def test_keep_original_valid_and_no_longer(self):
  p=Puzzle('x',[1,3,10],[97],300)
  program=[['*',2,2,3],['-',3,1,4],['-',4,0,5]]
  validate(p,program)
  result,stats=optimize_a4(p,program,return_stats=True)
  self.assertTrue(validate(p,result)['valid'])
  self.assertLessEqual(len(result),len(program))
 def test_limit_reject(self):
  p=Puzzle('limit',[1,3,10],[97],99)
  mem=p.starting_values+[None]*45
  self.assertFalse(any(seq[0][0]=='*' and seq[0][1:3]==[2,2] for seq,_ in _candidates(p,mem,97,200,3)))
if __name__=='__main__': unittest.main()
