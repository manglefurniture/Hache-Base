# Arquitectura del Design System 2026

## Regla

La arquitectura oficial es `Core → Theme → Extensions`. La dependencia solo fluye en ese sentido. Core no importa Theme ni Extensions; Theme asigna identidad a contratos definidos por Core; Extensions se cargan únicamente cuando un caso real las requiere.

## Core

Infraestructura transversal y sin identidad de proyecto:

- `src/ui/core/foundation.css`: escalas físicas de espacio, tipo, duración, radios, capas, contenedores y densidad.
- `src/ui/core/semantic.css`: contratos funcionales de texto, superficie, borde, foco, estado, movimiento y layout.
- `src/ui/core/components.css`: tokens y primitives opt-in de botones, campos, estados, superficies, cards, navegación, tablas y overlays.
- `src/ui/core/base.css`: baseline mobile-first, foco, reflow, tipografía semántica, reduced motion y forced colors.
- `src/ui/core/interactions.js`: mejora progresiva opcional para preferencia de tema, disclosures y diálogos; la funcionalidad básica debe existir sin el helper.

Core puede definir nombres, estructura, estados y fallbacks. Core no define una paleta de marca, familia tipográfica propietaria, estilo fotográfico, sombra distintiva ni efecto experimental.

## Theme

Valores configurables por proyecto:

- `src/ui/themes/dimensional.css`: preset recomendado y default técnico, ligero.
- `src/ui/themes/clean.css`: menor profundidad y movimiento.
- `src/ui/themes/immersive.css`: solo variables de capacidad; no activa WebGL, parallax ni animaciones pesadas.
- overrides de light/dark, marca, tipografía, radios, sombras, profundidad, densidad, controles, cards, fotografía, iconografía e intensidad de movimiento.

Los presets se activan con `data-visual-level="clean|dimensional|immersive"`. La ausencia del atributo equivale a Dimensional. `immersive` siempre requiere opt-in explícito y justificación en el perfil del proyecto.

Los temas de color se resuelven así:

1. light por defecto seguro;
2. `prefers-color-scheme: dark` si no hay preferencia manual;
3. `data-theme="light|dark"` como override explícito;
4. persistencia local únicamente cuando el proyecto habilita selector.

## Extensions

Capacidades específicas, ausentes del bundle Core:

- WebGL o 3D complejo;
- scrollytelling avanzado;
- timelines especiales;
- visores y comparadores;
- heroes experimentales;
- transiciones propietarias de un proyecto.

`src/ui/extensions/README.md` define el contrato de admisión: valor demostrado, carga diferida, fallback estático, desactivación segura, reduced motion, control de recursos, semántica/SEO preservados y pruebas. Esta misión no añade ninguna extensión de ejecución.

## Fronteras

| Decisión | Core | Theme | Extension |
| --- | --- | --- | --- |
| Nombre del token de foco | Sí | No | No |
| Color concreto de foco/branding | Fallback accesible neutro | Sí | No |
| Estructura y estados de botón | Sí | No | No |
| Radio, sombra y profundidad del botón | Contrato | Sí | No |
| Reduced motion | Sí | Puede reducir más | Debe obedecerlo |
| Paleta dark | Contrato/fallback | Sí | No |
| WebGL | No | Solo nivel permitido | Sí |
| Layout de un comparador específico | No | Tratamiento visual | Sí |

## Compatibilidad

`src/ui/backend-relief.css` se conserva como entrada compatible y pasa a consumir la nueva jerarquía de tokens. Sus clases públicas no cambian. Los proyectos pueden seguir cargándolo solo, con fallbacks seguros, o cargar el módulo Core + Theme para configuración completa.

## Regla de promoción

Una Extension solo puede promoverse a Core después de demostrar reutilización transversal en proyectos distintos, mantener fallback, no introducir identidad específica y superar la matriz de adopción de tendencias. “Podría reutilizarse” no constituye evidencia.
