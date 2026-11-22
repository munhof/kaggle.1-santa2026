# Santa 2026 · The Elf Calculator

Optimizador en Python 3.10+ para construir objetivos aritméticos con 48 registros.
La puntuación es la suma de instrucciones de todos los puzzles. Cada programa
se valida reproduciendo sus operaciones y comprobando registros, división
exacta, positividad, límites y cobertura de objetivos.

## Objetivo actual: mejorar la cartera pública

Cada experimento sobre los 1.000 puzzles puntuables parte del programa público
válido más corto disponible para cada ID. La referencia local validada suma
**130.922 instrucciones**. Corresponde a [GoodPJW v169](https://www.kaggle.com/datasets/goodpjw2008/santa-2026-dag-lns-programs/versions/169).
[Avazaku v30](https://www.kaggle.com/code/avazaku/elf-calc-backward-frontier-rewrite?scriptVersionId=372752967)
suma 130.943 y aporta recetas alternativas.

Para medir el aporte propio, se fija la versión de cada fuente, se valida la
cartera pública inicial y se cuentan los pasos que el optimizador ahorra
frente a esa base en cada ID. Si aparece una nueva fuente pública, se registra
primero cuánto aporta al combinarla. El diario muestra después el ahorro
propio, los IDs mejorados y el total validado de los 1.000 programas.

La búsqueda conjunta de auxiliares, la reparación, el pulido y el cruce
CP-SAT entre ambas fuentes mantuvieron los **130.922 pasos**. El ahorro propio
medido sobre esa referencia es **0**. Los experimentos sobre programas propios
sirven como diagnóstico. [Diario de experimentos](diarios%20de%20avances%20de%20exploracion.ipynb)

## Resultados históricos de los constructores iniciales

| Etapa | Práctica (200/200) | Puntuables (1000/1000) |
|---|---:|---:|
| Una base con reutilización | 281.552 | 1.372.573 |
| Múltiples anillos con reutilización | 267.490 | 1.306.093 |
| + Posprocesamiento | 152.585 | 729.745 |
| + A4 | 152.035 | 727.166 |
| + Ventanas de ventanas | **151.598** | **724.927** |

La referencia de los 1000 puzzles suma 1.490.379 instrucciones. La última
etapa de esta tabla redujo ese total un 51,36 %.

## Métodos

- **A1** (`incremental`) incrementa un acumulador con una constante 1.
- **A2** (`rings`) usa la base máxima y avanza por cocientes y restos.
- **A3** (`bisection`) divide el intervalo entre múltiplos vecinos en puntos enteros.
- **A3 bis** prueba distintas bases iniciales (`multirings`), reutiliza extremos
  y valores residentes (`bisection-reuse`) o combina ambos (`multirings-reuse`).
- **Posprocesamiento** comprime secuencias de operaciones y elimina resultados sin uso.
- **A4** busca checkpoints y corrige por resta, división exacta o ambas. Por
  ejemplo, con 3 y 10 disponibles puede construir 97 como 10 × 10 − 3.
- **Ventanas de ventanas** combina bloques vecinos y reutiliza cálculos entre ellos.

## Uso

Desde la raíz, sin dependencias externas:

```bash
python -m unittest -q
python elf_baselines.py --algorithm multirings-reuse --postprocess --a4 --nested-windows --demo
python elf_baselines.py --algorithm multirings-reuse --postprocess --a4 --nested-windows --input practice_puzzles.csv --output reports/practice_final.csv
python validate_submission.py reports/practice_final.csv --puzzles practice_puzzles.csv
```

Para evaluar los 1000 puntuables, ejecutar explícitamente
`python scripts/evaluate_scored.py`. El script compara las variantes por ID,
escribe el mejor programa válido y verifica el CSV exportado. Muestra la
carpeta de corrida. Para repetir la validación, ejecutar
`python validate_submission.py reports/<corrida>/submission.csv`.

## Organización y reproducción de mediciones

Los constructores viven en `elf_calculator/constructors/`, los optimizadores
en `elf_calculator/optimizers/`, las pruebas en `tests/` y los benchmarks en
`scripts/`. Los tres CSV de entrada se versionan. Las salidas de `reports/`,
las entregas locales de `artifacts/` y los CSV intermedios se excluyen de Git.

Para reproducir las comparaciones históricas de práctica desde cero:

```bash
python elf_baselines.py --algorithm multirings-reuse --input practice_puzzles.csv --output multirings_reuse_results.csv
python scripts/compare_postprocess.py
python scripts/compare_a4.py
python scripts/compare_nested.py reports/<corrida_a4>/programs.csv
python scripts/evaluate_impact.py reports/<corrida_a4>/programs.csv reports/<corrida_nested>/programs.csv
```

Reemplazar los nombres entre ángulos por las carpetas impresas en cada corrida.
