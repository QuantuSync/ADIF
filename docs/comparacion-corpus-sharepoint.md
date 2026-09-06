# Comparación del corpus local contra la carpeta Input de SharePoint

Sesión 2026-09-06, bloque 5. Sin acceso a SharePoint desde este entorno
(ningún conector configurado en esta sesión): no se pudo comprobar en vivo
si los documentos que tenemos descargados son los mismos que el cliente
tiene en su carpeta Input. Lo que sigue es la comprobación preparada, más lo
que hace falta para poder ejecutarla.

## Estado del corpus local, medido hoy

- **215 documentos** con fila propia en `documentos`, repartidos en 57
  expedientes — todos hasheados con éxito (ningún fichero roto o
  desaparecido del disco).
- **222 ficheros en disco** (`/data/documentos` dentro del contenedor
  `api`/`worker`, volumen `documentos` de `docker-compose.yml`) — **7 de más**,
  los siete del expediente `3.23/28510.0135` (`ADJUDICACION`, `CONTRATO` ×2,
  `ANEJO` ×3, `PLIEGO`), que no tenía fila ni en `expedientes` ni en
  `documentos`. **Investigado y cerrado en la sesión siguiente**
  (`docs/auditoria-huerfanos-y-autorreferencia.md`): no era un fallo de
  registro, sino una limpieza de base de datos anterior
  (`docs/decisiones-cliente.md`, "Limpieza de la base de datos") que
  clasificó mal este expediente como "contaminación de pruebas" y borró su
  fila sin tocar el volumen de documentos. Ficheros verificados íntegros
  (hash SHA-256[:16] recalculado), expediente registrado y reprocesado —
  ese mismo reproceso destapó y arregló, de paso, el bug real de extracción
  multi-lote que `docs/hallazgos-sindicacion.md` ya había medido en 2024
  para este expediente ("1 de 8 lotes"). Comprobado que no hay ningún otro
  caso: 43 carpetas en disco, 42 con fila en `documentos` antes de
  registrar esta, ninguna otra huérfana.
- **Manifiesto completo** de los 215 documentos trackeados, con SHA-256
  íntegro (no el hash de 16 caracteres que usa `app.scraping.pcsp` para
  deduplicar nombres de fichero al descargar — ese es demasiado corto para
  servir de comprobación de integridad seria):
  `docs/manifiesto-documentos-local-2026-09-06.csv`
  (columnas: `codigo_expediente`, `nombre_archivo`, `ruta_almacenamiento`,
  `sha256_completo`, `tamano_bytes`).

## Procedimiento para comparar por hash

1. **Generar el manifiesto del lado SharePoint**, mismo formato que el de
   arriba (columnas mínimas: nombre de fichero + SHA-256 del contenido).
   Dos formas, según qué acceso se consiga:
   - **Con acceso de aplicación (Microsoft Graph API)**: listar los
     ficheros del site/carpeta Input (`GET
     /sites/{site-id}/drive/root:/{ruta-input}:/children`, paginando) y
     descargar cada uno (`GET .../content`) para hashear su contenido —
     Graph no expone el SHA-256 del fichero directamente en todos los
     casos (sí expone `quickXorHash` de OneDrive/SharePoint, que **no** es
     comparable a un SHA-256 salvo que se recalcule igual en ambos lados),
     así que lo fiable es descargar y hashear en el mismo formato que el
     manifiesto local.
   - **Con acceso delegado de un usuario (navegador o cliente de
     sincronización)**: sincronizar o descargar la carpeta Input a un
     disco local y ejecutar el mismo script de abajo sobre esa carpeta.
2. **Diferencia los dos manifiestos** por `sha256_completo` (no por nombre
   de fichero — el mismo contenido con un nombre distinto en cada sitio
   debe contar como "el mismo documento"; CONTEXTO.md sección 8, "el
   scraping funciona... deduplicación por hash" ya sigue este criterio en
   el resto del sistema):
   - Hash presente en SharePoint y no en el manifiesto local → documento
     que falta descargar.
   - Hash presente en local y no en SharePoint → documento local que no
     está (o ya no está) en la carpeta Input del cliente — con qué
     expediente lo cruza el manifiesto local, para investigar antes de
     asumir que sobra.
   - Mismo nombre de fichero con hash distinto en cada lado → mismo
     documento nominal pero contenido diferente (una versión sustituida) —
     el caso que más importa para la entrega, porque un hash de nombre a
     secas no lo detectaría nunca.
3. **Repetir con `du`/tamaño** como comprobación barata antes del hash
   completo, si el volumen de documentos crece mucho: un tamaño distinto ya
   descarta la coincidencia sin necesidad de descargar/hashear.

### Script para generar el manifiesto (mismo criterio en los dos lados)

Ejecutado dentro del contenedor `api` para el lado local (tiene acceso
directo a `/data/documentos` y a la base de datos para anotar el
expediente de cada fichero):

```python
import csv, hashlib, sys
sys.path.insert(0, "/app")
from sqlalchemy import select
from app.db import SessionLocal
from app.models import Documento, Expediente

db = SessionLocal()
filas = db.execute(
    select(Documento, Expediente).join(Expediente, Documento.expediente_id == Expediente.id)
).all()
with open("/tmp/manifiesto_local.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["codigo_expediente", "nombre_archivo", "ruta_almacenamiento", "sha256_completo", "tamano_bytes"])
    for doc, exp in filas:
        with open(f"/data/documentos/{doc.ruta_almacenamiento}", "rb") as fh:
            contenido = fh.read()
        w.writerow([exp.codigo_expediente, doc.nombre_archivo, doc.ruta_almacenamiento,
                    hashlib.sha256(contenido).hexdigest(), len(contenido)])
```

Para un directorio suelto (carpeta Input sincronizada a disco, sin base de
datos detrás), la misma idea sin la parte de SQLAlchemy:

```python
import csv, hashlib, os

with open("manifiesto_sharepoint.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["ruta_relativa", "sha256_completo", "tamano_bytes"])
    for root, _dirs, files in os.walk("RUTA_A_LA_CARPETA_INPUT"):
        for nombre in files:
            ruta = os.path.join(root, nombre)
            with open(ruta, "rb") as fh:
                contenido = fh.read()
            w.writerow([os.path.relpath(ruta, "RUTA_A_LA_CARPETA_INPUT"),
                        hashlib.sha256(contenido).hexdigest(), len(contenido)])
```

## Qué hace falta para ejecutarlo de verdad

- **Acceso a la carpeta Input de SharePoint**: una app registrada en
  Entra ID con permiso `Sites.Read.All` (o `Files.Read.All`) sobre el site
  del cliente, o credenciales de un usuario con acceso delegado a esa
  carpeta concreta — ninguna de las dos existe en este entorno ni en este
  proyecto todavía (CONTEXTO.md invariante 5: nada específico de un
  proveedor cloud en el código del motor, así que este acceso viviría
  fuera de `engine/`, como un paso manual o un script aparte, nunca como
  una dependencia del sistema en producción).
- **La URL/ID exacto del site y la ruta de la carpeta Input** — no están
  documentados en este repositorio; hace falta pedírselos al cliente o a
  quien gestione el SharePoint de ADIF.
- **Decidir el criterio de "coincide"**: por hash de contenido (lo que
  prepara este procedimiento, el único que detecta un documento sustituido
  con el mismo nombre) o basta con nombre+tamaño (más simple, menos fiable).
- Con eso resuelto, comparar los dos manifiestos es un `diff`/`join` por
  `sha256_completo` entre el CSV de este documento y el que se genere del
  lado de SharePoint — no hace falta más código del que ya está arriba.
