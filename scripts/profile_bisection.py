"""Count emitted instructions without changing A3; practice data only."""
import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from elf_calculator.constructors.elf_baselines import Builder, ConstructionError, Puzzle, bisection, validate

PHASES = ('setup', 'boundary_numbers', 'boundary_multiplication', 'midpoints')


def profile(puzzle):
    counts = Counter()
    seen = set(puzzle.starting_values)
    captured = []
    original = Builder.emit

    def measured(builder, op, i, j, d):
        frame = sys._getframe(1)
        names = []
        a3 = None
        while frame:
            names.append(frame.f_code.co_name)
            if frame.f_code.co_name == 'bisection':
                a3 = frame
                break
            frame = frame.f_back
        if 'boundary' in names:
            phase = 'boundary_numbers' if 'number' in names else 'boundary_multiplication'
        else:
            phase = 'midpoints' if a3 and 'target' in a3.f_locals else 'setup'
        previous = set(builder.memory)
        occupied = builder.memory[d] is not None
        original(builder, op, i, j, d)
        value = builder.memory[d]
        counts[phase] += 1
        counts['overwrites'] += occupied
        counts['recreated_absent'] += value in seen and value not in previous
        counts['duplicate_resident'] += value in previous
        seen.add(value)
        captured.append([op, i, j, d])

    error = ''
    with patch.object(Builder, 'emit', measured):
        try:
            program = bisection(puzzle)
            validate(puzzle, program)
        except ConstructionError as exc:
            error = str(exc)
    # Independent uninstrumented execution checks that profiling is transparent.
    normal_error = ''
    try:
        normal = bisection(puzzle)
        assert normal == captured
        validate(puzzle, normal)
    except ConstructionError as exc:
        normal_error = str(exc)
    assert normal_error == error
    assert sum(counts[k] for k in PHASES) == len(captured)
    return dict(status='failed' if error else 'valid', error=error,
                emitted=len(captured), **{k: counts[k] for k in
                (*PHASES, 'overwrites', 'recreated_absent', 'duplicate_resident')})


def main():
    # A tiny known construction verifies phase assignment and count accounting.
    tiny = profile(Puzzle('synthetic', [1], [2], 2))
    assert tiny['setup'] == 1 and tiny['emitted'] == 1
    with (ROOT / 'practice_puzzles.csv').open() as fp:
        inputs = list(csv.DictReader(fp))
    rows = [dict(id=r['id'], family=r['family'], design_tier=r['design_tier'],
                 **profile(Puzzle.from_dict(r))) for r in inputs]
    with (ROOT / 'reports/a3_profile.csv').open('w', newline='') as fp:
        writer = csv.DictWriter(fp, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    def aggregate(group):
        return dict(instances=len(group), **{
            key: sum(r[key] for r in group) for key in
            ('emitted', *PHASES, 'overwrites', 'recreated_absent', 'duplicate_resident')})

    summary = {
        'sha256': {n: hashlib.sha256((ROOT/n).read_bytes()).hexdigest()
                   for n in ('elf_calculator/constructors/elf_baselines.py', 'practice_puzzles.csv')},
        'note': 'Failed cases include only the first 4096 emitted instructions. '
                'Recreated values and resident duplicates overlap phase totals; '
                'these counts do not measure avoidable instructions.',
        'by_status': {s: aggregate([r for r in rows if r['status'] == s])
                      for s in ('valid', 'failed')},
        'by_family': {f: {s: aggregate([r for r in rows if r['family'] == f and r['status'] == s])
                          for s in ('valid', 'failed')}
                      for f in sorted({r['family'] for r in rows})},
    }
    (ROOT / 'reports/a3_profile.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
