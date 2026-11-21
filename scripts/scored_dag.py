"""Compare DAG routes on the scored set and export validated per-ID winners."""
import csv
import json
import multiprocessing
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from tempfile import mkdtemp

from scripts.compare_dag import (ROOT, Puzzle, validate, compare, summarize, incremental,
    rings, bisection, multirings, bisection_reuse, multirings_reuse)
from scripts.evaluate_scored import index
from scripts.validate_submission import verify


def evaluate(args):
    puzzle, previous = args
    best = json.loads(previous)
    previous_steps = validate(puzzle, best)['steps']
    winner = 'previous'
    rows = []
    for fn in (incremental, rings, bisection, multirings, bisection_reuse, multirings_reuse):
        detail, candidate = compare(puzzle, fn, export=True)
        rows.extend(detail)
        if candidate is not None and len(candidate) < len(best):
            best = candidate
            winner = fn.__name__
    return puzzle.id, rows, best, winner, previous_steps


def main():
    puzzles = {k: Puzzle.from_dict(v) for k, v in index(ROOT / 'puzzles.csv').items()}
    previous = index(ROOT / 'artifacts/submission.csv')
    if previous.keys() != puzzles.keys():
        raise ValueError('IDs distintos en el entregable previo')
    out = Path(mkdtemp(prefix='dag_scored_', dir=ROOT / 'reports'))
    print(out, flush=True)
    with (
        (out / 'comparison.csv').open('w', newline='') as report,
        (out / 'candidate.csv').open('w', newline='') as submission,
        (out / 'winners.csv').open('w', newline='') as winners,
        ProcessPoolExecutor(14, mp_context=multiprocessing.get_context('fork')) as pool,
    ):
        detail, programs, scores = map(csv.writer, (report, submission, winners))
        detail.writerow(('id', 'algorithm', 'insertion', 'before', 'after', 'control_final', 'dag_final', 'error'))
        programs.writerow(('id', 'program'))
        scores.writerow(('id', 'algorithm', 'previous', 'steps'))
        jobs = ((p, previous[k]['program']) for k, p in puzzles.items())
        for n, (k, rows, best, alg, prior) in enumerate(pool.map(evaluate, jobs), 1):
            detail.writerows(rows)
            programs.writerow((k, json.dumps(best, separators=(',', ':'))))
            scores.writerow((k, alg, prior, len(best)))
            if n % 20 == 0:
                for fp in (report, submission, winners):
                    fp.flush()
                print(n, '/ 1000', flush=True)
    count, total = verify(ROOT / 'puzzles.csv', out / 'candidate.csv')
    summarize(out)
    (out / 'candidate.csv').rename(out / 'submission.csv')
    print(f'Validated {count}', total, flush=True)


if __name__ == '__main__':
    main()
