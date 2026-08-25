# Arrancar un proyecto con Hache-Base

## 1. Describe el negocio

Completa `templates/PROJECT-PROFILE.md` y `docs/CHECKLIST-NUEVO-PROYECTO.md`.

No empieces por copiar tablas o pantallas. Primero define usuarios, sedes, permisos, datos, flujos críticos y la superficie pública del proyecto.

## 2. Define el modo SEO

Selecciona uno en el perfil:

- `public`: sitio/rutas públicas con objetivo de rastreo e indexación;
- `private-app`: aplicación autenticada, sin objetivo de indexación pública;
- `hybrid`: web pública + aplicación privada;
- `none`: sin superficie web pública ni objetivo SEO.

Para `public` y `hybrid`, el `Minimum SEO Baseline` forma parte del criterio de producción. Para `private-app`, aplicar solo controles relevantes y asegurar que lo privado no se exponga por error.

## 3. Selecciona módulos

Consulta `CATALOGO_MODULOS.md` y marca únicamente lo que aplica.

Ejemplos:

- cadena de restaurantes: arquitectura + multisede + roles + seguridad + auditoría + SEO técnico/local + despliegue; el dominio de órdenes/mesas/inventario se construye aparte;
- SPA híbrido: clientes + servicios + horarios/citas + pagos + seguridad + auditoría + SEO para la superficie pública;
- academia: núcleo recurrente + asistencia/ausencias/reposiciones cuando las reglas reales lo requieran + SEO si tiene web pública.

## 4. Extrae, no clones a ciegas

Copia/adapta solo los módulos seleccionados. Sustituye nombres, roles, reglas, variables e índices por los definidos en el nuevo proyecto.

## 5. Define datos

Usa `database/modules/` como referencia, convierte la selección real en migraciones pequeñas del proyecto y prueba en staging/clon.

## 6. Configura seguridad

Aplica la matriz de permisos, contexto de sede, CSRF/API según superficie y secretos por entorno.

## 7. Configura SEO si aplica

Para `public` o `hybrid`:

- revisar `seo/baseline/MINIMUM-SEO-BASELINE.md`;
- adaptar robots, sitemap, canonicals, metadata y schema al proyecto;
- incorporar `seo/tests/seo-static.mjs` a CI;
- usar `seo/tests/seo-smoke.sh` contra staging/producción;
- dejar para revisión humana intención, contenido, canonicals/redirects ambiguos, SEO local, reputación y decisiones YMYL.

## 8. Activa pruebas

Conserva `tests/run.sh` como base y añade casos del nuevo negocio: positivos, negativos, roles, sedes y mutaciones críticas. Si existe superficie pública, añade las comprobaciones SEO aplicables.

## 9. Prepara operación

Antes de producción deben existir:

- `.env.example` propio;
- staging cuando el riesgo lo requiera;
- backup probado;
- rollback conocido;
- health check;
- CI;
- despliegue identificado por commit;
- para `public`/`hybrid`, `MUST` SEO aplicables en PASS o excepción formal.

## Forma corta de pedirlo

Puedes describir el proyecto por capacidades, por ejemplo:

> Usa Hache-Base para un restaurante con cuatro sucursales. Necesito administración central, empleados limitados a su sede, clientes, pedidos, inventario y SEO local. Selecciona los módulos reutilizables y crea solo el dominio que falta.

El catálogo permite resolver qué archivos corresponden sin que el solicitante tenga que recordar rutas internas.
