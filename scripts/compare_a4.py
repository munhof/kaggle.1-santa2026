"""Benchmark A4 on saved practice baseline. Every run gets a fresh directory."""
import sys, csv, json, tempfile
from collections import Counter
from pathlib import Path
from time import monotonic
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from elf_calculator.constructors.elf_baselines import Puzzle, validate
from elf_calculator.optimizers.elf_a4 import optimize_a4

def read(name):
    with (ROOT/name).open() as f:
        rows = list(csv.DictReader(f))
    assert len(rows)==len({r['id'] for r in rows})==200
    return {r['id']:r for r in rows}

def main():
    puzzles = read('practice_puzzles.csv')
    baseline = read('multirings_reuse_postprocessed_results.csv')
    assert puzzles.keys()==baseline.keys()
    programs = {k:json.loads(v['program']) for k,v in baseline.items()}
    assert sum(map(len,programs.values()))==152585
    out = Path(tempfile.mkdtemp(prefix='a4_',dir=ROOT/'reports'))
    print(out,flush=True)
    rows,summary,solutions = [],{},[]
    for mode in ['baseline','additive','division','mixed','all']:
        start = monotonic()
        family = Counter()
        valid = improved = total = 0
        for k,r in puzzles.items():
            p = Puzzle.from_dict(r)
            original = programs[k]
            result = original
            stats = {}
            error = ''
            try:
                validate(p,original)
                if mode!='baseline':
                    result,stats = optimize_a4(p,original,mode=mode,return_stats=True)
                validate(p,result)
                assert len(result)<=len(original)
                valid += 1
            except Exception as exc:
                error = repr(exc)
                result = original
            gain = len(original)-len(result)
            total += len(result)
            family[r['family']] += gain
            improved += gain>0
            rows.append(dict(id=k,mode=mode,family=r['family'],before=len(original),after=len(result),error=error,**{a:b for a,b in stats.items() if a not in ('before','after')}))
            if mode=='all':
                solutions.append(dict(id=k,program=json.dumps(result,separators=(',',':'))))
        summary[mode] = dict(valid=valid,steps=total,saved=152585-total,percent=100*(152585-total)/152585,improved=improved,unchanged=200-improved,seconds=round(monotonic()-start,2),by_family_saved=family)
        print(mode,summary[mode],flush=True)
    for name,data in [('instances',rows),('programs',solutions)]:
        with (out/(name+'.csv')).open('w',newline='') as f:
            w = csv.DictWriter(f,fieldnames=list(dict.fromkeys(key for row in data for key in row)))
            w.writeheader()
            w.writerows(data)
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
if __name__=='__main__': main()
