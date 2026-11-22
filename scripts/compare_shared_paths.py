"""Target-guided search for a shared arithmetic chain up to three steps long."""
import csv
import json
import multiprocessing
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from tempfile import mkdtemp

from scripts.compare_shared_greedy import DATA, ROOT, Puzzle, inverse, journal, ordered, allocate, recipes, repair, validate, verify


def chain(value, anchors, one, depth, limit):
    if value in one:
        return {value:one[value]}
    if depth < 2:
        return None
    for a in anchors:
        for op,b,rev in inverse(value,a):
            if 0 < b <= limit and b != value and b not in anchors:
                prefix = chain(b,anchors,one,depth-1,limit)
                if prefix and value not in prefix:
                    prefix[value] = (op,b,a) if rev else (op,a,b)
                    return prefix
    return None


def optimize(p,base,depth):
    best=base
    moves=[]
    for _ in range(4):
        graph=recipes(p,best)
        initial=set(p.starting_values)
        targets=sorted(set(p.targets)-initial)
        uses=Counter(v for t in targets for v in ordered(initial,[t],graph))
        anchors=sorted(initial)+sorted(graph,key=lambda v:(-uses[v],v))[:24]
        one={}
        for i,a in enumerate(anchors):
            for b in anchors[:i+1]:
                hi,lo=max(a,b),min(a,b)
                for v,r in ((a+b,('+',a,b)),(a*b,('*',a,b)),(hi-lo,('-',hi,lo)),
                            (hi//lo if hi%lo==0 else 0,('/',hi,lo))):
                    if 0<v<=p.value_limit and v not in graph and v not in initial:
                        one.setdefault(v,r)
        groups=defaultdict(dict)
        for t in targets:
            for a in anchors:
                if a==t:
                    continue
                for op,h,rev in inverse(t,a):
                    if 0<h<=p.value_limit and h not in graph and h not in initial:
                        groups[h].setdefault(t,(op,h,a) if rev else (op,a,h))
        found=False
        ranked=sorted((h for h,g in groups.items() if len(g)>=2),key=lambda h:(-len(groups[h]),h))
        for h in ranked[:48]:
            for d in range(1,depth+1):
                patch=chain(h,anchors,one,d,p.value_limit)
                if patch:
                    break
            if not patch or set(patch)&graph.keys():
                continue
            updated=graph|patch|groups[h]
            order=ordered(initial,p.targets,updated)
            if order is None or len(order)>=len(best):
                continue
            code=allocate(p,updated,order)
            if code is not None:
                validate(p,code)
                moves.append((len(patch),len(groups[h]),len(best)-len(code)))
                best=code
                found=True
                break
        if not found:
            break
    return best,moves


def run(args):
    p,base=args
    results=[]
    polished={}
    for depth in range(4):
        raw,moves=optimize(p,base,depth) if depth else (base,[])
        key=tuple(map(tuple,raw))
        if key not in polished:
            final,_=repair(p,raw)
            validate(p,final)
            polished[key]=final
        results.append((len(raw),polished[key],moves))
    return p.id,results


def main():
    baseline=ROOT/'reports/shared_greedy_vfo65a3a/portfolio.csv'
    assert verify(DATA,baseline)==(200,35938)
    with baseline.open() as f:
        bases={r['id']:json.loads(r['program']) for r in csv.DictReader(f)}
    with DATA.open() as f:
        puzzles=list(map(Puzzle.from_dict,csv.DictReader(f)))
    out=Path(mkdtemp(prefix='shared_paths_',dir=ROOT/'reports'))
    print(out,flush=True)
    intro=['## Caminos compartidos de hasta tres operaciones','',
           'Control: 35.938 pasos. Se busca un valor nuevo útil a dos o más objetivos. Cada eslabón combina el anterior con un ancla. Mismos límites por variante: semillas + 24 intermedios, 48 valores compartidos por ronda, hasta 4 rondas. Orden por cobertura decreciente. Cada columna muestra antes/después de E4.']
    rows=['| ID | Control | Hasta 1 | Hasta 2 | Hasta 3 | Mejor |','|---|---:|---:|---:|---:|---:|']
    sums=Counter()
    with (out/'comparison.csv').open('w') as cf,(out/'portfolio.csv').open('w') as pf,ProcessPoolExecutor(14,mp_context=multiprocessing.get_context('fork')) as pool:
        cw,pw=csv.writer(cf),csv.writer(pf)
        cw.writerow(['id','depth','before_e4','after_e4','moves'])
        pw.writerow(['id','program'])
        for k,results in pool.map(run,[(p,bases[p.id]) for p in puzzles]):
            best=min([bases[k]]+[r[1] for r in results],key=len)
            pw.writerow([k,json.dumps(best,separators=(',',':'))])
            for d,(raw,code,moves) in enumerate(results):
                cw.writerow([k,d,raw,len(code),json.dumps(moves)])
                sums[d,0]+=raw
                sums[d,1]+=len(code)
            cf.flush()
            pf.flush()
            rows.append('|'+k+'|'+'|'.join(f'{n}/{len(c)}' for n,c,_ in results)+f'|{len(best)}|')
            journal(intro+['']+rows,'caminos-compartidos')
    count,total=verify(DATA,out/'portfolio.csv')
    summary=[f'{count} programas reproducidos: {total} pasos. [Comparación por ID]({out.relative_to(ROOT)}/comparison.csv)']+[f'Profundidad {d}: {sums[d,0]} antes de E4, {sums[d,1]} después.' for d in range(4)]
    journal(intro+['']+summary+['']+rows,'caminos-compartidos')
    print(*summary,sep='\n')


if __name__=='__main__':
    main()
