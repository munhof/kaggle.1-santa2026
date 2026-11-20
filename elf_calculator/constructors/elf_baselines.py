"""Santa 2026: three independent, deliberately simple arithmetic constructors.

Does not read competition CSVs or solve official instances unless explicitly invoked.
Python 3.10+. Standard library only.
"""
from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Instruction = list[int | str]
MAX_STEPS = 4096
MAX_BYTES = 131072


class ConstructionError(ValueError):
    """This baseline cannot produce a submission-valid program."""


@dataclass(frozen=True)
class Puzzle:
    id: str
    starting_values: list[int]
    targets: list[int]
    value_limit: int
    registers: int = 48

    @classmethod
    def from_dict(cls, row: dict) -> 'Puzzle':
        def parse(value):
            return json.loads(value) if isinstance(value, str) else value
        return cls(
            id=str(row.get('id', 'synthetic')),
            starting_values=parse(row['starting_values']),
            targets=parse(row['targets']),
            value_limit=int(row['value_limit']),
            registers=int(row.get('registers', 48)),
        )


def _check_puzzle(p: Puzzle) -> None:
    if not (1 <= len(p.starting_values) <= p.registers == 48):
        raise ConstructionError('Invalid initial register count')
    if p.value_limit < 1 or not p.targets:
        raise ConstructionError('Invalid value limit or empty targets')
    if any(type(x) is not int or not 1 <= x <= p.value_limit for x in p.starting_values + p.targets):
        raise ConstructionError('Initial values/targets outside [1, value_limit]')


class Builder:
    def __init__(self, puzzle: Puzzle):
        _check_puzzle(puzzle)
        self.p = puzzle
        self.memory: list[int | None] = list(puzzle.starting_values) + [None] * (48 - len(puzzle.starting_values))
        self.program: list[Instruction] = []
        self.covered = set(puzzle.starting_values) & set(puzzle.targets)

    def alloc(self, avoid: set[int] | None = None) -> int:
        for i, value in enumerate(self.memory):
            if value is None and i not in (avoid or set()):
                return i
        raise ConstructionError('No free register: this simple baseline does not evict values')

    def emit(self, op: str, i: int, j: int, d: int) -> None:
        if len(self.program) >= MAX_STEPS:
            raise ConstructionError('Exceeded 4096 instructions')
        a, b = self.memory[i], self.memory[j]
        if a is None or b is None:
            raise ConstructionError('Undefined source register')
        if op == '+': value = a + b
        elif op == '-': value = a - b
        elif op == '*': value = a * b
        elif op == '/':
            if b == 0 or a % b: raise ConstructionError('Non-exact division')
            value = a // b
        else: raise ConstructionError('Unknown operator')
        if not 1 <= value <= self.p.value_limit:
            raise ConstructionError(f'Intermediate {value} outside allowed range')
        self.memory[d] = value
        self.program.append([op, i, j, d])
        if value in self.p.targets:
            self.covered.add(value)

    def one(self) -> int:
        if 1 in self.memory:
            return self.memory.index(1)
        slot = self.alloc()
        self.emit('/', 0, 0, slot)
        return slot

    def copy(self, src: int, one: int) -> int:
        dest = self.alloc()
        self.emit('*', src, one, dest)
        return dest

    def finish(self) -> list[Instruction]:
        if not set(self.p.targets) <= self.covered:
            raise ConstructionError('Not all targets covered')
        if len(json.dumps(self.program, separators=(',', ':'), ensure_ascii=False).encode('utf-8')) > MAX_BYTES:
            raise ConstructionError('Program exceeds 128KiB')
        return self.program


def incremental(p: Puzzle) -> list[Instruction]:
    """Algorithm 1: keep a constant 1 and increment a single accumulator by +1.

    Targets are ascending; already-covered initial values are skipped. May fail
    for large targets because of the 4096-instruction limit. This is expected.
    """
    b = Builder(p)
    pending = sorted(set(p.targets) - b.covered)
    if not pending: return []
    one = b.one()
    # Copy 1 so it is never overwritten.
    acc = b.copy(one, one)
    current = 1
    for target in pending:
        while current < target:
            b.emit('+', acc, one, acc)
            current += 1
    return b.finish()


def _apply_multiples(b: Builder, acc: int, unit: int, amount: int, op: Literal['+', '-'], scratch: int) -> None:
    """Add/subtract amount * unit using repeated doubling of the unit.

    Scratch is overwritten; unit and accumulator are preserved as separate registers.
    Performs only allowed calculator operations. All intermediate values checked.
    """
    if amount <= 0: return
    # For subtraction, descending powers prevent temporary zero/negative states
    # provided the total subtraction is smaller than the current accumulator.
    bits = list(range(amount.bit_length()))
    if op == '-':
        # Build powers one at a time into scratch while recording their values in
        # distinct registers would be expensive. Instead use repeated unit subtraction.
        # It is valid, simple, and faithful to corrections between rings.
        for _ in range(amount):
            b.emit('-', acc, unit, acc)
        return
    # Positive: current + amount*unit must fit the limit, therefore each
    # positive prefix and the doubling powers needed also fit.
    power = unit
    for bit in bits:
        if bit == 1:
            b.emit('+', unit, unit, scratch)
            power = scratch
        elif bit > 1:
            b.emit('+', scratch, scratch, scratch)
        if amount & (1 << bit):
            b.emit('+', acc, power, acc)


def rings(p: Puzzle) -> list[Instruction]:
    """Algorithm 2: q=floor(target/base), r=target%base; traverse sorted targets.

    The base is max(starting_values). For every target, transition between
    quotient rings via multiples of the base, then adjust the residue by ±1.
    Quotient jumps are accelerated by binary doubling (only additions).
    Uses 1, base, accumulator, one scratch register; no optimization over bases.
    Not guaranteed to beat a global optimizer or solve every large puzzle.
    """
    b = Builder(p)
    pending = sorted(set(p.targets) - b.covered)
    if not pending: return []
    base = max(p.starting_values)
    base_reg = p.starting_values.index(base)
    one = b.one()
    acc = b.copy(one if pending[0] < base else base_reg, one)
    scratch = b.alloc()
    # To use the scratch, it must be defined before becoming a read operand.
    b.emit('*', one, one, scratch)

    current = b.memory[acc]
    assert current is not None
    q_current, r_current = divmod(current, base)

    for target in pending:
        q_next, r_next = divmod(target, base)
        if q_next == q_current:
            # Sorted targets imply a nonnegative residue difference here.
            _apply_multiples(b, acc, one, r_next-r_current, '+', scratch)
        else:
            # Align to current ring's base first. It must stay strictly positive.
            # Special case: if current=1 and base>1, adding base before correcting
            # is safe unless it exceeds value_limit. For this case, construct the
            # next target directly by increments when necessary.
            if q_current == 0:
                # Current started at 1. Build to the base by increments of one.
                # This part is intentionally simple; can exceed step limit.
                while current < base:
                    b.emit('+', acc, one, acc)
                    current += 1
                q_current, r_current = 1, 0
                # In case target is base itself (which may already be covered).
            elif r_current:
                _apply_multiples(b, acc, one, r_current, '-', scratch)
                r_current = 0
            # We are at q_current * base. Move to next target's ring.
            _apply_multiples(b, acc, base_reg, q_next-q_current, '+', scratch)
            _apply_multiples(b, acc, one, r_next, '+', scratch)
        current = target
        q_current, r_current = q_next, r_next
        assert b.memory[acc] == target, (b.memory[acc], target)
    return b.finish()


def _midpoint_toward(low: int, high: int, target: int) -> int:
    """Round half-integers away from the target, preserving an interior target."""
    return (low + high + (2 * target < low + high)) // 2


def bisection(p: Puzzle) -> list[Instruction]:
    """A3: bisect neighboring maximum-base rings toward each target.

    Cache actual register values, evicting the first unprotected slot when full.
    Boundaries outside the legal domain are clipped to 1 and value_limit.
    Integer constants/boundaries use binary additions; midpoints use exact
    division of the endpoint difference, avoiding an overflowing endpoint sum.
    """
    b = Builder(p)
    if set(p.targets) <= b.covered:
        return []
    base = max(p.starting_values)
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
    for target in sorted(set(p.targets)):
        if target in b.covered:
            continue
        q = target // base
        low = max(1, q * base)
        high = min(p.value_limit, (q + 1) * base)
        # Build neighboring rings by exact multiplication of a constructed q.
        def boundary(value: int, protected: set[int]) -> int:
            if value in b.memory:
                return b.memory.index(value)
            if value % base == 0:
                quotient = number(value // base, protected)
                return emit('*', quotient, base_reg, protected)
            return number(value, protected)

        left = boundary(low, set())
        right = boundary(high, {left})
        while target not in b.covered:
            mid = _midpoint_toward(low, high, target)
            protected = {left, right}
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
    return b.finish()


def validate(p: Puzzle, program: list[Instruction]) -> dict:
    """Independent replay of a proposed program; raises on any rule violation."""
    _check_puzzle(p)
    encoded = json.dumps(program, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    if len(program) > MAX_STEPS or len(encoded) > MAX_BYTES:
        raise ConstructionError('Step or bytes limit exceeded')
    reg: list[int | None] = list(p.starting_values) + [None] * (48 - len(p.starting_values))
    covered = set(p.starting_values) & set(p.targets)
    for step, instruction in enumerate(program, start=1):
        if (not isinstance(instruction, list) or len(instruction) != 4):
            raise ConstructionError(f'Bad instruction #{step}')
        op, i, j, d = instruction
        if op not in ('+', '-', '*', '/') or any(type(k) is not int or not 0 <= k < 48 for k in (i,j,d)):
            raise ConstructionError(f'Bad operator/register at step #{step}')
        a,b = reg[i],reg[j]
        if a is None or b is None: raise ConstructionError(f'Undefined source #{step}')
        if op == '+': v = a+b
        elif op == '-': v = a-b
        elif op == '*': v = a*b
        else:
            if a % b: raise ConstructionError(f'Non-exact division #{step}')
            v = a // b
        if not 1 <= v <= p.value_limit: raise ConstructionError(f'Invalid value #{step}: {v}')
        reg[d]=v
        if v in p.targets: covered.add(v)
    missing = sorted(set(p.targets)-covered)
    if missing: raise ConstructionError(f'Missing targets: {missing[:10]}')
    return {'id': p.id, 'steps': len(program), 'covered': len(covered), 'valid': True}


def main() -> None:
    parser = argparse.ArgumentParser(description='Santa 2026 arithmetic constructors')
    parser.add_argument('--algorithm', choices=('incremental','rings','bisection','multirings','bisection-reuse','multirings-reuse'), required=True)
    parser.add_argument('--input', type=Path, help='CSV with puzzle instances, explicitly supplied')
    parser.add_argument('--output', type=Path, help='Output CSV containing only validated solutions (may be partial)')
    parser.add_argument('--failures', type=Path, help='Optional CSV report of failed instances; default: <output stem>_failures.csv')
    parser.add_argument('--postprocess', action='store_true', help='Compress valid programs with exact arithmetic rewrites')
    parser.add_argument('--nested-windows', action='store_true', help='Merge windows and reuse intermediate values')
    parser.add_argument('--a4', action='store_true', help='Run bounded checkpoint overshoot optimization')
    parser.add_argument('--demo', action='store_true', help='Solve only a synthetic example')
    args = parser.parse_args()
    if args.algorithm == 'multirings-reuse':
        from elf_calculator.constructors.elf_multirings_reuse import multirings_reuse
        algorithm = multirings_reuse
    elif args.algorithm == 'multirings':
        from elf_calculator.constructors.elf_multirings import multirings
        algorithm = multirings
    elif args.algorithm == 'bisection-reuse':
        from elf_calculator.constructors.elf_bisection_reuse import bisection_reuse
        algorithm = bisection_reuse
    else:
        algorithm = {'incremental': incremental, 'rings': rings, 'bisection': bisection}[args.algorithm]
    if args.demo:
        puzzles = [Puzzle('example_0001',[3],[1,2,5,8],9,48)]
    elif args.input:
        with args.input.open(newline='',encoding='utf-8') as fp:
            puzzles = list(csv.DictReader(fp))
    else:
        parser.error('Provide --demo or --input FILE')
    results = []
    failures = []
    for row in puzzles:
        puzzle_id = row.id if isinstance(row, Puzzle) else str(row.get("id", "synthetic"))
        try:
            puzzle = row if isinstance(row, Puzzle) else Puzzle.from_dict(row)
            program = algorithm(puzzle)
            if args.postprocess:
                from elf_calculator.optimizers.elf_postprocess import postprocess
                before = len(program)
                program = postprocess(puzzle, program)
                print(f'{puzzle.id}: postprocess {before} -> {len(program)}')
            if args.a4:
                from elf_calculator.optimizers.elf_a4 import optimize_a4
                program, stats = optimize_a4(puzzle, program, return_stats=True)
                print(f"{puzzle.id}: A4 {stats['before']} -> {stats['after']}, {stats['candidates']} candidates")
            if args.nested_windows:
                from elf_calculator.optimizers.elf_nested import nested_windows
                program = nested_windows(puzzle, program)
            metrics = validate(puzzle, program)
            print(f'{puzzle.id}: {metrics["steps"]} instructions, valid')
            results.append({'id': puzzle.id, 'program': json.dumps(program, separators=(',', ':'))})
        except (ValueError, IndexError, KeyError, TypeError, AssertionError) as exc:
            reason = f"{type(exc).__name__}: {exc}"
            print(f'{puzzle_id}: NOT SOLVED - {reason}')
            failures.append({'id': puzzle_id, 'reason': reason})

    print(f'\nSummary: {len(results)} solved, {len(failures)} failed, {len(puzzles)} total')
    if args.output:
        with args.output.open('w', newline='', encoding='utf-8') as fp:
            writer = csv.DictWriter(fp, fieldnames=['id', 'program'])
            writer.writeheader()
            writer.writerows(results)
        print(f'Wrote {args.output} ({len(results)} valid programs)')
        if failures:
            print('WARNING: This is a partial CSV, NOT a valid full competition submission.')
    if args.failures or args.output:
        path = args.failures or args.output.with_name(args.output.stem + '_failures.csv')
        with path.open('w', newline='', encoding='utf-8') as fp:
            writer = csv.DictWriter(fp, fieldnames=['id', 'reason'])
            writer.writeheader()
            writer.writerows(failures)
        print(f'Wrote {path} ({len(failures)} failures)')


if __name__ == '__main__':
    main()
