"""A4 bounded checkpoint overshoot optimizer for valid programs."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from time import monotonic
from elf_calculator.constructors.elf_baselines import Puzzle, Instruction, validate

@dataclass
class A4Stats:
    before: int = 0
    after: int = 0
    candidates: int = 0
    invalid: int = 0
    accepted: int = 0
    lower: int = 0
    additive: int = 0
    division: int = 0
    mixed: int = 0
    elapsed: float = 0.0

def _apply(op, a, b):
    if op == '+': return a+b
    if op == '-': return a-b
    if op == '*': return a*b
    if b and a % b == 0: return a//b
    return None

def _state(p, program):
    mem=list(p.starting_values)+[None]*(48-len(p.starting_values))
    states=[mem.copy()]
    for op,i,j,d in program:
        v=_apply(op,mem[i],mem[j])
        if v is None or not 1<=v<=p.value_limit: raise ValueError('invalid source program')
        mem[d]=v; states.append(mem.copy())
    return states

def _pair(value, regs):
    for a, i in regs.items():
        if value % a == 0 and value//a in regs:
            return ['*', i, regs[value//a]]
        if value-a in regs:
            return ['+', i, regs[value-a]]
    return None


def _recipes(p, mem, target, dest, live, mode, cap, corrections, divisors, depth):
    regs = {v:i for i,v in enumerate(mem) if v is not None}
    small = sorted(regs)
    # One-step auxiliary constants are materialized only if the recipe needs them.
    aux = {v:_pair(v, regs) for v in range(1,min(8,p.value_limit)+1) if v not in regs}
    aux = {v:op for v,op in aux.items() if op}
    operands = small + sorted(aux)
    ds = [v for v in operands if v>1][:divisors]
    deltas = operands[:corrections]
    specs = []
    for delta in deltas:
        if mode in ('additive','all'):
            specs.append(('additive',target+delta, [('-',delta)]))
        if mode=='all':
            specs.append(('lower',target-delta, [('+',delta)]))
    if mode in ('division','all'):
        specs.extend(('division',target*d,[('/',d)]) for d in ds)
    if mode in ('mixed','all'):
        specs.extend(('mixed',(target+a)*d,[('/',d),('-',a)]) for a in deltas for d in ds)
    specs = [x for x in specs if 1<=x[1]<=p.value_limit]
    # Resident checkpoints first; prefer centers with a second reachable target.
    specs.sort(key=lambda x:(x[1] not in regs,
                             not any(t!=target and abs(t-x[1]) in regs for t in p.targets)))
    for family,c,tail in specs[:cap]:
        scratch = [i for i in reversed(range(48)) if i not in live and i!=dest and mem[i] is None]
        scratch += [i for i in reversed(range(48)) if i not in live and i!=dest and mem[i] is not None]
        local = regs.copy()
        steps = []
        # Protect every source used in the planned arithmetic.
        build = []
        if c not in regs:
            op = _pair(c,regs)
            if op:
                build = [op]
            elif depth>=2:
                for factor in small:
                    if factor>1 and c%factor==0:
                        op = _pair(c//factor,regs)
                        if op:
                            build = [op,['*',-1,regs[factor]]]
                            break
            if not build: continue
        missing = list(dict.fromkeys(v for _,v in tail if v not in regs))
        if len(build)+len(missing)>depth: continue
        protected = {r for instruction in build for r in instruction[1:]}
        protected.update(regs[v] for _,v in tail if v in regs)
        protected.update(r for v in missing for r in aux[v][1:])
        if c in regs: protected.add(regs[c])
        slots = [i for i in scratch if i not in protected]
        if len(slots)<len(missing)+bool(build)+(len(tail)>1): continue
        for v in missing:
            local[v] = slots.pop(0)
            steps.append(aux[v]+[local[v]])
        if build:
            checkpoint = slots.pop(0)
            for op,i,j in build:
                steps.append([op,checkpoint if i==-1 else i,j,checkpoint])
        else:
            checkpoint = regs[c]
        source = checkpoint
        for k,(op,v) in enumerate(tail):
            d = dest if k==len(tail)-1 else slots.pop(0)
            steps.append([op,source,local[v],d])
            source = d
        yield steps,family


def _candidates(p, mem, wanted, cap, max_corr):
    yield from _recipes(p,mem,wanted,47,set(),'all',cap,max_corr,12,2)


def optimize_a4(p, program, *, max_candidates=32, max_corrections=5, max_divisors=4,
                max_depth=2, max_window=8, max_iterations=2, time_budget=None,
                mode='all', return_stats=False):
    """Search target-ending windows; validate each proposed splice before committing."""
    start = monotonic()
    validate(p,program)
    result = program.copy()
    stats = A4Stats(before=len(program))
    if mode not in ('all','division','mixed','additive'):
        raise ValueError('unknown A4 mode')
    for iteration in range(max_iterations):
        states = _state(p,result)
        live = set()
        exits = {}
        for k in reversed(range(len(result))):
            _,i,j,d = result[k]
            if states[k+1][d] in p.targets:
                exits[k+1] = live.copy()
            live.discard(d)
            live.update((i,j))
        changed = False
        for hi in sorted(exits):
            if time_budget is not None and monotonic()-start>=time_budget: break
            live = exits[hi]
            dest = result[hi-1][3]
            goal = states[hi][dest]
            best = None
            for lo in range(max(0,hi-max_window),hi-1):
                if any(states[lo][r]!=states[hi][r] for r in live-{dest}): continue
                for seq,family in _recipes(p,states[lo],goal,dest,live,mode,max_candidates,max_corrections,max_divisors,max_depth):
                    stats.candidates += 1
                    gain = hi-lo-len(seq)
                    if gain<=0 or (best and gain<=best[0]): continue
                    trial = result[:lo]+seq+result[hi:]
                    try:
                        validate(p,trial)
                    except ValueError:
                        stats.invalid += 1
                        continue
                    best = gain,trial,family
            if best:
                _,result,family = best
                setattr(stats,family,getattr(stats,family)+1)
                stats.accepted += 1
                changed = True
                break
        if not changed: break
    stats.after = len(result)
    stats.elapsed = monotonic()-start
    return (result,dict(asdict(stats),saved=stats.before-stats.after)) if return_stats else result
