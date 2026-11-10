# Instalación Android desde QR

Página pública: `http://67.205.150.186/instalar`, con alias `/install`.
Ambos admiten GET y HEAD, sin autenticación, y mantienen el CSP de las páginas
públicas. La plantilla `app/templates/install.html` se copia sin cambios del
HTML proporcionado; el layout añade únicamente la navegación compartida.

Los botones enlazan al grupo de evaluadores, a la prueba de Google Play y a
`/descargar/fluilet.apk`. Los dos enlaces de Google abren otra pestaña con
`noopener`; el enlace del APK es relativo al mismo servidor.

## APK publicado

* Paquete: `com.fluilet.app`; versión: `1.0`.
* Tamaño: **11.120.550 bytes**.
* SHA-256: `d0489f1a6a5726f1bac4d432db0f34b348e69fd748d32e73b25aa8b5490d97f4`.
* Archivo del servidor: `/srv/fluilet/descargas/fluilet.apk`.
* Variable configurable: `FLUILET_APK_PATH`, con esa ruta como valor predeterminado.

El APK ya está firmado y se publica sin compilarlo ni firmarlo de nuevo.
No se incluye en Git ni en la imagen del backend. La descarga usa FileResponse
en GET y HEAD, con tipo `application/vnd.android.package-archive`, nombre de
adjunto `fluilet.apk`, longitud del archivo y `nosniff`. Si falta el archivo,
la ruta devuelve 404 sin exponer la ruta del servidor.

## Despliegue

La instalación actual del droplet usa `fluilet-backend.service` con systemd.
El directorio y el APK pertenecen a root, con permisos 755/644 para que el
servicio pueda leerlos sin modificarlos. `ProtectSystem=strict` mantiene
la protección del sistema de archivos del servicio. Se publica primero a un
nombre temporal, se verifica su hash y se renombra al archivo definitivo.

Para Docker Compose, `api` tiene un bind mount de
`/srv/fluilet/descargas:/srv/fluilet/descargas` en **solo lectura**. El directorio
debe existir antes de iniciar Compose; no se crea automáticamente una carpeta
vacía si la ruta está mal escrita. Este cambio no migra la base de datos ni el
servicio de producción a contenedores.

Los despliegues conservan `.env`, checkpoint y datos de PostgreSQL. Los
respaldos de código no contienen el APK ni dumps de datos personales.


## Verificación del cambio

* Suite completa PostgreSQL: **970 pruebas aprobadas**.
* Páginas y descarga: **17 pruebas aprobadas**, sin modificar las pruebas
  originales de privacidad.
* Ruff y formato: sin incidencias; 147 archivos Python formateados.
* `docker compose --env-file .env.example config --quiet`: configuración válida
  usando valores de validación, sin mostrar secretos.
* Plantilla copiada byte por byte, SHA-256:
  `d3c5caa982f3c910a8086aa8953e7985030ca008f077faec60d9dc1cd92da470`.
