import unittest
from scripts.compare_shared_paths import chain

class PathTests(unittest.TestCase):
    def test_depth_budget(self):
        one = {25:('*',5,5),10:('+',5,5),1:('/',5,5)}
        self.assertEqual(len(chain(125,[5],one,2,625)),2)
        self.assertIsNone(chain(625,[5],one,2,625))
        self.assertEqual(len(chain(625,[5],one,3,625)),3)
