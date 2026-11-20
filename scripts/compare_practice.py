"""Reproduce A2/A3 comparison on practice only; no heuristic changes."""
import csv
import hashlib
import json
import platform
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from elf_calculator.constructors.elf_baselines import Puzzle, rings, bisection, validate

def main():
    source = ROOT / 'practice_puzzles.csv'
    with source.open(newline='', encoding='utf-8') as fp:
        inputs = list(csv.DictReader(fp))
    rows = []
    for raw in inputs:
        puzzle = Puzzle.from_dict(raw)
        row = {k: raw[k] for k in ('id', 'family', 'design_tier', 'lower_bound')}
        for name, algorithm in [('a2', rings), ('a3', bisection)]:
            try:
                program = algorithm(puzzle)
                row[name + '_steps'] = validate(puzzle, program)['steps']
                row[name + '_error'] = ''
            except (ValueError, IndexError, KeyError, TypeError, AssertionError) as exc:
                row[name + '_steps'] = ''
                row[name + '_error'] = f'{type(exc).__name__}: {exc}'
        a, b = row['a2_steps'], row['a3_steps']
        row['status'] = ('both' if b != '' else 'only_a2') if a != '' else ('only_a3' if b != '' else 'neither')
        row['delta_a3_minus_a2'] = b - a if row['status'] == 'both' else ''
        rows.append(row)
    with (ROOT / 'reports/practice_comparison.csv').open('w', newline='') as fp:
        writer = csv.DictWriter(fp, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    def summary(group):
        common = [r for r in group if r['status'] == 'both']
        result = {'count': len(group)}
        for name in ('a2', 'a3'):
            values = [r[name + '_steps'] for r in group if r[name + '_steps'] != '']
            result[name] = {'solved': len(values)}
        result['coverage'] = {s: sum(r['status'] == s for r in group)
                              for s in ('both', 'only_a2', 'only_a3', 'neither')}
        result['common'] = {
            'count': len(common),
            'a2_total': sum(r['a2_steps'] for r in common),
            'a3_total': sum(r['a3_steps'] for r in common),
            'a3_wins': sum(r['delta_a3_minus_a2'] < 0 for r in common),
            'ties': sum(r['delta_a3_minus_a2'] == 0 for r in common),
            'a2_wins': sum(r['delta_a3_minus_a2'] > 0 for r in common),
            'median_delta': statistics.median(r['delta_a3_minus_a2'] for r in common) if common else None,
        }
        return result

    report = {
        'python': platform.python_version(),
        'sha256': {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
                   for name in ('practice_puzzles.csv', 'elf_calculator/constructors/elf_baselines.py')},
        'overall': summary(rows),
        'family': {key: summary([r for r in rows if r['family'] == key])
                   for key in sorted({r['family'] for r in rows})},
        'design_tier': {key: summary([r for r in rows if r['design_tier'] == key])
                   for key in sorted({r['design_tier'] for r in rows})},
        'only_a3_ids': [r['id'] for r in rows if r['status'] == 'only_a3'],
        'only_a2_ids': [r['id'] for r in rows if r['status'] == 'only_a2'],
        'neither_ids': [r['id'] for r in rows if r['status'] == 'neither'],
        'largest_improvements': sorted([r for r in rows if r['status'] == 'both'],
                                      key=lambda r: r['delta_a3_minus_a2'])[:5],
        'largest_regressions': sorted([r for r in rows if r['status'] == 'both'],
                                     key=lambda r: r['delta_a3_minus_a2'], reverse=True)[:5],
    }
    (ROOT / 'reports/practice_summary.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))

if __name__ == '__main__':
    main()
