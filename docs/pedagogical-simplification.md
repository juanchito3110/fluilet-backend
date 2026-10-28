# Simplificación pedagógica v2.3

**Aceptación medida: true**. Cinco bandas y progresión estricta: **31/31 catálogo, 6/6 EASIER, 6/6 controlados, 15/15 demos**. SARI de selección **44.557636125 > 44.543847868**; top-1 **73.245614% > 53.070175%**. [Métricas, protocolo y límites](model-retraining-report.md). [Historial anterior](pedagogical-simplification-v2.2.md).

## Dos etapas explícitas

1. El ranker contextual conserva sus pesos léxicos entrenados. Una compuerta ajustada en train y calibrada en validation compara su salida con la heurística histórica, usando señales del par y un veto de aumento silábico. Test no participa en esos ajustes. Sus referencias ya eran conocidas en el proyecto; el resultado no es ciego externo.
2. El controlador algebraico mide cada propuesta con la fórmula exacta de Szigriszt-Pazos. Reduce locuciones y separa cláusulas completas cuando el índice está bajo; restaura términos de la fuente y coordina enunciados cuando está alto. Mantiene números y ámbito de condiciones/negaciones. La búsqueda es finita; el contenido libre no admite una garantía universal.
3. Si hace falta, añade apoyo contextual licenciado por la fuente. Son paráfrasis/glosas redactadas, finitas y distintas, cada una ligada a una evidencia. Se limita su extensión y no se añaden plantillas sobre buscar un tema en libros. Los apoyos no son nuevas anotaciones gold ni salidas de un mT5 convergido.

## Transparencia del contrato

Texto, TXT/PDF, generación y versiones retenidas conservan las comparaciones, reemplazos, cinco previews, modelo y checkpoint. En cada preview se exponen `pre_support_text`, `pre_support_readability_score` y `pedagogical_support=[{text,evidence,kind}]`. El apoyo del nivel elegido también aparece en la raíz. `readability_score` siempre mide el texto completo entregado; el puntaje previo permite distinguir el efecto del apoyo.

La fuente original no se dificulta ni se sustituye para fabricar mejoras. Los niveles avanzados pueden ser más exigentes que una fuente sencilla, y eso se declara en warnings. «Hola» se conserva y no recibe una progresión inventada. Entradas válidas mantienen mejor esfuerzo 200; vacías/niveles inválidos reciben 422 saneado y archivos no admitidos 415.

## Bandas y límites

| Nivel | Intervalo de índice | Longitud media orientativa |
|---|---:|---:|
| 1 | 82–100 | 6–9 |
| 2 | 74–84 | 9–12 |
| 3 | 65–74 | 11–15 |
| 4 | 58–66 | 14–18 |
| 5 | 50–65 | 16–24 |

La aceptación de esta fase exige bandas y progresión, además de las tres mejoras comparativas. `target_met` exige también longitud media: no todos los casos la cumplen. La Doble Condición ≥15/≥65 es otro indicador, especialmente distinto para N4/N5. Ninguno prueba adecuación individual de edad, fidelidad clínica o comprensión; hacen falta revisión humana y evaluación externa.

Las 15 lecciones gestionadas se actualizan sin borrar práctica ni gemas/XP. Producción migra antes de servir y asegura cuentas/demos de forma idempotente; [verificación](verification.md) registra las suites y la comprobación HTTP reales.
