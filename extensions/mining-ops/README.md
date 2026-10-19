# Diagnóstico operativo para minería

Herramienta de solo lectura para la cuenta Linux `gpt-agent` en un VPS con
HACHE-MINER. Usa Python estándar, MariaDB por unix_socket y systemctl show.
No necesita claves de Vast, Salad, billeteras ni credenciales de aplicaciones.
No instala un LLM, no ejecuta acciones correctivas y no reemplaza los supervisores existentes.

## Uso

`python3 mining_status.py --state-dir /home/gpt-agent/mining-ops/state`

Devuelve JSON con temporizadores, presión de recursos, cobertura de Salad,
estado de sincronización y frescura/consistencia de telemetría Vast. Conserva
solo el último estado, de forma atómica, con permisos privados. Los errores
no imprimen stderr del cliente SQL ni excepciones que puedan contener secretos.
Las consultas son fijas, acotadas y no incluyen datos personales ni logs libres.
La sincronización se evalúa por proyecto Salad habilitado; no se generan
incidentes a partir de fuentes históricas de grupos eliminados o proyectos retirados.
Requiere los nombres de tablas/columnas de la versión actual de HACHE-MINER;
si cambia el esquema, informa diagnóstico desconocido en lugar de asumir éxito.

La lista de instancias registradas no es el estado actual del proveedor.
Una instancia detenida puede conservar enabled=1 en el registro. Confirmar
siempre mediante la API de Vast antes de decidir una intervención. Un único
snapshot bajo no prueba la condición temporal del controlador de parada.
Los resultados de Salad partial/error tampoco acreditan minería operativa.

## Autonomía operativa

El agente puede consultar, diagnosticar, preparar correcciones, probarlas,
crear PR y usar los procedimientos de despliegue autorizados. Las acciones
de proveedor siguen las autorizaciones específicas y presupuesto establecidos
para cada instancia. Sin presupuesto/ventana no se alquilan ni reanudan recursos.
No se destruyen instancias como recuperación. No se cambian billeteras,
umbrales, credenciales o controles de aprobación para desbloquear una tarea.
No se reinicia un minero vivo para probar una corrección.

Conservar la separación entre los supervisores de Vast y Salad. No añadir
un segundo motor de auto-stop o auto-reallocate. Las alertas se comparan por
fingerprint; avisar solo por cambios significativos, recuperación o necesidad
de intervención. No presentar cambios de edad numérica como nuevos incidentes.

El diagnóstico no impone los permisos MariaDB. Si el usuario del sistema
conserva escritura directa, documentar esa limitación: SQLGuard no está activo.
La activación de SQLGuard requiere las pruebas y transición de permisos de
`../sql-guard/MARIADB-ROLLOUT.md`.

## Instalación

Instalar exclusivamente una copia de un commit revisado e integrado, en
`/home/gpt-agent/mining-ops/releases/<commit>/`, y apuntar `current` a ella.
No modificar releases instalados ni archivos de HACHE-MINER en producción.
Una ejecución periódica puede actualizar el estado local; nunca enviar
notificaciones o ejecutar operaciones de proveedor desde este programa.
La investigación inteligente requiere un agente/scheduler independiente:
la cuenta `gpt-agent` y Desktop Commander son acceso a herramientas, no un
modelo que toma decisiones continuamente.

Pruebas: `python3 -m unittest discover -s extensions/mining-ops -p 'test_*.py'`.


## VAST-003: preparar un Vast aprobado desde el VPS

`vast_provision.py` añade un transporte SSH **acotado** desde `gpt-agent`,
que nunca alquila, arranca ni apaga una instancia Vast. Antes de un
`--stage` o `--apply` exige un archivo fijo, propiedad de root,
`/etc/hache-mining-operator/approved-vast-release.json`. Este archivo
contiene exclusivamente **metadatos no secretos**: repositorio exacto
`manglefurniture/HACHE-MINER`, commit de 40 caracteres, ID/identidad física
de la GPU, host y puerto SSH, hashes de Git blob para los cuatro archivos,
SHA-256 del tar, acción única (`stage` o `apply`) y vigencia de hasta
15 minutos. Debe ser regular, root-owned, sin enlaces y no modificable
por grupo ni otros (modo 0644 si el agente necesita leerlo). Se genera
solo a partir de un commit revisado y **fijado en GitHub** por un
proceso administrativo confiable; no confiar en hashes propuestos por el
agente que solicita el despliegue. Hay que renovar explícitamente el permiso
para pasar de `stage` a `apply`.

Acepta exclusivamente perfiles Vast ligados a identidad física verificada
por la API, `known_hosts` anclado, clave SSH propia y paquete `tar.gz`
privado de un commit aprobado de HACHE-MINER. Ese paquete solo puede contener:
`vast-auto-prepare.py`, `vast-instance-prepare.py`,
`vast-onstart.sh`, `vast-collector.py`. Se valida también SHA-256
del tar y su contenido (archivos regulares, sin enlaces, rutas o directorios
extras).

```sh
# Diagnóstico sin red ni modificación:
python3 vast_provision.py --profile vast-12345 --instance-id 12345 \
  --release-commit COMMIT40HEX

# Transfiere paquete aprobado solo a instancia running y con SSH verificado:
python3 vast_provision.py --profile vast-12345 --instance-id 12345 \
  --release-commit COMMIT40HEX --stage --confirm-instance 12345 \
  --bundle /home/gpt-agent/private/release.tar.gz

# Ejecuta el instalador existente en la GPU aprobada:
python3 vast_provision.py --profile vast-12345 --instance-id 12345 \
  --release-commit COMMIT40HEX --apply --confirm-instance 12345
```

**Prerequisitos no resueltos por el transporte:** el archivo
`/etc/hache-vast/approved-recipe.json` y la clave HMAC
`/etc/hache-vast/ingest.key` deben estar aprovisionados de forma segura
en el host antes de `--apply`. La receta requiere wallet PRL y release
del minero previamente aprobados. No usar huellas obtenidas únicamente
de un `ssh-keyscan` no autenticado.

Este transporte **no ofrece arranque de SRBMiner**, no instala secretos ni
sustituye el plan de gasto ni el supervisor financiero de Vast. Debe
implementarse posteriormente el transporte del secreto mediante un
servicio privilegiado separado y un orquestador que encadene estas fases
con autorizaciones correctas; hasta entonces no certificar autonomía
end-to-end. La operación `vast.register` en el broker es distinta y
requiere un grant root de un solo uso.

Todos los errores fallan cerrados; ninguna prueba de esta fase debe usar
GPU en producción.

Nota de seguridad: este control limita el **cliente de aprovisionamiento**,
pero no elimina otras vías de SSH root que tenga habilitadas la cuenta Linux
`gpt-agent`. Para que la política sea una frontera de seguridad global se
necesita restringir esa clave SSH mediante un forced-command o servicio
privilegiado acotado en la GPU; no considerar terminado ese aislamiento
hasta su despliegue y prueba con instancia autorizada.
