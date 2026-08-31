# UI de backend — relieve reutilizable

Patrón visual reutilizable para controles de panel administrativo derivados de Hache-Base.

## Objetivo

Dar a botones y acciones una sensación ligera de volumen sin convertir la interfaz en un diseño ornamental. El relieve debe ayudar a distinguir controles interactivos, mantener buena lectura en móvil y escritorio y conservar accesibilidad de teclado.

Este patrón se extrajo de una solución ya validada en producción, pero Hache-Base lo mantiene **genérico y opt-in**: no depende de nombres de pantallas, rutas ni reglas de negocio.

## Archivo base

`src/ui/backend-relief.css`

Clases principales:

- `.hache-control` — relieve claro/base.
- `.hache-control--primary` — variante para botones con fondo oscuro o de alta prioridad.
- `.hache-control--flat` — exclusión explícita para iconos, cierres, autocompletados, encabezados o controles posicionados que deban conservar íntegramente su geometría local.

## Regla visual aprobada

### Controles claros

El borde superior **no debe ser blanco puro**. En superficies claras se pierde visualmente y parece que el botón no tiene línea arriba.

Hache-Base usa:

```css
--hache-control-top-edge: rgba(148,163,184,.34);
```

El brillo blanco permanece **dentro** de la sombra (`inset 0 1px ...`), de modo que la lectura final sea:

1. línea superior visible;
2. brillo interior;
3. cara del control;
4. borde inferior más oscuro;
5. sombra exterior suave.

### Controles oscuros

En fondos oscuros la línea superior sí debe ser clara para crear contraste. Por eso `.hache-control--primary` usa un borde superior blanco translúcido y un borde inferior más oscuro.

## Estados

El patrón incluye:

- `:hover` solo cuando el dispositivo realmente soporta hover;
- `:active` con desplazamiento de 1 px para sensación de pulsado;
- `:focus-visible` con indicador azul sólido (`#2563eb`), diseñado para mantener un contraste mínimo de 3:1 frente a superficies claras habituales del backend;
- neutralización del hover en controles deshabilitados;
- `prefers-reduced-motion`;
- sombras de menor profundidad en pantallas de hasta 750 px.

No sustituir el indicador de foco por un borde translúcido de bajo contraste. Si un proyecto cambia el color mediante `--hache-control-focus`, debe volver a validar contraste contra sus fondos reales.

## Variante plana

`.hache-control--flat` **no es un reset visual**. Su función es excluir un control de las reglas de relieve.

El módulo usa selectores como:

```css
.hache-control:not(.hache-control--flat) { ... }
```

Por tanto, la variante plana no sobrescribe borde, sombra, `transform` ni `filter` definidos por el componente. Esto evita romper autocompletados, cierres, encabezados, iconos o controles posicionados que ya tienen geometría propia.

## Uso recomendado

```html
<button class="hache-control">Cancelar</button>
<button class="hache-control hache-control--primary">Guardar</button>
<button class="hache-control hache-control--flat" aria-label="Cerrar">×</button>
```

No aplicar `.hache-control` indiscriminadamente a todo `<button>` del proyecto. Algunos controles nativos pueden formar parte de un panel, autocompletado, menú o componente posicionado y deben conservar su geometría propia.

## Integración en proyectos derivados

1. Copiar o adaptar `src/ui/backend-relief.css` al bundle de estilos del backend.
2. Cargarlo después de los estilos base del panel para que los tokens tengan precedencia predecible.
3. Marcar explícitamente controles de acción con `.hache-control`.
4. Añadir `.hache-control--primary` solo a controles realmente oscuros/primarios.
5. Usar `.hache-control--flat` cuando el componente deba conservar sus estilos propios sin recibir borde, sombra ni desplazamiento del módulo.
6. Validar `--hache-control-focus` contra los fondos reales del proyecto y mantener al menos 3:1 de contraste para el indicador de foco.
7. Crear regresiones para controles dinámicos o convenciones locales que el proyecto añada.

## Qué no debe cambiar este módulo

- tamaños o jerarquía tipográfica del proyecto;
- lógica, permisos o navegación;
- colores de marca salvo los tokens de borde/sombra/foco;
- layout de formularios o tablas;
- estados funcionales del negocio;
- geometría propia de controles excluidos mediante `.hache-control--flat`.

## Criterio de aceptación visual

En un control claro debe distinguirse una línea fina arriba incluso sobre fondo blanco/gris claro. El brillo interior debe seguir presente, pero no reemplazar el borde real. En un control oscuro el bisel claro superior y el borde inferior oscuro deben conservar contraste. El indicador de foco debe ser inequívoco para teclado. En móvil el efecto debe ser perceptible pero más contenido que en escritorio.
