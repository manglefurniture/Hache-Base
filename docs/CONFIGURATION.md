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

## Secretos

Nunca versionar:

- contraseñas;
- tokens Bearer;
- claves API;
- claves SSH privadas;
- cookies/sesiones;
- credenciales de correo;
- dumps de producción.

En CI/CD usar GitHub Environments/Secrets (o el gestor equivalente). En el VPS limitar permisos del archivo/servicio que cargue variables.

## Rotación

Todo token interno debe poder cambiarse sin modificar el código. Si una credencial temporal se usa durante una intervención, retirarla al terminar.

## Validación al arrancar

Una aplicación debe fallar de forma clara si falta una variable obligatoria, pero nunca imprimir el valor secreto en logs o respuestas HTTP.

Una zona horaria inválida debe tratarse como error de configuración, no corregirse silenciosamente con la zona del servidor.

## Producción

`APP_DEBUG=false`. Los errores internos se registran por un canal privado y las respuestas públicas permanecen controladas.
