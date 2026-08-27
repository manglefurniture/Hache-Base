# Configuración y secretos

## Regla principal

El repositorio contiene nombres y ejemplos de variables; los valores reales viven fuera del código.

## Entornos

Cada proyecto debe poder definir al menos:

- `APP_ENV`;
- dominio/URL;
- `APP_TIMEZONE` cuando existan reglas de fechas, vencimientos, agenda o cierres;
- conexión MariaDB;
- tokens internos;
- credenciales de integraciones;
- rutas de backup/despliegue;
- health check.

`.env.example` documenta la interfaz de configuración. `.env` real permanece ignorado por Git.

## Zona horaria operativa

No asumir que la zona horaria del VPS coincide con la del negocio. Toda lógica basada en `hoy`, vencimientos, rangos, agenda o cambios automáticos de estado debe usar una zona IANA explícita.

Ejemplo:

```env
APP_TIMEZONE=America/Cancun
```

Hache-Base usa `UTC` como valor neutro en la plantilla; cada proyecto debe sustituirlo por la zona operativa correcta cuando corresponda. Si una aplicación opera en múltiples zonas, la zona debe formar parte del contexto de organización/sede/recurso en lugar de depender de un único valor global.

La utilidad temporal de Hache-Base acepta `UTC` y zonas regionales IANA como `America/Cancun`, `Europe/Madrid` o `Asia/Tokyo`. Rechaza abreviaturas ambiguas como `EST`/`CST` y offsets fijos como `+05:00`, porque no expresan correctamente reglas regionales ni cambios históricos/estacionales.

## Secretos

Nunca versionar:

- contraseñas;
- tokens Bearer;
- claves API;
- claves SSH privadas;
- cookies/sesiones;
- credenciales de correo;
- secretos de firma de webhooks;
- dumps de producción.

En CI/CD usar GitHub Environments/Secrets (o el gestor equivalente). En el VPS limitar permisos del archivo/servicio que cargue variables.

### Formas de inyección en VPS

Elegir una estrategia explícita por proyecto:

1. `.env` protegido, leído por un loader de la aplicación;
2. variables de entorno inyectadas por systemd/PHP-FPM y consumidas con `getenv()`;
3. gestor de secretos equivalente si la infraestructura ya lo proporciona.

No mezclar mecanismos sin documentarlo. Si PHP depende de variables de FPM, validar configuración antes de reiniciar el servicio y comprobar después que el pool está activo.

Cuando una credencial se copie mediante shell, preferir lectura silenciosa/variable temporal en lugar de escribirla en el comando o historial. Tras instalarla y probarla, ejecutar `unset` sobre la variable temporal.

## Red y egress

No asumir que el VPS puede abrir cualquier puerto saliente. Algunos proveedores cloud restringen SMTP u otros protocolos aunque HTTP/HTTPS funcione normalmente.

Antes de elegir una integración:

- identificar protocolo y puerto de salida;
- comprobar conectividad desde staging/producción;
- documentar si la integración usa HTTPS, SMTP, conexión directa a DB u otro canal;
- definir timeout y comportamiento cuando el proveedor externo no responde.

Para correo transaccional, una API HTTPS sobre 443 suele ser una alternativa operativa cuando SMTP no está disponible. Consultar `integrations/email/README.md`.

Para pagos, el webhook debe tener un secreto o mecanismo de autenticación independiente del access token usado para consultar la API. Consultar `integrations/payments/README.md`.

## Rotación

Todo token interno debe poder cambiarse sin modificar el código. Si una credencial temporal se usa durante una intervención, retirarla al terminar.

Las credenciales de proveedor deben tener el menor alcance posible. Cuando el proveedor permita restringir una API key por dominio, acción o entorno, usar ese alcance mínimo.

## Validación al arrancar

Una aplicación debe fallar de forma clara si falta una variable obligatoria, pero nunca imprimir el valor secreto en logs o respuestas HTTP.

Una zona horaria inválida debe tratarse como error de configuración, no corregirse silenciosamente con la zona del servidor.

Para integraciones críticas, validar también que existan las extensiones/runtime necesarios (por ejemplo cURL para APIs HTTPS) y que el endpoint externo sea alcanzable desde el entorno real.

## Producción

`APP_DEBUG=false`. Los errores internos se registran por un canal privado y las respuestas públicas permanecen controladas.
