# Sesión 2026-09-21 (cuarta parte) — La unidad del maestro en el proceso automático, la nota de `0177` y los lotes sin expediente

Cuatro bloques. El registro de la sesión anterior es
`docs/sesion-2026-09-21-valores-viejos-lecturas-malas-y-lineas-que-faltan.md`.

---

## Bloque 1 — La unidad del maestro dentro del proceso automático

**Antes.** La unidad que el maestro de materiales de ADIF da por matrícula se
aplicaba con un paso manual (`POST /mantenimiento/maestro-materiales/completar-unidades`)
que no se había vuelto a lanzar desde la carga del maestro. Las líneas nuevas
desde entonces no la tenían: 5.786 líneas, 3.222 celdas del Excel.

**Ahora.** `app.extraccion.maestro_materiales.aplicar_unidades_del_maestro`
corre en dos sitios del proceso automático:

- al **guardar las líneas de cada documento** (`guardar_lineas_catalogo`),
  sobre la fila ya escrita, igual que el motivo de la matrícula fuera del
  maestro: una consulta al maestro por llamada;
- al **final de cada ciclo de mantenimiento**, antes de la auditoría
  (`completar_unidades_desde_maestro` sobre todo el catálogo), para lo que ese
  ciclo no haya vuelto a guardar (un maestro recién recargado). Su resumen va
  en el del ciclo (`unidades_desde_maestro`).

Las reglas:

1. **La unidad del documento manda siempre.** Nunca se pisa; si el maestro da
   otra, se anota la discrepancia como hasta ahora. Si una pasada trae unidad
   para una fila que la tenía del maestro, la del documento la sustituye y la
   marca `unidad_medida_completada_desde_maestro` se quita.
2. La unidad del maestro se **recalcula** en cada pasada, no se hereda: si la
   matrícula deja de figurar en el maestro, la unidad se retira.
3. La partida alzada (`PA` en la celda de unidad) no la recibe: su celda sigue
   siendo "no aplica".
4. Sin maestro cargado no se toca nada.

**La fila lo dice.** En "Motivo de las celdas vacías":
*"Unidad de medida: del maestro de materiales de ADIF (el documento no la
publica)"*. Añadido al diccionario del Excel (columnas 13 y 17).

**Hallazgo al empezar: la P de la placa nervada no lo decía en la fila.** El
encargo daba por hecho que esas filas ya decían que su unidad venía del
maestro; en el Excel del 21/09 (tercera parte) las 3 filas de `612860020`
llevan la `P` sin ninguna nota: solo lo explicaba el diccionario. Desde esta
sesión llevan la misma nota que las demás.

Pruebas nuevas en `engine/tests/test_unidad_del_maestro_2026_09_21_cuarta.py`.
`reconstruccion.py` ya no lanza el paso aparte: lo hace el ciclo.

## Bloque 2 — Las 7 filas de `6.19/28510.0177` sin la nota de cantidad mínima

**Causa, medida en la base aparte** (extracción del expediente con la red
aislada, imprimiendo la cabecera de cada tabla): la tabla de la p.22,
escaneada, empieza en una fila de datos que la extracción toma por cabecera, y
su celda de matrícula trae **dos matrículas** leídas por reconocimiento óptico:
`64315045O 64810014Z`. La comprobación "esta cabecera es de verdad una fila de
datos" quitaba los espacios y buscaba **una** matrícula, así que la daba por
cabecera nueva sin columna de cantidad y cerraba el cuadro de la nota.

**Arreglo**: `_es_celda_de_matriculas` (`app.extraccion.pipeline_anejo`)
reconoce una celda de una o varias matrículas separadas por espacios (y sigue
aceptando una matrícula partida por un espacio). En la base aparte, las 7
filas de la p.22 pasan a llevar la nota: *"Cantidad: es la columna «CANTIDAD
MINIMA A SUMINISTRAR POR PEDIDO» del cuadro, no la cantidad total a comprar;
su columna «PEDIDO INICIAL» trae 2945 en esta fila"*.

## Bloque 3 — Pregunta 17 para el cliente

Añadida a `docs/preguntas-pendientes-cliente.md`, con la lista completa de
materiales por lote en `docs/preguntas-cliente-lotes-sin-expediente.md`:
**a qué expediente pertenece cada lote** cuyas filas no salen en "Materiales"
porque ese lote no es ningún expediente del catálogo.

| Caso | Lotes sin expediente | Filas fuera de "Materiales" | Materiales distintos |
|---|---|---:|---:|
| `6.20/28510.0041` (lote 2) | 1 | 336 | 336 |
| Regulación de tensión, `6.19/28510.0231` (lote 4) y `6.20/28510.0025` (lote 5) | 1, 2, 3 y 6 | 32 | 32 |
| `3.23/28510.0135` (lotes 2 y 6) | 1, 3, 4, 5, 7 y 8 | 20 | 30 |
| `3.22/28510.0048` (lotes 1, 3 y 5) | 2 | 2 | 2 |
| `6.21/28510.0058` y familia | 4 y 8 | 205 | 42 |

Dos cosas que salieron al medirlo y que el encargo no decía:

- **`6.21/28510.0136`** (lote 7) también perdió el 21/09 las 37 filas de la
  tabla del lote 8: las 205 filas del caso son 42 en cada uno de `0058`,
  `0135`, `0137`, `0138` y 37 en `0136`.
- **Los lotes 2, 5, 6 y 9 de esa misma licitación tampoco están en ningún
  expediente**; sus filas ya estaban fuera de "Materiales" antes del 21/09. Se
  dice en la pregunta; no cambia el alcance.

Las cifras de `3.23/28510.0135` (20 filas) son las que salieron el 21/09; el
cuadro aparece dos veces (anejo y contrato) y tiene 30 materiales distintos
en esos seis lotes.

---

## Bloque 4 — Cierre

### Pruebas, imagen y el único reproceso

- **1.411 pruebas en verde** (1.402 al empezar). Imágenes `api` y `worker`
  reconstruidas desde `/mnt/c/dev/ADIF` con el código final, antes del
  reproceso. Copia previa de la base: `/tmp/prod_antes_reproceso_20260922.dump`
  en `adif-postgres-1` (el nombre lleva la fecha equivocada, es de hoy).
- **Un único reproceso completo** (trabajo 33045, `forzar`, sindicación y
  búsqueda apagadas): 517 expedientes, **22 min 16 s**, **`descargas_lanzadas: 0`**,
  ninguna extracción fallida. La pasada de unidades del final del ciclo no
  tuvo nada que completar (`lineas_completadas: 0`): el guardado de cada
  documento ya las había puesto todas. Después del reproceso **no queda
  ninguna línea con matrícula del maestro sin unidad**.
- **Auditoría: 0 errores, 7 avisos** (los mismos siete de ayer).

### El entregable, descargado desde la web

`C:\dev\ADIF\catalogo_adif_2026-09-21-unidad-del-maestro-y-lotes-sin-expediente.xlsx`,
descargado con Chromium desde `/catalogo` pulsando "Exportar Excel" (190 s),
sin avisos de error ni errores de consola. **Idéntico a la exportación del
endpoint de la API (`/catalogo/exportar.xlsx`) salvo `docProps/core.xml`**
(la fecha de creación).

### Comparación con `catalogo_adif_2026-09-21-valores-viejos-y-lineas-que-faltan.xlsx`

| | Antes | Ahora |
|---|---:|---:|
| Filas de "Materiales" | 19.333 | **19.333**, las mismas (0 salen, 0 entran) |
| "Conciliación" | 19.333 = 19.333 | **19.333 = 19.333**, 0 celdas distintas |
| "Contraste de presupuestos" | 486 lotes | 486, **0 celdas distintas** |
| "Resumen" | — | 0 celdas distintas |

**Solo cambian dos columnas de "Materiales", y cada cambio tiene su causa:**

| Columna | Celdas | Causa |
|---|---:|---|
| Unidad de medida | **3.029** (vacía → `ud` 2.943, `m` 84, `kg` 2) | Bloque 1: la unidad del maestro, que no se había aplicado desde su carga. Cada una con su nota |
| Motivo de las celdas vacías | 3.029 | Las mismas filas: desaparece "Unidad de medida: no consta" y entra la nota del maestro |
| Motivo de las celdas vacías | 3.453 | Filas cuya unidad ya venía del maestro (de la última vez que se lanzó el paso manual) y no lo decían: ahora llevan la nota. Entre ellas, las 3 de la `P` de la placa nervada |
| Motivo de las celdas vacías | 7 | Bloque 2: `6.19/28510.0177` p.22, la nota de la cantidad mínima por pedido (5 de ellas ganan también unidad del maestro) |

En total, **6.482 filas dicen que su unidad viene del maestro**.

**Por qué 3.029 y no las 3.222 del encargo**: los 3.222 se midieron sobre el
Excel de 19.857 filas (la reconstrucción de la tercera parte). Contadas con el
mismo criterio —celda vacía y matrícula con unidad en el maestro— el Excel de
19.857 filas da 3.222 y el de 19.333 da **exactamente 3.029**: las 193 de
diferencia se fueron con las 570 filas que salieron de "Materiales" en la
tercera parte (los anejos escaneados, con matrícula y sin unidad).

### La web da las mismas cifras que el Excel

Leído con Chromium: `/conciliacion`, 534 expedientes, 0 que no coincidan en
líneas con la hoja (suman 19.333); `/contraste-presupuestos`, 486 lotes, el
mismo recuento por resultado que la hoja y los once botones con sus cifras
(271 / 13 / 0 / 0 / 84 / 6 / 2 / 11 / 0 / 99). Ningún aviso de error ni error
de consola.

### Cómo ha evolucionado el número de filas desde el 20/09

En lenguaje para el cliente:

| Entregable | Filas | Cambio |
|---|---:|---|
| 20/09 (`…-2026-09-20-motivos-completos.xlsx`) | **20.062** | — |
| 21/09, mañana (`…-contraste-y-en-ejecucion.xlsx`) | 20.062 | Ninguno: se añadió la hoja que compara cada lote con su presupuesto |
| 21/09, segunda entrega (`…-causas-del-contraste.xlsx`) | **19.857** | **−205** |
| 21/09, tercera entrega (`…-valores-viejos-y-lineas-que-faltan.xlsx`) | **19.333** | **−570, +46** |
| 21/09, hoy (`…-unidad-del-maestro-y-lotes-sin-expediente.xlsx`) | **19.333** | Ninguna fila: se completan 3.029 unidades |

**Por qué salen 775 filas.** En todos los casos por la misma razón: **eran
materiales de otro lote atribuidos al expediente equivocado**. Hay licitaciones
que publican en un mismo cuadro los materiales de todos sus lotes, y cada
expediente es solo uno de esos lotes. Antes, un expediente se quedaba con
filas que no eran suyas; ahora cada fila va al expediente de su lote.

- **205 filas** (pequeño material de vía, `6.21/28510.0058` y su familia): el
  rótulo "LOTE 4" y "LOTE 8" del cuadro se leía mal (la letra en negrita salía
  doble, "LLOTE") y esas tablas se sumaban a los lotes 3 y 7. Leídas bien, no
  son de ningún expediente del catálogo.
- **570 filas** (tercera entrega): los cuadros con todos los lotes de
  `6.20/28510.0041` (336), de las grifas (124), de la regulación de tensión
  (77), de `3.23/28510.0135` (22), de `3.22/28510.0048` (2), de
  `6.19/28510.0195` (8) y una de `3.22/28510.0009`.

**¿Se ha perdido algún material?** No de la base de datos: todas esas filas
siguen guardadas, con su lote de la licitación y su motivo. De "Materiales",
dos casos distintos:

- **Siguen en el Excel, en el expediente de su lote**, las de los lotes que sí
  son un expediente del catálogo: las 124 de las grifas, las 8 de `0195`, 2 de
  `3.23/28510.0135` y, de la regulación de tensión, las de los lotes 4 y 5
  (cada uno de sus dos expedientes se queda con el suyo). Solo han cambiado de
  expediente, al que es el suyo.
- **No salen** las de los lotes que no son ningún expediente del catálogo: 336
  de `6.20/28510.0041`, los 32 materiales de los lotes 1, 2, 3 y 6 de la
  regulación de tensión (el anejo está en los dos expedientes, así que cada
  material está guardado dos veces), 20 de `3.23/28510.0135`, 2 de
  `3.22/28510.0048` y las 205 de la familia `6.21/28510.0058`. Es la
  **pregunta 17**: en cuanto ADIF diga qué expediente es cada uno de esos
  lotes, entran solas.

**Por qué entran 46 filas.** 39 son líneas que faltaban en 16 lotes (una
partida alzada que la tabla no leía, la primera fila de una página, filas
que el cuadro repite…); cada una solo se aceptó porque con ella el lote
cuadra al céntimo con su presupuesto publicado. Las otras 7 son filas de
`3.22/28510.0009` que no tenían lote y ahora tienen el suyo.

---

## Pendiente para la próxima sesión

1. **Las 723 celdas que el código actual ya no lee** (83 cantidades de
   `6.26/28510.0016`, 212 unidades en cinco expedientes y 428 cantidades sin
   lote de `6.21/28510.0112`/`0113`): el valor guardado es el bueno y hoy
   sobrevive porque un `None` no pisa. Hay que arreglar la lectura.
2. **La prueba de reconstrucción desde cero** con el código de esta sesión
   (CONTEXTO.md sección 13): mismas filas que producción, y como únicas
   diferencias esas 723 celdas.
3. Las preguntas 16 (qué cantidad mostrar en los cuadros de mínima por pedido)
   y 17 (a qué expediente pertenece cada lote) a ADIF.
