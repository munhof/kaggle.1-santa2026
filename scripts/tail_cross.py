"""Practice comparison of suffix replanning, cross recipes and register allocation."""
import csv
import json
import multiprocessing
import subprocess
import time
from collections import defaultdict, Counter, deque
from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED

from scripts.target_planner import ROOT, CONFIG, OUT as PLANS, source
from scripts.compare_four import DATA, Puzzle, verify, validate, STAGES
from scripts.compare_shared_greedy import journal, ordered, recipes
from elf_calculator.optimizers.elf_a4 import _apply

OUT=ROOT/'reports/tail_cross_practice'
BASE=ROOT/'reports/planner_polish/practice.csv'


def cuts(p,code,lengths):
    regs=list(p.starting_values)+[None]*(48-len(p.starting_values))
    missing=set(p.targets)-set(regs)
    events=[]
    for i,(op,a,b,d) in enumerate(code):
        v=_apply(op,regs[a],regs[b])
        if v in missing:
            events.append((i,regs.copy(),sorted(missing)))
            missing.remove(v)
        regs[d]=v
    return [event for i,event in enumerate(events) if i in {max(0,len(events)-n) for n in lengths}]


def victim(options,weighted):
    return min(options,key=lambda x: (x[1]**2/x[2] if weighted else -x[2],x[0]))[0]


def witness_order(p,code):
    regs=list(p.starting_values)+[None]*(48-len(p.starting_values))
    unseen=set(p.targets)-set(p.starting_values)
    seen=[]
    for op,a,b,d in code:
        regs[d]=_apply(op,regs[a],regs[b])
        if regs[d] in unseen:
            seen.append(regs[d])
            unseen.remove(regs[d])
    return seen


def compile_graph(entry,targets,graph,weighted,reorder):
    regs=entry.copy()
    initial=set(regs)-{None}
    goals=list(targets)
    if reorder:
        ready=initial.copy()
        sequence=[]
        while goals:
            _,t,sub=min((len(s),t,s) for t in goals for s in [ordered(ready,[t],graph)])
            sequence.extend(sub)
            ready.update(sub)
            goals.remove(t)
    else:
        sequence=ordered(initial,goals,graph)
    future=defaultdict(deque)
    for i,v in enumerate(sequence):
        for a in set(graph[v][1:]):
            future[a].append(i)
    code=[]
    def emit(v,locked):
        if v in regs: return regs.index(v)
        if v not in graph: raise ValueError('semilla desalojada')
        op,a,b=graph[v]
        ra=emit(a,locked)
        rb=emit(b,locked|{ra})
        if None in regs: dest=regs.index(None)
        else:
            opts=[]
            resident=set(regs)
            for j,x in enumerate(regs):
                if j in locked: continue
                # Preserve seeds or allow their last use in a prefix-filled bank.
                if x in initial and (len(initial)<48 or future[x]): continue
                distance=future[x][0]-i+1 if future[x] else float('inf')
                cost=1
                if weighted and future[x]:
                    try:
                        cost=len(ordered(resident-{x},[x],graph))
                    except KeyError:
                        continue
                opts.append((j,cost,distance))
            if not opts: raise ValueError('registros ocupados')
            dest=victim(opts,weighted)
        regs[dest]=v
        code.append([op,ra,rb,dest])
        return dest
    for i,v in enumerate(sequence):
        for x in set(graph[v][1:]): future[x].popleft()
        emit(v,set())
    return code,len(sequence)


def cross_recipes(bank,starts):
    vals=sorted(bank.keys()|set(starts))
    for i,a in enumerate(vals):
        for b in vals[:i+1]:
            for v,r in ((a+b,('+',a,b)),(a*b,('*',a,b)),(a-b,('-',a,b)),
                        (a//b,('/',a,b)) if a%b==0 else (0,None)):
                if v in bank and v not in (a,b): bank[v].add(r)


def joint_graph(p,donors,cross, *, seconds=30):
    from ortools.sat.python import cp_model
    bank=defaultdict(set)
    for donor in donors:
        for v,r in recipes(p,donor).items():bank[v].add(r)
    if cross: cross_recipes(bank,p.starting_values)
    model=cp_model.CpModel()
    hint=recipes(p,min(donors,key=len))
    active={v:model.new_bool_var('') for v in bank}
    level={v:model.new_int_var(0,len(bank),'') for v in bank}
    choices={}
    for v,rs in bank.items():
        choices[v]=[]
        for r in sorted(rs):
            f=model.new_bool_var('')
            choices[v].append((f,r))
            model.add_hint(f,int(hint.get(v)==r))
            for x in set(r[1:])&active.keys():
                model.add(active[x]>=f)
                model.add(level[x]<level[v]).only_enforce_if(f)
        model.add(sum(f for f,_ in choices[v])==active[v])
    for t in set(p.targets)&active.keys():model.add(active[t]==1)
    model.minimize(sum(active.values()))
    solver=cp_model.CpSolver()
    solver.parameters.num_search_workers=1
    solver.parameters.random_seed=42
    solver.parameters.max_time_in_seconds=seconds
    status=solver.solve(model)
    graph=None
    if status in (cp_model.FEASIBLE,cp_model.OPTIMAL):
        graph={v:r for v,rows in choices.items() for f,r in rows if solver.value(f)}
    return graph,solver.status_name(status)


def tail_source():
    s=source().replace('int capacity = 0','int first_rank=0; bool first=true; int capacity = 0')
    s=s.replace('Int selected=ranking.front().second;', 'Int selected=ranking[min(size_t(first && first_rank),ranking.size()-1)].second;')
    s=s.replace('pair<int,Int> best={INT_MAX,0};','vector<pair<int,Int>> scores;')
    s=s.replace('best=min(best,make_pair(objective(price,remaining),t));','scores.emplace_back(objective(price,remaining),t);')
    s=s.replace('selected=best.second;', 'sort(scores.begin(),scores.end());selected=scores[min(size_t(first && first_rank),scores.size()-1)].second;')
    s=s.replace('take(d,selected);','first=false; take(d,selected);')
    s=s.replace('p.capacity=stoi(argv[2]);','p.first_rank=stoi(argv[4]); p.capacity=stoi(argv[2]);')
    a=s.index('        auto prog = p.compile();')
    return s[:a]+'''        for(Int v:p.order){auto [a,b]=p.args.at(v);cout<<v<<" "<<p.defs.at(v).op<<" "<<a<<" "<<b<<"\\n";}
        cout<<"ORDER"; for(Int t:p.chosen) cout<<" "<<t; cout<<endl;
    }
}
'''


def unique(programs):
    return list({tuple(map(tuple,p)):p for p in programs}.values())


def experiment(p,base,donors,arm):
    start=time.monotonic()
    rows=[]
    pool=[base]
    def save():
        path=OUT/f'{p.id}-{arm}.progress'
        tmp=path.with_suffix('.tmp')
        tmp.write_text(json.dumps(rows));tmp.replace(path)
    def record(label,code=None,dag=None,status='válido'):
        if code is not None:
            validate(p,code)
            pool.append(code)
        rows.append([label,len(code) if code is not None else None,dag,status])
        save()
    entry=list(p.starting_values)+[None]*(48-len(p.starting_values))
    def allocate_all(label,graph,all_modes,targets=None):
        for w,o in ([(False,False),(True,False),(False,True),(True,True)] if all_modes else [(False,False)]):
            name=f'{label}/coste{int(w)}/orden{int(o)}'
            try: code,dag=compile_graph(entry,p.targets if targets is None else targets,graph,w,o)
            except ValueError as e: record(name,status=str(e));continue
            record(name,code,dag)
    if arm=='E1':
        for stop,regs,left in cuts(p,base,[6,8,10]):
            seeds=list(dict.fromkeys(x for x in regs if x is not None))
            fields=[p.id,p.value_limit,len(seeds),len(left),*seeds,*left]
            for pol in [1,2]:
                for rank in range(min(2,len(left))):
                    name=f'cola{len(left)}/pol{pol}/inicio{rank}'
                    proc=subprocess.run([OUT/'solver','6','128',str(pol),str(rank)],input=' '.join(map(str,fields)),text=True,capture_output=True,check=True)
                    graph={}
                    for line in proc.stdout.splitlines():
                        key,*data=line.split()
                        if key=='ORDER': order=list(map(int,data))
                        else: graph[int(key)]=(data[0],int(data[1]),int(data[2]))
                    try: tail,dag=compile_graph(regs,order,graph,False,False)
                    except ValueError as e: record(name,status=str(e));continue
                    record(name,base[:stop]+tail,dag)
    elif arm=='E3':
        for i,code in enumerate(donors):
            allocate_all(f'donante{i}',recipes(p,code),True,witness_order(p,code))
    else:
        pool.extend(donors)
        for cross in ([False,True] if arm=='E2' else [True]):
            graph,status=joint_graph(p,donors,cross)
            record('CP-SAT '+('cruzado' if cross else 'observado'),status=status)
            if graph is not None:allocate_all('CP '+str(cross),graph,arm=='Cruce')
        if arm=='Cruce': allocate_all('mejor independiente',recipes(p,min(donors,key=len)),True)
    raw=min(pool,key=len)
    best=raw
    ties=[]
    for code in unique(pool):
        for stage in STAGES:
            code=min((code,stage(p,code)),key=len)
        validate(p,code)
        if len(code)<len(best): best=code;ties=[]
        if len(code)==len(best):ties.append(code)
    return dict(raw=len(raw),code=best,ties=unique([best]+ties),rows=rows,seconds=time.monotonic()-start)


def main():
    OUT.mkdir(exist_ok=True)
    assert verify(DATA,BASE)==(200,32520)
    cpp=OUT/'tails.cpp'
    cpp.write_text(tail_source())
    subprocess.run(['g++','-std=c++17','-O3',cpp,'-o',OUT/'solver'],check=True)
    with DATA.open() as f: rows=list(csv.DictReader(f))
    with BASE.open() as f: base={r['id']:json.loads(r['program']) for r in csv.DictReader(f)}
    puzzles={r['id']:Puzzle.from_dict(r) for r in rows}
    families={r['id']:r['family'] for r in rows}
    pilot={k for fam in set(families.values()) for k in [i for i in puzzles if families[i]==fam][:2]}
    arms=['E1','E2','E3','Cruce']
    result={}
    live={}
    def render(note):
        text=['## Colas, recombinación y registros en práctica','',note,'','| Método | Completos | Histórico en esos IDs | Antes del pulido | Después | Segundos acumulados |','|---|---:|---:|---:|---:|---:|']
        for a in arms:
            keys=[k for k in puzzles if (k,a) in result]
            text.append(f"|{a}|{len(keys)}/200|{sum(len(base[k]) for k in keys)}|{sum(result[k,a]['raw'] for k in keys)}|{sum(len(result[k,a]['code']) for k in keys)}|{sum(result[k,a]['seconds'] for k in keys):.1f}|")
        ids=[k for k in puzzles if all((k,a) in result for a in arms[:3])]
        text+=['',f'Comparación directa, {len(ids)} IDs comunes: '+', '.join(f"{a} {sum(len(result[k,a]['code']) for k in ids)}" for a in arms[:3]),'','| ID | Familia | Método | Configuración | Pasos | Operaciones DAG | Estado |','|---|---|---|---|---:|---:|---|']
        for (k,a),entries in sorted(live.items()):
            for label,length,dag,status in entries:
                text.append(f"|{k}|{families[k]}|{a}|{label}|{length if length is not None else '—'}|{dag if dag is not None else '—'}|{status}|")
        journal(text,'colas-recetas-registros')
    for pilot_phase in (True,False):
        phase='Piloto de dos IDs por familia' if pilot_phase else 'Corrida completa'
        render(phase+' · referencia validada: 32.520')
        donors={}
        for k in puzzles:
            if (k in pilot)!=pilot_phase: continue
            donors[k]=unique([base[k]]+[json.loads((PLANS/f'{k}-{n}-{p}.json').read_text())['code'] for n,p in CONFIG])
        with ProcessPoolExecutor(14,mp_context=multiprocessing.get_context('fork')) as pool:
            jobs={}
            scheduled=set()
            def submit(k,a):
                if (k,a) in scheduled:return
                scheduled.add((k,a))
                path=OUT/f'{k}-{a}.json'
                if path.exists():
                    result[k,a]=json.loads(path.read_text())
                    live[k,a]=result[k,a]['rows']
                    return
                bank=donors[k]
                if a=='Cruce':
                    bank=unique(bank+[c for x in arms[:3] for c in result[k,x]['ties']])
                jobs[pool.submit(experiment,puzzles[k],base[k],bank,a)]=(k,a,path)
            for k in donors:
                for a in arms[:3]:submit(k,a)
                if all((k,a) in result for a in arms[:3]): submit(k,'Cruce')
            last=time.monotonic()
            while jobs:
                done,_=wait(jobs,timeout=2,return_when=FIRST_COMPLETED)
                for f in done:
                    k,a,path=jobs.pop(f)
                    try:r=f.result()
                    except Exception as exc:
                        render(f'Error en {k} {a}: {exc}')
                        raise
                    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(r,separators=(',',':')));tmp.replace(path)
                    result[k,a]=r;live[k,a]=r['rows']
                    if all((k,x) in result for x in arms[:3]):submit(k,'Cruce')
                if time.monotonic()-last>=5 or not jobs:
                    for path in OUT.glob('*.progress'):
                        k,a=path.stem.split('-')
                        if (k,a) not in result:live[k,a]=json.loads(path.read_text())
                    render(phase)
                    last=time.monotonic()
    stats=Counter()
    with (OUT/'portfolio.csv').open('w') as pf,(OUT/'comparison.csv').open('w') as cf:
        pw,cw=csv.writer(pf),csv.writer(cf)
        pw.writerow(['id','program'])
        cw.writerow(['id','family','baseline',*arms,'independent','final'])
        for k in puzzles:
            codes={a:result[k,a]['code'] for a in arms}
            independent=min([base[k]]+[codes[a] for a in arms[:3]],key=len)
            final=min((independent,codes['Cruce']),key=len)
            pw.writerow([k,json.dumps(final,separators=(',',':'))])
            cw.writerow([k,families[k],len(base[k]),*map(len,codes.values()),len(independent),len(final)])
            stats['independent_total']+=len(independent)
            stats[families[k]]+=len(base[k])-len(final)
            for a in arms[:3]:
                stats[a]+=min([len(base[k])]+[len(codes[x]) for x in arms[:3] if x!=a])-len(independent)
    count,total=verify(DATA,OUT/'portfolio.csv')
    note=f"{count} programas reproducidos: {total} pasos. Independientes: {stats['independent_total']}. Ahorro adicional del cruce: {stats['independent_total']-total}. [Detalle](reports/tail_cross_practice/comparison.csv) · [Programas](reports/tail_cross_practice/portfolio.csv)"
    note+='\n\nAporte exclusivo entre independientes: '+', '.join(f'{a} {stats[a]}' for a in arms[:3])
    note+='\n\nAhorro final por familia: '+', '.join(f'{fam} {stats[fam]}' for fam in sorted(set(families.values())))
    note+='\n\n| Método | IDs mejorados | Pasos ahorrados | Segundos acumulados por paso |\n|---|---:|---:|---:|'
    for a in arms:
        gains=[len(base[k])-len(result[k,a]['code']) for k in puzzles]
        saved=sum(gains)
        seconds=sum(result[k,a]['seconds'] for k in puzzles)
        cost=f'{seconds/saved:.1f}' if saved else '—'
        note+=f"\n|{a}|{sum(g>0 for g in gains)}|{saved}|{cost}|"
    note+='\n\n| Familia | Histórico | E1 | E2 | E3 | Cruce | Cartera |\n|---|---:|---:|---:|---:|---:|---:|'
    for fam in sorted(set(families.values())):
        ids=[k for k in puzzles if families[k]==fam]
        historical=sum(len(base[k]) for k in ids)
        values=[historical,*[sum(len(result[k,a]['code']) for k in ids) for a in arms],historical-stats[fam]]
        note+='\n|'+fam+'|'+'|'.join(map(str,values))+'|'
    observed=crossed=0
    for k in puzzles:
        counts={r[0]:r[1] for r in result[k,'E2']['rows']}
        first=min(len(base[k]),counts.get('CP False/coste0/orden0') or len(base[k]))
        observed+=first
        crossed+=min(first,counts.get('CP True/coste0/orden0') or first)
    note+=f'\n\nCP-SAT antes del pulido, conservando la referencia: {observed} pasos con recetas observadas y {crossed} al incorporar también las cruzadas.'
    render(note);print(note,flush=True)

if __name__=='__main__': main()
