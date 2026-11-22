"""Compare bounded shared-factor substitutions on the frozen practice portfolio."""
import csv
import json
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from itertools import combinations
from math import gcd
from multiprocessing import get_context
from time import monotonic

from scripts.compare_dag import STAGES
from scripts.compare_offsets import optimize as additive
from scripts.compare_shared_paths import (
    DATA, ROOT, Puzzle, allocate, inverse, journal, ordered, recipes, validate, verify,
)

BASE = ROOT / 'reports/tail_cross_practice/portfolio.csv'
OUT = ROOT / 'reports/shared_factors_practice'
ARMS = ('hist', 'A', 'B', 'C')


def detect(targets):
    found = {}
    for pair in combinations(sorted(set(targets)), 2):
        lo, hi = pair
        threshold = max(10**6, int(lo ** .4))
        if lo + 24 < threshold:
            continue
        options = set()
        for r in range(-24, 25):
            for s in range(-24, 25):
                g = gcd(lo-r, hi-s)
                if g >= threshold:
                    options.add((g, r, s))
        if options:
            found[pair] = sorted(options, key=lambda c: (-c[0], c[1:]))
    return found


def bank(values, limit):
    one = {}
    anchors = sorted(values)
    for i, a in enumerate(anchors):
        for b in anchors[:i+1]:
            for value, recipe in ((a+b, ('+', a,b)), (a-b, ('-', a,b)),
                                  (a*b, ('*', a,b)), (a//b if a%b == 0 else 0, ('/', a,b))):
                if 0 < value <= limit and value not in values:
                    one.setdefault(value, recipe)
    return one


def shortlist(pair, candidates, available, one, alternatives):
    def cost(c):
        g, *offsets = c
        needed = {g}
        for t, r in zip(pair, offsets):
            k = (t-r)//g
            if k != 1:
                needed.add(k)
            if r:
                needed.add(abs(r))
        return sum(0 if v in available else 1 if v in one else 2 for v in needed), -g, offsets
    maximum = max(candidates, key=lambda c: c[0])
    others = (c for c in candidates if c != maximum)
    return [maximum] + (sorted(others, key=cost)[:7] if alternatives else [])


def usable_values(initial, graph, pair, candidate):
    g, *offsets = candidate
    # An unchanged target equal to g can still be an anchor.
    blocked = {t for t,r in zip(pair,offsets) if (t,r) != (g,0)}
    for v, (_,a,b) in graph.items():  # recipes are in first-production order
        if a in blocked or b in blocked:
            blocked.add(v)
    return initial | (graph.keys()-blocked)


def materialize(p, graph, pair, candidate, one=None, cutoff=None, anchors=None):
    initial = set(p.starting_values)
    if anchors is None:
        anchors = usable_values(initial,graph,pair,candidate)
    if one is None:
        one = bank(anchors, p.value_limit)
    updated = graph.copy()

    def build(v):
        if v in anchors or (v in updated and updated.get(v) != graph.get(v)):
            return True
        if v in pair:
            return False
        if v in one:
            updated[v] = one[v]
            return True
        for a in sorted(anchors):
            for op, b, rev in inverse(v,a):
                if b in one and b != v and b not in pair:
                    updated[b] = one[b]
                    updated[v] = (op,b,a) if rev else (op,a,b)
                    return True
        return False

    g, *offsets = candidate
    if not 0 < g <= p.value_limit or not build(g):
        return None
    for target, r in zip(pair, offsets):
        product = target-r
        k, remainder = divmod(product,g)
        if remainder or k < 1 or product > p.value_limit:
            return None
        if k != 1:
            if not build(k):
                return None
            if product not in anchors or r == 0:
                updated[product] = ('*',g,k)
        if r:
            if not build(abs(r)):
                return None
            updated[target] = ('+' if r>0 else '-',product,abs(r))
    order = ordered(initial,p.targets,updated)
    if order is None or (cutoff is not None and len(order)>=cutoff):
        return None
    return allocate(p,updated,order)


def optimize(p, base, groups, alternatives):
    best = base
    moves = []
    tried = 0
    for _ in range(4):
        if not groups:
            break
        graph = recipes(p,best)
        available = set(p.starting_values) | graph.keys()
        one = bank(available,p.value_limit)
        winner = best
        for pair, options in groups.items():
            previous_anchors = None
            for c in shortlist(pair,options,available,one,alternatives):
                tried += 1
                anchors = usable_values(set(p.starting_values),graph,pair,c)
                if anchors != previous_anchors:
                    safe_one = bank(anchors,p.value_limit)
                    previous_anchors = anchors
                code = materialize(p,graph,pair,c,safe_one,len(winner),anchors)
                if code is not None:
                    validate(p,code)
                    winner = code
                    witness = dict(pair=pair, factor=c[0], residuals=c[1:],
                                   multipliers=[(t-r)//c[0] for t,r in zip(pair,c[1:])])
        if winner is best:
            break
        after = recipes(p,winner)
        witness.update(gain=len(best)-len(winner), removed=sorted(graph.keys()-after.keys()),
                       changed={v:r for v,r in after.items() if graph.get(v)!=r})
        moves.append(witness)
        best = winner
    return best, moves, tried


def run(row, base):
    p = Puzzle.from_dict(row)
    start = monotonic()
    groups = detect(set(p.targets)-set(p.starting_values))
    detection = monotonic()-start
    example = [(pair,c) for pair,cs in groups.items() for c in cs if c[0]==657003598768]
    results = {}
    cache = {}
    for arm in ARMS:
        start = monotonic()
        tried = None
        if arm == 'hist':
            raw,moves = base,[]
        elif arm == 'A':
            raw,moves = additive(p,base)
        else:
            raw,moves,tried = optimize(p,base,groups,arm=='C')
        key = tuple(map(tuple,raw))
        if key not in cache:
            code = raw
            for stage in STAGES:
                code = stage(p,code)
            validate(p,code)
            cache[key] = code
        results[arm] = (len(raw), cache[key], moves, tried, round(monotonic()-start,3))
    return results, len(groups), sum(map(len,groups.values())), detection, example


def main():
    assert verify(DATA,BASE)==(200,31834)
    with BASE.open() as f:
        bases = {r['id']:json.loads(r['program']) for r in csv.DictReader(f)}
    with DATA.open() as f:
        rows = list(csv.DictReader(f))
    pilot = {r['id'] for family in {r['family'] for r in rows}
             for r in [x for x in rows if x['family']==family][:2]}
    OUT.mkdir(exist_ok=True)
    intro = ['## Factores compartidos con residuos pequeños en práctica','',
             'Base de 31.834 pasos. A usa centros aditivos. B prueba el MCD máximo por par. C incluye hasta siete alternativas por coste. Las cuatro columnas incluyen el mismo pulido. Los tiempos por variante incluyen solo el trabajo ejecutado y comparten caché de pulido.','']
    table = ['| ID | Familia | Histórico pulido | A | B | C | Aporte factorial |',
             '|---|---|---:|---:|---:|---:|---:|']
    journal(intro+table,'factores-compartidos')
    family_gain = Counter()
    totals = Counter()
    examples = []
    with ProcessPoolExecutor(14, mp_context=get_context('fork')) as pool, (OUT/'comparison.csv').open('w') as cf, (OUT/'portfolio.csv').open('w') as pf:
        cw,pw = csv.writer(cf),csv.writer(pf)
        cw.writerow(['id','family','pilot','arm','baseline','raw','polished','pairs','candidates','attempts','detection_seconds','arm_seconds','moves'])
        pw.writerow(['id','program'])
        for is_pilot in (True,False):
            jobs = {pool.submit(run,r,bases[r['id']]):r for r in rows if (r['id'] in pilot)==is_pilot}
            for job in as_completed(jobs):
                r = jobs[job]
                pid, family = r['id'],r['family']
                results,pairs,count,seconds,example = job.result()
                scores = []
                totals['detected_ids'] += pairs>0
                totals['pairs'] += pairs
                totals['candidates'] += count
                for arm,(raw,code,moves,tried,duration) in results.items():
                    cw.writerow([pid,family,is_pilot,arm,len(bases[pid]),raw,len(code),pairs,count,tried,seconds,duration,json.dumps(moves)])
                    totals[arm+'_attempts'] += tried or 0
                    scores.append(len(code))
                    totals[arm] += len(code)
                best = min([bases[pid]]+[v[1] for v in results.values()],key=len)
                pw.writerow([pid,json.dumps(best,separators=(',',':'))])
                cf.flush()
                pf.flush()
                gain = min(scores[:2])-len(best)
                family_gain[family] += gain
                totals['wins'] += gain>0
                totals['gain'] += gain
                if pid=='practice_0074':
                    examples.append(f'Ejemplo {pid}, pares y residuos detectados para 657003598768: {example}.')
                table.append('|'+ '|'.join(map(str,[pid,family,*scores,gain]))+'|')
                journal(intro+examples+table,'factores-compartidos')
            print('Piloto' if is_pilot else 'Práctica completa',totals,flush=True)
    count,total = verify(DATA,OUT/'portfolio.csv')
    summary = [f'{count} programas validados, {total} pasos. Aporte factorial frente al mejor control por ID: {totals["gain"]} pasos en {totals["wins"]} IDs.',
               f'Detección: {totals["candidates"]} candidatos en {totals["pairs"]} pares de {totals["detected_ids"]} puzzles. Intentos B/C: {totals["B_attempts"]}/{totals["C_attempts"]}.',
               f'Totales por variante: '+', '.join(f'{a} {totals[a]}' for a in ARMS),
               'Aporte factorial por familia: '+', '.join(f'{f} {v}' for f,v in sorted(family_gain.items())),
               '[Detalle y sustituciones](reports/shared_factors_practice/comparison.csv) · [Programas](reports/shared_factors_practice/portfolio.csv)']
    journal(intro+summary+examples+['']+table,'factores-compartidos')
    print(*summary,sep='\n')


if __name__ == '__main__':
    main()
