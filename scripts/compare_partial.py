"""Compare four selection routes and replay their practice portfolio."""
import csv
import json
import multiprocessing
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from tempfile import mkdtemp
from time import perf_counter

from scripts.compare_dag import (ROOT, STAGES, Puzzle, ConstructionError, validate,
    incremental, rings, bisection, multirings, bisection_reuse, multirings_reuse,
    postprocess, optimize_dag)
from scripts.validate_submission import verify
from elf_calculator.optimizers.elf_partial import recipes, candidates

CONSTRUCTORS = (incremental, rings, bisection, multirings, bisection_reuse, multirings_reuse)
HISTORY = ROOT / 'reports/dag_practice_gpvvc01y/comparison.csv'


def finish(p, code):
    for stage in STAGES[1:]:
        code = stage(p, code)
    validate(p, code)
    return code


def evaluate(p, historical):
    originals, errors = {}, {}
    for fn in CONSTRUCTORS:
        try:
            code = fn(p)
            validate(p, code)
            originals[fn.__name__] = code
        except ConstructionError as exc:
            errors[fn.__name__] = str(exc)

    name, stage, expected = historical
    best = originals[name]
    for label, transform in zip(('constructor', 'postprocess', 'a4', 'nested'), (*STAGES, None)):
        if label == stage:
            best = optimize_dag(p, best)
        if transform:
            best = transform(p, best)
    if validate(p, best)['steps'] != expected:
        raise ValueError((p.id, historical, len(best)))

    cooked, prep = {}, {}
    for name, code in originals.items():
        start = perf_counter()
        cooked[name] = postprocess(p, code)
        prep[name] = perf_counter() - start
    raw_pool = [recipes(p, code) for code in originals.values()]
    cooked_pool = [recipes(p, code) for code in cooked.values()]
    rows = [(p.id, name, r, 0, '', '', '', '', '', err)
            for name, err in errors.items() for r in 'ABCD']
    winner = 'historical'
    for name, base in originals.items():
        start = perf_counter()
        raw = candidates(p, base, raw_pool)
        search = perf_counter() - start
        short = min(range(len(raw)), key=lambda i: len(raw[i]))
        posts = {0: cooked[name]}
        finals = {}
        post_times = {0: prep[name]}
        for route in 'ABCD':
            elapsed = 0
            if route == 'D':
                start = perf_counter()
                options = candidates(p, cooked[name], cooked_pool)
                idx = min(range(len(options)), key=lambda i: len(options[i]))
                post = options[idx]
                elapsed = perf_counter() - start + prep[name]
            else:
                options = [base] if route == 'A' else raw
                indices = {'A': [0], 'B': [short], 'C': range(len(raw))}[route]
                for i in indices:
                    if i not in posts:
                        start = perf_counter()
                        posts[i] = postprocess(p, raw[i])
                        post_times[i] = perf_counter() - start
                idx = min(indices, key=lambda i: len(posts[i]))
                post = posts[idx]
                elapsed = sum(post_times[i] for i in indices)
                if route != 'A':
                    elapsed += search
            key = tuple(map(tuple, post))
            if key not in finals:
                start = perf_counter()
                final = finish(p, post)
                finals[key] = final, perf_counter() - start
            final, cost = finals[key]
            rows.append((p.id, name, route, len(options), idx, len(options[idx]),
                         len(post), len(final), elapsed + cost, ''))
            if len(final) < len(best):
                best, winner = final, f'{route}/{name}/{idx}'
    return p.id, rows, expected, winner, best


def main():
    data = ROOT / 'practice_puzzles.csv'
    with data.open() as fp:
        puzzles = list(map(Puzzle.from_dict, csv.DictReader(fp)))
    history = {}
    with HISTORY.open() as fp:
        for row in csv.DictReader(fp):
            if row['error']:
                continue
            k = row['id']
            score = int(row['dag_final'])
            if k not in history or score < history[k][2]:
                history[k] = row['algorithm'], row['insertion'], score
    if len(history) != 200 or sum(s for _, _, s in history.values()) != 98127:
        raise ValueError('Referencia histórica incompleta')
    out = Path(mkdtemp(prefix='partial_practice_', dir=ROOT / 'reports'))
    print(out, flush=True)
    with ((out/'comparison.csv').open('w') as detail, (out/'programs.csv').open('w') as programs,
          (out/'winners.csv').open('w') as scores, ProcessPoolExecutor(14, mp_context=multiprocessing.get_context('fork')) as pool):
        dw, pw, sw = map(csv.writer, (detail, programs, scores))
        dw.writerow('id algorithm route candidates selected input post final seconds error'.split())
        pw.writerow(('id', 'program'))
        sw.writerow(('id', 'historical', 'A', 'B', 'C', 'D', 'winner', 'final'))
        for k, rows, expected, winner, best in pool.map(evaluate, puzzles, [history[p.id] for p in puzzles]):
            dw.writerows(rows)
            pw.writerow((k, json.dumps(best, separators=(',', ':'))))
            route_scores = [min(row[7] for row in rows if row[2] == route and row[3])
                            for route in 'ABCD']
            sw.writerow((k, expected, *route_scores, winner, len(best)))
            for fp in (detail, programs, scores):
                fp.flush()
    print(verify(data, out/'programs.csv'), flush=True)


if __name__ == '__main__':
    main()
