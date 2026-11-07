# Cierre pedagógico v3.1 — 7 de noviembre de 2026

El servicio usa `pedagogical-es-v3.1`. El checkpoint aprobado continúa siendo
`context-ranker-es-v2.3`, SHA-256
`67e79bf3c13381cc8d000575e6e57b4f9787f895cbfb8cfc4569fb9ae3ba2507`.
No se reentrenaron ni reemplazaron pesos. Este cambio afecta al selector de
reescrituras, la organización de cláusulas, el glosario y las preguntas.

## Qué se mide

Las bandas solicitadas para este cierre son de **promedio de palabras por
oración**, distintas de los intervalos numéricos de Szigriszt-Pazos usados en
la auditoría anterior. Ambas mediciones se conservan, con nombres separados.
Un resultado de longitud no se presenta como un resultado de INFLESZ.

| Nivel | Objetivo vigente | Presupuesto individual preferido |
| --- | --- | ---: |
| 1 · Inicial | 6–9 palabras por oración | 11 |
| 2 · Básico | 9–12 palabras por oración | 14 |
| 3 · Intermedio | 12–15 palabras por oración | 18 |
| 4 · Avanzado | 15–19 palabras por oración | 25 |
| 5 · Experto | Más de 19 palabras por oración, o estructura original depurada | Cláusulas completas |

Los intervalos anteriores son promedios, no máximos rígidos por oración.
Se penaliza el exceso de los presupuestos individuales anteriores. Cuando esos
topes impiden una coordinación natural de hechos completos, el objetivo vigente
de promedio tiene prioridad; los máximos reales permanecen en la auditoría y
`short_sentence_budget_not_met` advierte sobre la versión seleccionada.

`level_previews[].target_met` expresa esta política vigente de longitud.
`readability_score`, los dos puntajes del comparador y las métricas silábicas
siguen calculándose sobre los textos efectivamente entregados, sin redondear
antes de tomar decisiones. `quality_status` y `meets_readability_target`
conservan la comprobación matemática de delta y puntaje de lectura; son una
medición diferente y un resultado `best_effort` permite abrir la lectura.

El modelo sigue exponiendo su informe congelado con
`acceptance_criteria_scope: frozen_context_ranker_v2.3_benchmark`.
Su `acceptance_criteria_met` no es una nueva validación del motor v3.1 ni una
estimación de comprensión infantil.

## Selección conjunta y contenido completo

El selector distingue la densidad silábica, la longitud media y el tamaño de
cada oración. La búsqueda de cinco versiones usa sus puntajes reales y exige
progresión estricta de legibilidad. Las opciones de los niveles iniciales
mantienen conceptos educativos con explicaciones accesibles. Para la alternativa
de Nivel 5 «estructura original depurada» se comprueban el mismo número de
oraciones, las mismas cifras y marcadores de negación/condición/modalidad, y
una similitud de secuencia de tokens de al menos 0,85 con la fuente. No se
clasifica cualquier texto corto como original depurado.

La calibración particiona globalmente cláusulas completas. Puede reunir
proposiciones contiguas mediante puntuación española correcta, manteniendo
sujetos, cifras, condiciones y negaciones. No corta por un índice de palabras,
no añade conectores causales a hechos sin relación causal y no introduce
información para completar una cuota. Se retiró la selección de apoyos que
volvían a enunciar hechos ya presentes para mejorar una cifra. Las claves
históricas de esos apoyos permanecen disponibles en el contrato JSON.

Las alineaciones de estrellas, relatos de dragones y La isla del tesoro tienen
versiones intermedias revisadas. Los extractos siguen limitándose, antes de
adaptar, a 120/180/240 palabras según la edad y a oraciones completas. Las
alineaciones locales usan exclusivamente las oraciones retenidas.

La caché acotada solo admite referencias públicas exactas y sus prefijos
revisados; sus respuestas son copias independientes. Los textos privados o
libres no se guardan en esa caché. El checkpoint conserva su identidad y las
rutas no cambian.

## Glosario de lectura

La clave existente es `key_vocabulary`; sus objetos siguen conteniendo
`word`, `definition` y `example`. Se entregan cuatro conceptos cuando hay
contenido suficiente, dentro del intervalo solicitado de cuatro a seis.

El extractor usa un banco de sentidos nominales redactados y revisados.
Rechaza entradas aisladas de menos de cuatro letras, números, preposiciones,
artículos, pronombres y verbos comunes. Por tanto no selecciona `v`, `y`,
`o`, `Sol` ni `luz` como entradas aisladas. Los conceptos de varias palabras
se reconocen como unidades completas. Las formas ambiguas, como `prueba`,
`vela` o `modelo`, también se filtran según su uso verbal o nominal.

Cada definición tiene entre **10 y 22 palabras**. Los sentidos de `masa` en
física y panadería se eligen según el contexto. Cada término aparece literalmente
en la adaptación y su ejemplo es una oración completa de esa lectura; se
eliminó el recorte por caracteres que podía terminar a mitad de una palabra.
Un término desconocido solo obtiene una definición extractiva si la propia
fuente lo define expresamente. No se etiqueta una palabra aleatoria con una
frase genérica de «su significado se entiende por el contexto».

## Mini-retos fundamentados

Cada lectura normal ofrece tres preguntas distintas y cuatro opciones completas
por pregunta, con respuestas de entre 3 y 12 palabras. La selección combina:

1. Un dato concreto, como año, cantidad, lugar, componente o definición factual.
2. Una relación de causa, consecuencia o finalidad realmente descrita.
3. Un concepto, inferencia o conclusión diferente de los dos anteriores.

Las anotaciones revisadas se licencian por fuente exacta, incluido el extracto,
y se contrastan con la versión que realmente leyó el usuario. Sus explicaciones
citan una secuencia completa que aparece literalmente en el texto entregado.
No se asigna a la NASA la fecha que corresponde a otro sujeto del mismo texto.
Las cláusulas independientes unidas con punto y coma también se analizan por
separado sin perder su evidencia original.

El extractor dinámico reconoce fechas al principio de la oración, cantidades
con unidad y estructuras causales o de finalidad. Sus distractores mantienen
los argumentos y el dominio de la cláusula. Una causa relativa a la energía
de un motor ya no recibe opciones universales sobre agua o luz solar. Los
patrones que no permiten formar alternativas fiables se omiten; no se presentan
hipótesis del cuestionario como hechos añadidos a la lección.

El artículo olímpico explica la distinción de las pruebas de invierno mediante
su práctica sobre nieve o hielo, conforme a la
[Carta Olímpica del COI](https://www.olympics.com/ioc/olympic-charter).
Así existe evidencia para esa pregunta causal dentro de la propia lectura.

## Integridad del texto y contrato

El backend entrega `adapted_text` y `chunks`; no se cambian esas claves ni se
introduce un contrato alternativo llamado `blocks`. El agrupador conserva todos
los caracteres de las oraciones y comprueba sus posiciones antes de crear un
bloque. Las pruebas recorren textos largos y su última enumeración completa.

La ingesta restaura palabras conocidas partidas por guion y salto de línea en
PDF, y elimina el guion blando sin separar una palabra. La corrección OCR de
`crustáceos v mamíferos` está restringida a enumeraciones de animales. No borra
una variable científica `v` ni el numeral `V` de un siglo. Una cola corrupta
conocida se registra como ruido retirado; no se adivina contenido ausente.

GET de una adaptación antigua conserva su UUID, par original/adaptado, métricas
e historial. Actualiza el glosario en memoria y revisa preguntas heredadas sin
reescribir el texto histórico. Las lecciones demo marcadas se regeneran con el
mecanismo existente de `refresh_marked`, que mantiene UUID, sesiones, premios
y controles del perfil. Sofía conserva su Nivel 1.

## Auditoría reproducible y alcance

```sh
python -m scripts.audit_pedagogical_quality --output docs/pedagogical-v3-evaluation.json --check
```

El diagnóstico abarca **50 fuentes × 3 edades = 150 casos**, con cinco versiones
por caso: **750 textos medidos**. No son 150 textos individuales. También se
verifican las versiones completas de los temas que forman las 15 lecciones
oficiales y pasajes nuevos de regresión que no coinciden con las referencias
locales. Los resultados finales se registran en el JSON y en la tabla de cierre.

Este material es público y redactado para la aplicación. No constituye un
conjunto de investigación independiente ni valida clínicamente la comprensión.
En particular, un saludo o un número aislado no contiene cuatro conceptos ni
tres hechos distintos. Esas entradas siguen siendo legibles y no reciben
causas, fechas o definiciones inventadas para satisfacer una cuota. Los textos
libres que no permiten una transformación segura conservan su mejor versión y
sus avisos; una garantía universal de bandas sobre cualquier cadena sería falsa.

Las pruebas se ejecutan sobre una base PostgreSQL de pruebas y esquemas
privados; ninguna prueba automática usa la base de producción. Las comprobaciones
HTTP finales usan cuentas temporales que se eliminan al terminar. Se preservan
los secretos locales y del servidor, los pesos y las bases de datos fuera de Git.
No se modifica ningún archivo de `fluilet-android` en este cierre.


## Resultados de cierre

Resultados medidos en `pedagogical-v3-evaluation.json`, sin redondear los
puntajes antes de comprobar la progresión:

| Comprobación de las cinco versiones | Catálogo, 150 casos | Lecciones oficiales, 15 casos | Pasajes nuevos y regresiones, 8 casos |
| --- | ---: | ---: | ---: |
| Bandas vigentes de longitud media | 150/150 | 15/15 | 8/8 |
| Progresión estricta de Szigriszt-Pazos | 150/150 | 15/15 | 8/8 |
| Glosarios completos y definiciones válidas | 150/150 | 15/15 | 8/8 |
| Preguntas variadas, completas y con cuatro opciones | 150/150 | 15/15 | 8/8 |
| Oraciones y bloques completos | 150/150 | 15/15 | 8/8 |
| Cinco intervalos históricos numéricos de Szigriszt-Pazos | 18/150 | 1/15 | 0/8 |

`release_criteria_met: true` corresponde a las cinco primeras filas, los
criterios de este cierre. **No significa que los cinco intervalos históricos
numéricos alcancen el 100 %.** Su resultado independiente sigue siendo 18/150.
Tampoco equivale a una prueba de vocabulario «100 % cotidiano» ni a una
validación de comprensión con niños; los conceptos nominales necesarios para
enseñar la lectura se conservan y se explican en el glosario.

Validación final sobre PostgreSQL: **944 pruebas aprobadas en 415,52 segundos**.
Ruff pasa sin incidencias; los 142 archivos Python están formateados.
`python -m pip check` no detecta dependencias incompatibles. No se alteran
`ml_training/`, `checkpoints/` ni archivos Android.
