# Presupuesto de performance — P1-11 / PERF-004

> Presupuesto **por proyecto** para conectar Design System, assets reales y terceros con el release. Los límites se justifican por baseline, CUF, dispositivo/perfil y riesgo; Hache Base no impone un número universal de KB, requests o terceros.

- Proyecto:
- Nivel Production Readiness: A / B / C
- Nivel visual: Clean / Dimensional / Immersive
- Owner:
- Persona revisora:
- Fecha/commit de baseline:
- Referencia de baseline/reporte:
- Entorno, dispositivo/perfil y herramienta:
- CUF/páginas representativos:
- Justificación de los límites:
- Config machine-readable: `performance-budget.json` / otra ruta:
- Estado: BORRADOR / REVISADO

## 1. Objetivos de experiencia

| Métrica | Objetivo | Resultado móvil | Resultado desktop | Fuente |
| --- | ---: | ---: | ---: | --- |
| LCP p75 | ≤ 2.5 s | | | campo / laboratorio |
| INP p75 | ≤ 200 ms | | | campo / laboratorio |
| CLS p75 | ≤ 0.1 | | | campo / laboratorio |

Los objetivos de experiencia no se sustituyen por un presupuesto de bytes. P1-11 limita regresiones de release/red; P1-03/P1-04 y la evidencia del proyecto siguen cubriendo Lighthouse/RUM/campo.

## 2. Presupuesto del artefacto/release

Completar solo dimensiones que el stack pueda medir de forma estable. Registrar bytes **del artefacto/build**, no llamarlos “transferencia comprimida” salvo que la medición provenga realmente de network/Lighthouse.

| Dimensión | Límite | Baseline actual | Resultado release | Fuente/evidencia |
| --- | ---: | ---: | ---: | --- |
| Total de archivos desplegables | | | | scan de release |
| JavaScript del release | | | | scan de release |
| CSS del release | | | | scan de release |
| Imágenes del release | | | | scan de release |
| Fuentes del release | | | | scan de release |
| Otros assets | | | | scan de release |
| Imagen individual máxima | | | | scan de release |
| Fuente individual máxima | | | | scan de release |

### Imágenes — PERF-005/PERF-006

- Presupuesto de imagen LCP:
- Presupuesto del primer viewport:
- ¿Dimensiones o `aspect-ratio` definidos?: sí / no / N/A con justificación
- ¿`srcset`/`sizes` cuando existen tamaños distintos?: sí / no / N/A
- ¿AVIF/WebP u optimización equivalente aporta reducción?:
- ¿El recurso LCP evita lazy loading que retrase descubrimiento?:
- ¿Imágenes fuera de viewport se difieren cuando aporta valor?:
- Evidencia waterfall/markup:

El budget de bytes no prueba por sí mismo `PERF-005`/`PERF-006`; ayuda a detectar regresiones cuantitativas.

### Fuentes — PERF-008

- Familias/variantes realmente usadas:
- Formato(s):
- Presupuesto total de fuentes:
- Presupuesto por archivo de fuente:
- `font-display`:
- Fallback/métrica:
- Evidencia de ausencia de shifts materiales:

Un archivo pequeño no demuestra que la estrategia de fuentes sea correcta; el budget complementa network/CLS/CSS.

## 3. Presupuesto de transferencia en navegador

Cuando exista Lighthouse/network reproducible, documentar límites **por reporte/página/CUF**. No sumar varias corridas de Lighthouse como si fueran una sola visita.

| Dimensión | Límite por página/CUF | Baseline | Resultado | Evidencia |
| --- | ---: | ---: | ---: | --- |
| Transferencia total | | | | LHR/network |
| JavaScript transferido | | | | LHR/network |
| CSS transferido | | | | LHR/network |
| Imágenes transferidas | | | | LHR/network |
| Fuentes transferidas | | | | LHR/network |
| Transferencia de terceros | | | | LHR/network |
| Requests de terceros | | | | LHR/network |

Hosts/CDN operados como superficie first-party del proyecto deben declararse explícitamente en la configuración; no clasificar un origen como first-party solo para esconder su coste.

## 4. Terceros — PERF-010

Cada tercero runtime sigue teniendo un registro `TP-*` en `THIRD-PARTY-INVENTORY.md`. P1-11 puede automatizar límites de transferencia/requests, pero no reemplaza owner, propósito, datos, timeout/fallback, medición con/sin tercero ni criterio de retiro.

| TP-ID / origen | Transferencia límite | Requests límite | Baseline medido | Resultado | Owner |
| --- | ---: | ---: | ---: | ---: | --- |
| TP-___ / `https://...` | | | | | |

- Orígenes first-party explícitos:
- Terceros en camino crítico:
- Referencia al inventario P1-05:
- ¿El budget machine-readable tiene regla por origen cuando hace falta?:
- Evidencia de medición con/sin tercero o baseline equivalente:

## 5. Configuración automatizable

Copiar `templates/performance-budget.example.json` al proyecto, completar límites reales y mantenerlo versionado. Los campos `null` son **no configurados**, no “sin límite aprobado”. El checker exige al menos un budget configurado y metadata de baseline/revisión.

Ejemplo de ejecución:

```bash
node tools/performance/release-budget.mjs \
  --config performance-budget.json \
  --root dist \
  --lighthouse-dir artifacts/lighthouse \
  --json artifacts/release-budget.json
```

Semántica:

- `--root` mide bytes reales del directorio que se pretende desplegar;
- `--lighthouse-dir` lee reportes Lighthouse JSON y evalúa cada reporte de forma independiente;
- `first_party_origins` añade hosts/CDN explícitamente first-party además del origen de cada página;
- `network.per_origin` permite límites concretos por origen de tercero;
- un symlink dentro del release falla en vez de permitir escapar/doble-contar el root;
- salida `0`: dentro de **los límites configurados**;
- salida `1`: budget excedido;
- salida `2`: configuración/evidencia inválida o insuficiente.

`WITHIN_CONFIGURED_BUDGETS` **no equivale a Production Ready ni a PASS automático de PERF-004/PERF-010**. La revisión humana y la justificación del proyecto siguen siendo necesarias.

## 6. Cambios y excepciones

Subir un límite es un cambio de política, no una forma silenciosa de “arreglar CI”. Toda subida debe registrar:

- dimensión afectada;
- baseline anterior y nuevo resultado;
- causa/regresión o nueva necesidad funcional;
- impacto sobre CUF/dispositivo;
- alternativas consideradas (optimizar, diferir, retirar tercero, cambiar asset, etc.);
- owner y persona revisora;
- fecha/commit de aprobación.

No incluir un bypass genérico de “ignore budget” en Core. Si un proyecto necesita una excepción temporal, versionar el nuevo límite/decisión con su justificación y fecha de revisión.

## 7. Verificaciones cualitativas

- [ ] Sin layout shifts evitables por imágenes, fuentes o estados loading.
- [ ] No hay dependencia pesada para un efecto simple.
- [ ] Módulos no críticos usan carga diferida cuando aporta valor.
- [ ] Animaciones fuera de viewport se pausan/reducen cuando corresponde.
- [ ] Reduced motion probado.
- [ ] Fallback de Extensions probado.
- [ ] Imágenes y fuentes tienen estrategia coherente con sus controles del Standard.
- [ ] Cada tercero tiene owner/coste/fallback/retiro en `THIRD-PARTY-INVENTORY.md`.
- [ ] Regresión respecto al baseline explicada y aceptada.
- [ ] CI evalúa el build/release real cuando el stack permite una medición estable.
