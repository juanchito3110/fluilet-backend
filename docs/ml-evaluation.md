# Evaluación técnica de mT5 + EASIER

**Fluilet · 19 de octubre de 2026 · Entregable para el asesor Aldo Maciel**

Se ejecutaron preparación del corpus real, fine-tuning LoRA de `google/mt5-small`,
guardado y recarga del checkpoint e inferencia con el sistema híbrido completo.
La calibración actual conserva los pesos del ensayo de 120 pasos y cambia la
orquestación: evalúa primero un candidato determinista; si no pasa la puerta,
ejecuta mT5 y refinamiento con reintentos acotados. No modifica los umbrales.

**Resultado:** el sistema aceptó 8/14 casos sintéticos de diagnóstico. Las seis
adaptaciones sin excepción pasaron, en promedio pareado, de **46,686563 a
78,204363** (delta **31,517800**), con 6/6 cumpliendo ambas condiciones. Las otras
dos salidas aplicaron la excepción explícita de mantenimiento. Las seis entradas
EASIER originales siguen con 0/6 aceptaciones: la batería sintética no las sustituye.
Las ocho salidas aceptadas fueron producidas por reglas, sin atribuir ese mérito
a mT5. El checkpoint aislado continúa sin estar listo para uso clínico.

La evidencia actual está en [hybrid-evaluation-results.json](hybrid-evaluation-results.json).
La primera corrida y el entrenamiento permanecen documentados en
[ml-evaluation-results.json](ml-evaluation-results.json). Ambos contienen métricas
numéricas y procedencia, sin textos del corpus. Ninguna corrida constituye una
validación humana de significado, comprensión o eficacia clínica.

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

## Evaluación formal del sistema completo

Se ejecutó `evaluate.py --hybrid` cuatro veces: base y checkpoint ajustado, cada
uno sobre EASIER (6 casos) y sobre una batería sintética (14 casos). Cada ejecución
mide generación pura y el `AdaptationPipeline` real sobre exactamente las mismas
entradas. El modelo se recarga desde disco; no se simulan predicciones. El hash del
checkpoint fusionado coincide con el publicado en la corrida inicial. No hubo
nuevo entrenamiento de pesos en esta calibración.

La batería [hybrid_es.json](../ml_training/fixtures/hybrid_es.json) es un conjunto
fijo de diagnóstico creado durante desarrollo, con léxico cubierto, coordinación,
relativas, negaciones, números, vocabulario no cubierto y mantenimiento. Contiene
éxitos y rechazos; no se filtraron casos según su resultado. Es distinta de EASIER
y no es un conjunto clínico o ciego. Su referencia textual es el original, por lo
que su F1 léxico mide solapamiento, no calidad frente a una simplificación humana.
No se mezclan ambos conjuntos en una tasa global.

### Qué garantiza la puerta

Se aplica sin redondear:

`Szigriszt = 206.835 − 62.3 × (sílabas / palabras) − (palabras / oraciones)`.

Una salida ordinaria solo se devuelve si **adaptado − original ≥15,0** y
**adaptado ≥65,0**, tanto por chunk como por documento. Si original >128,535, la
excepción requiere adaptado ≥85,0 y se informa separadamente. No se recortan los
índices a 0–100. El redondeo de las tablas ocurre después de decidir.

También se exige el control automático de fidelidad: conservar números,
negaciones, cobertura y orden léxico canónico; las divisiones sintácticas se
restringen a patrones reconocidos con sujeto explícito. Marcadores internos de
mT5 como `<extra_id_0>` son inválidos aunque sobrevivan al decodificador.

**La garantía matemática es condicional a devolver una adaptación.** No garantiza
que toda entrada sea aceptada ni demuestra equivalencia semántica universal. La
preservación semántica se protege con reglas conservadoras y el filtro automático;
requiere revisión humana independiente para validarla. Cuando no hay candidato
válido se devuelve HTTP 422, sin texto ni resultados parciales. Un rechazo correcto
no se contabiliza como una simplificación exitosa.

### EASIER: conjunto original conservado

| Métrica (6 entradas) | Texto original | mT5 puro base | mT5 puro ajustado | Híbrido con base / ajustado |
|---|---:|---:|---:|---:|
| Puntaje original promedio | 32,145756 | 32,145756 | 32,145756 | 32,145756 |
| Salidas válidas / aceptadas | — | 0/6 | 0/6 | 0/6 / 0/6 |
| Puntaje adaptado promedio | — | N/E | N/E | N/E |
| Delta promedio | — | N/E | N/E | N/E |
| Doble condición sobre todas las entradas | — | 0 % | 0 % | 0 % |
| Cumplimiento entre aceptadas | — | N/E | N/E | N/E |

No hubo entradas elegibles para mantenimiento. El refinador conservador no
resuelve esta muestra y mT5 no aportó candidatos aceptables. El resultado negativo
se mantiene visible; no se reemplaza por los casos favorables del diagnóstico.

### Diagnóstico sintético: Original vs. mT5 puro vs. Fluilet

| Métrica (14 entradas) | Texto original | mT5 puro base | mT5 puro ajustado | Sistema híbrido (base y ajustado) |
|---|---:|---:|---:|---:|
| Puntaje original, todas las entradas | 54,746347 | 54,746347 | 54,746347 | 54,746347 |
| Salidas válidas / aceptadas | — | 0/14 | 0/14 | 8/14 (57,14 %) |
| Original pareado, solo las 8 aceptadas | — | N/E | N/E | 70,023672 |
| Adaptado promedio, solo las 8 aceptadas | — | N/E | N/E | 93,662022 |
| Delta promedio, solo las 8 aceptadas | — | N/E | N/E | 23,638350 |
| Cumplimiento estricto entre aceptadas sin mantenimiento | — | N/E | N/E | 6/6 (100 %) |
| Doble condición sobre todas las entradas | — | 0/14 | 0/14 | 6/14 (42,86 %) |
| Excepción de mantenimiento aceptada | 2 elegibles | 0 | 0 | 2/14 |
| Puerta matemática + filtro léxico entre aceptadas | — | N/E | N/E | 8/8 (100 %) |
| Rechazos del sistema completo | — | — | — | 6/14 (42,86 %) |

N/E significa no evaluable: no hay salidas válidas/aceptadas para ese promedio o
denominador. Las salidas inválidas cuentan como fracasos en las tasas sobre todas
las entradas. No se interpretan marcadores de mT5 como texto español legible.
Los promedios adaptados y deltas son pareados sobre las mismas entradas aceptadas,
no sobre las 14 entradas iniciales. Las ocho aceptadas incluyen dos mantenimientos
con delta cero.

Separando mantenimiento, las **seis adaptaciones ordinarias** tienen promedio
original **46,686563**, adaptado **78,204363** y delta **31,517800**. Cada una cumple
los umbrales sin redondear; el 100 % de cumplimiento condicional no equivale al
100 % de cobertura. Ambos modelos produjeron el mismo resultado híbrido: 8 salidas
`rules`, 6 rechazos y 18 llamadas a generación en los casos no resueltos. El modelo
no fue necesario para las ocho salidas aceptadas.

| Caso sintético | Original | mT5 puro base / ajustado | Híbrido: adaptado | Delta | Resultado |
|---|---:|---|---:|---:|---|
| lexical-school | 37,085 | N/E / N/E | 77,135 | 40,050 | Doble condición |
| lexical-teachers | 28,185 | N/E / N/E | 68,235 | 40,050 | Doble condición |
| lexical-tutors | 45,985 | N/E / N/E | 86,035 | 40,050 | Doble condición |
| negation | 46,766 | N/E / N/E | 81,810 | 35,044 | Doble condición |
| numbers | 27,298 | N/E / N/E | N/E | N/E | 422 |
| negation-numbers | 36,546 | N/E / N/E | N/E | N/E | 422 |
| coordination | 71,651 | N/E / N/E | 87,393 | 15,742 | Doble condición |
| relative | 61,027 | N/E / N/E | N/E | N/E | 422 |
| independent-clauses | 77,800 | N/E / N/E | N/E | N/E | 422 |
| argument-order | 50,448 | N/E / N/E | 68,618 | 18,171 | Doble condición |
| unsupported-vocabulary | -84,965 | N/E / N/E | N/E | N/E | 422 |
| already-readable-no-rule | 88,553 | N/E / N/E | N/E | N/E | 422 |
| maintenance | 140,535 | N/E / N/E | 140,535 | 0,000 | Mantenimiento |
| maintenance-negation | 139,535 | N/E / N/E | 139,535 | 0,000 | Mantenimiento |

Los rechazos incluyen `relative` (el candidato determinista mejora solo 14,630769
puntos), `independent-clauses` (13 puntos) y casos con números cuyo candidato no
alcanza 65. Esto muestra que el sistema conserva las dos condiciones incluso cuando
el filtro léxico pasa. Los números y las negaciones no se eliminan para mejorar
artificialmente el puntaje. Estos candidatos diagnósticos no se devuelven al cliente.

## Tiempos medidos

Se midió tokenización + generación + decodificación de mT5 puro; el híbrido incluye
refinamiento, reintentos y controles por chunk/documento. Se incluye el primer caso
sin descartar calentamiento. La carga se mide por separado. No se incluyen descarga,
HTTP, PostgreSQL o red. Se usaron CPU M1, dos hilos, dos beams para generación pura,
hasta tres intentos híbridos con beams 2/4/6 y un máximo de 64 tokens generados.
EASIER conserva su límite de 96 tokens de entrada; el diagnóstico usa 512 para
incluir las entradas sintácticas y de rechazo completas, sin truncarlas.

| Conjunto / modelo | Media mT5 puro (s) | Media híbrido (s) | Mediana híbrido (s) | p95 híbrido (s) | Carga (s) |
|---|---:|---:|---:|---:|---:|
| EASIER / base | 0,439 | 2,346 | 2,237 | 3,787 | 6,616 |
| EASIER / ajustado | 2,931 | 7,989 | 8,214 | 12,441 | 1,457 |
| Diagnóstico / base | 0,312 | 0,406 | 0,004 | 1,175 | 6,006 |
| Diagnóstico / ajustado | 2,978 | 2,368 | 0,006 | 10,049 | 1,303 |

La política evita generar cuando las reglas ya cumplen. Las entradas rechazadas
siguen pagando los reintentos de mT5 y pueden aumentar la media. Las diferencias
entre formatos/caché de carga no son una mejora atribuible al fine-tuning. Con
n=6/14 el p95 empírico coincide con el máximo; no estima la latencia de producción.
No son pruebas de concurrencia ni documentos de 500–800 palabras. Los tiempos de
la corrida inicial siguen disponibles como registro histórico en el JSON anterior.

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

### Repetir la comparación actual

Después de preparar los datos y disponer del snapshot/checkpoint anteriores, cada
comando con `--hybrid` produce tanto métricas puras como del sistema completo:

```sh
python -m ml_training.evaluate --data ml_training/data/easier-smoke/test.jsonl --checkpoint "$(cat ml_training/output/base-model-path.txt)" --output ml_training/output/easier-base-hybrid.json --max-input-tokens 96 --max-new-tokens 64 --num-beams 2 --threads 2 --hybrid
python -m ml_training.evaluate --data ml_training/data/easier-smoke/test.jsonl --checkpoint checkpoints/easier-smoke/merged --output ml_training/output/easier-tuned-hybrid.json --max-input-tokens 96 --max-new-tokens 64 --num-beams 2 --threads 2 --hybrid
python -m ml_training.evaluate --data ml_training/fixtures/hybrid_es.json --checkpoint "$(cat ml_training/output/base-model-path.txt)" --output ml_training/output/diagnostic-base-hybrid.json --max-input-tokens 512 --max-new-tokens 64 --num-beams 2 --threads 2 --hybrid
python -m ml_training.evaluate --data ml_training/fixtures/hybrid_es.json --checkpoint checkpoints/easier-smoke/merged --output ml_training/output/diagnostic-tuned-hybrid.json --max-input-tokens 512 --max-new-tokens 64 --num-beams 2 --threads 2 --hybrid
```

El hash de la batería sintética y las cuatro salidas numéricas están en
`hybrid-evaluation-results.json`. Las tasas globales usan todos los casos; las
condicionales usan solo las aceptadas, separando mantenimiento. La atribución al
experto y el contador de llamadas permiten auditar qué parte del sistema produjo
el resultado.

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
validez externa. El cambio de prioridad de candidatos no convierte los 0/6 de
EASIER en una validación positiva del modelo. Los resultados justifican mantener
la puerta de rechazo y continuar con supervisión y evaluación humana independientes
antes de afirmar preservación semántica o eficacia clínica general.
