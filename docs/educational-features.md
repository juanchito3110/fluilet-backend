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
- Tutor de un perfil: `GET /api/v1/children/{child_id}/progress?view=educational`.

**Compatibilidad Android:** sin `view=educational`, la ruta infantil sigue
respondiendo la lista `SessionProgress` anterior. `/api/v1/users/me/progress`
también mantiene su lista anterior. El objeto educativo contiene exactamente
`total_lessons`, `completed_lessons`, `incomplete_lessons`,
`completion_rate_percent`, `total_reading_seconds`, `average_comprehension_score`,
`current_recommended_level`, `level_progression` y `badges`.

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
