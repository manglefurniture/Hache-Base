# HACHE BASE — DESIGN SYSTEM 2026

**Estado:** Norma cerrada y aprobada v1.0
**Ámbito:** Sitios públicos, landing pages, tiendas, portales, sistemas administrativos y futuros productos construidos sobre Hache Base.
**Objetivo:** Establecer una base visual y de experiencia moderna, reutilizable, accesible, rápida y configurable, sin convertir Hache Base en una plantilla visual repetitiva.
**Cierre de norma:** 30 de agosto de 2026.

---

## 0. Lenguaje normativo

Esta guía usa tres niveles:

- **MUST / DEBE:** requisito obligatorio para considerar que un proyecto cumple Hache Base.
- **SHOULD / DEBERÍA:** recomendación fuerte; puede omitirse si existe una razón de producto o técnica documentada.
- **MAY / PUEDE:** recurso opcional, dependiente de identidad, proyecto o nivel visual.

La regla superior es simple:

> **Hache Base estandariza calidad, no apariencia.**

---

## 1. Filosofía de diseño

### 1.1 Principios permanentes

Todo proyecto Hache Base DEBE:

1. Ser comprensible antes de ser espectacular.
2. Ser funcional antes de ser decorativo.
3. Tener identidad propia y evitar apariencia de plantilla genérica.
4. Diseñarse mobile-first.
5. Integrar accesibilidad y rendimiento desde el diseño, no como corrección posterior.
6. Usar movimiento con intención.
7. Incorporar profundidad o 3D solo cuando aporte jerarquía, experiencia o identidad.
8. Priorizar contenido real, fotografía auténtica y lenguaje propio de la marca.
9. Escalar desde componentes reutilizables.
10. Aplicar progressive enhancement: la experiencia principal no puede depender de una tecnología experimental.

> **Hache Base estandariza calidad, no apariencia.**

### 1.2 Prioridad de identidad y propósito

Una tendencia NUNCA DEBE imponerse sobre la personalidad, el público, la accesibilidad o el objetivo comercial del proyecto.

> **Cada decisión visual debe tener una razón de negocio, de experiencia o de identidad.**

### 1.3 Tendencias como recursos, no como obligación

Hache Base reconoce como recursos contemporáneos:

- jerarquía tipográfica expresiva;
- composiciones editoriales y asimétricas;
- capas, profundidad y sensación táctil;
- microinteracciones;
- transiciones de estado y de página;
- scrollytelling moderado;
- texturas y tratamientos visuales propios;
- fotografía y elementos humanos frente a estética genérica de IA;
- 3D ligero;
- color expresivo;
- interfaces menos homogéneas.

Ningún proyecto DEBE usar todas estas tendencias. La identidad del proyecto determina cuáles se activan.

## 2. Arquitectura visual de Hache Base

La arquitectura visual se organiza en tres capas:

### Capa A — Core

Se reutiliza entre todos los proyectos:

- grid y layout;
- escala de espaciado;
- accesibilidad;
- comportamiento responsive;
- estados de interacción;
- formularios;
- patrones de navegación;
- reglas de movimiento;
- performance;
- semántica;
- componentes estructurales;
- estructura de design tokens.

### Capa B — Theme

Cada proyecto DEBE poder definir, como mínimo:

- colores;
- tipografía;
- radios;
- sombras;
- profundidad;
- estilo de botones y tarjetas;
- iconografía;
- estilo fotográfico;
- intensidad de movimiento;
- nivel de 3D;
- densidad visual.

Dos proyectos construidos con Hache Base NO DEBERÍAN parecer versiones coloreadas de la misma web.

### Capa C — Extensions

Resuelve necesidades específicas que no pertenecen al core, por ejemplo:

- visor 3D;
- timeline interactivo;
- comparador;
- hero experimental;
- módulo editorial especial;
- integración visual propia de un proyecto.

> **Una funcionalidad o recurso visual específico no debe entrar al core solo porque ya fue construido una vez. Debe demostrar reutilización real antes de convertirse en parte de Hache Base.**

Arquitectura oficial:

> **Core → Theme → Extensions**

## 3. Niveles de expresión visual

Cada proyecto DEBE declarar un nivel visual base. Los niveles son presets iniciales configurables, no planes cerrados.

Un mismo proyecto PUEDE mezclar niveles por sección cuando exista coherencia; por ejemplo, navegación Clean, home Dimensional y hero Immersive.

### Nivel 1 — CLEAN

Ideal para corporativos, servicios profesionales, paneles administrativos y contextos donde claridad y velocidad predominan.

Características:

- movimiento mínimo;
- composición limpia;
- profundidad suave;
- tipografía fuerte pero contenida;
- pocas decoraciones.

### Nivel 2 — DIMENSIONAL

**Preset recomendado por defecto para sitios comerciales Hache.**

Características:

- capas;
- tarjetas con profundidad;
- sombras y gradientes controlados;
- microinteracciones;
- entradas suaves;
- fotografías protagonistas;
- algún recurso distintivo de marca.

Debe sentirse moderno y premium sin sacrificar rendimiento.

### Nivel 3 — IMMERSIVE

Opt-in. Nunca es el nivel por defecto.

Puede incorporar:

- scrollytelling;
- composiciones editoriales;
- parallax;
- transiciones avanzadas;
- 3D;
- WebGL;
- elementos interactivos especiales.

Su uso DEBE justificar explícitamente el coste de rendimiento, accesibilidad, mantenimiento y complejidad.

Resumen:

> **Dimensional = default · Clean = disponible · Immersive = opt-in y justificado**

## 4. Design Tokens

Los valores visuales principales DEBEN implementarse mediante tokens y no repetirse como valores arbitrarios por el CSS.

La jerarquía oficial es:

> **Foundation → Semantic → Component**

Ejemplo conceptual:

`#0B57D0 → --color-primary → --button-primary-bg`

### Tokens mínimos

Hache Base DEBE contemplar tokens para:

- color;
- tipografía: tamaño, peso, line-height y letter-spacing;
- espaciado;
- radios;
- sombras y elevación;
- z-index;
- opacidad;
- blur;
- motion: duración y easing;
- contenedores y anchos máximos;
- rangos responsive;
- densidad de interfaz.

Los nombres DEBEN representar función y no apariencia accidental.

Preferir:

`--color-primary`, `--surface-elevated`, `--text-muted`, `--motion-fast`.

Evitar:

`--blue-1`, `--big-shadow`, `--card-red`.

> **Los componentes del core no deben consumir valores visuales directos; deben consumir tokens semánticos.**

> **El core define la estructura de tokens; cada proyecto define sus valores.**

## 5. Color y temas

### 5.1 Contraste

MUST:

- texto normal: contraste mínimo 4.5:1;
- texto grande: mínimo 3:1;
- componentes e información visual necesaria: mínimo 3:1.

La identidad de marca nunca justifica contenido ilegible.

### 5.2 Marca y función

Cada proyecto SHOULD definir:

- primario;
- secundario;
- acento;
- fondo;
- superficies;
- texto principal;
- texto secundario;
- éxito;
- advertencia;
- error;
- información.

Los colores funcionales no deben improvisarse a partir de la paleta de marca.

Ningún estado debe depender únicamente del color; DEBE existir texto, icono, forma, borde u otra señal cuando sea necesario.

### 5.3 Light / Dark mode

> **Hache Base DEBE soportar light y dark mode a nivel de tokens.**

Cada proyecto PUEDE:

- usar un único modo;
- seguir `prefers-color-scheme`;
- ofrecer selector manual;
- combinar sistema + preferencia persistida del usuario.

Si existe selector manual, la preferencia SHOULD recordarse.

Contraste, imágenes, logos, sombras, gráficos y estados DEBEN revisarse en ambos modos. No se considera dark mode válido una simple inversión automática de colores.

### 5.4 Gradientes

MAY utilizarse para branding, profundidad, fondos o énfasis. No DEBEN reducir legibilidad ni convertirse en ruido permanente.

Cierre del bloque:

> **Marca + Función + Contraste + Soporte nativo para temas**

## 6. Tipografía

### 6.1 Jerarquía semántica

Todo proyecto DEBE disponer de una jerarquía consistente:

**Display → H1 → H2 → H3 → Body → Small → UI/Label**

La jerarquía visual no sustituye la jerarquía semántica HTML.

### 6.2 Fluidez

La tipografía SHOULD ser fluida y no depender únicamente de saltos bruscos entre móvil y desktop.

`clamp()` SHOULD utilizarse cuando tenga sentido.

```css
.hero-title {
  font-size: clamp(2.5rem, 7vw, 7rem);
}
```

La tipografía expresiva PUEDE dominar un hero, pero NUNCA comprometer lectura, accesibilidad o responsive.

### 6.3 Marca vs. interfaz

El sistema PUEDE diferenciar entre tipografía de marca y tipografía de lectura/interfaz.

Cada proyecto puede tener voz tipográfica distinta, mientras mantiene consistente la estructura de jerarquía.

### 6.4 Performance

SHOULD:

- limitar familias y pesos;
- cargar solo variantes usadas;
- preferir WOFF2;
- utilizar una estrategia adecuada de `font-display`;
- evitar fuentes de iconos cuando SVG sea mejor solución.

Cierre del bloque:

> **Jerarquía + Fluidez + Performance**

## 7. Espaciado y composición

Hache Base DEBE usar una escala coherente de espaciado.

Escala base de referencia:

`4 / 8 / 12 / 16 / 24 / 32 / 48 / 64 / 96 / 128`

Estos valores SHOULD consumirse mediante tokens semánticos (`--space-xs`, `--space-sm`, etc.) en vez de números arbitrarios repetidos.

### 7.1 Ritmo y lectura

El contenido de lectura prolongada SHOULD mantener aproximadamente 60–75 caracteres por línea.

El espacio vacío se considera parte activa de la composición. No se debe rellenar una sección únicamente porque “se ve vacía”.

### 7.2 Densidad configurable

Hache Base DEBE poder variar densidad según contexto, al menos conceptualmente:

- **Comfortable** — landings, corporativos, sitios editoriales;
- **Compact** — dashboards, tablas y herramientas de gestión.

### 7.3 Libertad controlada

La cuadrícula es estructura, no cárcel.

MAY utilizarse:

- asimetría;
- overlays;
- elementos que crucen columnas;
- composiciones editoriales;
- desplazamientos visuales.

Siempre que mantengan legibilidad, accesibilidad y adaptación responsive.

Cierre del bloque:

> **Escala + Ritmo + Densidad configurable + Libertad controlada**

## 8. Responsive 2026

Responsive NO significa únicamente “que no se rompa en móvil”. La composición puede cambiar según el espacio disponible.

### MUST

- mobile-first real;
- sin scroll horizontal accidental;
- navegación adaptable;
- jerarquía y densidad adaptables;
- acciones principales accesibles;
- zoom y reflow funcionales;
- contenido esencial disponible en todos los tamaños.

### Media Queries + Container Queries

Media Queries siguen siendo válidas para estructura general.

Los componentes reutilizables SHOULD usar Container Queries cuando su comportamiento dependa del espacio disponible dentro del componente y no del viewport completo.

> **Los componentes deben responder a su contenedor, no asumir dónde serán colocados.**

### Breakpoints

Los breakpoints SHOULD definirse por necesidad del contenido y layout, no por una lista rígida de modelos de dispositivos.

### Pruebas mínimas

Todo proyecto DEBE revisarse, como mínimo, en categorías equivalentes a:

- móvil pequeño;
- móvil grande;
- tablet;
- laptop;
- desktop amplio.

Cierre del bloque:

> **Mobile-first + Component-responsive + Breakpoints por contenido + Reflow real**

## 9. Navegación

> **El usuario siempre debe entender dónde está, qué puede hacer y cómo volver.**

MUST:

- indicar estado activo cuando sea relevante;
- ser operable por teclado;
- mostrar foco claramente;
- evitar interacciones esenciales dependientes solo de hover;
- cerrar correctamente menús, dropdowns y overlays;
- mantener acciones esenciales accesibles en móvil.

### Patrones permitidos

Hache Base PUEDE ofrecer, según el proyecto:

- header clásico;
- mega menu;
- bottom navigation;
- sidebar;
- navegación contextual;
- breadcrumbs.

El patrón debe responder a la arquitectura de información, no a una moda.

### Mobile

La experiencia SHOULD considerar uso con una mano y alcance razonable del pulgar.

El menú hamburguesa no debe utilizarse para ocultar una arquitectura de información mal resuelta.

Cierre del bloque:

> **Orientación + Accesibilidad + Alcance móvil + Arquitectura clara**

## 10. Componentes interactivos

> **Todo componente interactivo debe definir sus estados antes de considerarse terminado.**

Cuando aplique, DEBE contemplar:

- default;
- hover;
- focus-visible;
- active;
- disabled;
- loading;
- success;
- warning;
- error.

Los estados SHOULD ser perceptibles por más de una señal cuando sea necesario; no basta con cambiar únicamente color.

### Feedback

> **El usuario nunca debe preguntarse si el sistema recibió su acción.**

Por ello:

- feedback inmediato;
- prevención de doble activación cuando pueda duplicar operaciones;
- loading claro;
- evitar saltos de layout durante operaciones;
- desactivar temporalmente acciones procesándose cuando corresponda.

### Área táctil Hache

WCAG 2.2 AA establece 24×24 CSS px bajo sus condiciones y excepciones. Hache Base adopta como objetivo interno:

> **44×44 CSS px para acciones táctiles independientes siempre que sea viable.**

Cierre del bloque:

> **Estados completos + Feedback inmediato + Tacto seguro + Consistencia visual**

## 11. Botones y CTA

Jerarquía recomendada:

- **Primary** — acción principal;
- **Secondary** — alternativa;
- **Tertiary / Ghost** — menor peso;
- **Destructive** — acción peligrosa.

> **Una sección no debería tener más de una acción primaria compitiendo visualmente.**

> **El texto del botón debe describir qué ocurrirá al activarlo.**

Preferir “Guardar cambios”, “Solicitar información” o “Inscribirme” frente a etiquetas ambiguas como “Enviar” o “Clic aquí”.

MUST:

- focus-visible;
- estados completos;
- loading en operaciones asíncronas;
- disabled cuando corresponda;
- iconos acompañados de texto cuando la acción no sea universalmente comprensible.

Profundidad, escala y microanimación MAY utilizarse como feedback, siempre de forma sutil.

> **La prioridad visual de un CTA responde al objetivo de conversión, no a que todos los botones quieran protagonismo.**

Cierre del bloque:

> **Jerarquía + Claridad + Conversión + Estados completos**

## 12. Formularios

> **Un formulario debe pedir lo mínimo necesario, en el momento adecuado, y explicar claramente cualquier error.**

MUST:

- labels visibles;
- placeholder solo como ayuda, nunca como sustituto del label;
- tipos de input correctos;
- teclado adecuado en móvil;
- `autocomplete` cuando aplique;
- validación cercana al campo;
- conservar datos válidos cuando ocurra un error;
- indicar campos obligatorios;
- navegación por teclado;
- errores que no dependan solo del color.

> **No pedir dos veces un dato que el sistema ya conoce.**

> **No validar agresivamente mientras el usuario todavía está escribiendo.**

SHOULD:

- mostrar progreso en formularios largos;
- dividir en pasos solo cuando reduzca carga cognitiva;
- permitir mostrar/ocultar contraseña;
- ofrecer mensajes claros de éxito;
- prevenir doble envío;
- mostrar loading;
- preservar estado al volver atrás cuando sea técnicamente razonable.

En registro, compra, inscripción u otros flujos críticos, el usuario DEBE saber qué falta, por qué falta y cómo corregirlo.

Cierre del bloque:

> **Mínimo esfuerzo + Errores claros + Datos persistentes + Mobile-friendly**

## 13. Cards y superficies

Las cards son un patrón, no una obligación.

Cuando se usen DEBEN agrupar contenido o acciones realmente relacionadas. No convertir cada párrafo en una tarjeta.

### Profundidad base

Se establecen tres niveles conceptuales:

- **Surface 0** — fondo/plano;
- **Surface 1** — contenido elevado;
- **Surface 2** — flotante, modal o popover.

Borde, sombra, fondo y elevación deben provenir del Theme y de tokens semánticos.

Una tarjeta interactiva DEBE dejar claro qué parte es accionable y mantener todos los estados correspondientes.

**Cierre:** las superficies comunican agrupación y jerarquía; no son decoración automática.

## 14. Profundidad, 3D y estética táctil

La profundidad PUEDE lograrse mediante superposición, sombra, blur, gradiente, perspectiva, escala, iluminación, textura o 3D real.

Su función primaria es jerarquía, identidad o comprensión espacial.

### MUST

El 3D no puede:

- ocultar contenido esencial;
- impedir navegación;
- ser requisito para comprender la página;
- degradar gravemente Core Web Vitals;
- romper teclado, zoom o reduced motion.

### WebGL / escenas pesadas

Solo SHOULD usarse cuando el valor visual o funcional sea demostrable.

Si se utiliza:

- lazy load;
- fallback estático;
- control de DPR/resolución;
- pausa o reducción cuando no está visible;
- degradación razonable en dispositivos limitados;
- respeto a preferencias de movimiento.

> **3D y WebGL son extensiones opt-in, nunca dependencias del core.**

## 15. Movimiento y microinteracciones

### Principio

> **El movimiento debe explicar, orientar o reforzar. Nunca competir con el contenido.**

### Tipos aprobados

- feedback de botones;
- entradas discretas;
- cambios de estado;
- expansión/colapso;
- transición entre vistas;
- énfasis tipográfico puntual;
- narrativa por scroll moderada.

### Rangos iniciales

- microinteracción: 120–220 ms;
- transición UI: 180–300 ms;
- entrada de sección: 250–450 ms.

Son referencias, no límites rígidos.

### MUST

- respetar `prefers-reduced-motion`;
- no depender del movimiento para información indispensable;
- evitar flashes peligrosos;
- no bloquear interacción esperando animación decorativa;
- evitar cambios de layout innecesarios.

### Anti-patrones

- scroll hijacking;
- animar todo al entrar;
- elementos flotando eternamente sin función;
- retrasar texto imprescindible;
- parallax agresivo.

**Cierre:** movimiento con intención, reducido cuando el usuario lo pide y barato en rendimiento.

## 16. View Transitions

La View Transition API MAY utilizarse para dar continuidad visual entre vistas o documentos.

A 2026 su soporte moderno es considerablemente mejor, pero sigue tratándose como progressive enhancement por compatibilidad con navegadores o dispositivos antiguos y por variación entre capacidades.

MUST:

- fallback sin transición;
- respeto a reduced motion;
- no romper historial, scroll, foco ni navegación;
- no retrasar contenido esencial;
- evitar transiciones innecesarias en operaciones frecuentes.

> **View Transitions mejora la experiencia; nunca define la funcionalidad.**

## 17. Scroll y scrollytelling

Scrollytelling MAY utilizarse principalmente en niveles Dimensional e Immersive.

MUST:

- scroll nativo;
- contenido legible sin el efecto;
- navegación razonable por teclado;
- secciones con propósito narrativo;
- no secuestrar rueda, trackpad o gesto;
- no convertir una página simple en una demo tecnológica.

Efectos vinculados al scroll SHOULD pausarse o reducirse cuando no aporten valor o cuando el usuario solicite menos movimiento.

> **Si el efecto no mejora la narrativa, se elimina.**

## 18. Fotografía e imagen

Hache Base SHOULD favorecer fotografía auténtica, escenas creíbles y tratamiento visual consistente con la marca.

La imagen generada por IA PUEDE utilizarse, pero NO DEBERÍA introducir una estética genérica, falsa o incoherente cuando existe material real mejor.

### Técnica

MUST cuando corresponda:

- dimensiones declaradas;
- compresión;
- formatos modernos;
- `srcset` / `sizes`;
- lazy loading fuera del primer viewport;
- texto alternativo significativo;
- evitar lazy-load del elemento LCP cuando perjudique su carga.

El Theme SHOULD definir tratamiento fotográfico: proporciones, recorte, contraste, bordes, filtros y comportamiento light/dark.

**Cierre:** autenticidad visual + consistencia + optimización.

## 19. Iconografía

SHOULD:

- utilizar SVG cuando sea razonable;
- mantener una familia visual coherente;
- evitar mezclar estilos sin justificación;
- acompañar iconos ambiguos con texto;
- heredar color mediante tokens cuando sea posible.

MUST existir nombre accesible para controles representados solo por icono.

No usar iconos como sustituto decorativo de una arquitectura clara.

**Cierre:** iconos consistentes, comprensibles y accesibles.

## 20. Modales, overlays, popovers y capas

MUST:

- gestionar foco correctamente;
- permitir cierre claro;
- funcionar por teclado;
- evitar que elementos sticky u overlays oculten el foco;
- bloquear interacción con el fondo cuando corresponda;
- devolver el foco al lugar lógico al cerrar;
- evitar cierres accidentales en tareas críticas.

Los modales NO DEBEN sustituir una arquitectura de información adecuada ni usarse para contenido que merece una página propia.

Z-index DEBE gestionarse mediante tokens/capas definidas, no con una escalada de números arbitrarios.

**Cierre:** las capas deben comportarse de forma predecible y accesible.

## 21. Accesibilidad

Objetivo mínimo general:

> **WCAG 2.2 AA**

Hache Base SHOULD superar AA cuando sea razonable.

MUST:

- HTML semántico;
- navegación por teclado;
- foco visible;
- contraste suficiente;
- labels;
- landmarks;
- alt text;
- orden DOM lógico;
- zoom y reflow;
- reduced motion;
- mensajes de error comprensibles;
- no depender solo de color, sonido o movimiento;
- alternativa a gestos de arrastre cuando WCAG lo requiera;
- target size conforme a AA, con objetivo interno Hache de 44×44 CSS px en acciones táctiles independientes.

### Focus

El foco no debe quedar oculto por headers sticky, banners, overlays u otros elementos. El indicador DEBE ser claramente perceptible.

La accesibilidad se prueba durante el desarrollo, no únicamente al final.

**Cierre:** accesibilidad como requisito de producto y definición de terminado.

## 22. Performance como regla de diseño

> **Un efecto visual que destruye rendimiento es un defecto de diseño.**

Objetivos Core Web Vitals:

- **LCP ≤ 2.5 s**
- **INP ≤ 200 ms**
- **CLS ≤ 0.1**

Evaluados idealmente con datos reales en percentil 75 y segmentados por dispositivo.

### SHOULD

- minimizar JavaScript inicial;
- preferir CSS para efectos simples;
- dividir código pesado;
- lazy load de módulos no críticos;
- optimizar imágenes;
- limitar fuentes y pesos;
- evitar dependencias grandes para efectos pequeños;
- pausar animaciones fuera de viewport cuando corresponda;
- establecer performance budget por proyecto.

### Performance budget

Proyectos Dimensional e Immersive SHOULD declarar presupuesto para JS, imágenes, fuentes y efectos avanzados antes de incorporar recursos pesados.

**Cierre:** performance forma parte del lenguaje visual, no es trabajo posterior de optimización.

## 23. SEO + Diseño

La norma visual DEBE coexistir con la norma SEO de Hache Base.

MUST:

- contenido principal disponible en HTML accesible;
- jerarquía correcta de headings;
- texto relevante no convertido exclusivamente en imagen;
- evitar experiencias canvas-only para contenido principal;
- enlaces reales y rastreables;
- navegación pública comprensible;
- canonical, metadata y datos estructurados preservados cuando apliquen;
- no ocultar contenido crítico esperando interacciones o JavaScript decorativo.

El diseño PUEDE ser avanzado sin convertirse en una caja negra para buscadores, lectores o agentes.

> **SEO y diseño son capas cooperativas de Hache Base, no disciplinas enfrentadas.**

## 24. Diseño preparado para asistentes y agentes

Las interfaces modernas serán consumidas por personas, buscadores, lectores de pantalla y agentes automatizados.

Hache Base SHOULD:

- usar estructura semántica;
- etiquetar acciones claramente;
- mantener contenido textual accesible;
- evitar interfaces donde toda la información dependa de coordenadas visuales;
- usar formularios y acciones con nombres comprensibles;
- exponer estados identificables;
- mantener navegación y enlaces reales.

Preparar una web para agentes NO significa quitar personalidad ni diseñar para robots por encima de las personas.

**Cierre:** semántica robusta para múltiples formas de consumo.

## 25. Personalidad de proyecto

Antes de iniciar la capa visual, cada proyecto SHOULD definir un mini manifiesto.

### Personalidad

3–5 atributos que describen cómo debe sentirse.

Ejemplo:

`enérgico / cercano / acuático / profesional / adulto`

### Evitar

3–5 atributos que expresamente NO debe transmitir.

Ejemplo:

`infantil / clínico / genérico / saturado`

### Intensidad visual

`Clean / Dimensional / Immersive`

### Movimiento

`mínimo / medio / alto`

### Densidad

`comfortable / compact / mixta`

### Temas

`light / dark / system / selector`

### Fotografía

Definir lenguaje, recorte y tratamiento.

### Recurso propietario

Todo proyecto comercial SHOULD intentar incorporar al menos un recurso reconocible propio: forma, patrón, transición, composición, tipografía, textura, fotografía o iconografía.

> **La personalidad del proyecto es parte de la especificación, no una decoración al final.**

## 26. Paneles administrativos y aplicaciones

Los dashboards comparten la base Hache, pero priorizan claridad, velocidad operativa y densidad controlada.

MUST:

- jerarquía clara;
- estados y feedback inmediatos;
- tablas adaptables;
- filtros accesibles;
- acciones destructivas diferenciadas;
- navegación eficiente;
- densidad configurable;
- teclado y focus bien resueltos;
- estados vacíos, loading y error diseñados.

MAY:

- profundidad ligera;
- superficies elevadas;
- microinteracciones;
- gráficos;
- transiciones discretas;
- dark mode cuando resulte útil.

Los backends usarán preferentemente Clean o Dimensional. Immersive solo se justifica en módulos concretos.

> **Un panel administrativo no debe convertirse en una landing de premios de diseño.**

## 27. Anti-patrones Hache

Evitar por defecto:

1. Glassmorphism en todas las superficies.
2. Sombras intensas por todas partes.
3. Gradientes sin función.
4. Scroll hijacking.
5. Cursores personalizados como requisito de interacción.
6. Autoplay de video pesado.
7. Carruseles para contenido imprescindible.
8. Menús ocultos sin necesidad.
9. Texto con contraste pobre por estética.
10. Animaciones de entrada en absolutamente todo.
11. Varias librerías para un efecto mínimo.
12. WebGL decorativo permanente sin justificación.
13. Fotografías de IA genéricas cuando existe material real mejor.
14. Interfaces que parecen una plantilla recoloreada.
15. Diseñar desktop y luego “arreglar móvil”.
16. Ocultar contenido crítico hasta que JavaScript ejecute.
17. Componentes sin focus/disabled/loading/error.
18. Efectos que empeoran CLS.
19. Imágenes gigantes sin optimización.
20. Tendencias usadas solo porque están de moda.
21. Z-index arbitrarios crecientes.
22. Dark mode por simple inversión automática.
23. Validación agresiva mientras el usuario escribe.
24. Demasiados CTAs primarios compitiendo.
25. Subir al core una solución específica sin evidencia de reutilización.

**Cierre:** si una decisión añade complejidad sin añadir valor, se elimina.

## 28. Criterio de adopción de una tendencia futura

Una nueva tendencia solo debe incorporarse al core de Hache Base si supera estas preguntas:

1. ¿Mejora experiencia, conversión o identidad?
2. ¿Puede implementarse de manera accesible?
3. ¿Puede ofrecer fallback?
4. ¿Su coste de rendimiento es aceptable?
5. ¿Es reutilizable en proyectos distintos?
6. ¿No compromete SEO ni semántica?
7. ¿Puede configurarse por proyecto?
8. ¿Puede desactivarse sin romper funcionalidad?
9. ¿Seguiría teniendo sentido si deja de estar de moda?

Si las respuestas negativas dominan, la tendencia pertenece a una Extension o al proyecto concreto, no al core.

Toda incorporación relevante SHOULD documentar motivo, coste y fallback.

> **Hache Base evoluciona por valor demostrado, no por hype.**

## 29. Checklist de cumplimiento

Antes de considerar un proyecto listo:

### Identidad
- [ ] Personalidad definida.
- [ ] Nivel visual base declarado.
- [ ] No parece clon visual de otro proyecto Hache.
- [ ] Tiene al menos un recurso reconocible propio cuando aplica.

### Theme y tokens
- [ ] Foundation / Semantic / Component implementados correctamente.
- [ ] Sin valores visuales arbitrarios repetidos en el core.
- [ ] Light/dark preparado a nivel de tokens.
- [ ] Assets comprobados en los temas habilitados.

### Responsive
- [ ] Mobile-first real.
- [ ] Sin scroll horizontal accidental.
- [ ] Navegación móvil usable.
- [ ] Componentes adaptan estructura según espacio.
- [ ] Breakpoints responden al contenido.
- [ ] Zoom/reflow probado.
- [ ] Revisado en las cinco categorías mínimas de viewport.

### Accesibilidad
- [ ] WCAG 2.2 AA como objetivo mínimo.
- [ ] Contraste correcto.
- [ ] Navegación por teclado.
- [ ] Focus visible y no oculto.
- [ ] Labels y errores correctos.
- [ ] Reduced motion.
- [ ] Áreas táctiles adecuadas.
- [ ] Estados no dependen solo de color.

### Movimiento y avanzado
- [ ] Cada animación tiene propósito.
- [ ] No existe scroll hijacking.
- [ ] No se retrasa contenido esencial.
- [ ] Fallback disponible para efectos avanzados.
- [ ] 3D/WebGL justificado si existe.

### Performance
- [ ] LCP objetivo ≤ 2.5 s.
- [ ] INP objetivo ≤ 200 ms.
- [ ] CLS objetivo ≤ 0.1.
- [ ] Imágenes optimizadas.
- [ ] Fuentes controladas.
- [ ] JS decorativo limitado.
- [ ] Performance budget definido si el proyecto es pesado.

### SEO y semántica
- [ ] Contenido principal accesible en HTML.
- [ ] Headings semánticos.
- [ ] Enlaces rastreables.
- [ ] No existe contenido SEO crítico únicamente en canvas/imagen.
- [ ] La norma SEO Hache Base sigue cumpliéndose.

### Componentes
- [ ] Estados completos.
- [ ] Feedback inmediato.
- [ ] Reutilizables.
- [ ] Tokens en lugar de valores arbitrarios.
- [ ] Sin estilos de proyecto incrustados innecesariamente en el core.

### Formularios
- [ ] Piden solo datos necesarios.
- [ ] Conservan datos válidos tras errores.
- [ ] Mensajes de error accionables.
- [ ] Prevención de doble envío cuando aplica.
- [ ] Mobile keyboard/autocomplete correctos.

## 30. Criterio de aceptación para Hache Base

Una implementación del Design System 2026 se considera correcta cuando:

1. El core proporciona tokens, componentes y reglas estructurales.
2. Theme y Extensions están claramente separados del core.
3. Puede cambiar radicalmente de identidad sin modificar la arquitectura base.
4. Clean, Dimensional e Immersive funcionan como presets configurables.
5. Dimensional existe como preset recomendado por defecto.
6. Light/dark está soportado por tokens aunque el proyecto no exponga ambos.
7. Accesibilidad y reduced motion están contemplados desde el sistema.
8. Los componentes responden al espacio disponible.
9. Los efectos avanzados son progressive enhancement.
10. Se mantienen los objetivos de Core Web Vitals.
11. La integración no rompe la norma SEO existente.
12. No existe dependencia obligatoria de una librería visual pesada.
13. Los componentes tienen estados completos.
14. Un nuevo proyecto hereda calidad sin heredar apariencia.
15. Cualquier excepción a un MUST queda documentada y justificada.

> **La definición de terminado incluye diseño, accesibilidad, responsive, semántica y rendimiento.**

## 31. Fase siguiente: auditoría e implementación

Este documento define la norma cerrada. La siguiente fase NO consiste en rediseñar Hache Base a ciegas.

El agente encargado de implementación deberá:

1. auditar Hache Base contra cada capítulo;
2. clasificar cada requisito como:
   - cumple;
   - cumple parcialmente;
   - no cumple;
   - no aplica;
3. identificar componentes reutilizables existentes;
4. separar hallazgos en Core, Theme y Extensions;
5. proponer cambios mínimos antes de reescribir componentes;
6. implementar sin romper SEO ni funcionalidades existentes;
7. mantener compatibilidad y fallbacks donde corresponda;
8. ejecutar pruebas responsive, accesibilidad y performance;
9. verificar light/dark a nivel de tokens;
10. revisar estados completos de componentes;
11. documentar excepciones y deuda técnica;
12. entregar matriz final de cumplimiento.

### Orden recomendado de implementación

1. Tokens y arquitectura Core / Theme / Extensions.
2. Accesibilidad y estados base.
3. Responsive y Container Queries.
4. Componentes estructurales.
5. Light/dark infrastructure.
6. Movimiento y reduced motion.
7. Preset Dimensional.
8. Presets Clean e Immersive.
9. Performance y auditoría final.
10. Validación conjunta con la base SEO.

> **Work debe implementar una especificación cerrada; no reinterpretar la dirección visual de Hache Base.**

## Referencias técnicas de base

La norma se apoya conceptualmente en:

- W3C — Web Content Accessibility Guidelines (WCAG) 2.2.
- W3C/WAI — criterios de foco, target size, dragging, entrada y navegación.
- web.dev — Core Web Vitals (LCP, INP y CLS).
- MDN — CSS Container Queries.
- MDN — `prefers-reduced-motion`.
- MDN — View Transition API y CSS View Transitions.
- MDN — rendimiento de fuentes y recursos web.
- Investigación de tendencias 2026 de Webflow, Wix Studio y ecosistemas contemporáneos de diseño.

Las tendencias son contexto; los estándares de accesibilidad, semántica y rendimiento son requisitos.

---

## Principio final

> **Hache Base no debe producir sitios que se vean iguales. Debe producir sitios que se sientan igual de bien construidos.**
