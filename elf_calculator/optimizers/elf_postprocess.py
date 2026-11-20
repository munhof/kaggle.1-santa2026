"""Bounded arithmetic compression; all accepted output is independently replayed."""
from elf_calculator.constructors.elf_baselines import Puzzle, Instruction, validate


def _value(op, a, b):
    if op == '+':
        return a + b
    if op == '-':
        return a - b
    if op == '*':
        return a * b
    return a // b


def _pair(value, memory):
    """Find one exact addition or multiplication using resident operands."""
    registers = {v: i for i, v in reversed(list(enumerate(memory))) if v is not None}
    for a, i in registers.items():
        if value - a in registers:
            return ['+', i, registers[value-a]]
        if value % a == 0 and value // a in registers:
            return ['*', i, registers[value//a]]
    return None


def _replacement(value, destination, memory, live, limit, allow_two):
    pair = _pair(value, memory)
    if pair:
        return [pair + [destination]]
    if not allow_two:
        return None
    for i, a in enumerate(memory):
        if a is None:
            continue
        for op, intermediate in [('+', value-a),
                                 ('*', value//a if value % a == 0 else 0)]:
            if not 1 <= intermediate <= limit:
                continue
            pair = _pair(intermediate, memory)
            if pair is None:
                continue
            scratch = next((k for k in range(48)
                            if k != i and (k not in live or k == destination)), None)
            if scratch is not None:
                return [pair + [scratch], [op, i, scratch, destination]]
    return None


def _pass(p, program, window):
    memory = list(p.starting_values) + [None] * (48-len(p.starting_values))
    seen = set(p.starting_values)
    values, witnesses = [], set()
    for k, (op, i, j, d) in enumerate(program):
        value = _value(op, memory[i], memory[j])
        memory[d] = value
        values.append(value)
        if value in p.targets and value not in seen:
            witnesses.add(k)
        seen.add(value)

    # Preserve one occurrence of each target and every value needed to produce it.
    live_after = [set() for _ in program]
    live, needed = set(), set(witnesses)
    for k in range(len(program)-1, -1, -1):
        live_after[k] = live.copy()
        op, i, j, d = program[k]
        if d in live or k in witnesses:
            needed.add(k)
            live.discard(d)
            live.update((i, j))

    memory = list(p.starting_values) + [None] * (48-len(p.starting_values))
    result = []
    start = 0
    while start < len(program):
        if start not in needed:
            start += 1
            continue
        replacement = None
        stop = start+1
        for end in range(min(len(program), start+window), start+1, -1):
            changed = {instruction[3] for instruction in program[start:end]}
            required = changed & live_after[end-1]
            targets = {values[k] for k in range(start, end) if k in witnesses}
            if len(required) > 1 or len(targets) > 1:
                continue
            destination = next(iter(required)) if required else program[end-1][3]
            last = next((k for k in range(end-1, start-1, -1)
                         if program[k][3] == destination), None)
            value = values[last]
            if targets and targets != {value}:
                continue
            replacement = _replacement(value, destination, memory,
                                       live_after[end-1], p.value_limit, end-start > 2)
            if replacement is not None and len(replacement) < end-start:
                stop = end
                break
            replacement = None
        chosen = replacement if replacement is not None else [program[start].copy()]
        for op, i, j, d in chosen:
            memory[d] = _value(op, memory[i], memory[j])
        result.extend(chosen)
        start = stop
    return result


def postprocess(p: Puzzle, program: list[Instruction], window: int = 12) -> list[Instruction]:
    """Remove dead work and replace short windows with 1-2 exact +/* operations.

    Preserve target witnesses and live registers, including overwritten sources.
    Constants must already be resident or be built by the counted first operation.
    Three bounded passes; no optimality claim. Input must already be valid.
    """
    validate(p, program)
    result = [instruction.copy() for instruction in program]
    for _ in range(3):
        candidate = _pass(p, result, window)
        validate(p, candidate)
        if len(candidate) >= len(result):
            break
        result = candidate
    return result
