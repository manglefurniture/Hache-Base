# Review y cierre de Pull Requests

## Objetivo

Cerrar cambios con una secuencia verificable sin confundir **CI verde** con **revisión técnica completa**.

## Flujo recomendado

`PR -> CI/Quality -> revisión automática/humana -> corregir hallazgos válidos -> regresiones -> CI/Quality final -> merge -> deploy controlado -> smoke test`

Un workflow verde demuestra que pasaron las comprobaciones implementadas. No demuestra por sí solo que no existan observaciones válidas de revisión de código.

## Estado obligatorio de cada hallazgo

Antes del merge, cada review thread relevante debe poder clasificarse como uno de estos estados:

- **corregido**: el cambio está implementado y cubierto por una verificación proporcional;
- **ya resuelto**: el código actual ya contiene la solución por un cambio posterior;
- **no aplica / falso positivo**: existe evidencia concreta para descartarlo;
- **requiere decisión humana**: falta una regla de negocio, dato legal, dato operativo o decisión que no debe inventarse.

No dejar comentarios técnicamente atendidos acumulados como deuda administrativa. Una vez comprobada su resolución material, cerrar el hilo cuando el flujo del repositorio lo permita.

## Corrección quirúrgica

Cuando una revisión detecte un problema concreto:

1. reproducir o demostrar el caso señalado;
2. tocar el mínimo código necesario;
3. añadir o ajustar una regresión específica cuando aporte valor;
4. ejecutar las pruebas afectadas y la suite establecida por el proyecto;
5. detenerse al resolver el alcance acordado.

Un fix de revisión no debe convertirse automáticamente en auditoría, refactor, optimización general ni búsqueda abierta de problemas nuevos.

## Hallazgos posteriores al propio fix

Una corrección puede revelar un segundo caso límite. Tratarlo como un hallazgo nuevo: validar su impacto, corregirlo en un cambio pequeño y no marcarlo como resuelto solo porque el hallazgo original ya esté atendido.

## Deploy

El merge y el despliegue son eventos distintos. Tras mergear:

- desplegar un commit identificable;
- ejecutar health/smoke checks proporcionales al cambio;
- confirmar que producción funciona antes de declarar el ciclo cerrado.

## Regla de eficiencia para agentes

Cuando se delegue a un agente:

- proporcionar los hallazgos concretos y archivos conocidos;
- prohibir explícitamente auditorías o refactors no solicitados;
- definir pruebas mínimas y criterio de parada;
- pedir un PR sin merge cuando el riesgo amerite revisión humana;
- evitar repetir suites costosas sin cambios relevantes.
