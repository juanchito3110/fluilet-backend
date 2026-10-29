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

No se cambian el contrato JSON, los endpoints de texto/subida, las fórmulas de
legibilidad, los pesos del modelo, el catálogo completo ni las demos ya guardadas.
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
