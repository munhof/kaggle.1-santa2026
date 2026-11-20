"""Replay an exported submission and verify exact ID coverage and raw cell size."""
import argparse
import csv
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from elf_calculator.constructors.elf_baselines import Puzzle, validate, MAX_BYTES


def verify(puzzles_path, submission_path):
    with puzzles_path.open(newline='', encoding='utf-8') as fp:
        puzzles = {r['id']: Puzzle.from_dict(r) for r in csv.DictReader(fp)}
    seen = set()
    steps = 0
    with submission_path.open(newline='', encoding='utf-8') as fp:
        rows = csv.DictReader(fp)
        if rows.fieldnames != ['id', 'program']:
            raise ValueError('Se esperaba la cabecera id,program')
        for row in rows:
            key = row['id']
            if key not in puzzles or key in seen or None in row:
                raise ValueError(f'Fila inesperada o duplicada: {key}')
            try:
                cell = row['program']
                if len(cell.encode('utf-8')) > MAX_BYTES:
                    raise ValueError('Celda demasiado grande')
                program = json.loads(cell)
                if not isinstance(program, list):
                    raise ValueError('Se esperaba una lista de instrucciones')
                steps += validate(puzzles[key], program)['steps']
            except (ValueError, TypeError, AttributeError) as exc:
                raise ValueError(f'{key}: {exc}') from exc
            seen.add(key)
    missing = puzzles.keys() - seen
    if missing:
        raise ValueError(f'Faltan {len(missing)} IDs, por ejemplo {min(missing)}')
    return len(seen), steps


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('submission', type=Path)
    parser.add_argument('--puzzles', type=Path, default=Path('puzzles.csv'))
    args = parser.parse_args()
    count, steps = verify(args.puzzles, args.submission)
    print(f'{count} programas válidos, {steps} instrucciones')


if __name__ == '__main__':
    main()
