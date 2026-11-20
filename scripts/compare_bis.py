"""Compare the preserved A2/A3 and both bis variants on practice only."""
import csv
import hashlib
import json
import sys
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from elf_calculator.constructors.elf_baselines import Puzzle, rings, bisection, validate
from elf_calculator.constructors.elf_multirings import multirings
from elf_calculator.constructors.elf_multirings_reuse import multirings_reuse
from elf_calculator.constructors.elf_bisection_reuse import bisection_reuse


def main():
    algorithms = dict(rings=rings, bisection=bisection,
                      multirings=multirings, bisection_reuse=bisection_reuse,
                      multirings_reuse=multirings_reuse)
    with (ROOT / 'practice_puzzles.csv').open() as fp:
        inputs = list(csv.DictReader(fp))
    rows = []
    elapsed = {name: 0.0 for name in algorithms}
    for raw in inputs:
        p = Puzzle.from_dict(raw)
        row = {key: raw[key] for key in ('id', 'family', 'design_tier')}
        for name, algorithm in algorithms.items():
            start = perf_counter()
            try:
                program = algorithm(p)
                row[name] = validate(p, program)['steps']
                row[name + '_error'] = ''
            except (ValueError, IndexError, KeyError, TypeError, AssertionError) as exc:
                row[name] = None
                row[name + '_error'] = f'{type(exc).__name__}: {exc}'
            elapsed[name] += perf_counter() - start
        rows.append(row)
    with (ROOT / 'reports/bis_comparison.csv').open('w', newline='') as fp:
        writer = csv.DictWriter(fp, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = {}
    for name in algorithms:
        common = [r for r in rows if r[name] is not None and r['bisection'] is not None]
        summary[name] = {
            'solved': sum(r[name] is not None for r in rows),
            'elapsed_seconds_including_validation': elapsed[name],
            'common_with_a3': len(common),
            'common_a3_steps': sum(r['bisection'] for r in common),
            'common_variant_steps': sum(r[name] for r in common),
            'wins_vs_a3': sum(r[name] < r['bisection'] for r in common),
            'ties_vs_a3': sum(r[name] == r['bisection'] for r in common),
            'losses_vs_a3': sum(r[name] > r['bisection'] for r in common),
            'recovered_vs_a3': [r['id'] for r in rows if r[name] is not None and r['bisection'] is None],
            'lost_vs_a3': [r['id'] for r in rows if r[name] is None and r['bisection'] is not None],
        }
    common_all = [r for r in rows if all(r[n] is not None for n in algorithms)]
    output = dict(algorithms=summary,
                  common_all_count=len(common_all),
                  common_all_steps={n: sum(r[n] for r in common_all) for n in algorithms},
                  sha256={n: hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in
                          ('practice_puzzles.csv', 'elf_calculator/constructors/elf_baselines.py', 'elf_calculator/constructors/elf_multirings.py', 'elf_calculator/constructors/elf_bisection_reuse.py', 'elf_calculator/constructors/elf_multirings_reuse.py')})
    (ROOT / 'reports/bis_summary.json').write_text(json.dumps(output, indent=2)+'\n')
    print(json.dumps(output, indent=2))


if __name__ == '__main__':
    main()
