# Extensions UI

Esta carpeta no forma parte del bundle Core y permanece sin implementación de ejecución por defecto.

Una Extension (WebGL, 3D complejo, scrollytelling, timeline, visor, comparador o componente experimental) solo puede añadirse con:

1. necesidad de producto y reutilización demostradas;
2. carga diferida y presupuesto de recursos;
3. fallback estático o funcional;
4. contenido principal disponible en HTML;
5. soporte de teclado, zoom, reflow y `prefers-reduced-motion`;
6. pausa o reducción fuera de viewport cuando corresponda;
7. control de DPR/resolución para render pesado;
8. desactivación sin romper la tarea principal;
9. pruebas de LCP, INP, CLS y errores de consola;
10. documentación de motivo, coste, fallback y alcance.

No se promueve una Extension al Core por reutilización hipotética.
