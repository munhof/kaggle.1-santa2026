"""Share equal values globally, retaining the first recipe for each value."""
from collections import Counter

from elf_calculator.constructors.elf_baselines import ConstructionError, validate
from elf_calculator.optimizers.elf_a4 import _apply


def optimize_dag(puzzle, program):
    validate(puzzle, program)
    initial = puzzle.starting_values
    memory = list(initial) + [None] * (48 - len(initial))
    known = set(initial)
    recipes = []
    for op, i, j, dest in program:
        a, b = memory[i], memory[j]
        value = _apply(op, a, b)
        memory[dest] = value
        if value not in known:
            known.add(value)
            recipes.append((value, op, a, b))

    needed = set(puzzle.targets)
    live_recipes = []
    uses = Counter()
    for recipe in reversed(recipes):
        value, _, a, b = recipe
        if value in needed:
            live_recipes.append(recipe)
            needed.update((a, b))
            uses.update((a, b))
    if len(live_recipes) >= len(program):
        return program

    registers = {v: i for i, v in enumerate(initial) if uses[v]}
    free = sorted(set(range(48)) - set(registers.values()), reverse=True)
    result = []
    for value, op, a, b in reversed(live_recipes):
        i, j = registers[a], registers[b]
        for operand in (a, b):
            uses[operand] -= 1
            if uses[operand] == 0:
                free.append(registers.pop(operand))
        if not free:
            return program
        dest = free.pop()
        result.append([op, i, j, dest])
        if uses[value]:
            registers[value] = dest
        else:
            free.append(dest)
    try:
        validate(puzzle, result)
    except ConstructionError:
        return program
    return result
