# Sesión 2026-09-22 — La reconstrucción desde cero, idéntica a producción

Dos bloques. El registro de la sesión anterior es
`docs/sesion-2026-09-21-unidad-del-maestro-nota-de-0177-y-lotes-sin-expediente.md`.

Objetivo: que el catálogo se pueda reconstruir desde cero con el código actual
y salga idéntico a producción, salvo las confirmaciones manuales de la cola de
revisión. Cuando esto se migre a un servidor se montará una base nueva.

---

## Cómo se ha medido

- **La referencia ("antes")**: una reconstrucción completa desde cero con el
  código del cierre de ayer (`d35ee0c`), en `adif_reconstruccion`, con la red
  aislada y dos pasadas (517 extracciones cada una, 0 descargas, 0 fallos),
  comparada con el Excel entregado ayer y con una copia de producción de antes
  de la sesión (`adif_prod_antes`).
- **Cada arreglo, en unos pocos expedientes**: `engine/scripts/reconstruccion/extrae_subconjunto.py`
  extrae desde cero solo los expedientes nombrados en una base aparte
  (`adif_reconstruccion_seco`) y compara sus líneas con producción celda a
  celda. Sin `--vaciar`, sobre una copia del estado de producción, enseña qué
  hace el código nuevo con los valores y las claves que producción ya tiene.
  Para las 723 celdas se usaron los 24 expedientes de sus documentos (los
  cinco y sus hermanos que comparten documento).
- `compara_bd.py` empareja ahora por contenido las filas cuya clave interna
  cambió (ver la causa 1 del bloque 2) y acepta los nombres de las dos bases.

**Aviso de entorno que costó una pasada**: el contenedor de la reconstrucción
necesita `MODEL_API_KEY` en su entorno aunque la red esté aislada. Sin clave
no se construye el proveedor de modelo y **tampoco se lee la caché en disco
del modelo** (`CachedModelProvider` envuelve al proveedor): las tablas sin
cabecera cuyo mapeo está en esa caché no se extraen. La primera reconstrucción
de la sesión se lanzó así y se tiró. Con la red `--internal` la clave no puede
llamar a nada: lo que no está en caché falla.

---

## Bloque 1 — Las 723 celdas que el código actual ya no leía

Agrupadas por causa en el código:

| Causa | Celdas | Resultado |
|---|---:|---|
| **No era una cantidad**: `6.21/28510.0112`/`0113`, cuadro de «impacto del fallo en la seguridad operacional» (pp.159-187 de sus dos documentos). En las 428 el valor guardado es exactamente la celda de «PESO en toneladas» (13 t un semicambio, 4,5 t una aguja) | 428 | El código actual acierta al no leerla. **Vaciadas en producción, decisión tuya** (`UPDATE` fila a fila, 428 de 428 coincidencias) |
| Subcolumna de la cabecera: en `6.26/28510.0016` p.10 «PRECIO ADQUISICIÓN» y «CANTIDAD ESTIMADA» son subcolumnas (430,7-483,7) de la columna de las pp.11-12 (427,2-487,1), a 3,5 pt de cada borde; la herencia del mapeo por geometría exigía 3 | 83 | **Recuperadas**: `heredar_mapeo_por_geometria` acepta la columna que coincide con la **madre** de la subcolumna en la cabecera, nunca una que ya tenga otro campo (la primera versión, «la que la contiene», causó la regresión de `6.19/28510.0122`, ver el bloque 2) |
| Tabla sin cabecera propia con «UD.» en una columna que el mapeo no reclama (`derivar_mapeo_por_contenido` nunca asigna la unidad): `6.22/28510.0094` pp.5-6 y p.20, `0122`/`0155`/`0156` pp.11-12 | 203 | **Recuperadas**: `completar_unidad_por_contenido`, hermana de la de cantidad (el documento declara la unidad en otra tabla, y hay exactamente una columna libre con todos sus valores unidades conocidas) |
| Columna fantasma de la unidad: `4.26/28510.0020` pp.14-17, la cabecera «Ud.» ocupa dos rangos y en unas filas la unidad cae en el de al lado | 9 | **Recuperadas**: recuperación de columna fantasma para la unidad, con la prueba estricta de que la celda es una unidad conocida («Precio mensual» se queda fuera) |

**Las 212 unidades seguían siendo diferencia** con la unidad del maestro dentro
del ciclo: sus matrículas no tienen unidad en el maestro. Había además 151
filas en las que el código tampoco leía la unidad del documento y el maestro
lo tapaba con el mismo valor (`ud`), cambiando solo la nota de la fila.

**Comprobación en los 24 expedientes**: después de los arreglos, las 83
cantidades y las 212 unidades salen iguales que en producción, y las filas
coinciden todas (0 de más, 0 de menos). Cambian otras celdas, todas del mismo
tipo y **aceptadas por ti**: 823 filas de los mismos documentos ganan una
unidad que está literal en su fila («UD.»/«Ud.»), unas 287 de ellas en lotes
que salen en «Materiales»; ~470 que tenían la del maestro la toman del
documento (mismo valor, sin la nota del maestro); y las 83 filas de
`6.26/28510.0016` pp.11-12 ganan su código de precio (la «PARTIDA», 43, 44…,
igual que las de la p.10).

Pruebas: `engine/tests/test_lecturas_recuperadas_2026_09_22.py`.

---

## Bloque 2 — Prueba de reconstrucción y cierre

### Lo que separaba la referencia de producción, además de las 723

La referencia destapó cuatro causas más, y dos grupos de restos viejos:

| Causa | Qué se veía | Qué se hizo |
|---|---|---|
| 1. Clave interna de otro orden de aparición: una fila sin código ni matrícula lleva por clave un hash de su descripción y su orden; producción la conservaba con el orden de cuando se insertó, y en cada reproceso la línea la encontraba por firma y le ponía «fila fundida con otra de igual descripción… confirmar» | 441 filas de 10 expedientes con otra clave, 51 con ese motivo; no se ven en el Excel | La fila guardada con la clave de otra pasada, que esta pasada aún no ha escrito, toma la clave de hoy y no es una fusión (`guardar_lineas_catalogo`) |
| 2. `baja_heredada_de_matriz` solo se ponía a `True` y nunca se recalculaba | 33 lotes con la marca de una pasada antigua (`6.19/28510.0022` ni siquiera tiene baja); solo se ve en la API | Se recalcula con la baja del lote en cada extracción; la herencia la vuelve a poner si de verdad hereda |
| 3. El aviso de integridad «0 -> 31 líneas sin que cambiaran sus documentos» | `6.20/28510.0040`, que en la pasada 1 se extrae antes que su matriz `6.18/28510.0003` y hereda en la 2 | Pasar de 0 líneas a N no es una duplicación: no avisa |
| 4. La cita de la baja en «Conciliación» salía de trazas de expediente que escribió el código del 03-04/09 | 13 celdas | **Decisión tuya**: los multilote citan desde la traza de cada lote, la que declara su baja de hoy. 124 filas ganan la cita y 12 la cambian por la de su lote (`6.23/28510.0051` cita ahora sus dos bajas, no una); ninguna la pierde |
| Restos de expedientes sin ningún documento | 9 lotes vacíos (conjunto de prueba `sin_publicar`, `6.14/28510.0148`/`0177`, `6.25/28510.5001/01`), importes en 8 expedientes de prueba y una baja global | **Decisión tuya**: limpiados en producción, comprobando cada valor |

Las trazas en sí no pueden ser idénticas: una traza con otro valor u otro
documento se conserva como historia (`app.extraccion.traza`), y una base nueva
no tiene historia. Producción guarda 69 trazas de baja que la reconstrucción
no tiene; desde el punto 4, ninguna llega al Excel ni a la web.

### La regresión de `6.19/28510.0122`, y cómo se validó

El primer arreglo de la subcolumna aceptaba «la columna que contiene a la de
la cabecera». En la p.16, escaneada y con otra maquetación, eso llevó el precio
a la columna de la referencia, y la recuperación de columna fantasma tomó
«ESQUEMA VIA 311 623» por importe: **11 precios pasaron de 395 € a 311.623 €**
con el reproceso de las 10:30. No lo detectó la reconstrucción, que llevaba el
mismo fallo (se paró), sino la comparación del entregable con el de ayer. Arreglo: solo
vale la columna que coincide con la **madre** de la subcolumna en la cabecera.
Comparando la base de antes de la sesión con la de después, fue la única
sobrescritura de un valor por otro, fuera de las lecturas que aceptaste.

**Decisión tuya: el reproceso completo que cuenta es el de las 10:30 más la
reextracción de `6.19/28510.0122`, y lo valida la reconstrucción desde cero.
Si la reconstrucción saca cualquier diferencia con producción más allá de las
confirmaciones manuales, se para y se te cuenta antes de lanzar otro
reproceso completo.** Tras la reextracción, las 182 líneas de `0122` son
idénticas a las de antes de la sesión (precio, motivo, unidad y clave).

Hubo además un reproceso de producción anterior (trabajo 33565), lanzado a las
10:02 antes de terminar de analizar la referencia. Se paró en 239 de 518
expedientes, y sus 279 trabajos se marcaron fallidos («cancelado a mano»). No
cuenta.

### Pasos de cierre

1. **1.429 pruebas en verde** (1.411 al empezar). Imagen `api`/`worker`
   reconstruida desde `/mnt/c/dev/ADIF` antes de cada reproceso y de cada
   exportación.
2. **Reproceso completo de producción** (trabajo 34083, `forzar`, sindicación
   y búsqueda apagadas): 517 expedientes, **21 min 39 s, `descargas_lanzadas: 0`**,
   ninguna extracción fallida. Más la reextracción de `6.19/28510.0122`
   (trabajo 34602).
3. **Reconstrucción desde cero** en `adif_reconstruccion`, con la red
   `--internal` y dos pasadas (24 y 22 min; 517 extracciones cada una, 0
   descargas, 0 fallos).
4. **Comparación** de producción con la segunda pasada:

| | Antes de la sesión (código de ayer) | Ahora |
|---|---:|---:|
| «Materiales»: filas | 19.333 = 19.333 | 19.333 = 19.333 |
| «Materiales»: celdas distintas | **336** (83 cantidades, 74 unidades, 179 motivos) | **0** |
| «Conciliación»: celdas distintas | **13** | **0** |
| «Contraste de presupuestos»: celdas distintas | **8** (`6.26/28510.0016` lote 1 y el recuento) | **0** |
| «Resumen»: celdas distintas | 0 | 0 |
| Base, líneas: campos distintos | **1.292** (511 cantidades, 577 de unidad, 151 marcas del maestro, 51 motivos, 2 manuales) y 524 filas con otra clave | **2** (las dos confirmaciones manuales) y 0 con otra clave |
| Base, lotes | 9 de más en producción y 33 marcas | 0 |
| Base, expedientes | 18 campos | 0 |

   Las dos que quedan son las confirmaciones manuales de la cola de revisión:
   `6.24/28510.0128` lote 1 (matrícula confirmada a mano) y `6.24/28510.0130`
   lote 6 (candidatos de matrícula rechazados). La auditoría de la base
   reconstruida da un error, `lineas_cambian_sin_cambiar_documentos` en
   `6.20/28510.0040`, porque compara con la auditoría de su pasada 1, antes de
   que heredara sus 31 líneas. Es propio de reconstruir en dos pasadas; en
   producción no aparece.
5. **El entregable, descargado desde la web** con Chromium desde `/catalogo`,
   pulsando «Exportar Excel» (202 s, sin avisos de error ni errores de
   consola), después de la reextracción de `0122`. **Idéntico a la
   exportación de la API salvo `docProps/core.xml`.**
6. **Comparación con `catalogo_adif_2026-09-21-unidad-del-maestro-y-lotes-sin-expediente.xlsx`**:
   las mismas **19.333 filas y 390 expedientes**, y todas las filas emparejadas:
   **ningún expediente pierde ni gana filas**. Cambian:

| Hoja / columna | Celdas | Por qué |
|---|---:|---|
| «Materiales», Unidad de medida | 441 | Vacía → la unidad literal de su fila (comprobadas las 441 contra su fragmento): `6.22/28510.0125` lote 1 (123), `4.25/28510.0132` (96), `6.22/28510.0094` lote 2 (82), `0126` lote 2 (82), `6.18/28510.0109` y sus 14 pedidos `6.19/…` (m3 y m3×km, 4 cada uno), `6.22/28510.0174` y `6.25/28510.0251` (1 cada uno). Cuatro son partidas alzadas cuya fila trae «UD.» en la celda de unidad |
| «Materiales», Código de precio | 83 | `6.26/28510.0016` pp.11-12: la «PARTIDA» (43…125), como en la p.10 |
| «Materiales», Motivo de las celdas vacías | 721 | Las mismas filas: desaparece «Unidad de medida: no consta» (437), «del maestro» (197, ahora la da el documento), «no aplica (partida alzada)» (4) y «Código de precio: no consta» (83) |
| «Conciliación», Baja y de dónde sale | 136 | La cita desde la traza de cada lote (punto 4 de la tabla de causas) |
| «Contraste de presupuestos», «Resumen» | 0 | — |

   En la base, fuera del Excel: 977 unidades nuevas en total (todas literales
   en su fila), 499 filas que pasan de la unidad del maestro a la del
   documento, las 428 cantidades-peso vaciadas y los restos limpiados.
7. **Conciliación**: 534 expedientes, que suman **19.333 = 19.333** filas de
   «Materiales». **Auditoría de producción: 0 errores, 7 avisos** (los siete de
   siempre). **Contraste**: 486 lotes; 271 cuadran al céntimo, 13 con una
   diferencia menor del 0,01 %, 0 / 0 / 84 / 6 / 2 / 11 / 0 en las causas de
   no cuadrar, y 99 que no se pueden cerrar. **La web da las mismas cifras**:
   `/conciliacion`, 534 filas y 0 que no coincidan en líneas;
   `/contraste-presupuestos`, 486 filas con los mismos resultados y los once
   botones con esas cifras; ni avisos ni errores de consola.
8. La reconstrucción idéntica a producción es, desde hoy, **condición de
   cierre de cualquier cambio de la extracción** (CONTEXTO.md sección 13).

Copias de la base de esta sesión, en `adif-postgres-1`:
`/tmp/prod_antes_428_20260922.dump`, `/tmp/prod_antes_reproceso_20260922.dump`,
`/tmp/prod_antes_restos_20260922.dump`, `/tmp/prod_antes_reproceso_final_20260922.dump`
y `/tmp/prod_antes_reextraer_0122_20260922.dump`, además de la base `adif_prod_antes`.

## Lo que queda anotado, sin decidir

- **Citas que siguen faltando**: 50 bajas únicas y 5 por lote siguen sin cita
  en «Conciliación», porque ni el expediente ni sus lotes tienen una traza que
  declare esa baja. No se ha tocado.
- Las preguntas 16 y 17 a ADIF siguen abiertas.
