# Lecciones, comprensión y evolución educativa

## Generar una lección

`POST /api/v1/adaptations/generate` usa la misma autenticación y los roles
`TUTOR` / `ADULTO_INDEPENDIENTE` de las adaptaciones existentes. El tutor puede
indicar uno de sus perfiles activos mediante `child_id`; la lectura queda en su
biblioteca. El adulto independiente omite ese identificador.

```json
{
  "category": "ciencia_espacio",
  "custom_topic": "Agujeros negros",
  "target_level": 2,
  "child_id": null
}
```

Categorías: `ciencia_espacio`, `animales_naturaleza`, `historia_misterios`,
`deportes`, `tecnologia` y `cuentos_aventuras`. Se normalizan mayúsculas,
acentos, espacios y guiones; una categoría desconocida o vacía selecciona
`ciencia_espacio`. `topic` es opcional, de hasta 120 caracteres. El nivel
predeterminado es 2 y el intervalo permitido es 1..5.

El resolvedor combina el tema con la categoría antes de buscar. `marina` en
naturaleza o ciencia se interpreta como biología marina, `egipcia` como Antiguo
Egipto, `olímpicos` como Juegos Olímpicos y `Real Madrid` como Real Madrid Club de
Fútbol. Los nombres anteriores `topic` y `simplification_level` siguen funcionando;
`custom_topic` y `target_level` son equivalentes. Si ambos nombres de un mismo
campo se envían con valores distintos, la respuesta es 422.

La fuente preferente es la API de Wikipedia en español: búsqueda de cinco
resultados y extracción de introducciones en texto plano. Se puntúan título,
contenido y palabras de la categoría y se descartan desambiguaciones. Las dos
consultas comparten un plazo máximo de 3,5 segundos y cuatro plazas de concurrencia.
Usan POST y `User-Agent: FluiletEdTech/1.0`; los temas no se incluyen en las URL de
petición. El resumen conserva fechas y cifras con contexto y elimina referencias,
pronunciaciones fonéticas y líneas de fechas aisladas.

Cuando Wikipedia no responde, el banco local contiene **29 artículos originales
con fuentes**: tres opciones por categoría y once temas específicos adicionales.
Incluye fútbol, Real Madrid, biología marina, tiburones, dinosaurios, sistema solar,
agujeros negros, volcanes, Antiguo Egipto, robots e inteligencia artificial. La
categoría literaria explica obras y autores reales y distingue sus personajes de
ficción. No se generan actividades genéricas de investigación ni relleno temático.
Un tema desconocido sin fuente disponible devuelve **503** con un mensaje genérico,
sin repetir el tema ni sustituirlo por información inventada. Esto no cambia la
entrega 200 de mejor esfuerzo de textos válidos en `/adaptations/text`.
`WIKIPEDIA_ENABLED=false` permite operación local reproducible; pytest lo configura
por defecto y prueba la red mediante transportes HTTP simulados.

Cada texto pasa por el pipeline existente al nivel solicitado. Con perfil infantil,
la edad limita a 10 palabras (6–8 años) o 12 (9–11) el umbral para separar cláusulas
independientes reconocidas, conservando el nivel pedido. No se cortan relaciones
restrictivas ni se garantiza dividir estructuras ambiguas. Se entrega una adaptación de
mejor esfuerzo cuando no alcanza el objetivo de legibilidad. La respuesta conserva
`adapted_text`, `document`, `chunks`, los puntajes y los indicadores de calidad,
y añade:

- `title`: título de la lección o resumen breve en lectura libre.
- `category`: categoría normalizada o `lectura_libre`.
- `simplification_level`: nivel utilizado.
- `resolved_topic`: título del artículo seleccionado, solo para generación.
- `source`: proveedor, título y URL; Wikipedia añade licencia CC BY-SA 4.0,
  enlace de licencia y revisión cuando está disponible. Se debe conservar esta
  atribución al presentar o redistribuir la adaptación.
- `fun_fact`: un dato extraído del texto entregado, con preferencia por cifras o
  una característica destacada. En textos libres se identifica como dato de la
  lectura aportada; no equivale a una comprobación externa de sus afirmaciones.
- `key_vocabulary`: de tres a cuatro palabras presentes en las lecciones, con
  `word`, `definition` y `example`. Los ejemplos proceden del texto entregado.
  Las definiciones usan un glosario propio o una definición explícita del artículo;
  términos desconocidos se identifican mediante su contexto, sin inventar sentidos.
  Una entrada libre mínima puede producir menos de tres términos distintos.
- `comprehension_questions`: exactamente dos preguntas, `q1` y `q2`, con tres
  `options` distintas y `correct_option_index` entre 0 y 2.

Las preguntas son actividades de comprensión literal con un fragmento a completar,
extraído del **texto adaptado que se entrega**. La opción correcta restaura ese
fragmento; las alternativas se eligen entre términos del mismo campo cuando se
reconocen. Si no se reconoce vocabulario de apoyo, o la entrada es mínima, se usan tareas de reconocimiento de fragmentos del texto disponible.
Las opciones correctas cambian de posición y las preguntas no necesitan un modelo
adicional ni servicios externos.

Los campos educativos también aparecen en `/api/v1/adaptations/text`, `/file` y el
nuevo alias `/document`. Los dos últimos reciben PDF o TXT **como cuerpo binario**
con `Content-Type: application/pdf` o `text/plain`, conservando los parámetros
`nivel_simplificacion_nlp` y `child_id` de `/file`. No se usa multipart.

## Registrar la práctica

Las rutas existentes conservan sus campos y agregan metadatos opcionales:

- `POST /api/v1/children/{child_id}/readings`
- `POST /api/v1/readings` para adultos independientes.
- `PATCH /api/v1/readings/{reading_id}` para el lector autorizado.
- `PATCH /api/v1/children/{child_id}/readings/{reading_id}` como alias con
  comprobación adicional del perfil y la sesión.

```json
{
  "document_id": "UUID_DEL_DOCUMENTO",
  "category": "ciencia_espacio",
  "simplification_level": 2,
  "questions_answered": 2,
  "questions_correct": 1,
  "comprehension_score": 50,
  "tts_speed_used": 1.0
}
```

Al crear una sesión, la categoría y el nivel omitidos se copian del documento.
Los registros anteriores a la migración reciben `lectura_libre` y nivel 2 porque
su nivel original no estaba guardado. Los contadores empiezan en cero, la velocidad
en 1.0 y el puntaje desconocido en `null`.

Los contadores son enteros entre 0 y 10.000 y `questions_correct` no supera
`questions_answered`. Si hay respuestas, se calcula el porcentaje de aciertos,
redondeado al entero más cercano con mitades hacia arriba. Un puntaje explícito
debe coincidir con los contadores. Con cero respuestas, reiniciar los contadores
restablece el puntaje a `null`. También se admite comunicar solo un puntaje
0..100 cuando no se han comunicado contadores. La velocidad TTS es finita,
mayor que cero y menor o igual a 4.

Estas cifras son telemetría comunicada por el cliente; no representan una
verificación de las respuestas en el servidor. El reto puede registrarse después
de finalizar la lectura. Los campos anteriores de duración y avance conservan
sus controles: una sesión finalizada no permite modificar ese avance o su tiempo.
Una actualización parcial valida el estado combinado de los contadores.

Todos los GET de sesiones incluyen los seis campos nuevos. Categoría, nivel y
puntajes se conservan en la sesión aunque después se vuelva a adaptar o se elimine
el documento asociado.

## Evolución y logros

El resumen educativo está disponible en:

- Adulto independiente: `GET /api/v1/readings/progress`.
- Tutor de un perfil: `GET /api/v1/children/{child_id}/progress`.
- Alias del mismo resumen: `GET /api/v1/profiles/{profile_id}/educational-progress`.
  Aplica la misma autorización de tutor y perfil activo.

**Contrato elegido:** la ruta infantil devuelve el objeto educativo por defecto,
sin parámetros adicionales. La lista `SessionProgress` anterior se encuentra en
`GET /api/v1/children/{child_id}/progress/legacy`; los clientes Android que aún
esperen esa lista deben usar esta ruta. `/api/v1/users/me/progress` mantiene su
lista anterior para adultos independientes. El objeto educativo conserva
`total_lessons`, `completed_lessons`, `incomplete_lessons`,
`completion_rate_percent`, `total_reading_seconds`, `average_comprehension_score`,
`current_recommended_level`, `level_progression` y `badges`, y añade los bloques de
FluiBot descritos más adelante.

El resumen cuenta todo el historial autorizado, sin el límite de paginación de
los GET de sesiones. Una lección completada es una sesión marcada `completed`;
los puntajes desconocidos no entran en el promedio. Sin puntajes, el promedio es
0.0. La evolución se ordena por fecha de inicio y UUID, con fechas ISO 8601 en UTC,
y muestra los puntajes de legibilidad originales de cada sesión.

La recomendación considera hasta las tres últimas sesiones completadas. Si tienen
comprensión >=50 **o** finalización al 100 %, recomienda un nivel por encima del
último nivel completado, con máximo 5. Sin sesiones completadas usa el nivel del
perfil infantil o 2 para el adulto. Consultar el resumen no modifica el perfil
ni provoca aumentos repetidos de nivel.

Los cinco logros son `primera_leccion`, `mente_brillante`, `habito_en_marcha`,
`explorador_curioso` y `subiendo_nivel`. El explorador cuenta categorías distintas
con alguna práctica: tiempo, avance o preguntas contestadas. Los demás corresponden
a una finalización, un puntaje de 100, tres finalizaciones y una finalización en
nivel >=3, respectivamente.

## Despliegue y privacidad

`python -m alembic upgrade head` incluye `0004_educational_progress`, sucesora de
`0004_best_effort`; no se cambia el identificador de una migración ya desplegada.
Añade los seis campos a sesiones y categoría/nivel al documento para heredar los
metadatos de una adaptación. PostgreSQL impone los rangos y los contadores válidos.
El downgrade rehúsa borrar metadatos educativos que ya contengan información.

La revisión siguiente, `0005_daily_activity`, añade `reading_activity_days`, un
registro numérico de actividad por sesión y fecha UTC. Guarda una clave SHA-256 de
lectura, finalización, existencia de acierto y si la fecha es inferida. La migración
reconstruye solo evidencia disponible: para sesiones antiguas utiliza cierre o
inicio y marca la estimación con `inferred=true`; no inventa fechas intermedias ni
reconstruye contenido. Usa el hash documental si existe y, en su ausencia, una clave
por documento o categoría. Un downgrade con actividad nueva observada se rechaza
para no borrar premios ganados.

Los títulos, temas libres, textos y preguntas solo viven en la respuesta y durante
el procesamiento en memoria. La base de datos conserva el hash, categorías
normalizadas, niveles y cifras; no se añaden columnas de contenido ni registros
de cuerpos HTTP. Se mantiene `Cache-Control: no-store`.

Verificación: `python -m pytest tests/test_education.py tests/test_educational_progress.py tests/test_migrations.py -q`.
Los tests usan SQLite en memoria o esquemas privados de una base PostgreSQL cuyo
nombre termina en `_test` mediante `TEST_DATABASE_URL`; nunca escriben lecturas de
prueba en la base de uso manual.

## Preguntas por edad, pistas y explicaciones

Todas las respuestas de `/adaptations/generate`, `/text`, `/document` y `/file`
añaden `child_age_years` y `question_age_group`. Con `child_id`, el servidor
consulta el perfil activo que pertenece al tutor y calcula los años cumplidos
con su `birth_date` y la fecha UTC de la respuesta. El cálculo compara mes y día;
no divide el número de días entre 365. Sin perfil, la edad es `null` y el grupo
es `12+`. Los datos de edad proceden del servidor.

| Grupo | Preguntas | Opciones |
|---|---|---|
| `6-8` | Dos preguntas cálidas de reconocimiento, de 5–9 palabras | Tres opciones de 2–4 palabras, por ejemplo `Dice «Sol»` |
| `9-11` | Enunciados de hasta 12 palabras sobre ideas, causas, resultados o propósitos expresados en el texto | Ideas o fragmentos claros de la lectura y dos alternativas |
| `12+` | Dos preguntas estándar de comprensión literal | Conservan el formato de completar o reconocer fragmentos |

En el grupo intermedio, la segunda pregunta usa relaciones explícitas como
`porque`, `debido a que`, `por eso` o `por lo que`. Un propósito expresado con
`para` o `el fin es` también puede ser objeto de una pregunta. Cuando la lectura
no contiene esas relaciones, las preguntas se centran en sus ideas literales.

Cada pregunta conserva `id`, `question`, `options` y `correct_option_index`, y
añade `hint` y `explanation`. La pista invita a releer; la explicación cita la
palabra o idea correcta de la adaptación entregada. La posición de la opción
correcta sigue variando. Las entradas mínimas conservan una respuesta válida.

El intervalo de alta de perfiles infantiles sigue siendo 6–11 años. Un perfil
ya existente que cumpla 12 años recibe automáticamente el grupo `12+`.
La edad, las preguntas, las pistas y las explicaciones se calculan para la
respuesta y mantienen la política de contenido en memoria.

## FluiBot y recompensas educativas

Los dos resúmenes educativos, `/children/{id}/progress` y `/readings/progress`,
conservan sus campos y añaden `streak_days`, `total_gems`, `total_xp`,
`total_stars`, `current_rank_title`, `next_rank_stars`, `mascot`,
`collectible_cards`, `shop_catalog` y `pedagogical_summary`.
`/children/{id}/progress/legacy` y `/users/me/progress` conservan sus listas.

Las recompensas se derivan del historial autorizado en cada consulta:

- Gemas: **30 de bienvenida + 50 por sesión completada al 100 % + 25 por respuesta correcta + bonos de misiones**.
- XP: **100 por sesión completada + 50 por respuesta correcta**.
- `total_stars`: el mismo valor que `total_gems`.
- Las respuestas correctas cuentan también durante una lectura en curso.
- `streak_days`: número de fechas UTC distintas con una finalización. Se utiliza
  `ended_at` y, para sesiones anteriores sin fecha de cierre, `started_at`.
  Las fechas con varias finalizaciones suman un día.

Consultar el progreso repetidamente conserva los mismos totales mientras el
historial no cambie. Los importes y las etapas se calculan desde las cifras
registradas; no se añaden escrituras de recompensas por consultar el resumen.

| XP | Rango | Etapa de FluiBot | Siguiente objetivo |
|---|---|---|---:|
| 0–149 | Explorador Inicial | 1 · Núcleo de Energía | 150 |
| 150–349 | Bot Explorador | 2 · Bot Explorador | 350 |
| 350–699 | Guardián Cyber-Lector | 3 · Guardián Cyber-Lector | 700 |
| 700+ | Sabio Cuántico | 4 · Sabio Cuántico | 1200 |

`mascot` incluye `name: "FluiBot"`, `species: "robot"`, etapa, nombre,
descripción motivadora, XP actual, siguiente objetivo y porcentaje dentro del
intervalo de esa etapa. El porcentaje va de 0 a 100. La cuarta etapa conserva su
nombre después de 1200 XP y su barra llega al 100 %. `next_rank_stars` mantiene
el nombre solicitado por compatibilidad y señala el siguiente objetivo de **XP**.

Las seis cartas corresponden a las seis categorías del generador. Una sesión
completada en una categoría desbloquea su carta: cero finalizaciones muestra
`Bloqueada`, una `Bronce`, dos `Plata` y tres o más `Oro`. Cada carta añade un
título y una curiosidad educativa. `lectura_libre` suma recompensas generales;
las cartas representan las seis categorías del banco de lecciones.

La tienda muestra los diez accesorios de FluiBot:

| Accesorio | Slot | Gemas |
|---|---|---:|
| Antena Prisma Neón | antenna | 15 |
| Visor Holográfico | eyes | 25 |
| Corbatín LED de Gala | neck | 30 |
| Auriculares Sónicos | ears | 40 |
| Emblema Estelar | chest | 50 |
| Jetpack de Plasma | thrusters | 60 |
| Mini-Dron Satélite | companion | 75 |
| Capa Fotónica | back | 90 |
| Alas Cyber-Halcón | wings | 100 |
| Corona Cuántica Dorada | crown | 120 |

Cada accesorio conserva su `item_id`, nombre, slot, descripción y precio.
`unlocked` indica que las gemas acumuladas alcanzan el precio de ese accesorio.
Las 30 gemas iniciales hacen accesibles los tres primeros. Una primera lectura
completada con dos aciertos lleva a **185 gemas y 200 XP** (incluye 55 gemas de las dos primeras misiones).

### Resumen pedagógico

`pedagogical_summary` devuelve `headline`, `strength_area`, `focus_area` y
`recommendation`. Usa las puntuaciones conocidas, las finalizaciones, la variedad
de categorías y los días de práctica para ofrecer mensajes positivos y una
siguiente actividad concreta.

La recomendación incluye el nivel de `current_recommended_level` y uno de estos
ritmos de voz:

- **0.8x** con comprensión conocida inferior al 50 % o menos de la mitad de
  lecturas finalizadas cuando existe práctica.
- **1.2x** con promedio conocido de al menos 85 %, tres finalizaciones y una
  tasa de finalización de al menos 75 %.
- **1.0x** en los demás casos, incluido el inicio sin sesiones.

Los puntajes desconocidos conservan su carácter de dato pendiente. Las sugerencias
son reglas educativas basadas en la telemetría existente. La selección de edad,
las cartas y FluiBot conservan la autorización de cada perfil o adulto.

Las preguntas y FluiBot usan metadatos existentes; las misiones requieren la revisión `0005_daily_activity`. El esquema se verifica con `alembic check`.
Pruebas: `python -m pytest tests/test_age_questions.py tests/test_fluibot.py -q`,
con `TEST_DATABASE_URL` configurada para ejecutarlas en PostgreSQL.

### Referencias de las curiosidades

Los datos de las cartas se contrastaron con fuentes educativas primarias:
[NASA: distancia en minutos luz](https://science.nasa.gov/exoplanets/what-is-a-light-year/),
[NC State Extension: comunicación de las abejas](https://content.ces.ncsu.edu/honey-bee-dance-language),
[British Museum: las tres escrituras de la piedra de Rosetta](https://www.britishmuseum.org/sites/default/files/2020-03/10010%20Hamlyn%206%2B%20Ancient%20Egypt%20PDF.pdf)
y [Springfield College: origen del baloncesto](https://springfield.edu/about/birthplace-of-basketball).

## Misiones diarias

Los resúmenes infantiles y de adulto añaden `daily_missions`, una lista de tres
objetos con `id`, `title`, `description`, `reward_gems`, `progress`, `target` y
`completed`:

| Identificador | Objetivo diario | Gemas |
|---|---|---:|
| `mission_read_lesson` | Explorador del Día: Completa 1 lectura | 25 |
| `mission_quiz_master` | Mente Brillante: Logra al menos 1 respuesta correcta en un Mini-Reto | 30 |
| `mission_category_variety` | Curiosidad Total: Explora 2 lecturas o temas distintos | 40 |

El día se delimita en UTC. Abrir una sesión sin avance, tiempo ni respuestas no
cuenta como práctica. Dos sesiones del mismo texto no completan variedad, incluso
si se elimina y vuelve a adaptar el documento: se usa su hash de contenido. En
sesiones antiguas sin documento solo puede distinguirse la categoría conocida.
Las actualizaciones de metadatos o velocidad de voz y los PATCH repetidos no
crean práctica nueva. Un acierto comunicado al día siguiente de terminar una
lectura puede completar la misión de quiz de ese día, sin premiar otra finalización.

Cada misión otorga su bono una sola vez por fecha. `daily_missions` muestra el día
actual; `total_gems` y su alias `total_stars` incluyen los bonos de todos los días
del historial conservado. Al llegar medianoche se reinician los objetivos visibles,
pero las gemas anteriores permanecen. Los GET no escriben recompensas y los bonos
no cambian XP, rangos ni requisitos de cartas. La evidencia depende de la telemetría
del cliente, igual que los contadores existentes; no hay verificación de respuestas
ni contabilidad de compras en este endpoint.

Pruebas específicas: `tests/test_encyclopedic_sources.py` y
`tests/test_daily_missions.py`, además de la suite completa y migraciones en PostgreSQL.
