# Reentrenamiento verificable del ranker contextual v2

Fecha: 27 de octubre de 2026. El modelo entrenado es **context-ranker-es-v2**: dos cabezas logísticas, **52 coeficientes ajustados por SGD en CPU**, con características de contexto, carga silábica, edición y estructura. No se presenta este trabajo como un nuevo fine-tuning de mT5. El antiguo checkpoint mT5 de 120 pasos sigue fuera de la activación automática.

## Datos: depuración antes que volumen

Se conserva el CSV original y su SHA-256 `02aeb385fdfa8fd4f9ab3afbc5b0eeac84d514f33c8f20fa387e48068dddab06`. El v1 completo producía **7.704 pares derivados**; el ensayo antiguo entrenó únicamente con 34 pares entre sus tres particiones. El v2 contiene **3.220 pares** después de filtrar y aumentar: **2.284 propuestas EASIER**, **900 ejemplos morfológicos** y **36 pares sintácticos**. La reducción total respecto del corpus sin depurar es intencional; no se atribuyen miles de anotaciones humanas nuevas a la generación automática.

Se descartan candidatos ruidosos, de longitud no menor o con carga silábica no menor. Las flexiones explícitas abarcan presente, pasado, imperfecto, futuro, condicional, participio, gerundio, infinitivo, género/número y nominalizaciones. Solo se conjugan los verbos regulares declarados; los cambios ortográficos como `utilicé` se tratan explícitamente. Los contextos ampliados cubren ciencia, historia, derecho, medicina, deporte y escuela, y se identifican como supervisión sintética débil.

Las etiquetas de nivel proceden del puntaje medido del destino: >=82, >=74, >=65, >=58 y la banda restante. Son cinco clases ordenadas para entrenamiento, no certificaciones de comprensión por edad. La distribución es desigual y limita el aprendizaje de niveles.

| Partición | Pares |
|---|---:|
| train | 2588 |
| validation | 404 |
| test | 228 |

| Nivel | Pares |
|---|---:|
| 1 | 420 |
| 2 | 271 |
| 3 | 227 |
| 4 | 140 |
| 5 | 2162 |

## Separación y límites de la evaluación

El constructor une fuentes repetidas en un componente documental, asigna grupos con semilla fija y purga familias que cruzan particiones. Las flexiones de un lema declarado comparten familia. La auditoría comprueba intersecciones vacías de documento, fuente normalizada y **familia registrada**. No es una prueba de ausencia universal de paráfrasis o parentesco morfológico no reconocido en todo el español.

Los documentos EASIER `120`, `276`, `68`, `30`, `200` y `84`, sus fuentes y 169 familias observadas se excluyen del ajuste v2. En producción, las propuestas del índice SGSS solo se usan cuando documento, familia y frecuencias pertenecen al entrenamiento; las etiquetas de validación/prueba no se consultan para elegir candidatos.

Esos seis documentos habían informado las reglas del v1 y se usaron para diagnosticar el generador de candidatos v2. Por ello **no son una prueba independiente ni ciega de generalización**. Los seis textos nuevos son entradas controladas redactadas aparte, ausentes de los JSONL de entrenamiento; comparten vocabulario y construcciones soportadas. La prueba de 228 ejemplos también se inspeccionó durante el desarrollo: sus cifras se publican como diagnóstico reproducible, sin llamarla evaluación externa ciega.

## Entrenamiento real y artefacto

Se ejecutaron **20 épocas**, con seed `20261027`, pérdida logística y regularización. Los pesos se inicializan a cero; se comprueba que su SHA-256 cambie y que todos los coeficientes sean finitos. Se selecciona la época por `val_loss`, sin usar respuestas de prueba para el gradiente. Los JSONL se verifican contra sus hashes antes de entrenar.

- Pérdida de entrenamiento: **0.485250 → 0.431136**.
- Pérdida de validación: **0.469675 → 0.418884**.
- Época seleccionada: **20**.

`checkpoints/context-ranker-v2/model.json` es el checkpoint local funcional. Su copia de distribución `app/services/assets/context-ranker-v2.json` es idéntica byte a byte e incluye los coeficientes y metadatos necesarios para reproducir la inferencia en GitHub Actions y Docker sin Torch. Los pesos binarios grandes permanecen ignorados. `checkpoints/retraining_metrics.json` se versiona expresamente y contiene historial por época, hashes, manifiesto y evaluación numérica; no contiene documentos privados.

El historial de cada época incluye loss sobre entrenamiento/validación completos, clasificación binaria de candidatos y SARI/ganancia sobre las primeras 24 entradas de validación. La sección `reference_ranking` separada ofrece la referencia como candidato y da 100 en ese diagnóstico: **no mide generación** y no se usa como cifra de eficacia del sistema.

## Comparación de los sistemas completos

El baseline se volvió a ejecutar desde el commit `b342076`, en una extracción temporal de Git, con el mismo SGSS y los mismos textos/métrica. Se comparan salidas reales de ambas arquitecturas; la mejora incluye la composición de reglas y el ranker, y no se atribuye íntegramente a los pesos.

| Conjunto / sistema | Progresión estricta | Doble condición N1 | Ganancia media N1 | SARI | Segundos por cinco niveles |
|---|---:|---:|---:|---:|---:|
| easier_diagnostic / v1 | 0/6 | 5/6 | 38.773 | 25.963 | 0.1234 |
| easier_diagnostic / v2 | 6/6 | 5/6 | 42.069 | 24.650 | 0.1282 |
| unseen_v2 / v1 | 0/6 | 1/6 | 23.695 | 79.669 | 0.0350 |
| unseen_v2 / v2 | 6/6 | 2/6 | 26.574 | 83.120 | 0.0516 |

**6/6** significa cinco textos con índices estrictamente descendentes, no cinco bandas pedagógicas exactas ni fidelidad clínica validada. En particular, algunos niveles intermedios EASIER siguen por debajo de las bandas solicitadas. La doble condición se cumple en 5/6 EASIER y 2/6 textos nuevos. En estos doce textos la ganancia de nivel 1 es >=15, pero no se garantiza ese umbral para entradas arbitrarias.

| Documento EASIER | Original | N1 | N2 | N3 | N4 | N5 |
|---|---:|---:|---:|---:|---:|---:|
| 120 | 58.685 | 87.809 | 82.699 | 71.855 | 63.976 | 58.685 |
| 276 | 27.559 | 71.343 | 41.863 | 40.537 | 40.004 | 37.268 |
| 68 | 44.832 | 62.735 | 62.051 | 61.138 | 60.774 | 59.043 |
| 30 | 36.607 | 72.564 | 60.706 | 58.696 | 56.687 | 54.677 |
| 200 | 14.106 | 84.772 | 42.283 | 34.807 | 32.277 | 24.839 |
| 84 | 11.085 | 66.066 | 24.046 | 21.849 | 20.622 | 20.400 |

## Ablación del aprendizaje: resultado que no debe ocultarse

Sobre las 228 entradas separadas del v2, con el mismo generador de candidatos, SARI pasa de **44.544 con pesos iniciales a 44.501 con pesos entrenados**; la ganancia media pasa de **10.580 a 10.555**. La clasificación binaria de candidatos entrenada tiene exactitud **0.649** y F1 **0.391**. No se obtuvo una mejora agregada de SARI atribuible al entrenamiento. El ranker es real y reduce la pérdida, pero estos resultados no bastan para afirmar que resuelve la selección semántica abierta.

SARI se calcula en escala 0–100 con conjuntos de n-gramas de 1 a 4, tokenización Unicode de palabras y una referencia: F1 de adición, F1 de conservación y precisión de eliminación, con operación vacía frente a vacía igual a uno. Es una variante declarada de referencia única; no se afirma equivalencia exacta con todos los tokenizadores/contadores de EASSE. [Definición de referencia de Hugging Face](https://github.com/huggingface/evaluate/tree/main/metrics/sari). Las referencias EASIER cambian una palabra, por lo que una reescritura estructural fiel puede tener SARI bajo. Ningún índice sustituye la revisión humana de sentido y gramática.

## Inferencia, API y demostración

El artefacto se carga con caché fuera del event loop. Los pesos ordenan sustituciones permitidas y puntúan candidatos estructurales; las reglas preservan números y contextos explícitos. La concordancia de las formas regulares es declarativa. No se afirma un analizador morfológico universal ni un generador neuronal de texto libre.

Texto manual, TXT/PDF y generación por tema usan el mismo pipeline. La API conserva originales completos y añade `model_version`, `checkpoint_name`, ganancias, sílabas, sustituciones y cinco previews. `GET /api/v1/adaptations/model-info` exige autenticación; `/api/v1/admin/overview` incorpora el mismo resumen con RBAC maestro. GET de una versión histórica no la etiqueta falsamente como producida por el modelo nuevo.

Una entrada como «Hola» no puede ganar 15 puntos ni producir cinco dificultades fieles. Se mantiene `200 OK` con mejor esfuerzo y señales de meta/progresión incumplidas. El 6/6 del diagnóstico no convierte esta excepción matemática en una garantía universal.

Las 15 lecciones gestionadas del tutor se regeneran con versión `pedagogical-es-v2`, conservando IDs, fechas, comprensión, gemas, XP y rachas. No se agregan columnas: se usan los JSON existentes. Android permanece sin cambios.

## Reproducción

```sh
python -m ml_training.build_enhanced_dataset
python -m ml_training.train_ranker --epochs 20
# Publicar el checkpoint recién entrenado antes de evaluarlo:
python -c "from pathlib import Path; Path('app/services/assets/context-ranker-v2.json').write_bytes(Path('checkpoints/context-ranker-v2/model.json').read_bytes())"
python -m ml_training.evaluate_baseline --ref b342076
MT5_ENABLED=false python -m ml_training.evaluate_retrained
pytest -q
```

Los derivados completos de entrenamiento y el corpus SGSS permanecen locales. El fixture público `easier_diagnostic.json` conserva sin modificar las seis filas del diagnóstico anterior, con procedencia EASIER; no se mezcla con los pares para ajuste. [Fuente y licencia declarada](https://github.com/LURMORENO/EASIER_CORPUS). Los textos `unseen_v2.json` son ejemplos de evaluación controlada redactados para este proyecto.

## Verificación de la entrega

Suite completa: **494 pruebas aprobadas en PostgreSQL** y **490 aprobadas, 4 omitidas en SQLite**. Ruff, formato, `pip check` y `alembic check` aprobados; no se necesitó migración. El servidor activo en el puerto **8000** devolvió readiness **200**. La verificación HTTP autenticada confirmó el checkpoint v2, el resumen maestro y las 15 lecciones demo, con conservación de práctica y recursos. Las líneas LF del artefacto publicado mantienen su fingerprint al clonar en Windows, Linux o macOS.
