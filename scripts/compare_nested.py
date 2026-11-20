"""Compare nested windows using the saved 200 A4 practice programs."""
import argparse
import csv
import json
import sys
from pathlib import Path
from tempfile import mkdtemp
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from elf_calculator.constructors.elf_baselines import Puzzle, validate
from elf_calculator.optimizers.elf_nested import nested_windows

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('a4_programs', type=Path)
    args = parser.parse_args()
    with (ROOT/'practice_puzzles.csv').open() as f:
        puzzles = {r['id']:Puzzle.from_dict(r) for r in csv.DictReader(f)}
    with (ROOT/args.a4_programs).open() as f:
        programs = {r['id']:json.loads(r['program']) for r in csv.DictReader(f)}
    assert programs.keys()==puzzles.keys() and len(programs)==200
    assert sum(map(len,programs.values()))==152035
    out = Path(mkdtemp(prefix='nested_',dir=ROOT/'reports'))
    with (out/'comparison.csv').open('w') as f, (out/'programs.csv').open('w') as g:
        w,v = csv.writer(f),csv.writer(g)
        w.writerow(['id','before','after'])
        v.writerow(['id','program'])
        total = wins = 0
        for k,code in programs.items():
            result = nested_windows(puzzles[k],code)
            validate(puzzles[k],result)
            assert len(result)<=len(code)
            total += len(result)
            wins += len(result)<len(code)
            w.writerow([k,len(code),len(result)])
            v.writerow([k,json.dumps(result,separators=(',',':'))])
    print(out,total,wins)
if __name__=='__main__': main()
