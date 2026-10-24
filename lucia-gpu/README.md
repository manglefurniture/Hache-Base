# Lucía GPU — respaldo reproducible

Este directorio contiene la configuración reproducible de la instancia GPU de Lucía. No guarda modelos, datasets, LoRAs ni salidas pesadas.

Estado: estructura inicial creada el 2026-09-29. La captura definitiva queda pendiente de que Work termine el vídeo actual.

- `bootstrap/`: manifiestos e instalación reproducible.
- `scripts/`: scripts de arranque y generación.
- `workflows/`: workflows exportados de ComfyUI.
- `config/`: configuración no secreta.
- `manifests/`: inventario del entorno y sus versiones.
- `RESTORE.md`: procedimiento de restauración.

Los assets pesados y únicos se guardarán en Google Drive, bajo `lucia/99_gpu_backup/`.
