# v2.1: contrato final, entrenamiento conjunto y verificación

**El cierre académico al 100% no está demostrado.** Se corrigió el contrato de nivel/edad y se ejecutó un entrenamiento conjunto real, pero el modelo no supera el SARI del baseline y no cumple todas las bandas. La API publica `acceptance_criteria_met=false`; no se fuerza un `true` ni se redondean los valores para aparentar una mejora. El [informe v2 anterior](model-retraining-v2.md) se conserva como evidencia histórica.

## Datos y separación

El CSV SGSS original no se modifica (SHA-256 `02aeb385fdfa8fd4f9ab3afbc5b0eeac84d514f33c8f20fa387e48068dddab06`). El v1 completo producía 7.704 pares derivados y el smoke anterior solo seleccionaba 34. El v2 tenía 3.220; **v2.1 tiene 4.738**: 2.282 propuestas EASIER filtradas, 2.420 ejemplos morfológicos sintéticos explícitos y 36 pares sintácticos. Se ampliaron las formas regulares de 12 a 21 verbos, con pasado, presente, imperfecto, futuro, condicional, participio y gerundio, variantes de género/número y nominalizaciones. No se adivinan flexiones de verbos irregulares desconocidos.

| Partición | Pares |
|---|---:|
| train | 4108 |
| validation | 402 |
| test | 228 |

La división agrupa documentos/fuentes repetidas y familias registradas, y purga cruces entre particiones. Cada JSONL tiene SHA-256 y se comprueba antes de entrenar. Los seis documentos EASIER del diagnóstico se excluyen del ajuste; el índice en producción restringe candidatos y frecuencias a documentos/familias/targets de entrenamiento. Se verifican intersecciones vacías de las claves auditadas, sin afirmar que eso detecte toda paráfrasis o familia no reconocida del español.

La partición test fue inspeccionada durante el desarrollo v2/v2.1; no se usa para gradientes ni para elegir época/política, pero **no es una prueba ciega externa**. Los seis casos conocidos informaron reglas y depuración del generador: el 6/6 no demuestra generalización independiente. Los seis textos controlados fueron redactados aparte y también se usaron para depurar concordancia/segmentación; no se presentan como un nuevo holdout.

## Entrenamiento conjunto real

`train_joint.py` ajusta cinco cabezas lineales sobre **31 características** (155 coeficientes): regresión directa de SARI keep/add/delete, utilidad conjunta y ranking léxico por pares. La utilidad combina SARI, cercanía a banda, reducción silábica y compatibilidad morfológica; las características incluyen retención, grupos de edición, concordancia conocida, números, negaciones y estructura. Las cabezas SARI proyectan fuera las variables de puntuación/edad/banda que no forman parte de su tokenización.

Se ejecutan **35 épocas SGD y 25 iteraciones de árboles residuales compartidos de profundidad 3**; `epochs=60` cuenta las dos fases, no 60 épocas neuronales. El modelo es un ranker de candidatos restringidos; no es un nuevo fine-tuning de mT5. La selección de época/árboles minimiza pérdida de validación. Una búsqueda solo en validación aprende el peso SARI/utilidad y la política de compresión/cercanía. Los logits y árboles se guardan en JSON, con pesos finitos y hashes antes/después.

Pérdida MSE seleccionada: entrenamiento **0.028389**, validación **0.032702**. Época/iteración seleccionada: **60**. La política elegida usa peso de banda **32** y mezcla SARI directa **0**. La pérdida no se compara numéricamente con la entropía cruzada v2, que tiene otra escala.

## Comparación congelada en test

El baseline sin entrenar se vuelve a ejecutar desde **fc12a7a** usando los mismos ejemplos/referencias. El conjunto generado no incorpora la referencia durante inferencia; solo entrenamiento usa destinos anotados. La política y sus umbrales se seleccionan con validation. El test de selección léxica proporciona un span y tres opciones (original, distractor de su propia partición, propuesta anotada): top-1 no equivale a generación libre.

| Métrica, 228 casos | Baseline sin entrenar | v2.1 | Requisito logrado |
|---|---:|---:|---|
| SARI agregado | 44.543848 | 44.529243 | **No** |
| Top-1 léxico | 53.07% | 61.84% | Sí |
| Distancia media a banda (menor es mejor) | 22.506362 | 22.456644 | Sí |

La reducción de distancia y la mejora léxica incluyen la ampliación del generador; no se atribuyen solo a los coeficientes. SARI sigue **por debajo** del baseline. Hubo intentos lineales y residuales anteriores sin mejora conjunta; sus resultados no se ocultaron ni se eligió un checkpoint por su test. Se mantienen las referencias originales: no se reescriben para favorecer al modelo.

SARI utiliza conjuntos de n-gramas Unicode de palabras de 1 a 4, una referencia, keep-F1/add-F1/delete-precision y operación vacía/vacía igual a 1, en escala 0–100. Es una variante declarada, no equivalencia exacta con todos los tokenizadores de EASSE. [Definición primaria](https://github.com/huggingface/evaluate/tree/main/metrics/sari). SGSS aporta sustituciones de una palabra, no cinco paráfrasis completas por edad: las etiquetas de legibilidad calculadas y la supervisión sintética no reemplazan destinos multinivel revisados por personas. Las muestras léxicas aisladas tampoco constituyen una validación de comprensión.

## Cumplimiento medido del pipeline completo

Los cinco textos se miden desde la salida real, sin clamp ni redondeo antes de decidir. Las bandas son N1 82–100, N2 74–84, N3 65–74, N4 58–66 y N5 50–65. `full_target_met` añade la longitud media de oración; no se confunde con pertenencia al intervalo de puntaje ni con la doble condición histórica.

| Conjunto | Progresión estricta | Todas las cinco bandas |
|---|---:|---:|
| Banco local | 31/31 | **4/31** |
| EASIER conocido | 6/6 | **1/6** |
| Textos controlados | 6/6 | **0/6** |

| Conjunto | N1 en banda | N2 | N3 | N4 | N5 |
|---|---:|---:|---:|---:|---:|
| Banco local | 7/31 | 18/31 | 26/31 | 24/31 | 25/31 |
| EASIER conocido | 2/6 | 2/6 | 1/6 | 2/6 | 3/6 |
| Textos controlados | 0/6 | 0/6 | 1/6 | 1/6 | 1/6 |

Las 15 lecciones demo tienen progresión en sus cinco previews. En el nivel que corresponde a cada lectura, **13/15** cumplen la banda de puntaje: Sofía 1/1, Mateo 3/3, Diego 4/5 y Valentina 5/6. Se regeneraron las quince versiones retenidas; once snapshots numéricos cambiaron, conservando IDs, fechas, respuestas, tiempos, gemas, XP y rachas. Repetir refresh no modifica nada.

La palabra «Hola» o un original ya más fácil que la banda avanzada no permiten cumplir todas las bandas a la vez manteniendo fidelidad y la política de no dificultar la fuente. Se entrega mejor esfuerzo con 200 y flags reales; no se añade relleno ni se manipulan métricas. Para textos complejos nuevos tampoco hay garantía universal: el propio conjunto controlado muestra **0/6** con las cinco bandas.

## Contrato de nivel/edad corregido

- Se aceptan `level` y `target_level`, además de los nombres históricos de cada ruta y BASICO/INTERMEDIO/AVANZADO. Alias contradictorios producen error controlado sin reproducir texto.
- Un nivel explícito tiene prioridad. Solo si falta, `age_group` selecciona 1/3/5 para 6-8/9-11/12+. La edad explícita decide las preguntas de esa lección, incluso si difiere del perfil; `child_age_years` y su cumpleaños real no se alteran. Sin contexto explícito se mantienen defaults y la edad del perfil.
- `adapted_text` y `readability_score` principales corresponden al preview del nivel solicitado en texto, generación y TXT/PDF. GET de una versión conserva ese par; otra adaptación de nivel 5 no reemplaza una versión de nivel 1.
- Se devuelven todas las métricas comparativas, `readability_level`, vocabulario, dato curioso y las dos preguntas. `questions` es un alias aditivo de `comprehension_questions`. Model-info y el resumen maestro incluyen las comparaciones, cumplimiento y el flag de criterios **false**.

## Artefacto activo, PostgreSQL y DigitalOcean

`checkpoints/context-ranker-v2.1/model.json` y `app/services/assets/context-ranker-v2.1.json` son copias idénticas; `checkpoints/retraining_metrics.json` es el reporte numérico versionado. No se publican el corpus completo, derivados JSONL, entornos, secretos ni pesos gigantes. Las seis filas públicas sin modificar del fixture EASIER conservan [procedencia y licencia declarada](https://github.com/LURMORENO/EASIER_CORPUS).

`RANKER_CHECKPOINT` selecciona la ruta explícita y el pin SHA-256 opcional verifica el archivo. La carga usa caché fuera del event loop, valida coeficientes/árboles y no necesita NumPy/Torch para servir. El estado `model` de readiness sigue refiriéndose al mT5 opcional; el ranker activo se consulta con versión/checksum en `/api/v1/adaptations/model-info`.

La imagen usa `app.bootstrap`: bloqueo PostgreSQL, `alembic upgrade head` y exec de Uvicorn con el mismo intérprete. Se probaron las ocho revisiones existentes y el segundo arranque idempotente en un esquema PostgreSQL vacío; no se añadió una columna ni una migración ficticia. El lifespan asegura cuentas y demos. [Preparación DigitalOcean](../deploy/README.md) incluye secretos privados de producción y el checkpoint incorporado. Docker CLI está presente pero su daemon local no está operativo. Se añadió un job `container` que construye y prueba la imagen en CI contra PostgreSQL vacío, sin depender del daemon local. No se realizó un despliegue remoto en DigitalOcean.

## Reproducción

```sh
# Requiere el SGSS local y el historial Git que contiene fc12a7a.
python -m pip install 'numpy>=2,<3'
python -m ml_training.build_enhanced_dataset
python -m ml_training.train_joint --epochs 35
MT5_ENABLED=false python -m ml_training.export_joint
pytest -q
```

Resultados exactos, hashes, búsquedas de validación y las 60 iteraciones se encuentran en `checkpoints/retraining_metrics.json`. El indicador de criterios pendientes es parte del resultado, no un error a eliminar con redondeos o pruebas que finjan superioridad.


## Verificación funcional de la entrega

Suite completa PostgreSQL: **538 aprobadas**. SQLite: **533 aprobadas y 5 omitidas**
(comprobaciones exclusivas de PostgreSQL). Después del ajuste del intérprete de
bootstrap se repitieron sus **6 pruebas PostgreSQL**, todas aprobadas. Ruff,
formato y `pip check` pasan. Las pruebas nuevas verifican nivel/edad en todos los
POST, versiones independientes, aliases, respuestas de preguntas y transparencia
de los criterios no cumplidos. Se actualizó la antigua expectativa que ignoraba
la edad solicitada: ahora cambia el grupo pedagógico, conservando el cumpleaños.

El servidor local se reinició mediante el propio `app.bootstrap`, aplicó upgrade
idempotente y devolvió readiness **200**. HTTP autenticado verificó model-info,
resumen maestro y las 15 versiones demo: salida principal igual al preview de su
nivel, puntajes medidos, preguntas y checksum v2.1, con recursos conservados.
La configuración Compose se validó localmente. La construcción y smoke test
reales de la imagen se ejecutan mediante el nuevo job Linux de GitHub Actions.
Nada de esto convierte `acceptance_criteria_met=false` en una validación académica
al 100%: siguen pendientes la superioridad SARI y el cumplimiento completo de bandas.
