# Longitud de las fuentes de lecciones generadas

`POST /api/v1/adaptations/generate` selecciona un extracto antes de llamar al NLP,
para Wikipedia, el banco local y cualquier respaldo local de Wikipedia:

| Edad efectiva | Presupuesto de palabras de la fuente |
|---|---:|
| 6–8 | 120 |
| 9–11 | 180 |
| 12+ | 240 |

Se conservan oraciones completas y un prefijo consecutivo de la fuente, incluidos
sus límites de párrafo. La última oración que excedería el presupuesto se omite.
El mínimo de tres oraciones tiene prioridad si esas tres solas superan el límite;
si la fuente contiene menos de tres, se conserva sin inventar contenido.
`clean_extract` utiliza los mismos presupuestos al limpiar un extracto.

La edad explícita prevalece sobre la del perfil; sin edad explícita se usa su edad
pedagógica efectiva. Para solicitudes sin perfil se mantiene la resolución actual
por nivel/edad y el grupo por defecto 12+. El presupuesto depende del grupo de edad,
no del nivel NLP cuando ambos se especifican.

El extracto elegido pasa a ser `original_text`. Su hash, tamaño, conteos y métricas
se calculan desde ese extracto. El texto adaptado y sus cinco `level_previews`
proceden de la misma entrada; las preguntas, el vocabulario y el dato curioso se
construyen sobre esa lectura adaptada, sin consultar la parte omitida. GET conserva
exactamente esa versión y las atribuciones/licencias originales.

La generación puede reutilizar alineaciones locales revisadas únicamente cuando
la fuente es un prefijo exacto de al menos tres oraciones completas de un artículo
conocido. Solo se utilizan las alineaciones de esas oraciones, nunca las del final
descartado. Este comportamiento es optativo y exclusivo de generación; el valor
por defecto del pipeline no cambia para texto manual o archivos.

Se conservan los campos del contrato JSON, los endpoints de texto/subida, las
fórmulas de legibilidad, los pesos del modelo y las demos ya guardadas.
El presupuesto corresponde a la fuente; las paráfrasis del NLP pueden variar el
número de palabras del texto adaptado. Las métricas siempre reflejan los textos
reales entregados.

## Verificación

- 31 pruebas nuevas: límites, cortes completos, tres oraciones, párrafos,
  Wikipedia/local/respaldo, edades del perfil y prioridad de edad explícita,
  original/huella/métricas/previews persistidos, preguntas y dato curioso sin
  hechos descartados, conservación de texto y archivos, alineaciones optativas.
- Suite completa en PostgreSQL: **631 aprobadas**, 290.80 s.
- Ruff y formato sin errores; `pip check` sin incompatibilidades.

## Revisión de bandas y mini-reto tras 85e1fc7

Las ayudas de calibración también reconocen el prefijo exacto de un artículo,
exclusivamente con la opción de generación. Cada ayuda lleva la oración fuente
que la respalda; se excluyen las correspondientes a las oraciones descartadas.
Esto corrige el Nivel 1 del extracto de Real Madrid para 6–8 años.

Se incorpora una referencia local sobre béisbol, con alineaciones por oración y
reglas contrastadas con [Baseball for Beginners de PBS](https://www.pbs.org/kenburns/baseball/baseball-for-beginners).
La normalización existente resuelve `beisbol` y `béisbol` al mismo tema.
Si Wikipedia no permite cumplir cualquiera de las cinco bandas o la progresión,
se utiliza la referencia local del mismo tema cuando existe. La respuesta declara
la fuente efectivamente utilizada; no atribuye el respaldo local a Wikipedia.

| Nivel | Banda Szigriszt-Pazos | Béisbol local (100 palabras fuente) |
|---|---|---:|
| 1 | 82–100 | 83,303 |
| 2 | 74–84 | 78,598 |
| 3 | 65–74 | 70,013 |
| 4 | 58–66 | 61,803 |
| 5 | 50–65 | 57,810 |

Las nuevas lecciones generadas entregan tres preguntas (`q1`, `q2`, `q3`), con
tres opciones, índice correcto, pista y explicación. Sus respuestas se extraen
de palabras presentes tanto en la fuente recortada como en la lectura adaptada.
Texto manual, archivos e historial/semillas conservan sus dos preguntas.
El esquema permite recuperar tanto versiones históricas de dos como nuevas de
tres preguntas, sin migración de BD.

La regresión verifica las 32 referencias locales × 3 edades: **96/96** extractos
con las cinco bandas y progresión estricta. También cubre las dos grafías de
béisbol × 3 edades × 5 niveles, respaldo de Wikipedia para niveles 2 y 5,
preguntas fundamentadas, persistencia y aislamiento de texto/archivos.

Este resultado es una verificación del catálogo y los casos probados, no una
garantía matemática para todo artículo externo posible: una fuente inédita muy
simple o con tecnicismos insustituibles puede carecer de cinco versiones fieles
en esas bandas. Se conservan las mediciones reales y la advertencia
`pedagogical_bands_not_met` cuando no hay un respaldo válido que las cumpla.
`acceptance_criteria_met` sigue describiendo la evaluación congelada del modelo;
esta revisión no modifica ni reentrena sus checkpoints.

### Resultado de la verificación de esta revisión

- PostgreSQL, única ejecución completa: 767 casos en 391,57 s. Pasaron 734;
  otros 33 detectaron expectativas heredadas de dos preguntas en generación.
  Se actualizaron únicamente esas expectativas y la revalidación focalizada
  aprobó los 33 casos en 12,62 s. Los 767 casos quedan verificados entre ambas
  ejecuciones; no se repitió la suite completa.
- SQLite, regresiones de extractos/béisbol: **135/135** en 54,04 s.
- Ruff y formato: sin errores (124 archivos); dependencias sin incompatibilidades.
- Servicio local: salud y preparación `200 OK`; generación real de béisbol para
  6–8 (niveles 1 y 2), 9–11 y 12+, con tres preguntas y cinco bandas válidas.
- `model-info`: `acceptance_criteria_met: true`; hash del checkpoint activo sin
  cambios respecto a 85e1fc7.
- Mantenimiento local: Sofía en Nivel 1; retirados dos documentos antiguos de
  más de 300 palabras, cinco versiones y una sesión de prueba. Las 15 lecciones
  oficiales permanecen idénticas, comprobadas antes y después del reinicio.
- SMTP configurado en `.env` ignorado por Git y cargado en el proceso servidor;
  no se publican credenciales ni copias de la BD.
