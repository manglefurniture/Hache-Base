# Artifact Promotion — P1-10 / DPL-001

> Plantilla de adopción por proyecto para construir y probar una vez y promover el **mismo artefacto verificable**. No sustituye los controles de migración, backup, health, smoke, observación ni rollback de P0-10.

## 1. Aplicabilidad

- Proyecto:
- Nivel Production Readiness: A / B / C
- Owner del pipeline:
- Stack/build:
- ¿El stack produce un artefacto desplegable separado?: sí / no
- Si no, modo de despliegue: commit exacto / imagen preconstruida / otro
- Justificación de aplicabilidad de P1-10:
- Entornos que adoptan artifact promotion:
- Fecha de revisión (`YYYY-MM-DD`):

P1-10 se adopta cuando el stack lo permite. Un sitio/source-only puede seguir desplegando el **commit exacto que pasó CI** con el runner existente; no hay obligación de inventar un build artificial.

## 2. Identidad del artefacto

- Formato: tar.gz / zip / imagen / paquete / otro
- Directorio/stage que contiene únicamente archivos desplegables:
- Nombre/patrón del artefacto:
- Registro/storage inmutable o versionado:
- Retención:
- Commit fuente (`40-hex SHA`):
- SHA-256/digest del artefacto:
- Manifest sidecar:
- Referencia de ejecución CI:
- Evidencia de build:
- Evidencia de tests sobre el contenido que se empaqueta:

El manifest de Hache Base registra identidad y referencias de evidencia. **No firma criptográficamente la identidad del actor y no declara Production Ready**. Para provenance/SBOM reforzada de Nivel C existe P2-06.

## 3. Contrato build → test → package

El pipeline del proyecto DEBE conservar este orden cuando use `deployment/build-artifact.sh`:

1. checkout del commit exacto aprobado;
2. working tree limpio antes de construir;
3. ejecutar el build una sola vez;
4. probar el contenido/stage que será empaquetado;
5. solo si build + tests pasan, empaquetar el stage;
6. crear manifest con commit, tamaño, SHA-256 y referencias de evidencia;
7. verificar inmediatamente artefacto + manifest;
8. publicar **ese mismo par** sin reconstruirlo.

Variables del helper:

```text
APP_ROOT
TARGET_COMMIT
ARTIFACT_CONTENT_DIR
ARTIFACT_PATH
ARTIFACT_MANIFEST
ARTIFACT_BUILD_COMMAND        # opcional; por defecto ':' para source-only
ARTIFACT_TEST_COMMAND         # obligatorio
CI_RUN_REF
BUILD_EVIDENCE_REF
TEST_EVIDENCE_REF
```

`ARTIFACT_CONTENT_DIR` debe ser un stage controlado. No apuntarlo a un directorio que contenga secretos de runtime. `ARTIFACT_PATH` y `ARTIFACT_MANIFEST` deben quedar fuera del stage para evitar auto-inclusión.

No guardar el texto de los comandos de build/test dentro del manifest: pueden incluir detalles operativos o secretos. Registrar referencias de evidencia, no credenciales.

## 4. Contrato de promoción

En release/production:

1. descargar el artefacto y manifest publicados por CI;
2. resolver el commit esperado desde la aprobación/release, no desde input anónimo;
3. `deployment/promote-artifact.sh` crea una copia privada del par;
4. verifica schema, nombre, tamaño, SHA-256 y `EXPECTED_COMMIT`;
5. expone al instalador únicamente `VERIFIED_ARTIFACT_PATH`, `VERIFIED_ARTIFACT_MANIFEST`, `VERIFIED_SOURCE_COMMIT`, `VERIFIED_ARTIFACT_SHA256` y `VERIFIED_ARTIFACT_SIZE`;
6. `PROMOTE_COMMAND` instala/copia **sin build ni pre-release tests**;
7. después continúan migraciones compatibles, health, smoke, observación y cierre según P0-10/proyecto.

`PROMOTE_COMMAND` es responsabilidad del proyecto y debe consumir el snapshot verificado de forma **sincrónica** antes de devolver control. No usar una ruta original no verificada ni volver a descargar/reconstruir dentro del comando.

## 5. Evidencia de release

Registrar por release:

| Campo | Valor |
| --- | --- |
| Release/deploy ID |  |
| Commit esperado |  |
| Artifact SHA-256/digest |  |
| CI run |  |
| Build evidence |  |
| Test evidence |  |
| Storage/registry ref |  |
| Promoción verificada | sí / no |
| Migraciones | N/A / evidencia |
| Health |  |
| Smoke CUF |  |
| Observación |  |
| Rollback artifact/ref |  |
| Owner |  |

La evidencia de P1-10 ayuda a demostrar `DPL-001`, pero **no auto-PASS** el control: debe confirmarse que producción ejecutó realmente el artefacto/commit verificado y que el resto de controles aplicables también tiene evidencia.

## 6. Rollback y compatibilidad

- Conservar el artefacto/digest anterior durante la ventana de rollback.
- El rollback no debe reconstruir el release anterior.
- Si existen migraciones, documentar compatibilidad código-esquema y punto de no retorno (`DPL-003`).
- Un cambio de configuración/runtime que no está dentro del artefacto mantiene su propia versión/evidencia.
- No mezclar en un mismo release archivos generados manualmente en producción con el artefacto promovido.

## 7. Guardrails

- No construir cambios no revisados directamente en producción.
- No aceptar solo nombre de archivo/tag mutable como identidad; verificar digest + commit.
- No crear el manifest antes de que pasen los tests requeridos.
- No editar el artefacto después de generar su SHA-256; cualquier cambio crea un artefacto nuevo.
- No copiar secretos de runtime al stage del artefacto.
- No tratar un upload exitoso como prueba de que producción sirve el release correcto; health/smoke/evidencia desplegada siguen siendo necesarios.
- No promover P1-10 a una topología universal de releases/symlinks/containers: cada proyecto adapta el instalador a su infraestructura.
