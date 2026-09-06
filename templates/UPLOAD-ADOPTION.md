# Upload Adoption — P2-04

> Plantilla por proyecto. No define límites universales, storage universal ni antivirus obligatorio.

## 1. Caso real y CUF

- Proyecto: `<nombre>`
- CUF que necesita upload: `<...>`
- Actor autorizado: `<rol/anon/API>`
- Endpoint/adapter: `<...>`
- Qué ocurre si upload falla: `<...>`
- Qué ocurre si metadata/DB falla después de almacenar bytes: `<cleanup/compensación>`

## 2. Datos y formatos

- MIME allowlist: `<...>`
- Extensiones **de servidor** por MIME: `<...>`
- `maxBytes`: `<... y justificación>`
- `maxFiles`: `<...>`
- Para imágenes: `maxImageWidth`, `maxImageHeight`, `maxImagePixels`: `<...>`
- Validación estructural adicional por formato: `<...>`
- ¿Se conserva el nombre original del cliente?: `<idealmente no; justificar si sí>`

El nombre, MIME y extensión declarados por el cliente no son autoridad para construir rutas ni decidir el tipo persistido.

## 3. Threat model

| Amenaza | ¿Aplica? | Control | Prueba/evidencia | Riesgo residual |
| --- | --- | --- | --- | --- |
| path traversal / overwrite | `<sí/no>` | `<...>` | `<...>` | `<...>` |
| MIME spoofing | `<sí/no>` | `<...>` | `<...>` | `<...>` |
| contenido corrupto/polyglot | `<sí/no>` | `<...>` | `<...>` | `<...>` |
| decompression/resource bomb | `<sí/no>` | `<...>` | `<...>` | `<...>` |
| malware | `<sí/no>` | `<...>` | `<...>` | `<...>` |
| scanner unavailable | `<sí/no>` | `<disabled/best_effort/required>` | `<...>` | `<...>` |
| ejecución de scripts desde storage | `<sí/no>` | `<...>` | `<...>` | `<...>` |
| fuga de archivos privados | `<sí/no>` | `<...>` | `<...>` | `<...>` |
| abuso de volumen/quota | `<sí/no>` | `<...>` | `<...>` | `<...>` |
| fallo parcial storage↔DB | `<sí/no>` | `<...>` | `<...>` | `<...>` |

## 4. Storage

- Implementación `UploadStorage`: `<local/object/...>`
- Root/bucket: `<referencia no secreta>`
- Público o privado: `<...>`
- Permisos/ACL: `<...>`
- ¿Puede ejecutar scripts?: `<prueba concreta>`
- URL signing/CDN si aplica: `<...>`
- Naming: `<server-generated>`
- Colisión/overwrite: `<create-if-absent>`
- Cifrado at rest si aplica: `<...>`
- Retención/lifecycle: `<...>`
- Backup/restore requerido: `<...>`

Si el storage vive bajo document root, aportar prueba explícita de que PHP/CGI/scripts no se ejecutan desde esa ruta. Una extensión `.jpg` no sustituye la configuración del servidor.

## 5. Scanner

- Modo: `<disabled|best_effort|required>`
- Implementación/proveedor: `<...>`
- Timeout: `<...>`
- Comportamiento si está unavailable: `<...>`
- Qué metadata se registra: `<solo estado/código minimizado>`
- Qué datos salen a tercero: `<...>`

`infected` siempre debe rechazar. Base no decide si `best_effort` es suficiente para el riesgo del proyecto.

## 6. Controles que siguen fuera de Upload Extension

- auth/autorización: `<...>`
- CSRF cuando aplique: `<...>`
- rate limit/abuse: `<...>`
- auditoría: `<...>`
- quotas por actor/tenant: `<...>`
- permisos para leer/borrar: `<...>`
- reconciliación de metadata huérfana: `<...>`

## 7. Pruebas mínimas

- [ ] archivo válido permitido;
- [ ] MIME spoofing rechazado;
- [ ] bytes por encima del límite rechazados;
- [ ] cantidad por encima del límite rechazada;
- [ ] imagen con dimensiones excesivas rechazada;
- [ ] imagen con píxeles excesivos rechazada;
- [ ] contenido inválido del formato rechazado;
- [ ] filename con traversal no influye en destino;
- [ ] no overwrite/collision;
- [ ] scanner infected rechazado cuando configurado;
- [ ] scanner unavailable sigue la política elegida;
- [ ] fallo de storage no deja archivo parcial;
- [ ] rollback posterior elimina bytes almacenados cuando corresponde;
- [ ] ruta pública no ejecuta scripts o storage privado bloquea acceso directo;
- [ ] logs/evidencia no contienen archivo, secreto ni PII innecesaria.

## 8. Criterio de adopción

P2-04 puede considerarse adoptado en el proyecto solo cuando:

1. existe un caso real y threat model revisado;
2. la policy concreta está versionada/justificada;
3. transporte, MIME, contenido y límites tienen pruebas negativas;
4. storage real impide traversal/overwrite y su exposición está probada;
5. scanner policy está explícita aunque sea `disabled`;
6. cleanup/compensación storage↔metadata está probado;
7. auth/CSRF/rate-limit/auditoría aplicables permanecen cubiertos por el proyecto;
8. una revisión humana valida el flujo real.

Tener `integrations/upload/` en Hache Base no declara P2-04 PASS en proyectos derivados.
