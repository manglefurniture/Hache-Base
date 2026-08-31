# Arrancar un proyecto con Hache-Base

## 1. Describe el negocio

Completa `templates/PROJECT-PROFILE.md` y `docs/CHECKLIST-NUEVO-PROYECTO.md`.

No empieces por copiar tablas o pantallas. Primero define usuarios, sedes, permisos, datos, flujos críticos, zona horaria operativa y la superficie pública del proyecto.

Si existen cursos, campañas, promociones, membresías, reservas, eventos o cualquier entidad cuyo estado cambie por fecha, documenta desde el inicio su regla temporal canónica.

## 2. Define el modo SEO

Selecciona uno en el perfil:

- `public`: sitio/rutas públicas con objetivo de rastreo e indexación;
- `private-app`: aplicación autenticada, sin objetivo de indexación pública;
- `hybrid`: web pública + aplicación privada;
- `none`: sin superficie web pública ni objetivo SEO.

Para `public` y `hybrid`, el `Minimum SEO Baseline` forma parte del criterio de producción. Para `private-app`, aplicar solo controles relevantes y asegurar que lo privado no se exponga por error.

## 2.1 Define el perfil visual

Completa personalidad, atributos a evitar, nivel visual, movimiento, densidad, temas, fotografía, iconografía y recurso propio en `templates/PROJECT-PROFILE.md`. Usa Core sin modificarlo, crea un Theme del proyecto y añade Extensions únicamente con necesidad y fallback demostrados. Dimensional es el preset recomendado; Immersive requiere justificación.

## 3. Selecciona módulos

Consulta `CATALOGO_MODULOS.md` y marca únicamente lo que aplica.

Ejemplos:

- cadena de restaurantes: arquitectura + multisede + roles + seguridad + auditoría + SEO técnico/local + despliegue; el dominio de órdenes/mesas/inventario se construye aparte;
- SPA híbrido: clientes + servicios + horarios/citas + pagos + seguridad + auditoría + estados temporales si existen promociones/membresías + SEO para la superficie pública;
- academia: núcleo recurrente + estados temporales para cursos/periodos + asistencia/ausencias/reposiciones cuando las reglas reales lo requieran + SEO si tiene web pública;
- tienda: seguridad + pagos/webhooks + reservas/idempotencia + correo transaccional + auditoría + despliegue + SEO para la superficie pública.

## 4. Extrae, no clones a ciegas

Copia/adapta solo los módulos seleccionados. Sustituye nombres, roles, reglas, variables e índices por los definidos en el nuevo proyecto.

## 5. Define datos

Usa `database/modules/` como referencia, convierte la selección real en migraciones pequeñas del proyecto y prueba en staging/clon.

Si decides persistir un estado que puede derivarse del tiempo, documenta cuál es la fuente de verdad y cómo se reconciliará sin depender de actualizaciones manuales.

Si existen pagos externos, definir desde el esquema una referencia local única, el identificador único del proveedor, estados permitidos, evidencia de incidencias y la identidad exacta del recurso que el pago satisface.

Si existen inventario/cupos reservables, definir el TTL, expiración y operación idempotente de liberación antes de construir checkout.

## 6. Configura seguridad

Aplica la matriz de permisos, contexto de sede, CSRF/API según superficie y secretos por entorno.

Las consultas read-only deben permanecer libres de escrituras colaterales. Una reconciliación persistida requiere permiso explícito de mutación.

## 7. Configura tiempo e integridad si aplica

- definir `APP_TIMEZONE` con la zona IANA del negocio;
- usar `src/common/DateRangeState.php` para clasificaciones temporales genéricas cuando encaje;
- adaptar `FUTURE / ACTIVE / ENDED` a los nombres de dominio del proyecto;
- asegurar que listados, fichas, detalles y formularios consuman la misma definición canónica;
- mantener la validación definitiva de acciones inválidas/duplicadas en servidor.

Consultar `docs/ESTADOS-TEMPORALES-E-INTEGRIDAD.md`.

## 8. Configura integraciones externas

Antes de conectar un proveedor:

- definir el adaptador y las variables de entorno;
- verificar conectividad/egress desde el entorno real;
- establecer timeouts, logs privados y política de reintentos;
- mantener secretos fuera del repositorio;
- definir cómo se desactiva la integración sin romper el núcleo.

Para correo transaccional, consultar `integrations/email/README.md`; verificar el dominio remitente y realizar al menos una entrega real desde staging/producción.

Para pagos, consultar `integrations/payments/README.md`; autenticar webhooks, consultar el recurso autoritativo al proveedor, validar importe/moneda y probar repetición/idempotencia.

## 9. Configura SEO si aplica

Para `public` o `hybrid`:

- revisar `seo/baseline/MINIMUM-SEO-BASELINE.md`;
- adaptar robots, sitemap, canonicals, metadata y schema al proyecto;
- incorporar `seo/tests/seo-static.mjs` a CI;
- usar `seo/tests/seo-smoke.sh` contra staging/producción;
- dejar para revisión humana intención, contenido, canonicals/redirects ambiguos, SEO local, reputación y decisiones YMYL.

## 10. Activa pruebas

Conserva `tests/run.sh` como base y añade casos del nuevo negocio: positivos, negativos, roles, sedes y mutaciones críticas. Si existe superficie pública, añade las comprobaciones SEO aplicables.

Para reglas por fecha, probar obligatoriamente antes de inicio, día de inicio, día final, día posterior y zona horaria. Para obligaciones, probar el recurso exacto y el rechazo de duplicados en servidor.

Para callbacks/webhooks, probar eventos repetidos y fuera de orden. Para reservas, probar concurrencia por la última unidad/cupo y liberación por expiración.

## 11. Prepara operación

Antes de producción deben existir:

- `.env.example` propio con zona horaria correcta cuando aplique;
- staging cuando el riesgo lo requiera;
- backup probado;
- rollback conocido;
- health check;
- CI;
- despliegue identificado por commit;
- conectividad de integraciones críticas verificada desde el host real;
- para `public`/`hybrid`, `MUST` SEO aplicables en PASS o excepción formal.

## Forma corta de pedirlo

Puedes describir el proyecto por capacidades, por ejemplo:

> Usa Hache-Base para un restaurante con cuatro sucursales. Necesito administración central, empleados limitados a su sede, clientes, pedidos, inventario y SEO local. Selecciona los módulos reutilizables y crea solo el dominio que falta.

El catálogo permite resolver qué archivos corresponden sin que el solicitante tenga que recordar rutas internas.
