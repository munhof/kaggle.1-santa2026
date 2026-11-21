"""Bounded single-value recipe substitutions between valid programs."""
from collections import Counter, deque

from elf_calculator.constructors.elf_baselines import ConstructionError, validate
from elf_calculator.optimizers.elf_a4 import _apply


def recipes(p, program):
    memory = list(p.starting_values) + [None] * (48 - len(p.starting_values))
    initial = set(p.starting_values)
    result = {}
    for op, i, j, dest in program:
        a, b = memory[i], memory[j]
        value = _apply(op, a, b)
        memory[dest] = value
        if value not in initial:
            result.setdefault(value, (op, a, b))
    return result


def ordered(initial, targets, graph):
    done = set(initial)
    active = set()
    order = []
    stack = [(v, False) for v in reversed(targets)]
    while stack:
        value, closing = stack.pop()
        if value in done:
            continue
        if closing:
            active.remove(value)
            done.add(value)
            order.append(value)
            continue
        if value in active:
            return None
        active.add(value)
        _, a, b = graph[value]
        stack.extend(((value, True), (b, False), (a, False)))
    return order


def allocate(p, graph, order):
    uses = Counter(x for v in order for x in graph[v][1:])
    regs = {v: i for i, v in enumerate(p.starting_values) if uses[v]}
    free = deque(sorted(set(range(48)) - set(regs.values())))
    program = []
    for v in order:
        op, a, b = graph[v]
        i, j = regs[a], regs[b]
        for operand in (a, b):
            uses[operand] -= 1
            if not uses[operand]:
                free.append(regs.pop(operand))
        if not free:
            return None
        dest = free.popleft()
        program.append([op, i, j, dest])
        if uses[v]:
            regs[v] = dest
        else:
            free.append(dest)
    return program


def candidates(p, base, donors):
    validate(p, base)
    own = recipes(p, base)
    initial = set(p.starting_values)
    live = ordered(initial, p.targets, own)
    uses = Counter(x for v in live for x in set(own[v][1:]))
    result = [base]
    for v in sorted(live, key=lambda x: -uses[x]):
        alternatives = []
        for donor in donors:
            if v not in donor or donor[v] == own[v]:
                continue
            additions = {v: donor[v]}
            stack = list(donor[v][1:])
            while stack:
                x = stack.pop()
                if x not in initial and x not in own and x not in additions:
                    additions[x] = donor[x]
                    stack.extend(donor[x][1:])
            if additions not in alternatives:
                alternatives.append(additions)
        for additions in sorted(alternatives, key=len):
            graph = own | additions
            order = ordered(initial, p.targets, graph)
            if order is None or len(order) > len(base) + 2:
                continue
            code = allocate(p, graph, order)
            if code is None or code in result:
                continue
            try:
                validate(p, code)
            except ConstructionError:
                continue
            result.append(code)
            if len(result) == 9:
                return result
    return result
