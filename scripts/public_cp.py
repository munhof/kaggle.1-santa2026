"""Cross GoodPJW's published programs with our scored portfolio and polish locally."""
import argparse
import csv
import hashlib
import json
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import get_context

from scripts.compare_factors import run as factor_search
from scripts.tail_cross import (
    ROOT, Puzzle, STAGES, compile_graph, joint_graph, journal, unique, validate, verify,
)

PUBLIC = ROOT/'reports/public_frontier_scored/goodpjw.csv'
LOCAL = ROOT/'artifacts/submission_shared_factors_156294.csv'
DATA = ROOT/'puzzles.csv'
OUT = ROOT/'reports/public_cp_scored'
SOURCE = 'https://www.kaggle.com/datasets/goodpjw2008/santa-2026-dag-lns-programs/versions/169'


def improve(p, public, local, seconds):
    seed = min((public, local), key=len)
    graph, status = joint_graph(p, [public,local], True, seconds=seconds)
    entry = list(p.starting_values) + [None]*(48-len(p.starting_values))
    programs = [seed]
    if graph is not None:
        for weighted in (False, True):
            for reorder in (False, True):
                try:
                    code,_ = compile_graph(entry,p.targets,graph,weighted,reorder)
                except ValueError:
                    continue
                validate(p,code)
                programs.append(code)
    cp = min(map(len, programs))
    best = min(programs,key=len)
    for code in unique(programs):
        for stage in STAGES:
            code = stage(p,code)
        validate(p,code)
        if len(code)<len(best):
            best = code
    return best, dict(public=len(public),local=len(local),status=status,
                      dag=len(graph) if graph is not None else None,
                      allocations=len(programs)-1,cp=cp,polished=len(best),final=len(best))


def job(row, public, local, seconds):
    p = Puzzle.from_dict(row)
    code, stats = improve(p, public, local, seconds)
    # The previous experiment already applied these passes to the frozen seed.
    if code != public:
        while True:
            options,*_ = factor_search(row, code)
            winner = min([code]+[v[1] for v in options.values()],key=len)
            if len(winner)==len(code):
                break
            code = winner
    stats['final'] = validate(p,code)['steps']
    return p.id,code,stats


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds',type=float,default=6,help='CP-SAT wall time per puzzle')
    parser.add_argument('--workers',type=int,default=14)
    args = parser.parse_args()
    if not args.seconds>0 or args.workers<1:
        parser.error('Los límites deben ser positivos')
    assert hashlib.sha256(PUBLIC.read_bytes()).hexdigest()=='1eb0f68e1a4fe978ff7e4d9c61165eae6ac42ce921f30d29bd47ffa3639bcf57'
    inputs = []
    for path,total in ((PUBLIC,130922),(LOCAL,156294)):
        assert verify(DATA,path)==(1000,total)
        with path.open() as f:
            inputs.append({r['id']:json.loads(r['program']) for r in csv.DictReader(f)})
    with DATA.open() as f:
        rows = list(csv.DictReader(f))
    OUT.mkdir(exist_ok=True)
    heading = ['## CP-SAT cruzado sobre GoodPJW y la cartera propia','',
               f'[GoodPJW v169]({SOURCE}), Apache 2.0, 130.922 pasos. Donante propio: 156.294 pasos. CP-SAT dispone de {args.seconds:g} segundos por puzzle, un hilo por modelo y cuatro estrategias de asignación. Las columnas muestran el mejor programa conservado en cada etapa.','']
    table = ['| ID | Pública | CP-SAT | Pulido | Final | Estado CP-SAT |',
             '|---|---:|---:|---:|---:|---|']
    journal(heading+table,'public-cp-scored')
    totals = Counter()
    statuses = Counter()
    winners = {}
    with ProcessPoolExecutor(args.workers,mp_context=get_context('fork')) as pool, (OUT/'comparison.csv').open('w') as report:
        jobs = [pool.submit(job,r,inputs[0][r['id']],inputs[1][r['id']],args.seconds) for r in rows]
        writer = csv.DictWriter(report,fieldnames=['id','public','local','status','dag','allocations','cp','polished','final'])
        writer.writeheader()
        for future in as_completed(jobs):
            pid,code,s = future.result()
            winners[pid] = code
            writer.writerow(dict(id=pid,**s))
            statuses[s['status']] += 1
            for key in ('public','cp','polished','final'):
                totals[key] += s[key]
            totals['wins'] += s['final']<s['public']
            table.append(f"|{pid}|{s['public']}|{s['cp']}|{s['polished']}|{s['final']}|{s['status']}|")
            if len(winners)%20==0:
                note = f"{len(winners)}/1000 procesados. Ahorro: {totals['public']-totals['final']} pasos en {totals['wins']} IDs."
                report.flush()
                journal(heading+[note,'']+table,'public-cp-scored')
                print(note,flush=True)
    path = ROOT/f"artifacts/submission_goodpjw_cp_{totals['final']}.csv"
    tmp = path.with_suffix('.tmp')
    with tmp.open('w') as f:
        writer = csv.writer(f)
        writer.writerow(['id','program'])
        writer.writerows((r['id'],json.dumps(winners[r['id']],separators=(',',':'))) for r in rows)
    assert verify(DATA,tmp)==(1000,totals['final'])
    tmp.replace(path)
    summary = (f"1.000 programas validados. CP-SAT {totals['cp']}, pulido {totals['polished']}, "
               f"final {totals['final']}. Ahorro de {130922-totals['final']} pasos en {totals['wins']} IDs.")
    journal(heading+[summary,str(dict(statuses)),f'[Entrega]({path.relative_to(ROOT)}) · [Detalle](reports/public_cp_scored/comparison.csv)','']+table,'public-cp-scored')
    print(summary,dict(statuses),flush=True)


if __name__=='__main__':
    main()
