"""Replay saved practice stages and measure the marginal benefit of each merge level."""
import argparse
import csv
import json
import sys
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from elf_calculator.constructors.elf_baselines import Puzzle, validate
from elf_calculator.optimizers.elf_nested import nested_windows


def indexed(path):
    with (ROOT / path).open() as fp:
        rows = list(csv.DictReader(fp))
    indexed_rows = {r['id']: r for r in rows}
    if len(rows) != len(indexed_rows):
        raise ValueError(f'IDs duplicados en {path}')
    return indexed_rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('a4_programs', type=Path)
    parser.add_argument('nested_programs', type=Path)
    args = parser.parse_args()
    data = indexed('practice_puzzles.csv')
    paths = ['multirings_reuse_results.csv', 'multirings_reuse_postprocessed_results.csv',
             args.a4_programs, args.nested_programs]
    stages = [indexed(path) for path in paths]
    assert len(data) == 200 and all(s.keys() == data.keys() for s in stages)
    records = []
    elapsed = [0.] * 4
    for key, row in data.items():
        puzzle = Puzzle.from_dict(row)
        codes = [json.loads(stage[key]['program']) for stage in stages]
        sizes = [validate(puzzle, code)['steps'] for code in codes]
        levels = []
        for i in range(4):
            start = perf_counter()
            result = nested_windows(puzzle, codes[2], width=8, levels=i+1)
            elapsed[i] += perf_counter() - start
            levels.append(validate(puzzle, result)['steps'])
        assert result == codes[3], key
        lengths = sizes[:3] + levels
        assert all(a >= b for a, b in zip(lengths, lengths[1:])), key
        records.append((key, row['family'], lengths))

    def fmt(n):
        return f'{n:,}'.replace(',', '.')
    totals = [sum(r[2][i] for r in records) for i in range(7)]
    labels = ['Constructor con reutilización', 'Posprocesamiento', 'A4', 'Ventanas nivel 1',
              'Ventanas nivel 2', 'Ventanas nivel 3', 'Ventanas nivel 4']
    lines = ['# Impacto en los 200 puzzles de práctica', '',
             'Cada programa de cada etapa pasó por validate sobre los mismos 200 IDs. '
             'La corrida con cuatro niveles reprodujo instrucción por instrucción la exportación guardada.', '',
             '| Etapa | Instrucciones | Ahorro marginal | Puzzles mejorados frente a la etapa previa |',
             '|---|---:|---:|---:|']
    for i, label in enumerate(labels):
        wins = sum(r[2][i] < r[2][i-1] for r in records) if i else '—'
        gain = fmt(totals[i-1]-totals[i]) if i else '—'
        lines.append(f'| {label} | {fmt(totals[i])} | {gain} | {wins} |')
    lines += ['', '## Efecto de las ventanas frente a A4', '',
              '| Familia | Puzzles | Mejorados | Ahorro de instrucciones |',
              '|---|---:|---:|---:|']
    for family in sorted({r[1] for r in records}):
        gains = [v[2]-v[-1] for _,f,v in records if f == family]
        lines.append(f'| {family} | {len(gains)} | {sum(g>0 for g in gains)} | {fmt(sum(gains))} |')
    best = max(records, key=lambda r:r[2][2]-r[2][-1])
    lines += ['', f'Mayor ahorro individual: {best[0]}, de {fmt(best[2][2])} a {fmt(best[2][-1])} instrucciones.',
              '', '## Reproducción', '', 'Desde la raíz: `python scripts/evaluate_impact.py`.',
              'La medición parte del mismo programa A4 para cada profundidad, con bloques iniciales de 8. '
              'El tiempo local acumulado por profundidad (1 a 4) fue ' +
              ', '.join(f'{t:.2f} s' for t in elapsed) +
              '. La puntuación cuenta instrucciones. Las cifras describen práctica.',
              '', 'Para generar un nuevo CSV de programas con cuatro niveles y el detalle antes/después: '
              '`python scripts/compare_nested.py`.']
    report = ROOT / 'reports/impacto_practica.md'
    report.write_text('\n'.join(lines)+'\n')
    print(report.read_text())


if __name__ == '__main__':
    main()
