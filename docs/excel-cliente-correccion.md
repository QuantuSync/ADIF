# Corrección del Excel de entrega al cliente

Sesión 2026-09-06. Álvaro revisó el Excel exportado (3.036 filas, once
columnas) y señaló cinco problemas. Este documento recoge el diagnóstico,
lo que se arregló, lo que se dejó explicado sin tocar código, y los números
finales verificados.

---

## 1. Marcadores de texto en columnas numéricas

`app/exportacion.py` escribía `"(no consta)"`/`"(no aplica)"` en cualquier
celda vacía, incluidas Cantidad y Precio unitario — 540 y 16 apariciones
respectivamente, que convertían esas columnas en texto mixto en Excel.

**Arreglo**: `_celda_numero` devuelve el valor como `float` o `None` (celda
vacía), nunca un marcador. Mismo criterio aplicado a las columnas de texto
(Matrícula, Código del material, Lote) por consistencia y porque es el
formato que el cliente ya maneja: celda vacía, sin variantes. El motivo por
el que falta ya vive en `motivo_revision`/la cola de revisión interna, no
se inventa un texto nuevo para la celda. Formato de celda explícito
añadido (`#,##0.###` para Cantidad, `#,##0.00` para los importes, `0.00%`
para la baja) para que Excel no las trate como texto por estar en
"General".

Tests: `tests/test_exportacion.py` reescrito para el nuevo comportamiento.

## 2. Duplicados sin limpiar

### Lo que NO era

Verificado contra `docs/correccion-defectos-auditoria.md`: el bug de
duplicación infinita (canonicalización de `clave_linea` sin guardia de
`fusion_material`) ya se arregló y limpió la noche del 2026-09-05/06,
confirmado con cero duplicados exactos (`ROW_NUMBER() OVER (PARTITION BY
expediente_id, documento_origen_id, pagina, orden_aparicion)`).

### Lo que sí era

El hueco que `docs/decisiones.md` sección 31 ya había dejado anotado como
pendiente de medir: de las 1.108 líneas huérfanas (`lote_id IS NULL`,
tabla que no se pudo asociar a un lote sin ambigüedad), medido sobre el
corpus completo (no solo `6.25/28510.0019` como en esa sección):

- **268 líneas** eran copia exacta de una línea que YA tiene lote resuelto
  en el mismo expediente (mismo `codigo_precio`, descripción y precio
  unitario, matrícula idéntica, sin `cantidad` perdida) — repetidas solo
  porque una segunda tabla (normalmente el CONTRATO adjuntando el mismo
  cuadro de precios que ya trae el ANEJO) no pudo asociarse a lote.
  Verificado antes de borrar: las 268 estaban `sin_revisar`, sin
  comentarios humanos, todas con `motivo_revision` explicando la
  ambigüedad. **Borradas** dentro de una transacción, con volcado previo
  de `lineas_catalogo` completo (`pg_dump --data-only`, guardado en
  `/home/lucas/adif/lineas_catalogo_backup_20260906.sql` en el servidor de
  desarrollo). Catálogo: 3.036 → **2.768 líneas**.
- **840 líneas** sin ningún lote resuelto equivalente: de estas, 671 son la
  misma materia repetida entre sí (varias copias de la misma tabla técnica
  sin lote, ninguna resuelta) y 169 son líneas únicas que solo les falta
  lote. Todas siguen en la cola de revisión interna, sin tocar.

### Política de exportación (encargo de esta sesión)

`generar_excel_catalogo` gana un parámetro `incluir_pendientes_sin_lote`
(por defecto `False`, expuesto como `?incluir_pendientes=true` en
`GET /catalogo/exportar.xlsx`): las líneas huérfanas no salen en la hoja
"Materiales" por defecto — mostrarían el mismo material repetido sin que
el cliente pueda distinguir una repetición real de un artefacto de
extracción, y siguen genuinamente pendientes de que alguien les asigne
lote. Nunca desaparecen en silencio: la hoja **"Resumen"** siempre dice
cuántas líneas hay en "Materiales", cuántas quedaron fuera y, si las hay,
el desglose por motivo agrupado (`_categoria_motivo`, cuatro categorías
según `app.extraccion.lote_tabla`). Con `incluir_pendientes=true` vuelven a
"Materiales" sin tocar código.

Tests: `tests/test_exportacion.py` (categorización de motivos) y
`tests/test_api_catalogo.py` (exclusión por defecto + hoja Resumen +
inclusión con el parámetro).

### Residuo menor, sin tocar (mismo mecanismo, expedientes de un solo lote)

47 grupos (142 filas) de "mismo material, mismo precio, más de una vez" **sí
siguen** en la hoja Materiales tras el arreglo de arriba. De estos, 32
grupos (67 filas) son la misma tabla repetida entre ANEJO y CONTRATO
(mecanismo B de `docs/hallazgos-extraccion.md` sección 30.2) pero en
expedientes de **un solo lote** — ahí la línea SÍ tiene lote asignado (el
único que hay), así que no cae en el filtro de huérfanas de arriba. La
fusión por firma de material (`_firma_material`, `app/catalogo.py`) no las
funde porque son líneas sin matrícula (p. ej. "PARTIDA ALZADA A JUSTIFICAR
PARA IMPREVISTOS"), y esa firma exige matrícula presente. Sin medir ni
tocar en esta sesión — queda para una sesión aparte, con el mismo cuidado
de verificar antes de fundir/borrar.

## 3. Columnas de precio adjudicado y baja de lote

Ya vivían en cada línea (`LineaCatalogo.precio_adjudicado`,
`LineaCatalogo.baja_lote`, calculadas en `app.catalogo`, sección 4 de
CLAUDE.md) — solo faltaban en el Excel. Añadidas **al final**, sin mover
las once columnas del formato original: "Precio adjudicado" y "Baja del
lote" (formato `0.00%`).

## 4. Código matriz vacío al 100%

No era un fallo del exportador ni del cruce. De los 58 expedientes en base
de datos, solo 8 tienen `codigo_matriz` real, y los 8 son pedidos
derivados de acuerdo marco cuya matriz sigue `sin_publicar` en la
Plataforma — por eso tienen **cero líneas de catálogo** y nunca llegan a
aparecer en el Excel. Nada que arreglar en código: se resuelve solo en
cuanto esas matrices se publiquen y hereden su cuadro de precios
(`app.extraccion.herencia_matriz`).

### Bug real encontrado en el camino: el cruce de códigos estaba roto en silencio

Al investigar el cruce con el Excel de códigos se encontró que
`docker-compose.override.yml` (deploy en `/home/lucas/adif`) monta
`Ejemplo/Input/Códigos de proyecto.xlsx` en el contenedor, y ese fichero
llevaba tiempo **ausente** del árbol de despliegue: Docker, al no
encontrar el origen del bind-mount, creó en su lugar un directorio vacío
tanto en el host como dentro del contenedor (`/data/codigos_proyecto.xlsx`
era un directorio, no un fichero). `asegurar_cruce_codigos` solo atrapa
`FileNotFoundError` — un directorio produce `IsADirectoryError` (via
`openpyxl`/`zipfile`) sin capturar, y como `codigos_cruzados` no se
reintenta nunca una vez escrito, cualquier expediente cuyo intento cayera
en una ventana con el mount roto quedaba marcado `codigos_cruzados = False`
para siempre, indistinguible de un expediente que de verdad no cruza.

Correlación verificada con timestamps: 6 expedientes
(`6.24/28510.0100`, `0101`, `0102`, `0103`, `0111`, `6.25/28510.0248` — los
pedidos derivados de acuerdo marco de la matriz `2.18/04703.00xx`/
`2.24/04110.0037`) tienen su único intento de cruce fechado
`2026-09-06 07:12:2x UTC`, exactamente en la ventana de una de las dos
caídas de `dockerd` documentadas en `docs/diagnostico-caidas-dockerd.md`
(09:12 hora local = 07:12 UTC).

**Restaurado**: el fichero real copiado de vuelta al árbol de despliegue
(`/home/lucas/adif/Ejemplo/Input/Códigos de proyecto.xlsx`), contenedores
reconstruidos. **Reprocesado** el cruce de los 16 expedientes con
`codigos_cruzados = False`: 6 (los de arriba) cruzan correctamente contra
el fichero restaurado y se corrigieron en base de datos (`codigos_cruzados
= True`, `codigo_interno` relleno). Los otros 10 (las 6 matrices
`sin_publicar` del Excel de acuerdo marco más `3.23/28510.0135`,
`4.26/28510.0020`, `6.25/28510.5001_01`, `6.26/28510.0016`) se reintentaron
también y siguen sin cruzar — confirmado con un cruce manual contra el
fichero ya restaurado: genuinamente no están en el Excel de códigos, no es
un efecto del mount roto.

Este arreglo **no cambia los números del Excel de hoy** (los 6 corregidos
siguen sin ninguna línea de catálogo propia, por la matriz sin publicar),
pero corrige datos incorrectos en base de datos y evita que futuras líneas
de estos 6 expedientes salgan sin código interno cuando su matriz se
publique.

**Comprobación permanente añadida** (encargo de esta sesión): 
`app.extraccion.cruce_codigos.validar_ruta_codigos_proyecto`, llamada al
arrancar tanto `app.main` (API) como `app.worker`. Si
`CODIGOS_PROYECTO_PATH` está configurada pero no es un fichero `.xlsx`
legible, el proceso falla al arrancar en vez de continuar con el cruce
roto en silencio. Tests en `tests/extraccion/test_cruce_codigos.py`.

## 5. Huecos menores (código interno/proyecto/nombre)

Confirmado exactamente contra la base de datos: 41 filas sin código
interno/proyecto (`6.26/28510.0016`, el único expediente con líneas de
catálogo que no cruza — confirmado gap real del Excel de códigos, no del
mount, ver punto 4) y 95 filas sin nombre de proyecto (`6.20/28510.0136`,
`6.20/28510.0054`, `6.23/28510.0018`, `6.24/28510.0116` — cuatro
expedientes cuyo Anuncio PCSP no dejó extraer el "Objeto del Contrato";
tres siguen en `pendiente_revision`, uno — `6.20/28510.0136` — ya está
`completado` con el nombre vacío, pendiente de mirar en una sesión aparte
de extracción, no de exportación).

## Hallazgo menor adicional, sin tocar

2 líneas (`6.23/28510.0051`, matrículas `740580020` y `740540009`) tienen
`descripcion = ''` (cadena vacía, no NULL — la columna es `NOT NULL`) con
matrícula pero sin ninguna descripción real capturada, `sin_revisar`. No es
uno de los cinco problemas de esta sesión; queda anotado para una sesión de
extracción.

## Verificación final

Tras el borrado de las 268 líneas y con la política de exclusión de
huérfanas activa (`incluir_pendientes=false`, el comportamiento por
defecto del Excel que se entrega):

| Concepto | Valor |
|---|---|
| Líneas en base de datos (post-limpieza) | 2.768 |
| Líneas en "Materiales" (hoja entregada) | 1.928 |
| Líneas pendientes de revisión (hoja "Resumen") | 840 (611 banda vacía + 131 sin cabecera + 98 lote no declarado) |
| Cantidad / Precio unitario / Precio adjudicado / Baja: tipos de celda | Solo `float`/`int`/vacío — cero texto mixto |
| Matrícula / Código del material / Lote: marcadores de texto | Cero — vacío o valor real |
| Sin código interno/proyecto | 41 (gap real de cruce, confirmado) |
| Sin nombre de proyecto | 95 (gap real de extracción, confirmado) |
| Con código matriz | 0 (gap real de cobertura: las 8 matrices reales no tienen líneas propias) |
| Grupos "mismo material repetido" restantes en Materiales | 47 grupos / 142 filas — 15 grupos / 75 filas son multi-lote legítimo (mismo material, lotes distintos); 32 grupos / 67 filas son el residuo del mecanismo B en expedientes de un solo lote (sin tocar, ver punto 2) |

Suite completa: **332 tests pasan** (319 antes de esta sesión + 13 nuevos:
6 de exportación, 5 de `validar_ruta_codigos_proyecto`, 2 de política de
huérfanas en la API).
