# Backup / Restore — P0-11

> Plantilla por proyecto. No completar con secretos reales en Git.

## Clasificación y alcance

- Proyecto: `<nombre>`
- Nivel: `<A|B|C>`
- ¿Hay datos persistentes no reproducibles?: `<sí|no>`
- DB-006 aplica: `<sí|no + justificación>`
- DB-007 aplica: `<sí|no + justificación>`
- Owner operativo: `<rol>`

## Objetivos de recuperación

- **RPO objetivo:** `<segundos/minutos/horas>`
- **RTO objetivo:** `<segundos/minutos/horas>`
- Justificación de negocio: `<qué pérdida/indisponibilidad es aceptable y por qué>`
- Ventana de retención: `<política>`
- Ubicación/storage de backups: `<sin credenciales>`
- Protección/cifrado: `<mecanismo y owner>`

El RPO debe expresarse como un umbral medible de antigüedad del último backup válido. El RTO debe medirse desde el inicio del drill —incluida la validación/checksum del backup— hasta que la restauración aislada supera la verificación definida por el proyecto.

## Contrato de backup

El backup generado por `deployment/backup.sh` se considera **completo** solo cuando contiene:

- `database.sql` no vacío;
- `commit.txt`;
- `SHA256SUMS` válido que incluya explícitamente `commit.txt` y `database.sql`;
- `backup-manifest.env` con `backup_status=complete` y `created_at_epoch` como entero decimal canónico sin ceros iniciales;
- marcador `BACKUP_COMPLETE` creado al final.

Una carpeta incompleta o sin marcador final no cuenta para freshness ni para RPO. En cambio, si existe `BACKUP_COMPLETE`, la evidencia ya se declaró terminada: la pérdida de `backup-manifest.env`, un `created_at_epoch` ausente/no canónico o cualquier artefacto obligatorio inconsistente se trata como `invalid_backup` y nunca se ignora en favor de evidencia más antigua. `backup-freshness-check.sh` vuelve a validar `backup_status`, artefactos obligatorios, cobertura de `SHA256SUMS` y checksums antes de declarar `fresh`.

## Freshness y alerta

Configurar una ejecución periódica de:

```bash
BACKUP_ROOT=/ruta/protegida \
RPO_SECONDS=<rpo_en_segundos> \
bash deployment/backup-freshness-check.sh
```

El proceso debe integrarse con un monitor/cron/CI que trate exit code distinto de cero como alerta. Opcionalmente puede configurarse un ejecutable local:

```bash
BACKUP_ALERT_COMMAND=/ruta/alert-wrapper \
BACKUP_ROOT=/ruta/protegida \
RPO_SECONDS=<rpo_en_segundos> \
bash deployment/backup-freshness-check.sh
```

El wrapper recibe cuatro argumentos: `status`, `backup_path`, `age_seconds`, `rpo_seconds`. No debe contener secretos en la línea de comandos ni convertir un backup stale/missing/invalid en PASS.

- Cadencia del check: `<ej. cada 15 min>`
- Canal/monitor de alerta: `<servicio>`
- Responsable de respuesta: `<rol>`
- Evidencia de una alerta de prueba: `<fecha/ref>`

## Restore drill aislado

Nunca usar el nombre de la DB fuente ni una DB productiva como target. El script exige `RESTORE_CONFIRM_ISOLATED=1`, rechaza que `RESTORE_DB_NAME` coincida con `database_name` del manifest y **falla si el target ya existe**. El drill solo crea una DB nueva cuya propiedad corresponde a esa ejecución y el cleanup solo puede eliminar esa DB creada por el propio drill.

Antes de tocar la DB target, el drill verifica además que `SHA256SUMS` incluya explícitamente `commit.txt` y `database.sql` y que ambos checksums sean válidos.

```bash
BACKUP_DIR=/ruta/backup-completo \
RESTORE_DB_HOST=<host-staging> \
RESTORE_DB_NAME=<db_aislada_nueva> \
RESTORE_DB_USER=<usuario> \
RESTORE_DB_PASSWORD=<desde-secret-store> \
RESTORE_CONFIRM_ISOLATED=1 \
RESTORE_VERIFY_COMMAND='<verificación específica del proyecto>' \
RESTORE_DRILL_REPORT_FILE=/ruta/evidencia/restore-drill.txt \
RPO_SECONDS=<rpo> \
RTO_SECONDS=<rto> \
bash deployment/restore-drill.sh
```

`RESTORE_VERIFY_COMMAND` debe validar evidencia útil del proyecto —por ejemplo tablas/filas críticas, invariantes o un smoke controlado contra la DB restaurada—. Un import SQL sin verificación específica no basta para declarar DB-007.

El reporte se reemplaza al iniciar el drill y el resultado final se escribe **después** del cleanup. Todo fallo posterior —incluido checksum inválido, manifest de checksums incompleto o cleanup fallido— termina persistiendo un resultado `failed`; una evidencia PASS anterior no debe permanecer como resultado vigente de una ejecución fallida.

Por default `RESTORE_CLEANUP=1` elimina la DB aislada creada por esta ejecución al terminar. Si ese cleanup falla, el resultado final pasa a `reason=cleanup_failed`, `cleanup_status=failed` y exit code no-cero. Si el drill ya venía fallando por otra causa, `pre_cleanup_reason` conserva esa causa previa para no perder evidencia. Solo usar `RESTORE_CLEANUP=0` si la retención temporal del drill está aprobada y protegida.

## Evidencia del último drill

- Fecha/hora UTC: `<...>`
- Backup restaurado: `<identificador/ruta no secreta>`
- Edad del backup al iniciar: `<segundos>`
- RPO objetivo / resultado: `<...>`
- Duración total del drill, incluida validación del backup + restore + verify: `<segundos>`
- RTO objetivo / resultado: `<...>`
- Verificación ejecutada: `<descripción>`
- Estado de cleanup (`cleanup_status`): `<passed|failed|disabled|not_applicable>`
- Causa previa si cleanup sobrescribió el resultado (`pre_cleanup_reason`): `<...>`
- Reporte: `<ruta/artifact/ref>`
- Resultado: `<PASS|FAIL>`
- Incidencias/correcciones: `<...>`

## Criterio de cierre

DB-006/DB-007 solo pueden marcarse según la evidencia real del proyecto. Tener estos scripts disponibles en Hache Base **no** convierte automáticamente un proyecto en compliant. Debe existir backup periódico, freshness vigente, alerta demostrada y restore aislado con RPO/RTO medidos cuando esos controles apliquen.
