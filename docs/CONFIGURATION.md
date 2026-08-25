# Configuración y secretos

## Regla principal

El repositorio contiene nombres y ejemplos de variables; los valores reales viven fuera del código.

## Entornos

Cada proyecto debe poder definir al menos:

- `APP_ENV`;
- dominio/URL;
- conexión MariaDB;
- tokens internos;
- credenciales de integraciones;
- rutas de backup/despliegue;
- health check.

`.env.example` documenta la interfaz de configuración. `.env` real permanece ignorado por Git.

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

## Producción

`APP_DEBUG=false`. Los errores internos se registran por un canal privado y las respuestas públicas permanecen controladas.
