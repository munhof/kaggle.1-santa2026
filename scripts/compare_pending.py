"""Practice ablation of dictionary leaf selection at width six."""
import csv
import json
import subprocess
import multiprocessing
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from tempfile import mkdtemp

from scripts.compare_shared_greedy import ROOT,DATA,Puzzle,journal,validate,verify

OLD=ROOT/'reports/four_backward_practice'
MODES=('utility','mixed')
LOOP='''                for (auto it = order.rbegin(); it != order.rend() && leaves.size() < 72; ++it)
                    add(*it);'''
SELECT='''                vector<Int> recent, pending;
                for (auto it = order.rbegin(); it != order.rend(); ++it)
                    if (!used.count(*it)) recent.push_back(*it);
                for (Int t : targets)
                    if (!defs.count(t)) pending.push_back(t);
                auto ranked = rank_pending(recent, leaves, pending);
                const auto quota = (72 - leaves.size()) / 2;
                if (MIXED) {
                    for (size_t i=0; i<min(quota,recent.size()); ++i) add(recent[i]);
                }
                for (Int v : ranked) {
                    if (leaves.size() >= 72) break;
                    add(v);
                }'''


def run(args):
    p,base,out=args
    control=json.loads((OLD/f'{p.id}-E2-52-6.json').read_text())['code']
    programs=[base,control]
    fields=[p.id,p.value_limit,len(p.starting_values),len(p.targets),*p.starting_values,*sorted(p.targets)]
    for mode in MODES:
        result=subprocess.run([out/mode,'6'],input=' '.join(map(str,fields))+'\n',
                              text=True,capture_output=True,check=True,timeout=240)
        k,cell=result.stdout.split(' ',1)
        assert k==p.id
        programs.append(json.loads(cell))
    for program in programs:
        validate(p,program)
    return p.id,programs


def main():
    baseline=ROOT/'reports/repolish_rkbtk2g8/portfolio.csv'
    assert verify(DATA,baseline)==(200,35882)
    out=Path(mkdtemp(prefix='pending_dictionary_',dir=ROOT/'reports'))
    print(out,flush=True)
    src=(OLD/'solver52.cpp').read_text()
    assert src.count(LOOP)==1
    for mode in MODES:
        file=out/f'{mode}.cpp'
        file.write_text('#include "pending_dictionary.hpp"\n'+src.replace(LOOP,SELECT.replace('MIXED',str(mode=='mixed').lower())))
        subprocess.run(['g++','-O3','-std=c++17','-I',ROOT/'elf_calculator/constructors',file,'-o',out/mode],check=True)
    with baseline.open() as f:
        bank={r['id']:json.loads(r['program']) for r in csv.DictReader(f)}
    with DATA.open() as f:
        puzzles=list(map(Puzzle.from_dict,csv.DictReader(f)))
    lines=['## Elegir intermedios por utilidad para objetivos pendientes','',
           'Control guardado 52/72, ancho 6. Utilidad cuenta objetivos distintos alcanzables con una operación o producto con resto firmado usando hojas fijas. Empates por recencia. Mixta reserva la mitad de los lugares libres para los recientes.','','| ID | Cartera previa | Recencia | Utilidad | Mixta | Final |','|---|---:|---:|---:|---:|---:|']
    sums=[0]*5
    wins=[0]*2
    with (out/'portfolio.csv').open('w') as pf,(out/'comparison.csv').open('w') as cf,ProcessPoolExecutor(14,mp_context=multiprocessing.get_context('fork')) as pool:
        pw,cw=csv.writer(pf),csv.writer(cf)
        pw.writerow(['id','program'])
        cw.writerow(['id','baseline','recent','utility','mixed','final'])
        for k,programs in pool.map(run,[(p,bank[p.id],out) for p in puzzles]):
            best=min(programs,key=len)
            sizes=[*map(len,programs),len(best)]
            sums=[s+x for s,x in zip(sums,sizes)]
            wins=[v+(sizes[i+2]<sizes[0]) for i,v in enumerate(wins)]
            pw.writerow([k,json.dumps(best,separators=(',',':'))])
            cw.writerow([k,*sizes])
            pf.flush()
            cf.flush()
            lines.append('|'+k+'|'+'|'.join(map(str,sizes))+'|')
            journal(lines,'seleccion-intermedios')
    assert verify(DATA,out/'portfolio.csv')==(200,sums[-1])
    note=f'Totales en orden: {sums}. IDs que mejoran la cartera por variante: {wins}. [Detalle]({out.relative_to(ROOT)}/comparison.csv)'
    journal(lines[:3]+['',note]+lines[3:],'seleccion-intermedios')
    print(note)

if __name__=='__main__':
    main()
