# Lecciones, comprensión y evolución educativa

## Generar una lección

`POST /api/v1/adaptations/generate` usa la misma autenticación y los roles
`TUTOR` / `ADULTO_INDEPENDIENTE` de las adaptaciones existentes. El tutor puede
indicar uno de sus perfiles activos mediante `child_id`; la lectura queda en su
biblioteca. El adulto independiente omite ese identificador.

```json
{
  "category": "ciencia_espacio",
  "topic": "Agujeros negros",
  "simplification_level": 2,
  "child_id": null
}
```

Categorías: `ciencia_espacio`, `animales_naturaleza`, `historia_misterios`,
`deportes`, `tecnologia` y `cuentos_aventuras`. Se normalizan mayúsculas,
acentos, espacios y guiones; una categoría desconocida o vacía selecciona
`ciencia_espacio`. `topic` es opcional, de hasta 120 caracteres. El nivel
predeterminado es 2 y el intervalo permitido es 1..5.

El banco contiene tres textos originales por categoría, de 57–68 palabras,
seleccionados al azar. Hay material específico para agujeros negros y dinosaurios.
Otros temas pueden seleccionar una lectura por su título o dar lugar a una
actividad de investigación sobre el tema escrito por el usuario. Esta última
explica cómo consultar fuentes, comparar datos y distinguir hechos de opiniones;
no inventa conocimientos específicos sobre un tema desconocido.

Cada texto pasa por el pipeline existente al nivel solicitado, con entrega de
mejor esfuerzo cuando no alcanza el objetivo de legibilidad. La respuesta conserva
`adapted_text`, `document`, `chunks`, los puntajes y los indicadores de calidad,
y añade:

- `title`: título de la lección o resumen breve en lectura libre.
- `category`: categoría normalizada o `lectura_libre`.
- `simplification_level`: nivel utilizado.
- `comprehension_questions`: exactamente dos preguntas, `q1` y `q2`, con tres
  `options` distintas y `correct_option_index` entre 0 y 2.

Las preguntas son actividades de comprensión literal con un fragmento a completar,
extraído del **texto adaptado que se entrega**. La opción correcta restaura ese
fragmento; las alternativas se eligen entre términos del mismo campo cuando se
reconocen. Si no se reconoce vocabulario de apoyo, o la entrada es mínima, se usan tareas de reconocimiento de fragmentos del texto disponible.
Las opciones correctas cambian de posición y las preguntas no necesitan un modelo
adicional ni servicios externos.

Estos cuatro campos también aparecen en `/api/v1/adaptations/text`, `/file` y el
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

`python -m alembic upgrade head` aplica `0004_educational_progress`, sucesora de
`0004_best_effort`; no se cambia el identificador de una migración ya desplegada.
Añade los seis campos a sesiones y categoría/nivel al documento para heredar los
metadatos de una adaptación. PostgreSQL impone los rangos y los contadores válidos.
El downgrade rehúsa borrar metadatos educativos que ya contengan información.

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

- Gemas: **30 de bienvenida + 50 por sesión completada al 100 % + 25 por respuesta correcta**.
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
completada con dos aciertos lleva a **130 gemas y 200 XP**.

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

Estas ampliaciones usan columnas existentes y se verifican con `alembic check`.
Pruebas: `python -m pytest tests/test_age_questions.py tests/test_fluibot.py -q`,
con `TEST_DATABASE_URL` configurada para ejecutarlas en PostgreSQL.

### Referencias de las curiosidades

Los datos de las cartas se contrastaron con fuentes educativas primarias:
[NASA: distancia en minutos luz](https://science.nasa.gov/exoplanets/what-is-a-light-year/),
[NC State Extension: comunicación de las abejas](https://content.ces.ncsu.edu/honey-bee-dance-language),
[British Museum: las tres escrituras de la piedra de Rosetta](https://www.britishmuseum.org/sites/default/files/2020-03/10010%20Hamlyn%206%2B%20Ancient%20Egypt%20PDF.pdf)
y [Springfield College: origen del baloncesto](https://springfield.edu/about/birthplace-of-basketball).
