# SQL Guard — preflight staging sin cambios en producción

Ejecutar desde el código de **Hache-Base versionado y fusionado**. El script
`deploy/preflight-staging.sh` comprueba identidades, grupos, directorios, unidades
y servicios base **sin root/sudo y sin modificar archivos ni permisos**.

```bash
bash extensions/sql-guard/deploy/preflight-staging.sh --report
```

Cuando un administrador instale las identidades y los servicios (todavía desactivados),
ejecutar `--require-staged` para comprobar los mínimos. El resultado **no confirma**
aislamiento SQL, recuperación de respaldos, identidad WebAuthn ni autorización para
activar producción.

## Secuencia de preparación

1. Asegurar checks verdes y commit exacto de Hache-Base en `main`.
2. Un administrador **ya autorizado** debe preparar dos cuentas sin shell ni sudo,
   directorios y grupos aislados según `../DEPLOY-RUNNER.md` y
   `../DEPLOY-APPROVAL.md`. **No ampliar el sudo de `deploy-hache`**.
3. Incorporar código de solo lectura desde commit GitHub verificado bajo
   `/opt/sqlguard/current` e instalar dependencias en un venv independiente.
4. Preparar variables secretas localmente fuera del chat, y el almacén y respaldos
   root-owned con comprobación de restauración. No generar ni mostrar secretos en
   los resultados de preflight ni en GitHub.
5. Instalar las unidades versionadas inicialmente desactivadas; comprobar ACLs
   Linux y restricciones a `gpt-agent`. Nunca tocar Nginx de Hache Natación.
6. Probar aprobación con una base de prueba, con passkey real del propietario y
   registro de auditoría.
7. **Activar endpoints públicos y realizar el cutover de permisos SQL solo con
   aprobación específica posterior**, respaldo verificado y plan de rollback.

## Estado actual esperado en el VPS

Mientras no exista un instalador autorizado, es normal que el preflight indique
`MISSING` para `sqlguard-approval`, `sqlguard-runner` y sus rutas. El HTTPS de
`aprobaciones.hacheinteractive.com` debe permanecer temporalmente en 503.

La cuenta `gpt-agent` conserva permisos MariaDB directos; no puede considerarse
protegida por SQL Guard hasta realizar el corte de permisos de forma validada.
