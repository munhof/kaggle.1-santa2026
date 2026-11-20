"""Combine adjacent blocks and reuse resident values across their boundaries."""
from elf_calculator.optimizers.elf_a4 import _apply, _state
from elf_calculator.constructors.elf_baselines import validate


def _rewrite(code, entry, live, targets):
    expected = entry.copy()
    actual = entry.copy()
    # Last writes to live outputs must materialize in their original register.
    required = set(live)
    materialize = set()
    for k in reversed(range(len(code))):
        d = code[k][3]
        if d in required:
            materialize.add(k)
            required.remove(d)
    steps = []
    for k,(op,i,j,d) in enumerate(code):
        a,b = expected[i],expected[j]
        value = _apply(op,a,b)
        expected[d] = value
        if value in actual and (k not in materialize or actual[d]==value):
            continue
        if a not in actual or b not in actual:
            return code
        left = i if actual[i]==a else actual.index(a)
        right = j if actual[j]==b else actual.index(b)
        steps.append(([op,left,right,d],value))
        actual[d] = value

    # Keep an occurrence of each local target plus the dependencies of live outputs.
    needed = set(live)
    witnessed = set(entry)
    keep_target = []
    for ins,value in steps:
        keep_target.append(value in targets and value not in witnessed)
        witnessed.add(value)
    result = []
    for k in reversed(range(len(steps))):
        ins,_ = steps[k]
        _,i,j,d = ins
        if d in needed or keep_target[k]:
            result.append(ins)
            needed.discard(d)
            needed.update((i,j))
    return list(reversed(result))


def nested_windows(p, program, width=8, levels=4):
    """Reconstruct leaf boundaries on the saved program, then merge pairs recursively."""
    if width<1 or levels<0:
        raise ValueError('invalid window size or level count')
    validate(p,program)
    blocks = [program[k:k+width] for k in range(0,len(program),width)]
    targets = set(p.targets)
    for level in range(levels):
        if len(blocks)<2:
            break
        parents = [sum(blocks[k:k+2],[]) for k in range(0,len(blocks),2)]
        current = [ins for block in parents for ins in block]
        states = _state(p,current)
        live = set()
        exits = []
        for block in reversed(parents):
            exits.append(live.copy())
            for _,i,j,d in reversed(block):
                live.discard(d)
                live.update((i,j))
        offset = 0
        blocks = []
        for block,live in zip(parents,reversed(exits)):
            candidate = _rewrite(block,states[offset],live,targets)
            blocks.append(candidate if len(candidate)<len(block) else block)
            offset += len(block)
        trial = [ins for block in blocks for ins in block]
        try:
            validate(p,trial)
        except ValueError:
            return current
    return [ins for block in blocks for ins in block]
