"""Match target differences against pairs of positive, available offsets."""
import csv
import json
import multiprocessing
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from tempfile import mkdtemp

from scripts.compare_shared_paths import DATA, ROOT, Puzzle, allocate, inverse, journal, ordered, recipes, validate, verify


def optimize(p, base):
    best = base
    moves = []
    initial = set(p.starting_values)
    targets = sorted(set(p.targets) - initial)
    for _ in range(4):
        graph = recipes(p, best)
        available = initial | graph.keys()
        # For lo = h-a and hi = h+b, b is determined once a is chosen.
        meetings = []
        for i, lo in enumerate(targets):
            for hi in targets[i+1:]:
                for a in sorted(available):
                    b = hi-lo-a
                    if b in available and lo not in (a,b) and hi not in (a,b):
                        meetings.append((lo+a,lo,hi,a,b))
        if not meetings:
            break
        values = sorted(available)
        one = {}
        for i, x in enumerate(values):
            for y in values[:i+1]:
                for v,r in ((x+y,('+',x,y)),(x-y,('-',x,y)),(x*y,('*',x,y)),
                            (x//y,('/',x,y)) if x%y==0 else (0,None)):
                    if 0<v<=p.value_limit and v not in available:
                        one.setdefault(v,r)
        next_best = best
        selected = None
        for h,lo,hi,a,b in meetings:
            patch = {lo:('-',h,a),hi:('+',h,b)}
            builds = []
            if h in available:
                builds.append({})
            else:
                if h in one:
                    builds.append({h:one[h]})
                for x in values:
                    for op,y,rev in inverse(h,x):
                        if y in one and y!=h and x not in (lo,hi) and not ({lo,hi} & set(one[y][1:])):
                            builds.append({y:one[y],h:(op,y,x) if rev else (op,x,y)})
                            if len(builds)>=8:
                                break
                    if len(builds)>=8:
                        break
            for build in builds:
                updated = graph | build | patch
                order = ordered(initial,p.targets,updated)
                if order is None or len(order)>=len(next_best):
                    continue
                code = allocate(p,updated,order)
                if code is not None:
                    validate(p,code)
                    next_best = code
                    selected = (lo,hi,h,a,b,len(best)-len(code))
        if selected is None:
            break
        moves.append(selected)
        best = next_best
    return best,moves


def run(args):
    p,base = args
    code,moves = optimize(p,base)
    return p.id,len(base),code,moves


def main():
    baseline=ROOT/'reports/shared_paths_4haiz295/portfolio.csv'
    assert verify(DATA,baseline)==(200,35935)
    with baseline.open() as f:
        bases={r['id']:json.loads(r['program']) for r in csv.DictReader(f)}
    with DATA.open() as f:
        puzzles=list(map(Puzzle.from_dict,csv.DictReader(f)))
    out=Path(mkdtemp(prefix='offsets_',dir=ROOT/'reports'))
    print(out,flush=True)
    lines=['## Diferencias de objetivos y punto de encuentro','',
           'Base: 35.935 pasos. Hasta cuatro sustituciones estrictas por puzzle; centro disponible o construido en una o dos operaciones. Solo práctica, sin E4 adicional.',
           '', '| ID | Antes | Después | Ahorro |','|---|---:|---:|---:|']
    wins=0
    with (out/'comparison.csv').open('w') as cf,(out/'portfolio.csv').open('w') as pf,ProcessPoolExecutor(14,mp_context=multiprocessing.get_context('fork')) as pool:
        cw,pw=csv.writer(cf),csv.writer(pf)
        cw.writerow(['id','before','after','moves_lo_hi_center_offsets_gain'])
        pw.writerow(['id','program'])
        for k,n,code,moves in pool.map(run,[(p,bases[p.id]) for p in puzzles]):
            pw.writerow([k,json.dumps(code,separators=(',',':'))])
            cw.writerow([k,n,len(code),json.dumps(moves)])
            wins+=len(code)<n
            lines.append(f'|{k}|{n}|{len(code)}|{n-len(code)}|')
            journal(lines,'diferencias-objetivos')
    count,total=verify(DATA,out/'portfolio.csv')
    summary=f'{count} programas validados, {total} pasos; {wins} IDs mejorados. [Movimientos por ID]({out.relative_to(ROOT)}/comparison.csv)'
    journal(lines[:3]+['',summary]+lines[3:],'diferencias-objetivos')
    print(summary)


if __name__=='__main__':
    main()
