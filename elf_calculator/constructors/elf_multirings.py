"""A3 bis: choose among rings defined by the distinct initial values.

For each ascending target, try each base on an isolated register/program state.
Commit the candidate using the fewest added instructions; ties prefer the
smaller base. This is a greedy choice for this target, not a global optimum.
Only committed instructions count. Previously emitted values are reusable
only while they remain in registers.
"""
from elf_calculator.constructors.elf_baselines import Builder, ConstructionError, Puzzle, _midpoint_toward


def _trial(current: Builder, target: int, base: int) -> Builder:
    """Construct one target without mutating the caller's state."""
    b = Builder(current.p)
    b.memory = current.memory.copy()
    b.program = current.program.copy()
    b.covered = current.covered.copy()
    pinned: set[int] = set()

    def emit(op: str, i: int, j: int, protected: set[int]) -> int:
        excluded = pinned | protected | {i, j}
        free = [k for k, value in enumerate(b.memory)
                if value is None and k not in excluded]
        available = free or [k for k in range(48) if k not in excluded]
        if not available:
            raise ConstructionError('No register available for multiple rings')
        destination = available[0]
        b.emit(op, i, j, destination)
        return destination

    if 1 in b.memory:
        one = b.memory.index(1)
    else:
        source = next(i for i, value in enumerate(b.memory) if value is not None)
        one = emit('/', source, source, set())
    pinned.add(one)
    if target in b.covered:
        return b

    def number(value: int, protected: set[int]) -> int:
        if value in b.memory:
            return b.memory.index(value)
        acc = one
        for bit in bin(value)[3:]:
            acc = emit('+', acc, acc, protected)
            if bit == '1':
                acc = emit('+', acc, one, protected)
        return acc

    two = number(2, set())
    pinned.add(two)
    base_reg = number(base, set())
    pinned.add(base_reg)
    if target in b.covered:
        return b

    low = max(1, (target // base) * base)
    high = min(b.p.value_limit, (target // base + 1) * base)

    def boundary(value: int, protected: set[int]) -> int:
        if value in b.memory:
            return b.memory.index(value)
        if value % base == 0:
            quotient = number(value // base, protected)
            return emit('*', quotient, base_reg, protected)
        return number(value, protected)

    left = boundary(low, set())
    if target in b.covered:
        return b
    right = boundary(high, {left})
    while target not in b.covered:
        mid = _midpoint_toward(low, high, target)
        protected = {left, right}
        if mid in b.memory:
            middle = b.memory.index(mid)
        else:
            delta = emit('-', right, left, protected)
            if (high - low) % 2:
                delta = emit('-', delta, one, protected)
            half = emit('/', delta, two, protected)
            middle = emit('+', left, half, protected)
            if mid > low + (high - low) // 2:
                middle = emit('+', middle, one, protected)
        if target == mid:
            break
        if target < mid:
            high, right = mid, middle
        else:
            low, left = mid, middle
    return b


def multirings(p: Puzzle) -> list:
    """Construct targets using the cheapest trial among initial-value bases."""
    b = Builder(p)
    bases = sorted(set(p.starting_values))
    for target in sorted(set(p.targets)):
        if target in b.covered:
            continue
        best = None
        errors = []
        for base in bases:
            try:
                candidate = _trial(b, target, base)
            except ConstructionError as exc:
                errors.append(str(exc))
                continue
            if best is None or len(candidate.program) < len(best.program):
                best = candidate
        if best is None:
            raise ConstructionError(
                f'No valid ring candidate for target {target}: ' + '; '.join(sorted(set(errors))))
        b = best
    return b.finish()
