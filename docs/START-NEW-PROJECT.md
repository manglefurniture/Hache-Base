# Arrancar un proyecto con Hache-Base

## 1. Describe el negocio

Completa `templates/PROJECT-PROFILE.md` y `docs/CHECKLIST-NUEVO-PROYECTO.md`.

No empieces por copiar tablas o pantallas. Primero define usuarios, sedes, permisos, datos y flujos críticos.

## 2. Selecciona módulos

Consulta `CATALOGO_MODULOS.md` y marca únicamente lo que aplica.

Ejemplos:

- cadena de restaurantes: arquitectura + multisede + roles + seguridad + auditoría + despliegue; el dominio de órdenes/mesas/inventario se construye aparte;
- SPA: clientes + sedes + servicios + horarios/citas + pagos + seguridad + auditoría;
- academia: núcleo recurrente + asistencia/ausencias/reposiciones cuando las reglas reales lo requieran.

## 3. Extrae, no clones a ciegas

Copia/adapta solo los módulos seleccionados. Sustituye nombres, roles, reglas, variables e índices por los definidos en el nuevo proyecto.

## 4. Define datos

Usa `database/modules/` como referencia, convierte la selección real en migraciones pequeñas del proyecto y prueba en staging/clon.

## 5. Configura seguridad

Aplica la matriz de permisos, contexto de sede, CSRF/API según superficie y secretos por entorno.

## 6. Activa pruebas

Conserva `tests/run.sh` como base y añade casos del nuevo negocio: positivos, negativos, roles, sedes y mutaciones críticas.

## 7. Prepara operación

Antes de producción deben existir:

- `.env.example` propio;
- staging cuando el riesgo lo requiera;
- backup probado;
- rollback conocido;
- health check;
- CI;
- despliegue identificado por commit.

## Forma corta de pedirlo

Puedes describir el proyecto por capacidades, por ejemplo:

> Usa Hache-Base para un restaurante con cuatro sucursales. Necesito administración central, empleados limitados a su sede, clientes, pedidos e inventario. Selecciona los módulos reutilizables y crea solo el dominio que falta.

El catálogo permite resolver qué archivos corresponden sin que el solicitante tenga que recordar rutas internas.
