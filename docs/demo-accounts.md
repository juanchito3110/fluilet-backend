# Cuentas académicas y administración maestra

La migración `0007_master_accounts` añade un rol maestro real, marcadores de
identidad de demo, hashes de PIN y ajustes de progreso por perfil. El seed se
realiza automáticamente en el lifespan de FastAPI cuando
`DEMO_ACCOUNTS_ENABLED=true` (valor predeterminado). No se crean tablas desde el
startup: primero se ejecuta `python -m alembic upgrade head`.

## Credenciales y fases iniciales

Estas son credenciales públicas de la demostración solicitada:

| Cuenta | Contraseña | Rol |
|---|---|---|
| `tutor@fluilet.com` | `Tutor2026!` | `TUTOR` |
| `admin@fluilet.com` | `Master2026!` | `master_admin` |

El tutor tiene PIN parental **1234**, guardado con bcrypt. El login normal sigue
siendo `POST /api/v1/auth/login` con formulario `username`/`password`. No existe un
login especial que omita la comprobación de contraseña. La respuesta conserva
access/refresh/token_type/role y añade `is_master_admin`; el maestro devuelve true,
los demás false. `GET /users/me` y su alias `/auth/me` incluyen la misma identidad
y `has_parental_pin`, sin exponer hashes ni PIN. `POST /auth/verify-parental-pin`
recibe `{"pin":"1234"}` y devuelve `{"valid":true}` para el tutor autenticado.

| Perfil | Edad didáctica | Nivel | FluiBot | Gemas | XP | Racha | Lecturas |
|---|---|---:|---|---:|---:|---:|---:|
| Sofía | 6–8 (7 años) | 1 | Núcleo de Energía | 45 | 40 | 1 | 1 |
| Mateo | 9–11 (10 años) | 2 | Bot Explorador | 160 | 190 | 3 | 3 |
| Diego | 9–11 (11 años) | 4 | Guardián Cyber-Lector | 340 | 460 | 6 | 5 |
| Valentina | 12+ (13 años) | 5 | Sabio Cuántico | 900 | 980 | 12 | 6 |

Sofía empieza con la Luna. Mateo incluye biología marina. Diego incluye Real
Madrid y agujeros negros y tiene dos misiones completadas hoy. Valentina tiene
seis categorías, comprensión simulada de 95 %, cartas Oro, medallas y misiones
desbloqueadas. Sus seis fechas abarcan siete días.

**Procedencia de los números:** las sesiones son datos de demostración marcados
con `is_demo`, y sus puntajes Szigriszt-Pazos se calculan desde las fuentes y
adaptaciones reales. No se falsean esos puntajes. Los saldos y rachas solicitados
no se deducen del historial ordinario: una finalización ya otorga 100 XP, por lo
que una lectura con 40 XP, cinco finalizaciones con seis días de racha o seis
lecturas con doce días de racha requieren ajustes explícitos. `profile_controls`
guarda esos ajustes; el progreso devuelve `has_admin_adjustments=true`.
Los datos sintéticos no representan mediciones clínicas del niño.

Todas las lecturas se conservan con original, adaptación, métricas sin redondear,
dato curioso, glosario y dos preguntas. Se recuperan por el `id` de adaptación
mediante `GET /adaptations/{id}`. El seed usa solo el banco local y el refinador
CPU; no consulta Wikipedia ni carga pesos de mT5 al iniciar.

## Restauración y persistencia

`POST /api/v1/admin/ensure-demo-accounts`, autenticado como maestro, devuelve el
mismo objeto de overview y asegura las dos cuentas y los cuatro perfiles marcados.
Es idempotente y se serializa en PostgreSQL con un lock transaccional también entre
procesos. Las restauraciones concurrentes no duplican cuentas, sesiones ni premios.

Las cuentas faltantes o desactivadas se crean/reactivan; las contraseñas y el PIN
conocidos de demo se restauran. Un cambio de contraseña o reactivación invalida
sus tokens anteriores. Los perfiles demo borrados se recrean con su fase inicial.
Los ajustes administrativos y la práctica de perfiles existentes se conservan;
las fechas del historial no se desplazan artificialmente a hoy en cada reinicio.
Las cuentas manuales y los niños manuales, incluso de igual nombre o pertenecientes
al tutor demo, no se adoptan, borran ni resetean. Se identifican demos mediante
marcadores persistentes, no por el nombre del niño.

Un email reservado previamente existente sin el marcador autorizado provoca un
conflicto controlado; no se convierte una cuenta arbitraria en maestra por su
email. El registro público rechaza ambas direcciones reservadas y los roles
`master_admin`/`NINO`; las nuevas cuentas TUTOR y ADULTO_INDEPENDIENTE mantienen su
registro y login normales. Desactivar `DEMO_ACCOUNTS_ENABLED` omite el seed de
startup; no borra cuentas existentes ni bloquea una restauración maestra explícita.

## Endpoints maestros

Todas las rutas siguientes tienen prefijo `/api/v1/admin` y requieren JWT vigente,
usuario activo, rol `master_admin`, marcador maestro y email maestro. El email por
sí solo no concede privilegios. Otros roles reciben 403; sin credenciales, 401.

### GET /overview

Devuelve KPIs globales, `users` y `profiles`. Incluye cuentas/perfiles activos e
inactivos, con `is_active`, y datos demo y reales. `total_adaptations` cuenta las
versiones retenidas de adaptación. `average_comprehension` promedia solo puntajes
conocidos. Las listas se construyen desde consultas de metadatos agrupadas; no se
incluyen textos, contraseñas, hashes de PIN ni tokens.

Cada usuario incluye `user_id`, email, rol, flag maestro, cantidad de perfiles y
fecha de alta. Cada perfil incluye IDs, tutor/email, grupo de edad, nivel, saldos,
etapa/título, racha, finalizaciones y medallas desbloqueadas. Los totales de progreso
coinciden con lo que ve el tutor en `/profiles/{id}/educational-progress`.

### POST /profiles/{id}/grant

Ejemplo:

```json
{
  "add_gems": 100,
  "set_evolution_stage": 3,
  "set_level": 4,
  "set_age_group": "12+",
  "set_streak_days": 6
}
```

Devuelve `EducationalProgress` actualizado. `add_gems` y `add_xp` admiten positivos
y negativos; los saldos resultantes deben estar en 0..1.000.000.000.
`set_gems` establece el saldo exacto y no se combina con un `add_gems` distinto de
cero. `set_evolution_stage` establece XP en 0/150/350/700 y, sin un ajuste explícito
de gemas, asegura al menos 0/150/300/700 gemas. No se combina con `add_xp` no nulo.

`set_level` modifica tanto el perfil como su nivel recomendado. `set_age_group`
guarda una preferencia didáctica sin falsificar su cumpleaños: las nuevas
adaptaciones y preguntas la respetan, pero `child_age_years` sigue siendo la edad
real calculada. Perfil y progreso exponen `age_group` y `current_level`.
`set_streak_days` es un contador administrativo persistente (no nuevas fechas de
lectura). Se admiten valores 0..36500.

`unlock_all_rewards=true` fuerza cartas Oro, medallas y misiones completadas y
abonadas. La primera activación añade 95 gemas, salvo que se envíe un `set_gems`
explícito, y asegura 700 XP como mínimo. Repetirlo no añade más recursos. No se
combina con una etapa explícita menor que 4. Los contadores de lecciones por
categoría conservan su valor real; no se inventan tres lecturas para mostrar Oro.

Los ajustes se guardan como diferencias respecto de recompensas reales; las nuevas
lecturas siguen sumando recursos. La recomendación/racha forzada permanece hasta
otro ajuste. Los saldos no son un libro contable de compras: el cliente conserva
su inventario/gastos locales, como en el contrato anterior.

### DELETE /profiles/{id}

Baja física, 204. Elimina perfil, sesiones, actividad diaria, adaptaciones ligadas,
ajustes y cuenta NINO vinculada con sus tokens. Los documentos compartidos con
otros perfiles/versiones se conservan; los metadatos documentales que quedan
huérfanos se eliminan. No equivale al DELETE ordinario del tutor, que sigue siendo
una desactivación. Un perfil ya inexistente devuelve 404.

### DELETE /tutors/{user_id}

Baja física, 204, de la cuenta y sus hijos, contenido/documentos, sesiones,
controles, cuentas NINO vinculadas y tokens. Se admite cualquier usuario distinto
del maestro protegido. Intentar eliminar `admin@fluilet.com` devuelve 400.
Una identidad eliminada deja de poder usar tokens antiguos de inmediato.
La restauración posterior solo recrea las identidades de demo que falten.

### POST /tutors/{user_id}/reset-pin

Sin cuerpo restablece 1234; opcionalmente admite `{"pin":"5678"}` (4–6 cifras).
Devuelve el user_id y `pin_reset:true`, sin el PIN ni su hash. El cambio no modifica
la contraseña de login. Para el tutor demo, una restauración/startup posterior
restablece su PIN académico 1234; el PIN de cuentas manuales no se toca.

## Verificación

`tests/test_master_accounts.py` cubre login real de ambas cuentas, fases, contenidos,
registro normal, RBAC, grants de las cuatro etapas y recursos futuros, PIN, bajas
con cascada y tokens, protección del maestro, restauración repetida y concurrente,
startup sin pesos y preservación de cuentas/perfiles manuales. Las migraciones
verifican guardas contra downgrade destructivo y consistencia del esquema.
