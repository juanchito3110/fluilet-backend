# HTTPS en la IP pública de Fluilet

Configuración aplicada el 10 de noviembre de 2026 a `67.205.150.186`, partiendo
de `e9f86a2`. El droplet ejecuta PostgreSQL, nginx y
`fluilet-backend.service` con systemd; no ejecuta Docker.

## Compatibilidad conservada

- HTTP en el puerto 80 continúa sirviendo las mismas respuestas, sin redirección
  a HTTPS y sin `Strict-Transport-Security`, para Android 1.0.
- HTTPS en el puerto 443 usa el mismo proxy, límites, locations y encabezados.
  Solo acepta TLS 1.2/1.3 y tampoco publica HSTS.
- Las rutas, las plantillas públicas, el APK firmado, la base de datos, el
  checkpoint y el archivo `.env` no se modifican.
- Uvicorn queda en `127.0.0.1:8000`, con un worker; UFW también rechaza conexiones
  públicas al 8000. SSH/22, HTTP/80 y HTTPS/443 siguen permitidos.

## Certificado para la IP y emisión sin interrupción

Se utiliza Certbot **5.9.0**, en un venv separado de las dependencias de la app.
Let's Encrypt permite identificadores de IP con su perfil `shortlived`. La
[guía oficial](https://letsencrypt.org/2026/03/11/shorter-certs-certbot.html)
requiere Certbot 5.4 o posterior para usar `webroot` con IP. Se exige el perfil
mediante `--required-profile shortlived`, sin permitir otro perfil de respaldo.

Preparación como root en Ubuntu 24.04:

```sh
python3 -m venv /opt/certbot
/opt/certbot/bin/python -m pip install 'certbot==5.9.0'
install -d -m 755 /var/www/letsencrypt/.well-known/acme-challenge
ufw allow 443/tcp
```

Antes de emitir, añadir **solo** esta location al bloque HTTP existente:

```nginx
location ^~ /.well-known/acme-challenge/ {
    root /var/www/letsencrypt;
    default_type text/plain;
    try_files $uri =404;
}
```

Guardar una copia de la configuración nginx anterior, ejecutar `nginx -t` y
recargar únicamente si la validación tiene éxito. Comprobar desde fuera que un
archivo temporal dentro de ese directorio responde por HTTP y retirarlo al
terminar. El resto del bloque de puerto 80 permanece idéntico. No se usa
`standalone` ni se detiene nginx para liberar el puerto 80.

Primero comprobar ACME contra staging sin guardar un certificado de prueba:

```sh
/opt/certbot/bin/certbot certonly --dry-run \
  --non-interactive --agree-tos --email fluilet123@gmail.com \
  --cert-name fluilet-ip --required-profile shortlived \
  --preferred-challenges http --webroot \
  --webroot-path /var/www/letsencrypt \
  --ip-address 67.205.150.186 --key-type ecdsa
```

Tras el éxito, repetir el comando **sin `--dry-run`**. Instalar el bloque HTTPS
solo después de que existan estos archivos:

```text
/etc/letsencrypt/live/fluilet-ip/fullchain.pem
/etc/letsencrypt/live/fluilet-ip/privkey.pem
```

Las claves, certificados y cuentas ACME permanecen únicamente en el servidor,
fuera del checkout. Se conservan los permisos restrictivos que establece Certbot.
No se copian a Git ni al Mac. Tampoco se crean dumps de datos personales.

Si la CA no puede emitir para la IP, detener aquí: mantener HTTP, dejar 443
permitido por el firewall **sin listener**, y no instalar el bloque SSL. No
recurrir a certificados autofirmados ni a otro dominio.

## Instalación nginx y cierre del 8000

La plantilla de esta instalación nativa es `deploy/nginx-ip.conf`. El archivo
`deploy/nginx.conf` es una configuración distinta, histórica, para Compose;
no debe copiarse encima de la configuración del droplet.

Desde `/opt/fluilet-backend`, con el certificado emitido:

```sh
install -m 644 deploy/nginx-ip.conf /etc/nginx/sites-available/fluilet-backend
nginx -t
# Ejecutar únicamente si nginx -t termina correctamente:
systemctl reload nginx
```

La instalación conserva el enlace existente en `sites-enabled`. Si la validación
falla, restaurar el archivo anterior sin recargar; nginx sigue atendiendo con su
configuración válida en memoria. Confirmar primero que nginx llega a la app:

```sh
curl --fail http://127.0.0.1:8000/health/ready
curl --fail http://127.0.0.1/health/ready
```

Después, retirar el permiso público y añadir un rechazo explícito:

```sh
ufw --force delete allow 8000/tcp
ufw reject 8000/tcp
install -d -m 755 /etc/systemd/system/fluilet-backend.service.d
install -m 644 deploy/systemd/fluilet-backend-loopback.conf \
  /etc/systemd/system/fluilet-backend.service.d/loopback.conf
systemctl daemon-reload
systemd-analyze verify fluilet-backend.service
systemctl restart fluilet-backend.service
```

El drop-in conserva todos los argumentos originales excepto `--host`, que pasa
de `0.0.0.0` a `127.0.0.1`. Comprobar readiness después del reinicio. UFW aplica
las reglas tanto a IPv4 como a IPv6 y conserva 22/80/443. Si existe un Cloud
Firewall de DigitalOcean que filtre HTTPS, debe permitir TCP/443 entrante. No se
dispone de una credencial de su API en este entorno: no se ha inventariado ni
modificado el panel de Cloud Firewalls. La conexión TLS desde el Mac verifica
que la ruta pública actual permite 443; no fue necesario cambiar un filtro remoto.

## Renovación automática

Instalar el hook y las unidades versionadas:

```sh
install -d -m 755 /etc/letsencrypt/renewal-hooks/deploy
install -m 755 deploy/renew-nginx.sh \
  /etc/letsencrypt/renewal-hooks/deploy/fluilet-nginx
install -m 644 deploy/systemd/fluilet-certbot-renew.service /etc/systemd/system/
install -m 644 deploy/systemd/fluilet-certbot-renew.timer /etc/systemd/system/
systemd-analyze verify /etc/systemd/system/fluilet-certbot-renew.service \
  /etc/systemd/system/fluilet-certbot-renew.timer
systemctl daemon-reload
systemctl enable --now fluilet-certbot-renew.timer
systemctl start fluilet-certbot-renew.service
```

`fluilet-certbot-renew.timer` comprueba la renovación **dos veces al día**, a las
00:00 y 12:00 UTC, con hasta diez minutos aleatorios y un minuto de precisión.
`Persistent=true` recupera una ejecución perdida cuando el servidor vuelve a
encender. Certbot decide cuándo renovar; el timer no fuerza emisiones diarias.
Se guardan el perfil, la IP y el webroot en
`/etc/letsencrypt/renewal/fluilet-ip.conf`.

Tras una renovación, el hook ejecuta `nginx -t` y solo entonces
`systemctl reload nginx`. Una validación fallida termina con error, sin recargar.
La recarga permite a nginx adoptar el certificado nuevo sin detener HTTP.

Prueba manual, con la CA de staging y el hook usando el certificado activo:

```sh
/opt/certbot/bin/certbot renew --cert-name fluilet-ip --dry-run \
  --run-deploy-hooks --non-interactive --no-random-sleep-on-renew
systemctl list-timers fluilet-certbot-renew.timer --all
systemctl status fluilet-certbot-renew.timer
journalctl -u fluilet-certbot-renew.service --since '2 days ago'
```

Ver [renovaciones y hooks en la documentación de Certbot](https://eff-certbot.readthedocs.io/en/stable/using.html#renewing-certificates).
El primer certificado vence **el 17 de noviembre de 2026 a las 11:54:11 UTC**
(05:54:11 de Ciudad de México). La exposición del 18 de noviembre depende de la
renovación automática ya habilitada; no se trata de un certificado de 90 días.

## Verificación externa del 10 de noviembre de 2026

Ejecutada desde el Mac, sin `-k`, sin seguir redirecciones:

| Comando / ruta | Resultado |
| --- | --- |
| `curl -sI https://67.205.150.186/instalar` | `200 OK`; `text/html; charset=utf-8` |
| `curl -sI https://67.205.150.186/descargar/fluilet.apk` | `200 OK`; `application/vnd.android.package-archive`; `Content-Length: 11120550` |
| `curl -fsS https://67.205.150.186/descargar/fluilet.apk \| shasum -a 256` | `d0489f1a6a5726f1bac4d432db0f34b348e69fd748d32e73b25aa8b5490d97f4` |
| `curl -sI http://67.205.150.186/instalar` | `200 OK`; sin `Location` ni HSTS |
| `curl -s -o /dev/null -w '%{http_code}' http://67.205.150.186/health/ready` | `200` |
| `GET /privacidad`, HTTP y HTTPS | `200 OK`; `text/html; charset=utf-8` |
| `GET /eliminar-cuenta`, HTTP y HTTPS | `200 OK`; `text/html; charset=utf-8` |
| `nc -z -w 5 67.205.150.186 8000` | Salida `1`; puerto público rechazado |
| `certbot renew --dry-run --run-deploy-hooks …` | `Congratulations, all simulated renewals succeeded` |
| `systemctl list-timers fluilet-certbot-renew.timer --all` | Timer activo y programado |

Las páginas de privacidad/eliminación conservan sus rutas GET existentes; no se
añaden rutas HEAD. Para comprobar sus encabezados, usar
`curl -sD - -o /dev/null URL`.

La inspección pública del certificado:

```sh
echo | openssl s_client -connect 67.205.150.186:443 2>/dev/null \
  | openssl x509 -noout -issuer -enddate -ext subjectAltName
```

```text
issuer=C = US, O = Let's Encrypt, CN = YE2
notAfter=Nov 17 11:54:11 2026 GMT
X509v3 Subject Alternative Name: critical
    IP Address:67.205.150.186
```

El `openssl` del Mac es LibreSSL 3.3.6 y no admite `x509 -ext`. Para esta
verificación, la conexión `s_client` se hizo desde el Mac, con validación correcta
de la cadena; el certificado público recibido se pasó por stdin al parser
OpenSSL de Ubuntu. No se guardaron archivos de certificado en el Mac. Como
alternativa local, `openssl x509 -noout -issuer -enddate -text` muestra también
el SAN. Los comandos `curl` anteriores verifican tanto la confianza como la IP.

La página de instalación conserva su CSP:

```text
default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'
```

Controles complementarios: `nginx -t`, `systemd-analyze verify`, sintaxis del
hook con `sh -n`, Ruff y formato correctos; **17 pruebas públicas aprobadas**.
No se modifican archivos de Android ni se recompila o firma el APK.
