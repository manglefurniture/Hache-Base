# Dominio Cloudflare para SQL Guard

**Nombre definitivo:** `aprobaciones.hacheinteractive.com`

**VPS de origen:** `162.243.32.80` (hache-natacion).

El 18 de octubre de 2026 se verificó por DNS público:
- NS de `hacheinteractive.com`: `megan.ns.cloudflare.com` y `elijah.ns.cloudflare.com`.
- `aprobaciones.hacheinteractive.com`: NXDOMAIN, aún sin registro.
- El VPS tiene Nginx y Certbot para otros sitios. No reutilizar certificados ajenos.
- No hay conexión de administración DNS Cloudflare disponible desde el agente.

## Paso DNS en Cloudflare (acción de propietario o integración autorizada)

DNS > Records > Add record:

| Tipo | Nombre | Destino IPv4 | TTL | Proxy |
| --- | --- | --- | --- | --- |
| A | aprobaciones | 162.243.32.80 | Auto | DNS only inicialmente |

Evitar AAAA o CNAME duplicados para el mismo nombre. Mantener los registros actuales del resto de sitios. Después de verificar el certificado LE y HTTPS real puede activarse `Proxied` (nube naranja) con Cloudflare SSL/TLS en modo **Full (strict)**. No usar `Flexible`. En modo proxied Cloudflare devolverá IP de borde, no directamente la del VPS; comprobar resolución con `dig`/Cloudflare API y acceso HTTPS.

**No crear el DNS mediante comandos locales ni modificar /etc/hosts:** solo funcionan localmente y no habilitan el dominio a usuarios externos.

## Instalación por etapas

1. Esperar propagación de DNS y verificar host exacto.
2. Desde la revisión/merge de GitHub, instalar `deploy/nginx/aprobaciones-http-bootstrap.conf.example` como vhost nuevo con acceso HTTP solo a `/.well-known/acme-challenge/`; mantener 404 para el resto.
3. Certbot: `certbot certonly --webroot -w /var/www/sqlguard-acme -d aprobaciones.hacheinteractive.com`.
4. Validar certificados, copia de seguridad de Nginx, `nginx -t` y recarga.
5. Instalar servicio de aprobaciones separado; `SQLGUARD_RP_ID=aprobaciones.hacheinteractive.com`, `SQLGUARD_ORIGIN=https://aprobaciones.hacheinteractive.com`. No iniciar sin claves del servicio, almacenamiento seguro, respaldos root-owned y protección de registro de passkey.
6. Sustituir el vhost bootstrap por `deploy/nginx/aprobaciones-https.conf.example`, tras verificar certificado. Prueba interna HTTP contra `127.0.0.1:8173` y externa HTTPS solo después de autenticación configurada.
7. Registra passkey en dispositivo real del propietario mediante código de enrolamiento fuera del chat.
8. Validar solicitudes reales, rollback, denegaciones y ausencia de bypass MariaDB con los permisos finales.

## Limites

Los templates de Nginx y este plan se guardan en GitHub; no han sido desplegados en el VPS. La mera presencia del registro DNS no activa protección SQL ni garantiza la identidad del solicitante. DNS y TLS son requisitos previos, no suficientes.
