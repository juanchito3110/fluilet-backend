# Evaluación técnica de mT5 + EASIER

> Actualización: el motor vigente y sus resultados están en [simplificación pedagógica](pedagogical-simplification.md). Las mediciones siguientes son históricas.

**Fluilet · 20 de octubre de 2026 (entrenamiento: 19 de octubre) · Entregable para el asesor Aldo Maciel**

## Política de entrega vigente desde el 21 de octubre de 2026

Por decisión de producto, la doble condición es ahora un **objetivo de calidad**,
no una causa de rechazo HTTP. Una entrada válida dentro de límites se entrega
con 200 como `target_met` o `best_effort`, conservando el original cuando no hay
mejora fiel. Los puntajes, delta, números y negaciones siguen comprobándose;
ninguna entrega por debajo del objetivo cuenta como cumplimiento matemático.
`evaluate.py` informa `delivery_rate` por separado de `acceptance_rate` y conserva
las métricas de calidad únicamente sobre salidas que cumplen el objetivo.

La regresión del emulador se reproduce con mT5 no disponible y las reglas activas:

| Texto manual | Niveles | Original | Adaptado | Delta | Objetivo | HTTP |
|---|---|---:|---:|---:|---|---|
| A: estímulos y comprensión lectora | 1, 2, 3, 4, 5 | -29,152097 | 65,420965 | 94,573062 | Cumple | 200 |
| B: materiales y herramientas escolares | 1, 2, 3, 4, 5 | -13,586875 | 59,851667 | 73,438542 | Mejor esfuerzo: puntaje <65 | 200 |

Los valores se muestran redondeados solo en esta tabla; las decisiones usan
flotantes sin redondear. Las frases explicitan el grupo de niños diagnosticados
y el grupo de alumnos con dificultades, sin convertir relativos restrictivos en
hechos sobre todos los lectores. Esto es una regresión funcional, no un nuevo
entrenamiento ni evidencia clínica. Se verifica también texto de una palabra,
texto técnico sin sustituciones, documentos largos, oraciones sin punto, TXT/PDF,
los cinco niveles y sesiones infantiles/adultas con métricas por debajo del objetivo.
Reproducción: `python -m pytest tests/test_best_effort.py -q`.

**Evidencia histórica:** todas las tablas y archivos de métricas que siguen son
resultados del 19–20 de octubre, bajo la puerta de rechazo anterior. Los valores
«422» y «rechazo» de esos experimentos describen esa versión, no el comportamiento
actual. No se han recalculado esas corridas de mT5 en este cambio funcional.

La calibración solicitada incorpora pares léxicos EASIER y plantillas sintácticas
con restricciones de contexto. El sistema completo mejora de **0/6 a 5/6 (83,33 %)**
en los seis casos EASIER usados para diseñar estas reglas. En las cinco entradas
aceptadas, el promedio pareado pasa de **29,608420 a 76,135673**, delta **46,527253**.
Las cinco cumplen las dos condiciones sin redondear y el filtro automático.

En el diagnóstico sintético mejora de **8/14 a 10/14 (71,43 %)**: ocho adaptaciones
ordinarias y dos mantenimientos. Los cuatro rechazos se conservan. Los modelos
puros base y ajustado siguen sin producir salidas válidas. Las adaptaciones
aceptadas se atribuyen a reglas, no al entrenamiento de mT5.

**Alcance:** los seis casos EASIER ahora son calibración, no prueba independiente.
En una muestra adicional de 12 documentos no usados para definir estas reglas,
la aceptación sigue en **0/12**. La mejora no demuestra generalización ni
preservación semántica validada por humanos. El checkpoint aislado no está listo
para uso clínico. No se modificaron pesos, umbrales ni excepciones en esta fase.

La evidencia actual está en [easier-calibration-results.json](easier-calibration-results.json).
Los registros anteriores permanecen en [hybrid-evaluation-results.json](hybrid-evaluation-results.json)
y [ml-evaluation-results.json](ml-evaluation-results.json). Se publican datos
numéricos, hashes y configuración, sin redistribuir textos EASIER ni pesos.

## Datos y trazabilidad

Se utilizó `SGSS.csv` del [repositorio oficial EASIER](https://github.com/LURMORENO/EASIER_CORPUS),
revisión `f0b8312d1ded3d674a7d96d0fb2dc00c2052603f`.
La [publicación del corpus](https://doi.org/10.1371/journal.pone.0283622) describe
su tarea de simplificación léxica. Sus anotaciones no equivalen a pares completos
de simplificación sintáctica ni a evidencia clínica para dislexia/TDAH.

| Registro | Valor observado |
|---|---|
| Archivo fuente | 1 368 484 bytes |
| SHA-256 del archivo | `02aeb385fdfa8fd4f9ab3afbc5b0eeac84d514f33c8f20fa387e48068dddab06` |
| Anotaciones leídas | 5 130 |
| Decodificación | 5 153 líneas UTF-8 y 1 línea CP1252 |
| Rechazos por codificación/forma en esta fuente | 0 |
| Pares léxicos derivados: entrenamiento / validación / prueba | 6 392 / 802 / 510 |
| Subconjunto ejecutado: entrenamiento / validación / prueba | 24 / 4 / 6 |
| Semilla | 42 |
| SHA-256 del JSONL de prueba | `0a0150d78fae93d533e60f68dc275efcf43334d9dfe3b9cd4ea363f21483e2f6` |

El cargador conserva los acentos de los registros UTF-8 aunque la cabecera esté en
CP1252 y rechaza explícitamente anotaciones dañadas. Cada par sustituye una única
aparición inequívoca de una palabra compleja por un sinónimo anotado. No se generó
supervisión sintáctica ficticia. La partición inicial se hace por documento y
elimina fugas de oraciones entre particiones.

El selector ordena por SHA-256 de semilla, documento, fuente y destino; toma un
ejemplo por documento con 20–45 palabras, y exige como máximo 96 tokens tanto en la
entrada con prefijo como en el destino. No selecciona por resultado de legibilidad.
Los documentos de prueba son `120`, `276`, `68`, `30`, `200` y `84`. Los identificadores
y hashes de todas las particiones constan en el JSON de evidencia. El entrenamiento
vuelve a comprobar la separación por documento y por oración.

La fuente declara CC BY-NC-ND 4.0. El repositorio contiene código y resultados
numéricos, sin redistribuir corpus, pares derivados, predicciones textuales ni pesos.
Los artefactos locales de investigación están en rutas ignoradas por Git y separados
de los documentos de usuarios. No se usaron solicitudes de la API, datos de menores
ni participantes humanos.

## Modelo y ejecución

Se descargó el modelo [google/mt5-small](https://huggingface.co/google/mt5-small/tree/73fb5dbe4756edadc8fbe8c769b0a109493acf7a)
en la revisión `73fb5dbe4756edadc8fbe8c769b0a109493acf7a`. Se utilizó SentencePiece
nativo (`use_fast=False`), con el mismo prefijo `simplificar español: ` en
entrenamiento e inferencia. No se utilizaron servicios comerciales de inferencia.

| Configuración / comprobación | Resultado |
|---|---|
| Equipo | Apple M1, RAM 8 GiB, macOS arm64 |
| Dispositivo de ejecución | CPU, 2 hilos; sin GPU/MPS |
| Python / torch / transformers | 3.14.7 / 2.14.1 / 4.57.6 |
| peft / datasets / accelerate | 0.18.1 / 4.8.5 / 1.15.0 |
| Adaptadores | LoRA, rango 4, alfa 8, dropout 0, módulos q/v/lm_head |
| Parámetros entrenables / totales con adaptadores | 1 174 528 / 301 351 296 (0,390 %) |
| Entrenamiento | 120 pasos, batch 1, acumulación 1; 5 épocas efectivas sobre 24 pares |
| Optimizador | AdamW, learning rate inicial 0,001; weight decay 0,01 |
| Longitud máxima de entrenamiento | 96 tokens de entrada / 96 de destino; sin truncar |
| Pérdida media de entrenamiento | 15,7882320881 |
| Pérdida final de validación (4 casos) | 7,2890772820 |
| Pérdida de prueba (6 casos, teacher forcing) | 6,2381110191 |
| Tiempo de carga para entrenamiento | 6,621 s |
| Tiempo medido de entrenamiento | 30,896 s; excluye descarga, carga y guardado |
| RSS máximo del proceso de entrenamiento y fusión | 1 713 373 184 bytes (1,596 GiB) |

La pérdida de prueba con teacher forcing no mide la calidad de generación libre.
El entrenamiento rechaza pérdidas o parámetros no finitos y verifica cambios en
los parámetros entrenables. Los hashes medidos fueron:

- Antes: `f4849f0eacc11c5b470f0c5d699510619611f743ac41b3d4dca7ad0916af615c`.
- Después: `815355895521fe365d11193d6cc9e75d3cad2b3494b623711ec42249eafd50fd`.
- Adaptador guardado, 4 711 456 bytes: `34900008fd1ac48facbce26ff5a070a5818e4a524d383eebbb706917dca20ea1`.
- Checkpoint fusionado Safetensors, 1 200 729 512 bytes: `3b5f44e74c22665dc703f0481f42db7555c4f778ee6a0438e8fc0c36a120afaa`.

El checkpoint fusionado se recargó desde disco para evaluar, sin reutilizar pesos
de un modelo simulado. Permanece en `checkpoints/easier-smoke/merged`, excluido de
Git. La carga opcional del modelo permanece separada del entorno ligero de la API.

## Calibración y evaluación del sistema completo

Se ejecutaron seis comparaciones reales con `evaluate.py --hybrid`: modelo base y
checkpoint ajustado sobre tres conjuntos. Cada ejecución mide mT5 puro y el
pipeline de producción con las mismas entradas. Se mantienen las revisiones,
checkpoint, prefijo, semilla y límites de generación del ensayo anterior.

### Cambios léxicos y sintácticos

Los pares cortos `aroma → olor`, `paulatina → gradual`, `homogéneo → similar` e
`involucración → compromiso` se incorporan con restricciones y frases contextuales.
La conjunción `e` se corrige a `y` ante `compromiso`. Otros cambios se restringen al
contexto: `envergadura` se expresa como importancia en un problema sociosanitario,
no en una nave; `detectar/localizar` se acota a nuevos casos en una población.
No se copian automáticamente todas las anotaciones: algunas sustituciones aisladas
producen errores gramaticales o cambian el sentido. Las siglas y los nombres que
no se sustituyen conservan sus mayúsculas; los espacios múltiples no bloquean reglas.

Las plantillas separan medidas y su finalidad/prioridad, expresan nominalizaciones
como subobjetivos explícitos, separan una causa ya declarada y convierten glosas
nominales existentes en frases explicativas. La coordinación temporal puede repetir
el sujeto conservando la negación de cada predicado. Las relativas restrictivas,
condicionales y concesivas no se convierten en hechos independientes. Las listas
con calificadores desconocidos no se expanden mediante la plantilla de subobjetivos.

La expansión explicativa aumenta la longitud: en los cinco casos EASIER aceptados
se pasa de **33 a 49,6 palabras** en promedio. Parte de la ganancia proviene de
explicitar objetivos/glosas y reducir longitud por oración, no de resumir contenido.
La repetición de referentes es deliberada para hacer explícitas las cláusulas;
fluidez, carga de lectura y comprensión requieren evaluación humana.

La puerta mantiene delta ≥15 y adaptado ≥65 sin redondear, por chunk y por documento.
Solo original >128,535 admite mantenimiento ≥85. Números y negaciones se conservan;
el orden/cobertura se verifica frente al original canónico y sus transformaciones
estructurales acotadas. Este último control comprueba consistencia con las reglas,
no una validación semántica independiente de ellas. Candidatos fuera de la puerta
terminan en 422, sin contenido ni adaptación parcial. No se bajó ningún umbral.

### Original vs. mT5 puro vs. híbrido

Las cifras de cada fila son iguales con base y checkpoint ajustado para el híbrido.
Los modelos puros tienen 0 salidas válidas en los tres conjuntos. N/E indica que
no hay salidas válidas/aceptadas para calcular un promedio; las salidas inválidas
sí cuentan como fracasos en la cobertura. Los conjuntos no se mezclan.

| Conjunto | Entradas | Original (todas) | mT5 puro base / ajustado válidas | Híbrido aceptadas | Cumplimiento estricto entre aceptadas sin mantenimiento |
|---|---:|---:|---:|---:|---:|
| EASIER calibrado | 6 | 32,145756 | 0 / 0 | 5/6 (83.33 %) | 100 % |
| Sintético de desarrollo | 14 | 54,746347 | 0 / 0 | 10/14 (71.43 %) | 100 % |
| Auditoría EASIER nueva | 12 | 38,054496 | 0 / 0 | 0/12 (0.00 %) | N/E |

| Promedios pareados, solo adaptaciones ordinarias aceptadas | Original | mT5 puro | Híbrido adaptado | Delta híbrido |
|---|---:|---:|---:|---:|
| EASIER calibrado (5) | 29,608420 | N/E | 76,135673 | 46,527253 |
| Sintético (8, excluye 2 mantenimientos) | 47,211599 | N/E | 77,607659 | 30,396060 |
| Auditoría (ninguna) | N/E | N/E | N/E | N/E |

El cumplimiento matemático entre salidas devueltas es una garantía condicional,
no una garantía de aceptación de cualquier entrada. En sintéticos, 8/14 cumplen
la doble condición estricta y 2/14 aplican mantenimiento; 10/10 pasan puerta y
filtro léxico. En EASIER calibrado, 5/6 cumplen ambas condiciones, sin mantenimiento.
Los contadores de atribución confirman que todas esas salidas son `rules`.

| Documento EASIER de calibración | Original | mT5 puro base / ajustado | Híbrido | Delta | Resultado |
|---|---:|---|---:|---:|---|
| 120 | 58,685000 | N/E / N/E | 85,933000 | 27,248000 | Doble condición |
| 276 | 27,559390 | N/E / N/E | 71,342843 | 43,783453 | Doble condición |
| 68 | 44,832436 | N/E / N/E | N/E | N/E | 422 |
| 30 | 36,606875 | N/E / N/E | 72,564412 | 35,957537 | Doble condición |
| 200 | 14,105833 | N/E / N/E | 84,772037 | 70,666204 | Doble condición |
| 84 | 11,085000 | N/E / N/E | 66,066073 | 54,981073 | Doble condición |

El documento 68 conserva su concesión, modalidad y cuantificadores; se rechaza al
no alcanzar los dos umbrales. No se simplificaron porcentajes o grupos de pacientes
alterando su alcance para obtener una aceptación.

### Auditoría de generalización

Tras fijar las reglas, se seleccionaron 12 documentos adicionales de la partición
EASIER de prueba original, excluyendo los seis de calibración. Se usa el selector
SHA-256 existente, semilla **314159**, un ejemplo por documento, 20–45 palabras y
máximo 96 tokens con prefijo/destino. No se escogieron por legibilidad ni por éxito.
Los documentos son `225`, `147`, `42`, `218`, `124`, `210`, `93`, `260`, `257`, `238`,
`156` y `215`. SHA-256 del JSONL:
`1ea48bf42bb429bdb5a5f86f9d6c004a26ebde4bc6d55889022b2915985ac4b6`.

El resultado fue 0/12 tanto con base como con checkpoint. No se añadieron reglas
usando esas fuentes tras observar este resultado. Es una auditoría interna pequeña,
no un estudio ciego clínico. La diferencia **83,33 % en calibración vs. 0 % en
esta auditoría** limita expresamente cualquier afirmación de generalización.
Hacen falta léxico y sintaxis más amplios revisados, además de evaluación humana
independiente de significado, gramática y comprensión.

## Tiempos medidos después de calibrar

CPU M1, dos hilos, generación pura con dos beams, hasta tres intentos con beams
2/4/6 y 64 tokens generados. Entrada máxima 96 tokens para EASIER y 512 para los
sintéticos. Incluye tokenización, generación y decodificación; el híbrido añade
reglas, controles y reintentos. Incluye el primer caso, excluye carga y descarga,
HTTP y base de datos. Máquina de desarrollo con carga variable: no es un benchmark
de producción, concurrencia o documentos de 500–800 palabras.

| Conjunto / modelo | Media mT5 puro (s) | Media híbrido (s) | p95 híbrido (s) |
|---|---:|---:|---:|
| Calibración / base | 0,246747 | 0,117977 | 0,686199 |
| Calibración / tuned | 2,477007 | 1,534379 | 9,184178 |
| Sintético / base | 0,180119 | 0,206049 | 0,774073 |
| Sintético / tuned | 1,620364 | 1,294376 | 8,350231 |
| Auditoría / base | 0,226056 | 0,701620 | 0,934875 |
| Auditoría / tuned | 2,200074 | 6,619282 | 10,965355 |

Las reglas se prueban antes de generar; los rechazos aún pagan reintentos del
modelo. Las métricas temporales completas y por caso figuran en el JSON actual.

## Reproducción

Desde la raíz del repositorio, activar un entorno separado con las dependencias de
`ml_training/requirements.txt`. En esta ejecución se usó `ml_training/.venv` con
Python 3.14.7. Los comandos siguientes usan el `python` de ese entorno. En macOS/Linux:

```sh
export HF_HOME="$PWD/.cache/huggingface"
export HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_XET=1
export TOKENIZERS_PARALLELISM=false OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
export MAX_GENERATION_ATTEMPTS=3
```

Descargar explícitamente los insumos de investigación fijados y comprobar el hash:

```python
from pathlib import Path
from urllib.request import urlretrieve
import hashlib
from huggingface_hub import snapshot_download

source = Path("datasets/EASIER/SGSS.csv")
source.parent.mkdir(parents=True, exist_ok=True)
urlretrieve(
    "https://raw.githubusercontent.com/LURMORENO/EASIER_CORPUS/"
    "f0b8312d1ded3d674a7d96d0fb2dc00c2052603f/SGSS.csv", source
)
assert hashlib.sha256(source.read_bytes()).hexdigest() == (
    "02aeb385fdfa8fd4f9ab3afbc5b0eeac84d514f33c8f20fa387e48068dddab06"
)
base = snapshot_download(
    "google/mt5-small",
    revision="73fb5dbe4756edadc8fbe8c769b0a109493acf7a",
    allow_patterns=["config.json", "generation_config.json", "pytorch_model.bin",
                    "spiece.model", "tokenizer_config.json", "special_tokens_map.json"],
)
Path("ml_training/output").mkdir(parents=True, exist_ok=True)
Path("ml_training/output/base-model-path.txt").write_text(base, encoding="utf-8")
```

```sh
python -m ml_training.prepare_easier --sgss datasets/EASIER/SGSS.csv --output ml_training/data/easier-full
python -m ml_training.select_subset --data ml_training/data/easier-full --output ml_training/data/easier-smoke --tokenizer "$(cat ml_training/output/base-model-path.txt)"
python -m ml_training.train --config ml_training/configs/mt5_small_smoke.yaml --data ml_training/data/easier-smoke --output checkpoints/easier-smoke
python -m ml_training.evaluate --data ml_training/data/easier-smoke/test.jsonl --checkpoint "$(cat ml_training/output/base-model-path.txt)" --output ml_training/output/base-evaluation.json --max-input-tokens 96 --max-new-tokens 64 --num-beams 2 --threads 2
python -m ml_training.evaluate --data ml_training/data/easier-smoke/test.jsonl --checkpoint checkpoints/easier-smoke/merged --output ml_training/output/finetuned-evaluation.json --max-input-tokens 96 --max-new-tokens 64 --num-beams 2 --threads 2 --hybrid
```

El manifiesto del entrenamiento guarda configuración, versiones, procedencia,
hashes, parámetros, pasos, pérdidas, duración y RSS. Los comandos de evaluación
guardan métricas agregadas y resultados numéricos por documento. Los tiempos
variarán entre ejecuciones. Los hashes de pesos también pueden variar con versiones
o kernels diferentes; los hashes del corpus y de las particiones permiten comprobar
que los datos coinciden.

### Repetir la calibración actual y la auditoría

Cada comando `--hybrid` obtiene las métricas puras y del sistema completo. Ejecutar
para ambos checkpoints, usando `base` o `tuned` como etiqueta de salida:

```sh
python -m ml_training.evaluate --data ml_training/data/easier-smoke/test.jsonl --checkpoint checkpoints/easier-smoke/merged --output ml_training/output/calibrated-easier-tuned.json --max-input-tokens 96 --max-new-tokens 64 --num-beams 2 --threads 2 --hybrid
python -m ml_training.evaluate --data ml_training/fixtures/hybrid_es.json --checkpoint checkpoints/easier-smoke/merged --output ml_training/output/calibrated-diagnostic-tuned.json --max-input-tokens 512 --max-new-tokens 64 --num-beams 2 --threads 2 --hybrid
```

Crear la muestra de auditoría con los datos preparados y el tokenizer fijado:

```python
import json
from pathlib import Path
from transformers import AutoTokenizer
from ml_training.select_subset import select_rows

excluded = set(json.loads(Path("ml_training/data/easier-smoke/manifest.json").read_text())["selected_documents"]["test"])
rows = [json.loads(line) for line in Path("ml_training/data/easier-full/test.jsonl").read_text(encoding="utf-8").splitlines()]
rows = [row for row in rows if row["document_id"] not in excluded]
tokenizer = AutoTokenizer.from_pretrained(Path("ml_training/output/base-model-path.txt").read_text().strip(), local_files_only=True, use_fast=False)
selected = select_rows(rows, tokenizer, 12, seed=314159, max_tokens=96)
folder = Path("ml_training/data/easier-audit")
folder.mkdir(exist_ok=True)
(folder / "test.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in selected), encoding="utf-8")
```

```sh
python -m ml_training.evaluate --data ml_training/data/easier-audit/test.jsonl --checkpoint checkpoints/easier-smoke/merged --output ml_training/output/calibrated-audit-tuned.json --max-input-tokens 96 --max-new-tokens 64 --num-beams 2 --threads 2 --hybrid
```

Repetir los tres comandos con `--checkpoint "$(cat ml_training/output/base-model-path.txt)"`
y etiquetas `base`. La evidencia numérica conserva configuración, hashes, resultados
por documento y atribución. No se vuelve a entrenar para esta comparación.

## Alcance académico y trabajo pendiente

Se realizaron ensayos exploratorios previos de 12 y 120 pasos con LoRA q/v.
Tampoco produjeron salidas válidas. El diagnóstico descubrió que un evaluador
inicial podía asignar legibilidad artificial a marcadores internos; ese defecto
se corrigió y las cifras publicadas se recalcularon. El ensayo final añadió
`lm_head` a los módulos adaptados manteniendo 120 pasos. **Se consultó el conjunto
de prueba durante esos diagnósticos**, por lo que no es una validación ciega
independiente ni una base para afirmar generalización. No se ocultaron estos
fracasos ni se alteraron los umbrales para obtener aceptación.

La muestra es pequeña y la supervisión solo léxica. Antes de considerar el modelo
para uso con lectores se requiere un conjunto independiente, más datos revisados
de simplificación sintáctica, selección de hiperparámetros exclusivamente en
validación y evaluación humana de gramática, hechos, negación, significado y
comprensión. Después deberá evaluarse con la población objetivo mediante un
protocolo apropiado. El resultado entregado aquí es una ejecución técnica
verificable con controles de rechazo funcionando y evidencia negativa de calidad.

La batería sintética actual comprueba comportamiento conocido del motor, no
validez externa. La calibración explícita de reglas sobre seis documentos no convierte su nueva
aceptación en validación positiva del checkpoint ni en un resultado independiente. Los resultados justifican mantener
la puerta de rechazo y continuar con supervisión y evaluación humana independientes
antes de afirmar preservación semántica o eficacia clínica general.
