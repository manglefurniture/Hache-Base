# Upload Extension — P2-04

Extensión **opt-in** para validar y almacenar uploads sin meter una política de archivos en Core. Nace de un caso real: el administrador de Tienda Natación permite subir fotos de productos y ya tenía auth, CSRF, límites por request, `is_uploaded_file()`, MIME sniffing, `getimagesize()`, nombres aleatorios y cleanup transaccional. El hueco reusable era formalizar límites de contenido/dimensiones, storage, scanner opcional y pruebas de abuso.

## Fronteras

La extensión separa cuatro responsabilidades:

1. `PhpUploadAdapter`: demuestra que el temp file proviene del transporte HTTP de PHP y **descarta** nombre/MIME declarados por el cliente;
2. `UploadPolicy`: allowlist MIME→extensión de servidor, bytes, cantidad, dimensiones/píxeles y modo de scanner definidos por proyecto;
3. `UploadService`: vuelve a medir bytes, detecta MIME sobre contenido, valida dimensiones y exige contenido de imagen decodificable antes de persistir;
4. `UploadStorage`: frontera de storage. `LocalUploadStorage` es un adapter local de referencia con nombre aleatorio, create-exclusive, fingerprint SHA-256 y borrado limitado a su root.

No existe filename del cliente en el receipt ni se usa para construir una ruta.

## Threat model mínimo

| Amenaza | Control reusable | Evidencia que sigue siendo del proyecto |
| --- | --- | --- |
| path traversal / overwrite por filename | el nombre del cliente se ignora; storage genera ID aleatorio y abre con modo exclusivo | permisos/ruta real del storage |
| MIME spoofing | `finfo` sobre bytes + allowlist | allowlist justificada |
| imagen truncada/corrupta o polyglot simple | `getimagesize` para metadata + decodificación real con GD cuando está disponible; fallback format-aware para PNG/JPEG/WebP/GIF | formatos adicionales requieren decoder/inspector compatible |
| decompression/resource bomb | límites obligatorios de ancho, alto y píxeles cuando se permite `image/*`, antes de decodificar | valores según memoria/worker/optimizer real |
| upload gigante / demasiados archivos | bytes reales + `maxBytes` + `maxFiles` | límites según CUF y hosting |
| malware conocido | `UploadScanner` opcional | proveedor, SLA y modo `disabled|best_effort|required` |
| scanner caído | modo explícito del proyecto; `required` falla cerrado, `best_effort` conserva estado `unavailable` | decisión de riesgo/UX |
| symlink / salida del root local | root y source symlink rechazados; borrado exige parent real == root | hardening del servidor y mount |
| artifact parcial por fallo de storage | adapter local limpia destinos parciales | rollback de DB/metadata después de un store exitoso |
| ejecución de archivo en web root | extensión deriva de MIME allowlisted, no del cliente | preferir storage no ejecutable/no público o probar configuración web |

### Lo que esta primitive no finge resolver

- No instala ClamAV ni un SaaS antivirus.
- No decide que `best_effort` sea aceptable para todos los proyectos.
- No impone un directorio público ni privado universal.
- No hace quotas por usuario/tenant ni lifecycle de object storage.
- No convierte `getimagesize()` en prueba suficiente de contenido completo: una imagen debe pasar además el decoder/inspector.
- No aplica la lógica de imagen a PDFs, ZIPs u otros formatos complejos; esos formatos requieren validadores propios.
- No reemplaza auth, autorización, CSRF, rate limit, auditoría ni reglas de negocio del endpoint.

## Política

Ejemplo **ficticio** para imágenes; cada proyecto debe escoger sus límites a partir de su runtime:

```php
use HacheBase\Integrations\Upload\UploadPolicy;

$policy = new UploadPolicy(
    allowedMimeExtensions: [
        'image/jpeg' => 'jpg',
        'image/png' => 'png',
        'image/webp' => 'webp',
    ],
    maxBytes: $projectMaxBytes,
    maxFiles: $projectMaxFiles,
    maxImageWidth: $projectMaxWidth,
    maxImageHeight: $projectMaxHeight,
    maxImagePixels: $projectMaxPixels,
    scannerMode: $projectScannerMode,
);
```

Cuando existe al menos un MIME `image/*`, ancho, alto y píxeles son obligatorios. Los límites se aplican antes de intentar una decodificación completa, de modo que una imagen comprimida pequeña no pueda forzar primero una reserva desproporcionada de memoria.

Para imágenes, `UploadService` primero obtiene metadata con `getimagesize()` y compara el MIME. Después exige contenido decodificable: usa `imagecreatefromstring()` cuando GD está disponible; si no, usa un inspector format-aware para PNG/JPEG/WebP/GIF. En PNG, el fallback valida firma, chunks/CRC, presencia de `IDAT`, `IEND` terminal y stream zlib cuando está disponible. Un archivo con solo `IHDR`/`IEND` se rechaza aunque `getimagesize()` pueda leer sus dimensiones.

## Scanner opcional

`UploadScanner::scan()` devuelve únicamente:

- `clean`;
- `infected`;
- `unavailable`.

`infected` siempre rechaza. `required` rechaza si el scanner falta o está unavailable. `best_effort` permite continuar cuando el scanner no está configurado/no disponible y lo deja visible en `scanner_status`. `disabled` no llama al scanner.

El adapter de antivirus no debe regresar salida cruda que pueda contener path, contenido, credenciales o datos sensibles.

## Storage local

`LocalUploadStorage` es referencia para una sola instancia/local filesystem. Recomendaciones de adopción:

- preferir root fuera del document root si los archivos no necesitan ser servidos directamente;
- si deben ser públicos, probar explícitamente que la ruta no ejecuta PHP/scripts y que el servidor fuerza content type seguro;
- no usar un root symlink;
- separar URL pública de path físico;
- conservar metadata (owner, MIME, hash, timestamps) en la capa de proyecto;
- para multiinstancia/object storage implementar `UploadStorage` con create-if-absent y delete scoped equivalentes.

## Flujo HTTP PHP

```php
$candidates = PhpUploadAdapter::candidates($_FILES['imagenes'] ?? [], $policy);
foreach ($candidates as $candidate) {
    $receipt = $service->store($candidate);
    // El proyecto persiste metadata/URL. Si una transacción posterior falla:
    // $service->delete($receipt);
}
```

`PhpUploadAdapter` usa `is_uploaded_file()` por defecto. El callable alternativo existe para pruebas/adapters controlados; no debe sustituirse por `fn()=>true` en producción.

## Evidencia para adoptar P2-04

Un proyecto real debe conservar:

- threat model y CUF;
- auth/autorización/CSRF del endpoint cuando aplique;
- policy concreta y justificación de límites;
- storage root/bucket y prueba de no ejecución/no traversal;
- MIME/content tests positivos y negativos;
- prueba de bytes + dimensiones/píxeles + archivo truncado/corrupto;
- scanner policy o decisión explícita `disabled`;
- cleanup/rollback probado;
- observabilidad/auditoría minimizada;
- revisión humana del flujo real.

La existencia de esta extensión en Hache Base **no** convierte P2-04 ni controles de seguridad de un proyecto derivado en PASS.
