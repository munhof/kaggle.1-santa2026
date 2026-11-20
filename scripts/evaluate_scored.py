"""Run local constructors and replay the exported best program per scored ID."""
import csv
import json
import multiprocessing
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from tempfile import mkdtemp

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from elf_calculator.constructors.elf_baselines import Puzzle, ConstructionError, validate, incremental, rings, bisection
from elf_calculator.constructors.elf_bisection_reuse import bisection_reuse
from elf_calculator.constructors.elf_multirings import multirings
from elf_calculator.constructors.elf_multirings_reuse import multirings_reuse
from elf_calculator.optimizers.elf_postprocess import postprocess
from elf_calculator.optimizers.elf_a4 import optimize_a4
from elf_calculator.optimizers.elf_nested import nested_windows

def evaluate(args):
    p, sample = args
    sizes, errors = {}, {}
    candidates = {}
    def record(name, program):
        sizes[name] = validate(p, program)['steps']
        candidates[name] = program
    record('sample', json.loads(sample))
    for fn in (incremental, rings, bisection, multirings, bisection_reuse, multirings_reuse):
        try:
            record(fn.__name__, fn(p))
        except ConstructionError as exc:
            errors[fn.__name__] = str(exc)
    prior = candidates.get('multirings_reuse')
    if prior is not None:
        for name,fn in [('postprocess',postprocess),('a4',optimize_a4),('nested',nested_windows)]:
            try:
                prior = fn(p,prior)
                record(name, prior)
            except (ValueError, TypeError, IndexError, AssertionError) as exc:
                errors[name] = str(exc)
                break
    winner = min(sizes, key=sizes.get)
    return p.id, winner, sizes, errors, candidates[winner]

def index(path):
    with path.open(newline='') as fp:
        rows = list(csv.DictReader(fp))
    result = {r['id']:r for r in rows}
    if len(result)!=len(rows) or len(rows)!=1000:
        raise ValueError(f'IDs duplicados o incompletos en {path}')
    return result

def main():
    puzzles = {k:Puzzle.from_dict(r) for k,r in index(ROOT/'puzzles.csv').items()}
    sample = index(ROOT/'sample_submission.csv')
    assert sample.keys()==puzzles.keys()
    out = Path(mkdtemp(prefix='scored_',dir=ROOT/'reports'))
    print(out,flush=True)
    variants = 'sample incremental rings bisection multirings bisection_reuse multirings_reuse postprocess a4 nested'.split()
    with (out/'comparison.csv').open('w',newline='') as stats, (out/'candidate.csv').open('w',newline='') as fp, ProcessPoolExecutor(max_workers=14, mp_context=multiprocessing.get_context('fork')) as pool:
        writer = csv.writer(fp)
        writer.writerow(['id','program'])
        report = csv.DictWriter(stats,fieldnames=['id','winner','steps',*variants,'errors'])
        report.writeheader()
        for n,(k,w,s,e,program) in enumerate(pool.map(evaluate, ((p,sample[k]['program']) for k,p in puzzles.items())),1):
            writer.writerow([k,json.dumps(program,separators=(',',':'))])
            report.writerow(dict(id=k,winner=w,steps=s[w],**s,errors=json.dumps(e)))
            if n%100==0:
                fp.flush()
                stats.flush()
                print(n,flush=True)
    exported = index(out/'candidate.csv')
    assert exported.keys()==puzzles.keys()
    total = 0
    for k,r in exported.items():
        assert len(r['program'].encode('utf8'))<=131072
        total += validate(puzzles[k],json.loads(r['program']))['steps']
    (out/'candidate.csv').rename(out/'submission.csv')
    print('Validated 1000',total,flush=True)

if __name__=='__main__': main()
