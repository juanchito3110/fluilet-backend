# Revisión académica: comparación y demostración

> Actualización: el motor vigente y sus resultados están en [simplificación pedagógica](pedagogical-simplification.md). Las mediciones siguientes son históricas.

Contrato revisado contra Android **b822b85**, sin modificar ese repositorio.
La conservación en BD de originales y adaptaciones, incluidos textos manuales,
fue autorizada explícitamente el **26 de octubre de 2026**. Sustituye la regla
anterior de Cero Retención; no se reconstruyen cargas históricas ya descartadas.

## Preparar el perfil

Con el token de su tutor propietario y un perfil activo:

```sh
curl -X POST "http://127.0.0.1:8000/api/v1/profiles/$PROFILE_ID/seed-demo" \
  -H "Authorization: Bearer $TOKEN"
```

El endpoint devuelve el resumen educativo completo y seis `demo_lessons` con
original, adaptación, métricas, dato curioso, glosario y preguntas. Al abrir cada
lectura debe utilizarse su `id` para recuperar esa adaptación; `document.id`
conserva su uso para crear sesiones. Para consultar el par después de reiniciar:

```sh
curl "http://127.0.0.1:8000/api/v1/adaptations/$ADAPTATION_ID" \
  -H "Authorization: Bearer $TOKEN"
```

En un perfil sin práctica previa, el seed crea seis documentos y siete sesiones
con fechas consecutivas desde hoy menos seis días, niveles 1/2/3/4 y comprensión
**simulada** de 65/75/80/85/90/100/100. La séptima sesión repite Real Madrid en nivel
4, con sus métricas calculadas en ese nivel. El resultado es una racha activa de
7 días, 900 XP (etapa 4) y 715 gemas acumuladas, incluidas misiones automáticas.
No hay contabilidad de compras en el backend: Android conserva el gasto local.

`demo_data=true` y `is_demo=true` distinguen estas sesiones. No representan una
medición del niño. Los porcentajes bajos se guardan como puntajes de demostración
sin inventar cantidades de respuestas a las dos preguntas de una lectura.
Las dos sesiones de 100 % tienen dos aciertos de dos preguntas.

Una segunda llamada, incluso simultánea, reutiliza la cohorte: no duplica
sesiones, biblioteca ni gemas. Las fechas quedan ancladas al primer seed; no se
mueve artificialmente la actividad hacia el presente. La práctica real previa y
las preferencias del perfil se conservan. No se modifica ningún perfil hasta que
su tutor llama expresamente al endpoint.

## Comparación verificable

Ejemplo del motor determinista local para un perfil de ocho años. Se redondea
**solo esta tabla**; la API devuelve los valores sin redondear y las métricas se
pueden recalcular desde ambos textos completos.

| Lección | Nivel | Original | Adaptado | Delta | Palabras/oración original → adaptado |
|---|---:|---:|---:|---:|---:|
| Real Madrid | 1 | 66.752 | 68.122 | 1.369 | 11.38 → 11.38 |
| Biología marina | 2 | 47.825 | 55.309 | 7.484 | 13.86 → 12.00 |
| Agujeros negros | 3 | 56.440 | 57.173 | 0.733 | 17.00 → 17.00 |
| Antiguo Egipto | 3 | 42.421 | 44.595 | 2.173 | 12.29 → 12.29 |
| Robots e Inteligencia Artificial | 4 | 26.202 | 36.343 | 10.142 | 14.50 → 14.00 |
| El Viaje del Pequeño Faro | 4 | 50.658 | 58.966 | 8.308 | 15.50 → 13.00 |

Estos resultados muestran una mejora real, pero **no alcanzan simultáneamente
Delta >=15 y score >=65**. La API los identifica como `best_effort`; no se inflan
los originales ni se falsean puntajes para cumplir el objetivo. El porcentaje de
comprensión simulado no demuestra eficacia educativa o clínica del refinador.

El cuento del faro es una narración original de ficción, identificada como tal,
que incorpora datos reales sobre señales de navegación. No es una obra histórica
atribuida a un autor inexistente. Su base factual es
[NOAA: faros y navegación](https://oceanservice.noaa.gov/facts/lighthouse.html) y
[NPS: patrones luminosos](https://www.nps.gov/articles/000/lighthouse-thaumatrope.htm).

## Campos Android y gemas

Los DTOs reciben exactamente `fun_fact`, `key_vocabulary` con
`word/definition/example` y `daily_missions` con
`id/title/description/reward_gems/progress/target`. El backend añade
`completed/claimed`. Las misiones completadas ya están abonadas una sola vez;
POST `/profiles/{id}/daily-missions/{mission_id}/claim` las confirma con 200 sin
otro abono (409 pendiente, 404 desconocida).

En **b822b85** Android no lee `original_text` ni `claimed`, no llama todavía a
GET de adaptación, claim o seed, y permite añadir gemas de misión localmente.
Para mostrar la comparación textual y evitar un premio local duplicado debe
consumir los campos nuevos. Los puntajes de las gráficas ya usan los nombres
existentes de `document` y `level_progression`. No se afirma que agregar campos
al servidor cambie automáticamente esas pantallas del cliente.
