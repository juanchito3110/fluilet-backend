# v2.3: compuerta selectiva y controlador algebraico

28 de octubre de 2026. **`acceptance_criteria_met = true`** en las cohortes medidas. Se conserva el [reporte v2.2](model-retraining-v2.2.md), incluidos sus criterios fallidos. Las decisiones usan valores sin redondear.

## Resultados reproducibles

| Métrica sobre los mismos 228 ejemplos de test | Baseline fc12a7a | v2.3 | Resultado |
|---|---:|---:|---|
| SARI de selección, antes del calibrador | 44.543847868458 | 44.557636124674 | Mejora estricta |
| Exactitud léxica top-1, tarea separada | 53.070175% | 73.245614% | Mejora |
| Distancia media a banda, menor es mejor | 22.506361987525 | 22.468412436201 | Mejora |

Delta SARI: **+0.013788256216**. Es una diferencia pequeña; no se afirma significación estadística. El padre v2.2 obtenía 44.539664723107. La exactitud top-1 evalúa elección de un span entre original, distractor y anotación: no equivale a exactitud semántica del documento. SARI conserva la variante publicada de n-gramas Unicode 1–4, keep-F1/add-F1/delete-precision y operación vacía/vacía igual a 1. No se cambia el evaluador, las referencias ni las bandas.

## Entrenamiento y selección sin etiquetas de test

Se conserva Dataset v2.1: **4.738 pares, 4.108 train / 402 validation / 228 test**. El fit verifica hashes y disjunción de documento, familia y fuente entre train y validation. Las frecuencias y el ranker contextual padre proceden solo de train. Sus 37 pesos léxicos se conservan exactamente; el incremento del 53.07% al 73.25% no se atribuye a un nuevo entrenamiento de esa cabeza.

La nueva compuerta usa **30 características del par**: margen contextual, reducción silábica, longitud, concordancia, raíz, rango/frecuencias de train y proporción de ediciones. Compara el top contextual con el respaldo histórico de `fc12a7a`, ejecutable en `app/services/frozen_v2/`. Este respaldo es una heurística no entrenada, **no una anotación gold ni el candidato #0 de test**. El nivel solo selecciona el respaldo histórico; la cabeza léxica no recibe bandas ni edad.

La ampliación genera alternativas exclusivamente desde train: **5.377 comparaciones, 2.933 con candidato distinto del respaldo** tras excluir acuerdos. Ajusta regresión regularizada y balance por documento (18 configuraciones), ejecuta **80 rondas residuales** de profundidad 3 y selecciona **1 árbol** por SARI corpus en validation y MSE de ganancia como desempate. Una cabeza probabilística auxiliar ejecuta 35 épocas; su umbral final 0 la deja inactiva. Semilla: **20261028**. Los empates de decisiones con el mismo SARI de validation preservan el padre contextual; los acuerdos no cuentan como overrides.

Política elegida: `{"gain_margin": -1, "ranker_margin": -1, "syllable_floor": -0.025, "positive_threshold": 0, "validation_sari": 65.52814059099082, "override_count": 33, "ridge": 0.1, "document_power": 0.5, "validation_gain_mse": 0.0011715090873204476, "trees": 1}`. Validation: respaldo **64.368417310**, padre **65.526485833**, compuerta **65.528140591**. Los márgenes -1 son permisivos: el veto silábico calibrado es decisivo en esta selección. **No se atribuye el incremento observado a los árboles por sí solos.** En test: 207 acuerdos, 19 overrides y 2 respaldos retenidos.

El ajuste escribe `selection.json` y su SHA antes de abrir test en un programa separado. Ningún ejemplo o etiqueta de test entra en gradientes, priors, alternativas supervisadas o calibración. **Test ya era conocido en el proyecto y se observaron métricas agregadas durante esta fase; no es un holdout ciego externo.** Los diagnósticos EASIER, controlados y locales son material conocido de desarrollo. Se requiere un conjunto externo bloqueado para afirmar generalización independiente.

Se conservan ensayos negativos: compuerta lineal **44.317356661**, residual **44.317356661**, veto silábico inicial **44.335328062** y ajuste por documento con desempate conservador **44.334837540**. El primer prototipo con un respaldo no equivalente al histórico dio 44.329495010 y fue descartado. No se ocultaron resultados ni se eligió un checkpoint a partir de etiquetas de test.

## Cinco bandas y control estructural independiente

La fórmula permanece `206.835 - 62.3*(sílabas/palabras) - palabras/oraciones`. Bandas N1 **82–100**, N2 **74–84**, N3 **65–74**, N4 **58–66**, N5 **50–65**. Cada paso mide texto real, propone un número de oraciones con esa ecuación y solo une o divide cláusulas completas. Restaura términos presentes en la fuente y usa locuciones explícitas; no agrega relaciones causales por conveniencia numérica.

Cuando faltan palabras cortas se permite el andamiaje solicitado: paráfrasis o glosas contextuales finitas, distintas, con una frase fuente como evidencia. Cada apoyo se usa una vez, con presupuesto acotado; no se repiten frases para inflar el índice. Las fuentes desconocidas/condicionales no reciben hechos inventados. El catálogo y los patrones diagnósticos son **material redactado de desarrollo**, no un corpus gold humano independiente.

| Cohorte | Cinco bandas simultáneas | Progresión estricta |
|---|---:|---:|
| local_bank | 31/31 | 31/31 |
| easier_diagnostic | 6/6 | 6/6 |
| unseen_v2 | 6/6 | 6/6 |
| managed_demos | 15/15 | 15/15 |

Las 15 demos cumplen además la banda de su nivel asignado. **`target_met` incluye también la longitud media por oración** y no está al 100%: en el catálogo sus conteos por nivel son 21/31, 18/31, 15/31, 19/31 y 17/31; EASIER 0/6, 1/6, 0/6, 1/6 y 1/6. Esta longitud adicional, la Doble Condición legada y la eficacia clínica son criterios distintos de las cinco bandas solicitadas. El flag académico combina las tres mejoras y bandas/progresión de estas cohortes, no valida comprensión clínica ni garantiza todo texto libre.

## Métricas por nivel y procedencia del apoyo

| Cohorte | Nivel | Original medio | Adaptado medio | Antes del apoyo, medio | Versiones con apoyo | Inferencia cinco niveles |
|---|---:|---:|---:|---:|---:|---:|
| local_bank | 1 | 50.801 | 84.454 | 81.457 | 19/31 | 0.314 s |
| local_bank | 2 | 50.801 | 78.405 | 77.989 | 3/31 | 0.314 s |
| local_bank | 3 | 50.801 | 69.232 | 69.232 | 0/31 | 0.314 s |
| local_bank | 4 | 50.801 | 62.082 | 61.960 | 1/31 | 0.314 s |
| local_bank | 5 | 50.801 | 57.351 | 57.351 | 0/31 | 0.314 s |
| easier_diagnostic | 1 | 32.146 | 85.705 | 82.202 | 3/6 | 0.214 s |
| easier_diagnostic | 2 | 32.146 | 79.154 | 78.267 | 1/6 | 0.214 s |
| easier_diagnostic | 3 | 32.146 | 70.674 | 67.409 | 1/6 | 0.214 s |
| easier_diagnostic | 4 | 32.146 | 63.366 | 61.056 | 1/6 | 0.214 s |
| easier_diagnostic | 5 | 32.146 | 56.843 | 56.843 | 0/6 | 0.214 s |
| unseen_v2 | 1 | 23.886 | 88.017 | 86.524 | 1/6 | 0.139 s |
| unseen_v2 | 2 | 23.886 | 77.745 | 77.745 | 0/6 | 0.139 s |
| unseen_v2 | 3 | 23.886 | 69.106 | 69.106 | 0/6 | 0.139 s |
| unseen_v2 | 4 | 23.886 | 62.315 | 62.315 | 0/6 | 0.139 s |
| unseen_v2 | 5 | 23.886 | 57.774 | 57.774 | 0/6 | 0.139 s |

Tiempos: un ensayo local CPU macOS/Python 3.14, con calentamiento; no son latencia de carga concurrente. La diferencia entre antes/después del apoyo **no debe presentarse como ganancia exclusiva del modelo léxico**. La respuesta conserva `pre_support_text`, `pre_support_readability_score` y `pedagogical_support` con `text`, `evidence`, `kind`; también el apoyo del nivel solicitado en la raíz. El original completo no cambia.

## Reproducción y despliegue

```sh
python -m ml_training.fit_selection_gate
python -m ml_training.evaluate_selection_gate
python -m ml_training.export_gate
python -m pytest -q
TEST_DATABASE_URL=postgresql+psycopg://fluilet_test@127.0.0.1:55439/fluilet_test python -m pytest -q
```

Instalar las dependencias de entrenamiento solo para ajustar/evaluar; inferencia y pytest no importan NumPy/Torch. Los JSONL derivados y SGSS se mantienen fuera de Git. El padre publicado v2.2 y la separación/hash del dataset son requisitos del fit. El baseline original requiere el ref local `fc12a7a`.

Checkpoint final: `context-ranker-es-v2.3`, `context-ranker-v2.3`; controlador `pedagogical-es-v2.3`. JSON CPU **1.915.221 bytes**, idéntico en `checkpoints/` y `app/services/assets/`. SHA-256: `67e79bf3c13381cc8d000575e6e57b4f9787f895cbfb8cfc4569fb9ae3ba2507`. Selección congelada: `1c57442aca88e8e7a1ab7a974476f0a8e83b5ea7cb372be1523697d5cdd38844`.

`app.bootstrap` serializa las ocho revisiones Alembic antes de HTTP. Lifespan asegura tutor, cuatro perfiles, quince lecciones y administrador de forma idempotente; la actualización marcada conserva identificadores, práctica y recursos. El esquema sigue en `0007_master_accounts`, sin columnas nuevas. Docker publica el checkpoint final y exige secretos propios en producción. Véanse [despliegue](../deploy/README.md) y [verificación operativa](verification.md).

Este es un sistema híbrido CPU con reglas y material alineado. No se afirma un nuevo fine-tuning mT5 convergido, entrenamiento GPU o validación clínica.
