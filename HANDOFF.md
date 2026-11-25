# Traspaso de agentes · Santa 2026

La meta es reducir las instrucciones de los programas del Elf Calculator. El último envío del usuario a Kaggle fue de **128.295**. La cartera pública de ishankarnick, descargada y validada localmente, suma **128.182** en los 1.000 puzzles. Los 113 pasos de diferencia ya estaban en la descarga pública. La corrida posterior no se envió a Kaggle.

| Experimento | Base | Final | Puzzles mejorados |
|---|---:|---:|---:|
| Práctica · recetas de otros puzzles | 32.892 | 32.819 | 51 de 200 |
| Práctica · dos recetas con un auxiliar compartido | 32.819 | 32.793 | 3 de 200 |
| Puntuables · ambas pasadas sobre el frontier público | 128.182 | 128.182 | 0 de 1.000 |

En práctica, el cruce por tramos ahorró 6, 14 y 6 pasos en `practice_0088`, `practice_0183` y `practice_0195`. En puntuables se ensayaron 68.548 grupos distintos por puzzle, sumados sobre todo el conjunto. 46.302 produjeron un grafo acíclico y ninguno redujo su tamaño. El CSV final es idéntico byte por byte al frontier congelado.

## Archivos

| Archivo local | Uso |
|---|---|
| `artifacts/submission_goodpjw_128295.csv` | Referencia del último envío |
| `reports/public_frontier_128182/submission.csv` | Frontier congelado, con atribución por puzzle en `sources.csv` y créditos en `CREDITS.md` |
| `reports/scored_cross_puzzle_3k3z4pv0/` | CSV final, métricas y movimientos por etapa |
| `reports/cross_puzzle_segments_practice_b6fztq3q/` | Resultado y diagnóstico del cruce por tramos en práctica |
| `scripts/cross_puzzle_recombine.py`, `scripts/cross_puzzle_segments.py` | Cruce individual y por pares |

Los CSV y diagnósticos bajo `reports/` son archivos locales ignorados por Git. Recuperá esa carpeta del workspace si necesitás comparar exactamente la misma versión. El [dataset público de ishankarnick](https://www.kaggle.com/datasets/ishankarnick/santa-2026-frontier-programs) se actualiza y una descarga nueva puede diferir. SHA-256 del frontier congelado y del CSV final: `7267bb038a8866cd311d58bb963a5522ab0c45f0c96cc14c00cf196a959eecfc`.

Para verificar el resultado local:

```bash
python validate_submission.py reports/scored_cross_puzzle_3k3z4pv0/final.csv --puzzles puzzles.csv
```

## Hipótesis pendiente

Buscar auxiliares nuevos adaptando las entradas de un tramo donante. El ensayo actual exige coincidencia exacta de valores, toma las dos recetas del mismo donante y exige un auxiliar importado en común. El siguiente piloto puede relajar la coincidencia exacta y medir el ahorro sobre una cartera de práctica fuerte. Validá la longitud del programa compilado y volvé a ejecutar el validador independiente antes de considerar una mejora. Consultá al usuario antes de una nueva corrida sobre los puntuables o un envío.
