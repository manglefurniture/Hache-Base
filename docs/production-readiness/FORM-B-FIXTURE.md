# P1-07 — Formulario fixture nivel B

P1-07 añade un fixture aislado para demostrar el contrato mínimo de un formulario público con efecto en un proyecto **Nivel B**, sin convertir ese ejemplo en runtime universal ni imponer CAPTCHA/proveedor externo.

## Qué demuestra

`tests/form-b/fixture-router.php` y `tests/form-b/ProductionReadinessFormBTest.sh` cubren de forma reproducible:

- **FORM-001:** validación real en servidor para nombre, correo, mensaje y `submission_id`; la validación HTML del navegador es solo una ayuda de UX;
- **FORM-002:** labels visibles, `required`, tipos, `autocomplete`, `inputmode`, errores enlazados con `aria-invalid`/`aria-describedby`, resumen con `role=alert` y foco del resumen tras error;
- **FORM-003:** estados `idle`, `loading`, `success` y `error`; el botón se deshabilita durante submit sin deshabilitar los demás successful controls; el servidor deduplica el mismo `submission_id` y no repite el efecto;
- **FORM-004:** tras un 422 se vuelven a mostrar los valores enviados de forma escapada; no se guardan esos campos en sesión;
- **FORM-005:** token CSRF y respuesta 419 cuando falta/es inválido; rate limit determinista con 429 + `Retry-After`;
- **FORM-006:** honeypot antes del efecto de negocio y respuesta de éxito genérica; el fixture no requiere CAPTCHA;
- **FORM-007:** texto de finalidad y advertencia para no enviar contraseñas, secretos ni datos de pago.

El efecto de negocio del fixture se representa únicamente mediante un contador de sesión y un conjunto de `submission_id` ya procesados. Los headers `X-Hache-Fixture-*` existen solo para que la regresión pueda probar que honeypot/duplicados no incrementan el efecto.

## Flujo del servidor

Para `POST /form-b` el orden es intencional:

1. sesión segura administrada por Hache Base;
2. CSRF;
3. rate limit;
4. honeypot;
5. validación de servidor;
6. dedupe por `submission_id`;
7. efecto de negocio del fixture;
8. respuesta `success`.

Ese orden evita gastar un efecto de negocio con un request inválido, evita que el honeypot sea un bypass del rate limit y hace que repetir el mismo request aceptado sea seguro dentro de la sesión del fixture.

## Qué NO demuestra

Un verde de este fixture **no convierte FORM-001…FORM-007 ni SEC-004/006/010 en PASS de un proyecto real**.

En particular:

- el rate limit del fixture es una bucket de sesión deliberadamente local y puede evadirse cambiando sesión; una app pública real debe seleccionar una defensa proporcional al abuso y, en multiinstancia, usar estado compartido o edge cuando corresponda;
- el dedupe del fixture vive en sesión; una mutación real importante necesita una clave/constraint/claim durable o una estrategia equivalente que sobreviva procesos, concurrencia y retries;
- el formulario es anónimo y solo crea una solicitud ficticia, por lo que no demuestra autorización de recursos autenticados;
- el honeypot es una capa de mitigación, no una garantía anti-spam; reputación, edge controls o CAPTCHA son decisiones de proyecto basadas en abuso observado, accesibilidad y privacidad;
- no se persiste PII ni se llama a email, mensajería, CRM u otro tercero;
- no se prueba infraestructura real, proxy, CDN ni disponibilidad de producción.

## Adopción por proyecto

Para reutilizar el patrón, el proyecto debe sustituir el contador ficticio por su mutación real y añadir evidencia para:

- reglas de negocio y autorización del CUF;
- dedupe/idempotencia durable si el efecto importa;
- rate limit apropiado a exposición y arquitectura;
- storage/retención/minimización de datos;
- logs/auditoría sin PII innecesaria;
- integración/cola/fallback si el submit llama a terceros;
- pruebas E2E/smoke del formulario desplegado.

CAPTCHA no es un requisito de Hache Base: se añade solo cuando la evidencia de abuso justifique ese coste.

## Ejecución

```bash
bash tests/form-b/ProductionReadinessFormBTest.sh
```

La prueba se integra en `tests/run.sh` y por tanto en el CI normal de Hache Base.
