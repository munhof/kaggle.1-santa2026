import unittest
from scripts.compare_factors import materialize, shortlist, detect
from scripts.compare_shared_paths import Puzzle, recipes, validate

class FactorTests(unittest.TestCase):
    def test_shared_negative_and_zero(self):
        p=Puzzle('offset',[1,2,3,1000003],[2000005,3000009],4000000)
        base=[['+',3,3,4],['-',4,0,5],['+',5,3,6],['+',6,0,7]]
        code=materialize(p,recipes(p,base),tuple(p.targets),(1000003,-1,0))
        self.assertEqual(validate(p,code)['steps'],3)
        self.assertIn((1000003,-1,0),detect(p.targets)[tuple(p.targets)])

    def test_expensive_maximum_and_cheap_alternative(self):
        pair = (4000007, 6000010)
        candidates = detect(pair)[pair]
        available = {2000003, 1, 2, 3}
        maximum = shortlist(pair, candidates, available, {}, False)
        expanded = shortlist(pair, candidates, available, {}, True)
        self.assertEqual(maximum, [(2000011, -15, -23)])
        self.assertEqual(expanded[:2], [*maximum, (2000003, 1, 1)])
        self.assertEqual(len(set(expanded)), 8)
        p=Puzzle('limit',[1,2,10],[9,20],20)
        graph={9:('-',10,1),20:('*',10,2)}
        self.assertEqual(len(materialize(p,graph,(9,20),(10,-1,0))),2)
        self.assertIsNone(materialize(p,graph,(9,20),(11,-2,-2)))

    def test_cyclic_ingredient(self):
        p=Puzzle('cycle',[1,2],[5,11],20)
        graph={4:('+',2,2),5:('+',4,1),10:('*',5,2),11:('+',10,1)}
        # g=10 already depends on 5; invalid products or cyclic replacements must not win.
        self.assertIsNone(materialize(p,graph,(5,11),(10,-5,1)))
