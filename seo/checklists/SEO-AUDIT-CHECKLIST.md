# Checklist técnico de auditoría SEO

No sustituye la investigación maestra. Sirve para ejecutar una auditoría reproducible y registrar evidencia por causa raíz.

## Método

1. Inventariar tipos de URL y objetivos de negocio.
2. Resolver primero acceso, servidor, rastreo, renderizado e indexabilidad.
3. Comparar URL declarada, renderizada e indexada cuando existan datos.
4. Segmentar por plantilla/directorio/finalidad; no extrapolar una muestra sin comprobarla.
5. Asignar severidad, evidencia, alcance, esfuerzo y propietario.
6. Corregir causas raíz antes que cientos de síntomas.
7. Validar con crawler, navegador, logs y herramientas del buscador según aplique.

## Plantilla de hallazgo

```text
ID: SEO-AREA-NNN
Estado: PASS | WARNING | FAIL | N/A
Severidad: CRÍTICA | ALTA | MEDIA | BAJA | EXPERIMENTAL
Evidencia: OFICIAL | EVIDENCIA FUERTE | EVIDENCIA MODERADA | EXPERIMENTO | CONSENSO PROFESIONAL | HIPÓTESIS | SIN EVIDENCIA SUFICIENTE
Alcance: URL | plantilla | directorio | sitio | entidad externa
Observación:
Evidencia observada:
Impacto probable:
Corrección propuesta:
Cómo validar:
Excepciones/contexto:
Propietario:
```

## Áreas

- [ ] Servidor, DNS, HTTPS, disponibilidad y seguridad.
- [ ] Rastreo, robots, headers y crawlability.
- [ ] Sitemaps, estados HTTP y redirects.
- [ ] Indexabilidad, canonicals, duplicación y huérfanas.
- [ ] Arquitectura, navegación, breadcrumbs y paginación.
- [ ] URLs y parámetros.
- [ ] Titles, headings, contenido, anchors e imágenes.
- [ ] JavaScript/render/deep links.
- [ ] Core Web Vitals y rendimiento de campo/laboratorio.
- [ ] Mobile-first y paridad móvil.
- [ ] Accesibilidad técnica relevante.
- [ ] Datos estructurados.
- [ ] SEO local/GBP/NAP cuando aplica.
- [ ] Entidad, perfiles y `sameAs`.
- [ ] Backlinks/autoridad con análisis editorial, no solo métricas externas.
- [ ] Bots de búsqueda/IA y políticas deliberadas.
- [ ] Medición: GSC/Bing/analytics/conversiones/citas IA según objetivo.
- [ ] Riesgos de spam, contenido masivo, doorway, stuffing y schema engañoso.

## Priorización

Usar como marco, no como matemática falsa:

```text
Prioridad = severidad × alcance × confianza de evidencia × valor de negocio ÷ esfuerzo
```

Documentar supuestos. La priorización final requiere juicio del proyecto.
