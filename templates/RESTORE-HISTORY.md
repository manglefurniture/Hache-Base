# Restore History — P2-07

> Plantilla por proyecto Nivel C. No contiene una cadencia, RPO/RTO ni proveedor universales.

## 1. Identidad y ownership

- Proyecto: `<nombre>`
- Nivel: `C`
- Owner operativo: `<rol>`
- Fuente del backup: `<storage/ruta no secreta>`
- Runner/scheduler: `<servicio>`
- Store de evidencia histórica: `<artifact store/log store>`
- Retención de evidencia: `<duración y justificación>`

## 2. Contrato de recuperación aprobado

- RPO aprobado: `<segundos>`
- RTO aprobado: `<segundos>`
- Cadencia del restore drill: `<cron/intervalo>`
- Zona horaria operativa: `<IANA>`
- Ventana de baja carga elegida: `<...>`
- Relación con la cadencia de backup: `<por qué el drill no compite con el backup ni usa evidencia previsiblemente stale>`
- Dependencia backup → restore: `<workflow dependency / guard fail-closed de frescura>`

La cadencia, RPO y RTO son **project-owned**. P2-07 no introduce defaults globales. Una ruta programada debe usar únicamente los valores ya aprobados por ese proyecto o fallar cerrado. Una ruta manual puede existir, pero no sustituye la evidencia recurrente.

Si el backup que alimenta el drill se produce en otro scheduler/workflow, el restore debe **depender explícitamente de su finalización exitosa** o validar de forma fail-closed que seleccionó el backup esperado de esa ventana antes de comenzar. **Dos cron independientes con una separación horaria no constituyen una dependencia**: cualquiera puede retrasarse y el restore podría consumir un backup stale o producir un falso incumplimiento de RPO.

## 3. Ejecución programada

La agenda debe ejecutar un restore real y aislado usando el mismo contrato de verificación que el proyecto acepta para DB-007. No basta con comprobar que el scheduler disparó.

Cada ejecución debe poder demostrar:

- `trigger`: `schedule` o equivalente programado;
- `run_id` y, si aplica, `run_attempt` únicos;
- fecha/hora UTC;
- identificador no secreto del backup seleccionado;
- edad del backup al iniciar;
- RPO objetivo y `rpo_met`;
- duración total del drill;
- RTO objetivo y `rto_met`;
- target aislado;
- verificación específica de datos/invariantes críticas;
- estado de cleanup;
- resultado `PASS|FAIL`;
- referencia al artifact/reporte minimizado.

El dump, credenciales y filas personales no deben copiarse al store de evidencia salvo que exista una necesidad explícita, cifrado/acceso apropiados y una revisión separada de privacidad/seguridad. El baseline recomendado es conservar solo evidencia minimizada.

## 4. Historia inmutable en significado

- Una ejecución fallida se conserva como fallo; no se reescribe como PASS.
- Un rerun debe tener identidad distinguible del intento anterior.
- No sobrescribir el último PASS para ocultar fallos intermedios.
- La historia debe permitir revisar tendencia de `backup_age`, duración, RPO/RTO y cleanup.
- La retención debe ser suficiente para observar más de una ejecución según la cadencia elegida.
- Evitar commits automáticos a la rama productiva solo para guardar historial cuando eso dispare releases innecesarios; usar artifacts/log store/evidence store cuando sea más seguro.

## 5. Primera activación

Configurar un cron **no** equivale a P2-07 cerrado. Antes de declarar la cadencia operativa debe existir al menos una ejecución programada real revisada humanamente.

Una evidencia bootstrap manual anterior puede demostrar que el mecanismo de restore funciona, pero no sustituye la primera ejecución nacida del scheduler.

## 6. Revisión periódica

Para cada ventana de revisión:

| Run | Trigger | Fecha UTC | Backup age | RPO | Restore duration | RTO | Verify | Cleanup | Resultado | Ref |
| --- | --- | --- | ---: | --- | ---: | --- | --- | --- | --- | --- |
| `<id>` | `<schedule>` | `<...>` | `<s>` | `<PASS/FAIL>` | `<s>` | `<PASS/FAIL>` | `<PASS/FAIL>` | `<passed/...>` | `<PASS/FAIL>` | `<artifact>` |

Revisar además:

- fallos no resueltos desde la última ventana;
- degradación sostenida de duración o edad de backup;
- cambios de RPO/RTO/cadencia y su aprobación;
- cambios de schema/datos que requieran ampliar `RESTORE_VERIFY_COMMAND` o equivalente;
- vigencia del owner, credenciales y ruta de escalación;
- disponibilidad real del historial durante la retención declarada.

## 7. Criterio de adopción P2-07

P2-07 puede considerarse cubierto en un proyecto Nivel C solo cuando:

1. existe scheduler real activo con cadencia documentada;
2. RPO/RTO provienen del proyecto y se validan en runtime;
3. cuando backup y restore son procesos separados, existe una dependencia explícita o un guard fail-closed equivalente que evita consumir un backup stale;
4. al menos una ejecución programada real fue revisada;
5. el restore usa backup real, target aislado y verificación específica;
6. fallos y reruns quedan históricamente distinguibles;
7. cleanup y minimización de evidencia se verifican;
8. la retención conserva suficiente historia para evaluar recurrencia;
9. una revisión humana confirma que la evidencia sigue siendo representativa.

Tener esta plantilla o `deployment/restore-drill.sh` en Hache Base **no** convierte automáticamente P2-07, DB-006 ni DB-007 en PASS para un proyecto derivado.
