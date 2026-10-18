# Contrato de aprobación desde ChatGPT — pendiente de integración autenticada

**Estado: diseño, no es una integración con la identidad ChatGPT.**

## Flujo previsto
1. La herramienta SQL Guard recibe una operación estructurada, la valida y calcula su hash inmutable. Nunca acepta SQL libre.
2. Si requiere autorización, devuelve un ID opaco y un enlace HTTPS de un único uso a un servicio independiente. En el chat se muestra qué base, tabla, condición y número máximo de filas se afectarán, junto con el ID y enlace.
3. El propietario abre el enlace desde ChatGPT y se autentica **en el servicio externo** con un método verificable (por ejemplo WebAuthn/passkey registrada previamente). El chat no firma ni autentica por sí mismo.
4. El servidor muestra la operación exacta y exige un gesto explícito de aprobación; genera el comprobante firmado para el hash y lo almacena en su base independiente.
5. El agente reintenta **la misma operación** mediante un ID: el gateway hace comprobación de identidad y nonce de un solo uso, además del respaldo verificado, en la misma transacción de solicitud.
6. El ejecutor aislado realiza el cambio; registra auditoría duradera y devuelve el resultado. No permite cambios en condiciones/datos tras la aprobación.

## Requisitos del servicio real
- HTTPS; origen y sesión protegidos; autenticación WebAuthn/OIDC con comprobación de identidad y enrolamiento del propietario.
- Cookies HttpOnly/Secure/SameSite; CSRF y rechazo de solicitudes cruzadas; rate limits; validación de Origin y anti-clickjacking.
- La identidad ChatGPT **no se infiere del texto** ni de un clic no autenticado.
- El secreto de firma no sale de la máquina/servicio de aprobaciones. GPT no obtiene token ni permiso de autoaprobación.
- Almacén persistente que registre aprobaciones y consumos atómicos, sin acceso del agente.
- Canal de ejecución aislado, cuenta distinta, SQL parametrizado, minimización de privilegios MariaDB y ACL del socket.
- Bloqueo integral de la vía de bypass `mariadb` por usuario `gpt-agent` antes de anunciar protección activa.
- Auditoría con IDs, recuentos, resultado y timestamp; sin secretos ni valores de datos sensibles.
- Revalidar contexto de operación justo antes de ejecutarla (no solo un SELECT previo).

## Barreras verificables para desplegar
1. Servicio implementado con autenticación humana real; enrolamiento terminado.
2. Herramienta aprobada y disponible para ChatGPT que pueda iniciar y consultar solicitudes.
3. Aislamiento Linux/MariaDB probado con un usuario de prueba y luego con producción.
4. Backup y rollback aprobados; pruebas end-to-end incluyendo un rechazo, una aprobación y un replay.
5. PR revisado, CI aprobado y despliegue explícitamente autorizado tras inspección de los riesgos.

Hasta completar estos pasos: **ninguna confirmación escrita en el chat equivale a aprobación criptográficamente autenticada**. Las librerías Python existentes son prototipos, no mecanismos activos en el VPS.
