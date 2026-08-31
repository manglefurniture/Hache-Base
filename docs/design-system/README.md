# Design System 2026 — guía de adopción

La norma de autoridad es `DESIGN-SYSTEM-2026-FINAL.md`. Este módulo la convierte en infraestructura reusable sin imponer branding. Hache Base estandariza calidad, no apariencia.

## Carga mínima

Para adopción completa puede cargarse `src/ui/hache-design-system.css`. En producción se recomienda concatenar/minificar sus entradas para evitar múltiples requests. Si existe pipeline CSS, usar este orden:

1. `core/foundation.css`;
2. `core/semantic.css`;
3. `core/base.css`;
4. `core/components.css`;
5. Theme/preset;
6. overrides de proyecto;
7. Extensions justificadas.

El Core no necesita JavaScript. `core/interactions.js` es progressive enhancement y no tiene dependencias.

## Configuración de proyecto

```html
<html lang="es" data-visual-level="dimensional" data-density="comfortable">
```

- omitir `data-visual-level` equivale a `dimensional`;
- `clean` reduce profundidad/motion;
- `immersive` es opt-in y no activa efectos por sí solo;
- `data-density="compact"` reduce densidad para herramientas/tablas;
- ausencia de `data-theme` sigue al sistema;
- `data-theme="light|dark"` fuerza preferencia manual.

El proyecto debe sobrescribir tokens semánticos, no editar Core:

```css
:root {
  --color-primary: /* color de marca validado */;
  --font-brand: /* familia del proyecto */;
  --radius-surface: /* tratamiento del proyecto */;
}
```

## Selector de tema opcional

No se añade un switch global. Si el producto lo necesita:

```html
<button type="button" data-hache-theme-value="light">Claro</button>
<button type="button" data-hache-theme-value="dark">Oscuro</button>
<button type="button" data-hache-theme-value="system">Sistema</button>
<script type="module">
  import { initThemePreference } from "/ui/core/interactions.js";
  initThemePreference();
</script>
```

La preferencia persiste cuando `localStorage` está disponible y degrada sin error cuando no lo está.

## Contratos de componentes

### Botón

Variantes: `.hache-button`, `--secondary`, `--ghost`, `--destructive`. Usar `disabled` para controles nativos, `aria-disabled="true"` para enlaces que deban permanecer enfocables y `aria-busy="true"` con texto que siga identificando la acción. No usar más de un CTA primario por sección salvo justificación de producto.

### Formularios

Los estilos no corrigen markup deficiente. Cada campo requiere `<label>` visible, tipo/inputmode adecuado, `autocomplete` cuando aplique, instrucciones y error próximos mediante `aria-describedby`; `aria-invalid="true"` activa borde doble/énfasis no dependiente solo del color. No validar agresivamente al escribir. `initSubmissionGuards()` es opcional para flujos asíncronos y se libera con `hache:submit-complete`.

### Navegación y disclosures

Usar enlaces reales y `aria-current="page"`. Los menús esenciales nunca dependen solo de hover. Para disclosure, el trigger necesita `aria-controls` y el panel un `id`; `initDisclosures()` sincroniza `aria-expanded`, permite Escape, devuelve foco y puede cerrar fuera con `data-hache-dismiss="outside"`.

### Diálogos

Preferir `<dialog class="hache-dialog">` y `showModal()` mediante `initDialogs()`: el navegador aísla el fondo, contiene el foco y gestiona Escape; el helper devuelve foco al disparador. Siempre ofrecer cierre visible. No usar modal para contenido que merece ruta propia.

### Estados

Loading, success, warning y error requieren nombre/mensaje accesible. Las clases `.hache-status--*` añaden forma además de color, pero el texto del estado sigue siendo obligatorio. Los estados vacíos deben explicar situación y siguiente acción posible.

### Tablas administrativas

`.hache-table-region` limita el overflow a la región; no se oculta overflow global. Mantener `<caption>`, headers/`scope`, lectura lineal y alternativa responsive si la tabla deja de ser comprensible. Los backends usan Clean o Dimensional; Immersive no es default.

## Contratos no simulables en la base

Estos puntos se verifican sobre cada proyecto real:

- navegación/arquitectura de información completa;
- contraste de la paleta y assets en light/dark;
- formularios y conservación de datos del servidor;
- dimensiones, `srcset`, `sizes`, lazy/LCP y alt de imágenes reales;
- heading outline, canonical, schema, robots y sitemap reales;
- CWV de laboratorio/campo, consola, fuentes y peso de bundles;
- zoom/reflow y cinco categorías mínimas de viewport.

No se marca un proyecto conforme solo por cargar este CSS.

## Imágenes

Declarar `width`/`height`; usar formatos y responsive images adecuados; `loading="lazy"` solo fuera del contenido crítico; no lazy-load del LCP si retrasa su carga. El Theme define recorte/tratamiento. Alt vacío es válido solo para decoración genuina.

## Iconos

Preferir SVG coherente y `currentColor`. Un control icon-only necesita nombre accesible; si el significado no es universal, acompañar con texto visible.

## Performance y SEO

Completar `templates/PERFORMANCE-BUDGET.md`. Core no incluye WebGL, framework, fuente, icon font ni runtime obligatorio. El contenido principal permanece en HTML, los enlaces son rastreables y el módulo SEO existente sigue siendo autoridad secundaria. View Transitions y efectos de scroll solo se incorporan como progressive enhancement con fallback.

## Checklist

Usar `docs/CHECKLIST-NUEVO-PROYECTO.md` y registrar excepciones a MUST con alcance, causa, mitigación y fecha de revisión.
