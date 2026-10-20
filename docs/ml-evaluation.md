# Evaluación técnica de mT5 + EASIER

**Fluilet · 19 de octubre de 2026 · Entregable para el asesor Aldo Maciel**

Se ejecutaron preparación del corpus real, fine-tuning LoRA de `google/mt5-small`,
guardado y recarga del checkpoint e inferencia con el pipeline híbrido de la API.
El entrenamiento modificó los pesos y produjo pérdidas finitas. Sin embargo, en
los seis ejemplos de prueba exploratoria el modelo generó salidas con marcadores
internos y ninguna adaptación superó la aceptación. **El checkpoint no está listo
para uso clínico ni se activó en la configuración de la API.**

Los resultados completos, sin textos del corpus, están en
[ml-evaluation-results.json](ml-evaluation-results.json). Esta evaluación comprueba
la ejecución del sistema y sus límites; no constituye un estudio de comprensión,
eficacia clínica o validación con pacientes.

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

## Legibilidad y aceptación observadas

Se aplica sin redondear:

`Szigriszt = 206.835 − 62.3 × (sílabas / palabras) − (palabras / oraciones)`.

El cumplimiento estricto exige simultáneamente **delta ≥ 15,0 y adaptado ≥ 65,0**.
La excepción de mantenimiento exige original > 128,535 y adaptado ≥ 85,0; se
contabiliza por separado. Ninguno de los seis originales califica para esa excepción.
No se recortan los índices al intervalo 0–100. Los decimales de las tablas solo
se redondean para presentación, después de tomar las decisiones.

| Métrica, denominador de 6 casos | mT5 base | mT5 ajustado | Híbrido ajustado + reglas |
|---|---:|---:|---:|
| Szigriszt-Pazos original promedio | 32,145755746 | 32,145755746 | 32,145755746 |
| Salidas válidas / adaptaciones aceptadas | 0/6 válidas | 0/6 válidas | 0/6 aceptadas |
| Szigriszt-Pazos adaptado promedio | N/E | N/E | N/E |
| Delta promedio | N/E | N/E | N/E |
| Cumplimiento estricto delta ≥15 y adaptado ≥65 | 0 % | 0 % | 0 % |
| Elegibilidad para mantenimiento | 0 % | 0 % | 0 % |
| Salidas que superan fidelidad léxica | 0 % | 0 % | 0 % aceptadas |

**N/E significa no evaluable:** no existe ninguna salida válida/aceptada sobre la
que calcular el promedio adaptado o el delta. Sustituirlo por cero o puntuar
marcadores internos como texto español produciría una conclusión falsa. Las
salidas inválidas sí cuentan como fracasos en el denominador de las tasas.

`evaluate.py` invalida marcadores como `<extra_id_0>` aunque el decodificador los
conserve al omitir tokens especiales. El control de fidelidad de ejecución aplica
el mismo rechazo. También comprueba números, negaciones, cobertura y orden léxico;
es un filtro conservador, no una prueba semántica o clínica.

El híbrido se ejecutó con `AdaptationPipeline` y `MT5Runtime` reales, nivel 3,
refinamiento determinista habilitado y hasta tres intentos con beams 2/4/6. En los
seis casos terminó con `acceptance_failed`, que la API traduce a HTTP 422 sin texto
ni adaptación parcial. El vocabulario manual de respaldo es de estilo EASIER,
independiente de los sinónimos anotados utilizados para entrenar. No alcanzó la
doble condición en esta muestra.

## Tiempos de inferencia

Generación determinista, entrada de hasta 96 tokens y salida de hasta 64 tokens.
La inferencia directa usa dos beams. Se midió tokenización + generación +
decodificación con reloj monotónico, incluyendo el primer caso y sin descartar
calentamiento. El híbrido incluye sus reintentos, refinamiento y controles, con el
modelo ya cargado. Se excluyen HTTP, red, base de datos y descarga de pesos.

| Tiempo en segundos, 6 casos | Base | Ajustado | Híbrido |
|---|---:|---:|---:|
| Promedio | 0,251 | 3,002 | 7,689 |
| Mediana | 0,211 | 3,060 | 8,538 |
| p95 empírico | 0,410 | 5,747 | 10,217 |
| Primer caso | 0,410 | 5,747 | 10,186 |
| Total | 1,507 | 18,012 | 46,132 |
| Carga independiente del modelo | 5,698 | 0,703 | reutiliza modelo ajustado |

Con n=6 el p95 empírico coincide con el máximo y no estima una latencia de
producción. La carga base y la del checkpoint utilizan formatos y estados de
caché diferentes; no permiten atribuir una mejora de carga al entrenamiento.
Estos tiempos corresponden a oraciones cortas seleccionadas y no representan
documentos de 500–800 palabras, concurrencia móvil o un VPS.

## Reproducción

Desde la raíz del repositorio, activar un entorno separado con las dependencias de
`ml_training/requirements.txt`. En esta ejecución se usó `ml_training/.venv` con
Python 3.14.7. Los comandos siguientes usan el `python` de ese entorno. En macOS/Linux:

```sh
export HF_HOME="$PWD/.cache/huggingface"
export HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_XET=1
export TOKENIZERS_PARALLELISM=false OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
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
