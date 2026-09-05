# Corrección de defectos de la auditoría previa

Sesión 2026-09-05/06. Continuación de `docs/auditoria-previa.md`: aquí se
investiga y cierra el bloque 1 del encargo de esa sesión — la duplicación
real del catálogo en los expedientes multi-lote.

---

## 1. Duplicación del catálogo en expedientes multi-lote

### Síntoma

El catálogo creció de forma sostenida sin que se hubiera añadido ningún
expediente ni documento nuevo. Medido en vivo (2026-09-06) antes de tocar
nada: 7.564 líneas totales, de las cuales **4.504 eran duplicados exactos**
(mismo `expediente_id`, `documento_origen_id`, `pagina` y `orden_aparicion`,
con los campos de contenido —`codigo_precio`, `matricula`, `descripcion`,
`cantidad`, `precio_unitario`, `unidad_medida`, `motivo_revision`,
`baja_lote`— idénticos entre copias, verificado con un `count(DISTINCT ...)`
sobre los 1.132 grupos afectados: **las 1.132 tuplas dieron exactamente 1
variante de contenido**, ninguna con datos distintos entre copias). Todas
las filas duplicadas tenían `estado_revision = sin_revisar` y `comentarios
IS NULL`: ningún trabajo de revisión humana en riesgo.

Concentrado en siete expedientes, todos multi-lote (CLAUDE.md sección 27):

| Expediente | Líneas antes | Huérfanas antes | Líneas después | Huérfanas después |
|---|---|---|---|---|
| `6.25/28510.0019` | 3.064 | 2.968 | 838 | 742 |
| `6.24/28510.0130` |   760 |   750 | 160 | 150 |
| `6.24/28510.0117` |   343 |   300 | 103 |  60 |
| `6.24/28510.0094` |   337 |   316 |  89 |  68 |
| `6.24/28510.0203` |   256 |   204 | 103 |  51 |
| `6.25/28510.0028` |   163 |   132 |  64 |  33 |
| `6.25/28510.0027` |   120 |   112 |  36 |  28 |

Ningún expediente de lote único tenía ni una sola línea huérfana afectada:
el defecto solo podía manifestarse donde existen líneas con
`lote_id IS NULL` (huérfanas, CLAUDE.md sección 2 y
`app.models.LineaCatalogo.lote_id`).

### Causa raíz

`app.catalogo.guardar_lineas_catalogo`, en la rama que actualiza una fila ya
existente, "canonicalizaba" `clave_linea` de vuelta al `codigo_precio`
desnudo de la fila, **sin comprobar si esa línea era huérfana**:

```python
if existente.codigo_precio:
    clave_ideal = existente.codigo_precio.strip()
    if clave_ideal:
        existente.clave_linea = clave_ideal
```

Este paso es correcto y necesario para una línea **con lote** (`lote_id`
conocido): cuando dos tablas del mismo lote repiten un material, una con
`codigo_precio` propio y otra sin él, se funden por `matricula +
descripcion + precio_unitario` (`_firma_material`) bajo la clave de
matrícula, y hay que "subir" la clave a la de `codigo_precio` en cuanto se
conoce, para que gane siempre esa clave sea cual sea el orden de llegada de
los documentos (docstring de `_combinar_por_clave`, caso real
`6.24/28510.0116`).

Pero una línea **huérfana** (`lote_id IS NULL`, tabla cuya asociación a
lote quedó ambigua — CLAUDE.md sección 2, `app.extraccion.lote_tabla`) no
usa esa clave desnuda: `app.extraccion.pipeline_anejo.procesar_anejo` le
añade un sufijo de página y franja vertical
(`f"{clave}@p{pagina}y{bbox_top}"`) precisamente para poder distinguir dos
tablas ambiguas del mismo documento que repiten el mismo `codigo_precio`
(caso real documentado en el propio módulo, `6.25/28510.0027`: los LOTE 2,
4, 5 y 6 traen cada uno su propio "P-1".."P-6").

La secuencia real, reconstruida con `created_at` de las filas duplicadas
(expediente `6.25/28510.0019`, matrícula `631500453`, cuatro
reprocesos reales entre el 2026-09-04 y el 2026-09-05):

1. **Reproceso 1**: se inserta la fila con `clave_linea =
   "P-094@p24y198"` (sufijada, correcta y única).
2. **Reproceso 2**: se recalcula la misma clave sufijada, la búsqueda por
   clave exacta SÍ encuentra la fila del paso 1 (`existente` no es `None`)
   → entra en la rama de actualización → el bloque de arriba, sin guardia,
   la "canonicaliza" a `clave_linea = "P-094"` (sin sufijo). La fila sigue
   siendo una sola, pero su clave ya no es la que el sistema recalculará la
   próxima vez.
3. **Reproceso 3**: se recalcula de nuevo `"P-094@p24y198"` (el cálculo en
   `pipeline_anejo` no depende de lo que haya guardado en la base de
   datos). La búsqueda por clave exacta busca `"P-094@p24y198"`, pero la
   fila guardada ahora tiene `"P-094"` → **no la encuentra** → inserta una
   fila nueva, idéntica en contenido, con la clave sufijada de nuevo.
4. **Reproceso 4**: esa fila nueva se encuentra, se actualiza, y el mismo
   bloque sin guardia la canonicaliza otra vez a `"P-094"` sin sufijo →
   vuelve a quedar "invisible" para el siguiente reproceso.

Cada ciclo de mantenimiento programado que reprocesaba estos expedientes
—atrapados en `pendiente_revision` por cobertura parcial de lotes, CLAUDE.md
sección 27, así que nunca llegaban a `completado` y volvían a entrar en
cada ronda— añadía exactamente una copia nueva por línea huérfana con
`codigo_precio`. `app.mantenimiento.frescura.VERSION_LOGICA_EXTRACCION`
sube en varias sesiones de desarrollo (para forzar el reproceso tras un
cambio en la cascada); cada subida disparaba otra ronda de duplicación para
estos siete expedientes, mientras que los expedientes sin huérfanas (o con
huérfanas sin `codigo_precio`, que caen en la rama de `hash(descripcion +
orden)` y no coinciden con este defecto) nunca se vieron afectados —
coherente con que el resto del catálogo (`6.23/28510.0051`, 1.079 líneas,
0 huérfanas) no mostrara ni un solo duplicado.

### Arreglo

`app.catalogo.guardar_lineas_catalogo`: la canonicalización a
`codigo_precio` desnudo ahora exige `fusion_material` (`True` solo cuando
`lote_id is not None` — ver la variable ya existente en la función), además
de `existente.codigo_precio`:

```python
if fusion_material and existente.codigo_precio:
    ...
```

Para una huérfana, `clave_linea` nunca vuelve a tocarse tras su inserción:
sigue siendo exactamente la que calculó `pipeline_anejo` (con o sin
sufijo), estable entre reprocesos, así que la búsqueda por clave exacta del
siguiente ciclo siempre la encuentra y actualiza en vez de duplicarla.

Regresión cubierta en
`tests/test_catalogo.py::test_guardar_lineas_catalogo_huerfana_con_clave_sufijada_no_se_duplica_al_reprocesar`
(el test previo,
`test_guardar_lineas_catalogo_huerfana_sin_lote_no_se_duplica_al_reprocesar`,
no ejercitaba el defecto porque su clave de prueba ya coincidía por
casualidad con su propio `codigo_precio` — canonicalizarla era un no-op).

### Limpieza de lo ya guardado

Verificado primero que los 1.132 grupos de duplicados eran, sin excepción,
copias exactas del mismo contenido (sección 1 de arriba) y que ninguna
tenía revisión humana. Colapsados con `ROW_NUMBER() OVER (PARTITION BY
expediente_id, documento_origen_id, pagina, orden_aparicion ORDER BY id)`,
conservando la fila de menor `id` de cada grupo y borrando el resto — 4.504
filas eliminadas, dentro de una transacción, con un volcado previo de la
tabla completa (`pg_dump --data-only -t lineas_catalogo`) guardado aparte
por si hiciera falta revertir.

**Recuento correcto tras la limpieza: 3.060 líneas de catálogo, 57
expedientes** (32 `pendiente_revision`, 15 `sin_publicar`, 10 `completado`).

Las huérfanas que quedan en estos siete expedientes (742 en `0019`, 150 en
`0130`, etc.) **no son el mismo defecto**: son la duplicación
entre-documentos ya documentada en `docs/decisiones.md` sección 31 (el
mismo cuadro de precios técnico aparece copiado tanto en `ANEJO_1` como en
el `CONTRATO` que lo adjunta como anejo firmado) — deliberadamente sin
tocar aquí, porque fundirlas exigiría el mismo tipo de fusión por firma de
material que esa sección ya explica por qué no se aplica a huérfanas (podría
confundir el mismo material ofertado en dos lotes distintos). Sigue siendo
el "hueco real y accionable" que esa sección ya señalaba, ahora con un
recuento correcto del que partir.

### Comprobación permanente añadida (encargo de esta sesión, punto 4)

`app.mantenimiento.frescura` gana tres funciones:

- `documentos_sin_cambios(expediente, documentos)`: compara la huella
  actual de documentos contra `expediente.huella_documentos` (el mismo
  mecanismo del bloque 1 de ejecución incremental, CLAUDE.md sección 23).
- `contar_lineas_catalogo(db, expediente_id)`.
- `detectar_crecimiento_sin_cambios(conteo_antes, conteo_despues)`: motivo
  de revisión explícito si el recuento creció.

`app.worker.procesar_extraer_expediente` las usa: si los documentos de un
expediente no cambiaron desde su última extracción con éxito, captura el
recuento de líneas antes de reprocesar y lo compara con el de después. Si
creció, añade un motivo a `Expediente.error` y — si el expediente había
quedado `completado` — lo baja a `pendiente_revision`, para que la próxima
duplicación silenciosa se detecte sola en vez de esperar a la próxima
auditoría manual.
