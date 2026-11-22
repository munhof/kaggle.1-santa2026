"""Choose up to four shared helpers before rewriting the reachable target graph."""
from collections import Counter, defaultdict
from itertools import combinations
from scripts.compare_four import allocate, inverse, ordered, recipes, validate


def operations(a,b,limit):
    hi,lo=max(a,b),min(a,b)
    for v,rule in ((a+b,('+',a,b)),(a*b,('*',a,b)),(hi-lo,('-',hi,lo)),
                   (hi//lo if hi%lo==0 else 0,('/',hi,lo))):
        if 0<v<=limit:
            yield v,rule


def rebuild(p,base):
    graph=recipes(p,base)
    roots=set(p.starting_values)
    goals=sorted(set(p.targets)-roots)
    cones={t:set(ordered(roots,[t],graph)) for t in goals}
    support=Counter(v for cone in cones.values() for v in cone)
    best=base
    stats=dict(sets=0,allocated=0,helpers=[],targets=0,bare=len(base),single=len(base))
    original_order=ordered(roots,goals,graph)
    if len(original_order)<len(base) and allocate(p,graph,original_order) is not None:
        stats['bare']=len(original_order)
        stats['single']=len(original_order)
    if len(goals)<2:
        return best,stats
    ancestry={v:set(ordered(roots,[v],graph)) for v in graph}
    common=sorted(graph.keys()-set(goals),key=lambda v:(-support[v]/len(ancestry[v]),v))
    for width in (0,12,28):
        anchors=sorted(roots|set(common[:width]))
        frozen=set(ordered(roots,anchors,graph))
        build={}
        for i,a in enumerate(anchors):
            for b in anchors[:i+1]:
                for v,r in operations(a,b,p.value_limit):
                    if v not in roots and v not in frozen and v not in goals:
                        build.setdefault(v,r)
        offers=defaultdict(dict)
        for v in graph.keys()-frozen:
            for a in anchors:
                for op,h,rev in inverse(v,a):
                    if h in build and h!=v:
                        offers[h].setdefault(v,(op,h,a) if rev else (op,a,h))
        def potential(h):
            return sum(1+min(6,len(ancestry[v]-frozen)) for v in offers[h])
        helpers=sorted(offers,key=lambda h:(-potential(h),h))[:12]
        if len(helpers)<2:
            continue

        def attempt(group):
            nonlocal best
            patch={}
            for h in group:
                patch.update(offers[h])
            for a,b in combinations(group,2):
                for v,r in operations(a,b,p.value_limit):
                    if v in graph and v not in frozen:
                        patch.setdefault(v,r)
            patch.update((h,build[h]) for h in group)
            updated=graph|patch
            seq=ordered(roots,goals,updated)
            if len(group)>1:
                stats['sets']+=1
            if seq is None:
                return len(base)+1
            n=len(seq)
            if len(group)==1:
                if n<stats['single'] and allocate(p,updated,seq) is not None:
                    stats['single']=n
                return n
            if n<len(best):
                code=allocate(p,updated,seq)
                if code is not None:
                    validate(p,code)
                    best=code
                    stats['allocated']+=1
                    live=set(seq)
                    stats['helpers']=[h for h in group if h in live]
                    changed={v for v in live if updated[v]!=graph.get(v)}
                    stats['targets']=sum(bool(changed.intersection(ordered(roots,[t],updated))) for t in goals)
            return n

        for h in helpers:
            attempt((h,))
        groups=list(combinations(helpers,2))
        for size in (2,3,4):
            ranking=sorted((attempt(g),g) for g in groups)
            if size<4:
                groups=sorted({tuple(sorted((*g,h))) for _,g in ranking[:4]
                               for h in helpers if h not in g})
    return best,stats
