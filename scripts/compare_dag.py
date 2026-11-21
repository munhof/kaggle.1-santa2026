"""Compare single DAG insertions with matched controls on practice puzzles."""
import csv
from collections import defaultdict
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
import sys
from tempfile import mkdtemp

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.evaluate_scored import (Puzzle, ConstructionError, validate, incremental,
    rings, bisection, multirings, bisection_reuse, multirings_reuse, postprocess,
    optimize_a4, nested_windows)
from elf_calculator.optimizers.elf_dag import optimize_dag

STAGES = (postprocess, optimize_a4, nested_windows)


def compare(puzzle, constructor):
    try:
        initial = constructor(puzzle)
    except ConstructionError as exc:
        return [(puzzle.id, constructor.__name__, 'failed', '', '', '', '', str(exc))]
    control = [initial]
    for stage in STAGES:
        control.append(stage(puzzle, control[-1]))
    final = validate(puzzle, control[-1])['steps']
    rows = []
    for index, program in enumerate(control):
        candidate = optimize_dag(puzzle, program)
        immediate = len(candidate)
        score = final
        if immediate < len(program):
            for stage in STAGES[index:]:
                candidate = stage(puzzle, candidate)
            score = validate(puzzle, candidate)['steps']
        label = ('constructor', 'postprocess', 'a4', 'nested')[index]
        rows.append((puzzle.id, constructor.__name__, label, len(program),
                     immediate, final, score, ''))
    return rows


def summarize(out):
    groups = defaultdict(list)
    with (out / 'comparison.csv').open() as fp:
        for row in csv.DictReader(fp):
            if not row['error']:
                groups[row['algorithm'], row['insertion']].append(row)
    with (out / 'summary.csv').open('w', newline='') as fp:
        writer = csv.writer(fp)
        writer.writerow(('algorithm', 'insertion', 'solved', 'immediate_saved',
                         'control_final', 'dag_final', 'wins', 'ties', 'losses'))
        for (algorithm, stage), rows in groups.items():
            immediate = sum(int(r['before']) - int(r['after']) for r in rows)
            controls = [int(r['control_final']) for r in rows]
            scores = [int(r['dag_final']) for r in rows]
            gains = [a - b for a, b in zip(controls, scores)]
            writer.writerow((algorithm, stage, len(rows), immediate, sum(controls),
                             sum(scores), sum(g > 0 for g in gains),
                             gains.count(0), sum(g < 0 for g in gains)))


def main():
    out = Path(mkdtemp(prefix='dag_practice_', dir=ROOT / 'reports'))
    print(out, flush=True)
    with (ROOT / 'practice_puzzles.csv').open() as fp:
        puzzles = list(map(Puzzle.from_dict, csv.DictReader(fp)))
    with (out / 'comparison.csv').open('w', newline='') as fp, ProcessPoolExecutor(14, mp_context=multiprocessing.get_context('fork')) as pool:
        writer = csv.writer(fp)
        writer.writerow(('id', 'algorithm', 'insertion', 'before', 'after', 'control_final',
                         'dag_final', 'error'))
        jobs = [pool.submit(compare, p, fn) for p in puzzles for fn in
                (incremental, rings, bisection, multirings, bisection_reuse, multirings_reuse)]
        for index, job in enumerate(as_completed(jobs), 1):
            writer.writerows(job.result())
            if index % 20 == 0:
                fp.flush()
                print(index, '/', len(jobs), flush=True)

    summarize(out)


if __name__ == '__main__':
    main()
