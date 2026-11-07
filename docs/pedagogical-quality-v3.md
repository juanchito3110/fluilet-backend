# Revisión de calidad pedagógica — 7 de noviembre de 2026

El motor de servicio es `pedagogical-es-v3.0`. El checkpoint sigue siendo
`context-ranker-es-v2.3`, SHA-256
`67e79bf3c13381cc8d000575e6e57b4f9787f895cbfb8cfc4569fb9ae3ba2507`.
No se reentrenaron ni reemplazaron sus pesos.

## Hallazgos y cambios

1. El selector anterior daba más peso a la banda numérica que a la longitud de
   cada oración. Había frases de 21 palabras en Nivel 3 y sustituciones sin
   concordancia, como «esa poder» y «estas útiles». El selector ahora penaliza
   primero el exceso de 11, 14 y 18 palabras en los niveles 1, 2 y 3. Las
   alternativas locales deben conservar los conceptos educativos y las cifras.
   La selección conjunta exige puntajes estrictamente decrecientes y cambios
   léxicos entre los tres primeros niveles. Los niveles 4 y 5 conservan más
   vocabulario y frases completas del original.
2. La transformación reconoce sujetos compartidos, coordinaciones, relativas
   explicativas, definiciones de procesos y causas. Repite el sujeto cuando
   procede. Cada partición recursiva reduce el tamaño del problema y tiene un
   límite de profundidad. Nunca introduce puntos en posiciones arbitrarias.
   Las condiciones, alternativas diagnósticas, negaciones y posibilidades se
   mantienen. Los dos casos de soporte educativo documentados tienen
   alineaciones explícitas en `clinical_frames.py`.
   Las cinco variantes de una fuente pública exacta se reutilizan en una caché
   acotada y ligada al hash del checkpoint. Las respuestas reciben copias
   independientes. Ningún texto libre del usuario entra en esa caché.
3. Se amplió el diccionario existente hasta más de 500 entradas revisadas.
   Las expresiones con cambio de género incluyen su determinante. Se retiraron
   expansiones que complicaban innecesariamente «baloncesto», «herramientas» o
   «materiales». Una corriente de agua ya no recibe una definición eléctrica.
4. Se sustituyó el mini-reto de huecos y palabras aisladas por extracción de
   hechos y anotaciones revisadas. Hay 153 preguntas específicas revisadas,
   cuatro opciones por pregunta y explicaciones que citan evidencia completa.
   Los años se contrastan con años; las cantidades conservan su unidad; las
   definiciones y funciones tienen opciones del mismo tipo. Cada opción nueva
   tiene entre 3 y 12 palabras. La posición correcta es reproducible y variable.
   La revisión editorial también retiró distractores anacrónicos o ajenos al
   dominio, como satélites en la vida vikinga o cartas para transmitir datos
   desde una sonda. Las preguntas revisadas delimitan expresamente su respuesta
   a lo explicado en la lectura: una alternativa plausible en el mundo real no
   se presenta como falsa universalmente.
5. Las anotaciones del catálogo solo se aplican a su fuente exacta o a un
   extracto reconocido. Un texto libre que mencione la NASA y el nacimiento de
   otra persona no atribuye ese año a la agencia. Los eventos negados tampoco
   producen una pregunta que los afirme.
6. El banco tiene 50 artículos y relatos. Todas las sugerencias actuales de
   Android tienen resolución local. Las cuatro familias de aventuras cuentan
   con dos relatos propios cada una. La ficción se identifica expresamente.
   «Bosque Encantado» no consulta reseñas de novelas. Wikipedia sigue disponible
   para otros temas, con plazo de 3,5 segundos y tamaño acotado; se descartan
   desambiguaciones y reseñas de medios o biografías irrelevantes.
7. La limpieza común retira referencias, IPA y metadatos editoriales. Conserva
   fechas de hechos, cifras, ecuaciones y calificadores científicos. Se aplica
   antes de recortar la fuente generada por edad: 120, 180 o 240 palabras en
   oraciones completas, con la regla existente de tres oraciones mínimas.

## Diagnóstico reproducible del catálogo

```sh
python -m scripts.audit_pedagogical_quality --output docs/pedagogical-v3-evaluation.json
```

El archivo JSON contiene los valores sin redondear de los 50 textos × 3 edades
× 5 niveles. Es una evaluación de material público escrito y revisado para la
aplicación. No es un conjunto de prueba independiente ni una validación clínica.

| Criterio | Resultado por extracto y edad |
| --- | ---: |
| Progresión estricta de los cinco puntajes | 150/150 |
| Máximo de 11/14/18 palabras por oración en niveles 1/2/3 | 150/150 |
| Vocabulario distinto entre niveles 1–2 y 2–3 | 150/150 |
| Tres preguntas completas, cuatro opciones y sin tarea literal de respaldo | 150/150 |
| Los cinco puntajes dentro de las bandas históricas simultáneamente | 84/150 |

Ejemplos para edad 6–8; los valores de esta tabla están redondeados únicamente
para mostrarlos. El JSON y las decisiones conservan precisión completa.

| Tema | Original: palabras/oración | Nivel 1: palabras/oración | Original: sílabas/palabra | Nivel 1: sílabas/palabra | Original: puntaje | Nivel 1: puntaje |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Real Madrid | 27,00 | 6,82 | 2,24 | 1,88 | 40,24 | 82,89 |
| NASA | 19,20 | 7,85 | 2,31 | 1,95 | 43,57 | 77,44 |
| Biología marina | 13,86 | 8,06 | 2,33 | 1,86 | 47,83 | 82,82 |
| Bosque Encantado: puente de raíces | 19,60 | 7,08 | 2,14 | 1,89 | 53,74 | 81,93 |

Las bandas de Szigriszt-Pazos se siguen midiendo y `target_met` expresa el
resultado real. El nuevo límite individual de las frases tiene prioridad sobre
forzar una banda mediante frases largas, repeticiones o pérdida de términos.
Por ejemplo, NASA conserva sus nombres, fecha completa y conceptos aun cuando
su Nivel 1 queda en 77,44. Los textos libres que no permiten una transformación
segura conservan su mejor versión y los avisos `level_goal_not_met`,
`level_progression_not_available` o `short_sentence_budget_not_met` pertinentes.

`/adaptations/model-info` conserva el informe congelado del Ranker v2.3,
incluido su `acceptance_criteria_met`. Lo identifica con
`acceptance_criteria_scope: frozen_context_ranker_v2.3_benchmark` y expone por
separado `runtime_engine_version`. Sus cifras históricas no representan una
nueva medición del motor v3. Los textos sin proposiciones suficientes, como
«Hola» o «42», usan reconocimiento literal como respaldo y pueden conservar dos
preguntas; no se inventan fechas o causas para completar una cuota.

Con los recursos y el checkpoint residentes, una medición local del cálculo de
las cinco variantes dio 0,9282 s en frío y 0,0001 s al reutilizar NASA;
0,9352/0,0003 s para Real Madrid y 0,7314/0,0001 s para Bosque Encantado.
Son tiempos del cálculo NLP en este equipo, sin red, base de datos ni envío del
JSON; no son una promesa de latencia HTTP en otros equipos.

## Administración y compatibilidad

`GET /api/v1/admin/overview` sigue enviando `users` y `profiles`, con sus mismas
claves. Todas las cuentas se listan independientemente de su número de niños.
Las cuentas independientes tienen un perfil lector administrativo con el UUID
de la cuenta. La migración `0010_reader_controls` guarda sus ajustes de gemas,
XP, nivel y edad pedagógica; no crea niños ni fechas de nacimiento ficticias.
La migración también incorpora las cuentas adultas ya existentes.

Las rutas actuales de `grant`, baja y restablecimiento de PIN funcionan con las
cuentas independientes. Sus ajustes aparecen en `/api/v1/readings/progress`.
Se conserva su recomendación inicial histórica de Nivel 2 cuando no hay ajuste.
La consulta de administración reutiliza las sesiones y controles cargados por
lotes, sin una consulta adicional por cada cuenta adulta.

Android mantenía un filtro local que ocultaba todo rol distinto de `TUTOR`.
Se corrigió con autorización del propietario para mostrar las cuentas
administrables, manteniendo sus roles y la protección de la cuenta maestra.
Las listas de preguntas y opciones de Android ya admitían las nuevas cantidades.
No cambian las rutas, el formulario de login ni las claves del JSON de lecciones.
Las versiones históricas recuperadas por GET reciben preguntas actualizadas en
memoria sin sobrescribir su texto histórico.

Las 15 lecciones demo se actualizan mediante el mecanismo existente de
`refresh_marked`, conservando UUID, sesiones, recompensas y controles. Los
registros de práctica anteriores mantienen sus respuestas y sus fechas.

## Fuentes y verificación

Cada artículo factual incluye su URL de referencia. Entre las fuentes de los
nuevos textos están [NASA: inicio de operaciones](https://www.nasa.gov/history/65-years-ago-nasa-begins-operations/),
[NASA: Marte](https://science.nasa.gov/mars/facts/),
[WWF: Amazonía](https://www.worldwildlife.org/places/amazon/),
[Royal Museums Greenwich: barcos vikingos](https://www.rmg.co.uk/stories/maritime-history/viking-ships)
y [English Heritage: castillos](https://www.english-heritage.org.uk/castles/life-in-a-castle/).
Los relatos son originales de Fluilet y se presentan como ficción.

Las pruebas cubren las sugerencias de Android, las cinco versiones de las
lecciones oficiales, la evidencia y forma de las preguntas, los casos libres
con negación o fechas ajenas, el límite de recursión, la conservación de fechas
factuales, cuentas sin niños, permisos, controles de lectores independientes y
la cadena real de Alembic en PostgreSQL.

Validación final: **914 pruebas aprobadas en PostgreSQL (354,88 s)**,
`ruff check`, `ruff format --check` sobre los 138 archivos Python y
`python -m pip check` correctos. Android: **32 pruebas de administración
aprobadas**, `assembleRelease` y `bundleRelease` correctos; firmas APK v2 y
AAB verificadas. Se mantuvieron fuera del commit los cambios locales del IDE,
los entornos, credenciales, pesos y corpus.
