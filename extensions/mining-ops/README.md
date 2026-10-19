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
