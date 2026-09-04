# Perfil del proyecto

## Identidad

- Nombre:
- Tipo de negocio:
- Objetivo principal:
- Usuarios esperados:
- Zona horaria operativa (`APP_TIMEZONE`):

## Perfil visual

- Personalidad (3–5 atributos):
- Evitar (3–5 atributos):
- Nivel visual base: Clean / Dimensional / Immersive
- Justificación si es Immersive:
- Movimiento: mínimo / medio / alto
- Densidad: comfortable / compact / mixta
- Temas: light / dark / system / selector
- Tipografía de marca/interfaz:
- Fotografía (lenguaje, proporción, recorte y tratamiento):
- Iconografía:
- Recurso reconocible propio:
- Extensions previstas y fallback:
- Excepciones a MUST del Design System:

## Organización

- ¿Multiempresa?: sí / no
- ¿Multisede?: sí / no
- Sedes iniciales:
- ¿Existen administradores globales?:
- ¿Todas las sedes comparten zona horaria?: sí / no / no aplica

## Roles

| Rol | Puede ver | Puede crear | Puede modificar | Puede eliminar/invalidar | Alcance |
| --- | --- | --- | --- | --- | --- |
| | | | | | |

Completar también `PERMISSION-MATRIX.md`.

## Datos principales

- Clientes/usuarios finales:
- Servicios/productos:
- Agenda/horarios:
- Pagos:
- Otros:

## Reglas críticas

1.
2.
3.

## Estados temporales

- ¿Existen entidades cuyo estado dependa de fecha/hora?: sí / no
- Entidades/rangos:
- Regla canónica por entidad:
- ¿Se persistirá el estado derivado?: sí / no
- Si se persiste, mecanismo de reconciliación y permiso requerido:
- Vistas/reportes que deben mostrar el mismo estado:

## Obligaciones y duplicados

- Obligaciones que no permiten duplicado activo:
- Identidad exacta de cada obligación (actor + recurso + tipo + periodo/estado):
- Defensa de servidor/transaccional prevista:

## Integraciones

- n8n:
- correo:
- mensajería:
- APIs externas:
- Inventario de terceros completado en `THIRD-PARTY-INVENTORY.md`: sí / no / no aplica
- Terceros críticos previstos:
- ¿Algún tercero participa en camino crítico de un CUF?: sí / no / por revisar

## SEO / superficie pública

- `SEO_MODE`: public / private-app / hybrid / none
- Dominio/host canónico esperado:
- Rutas públicas indexables:
- Rutas privadas/no indexables:
- ¿SEO local / ubicaciones reales?: sí / no
- ¿Search Console/Bing Webmaster Tools?: sí / no / pendiente
- ¿Schema previsto?:
- ¿Política de bots de búsqueda/IA definida?: sí / no
- Excepciones al Minimum SEO Baseline:

## Módulos Hache-Base seleccionados

- [ ] Arquitectura base
- [ ] Design System 2026 (Core + Theme; Extensions solo si aplican)
- [ ] Multisede/multiempresa
- [ ] Roles/permisos
- [ ] Estados temporales e integridad entre vistas
- [ ] Seguridad web/API
- [ ] Auditoría
- [ ] Modelo de servicios recurrentes
- [ ] Operaciones recurrentes (asistencia/ausencias/reemplazos)
- [ ] Utilidades comunes
- [ ] n8n
- [ ] SEO técnico / Minimum SEO Baseline
- [ ] Pruebas
- [ ] Backup/rollback
- [ ] Runner de despliegue
- [ ] Staging
- [ ] CI/CD

## Presupuesto visual y de performance

- Presupuesto completado en `PERFORMANCE-BUDGET.md`: sí / no
- LCP objetivo/resultados:
- INP objetivo/resultados:
- CLS objetivo/resultados:
- Categorías de viewport verificadas:
- Light/dark verificados:
- WCAG 2.2 AA verificado por:

## Entornos

- Development:
- Staging:
- Production:

## Criterio de listo para producción

- Pruebas críticas:
- Fronteras temporales/zona horaria:
- Consistencia entre vistas:
- SEO Baseline (si `public`/`hybrid`):
- Backup/restauración:
- Health check:
- Aprobación requerida:
