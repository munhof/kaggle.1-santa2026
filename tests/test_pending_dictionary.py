import subprocess
import tempfile
import unittest
from pathlib import Path

class PendingTests(unittest.TestCase):
    def test_old_helper_serves_two_pending_targets(self):
        header=Path('elf_calculator/constructors/pending_dictionary.hpp').resolve()
        with tempfile.TemporaryDirectory() as directory:
            exe=Path(directory)/'test'
            source=f'#include "{header}"\n'+'''
int main(){
    std::vector<long long> fixed{1,3}, recent{11,10,70}, pending{69,71};
    auto ranked=rank_pending(recent,fixed,pending);
    return ranked.front()==70 && ranked[1]==11 ? 0 : 1;
}
'''
            subprocess.run(['g++','-std=c++17','-x','c++','-','-o',exe],input=source,text=True,check=True)
            subprocess.run([exe],check=True)
