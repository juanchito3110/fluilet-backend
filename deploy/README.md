# DigitalOcean: arranque reproducible del backend

En el checkout del servidor, copia `deploy/digitalocean.env.example` a `.env` con
permisos `600` y completa sus valores privados. La contraseña de PostgreSQL debe
coincidir con la del URL y estar codificada para URL en `DATABASE_URL`. El hostname
del contenedor es `db`. Producción rechaza los placeholders y las dos contraseñas
académicas públicas; se mantienen los correos `tutor@fluilet.com` y
`admin@fluilet.com`. El entorno local de desarrollo conserva sus credenciales.

Coloca el certificado TLS válido en `/etc/fluilet/tls/fullchain.pem` y su clave en
`/etc/fluilet/tls/privkey.pem`. Desde el servidor:

```sh
docker compose --env-file .env build api
docker compose --env-file .env up -d
curl --fail https://your-domain.example/health/ready
```

El `CMD` de la imagen ejecuta `app.bootstrap`: toma un bloqueo asesor de PostgreSQL,
aplica `alembic upgrade head` y, solo si termina correctamente, reemplaza el proceso
por Uvicorn. Se aplican las **ocho revisiones existentes**, cuyo head se llama
`0007_master_accounts` (hay dos revisiones históricas con prefijo 0004). No se añade
una migración ficticia. Después, el lifespan carga el checkpoint y asegura las
cuentas/perfiles demo de forma idempotente. Un error de migración impide abrir HTTP.

La imagen incluye el JSON reentrenado en
`/srv/fluilet/checkpoints/context-ranker-v2.3/model.json`, idéntico al artefacto de
`app/services/assets/`. `RANKER_CHECKPOINT` permite una ruta explícita; un archivo
configurado ausente o un SHA-256 distinto del pin impide cargar el modelo. La
imagen no descarga modelos ni necesita Torch/NumPy para inferencia. El lector
SGSS es opcional: un montaje de solo lectura puede proporcionar
`/srv/fluilet/datasets/EASIER/SGSS.csv` sin incluir el corpus en la imagen.

Tras el arranque, comprueba con un token válido
`GET /api/v1/adaptations/model-info`: versión, checksum, `baseline_sari`,
`retrained_sari`, `band_compliance` y `acceptance_criteria_met`. Readiness 200
comprueba disponibilidad operativa; **no significa que las metas académicas estén
cumplidas**. El SARI léxico se mide por separado de la calibración estructural.
En v2.3 las tres comparaciones y las bandas/progresión de las cuatro cohortes
medidas cumplen los criterios. El reporte distingue los diagnósticos conocidos,
la longitud adicional orientativa y el apoyo contextual; no es validación clínica.

PostgreSQL usa volumen persistente; API y proxy tienen filesystem de solo lectura,
límites de cuerpo y logs sin contenido. Este cambio prepara la imagen/configuración;
no crea un Droplet ni modifica una cuenta DigitalOcean. Si no hay Docker disponible
localmente, la prueba de migraciones PostgreSQL y la comprobación del layout de
fuentes no sustituyen una construcción/ejecución real de la imagen.


El job `container` de `.github/workflows/ci.yml` construye la imagen y ejecuta
`scripts/verify_container.sh` en un runner Linux. La prueba usa PostgreSQL 18 vacío,
red/almacenamiento temporales, usuario de producción, filesystem de solo lectura
y puerto aleatorio: comprueba migraciones, login demo con credenciales de prueba,
checksum del checkpoint, niveles 1/5 y recuperación estable del nivel 5 tras generar
el 1. El cleanup elimina solo esos contenedores/red. Puede ejecutarse desde la raíz
con `bash scripts/verify_container.sh fluilet-backend:ci` después de construir la
imagen y tener Docker operativo. `FLUILET_ENV_FILE` selecciona un archivo de
entorno alternativo para Compose sin sobrescribir el `.env` local.

## Conexión Android desde fuera del Droplet

El cliente nativo Retrofit/OkHttp puede usar `https://api.tu-dominio.example/`
(con `/` final). Expón TCP 443 en el firewall del Droplet y asigna el DNS y un
certificado cuyo nombre coincida con ese dominio. También puede usarse una IP
pública si el certificado incluye esa IP como SAN. La API interna queda en
`127.0.0.1:8000`; el proxy publica HTTPS en 443. No es necesario exponer PostgreSQL.

Android nativo no aplica CORS ni suele enviar `Origin`: la autenticación Bearer
funciona con ese host público sin ampliar la lista de orígenes. Para un cliente
web/WebView, configura `CORS_ORIGINS=["https://tu-front.example"]` con sus orígenes
exactos (esquema y puerto, sin ruta). Se permiten Authorization y Content-Type y
el preflight OPTIONS. No se usa `*` con credenciales. CORS no sustituye TLS, DNS,
firewall ni el `BASE_URL` de Android. Esta entrega no ha creado un Droplet remoto.
