# v2.2: ranking léxico independiente y calibración estructural

27 de octubre de 2026. **El cierre académico al 100% sigue sin estar demostrado.**
`acceptance_criteria_met = false` es el resultado real. Se mejoró la precisión
léxica y la cobertura de bandas, pero no se ha superado el baseline SARI ni se
han alcanzado todas las bandas del nivel 1. No se redondean decisiones ni se
cambia la fórmula, las fuentes, las referencias o las bandas para declarar éxito.
El [informe v2.1](model-retraining-v2.1.md) conserva el estado anterior.

## Separación de objetivos y entrenamiento real

El ranker léxico recibe texto y candidatos, sin edad, nivel solicitado, banda ni
penalización estructural. Usa 37 características: la proyección léxica invariante
de v2.1, rango de candidato observado en train, frecuencia de propuestas y de
palabras en fuentes únicas de train, semejanza de raíz y señales parciales de
concordancia. Estas señales no constituyen un analizador morfológico completo ni
una norma representativa de frecuencia del español.

`train_separated.py` ajusta regresión regularizada de **delta SARI respecto a
identidad**, ejecuta 35 rondas de árboles residuales de profundidad 3 y selecciona
la ronda por validación. El checkpoint elegido contiene el ajuste lineal y **2
árboles** (etapa seleccionada 3 de las 36 registradas). Una cabeza léxica separada
se entrena durante 35 épocas por pares. `calibrate_lexical.py` elige en validation
el peso de confianza léxica, costo de ediciones y margen; nunca usa bandas.
Política final: peso **0.4**, costo **0.3**, margen **0.02**. Pérdida MSE del ajuste
seleccionado: train **0.006236018**, validation **0.018156266**.
La política completa alcanza SARI **65.526486** en validation.

Un ensayo adicional de 40 épocas optimizó directamente el SARI esperado de los
grupos de candidatos. No mejoró la validación del padre (la etapa elegida fue 0),
por lo que **no se activó ni se evaluó en test**. Su historial se conserva en el
reporte numérico. Estos son rankers CPU entrenados realmente; no se presenta este
trabajo como un nuevo fine-tuning convergido de mT5 ni como entrenamiento en GPU.

## Datos, aislamiento y alcance de test

Se conserva Dataset v2.1: **4.738 pares**, 4.108 train / 402 validation / 228 test.
Incluye 2.282 propuestas EASIER filtradas, 2.420 formas morfológicas sintéticas y
36 pares sintácticos. No se reescribe SGSS ni las referencias para favorecer el
resultado. SHA-256 del CSV original:
`02aeb385fdfa8fd4f9ab3afbc5b0eeac84d514f33c8f20fa387e48068dddab06`.

Las particiones verifican hashes e intersecciones vacías de documentos, fuentes
y familias registradas. Priors/frecuencias se calculan solo con train. Gradientes,
épocas, pesos de política y márgenes se ajustan con train/validation; el programa
escribe la selección congelada antes de calcular su test. Las referencias de
validation/test no se insertan en el conjunto generado de candidatos.

**Test ya fue observado durante este proyecto, también en iteraciones de esta
fase. No es una evaluación ciega externa y no se afirma cero influencia de su
observación en el desarrollo.** Los gradientes y la calibración no acceden a sus
etiquetas, pero eso por sí solo no restablece un holdout ciego. Se necesita un
nuevo conjunto externo bloqueado antes de sostener generalización independiente.
Los seis casos EASIER y los seis textos controlados también son diagnósticos de
desarrollo conocidos, no un nuevo holdout. La partición validation contiene 212
casos EASIER y 190 sintéticos; sus métricas separadas evitan confundir el buen
resultado morfológico con generación libre sobre EASIER.

## Comparación numérica con baseline congelado

El baseline se ejecuta desde `fc12a7a`, con los mismos 228 originales/referencias.
SARI mide selección de candidatos **antes** de la calibración estructural. Top-1
es otra tarea: selección de un span entre original, distractor de la misma
partición y opción anotada. La distancia a banda se mide con la salida estructural
real para los mismos 228 textos y niveles suministrados; no se introduce en el
ranker léxico. Las tres cifras no son un único SARI del texto final calibrado.

| Métrica | Baseline | v2.2 | Cumple |
|---|---:|---:|---|
| SARI | 44.543847868 | 44.539664723 | **No** |
| Exactitud léxica top-1 | 53.070175% | 73.245614% | Sí |
| Distancia media a banda, menor es mejor | 22.506361988 | 22.396247054 | Sí |

Diferencia SARI sin redondear: **-0.004183145351**.
No alcanza la desigualdad estricta solicitada. El incremento top-1 no equivale
a una validación de fidelidad semántica del documento ni de comprensión infantil.

Se conservan resultados negativos intermedios de SARI: 43.433457 (residual inicial),
43.341135 (ponderación por fuente), 43.255120 (frecuencias y selección EASIER),
44.329986 (confianza léxica calibrada) y 44.539665 (política final por validation).
Los pesos finales se reproducen con los scripts actuales; las primeras iteraciones
correspondían a implementaciones provisionales, no a una búsqueda por test de
pesos que después se presenten como ciegos.

SARI usa conjuntos de n-gramas Unicode 1–4, keep-F1/add-F1/delete-precision,
operación vacía/vacía igual a 1 y escala 0–100. Se mantiene la variante declarada,
sin cambiar tokenización para alterar la comparación. El corpus y la supervisión
sintética no incluyen cinco paráfrasis humanas revisadas por edad de cada texto.

## Calibrador analítico y resultados completos

Las bandas permanecen: N1 **82–100**, N2 **74–84**, N3 **65–74**, N4 **58–66**,
N5 **50–65**. Se aplican perífrasis españolas explícitas, sin derivar cualquier
palabra por su sufijo, y se miden candidatos tras cada pasada. Se dividen cláusulas
afirmativas con propósito sin afirmar que ese propósito se logró, se conserva
el ámbito condicional/negativo y se coordinan enunciados completos para ajustar
longitud en ambas direcciones. Las cifras y las negaciones no se eliminan para
forzar una banda. Los empates usan el texto como desempate estable y se verifican
en procesos con semillas hash distintas; el catálogo excluye la identidad cuando
dispone de paráfrasis, evitando un 503 de generación por escoger la fuente intacta. Las glosas están vinculadas a términos presentes; no se agregan
plantillas sobre investigar un tema.

Para niveles avanzados se permite una coordinación más exigente que la fuente
original sencilla. El delta negativo se publica con
`advanced_level_harder_than_source`; nivel 1 no degrada el original. La estructura
no redefine los pesos del ranker. Se retiraron reglas que podían producir doble
negación, discordancia de determinantes o pérdida de precisión científica. Las
reglas no prueban equivalencia semántica universal: sigue siendo necesaria una
revisión humana del material académico.

| Conjunto | Progresión estricta | Cinco bandas simultáneas |
|---|---:|---:|
| local_bank | 31/31 | 13/31 |
| easier_diagnostic | 6/6 | 2/6 |
| unseen_v2 | 6/6 | 5/6 |
| managed_demos | 15/15 | 7/15 |

| Conjunto | N1 | N2 | N3 | N4 | N5 |
|---|---:|---:|---:|---:|---:|
| local_bank | 13/31 | 28/31 | 31/31 | 31/31 | 31/31 |
| easier_diagnostic | 3/6 | 6/6 | 6/6 | 5/6 | 6/6 |
| unseen_v2 | 5/6 | 6/6 | 6/6 | 6/6 | 6/6 |

Las **15/15 demos** cumplen la banda del nivel que se les asignó (1, 2, 4 o 5),
pero **7/15** tienen todos sus cinco previews dentro de banda. No se confunden
ambas medidas. La principal deuda es nivel 1; la condición histórica delta ≥15 y
score ≥65 se publica aparte y no se afirma para los niveles avanzados 4/5.
Una entrada válida que no alcance las metas conserva 200 y su mejor lectura;
una palabra como «Hola» no recibe cinco niveles inventados ni un éxito falso.

## Inferencia y rendimiento

| Evaluación, cinco niveles juntos | Media CPU |
|---|---:|
| local_bank | 0.3565 s |
| easier_diagnostic | 0.1933 s |
| unseen_v2 | 0.1216 s |

Tiempos locales de diagnóstico, sin afirmar percentiles bajo concurrencia.
La búsqueda analiza solo candidatos estructurales cercanos antes del desempate
léxico. En documentos largos analiza cláusulas completas y reutiliza las
repetidas dentro de la solicitud, midiendo después el texto compuesto completo.
Un bloque repetitivo de 20 copias del Texto B pasó de **12.84 s** a **0.78 s**
en la comprobación local. La caché silábica vive dentro del chunk y se limpia
al salir o fallar; no se guarda texto privado en cachés globales.

## Contrato, PostgreSQL y despliegue

Texto, generación, TXT/PDF y GET conservan original, adaptación, puntajes reales,
ganancia, palabras/oración, sílabas/palabra, sustituciones, cinco previews, versión
y checkpoint. Nivel explícito gana sobre edad; edad explícita decide preguntas;
el cumpleaños real del perfil se conserva. Los errores de entrada usan mensajes
en español de una lista permitida, sin devolver el texto rechazado. Las rutas
conservan RBAC, login por formulario, telemetría infantil y de adulto independiente.

Checkpoint activo: `context-ranker-es-v2.2`, nombre `context-ranker-v2.2`; calibrador `pedagogical-es-v2.2.1`.
El JSON en `app/services/assets/` y el de `checkpoints/` son idénticos; SHA-256
`6ce2fcf01c885f872dde4e344a0a3cb360c908c673bdd01e53187537e15b867b`. No requiere NumPy/Torch para servir. Se regeneraron las
15 demos en PostgreSQL con recursos y práctica preservados; refresh es idempotente.
No se cambian columnas: Alembic mantiene sus ocho revisiones y head
`0007_master_accounts`.

Docker/Compose incluyen ese artefacto; bootstrap aplica migraciones antes de
abrir HTTP. La [guía DigitalOcean](../deploy/README.md) explica HTTPS por dominio/IP,
puerto 443, firewall y CORS exacto para web; Android nativo funciona sin Origin.
No se afirma haber desplegado un Droplet remoto.

## Reproducción y comprobaciones

```sh
python -m pip install 'numpy>=2,<3'
python -m ml_training.build_enhanced_dataset
python -m ml_training.train_separated
python -m ml_training.calibrate_lexical
# Ablación adicional, no activada si no mejora validation:
python -m ml_training.train_expected_sari
MT5_ENABLED=false python -m ml_training.export_separated
pytest -q
```

Se necesita SGSS local y el historial Git que contiene `fc12a7a`. El corpus,
JSONL derivados, pesos grandes y secretos siguen ignorados. El reporte numérico
versionado es `checkpoints/retraining_metrics.json`; contiene hashes, pérdidas,
políticas y métricas exactas. Las verificaciones finales se registran en `docs/verification.md`: PostgreSQL
562 aprobadas; SQLite 557 aprobadas y 5 omitidas por ser exclusivas de PostgreSQL.
El ajuste final del seed registrado solo cambió metadatos; se repitieron sus
pruebas de integridad de checkpoint después de actualizar el SHA-256.
