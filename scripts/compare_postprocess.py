"""Reproduce postprocessing comparison on exported practice programs only."""
import csv
import hashlib
import json
import sys
from pathlib import Path
from time import perf_counter
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from elf_calculator.constructors.elf_baselines import Puzzle, validate
from elf_calculator.optimizers.elf_postprocess import postprocess


def main():
    with (ROOT/'practice_puzzles.csv').open() as fp:
        puzzles = {r['id']: Puzzle.from_dict(r) for r in csv.DictReader(fp)}
    with (ROOT/'multirings_reuse_results.csv').open() as fp:
        inputs = list(csv.DictReader(fp))
    rows, outputs = [], []
    start = perf_counter()
    for raw in inputs:
        p = puzzles[raw['id']]
        original = json.loads(raw['program'])
        optimized = postprocess(p, original)
        validate(p, optimized)
        rows.append(dict(id=p.id, before=len(original), after=len(optimized),
                         saved=len(original)-len(optimized)))
        outputs.append(dict(id=p.id, program=json.dumps(optimized, separators=(',', ':'))))
    for path, data in [('reports/postprocess_comparison.csv', rows),
                       ('multirings_reuse_postprocessed_results.csv', outputs)]:
        with (ROOT/path).open('w', newline='') as fp:
            writer = csv.DictWriter(fp, fieldnames=list(data[0]))
            writer.writeheader()
            writer.writerows(data)
    summary = dict(valid=len(rows), before=sum(r['before'] for r in rows),
                   after=sum(r['after'] for r in rows),
                   improved=sum(r['saved']>0 for r in rows),
                   elapsed_seconds=perf_counter()-start,
                   sha256={n: hashlib.sha256((ROOT/n).read_bytes()).hexdigest()
                           for n in ('elf_calculator/optimizers/elf_postprocess.py', 'practice_puzzles.csv',
                                     'multirings_reuse_results.csv')})
    (ROOT/'reports/postprocess_summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
