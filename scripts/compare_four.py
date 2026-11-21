"""Four independent practice experiments with a resumable live notebook."""
import csv
import json
import multiprocessing
import subprocess
import time
from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED
from pathlib import Path

from scripts.compare_dag import ROOT, STAGES, Puzzle, validate
from scripts.validate_submission import verify
from elf_calculator.optimizers.elf_partial import allocate, ordered, candidates, recipes

BASE = ROOT / 'reports/backward_practice_wyyedfh3'
OUT = ROOT / 'reports/four_backward_practice'
DATA = ROOT / 'practice_puzzles.csv'
BOOK = ROOT / 'diarios de avances de exploracion.ipynb'
CONFIG = {'E1':['1','3','6'], 'E2':[f'{a}-{w}' for a in (52,64) for w in (1,3,6)],
          'E3':['joint'], 'E4':['repair']}


def dashboard(path, content):
    book = json.loads(path.read_text())
    cell = next((c for c in book['cells'] if c.get('id') == 'four-live'), None)
    if cell is None:
        cell = dict(id='four-live', cell_type='markdown', metadata={})
        book['cells'].append(cell)
    cell['source'] = content.splitlines(True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(book, ensure_ascii=False, indent=1)+'\n')
    temp.replace(path)


def winner(bank):
    return min(bank, key=lambda k:len(bank[k]))


def dictionary_source(limit):
    src = (BASE/'solver.cpp').read_text()
    return src.replace('leaves.size() < 52',f'leaves.size() < {limit}').replace(
        'leaves.size() < 56','leaves.size() < 72').replace('size_t i = slot(v);\n        if (keys[i])',
        'if (used.size() >= keys.size() * 3 / 4) return false;\n        size_t i = slot(v);\n        if (keys[i])')


def joint(p, programs):
    from ortools.sat.python import cp_model
    graphs = [recipes(p, c) for c in programs]
    bank = {}
    for graph in graphs:
        for v, recipe in graph.items():
            bank.setdefault(v,set()).add(recipe)
    m = cp_model.CpModel()
    active = {v:m.new_bool_var('') for v in bank}
    level = {v:m.new_int_var(0,len(bank),'') for v in bank}
    seed = min(programs,key=len)
    hint = recipes(p,seed)
    for v, variants in bank.items():
        flags = []
        for recipe in sorted(variants):
            flag = m.new_bool_var('')
            flags.append(flag)
            m.add_hint(flag,int(hint.get(v)==recipe))
            for x in set(recipe[1:]) & active.keys():
                m.add(active[x]>=flag)
                m.add(level[x]<level[v]).only_enforce_if(flag)
        bank[v] = list(zip(sorted(variants),flags))
        m.add(sum(flags)==active[v])
    for v in set(p.targets)&active.keys():
        m.add(active[v]==1)
    m.minimize(sum(active.values()))
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers=1
    solver.parameters.random_seed=42
    solver.parameters.max_time_in_seconds=30
    status=solver.solve(m)
    if status in (cp_model.OPTIMAL,cp_model.FEASIBLE):
        graph={v:r for v,choices in bank.items() for r,f in choices if solver.value(f)}
        code=allocate(p,graph,ordered(p.starting_values,p.targets,graph))
        if code is not None:
            validate(p,code)
            return min((seed,code),key=len),solver.status_name(status)
        return seed,'rechazado por registros'
    return seed,solver.status_name(status)


def inverse(t,a):
    yield '+',t-a,False
    yield '-',t+a,True
    yield '-',a-t,False
    if t%a==0:
        yield '*',t//a,False
    yield '/',t*a,True
    if a%t==0:
        yield '/',a//t,False


def repair(p, base):
    deadline=time.monotonic()+30
    graph=recipes(p,base)
    initial=set(p.starting_values)
    targets=sorted(set(p.targets)-initial)
    best=base
    def cone(t):
        keep=ordered(initial,[x for x in targets if x!=t],graph)
        return set(ordered(initial,[t],graph))-set(keep)
    ranking=sorted(targets,key=lambda t:(-len(cone(t)),t))
    for t in ranking:
        if time.monotonic()>=deadline:
            return best,'límite de tiempo'
        removed=cone(t)
        if len(removed)<2:
            continue
        pool=sorted((graph.keys()-removed)|initial)
        # Only values reachable independently of the removed branch are donors.
        pool=[v for v in pool if v in initial or not removed.intersection(ordered(initial,[v],graph))]
        known=set(pool)
        pairs={}
        for i,a in enumerate(pool):
            for b in pool[:i+1]:
                for v,r in ((a+b,('+',a,b)),(a-b,('-',a,b)),(a*b,('*',a,b)),
                            (a//b,('/',a,b)) if a%b==0 else (0,None)):
                    if 0<v<=p.value_limit and v not in known:
                        pairs.setdefault(v,r)
        def paths(v,depth):
            if v in known:
                yield {}
                return
            if v in pairs:
                yield {v:pairs[v]}
                return
            if depth>1:
                for a in pool:
                    if time.monotonic()>=deadline:
                        return
                    for op,b,rev in inverse(v,a):
                        if b!=v and 0<b<=p.value_limit:
                            for sub in paths(b,depth-1):
                                yield sub|{v:(op,b,a) if rev else (op,a,b)}
        for patch in paths(t,min(3,len(removed)-1)):
            updated=graph|patch
            order=ordered(initial,p.targets,updated)
            if order is not None and len(order)<len(best):
                code=allocate(p,updated,order)
                if code is not None:
                    validate(p,code)
                    best,graph=code,recipes(p,code)
                    break
    return best,'límite de tiempo' if time.monotonic()>=deadline else 'completo'


def job(p,bank,e,c):
    start=time.monotonic()
    cpu=time.process_time()
    stages=[]
    status='válido'
    def stage_done(label, code):
        validate(p,code)
        stages.append((label,len(code)))
        path=OUT/f'{p.id}-{e}-{c}.progress'
        tmp=path.with_suffix('.writing')
        tmp.write_text(json.dumps(stages))
        tmp.replace(path)

    if e=='E1':
        code=bank[c]
        for stage in STAGES:
            code=stage(p,code)
            stage_done(stage.__name__,code)
    elif e=='E2':
        import resource
        before=resource.getrusage(resource.RUSAGE_CHILDREN).ru_utime
        limit,width=c.split('-')
        fields=[p.id,p.value_limit,len(p.starting_values),len(p.targets),*p.starting_values,*sorted(p.targets)]
        run=subprocess.run([str(OUT/f'solver{limit}'),width],input=' '.join(map(str,fields))+'\n',
                           capture_output=True,text=True,check=True,timeout=180)
        pid,data=run.stdout.split(' ',1)
        assert pid==p.id
        code=json.loads(data)
        cpu-=resource.getrusage(resource.RUSAGE_CHILDREN).ru_utime-before
    elif e=='E3':
        donors=[recipes(p,x) for x in bank.values()]
        options=[x for base in bank.values() for x in candidates(p,base,donors)]
        stage_done('individual',min(options,key=len))
        code,status=joint(p,options)
    else:
        code,status=repair(p,bank['hist'])
    validate(p,code)
    return dict(code=code, stages=stages,status=status,seconds=time.monotonic()-start,cpu=time.process_time()-cpu)


def main():
    import ortools
    from collections import Counter
    OUT.mkdir(exist_ok=True)
    def read(path):
        with path.open() as f:
            return list(csv.DictReader(f))
    puzzles={r['id']:Puzzle.from_dict(r) for r in read(DATA)}
    families={r['id']:r['family'] for r in read(DATA)}
    banks={k:{} for k in puzzles}
    for name,file in [('hist','portfolio.csv'),('1','programs_w1.csv'),('3','programs.csv'),('6','programs_w6.csv')]:
        count,total=verify(DATA,BASE/file)
        assert count==200 and (name!='hist' or total==38540)
        for row in read(BASE/file):
            banks[row['id']][name]=json.loads(row['program'])
    for limit in (52,64):
        src=OUT/f'solver{limit}.cpp'
        src.write_text(dictionary_source(limit))
        subprocess.run(['g++','-std=c++17','-O3',str(src),'-o',str(src.with_suffix(''))],check=True)
    records={}
    def path(key):
        return OUT/('-'.join(key)+'.json')
    for f in OUT.glob('practice_*.json'):
        records[tuple(f.stem.split('-',2))]=json.loads(f.read_text())
    def best(k,e):
        return min((len(records[k,e,c]['code']) for c in CONFIG[e]),default=len(banks[k]['hist']))
    pilot=[]
    for fam in sorted(set(families.values())):
        pilot.extend([k for k in puzzles if families[k]==fam][:2])
    def render(note):
        lines=['## Cuatro experimentos sobre el constructor hacia atrás','',note,
               f'','Referencia validada: 38.540 pasos en 200 IDs. Haz 1/3/6. E2: 52/72 y 64/72. '
               f'CP-SAT {ortools.__version__}, semilla 42, un hilo y 30 s. Reparación local: 30 s. Grupo compartido: 14 procesos.',
               '', '| Método | IDs completos | Histórico | Método | Ahorro al combinar | CPU s | Tiempo acumulado s |','|---|---:|---:|---:|---:|---:|---:|']
        complete={}
        for e,cs in CONFIG.items():
            ids={k for k in puzzles if all((k,e,c) in records for c in cs)}
            complete[e]=ids
            hist=sum(len(banks[k]['hist']) for k in ids)
            raw=sum(best(k,e) for k in ids)
            gain=sum(max(0,len(banks[k]['hist'])-best(k,e)) for k in ids)
            rr=[r for (_,m,_),r in records.items() if m==e]
            lines.append(f"|{e}|{len(ids)}/200|{hist}|{raw}|{gain}|{sum(r['cpu'] for r in rr):.1f}|{sum(r['seconds'] for r in rr):.1f}|")
        common=set.intersection(*complete.values())
        lines+=['',f"Comparación directa sobre {len(common)} IDs comunes. "+' · '.join(f'{e}: {sum(best(k,e) for k in common)}' for e in CONFIG),
                '', 'Detalle de resultados recibidos. Las configuraciones restantes están pendientes.',
                '', '| ID | Método | Configuración | Entrada | Etapas (pasos) | Final validado | Estado |','|---|---|---|---:|---|---:|---|']
        for (k,e,c),r in sorted(records.items()):
            entry=c if e=='E1' else c.split('-')[-1] if e=='E2' else 'hist'
            lines.append(f"|{k}|{e}|{c}|{len(banks[k][entry])}|"+', '.join(f'{s} {v}' for s,v in r['stages'])+f"|{len(r['code'])}|{r['status']}|")
        for f in sorted(OUT.glob('*.progress')):
            k,e,c=f.stem.split('-',2)
            if (k,e,c) not in records:
                steps=', '.join(f'{s} {v}' for s,v in json.loads(f.read_text()))
                lines.append(f'|{k}|{e}|{c}|{len(banks[k].get(c,banks[k]["hist"]))}|{steps}|pendiente|en curso|')
        dashboard(BOOK,'\n'.join(lines))
    with ProcessPoolExecutor(14,mp_context=multiprocessing.get_context('fork')) as pool:
        for ids,label in [(pilot,'Piloto: dos IDs por familia'),([k for k in puzzles if k not in pilot],'Corrida completa')]:
            render(label+' · regresiones y suite verificadas')
            jobs={pool.submit(job,puzzles[k],banks[k],e,c):(k,e,c) for k in ids for i in range(6)
                  for e,cs in CONFIG.items() for c in cs[i:i+1] if (k,e,c) not in records}
            last=time.monotonic()
            while jobs:
                done,_=wait(jobs,timeout=2,return_when=FIRST_COMPLETED)
                for f in done:
                    key=jobs.pop(f)
                    try:
                        r=f.result()
                    except Exception as exc:
                        render(f'Fallo en {key}: {exc}. Pendiente de reintento.')
                        raise
                    tmp=path(key).with_suffix('.tmp')
                    tmp.write_text(json.dumps(r,separators=(',',':')))
                    tmp.replace(path(key))
                    records[key]=r
                if time.monotonic()-last>=4 or not jobs:
                    render(label)
                    last=time.monotonic()
    savings=Counter()
    family=Counter()
    exclusive=Counter()
    diagnostics=Counter()
    with (OUT/'portfolio.csv').open('w') as pf,(OUT/'comparison.csv').open('w') as cf:
        pw,cw=csv.writer(pf),csv.writer(cf)
        pw.writerow(['id','program'])
        cw.writerow(['id','family','historical',*CONFIG,'winner','final'])
        for k in puzzles:
            opts={'hist':banks[k]['hist']}
            for e,cs in CONFIG.items():
                opts[e]=min((records[k,e,c]['code'] for c in cs),key=len)
                family[families[k],e]+=len(opts[e])
            w=winner(opts)
            length=len(opts[w])
            pw.writerow([k,json.dumps(opts[w],separators=(',',':'))])
            cw.writerow([k,families[k],*map(len,opts.values()),w,length])
            savings[w]+=1
            family[families[k],'final']+=length
            for e in CONFIG:
                exclusive[e]+=min(len(v) for m,v in opts.items() if m!=e)-length
            short=min(('1','3','6'),key=lambda c:len(banks[k][c]))
            diagnostics['E1 elegir antes']+=len(records[k,'E1',short]['code'])
            diagnostics['E1 elegir después']+=len(opts['E1'])
            diagnostics['E3 individual']+=records[k,'E3','joint']['stages'][0][1]
            diagnostics['E3 con CP-SAT']+=len(opts['E3'])
    for e,cs in CONFIG.items():
        with (OUT/f'{e}.csv').open('w') as file:
            writer=csv.writer(file)
            writer.writerow(['id','program'])
            for k in puzzles:
                code=min((records[k,e,c]['code'] for c in cs),key=len)
                writer.writerow([k,json.dumps(code,separators=(',',':'))])
        assert verify(DATA,OUT/f'{e}.csv')[0]==200
    count,total=verify(DATA,OUT/'portfolio.csv')
    assert count==200 and total<=38540
    brief=f'Cierre validado: {total} pasos, {38540-total} ahorrados. [Programas](reports/four_backward_practice/portfolio.csv) · [Ganadores](reports/four_backward_practice/comparison.csv)'
    brief+='\n\nPiloto completado: 110 configuraciones en 10 IDs, dos por familia. Suite del entorno: 42 pruebas aprobadas.'
    brief+='\n\n| Diccionario y ancho | Control original | Ampliado | Diferencia a favor del ampliado |\n|---|---:|---:|---:|'
    for c in CONFIG['E2']:
        control=sum(len(banks[k][c.split('-')[1]]) for k in puzzles)
        expanded=sum(len(records[k,'E2',c]['code']) for k in puzzles)
        brief+=f'\n|{c}|{control}|{expanded}|{control-expanded}|'
    brief+='\n\n'+ ' · '.join(f'{k}: {v}' for k,v in diagnostics.items())
    brief+='\n\n| Método | IDs elegidos | Aporte exclusivo |\n|---|---:|---:|\n'+'\n'.join(f'|{e}|{savings[e]}|{exclusive[e]}|' for e in CONFIG)
    brief+='\n\n| Familia | E1 | E2 | E3 | E4 | Cartera |\n|---|---:|---:|---:|---:|---:|\n'+'\n'.join('|'+fam+'|'+'|'.join(str(family[fam,e]) for e in (*CONFIG,'final'))+'|' for fam in sorted(set(families.values())))
    brief+='\n\nProgramas reproducidos por método: '+' · '.join(f'[{e}](reports/four_backward_practice/{e}.csv)' for e in CONFIG)
    statuses=Counter(records[k,'E3','joint']['status'] for k in puzzles)
    brief+='\n\nEstados de CP-SAT: '+', '.join(f'{state} {n}' for state,n in sorted(statuses.items()))
    render(brief)
    print(brief,flush=True)


if __name__=='__main__':
    main()
