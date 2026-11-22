"""Target-order and virtual-register ablation, practice data only."""
import csv
import json
import subprocess
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path

from scripts.compare_pending import OLD
from scripts.compare_shared_greedy import DATA,ROOT,Puzzle,journal,validate,verify

OUT=ROOT/'reports/target_planner_practice'
BASE=ROOT/'reports/pending_dictionary_t1qgx25_/portfolio.csv'
CONFIG=[(n,p) for n in (0,48,128) for p in range(3)]


def source():
    s=(OLD/'solver52.cpp').read_text()
    begin=s.index('                Search s(d, width);')
    end=s.index('\n            }\n            done.insert',begin)
    block=s[begin:end]
    s=s[:begin]+'                build_target(d,target);'+s[end:]
    methods=(ROOT/'elf_calculator/constructors/target_planner.inc').read_text()
    s=s.replace('    void solve() {',f'void build_target(Dictionary &d,Int target) {{\n{block}\n}}\n{methods}\n    void solve() {{')
    s=s.replace('        map<Int, vector<int>> uses;', '        dag_steps=sequence.size();\n        map<Int, vector<int>> uses;')
    s=s.replace('    int width = argc', '''    if(argc==2 && string(argv[1])=="selftest"){
        if(Puzzle::objective(3,2)>=Puzzle::objective(1,10)) return 1;
        Puzzle p(20000,6); p.starts={1}; p.setup(); p.capacity=128; p.residents=p.starts;
        Puzzle copy=p; copy.binary(91); if(p.defs.count(91)) return 2;
        for(int v=50;v<110;++v){copy.binary(v);copy.load_value(v);copy.targets.push_back(v);}
        for(int v=50;v<110;++v){Int t=copy.make('*',v,v);copy.targets.push_back(t);}
        auto tape=copy.compile();
        if(copy.residents.size()<=48 || int(tape.size())<=copy.dag_steps) return 3;
        array<Int,48> regs{}; regs[0]=1; set<Int> seen{1};
        for(auto ins:tape){regs.at(ins[3])=apply(ins[0],regs.at(ins[1]),regs.at(ins[2]));seen.insert(regs[ins[3]]);}
        for(auto t:copy.targets) if(!seen.count(t)) return 4;
        return 0;
    }
    int width = argc''')
    s=s.replace('        p.solve();','''        p.capacity=stoi(argv[2]); int policy=stoi(argv[3]);
        if(!p.capacity && !policy){p.solve();p.chosen=p.targets;}
        else {p.plan(policy); if(p.capacity) p.targets=p.chosen;}
''').replace('        cout << id', '''        cerr<<p.dag_steps<<" "<<p.emitted;for(Int t:p.chosen)cerr<<" "<<t;cerr<<endl;
        cout << id''')
    return '#include <climits>\n'+s


def job(p,n,policy):
    start=time.monotonic()
    fields=[p.id,p.value_limit,len(p.starting_values),len(p.targets),*p.starting_values,*sorted(p.targets)]
    proc=subprocess.run([OUT/'solver','6',str(n),str(policy)],input=' '.join(map(str,fields)),capture_output=True,text=True,check=True)
    pid,cell=proc.stdout.split(' ',1)
    code=json.loads(cell)
    assert pid==p.id
    validate(p,code)
    if (n,policy)==(0,0):
        assert code==json.loads((OLD/f'{pid}-E2-52-6.json').read_text())['code']
    dag,virtual,*order=map(int,proc.stderr.split())
    return dict(code=code,dag=dag,virtual=virtual,order=order,seconds=time.monotonic()-start)


def main():
    OUT.mkdir(exist_ok=True)
    assert verify(DATA,BASE)==(200,35880)
    cpp=OUT/'solver.cpp'
    cpp.write_text(source())
    subprocess.run(['g++','-std=c++17','-O3',cpp,'-o',OUT/'solver'],check=True)
    with DATA.open() as f: rows=list(csv.DictReader(f))
    with BASE.open() as f: base={r['id']:json.loads(r['program']) for r in csv.DictReader(f)}
    pilot={k for family in {r['family'] for r in rows} for k in [r['id'] for r in rows if r['family']==family][:2]}
    details={}
    def render(note):
        lines=['## Orden de objetivos y registros virtuales en práctica','',note,'',
               'Políticas: 0 fija, 1 menor costo inmediato, 2 anticipación de seis. Capacidad 0: diccionario 52/72. Ancho 6 en todos los casos.',
               '', '| ID | Familia | Capacidad | Política | Pasos DAG | Operaciones virtuales | Reconstrucciones reales | Total validado | Segundos | Orden |','|---|---|---:|---:|---:|---:|---:|---:|---:|---|']
        for (k,n,p),r in sorted(details.items()):
            lines.append(f"|{k}|{families[k]}|{n}|{p}|{r['dag']}|{r['virtual']}|{len(r['code'])-r['dag']}|{len(r['code'])}|{r['seconds']:.2f}|"+', '.join(map(str,r['order']))+'|')
        journal(lines,'orden-y-registros')
    families={r['id']:r['family'] for r in rows}
    for phase in (True,False):
        label='Piloto' if phase else 'Corrida completa'
        render(label)
        with ThreadPoolExecutor(12) as pool:
            jobs={}
            for row in rows:
                p=Puzzle.from_dict(row)
                if (p.id in pilot)!=phase: continue
                for n,policy in CONFIG:
                    key=(p.id,n,policy)
                    path=OUT/f'{p.id}-{n}-{policy}.json'
                    if path.exists(): details[key]=json.loads(path.read_text())
                    else: jobs[pool.submit(job,p,n,policy)]=(key,path)
            last=time.monotonic()
            for f in as_completed(jobs):
                key,path=jobs[f]
                result=f.result()
                tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(result));tmp.replace(path)
                details[key]=result
                if time.monotonic()-last>3:
                    render(label);last=time.monotonic()
    stats=Counter()
    groups=Counter()
    with (OUT/'portfolio.csv').open('w') as pf,(OUT/'comparison.csv').open('w') as cf:
        pw,cw=csv.writer(pf),csv.writer(cf)
        pw.writerow(['id','program']);cw.writerow(['id','family','historical',*map(str,CONFIG),'winner','final'])
        for k,prior in base.items():
            codes={'hist':prior,**{c:details[k,*c]['code'] for c in CONFIG}}
            win=min(codes,key=lambda c:len(codes[c]))
            pw.writerow([k,json.dumps(codes[win],separators=(',',':'))])
            cw.writerow([k,families[k],*map(len,codes.values()),win,len(codes[win])])
            for c in CONFIG:
                stats[c,'total']+=len(codes[c])
                stats[c,'exclusive']+=min(len(v) for m,v in codes.items() if m!=c)-len(codes[win])
            groups[families[k]]+=len(prior)-len(codes[win])
    count,total=verify(DATA,OUT/'portfolio.csv')
    assert stats[(0,0),'total']==36281
    note=f'{count} programas validados: {total} pasos. Ahorro por familia: {dict(groups)}. [Comparación](reports/target_planner_practice/comparison.csv)\n\n| Capacidad, política | Total | Aporte exclusivo |\n|---|---:|---:|'
    for c in CONFIG: note+=f"\n|{c}|{stats[c,'total']}|{stats[c,'exclusive']}|"
    baseline_sum=sum(map(len,base.values()))
    note+=f"\n\nReferencia validada: {baseline_sum}. Ahorro final: {baseline_sum-total}. Empates a favor del histórico."
    note+="\n\n| Capacidad, política | IDs mejores que la cartera | Ahorro al añadirla sola | Segundos acumulados | Reconstrucciones reales |\n|---|---:|---:|---:|---:|"
    for c in CONFIG:
        saved=[len(base[k])-len(details[k,*c]['code']) for k in base]
        seconds=sum(details[k,*c]['seconds'] for k in base)
        rebuild=sum(len(details[k,*c]['code'])-details[k,*c]['dag'] for k in base)
        note+=f"\n|{c}|{sum(v>0 for v in saved)}|{sum(max(0,v) for v in saved)}|{seconds:.1f}|{rebuild}|"
    note+="\n\nTotales por familia. Cada columna usa la misma lista de IDs.\n\n| Familia | Histórico | "+" | ".join(map(str,CONFIG))+" | Cartera |\n|---|"+"---:|"*(2+len(CONFIG))
    for fam in sorted(groups):
        ids=[k for k in base if families[k]==fam]
        prev=sum(len(base[k]) for k in ids)
        values=[prev]+[sum(len(details[k,*c]['code']) for k in ids) for c in CONFIG]+[prev-groups[fam]]
        note+="\n|"+fam+"|"+"|".join(map(str,values))+"|"
    peak=OUT/'pilot_memory.txt'
    if peak.exists():
        note+="\n\nMuestra del piloto: "+peak.read_text()
    render(note);print(note,flush=True)

if __name__=='__main__': main()
