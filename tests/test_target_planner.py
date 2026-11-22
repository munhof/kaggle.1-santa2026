import unittest
from scripts.target_planner import source

class PlannerTests(unittest.TestCase):
    def test_generated_solver(self):
        import tempfile,subprocess
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            cpp=Path(tmp)/'solver.cpp'
            cpp.write_text(source())
            exe=cpp.with_suffix('')
            subprocess.run(['g++','-std=c++17','-O2',cpp,'-o',exe],check=True)
            subprocess.run([exe,'selftest'],check=True)
