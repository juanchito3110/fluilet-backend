# Simplificación pedagógica de cinco niveles

> Estado actual v2.2: ranker léxico y calibrador estructural separados. SARI 44,5396647 sigue por debajo de 44,5438479; top-1 mejora a 73,25%. Cinco bandas simultáneas: 13/31 catálogo, 2/6 EASIER, 5/6 controlados y 7/15 demos. Progresión estricta en todos esos conjuntos; las 15 demos cumplen su nivel asignado. `acceptance_criteria_met=false`. [Informe vigente](model-retraining-report.md). Las secciones v1/v2/v2.1 siguientes son históricas, incluida la antigua política de no dificultar ningún nivel.

> **Entrega v2.1:** se corrigieron `level`/edad, el texto principal por nivel y la recuperación de versiones, y se ejecutó entrenamiento conjunto sobre 4.738 pares. La progresión sigue en 31/31 artículos y 6/6 EASIER, pero solo 4/31 y 1/6, respectivamente, cumplen las cinco bandas. SARI 44,529 no supera el baseline 44,544. `acceptance_criteria_met=false`. Véase [el informe actual](model-retraining-report.md). Las tablas inferiores se conservan como historial v1/v2.

> Actualización v2 (27 de octubre de 2026): el ranker contextual fue entrenado realmente en 20 épocas sobre 3.220 pares depurados/ampliados. La progresión del diagnóstico EASIER pasa de 0/6 a 6/6; eso no implica bandas exactas ni una garantía universal. El aprendizaje aislado no mejoró SARI agregado frente a su ablación. Véase [el informe completo y las limitaciones](model-retraining-report.md). Las cifras siguientes describen la calibración histórica v1.

## Procedencia y arquitectura

El motor `pedagogical-es-v1` combina recursos léxicos con reescrituras sintácticas trazables y material didáctico local alineado. Las métricas siempre se calculan desde los textos que devuelve la API, sin redondear ni recortar puntajes.

1. **Recursos en memoria.** El startup carga una vez SGSS mediante el lector compartido de `ml_training/prepare_easier.py`, compatible con UTF-8/CP1252 mezclados. En esta máquina se leyeron **5.130 filas**, se indexaron **7.876 candidatos para 3.387 términos** y se descartaron explícitamente ocho anotaciones inválidas. El diccionario independiente contiene **397 pares curados**. La ausencia del CSV usa ese diccionario y se informa como `missing`; un archivo vacío o demasiado grande se informa sin bloquear el servidor.
2. **Limpieza derivada.** Se retiran pronunciaciones, referencias y rangos biográficos parentéticos reconocidos. `removed_fragments` permite inspeccionar esas omisiones. Condiciones, negaciones, ecuaciones y fechas dentro del relato permanecen. La introducción completa en texto plano de Wikipedia se conserva en `original_text` cuando esa es la fuente seleccionada; la limpieza se aplica a la derivación adaptada. Para temas conocidos, si la fuente remota no permite la progresión o la ganancia de nivel 1, se usa la referencia local con `source.provider=local` y el warning `pedagogical_local_reference`; no se presenta esa referencia como texto de Wikipedia.
3. **Reescritura.** Se reducen locuciones académicas, se transforman pasivas con actor/objeto explícitos y se separan coordinaciones con sujeto reconocible. Las subordinadas restrictivas y estructuras ambiguas no se cortan por posición de palabra. Los sinónimos EASIER requieren coincidencia fuerte con su oración anotada; no se aplica el primer sinónimo a cualquier sentido de una palabra.
4. **Diferenciación.** Cada nivel tiene una política de vocabulario, extensión y objetivo de puntaje. El banco de **31 artículos** dispone de alineaciones de hechos redactadas para lectura fácil y variantes de detalle. Se selecciona una secuencia de puntuaciones realmente descendentes cuando existe, sin volver más difícil un texto que su fuente para forzar una banda.
5. **Medición y entrega.** Se calculan los cinco textos, sus puntajes y las comparaciones completas. Entradas válidas conservan la entrega de mejor esfuerzo. Una entrada como «Hola» no admite cinco dificultades fieles: los cinco previews se entregan, pero `level_progression_met=false` y un warning evitan afirmar una progresión inexistente.

### Qué aportan el corpus y el checkpoint

La frecuencia usada para elegir candidatos es frecuencia de propuestas en SGSS, no una supuesta frecuencia general del español. Los equivalentes con problemas de polisemia, género o modificación quedan protegidos; las definiciones largas se enseñan en el glosario/material alineado en lugar de insertarlas ciegamente en cualquier frase.

El inventario detectó `checkpoints/easier-smoke/merged`, sus pesos y el manifiesto de **120 pasos**. Ese ensayo ya había fallado la evaluación de generación: no se activa automáticamente ni se presenta como un modelo clínico convergido. La inferencia mT5 sigue disponible de forma perezosa al configurar un checkpoint válido. La generación de previews y el seed no cargan ese ensayo ni requieren Torch. `ml_training/evaluate_levels.py` ejecuta la evaluación local reproducible sin pesos. El corpus, derivados de entrenamiento y pesos permanecen fuera de Git; se conserva la atribución/licencia declarada por el proveedor en `ml_training/README.md`.

## Originales y validez de la comparación

Un original recibido de Wikipedia, texto o PDF no se dificulta ni se sustituye para simular una mejora. Los originales del banco local son referencias redactadas con fuentes públicas. En esta revisión se publicó una referencia formal nueva para Real Madrid, explícitamente **local**, con los mismos hechos/datos históricos; no se atribuye esa redacción a Wikipedia. Los otros treinta originales se conservan. La media original del banco es **50.801** y la mediana **51.094**: la complejidad real varía, no se fuerza cada fuente a 35–55.

Las alineaciones del banco y la selección por bandas son material de desarrollo/calibración. No constituyen un holdout, una medida de comprensión infantil ni evidencia de generalización clínica. Los hechos se conservan o explican en sus alineaciones; las pruebas automatizadas verifican fechas/números, métricas y contratos, pero no sustituyen una revisión humana del sentido.

## Metas y etiquetas

Las bandas pedagógicas solicitadas son metas, no puntajes garantizados para cualquier entrada. `target_met` exige tanto banda de puntaje como media de palabras/oración. Los niveles 4 y 5 pueden ser adecuados a su meta sin satisfacer el objetivo legado de delta >=15 y score >=65; `quality_status` y `meets_readability_target` conservan ese contrato anterior.

`readability_level` interpreta el índice con las cinco bandas INFLESZ: muy difícil <40; algo difícil 40–55; normal 55–65; bastante fácil 65–80; muy fácil >80. Se distingue de las metas pedagógicas configuradas. Fuente primaria: [Barrio-Cantalejo y colaboradores, validación INFLESZ](https://doi.org/10.4321/s1137-66272008000300004). No se convierte un umbral de legibilidad en una prueba de edad o diagnóstico.

## Resultados medidos del banco local

**31/31 fuentes con cinco textos distintos y puntajes estrictamente descendentes.** Media de inferencia local para los cinco niveles juntos: **0.0329 s**, un ensayo CPU que incluye el calentamiento inicial; no es un benchmark de carga concurrente.

| Nivel | Puntaje medio | Ganancia media | Palabras/oración | Ganancia ≥15 | Meta de banda y longitud | Doble condición |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 75.427 | 24.626 | 7.94 | 26/31 | 7/31 | 22/31 |
| 2 | 72.148 | 21.347 | 8.78 | 24/31 | 9/31 | 20/31 |
| 3 | 66.174 | 15.374 | 11.35 | 13/31 | 17/31 | 10/31 |
| 4 | 60.574 | 9.773 | 13.87 | 7/31 | 12/31 | 0/31 |
| 5 | 57.385 | 6.584 | 14.19 | 3/31 | 3/31 | 0/31 |

| Fuente | Original | N1 | N2 | N3 | N4 | N5 |
|---|---:|---:|---:|---:|---:|---:|
| real madrid | 39.633 | 82.450 | 75.753 | 66.348 | 57.066 | 52.728 |
| biologia marina | 47.825 | 79.997 | 79.050 | 69.470 | 62.255 | 60.291 |

## Evaluación EASIER separada

El subconjunto de seis casos previamente calibrados pasó por el mismo motor: puntaje original medio **32.146**; nivel 1 **70.918**, delta medio **38.773**, doble condición **5/6**, progresión estricta de cinco niveles **0/6**. Se publica el resultado bajo para progresión, no se mezcla con el 31/31 del banco. El índice de SGSS completo incluye contextos de esta muestra, por lo que tampoco es una evaluación ciega.

Los archivos [resultados del banco](pedagogical-evaluation-results.json) y [resumen EASIER](pedagogical-easier-summary.json) contienen valores sin redondear. Reproducción:

```sh
python -m ml_training.evaluate_levels --output docs/pedagogical-evaluation-results.json
python -m ml_training.evaluate_levels --data ml_training/data/easier-smoke/test.jsonl --output ml_training/output/easier-five-level.json
```

## Contrato API y actualización de demos

Todos los POST de adaptación y GET de una versión añaden `readability_gain`, `original_avg_sentence_length`, `adapted_avg_sentence_length`, `original_syllables_per_word`, `adapted_syllables_per_word`, `lexical_replacements`, `level_previews`, `level_progression_met`, `removed_fragments` y `engine_version`. Cada preview incluye nivel, texto, puntaje, etiqueta, media de longitud, `target_met` y método. Las sustituciones son un desglose real de palabras/frases modificadas, acotado a 80 entradas; las operaciones de reordenamiento/noise se distinguen del cambio léxico.

Las versiones antiguas se enriquecen al leerlas con comparaciones de su **par almacenado**, sin escribirlo ni cambiarlo silenciosamente. Sus previews se calculan con el motor actual y la versión se identifica como `legacy_enriched`.

Los datos nuevos caben en el JSON de adaptación existente: no se requieren columnas ni migración. Al restaurar/iniciar las cuentas gestionadas se actualizan sus lecturas marcadas al motor nuevo. `/profiles/{id}/seed-demo` actualiza solo el perfil autorizado. Una actualización de los demos preserva IDs de adaptación cuando cambia una referencia local, fechas, respuestas, comprensión, recursos y claves de misión; solo cambia el contenido y la telemetría de legibilidad derivada. No se modifica la práctica real sin marca demo.

La imagen Docker incluye el lector CSV ligero compartido, sin instalar dependencias de entrenamiento. El corpus y los checkpoints siguen fuera de la imagen; para usar SGSS se monta el archivo suministrado en `/srv/fluilet/datasets/EASIER/SGSS.csv` como solo lectura. Sin ese montaje funcionan el diccionario curado y las alineaciones locales.

Las cuentas y las políticas de PIN/RBAC continúan en [demo-accounts.md](demo-accounts.md). El backend permanece compatible con DTOs previos; el cliente debe consumir `level_previews` para activar su selector de lectura en vivo.
