"""Independent combination of initial-base trials and resident arithmetic reuse."""
from elf_calculator.constructors.elf_baselines import Builder, ConstructionError, Instruction, Puzzle, _midpoint_toward


def _trial(current: Builder, target: int, base: int) -> Builder:
    """Isolated reuse trial; preserve prior endpoints while constructing new ones."""
    p = current.p
    b = Builder(p)
    b.memory = current.memory.copy()
    b.program = current.program.copy()
    b.covered = current.covered.copy()
    if target in b.covered:
        return b
    pinned: set[int] = set()

    def slot(protected: set[int]) -> int:
        excluded = pinned | protected
        for i, value in enumerate(b.memory):
            if value is None and i not in excluded:
                return i
        for i in range(48):
            if i not in excluded:
                return i
        raise ConstructionError('No register available for bisection')

    def emit(op: str, i: int, j: int, protected: set[int]) -> int:
        a, c = b.memory[i], b.memory[j]
        value = {'+': lambda: a+c, '-': lambda: a-c,
                 '*': lambda: a*c, '/': lambda: a//c}[op]()
        if value in b.memory:
            return b.memory.index(value)
        d = slot(protected | {i, j})
        b.emit(op, i, j, d)
        return d

    if 1 in b.memory:
        one = b.memory.index(1)
    else:
        one = emit('/', 0, 0, set())
    pinned.add(one)

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
    ring_registers: set[int] = set(getattr(current, '_ring_registers', set()))

    def binary_cost(value: int) -> int:
        return value.bit_length() + value.bit_count() - 2

    for target in [target]:
        if target in b.covered:
            continue
        q = target // base
        low = max(1, q * base)
        high = min(p.value_limit, (q + 1) * base)
        # Build neighboring rings by exact multiplication of a constructed q.
        def boundary(value: int, protected: set[int]) -> int:
            if value in b.memory:
                return b.memory.index(value)
            # Prefer a one-instruction connection to any resident value.
            for i, available in enumerate(b.memory):
                if available is None or available >= value:
                    continue
                delta = value - available
                if delta in b.memory:
                    return emit('+', i, b.memory.index(delta), protected)
            if value % base == 0:
                q = value // base
                direct_cost = binary_cost(q) + 1
                candidates = [(binary_cost((value-v)//base) + 2, i, v)
                              for i, v in enumerate(b.memory)
                              if v is not None and v < value and v % base == 0]
                if candidates:
                    cost, i, v = min(candidates)
                    if cost < direct_cost:
                        gap = number((value-v)//base, protected | {i})
                        jump = emit('*', gap, base_reg, protected | {i})
                        return emit('+', i, jump, protected)
                quotient = number(q, protected)
                return emit('*', quotient, base_reg, protected)
            return number(value, protected)

        # Old endpoints survive construction of the new lower boundary.
        left = boundary(low, ring_registers)
        right = boundary(high, {left} | ring_registers)
        ring_registers = {left, right}
        while target not in b.covered:
            mid = _midpoint_toward(low, high, target)
            protected = {left, right} | ring_registers
            if mid in b.memory:
                middle = b.memory.index(mid)
            else:
                delta = emit('-', right, left, protected)
                if (high - low) % 2:
                    # Floor half-gap first; the final +1 implements ceil.
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
    b._ring_registers = ring_registers
    return b


def multirings_reuse(p: Puzzle) -> list:
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
