# Integración n8n

## Propósito

Conectar automatizaciones sin convertir el núcleo de la aplicación en un workflow de n8n ni exponer endpoints internos sin autenticación.

## Patrón recomendado

### Aplicación -> n8n

- URL desde variable de entorno.
- Autenticación/secretos fuera del repositorio.
- Timeout y manejo explícito de errores.
- La operación principal no debe depender silenciosamente de que n8n responda, salvo que el caso de uso lo exija.

### n8n -> aplicación

- Endpoint privado y de alcance mínimo.
- Método HTTP explícito.
- Bearer token almacenado en variables/credenciales, nunca en Git.
- Comparación segura del token.
- `Cache-Control: no-store` para información privada.
- Rate limiting apropiado al entorno.
- Respuestas de error controladas.

El servidor web debe reenviar `Authorization` a PHP-FPM. Ver `nginx-php-auth.conf.example`.

## Actores de auditoría

Cuando n8n modifica datos, registrar el evento como `actor_type=automation` con un identificador estable del workflow. No atribuir la acción a un usuario humano inexistente.

## Separación de alcance

El asistente web, automatizaciones internas y mensajería externa deben poder activarse/desactivarse de forma independiente. Un workflow incompleto no debe romper la aplicación principal.

## Backup

Cuando n8n use Docker + SQLite, respaldar de forma consistente la base SQLite, la configuración necesaria del contenedor y los archivos del volumen. Ver `backup-n8n.sh`.

## Antes de activar una automatización nueva

- privacidad y datos enviados revisados;
- credenciales creadas/rotables;
- endpoint probado sin token (`401`) y con token correcto;
- errores y reintentos definidos;
- auditoría definida para mutaciones;
- backup/restauración disponibles;
- monitoreo básico disponible.
