# Presupuesto de performance

- Proyecto:
- Nivel visual: Clean / Dimensional / Immersive
- Fecha/commit de baseline:
- Entorno y herramienta:

## Objetivos

| Métrica | Objetivo | Resultado móvil | Resultado desktop | Fuente |
| --- | ---: | ---: | ---: | --- |
| LCP p75 | ≤ 2.5 s | | | campo / laboratorio |
| INP p75 | ≤ 200 ms | | | campo / laboratorio |
| CLS p75 | ≤ 0.1 | | | campo / laboratorio |

## Presupuesto de transferencia y ejecución

| Recurso | Presupuesto inicial | Resultado | Excepción justificada |
| --- | ---: | ---: | --- |
| JavaScript inicial comprimido | | | |
| CSS inicial comprimido | | | |
| Fuentes iniciales | | | |
| Imagen LCP | | | |
| Imágenes primer viewport | | | |
| Extension/efecto avanzado | | | |

## Verificaciones

- [ ] Sin layout shifts evitables por imágenes, fuentes o estados loading.
- [ ] No hay dependencia pesada para un efecto simple.
- [ ] Módulos no críticos usan carga diferida cuando aporta valor.
- [ ] Animaciones fuera de viewport se pausan/reducen cuando corresponde.
- [ ] Reduced motion probado.
- [ ] Fallback de Extensions probado.
- [ ] Regresión respecto al baseline explicada y aceptada.
