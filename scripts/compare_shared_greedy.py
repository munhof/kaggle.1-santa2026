"""Compare greedy shared-helper rankings on the frozen practice portfolio."""
import csv
import json
import multiprocessing
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from tempfile import mkdtemp

from scripts.compare_four import BOOK, DATA, ROOT, inverse, repair, verify
from elf_calculator.constructors.elf_baselines import Puzzle, validate
from elf_calculator.optimizers.elf_partial import allocate, ordered, recipes

MODES = ('coverage','saving')


def search(p, base, mode):
    best = base
    moves = []
    initial = set(p.starting_values)
    targets = set(p.targets) - initial
    for _ in range(8):
        graph = recipes(p,best)
        cones = {t:set(ordered(initial,[t],graph)) for t in targets}
        consumers = Counter(v for cone in cones.values() for v in cone)
        anchors = sorted(initial) + sorted(graph,key=lambda v:(-consumers[v],v))[:40]
        helpers = {v:None for v in anchors}
        for i,a in enumerate(anchors):
            for b in anchors[:i+1]:
                for h,r in ((a+b,('+',a,b)),(a*b,('*',a,b)),(abs(a-b),('-',max(a,b),min(a,b))),
                            (max(a,b)//min(a,b),('/',max(a,b),min(a,b))) if max(a,b)%min(a,b)==0 else (0,None)):
                    if 0<h<=p.value_limit:
                        helpers.setdefault(h,r)
        groups = defaultdict(dict)
        for t in sorted(targets):
            for a in anchors:
                if a==t or (a in cones and t in cones[a]):
                    continue
                for op,h,rev in inverse(t,a):
                    if h!=t and h in helpers:
                        r=(op,h,a) if rev else (op,a,h)
                        if r!=graph[t]:
                            groups[h].setdefault(t,r)
        def rank(item):
            h,patch=item
            support=len(patch)
            estimate=sum(sum(consumers[v]==1 for v in cones[t])-1 for t in patch)-(h not in graph and h not in initial)
            return (-support,-estimate,h) if mode=='coverage' else (-estimate,-support,h)
        for h,patch in sorted(groups.items(),key=rank)[:128]:
            updated=graph|patch
            if h not in graph and h not in initial:
                updated[h]=helpers[h]
            order=ordered(initial,p.targets,updated)
            if order is None or len(order)>=len(best):
                continue
            code=allocate(p,updated,order)
            if code is not None:
                validate(p,code)
                moves.append((len(patch),len(best)-len(code)))
                best=code
                break
        else:
            break
    return best,moves


def run(args):
    p,base=args
    results={}
    for mode in MODES:
        code,moves=search(p,base,mode)
        final,_=repair(p,code)
        validate(p,final)
        results[mode]=(final,moves,len(code))
    return p.id,base,results


def journal(lines, cell_id='greedy-compartido'):
    book=json.loads(BOOK.read_text())
    cell=next((c for c in book['cells'] if c['id']==cell_id),None)
    if cell is None:
        cell=dict(id=cell_id,cell_type='markdown',metadata={})
        book['cells'].append(cell)
    cell['source']='\n'.join(lines).splitlines(True)
    temp=BOOK.with_suffix('.tmp')
    temp.write_text(json.dumps(book,ensure_ascii=False,indent=1)+'\n')
    temp.replace(BOOK)


def main():
    baseline=ROOT/'reports/four_backward_practice/portfolio.csv'
    assert verify(DATA,baseline)==(200,36049)
    with baseline.open() as f:
        bases={r['id']:json.loads(r['program']) for r in csv.DictReader(f)}
    with DATA.open() as f:
        puzzles=list(map(Puzzle.from_dict,csv.DictReader(f)))
    out=Path(mkdtemp(prefix='shared_greedy_',dir=ROOT/'reports'))
    print(out,flush=True)
    header=['## Greedy por objetivos compartidos en práctica','',
            'Control: 36.049 pasos. Por ronda se construye el mismo banco a partir del estado actual. Hasta 8 rondas, 128 intentos por ronda y 40 intermedios más las semillas. Tras cada aceptación se regenera el banco. Cada orden termina con la misma reparación E4 (hasta 30 s).',
            '', '| ID | Control | Cobertura | Cobertura + E4 | Ahorro estimado | Ahorro estimado + E4 | Mejor |','|---|---:|---:|---:|---:|---:|---:|']
    journal(header)
    with (out/'portfolio.csv').open('w') as pf,(out/'comparison.csv').open('w') as cf,ProcessPoolExecutor(14,mp_context=multiprocessing.get_context('fork')) as pool:
        pw,cw=csv.writer(pf),csv.writer(cf)
        pw.writerow(['id','program'])
        cw.writerow(['id','historical','coverage','coverage_final','saving','saving_final','final','coverage_moves','saving_moves'])
        for k,base,results in pool.map(run,[(p,bases[p.id]) for p in puzzles]):
            best=min([base]+[x[0] for x in results.values()],key=len)
            row=[k,len(base)]
            for code,moves,size in results.values():
                row.extend([size,len(code)])
            row.append(len(best))
            pw.writerow([k,json.dumps(best,separators=(',',':'))])
            cw.writerow(row+[json.dumps(results[m][1]) for m in MODES])
            pf.flush()
            cf.flush()
            header.append('|'+'|'.join(map(str,row))+'|')
            journal(header)
    count,total=verify(DATA,out/'portfolio.csv')
    with (out/'comparison.csv').open() as f:
        rows=list(csv.DictReader(f))
    summary=[f'{count} programas reproducidos. Cartera: {total}. [Comparación]({out.relative_to(ROOT)}/comparison.csv)']
    for m in MODES:
        gains=Counter()
        for r in rows:
            for support,gain in json.loads(r[m+'_moves']):
                gains[min(support,3)]+=gain
        summary.append(f'{m}: {sum(int(r[m]) for r in rows)} antes de E4 y {sum(int(r[m+"_final"]) for r in rows)} después. Pasos ahorrados por movimientos con 1, 2 y 3+ objetivos: {gains[1]}, {gains[2]}, {gains[3]}.')
    journal(header[:3]+['']+summary+header[3:])
    print(*summary,sep='\n')

if __name__=='__main__':
    main()
