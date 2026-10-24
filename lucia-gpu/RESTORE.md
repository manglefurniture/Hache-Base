# Restauración de la GPU de Lucía

Este documento es el punto de partida para reconstruir una instancia compatible. Aún no representa una captura final del entorno.

## Tras finalizar el trabajo de vídeo

1. Registrar sistema, GPU, CUDA, Python, PyTorch y las versiones exactas de ComfyUI y nodos personalizados en `manifests/environment.json`.
2. Exportar los workflows usados y guardarlos en `workflows/`.
3. Generar `bootstrap/models_manifest.json` con nombre, versión, origen, checksum y ruta de cada modelo descargable.
4. Guardar LoRAs, datasets imprescindibles, referencias canónicas y modelos entrenados en la carpeta de Google Drive preparada para el backup.
5. Añadir scripts idempotentes de instalación y ejecución en `bootstrap/` y `scripts/`.
6. Revisar que no haya secretos, tokens, claves privadas ni archivos pesados en Git.

## Principio de restauración

Clonar el repositorio, restaurar los assets únicos desde Google Drive y ejecutar el instalador versionado. Los modelos públicos se descargarán a partir del manifiesto, en vez de conservar copias duplicadas.
