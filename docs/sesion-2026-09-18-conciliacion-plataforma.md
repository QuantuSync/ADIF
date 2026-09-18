# Sesión 2026-09-18 (continuación) — Columna duplicada, código interno heredado, orden total, atribución de la auditoría y hoja de conciliación

Cinco bloques. Ningún reproceso: el catálogo en base de datos se queda en
**37.638 líneas** antes y después. Todo lo que cambia es presentación (Excel),
criterio de cruce o criterio de auditoría.

---

## Bloque 1 — Se quita "Nº de expediente (documento)"

### Comprobación previa: quién dependía de la columna

Encargo explícito: comprobar antes de quitarla. **Nadie fuera del propio
generador del Excel.**

| Sitio | Depende |
|---|---|
| `engine/app/exportacion.py` | sí — es donde se define y se escribe |
| `engine/tests/test_api_catalogo.py`, `test_exportacion.py` | sí — dos aserciones |
| Web (`web/`) | **no**. La única referencia al Excel es el enlace de descarga (`CatalogoPanel.tsx:415`, `${apiUrl}/catalogo/exportar.xlsx`); ninguna pantalla lee la columna |
| API (`/catalogo`, `fila_a_dict`) | **no**. La API sirve `codigo_expediente`, que es el mismo campo, y nunca ha tenido una segunda clave |
| Base de datos | **no**. Nunca existió un campo propio: las dos columnas salían de `expediente.codigo_expediente` |

### Lo aplicado

`COLUMNAS` pasa de 18 a 17. Se queda "Código de expediente", que es el nombre
por el que el cliente filtra. Las dos tests actualizadas, más una nueva que
prohíbe que vuelva a aparecer una segunda columna con el mismo valor.

---

## Bloque 2 — "Código interno" deja de heredarse de la fila de otro expediente

### La medición que pedía el encargo, antes de tocar nada

Qué lleva hoy "Código matriz" en los 28 expedientes que cruzan por una clave
distinta de `codigo_expediente` → `Nº Expediente`:

| Clave del cruce | Expedientes | Con "Código matriz" relleno |
|---|---:|---:|
| `codigo_expediente` → `MATRIZ` | 23 | **0** |
| `codigo_matriz` → `Nº Expediente` | 3 | 3 |
| `codigo_matriz` → `MATRIZ` | 2 | 2 |
| **Total** | **28** | **5** |

**El hueco de los 23 no es un dato perdido: es que ahí no hay matriz que
guardar.** Cruzar `codigo_expediente` contra la columna `MATRIZ` significa que
la fila encontrada es la de un pedido que declara a NUESTRO expediente como su
acuerdo marco — la relación va en sentido contrario. Escribir el `Nº
Expediente` de esa fila en "Código matriz" diría que un pedido derivado es la
matriz de su propio acuerdo marco.

En los 5 restantes, "Código matriz" **ya lleva el código correcto** y coincide
con la fila que encontró el cruce (`6.26/28510.0014` → `6.25/28510.0016`;
`0032` y `0071` → `6.20/28510.0136`; `0047`/`0048` → `2.24/04110.0036`/`0035`).

Conclusión: **no se pierde ningún código de matriz al vaciar el interno.**

### Lo aplicado

- `_IndiceCodigosProyecto.buscar` devuelve ahora una tercera señal: si la fila
  encontrada es la **del propio expediente** (solo la primera de las cuatro
  claves lo garantiza).
- `CruceCodigos.fila_propia`; `codigo_interno` solo se devuelve cuando es
  `True`. `cruzado` sigue siendo `True` — la fila existe y su columna MATRIZ
  puede seguir aportando información, y "Código matriz"/"Estado del contrato
  (SAP)" no cambian de comportamiento.
- `expedientes.cruce_fila_propia` (migración **0036**), para que la celda vacía
  pueda explicarse. Se deja a `NULL` y `asegurar_cruce_codigos` rehace el cruce
  **una sola vez** sobre cada expediente ya cruzado (el índice del Excel está en
  memoria, no cuesta nada); el exportador dispara ese backfill antes de generar.
- Texto nuevo de celda vacía, escrito para almacenes y con el test de jerga
  prohibida en vigor:
  `Código interno: no consta (este expediente no figura por sí mismo en el listado de códigos de ADIF)`

### Resultado sobre los datos reales

```
cruce_fila_propia | expedientes | con código interno
------------------+-------------+-------------------
 true             |         352 |               321
 false            |          28 |                 0
 (no cruza)       |         231 |                 0
```

En el Excel: **24 expedientes pierden el interno ajeno, 1.404 filas**. (Los
otros 4 de los 28 no aportan ninguna línea al entregable.) El total de filas con
"Código interno" relleno baja de 15.361 a 13.957 — exactamente esas 1.404.

Motivos de "Código interno" vacío en el Excel nuevo:

| Filas | Motivo |
|---:|---|
| 2.381 | no consta (este expediente no aparece en el listado de códigos de ADIF) |
| **1.404** | **no consta (este expediente no figura por sí mismo en el listado de códigos de ADIF)** |
| 497 | no consta (el listado de códigos de ADIF no trae número interno para este expediente) |

### Comprobación pedida: ¿quedan internos repetidos entre expedientes distintos?

**Sí, 42 en el Excel (52 en base de datos), y ninguno llega por esta vía.**
Verificado en solo lectura sobre los 611 expedientes:

- Los 28 de la herencia **han desaparecido de la lista**. El caso que traía el
  encargo, `20012` en `6.26/28510.0032` y `6.26/28510.0071`, ya no existe: ese
  interno solo lo lleva ahora `6.20/28510.0136`, que es su dueño real.
- De los que quedan, **los 52 grupos cruzan todos por su fila propia**
  (`cruce_fila_propia = true`) y **0 de 52 quedan sin respaldo en el propio
  listado de ADIF**: es el fichero de códigos el que asigna el mismo `Nº
  Interno` a varias filas con `Nº Expediente` distinto. Ejemplo:

  | Nº Interno | Expedientes en el catálogo | Filas del Excel de ADIF con ese Nº Interno |
  |---|---|---|
  | 19001 | `6.19/28510.0135`, `0175`, `0177` | `6.19/28510.0135`, `0175`, **`0176`**, `0177` |
  | 19004 | `6.19/28510.0115`, `0161`, `0162`, `0163` | las mismas cuatro |

  Es lo que CONTEXTO.md sección 7 ya dice de este campo: *"No uses `Nº Interno`
  (se repite entre filas: agrupa varios pedidos de un mismo procedimiento)"*.
  Cada expediente coge el suyo, de su propia fila. **No es herencia; es cómo
  ADIF numera una familia.** Si el cliente quiere que tampoco eso se repita, es
  una decisión sobre su listado, no sobre este sistema.

---

## Bloque 3 — Orden total de las líneas

`LineaCatalogo.id` añadido como último desempate en `consultar_catalogo`, detrás
de `expediente`, `lote` y `orden_aparicion`. Los tres anteriores no forman un
orden total: `orden_aparicion` es la posición de la fila dentro de **su** tabla,
así que se repite entre dos documentos del mismo expediente y lote, y Postgres
no garantiza nada entre filas empatadas.

### Demostrado: dos exportaciones seguidas, byte a byte

Un `.xlsx` es un ZIP y sus entradas llevan la fecha de creación, que cambia
siempre; se comparan los **contenidos** de las 11 entradas:

```
mismas entradas: True (11)
  DISTINTA: docProps/core.xml
entradas identicas byte a byte: 10; distintas: 1
```

La única entrada distinta es la metadatos de openpyxl (`<dcterms:created>`
`11:08:48Z` frente a `11:11:41Z`). **`xl/worksheets/sheet1.xml` (Materiales),
sheet2 (Conciliación), sheet3 (Resumen) y las siete entradas restantes son
idénticas byte a byte.**

Contra el Excel de la sesión anterior quedan exactamente **2 filas** con
contenido distinto — las 813 y 814 de `6.21/28510.0108` —, y son un intercambio
exacto (`viejo[813] == nuevo[814]` y `viejo[814] == nuevo[813]`): las dos
descripciones de semicambio DSIH-60 que ya se habían anotado como el síntoma.
Con el `id` en el orden, ese par ya no se mueve.

Tests nuevos: `engine/tests/test_catalogo_consulta.py` (3), incluido uno que
compila la consulta y comprueba que el `ORDER BY` termina en
`lineas_catalogo.id` — el de comportamiento solo pasaría por casualidad si el
motor devolviera las filas empatadas en orden de inserción.

---

## Bloque 4 — La atribución del error de `6.23/28510.0105`

### Qué pasaba de verdad

El encargo lo decía bien: **es un falso positivo**. La regla anterior comparaba
`lineas_podadas` contra la diferencia neta de recuento, y eso solo cuadra cuando
la reextracción no crea ninguna línea. Los números reales del trabajo 21566:

```
6.23/28510.0105:  36 → 35 líneas (diferencia −1)
                  lineas_podadas = 32, lineas_creadas = 31
```

La única fila que de verdad se pierde la quitó el filtro de extracción
(`_es_concepto_de_presupuesto`, arreglo del día anterior: las filas "Suma",
"IVA (21%)", "Presupuesto de Ejecución Material" pasan a ser pie de tabla).
Quitar esa fila corre el `orden_aparicion` de todas las siguientes, y con él su
clave, así que la pasada poda 32 y crea 31. `32 ≠ 1` → error.

### Lo aplicado

`_lineas_podadas_por_expediente` pasa a ser `_movimiento_de_extracciones` y
devuelve `(podadas, creadas)`. La atribución de una BAJADA es ahora:

| Caso | Regla | Gravedad |
|---|---|---|
| `creadas == 0` y `podadas == −diferencia` | poda pura, como hasta hoy | aviso `lineas_bajan_explicado_por_poda` |
| `podadas − creadas == −diferencia` | balance completo de las reextracciones | aviso **`lineas_bajan_explicado_por_reextraccion`** (nuevo) |
| resto | sin explicar | **error** |
| cualquier SUBIDA | ni la poda ni un filtro suman líneas | **error**, sin excepción |

### Demostrado sobre los datos reales

Replay en solo lectura de las auditorías 21560 (antes) y 21567 (después), los
mismos snapshots que produjeron el error:

```
Expediente               dif  podadas  creadas  REGLA VIEJA  REGLA NUEVA
3.21/28510.0052           -3        3        0  aviso (poda) aviso (poda)
6.17/28510.0007           -6        6        0  aviso (poda) aviso (poda)
6.17/28510.0056           -6        6        0  aviso (poda) aviso (poda)
6.17/28510.0123           -3        3        0  aviso (poda) aviso (poda)
6.19/28510.0064           -3        3        0  aviso (poda) aviso (poda)
6.23/28510.0105           -1       32       31  ERROR        aviso (reextracción)
```

Los cinco que ya salían bien no cambian de categoría; `0105` pasa de error a
aviso explicado, que es exactamente lo que pedía el encargo.

Dos tests nuevos, incluido el que fija que una subida sigue siendo error aunque
la reextracción haya creado líneas — la atribución nueva no puede convertirse en
una puerta de atrás.

---

## Bloque 5 — Hoja "Conciliación"

### La pregunta

*"¿Cómo saben que la app ha leído todo lo que hay publicado?"* Hasta hoy el
entregable solo enseñaba lo extraído: un expediente que no aportaba ninguna
línea simplemente no aparecía, indistinguible de uno que el sistema nunca
hubiera visto.

### Qué lista es

Una fila por cada expediente del departamento **28510** que consta publicado en
la Plataforma, aporte líneas o no, de cualquier año, estado y tipo de
procedimiento (el criterio del cliente que ya rige el descubrimiento,
`app.criterio_expediente`).

Un expediente **consta publicado** cuando alguna de las dos vías de
descubrimiento lo encontró — sindicación mensual o búsqueda directa en el
buscador — o cuando se le descargó al menos un documento de la Plataforma, que
es la evidencia más fuerte de las tres. Queda fuera lo que la Plataforma
**confirmó que no tiene** (`sin_publicar`): ahí no hay nada que conciliar, y
meterlo en la lista daría a entender que el sistema se ha dejado algo. La
cuenta, sobre los 611 expedientes del sistema:

```
611 expedientes
├── 590 con 28510 en el código
│   ├── 515 constan publicados  → filas de "Conciliación"
│   └──  75 la Plataforma confirma que no publica
└──  21 de otros departamentos (matrices de pedidos; ninguna aporta filas hoy)
```

Medido: de los 515, **ninguno** llega sin evidencia (513 con documento de la
Plataforma, 124 con fila de sindicación).

### Columnas

`Código de expediente` · `Título` · `Órgano de contratación` · `Estado que
consta publicado en la Plataforma` · `Documentos descargados` · `Documentos
leídos con reconocimiento óptico` · `Líneas que aporta al catálogo` · `Baja y de
dónde sale` · `Situación` · `Motivo`.

El estado se traduce del código CODICE de la sindicación (`PUB` → "En plazo de
presentación", `EV` → "Pendiente de adjudicación", `ADJ` → "Adjudicada", `RES` →
"Resuelta"...); un código que no esté en la tabla se escribe tal cual, nunca se
traduce a ciegas.

**Dos columnas con hueco de origen, dicho en el Resumen:** "Órgano de
contratación" y "Estado que consta publicado" solo existen para los **124** que
ha listado la sindicación mensual, que es la vía que trae esos dos datos. Los
que se conocen solo por el buscador salen con esas dos celdas explicadas: el
buscador devuelve el número de expediente, no su ficha. No es un hueco de
lectura, es lo que publica cada vía.

### Cómo se garantiza el cuadre

La columna de líneas **no se consulta**: `app.exportacion` la va contando
mientras escribe la hoja "Materiales" y se la pasa a `construir_conciliacion`.
Si las dos cifras pudieran discrepar, la hoja dejaría de servir para lo único
que existe. Encima, `comprobar_cuadre` **revienta la exportación** si la suma no
da o si algún expediente se queda sin Situación: nunca sale un Excel
descuadrado, que es justo la clase de dato que esta hoja existe para descartar.

### Recuento por Situación

| Situación | Expedientes |
|---|---:|
| Aporta líneas | **358** |
| Publicado sin cuadro de precios | **56** |
| Los precios están en un acuerdo marco que no está publicado | **49** |
| Documentos escaneados que no se han podido leer | **31** |
| Otro | **19** |
| Pendiente de procesar | **2** |
| **Total** | **515** |

### Comprobaciones duras del encargo

| Requisito | Resultado |
|---|---|
| Todo expediente de "Materiales" aparece en "Conciliación" | **358 de 358** ✅ |
| La suma de líneas es el número de filas de "Materiales" | **18.239 = 18.239** ✅ |
| Ningún expediente sin Situación | **0** ✅ |

### Los 19 de "Otro", uno a uno

Ninguno es un silencio: todos llevan en "Motivo" lo que anotó el sistema.

| Expediente | Qué pasa |
|---|---|
| `2.19/28510.0145`, `3.19/28510.0218`, `3.21/28510.0096`, `3.21/28510.0098`, `3.21/28510.0158`, `3.22/28510.0009`, `3.22/28510.0048`, `3.22/28510.0106`, `6.19/28510.0206`, `6.23/28510.0105`, `6.24/28510.0113` | cobertura parcial: de los N lotes declarados, solo algunos traen baja o importe |
| `3.20/28510.0071` | el Anuncio de adjudicación agrupa 4 lotes en un documento y no se puede atribuir |
| `6.19/28510.0228` | su lote propio (lote 2) no trae baja ni importe en ningún documento |
| `6.19/28510.0230`, `6.25/28510.0219` | bajas declaradas en documentos compartidos con expedientes hermanos, cada uno con su "Contrato nº" |
| `6.20/28510.0002`, `6.20/28510.0003` | su matriz `6.19/28510.0230` tampoco tiene cuadro ni baja |
| `6.23/28510.0074` | el documento declara "EXPEDIENTE PRINCIPAL/ORIGEN" distinto del expediente bajo el que está archivado |
| `6.25/28510.0081` | su matriz `6.25/28510.0028` es multi-lote (6) y el pedido no declara a cuál pertenece |

### Tres códigos con forma inusual

`19/28510`, `28510/2023` y `28510Z/2018` aparecen en la lista. Son expedientes
reales que devolvió el buscador de la Plataforma con su propia numeración, y el
criterio del cliente es el departamento en el código, no su forma. Salen con su
Situación (dos "Publicado sin cuadro de precios", uno "Documentos escaneados").

### De qué fecha es el registro, escrito en el Resumen

Bloque nuevo en la hoja "Resumen", calculado en cada exportación, nunca fijo:

- **Departamento(s) que cubre**: 28510, cualquier año, cualquier estado,
  cualquier tipo de procedimiento.
- **Sindicación mensual**: 25 boletines leídos, de 08/2024 a 09/2026; dato más
  reciente 15/09/2026.
- **Búsqueda directa**: última ejecución 17/09/2026, buscando "28510" en el
  campo "Nº de expediente"; devolvió 368 expedientes.
- **Cobertura**: 515 expedientes publicados en la hoja, más 75 que se buscaron
  uno a uno y la Plataforma confirmó que no publica.

---

## Cierre

### Pruebas

**1.012 pasan** (990 antes, +22). Ninguna saltada.

### Excel

```
C:\dev\ADIF\catalogo_adif_2026-09-18-conciliacion.xlsx
```

Tres hojas: `Materiales` (17 columnas, 18.239 filas), `Conciliación` (10
columnas, 515 filas) y `Resumen`.

### Comparación con `catalogo_adif_2026-09-18.xlsx`

| | 2026-09-18 | hoy |
|---|---:|---:|
| Hojas | Materiales, Resumen | Materiales, **Conciliación**, Resumen |
| Columnas de "Materiales" | 18 | **17** (se va la duplicada) |
| Filas | 18.239 | **18.239** |
| Expedientes con filas | 358 | **358** |
| Materiales distintos (expediente + matrícula + descripción) | 17.269 | **17.269** |

**0 expedientes pierden filas, 0 ganan, 0 materiales desaparecen, 0 aparecen.**
Comparado además como multiconjunto de filas completas ignorando las tres
columnas que esta sesión cambia a propósito: **0 filas solo en el anterior, 0
solo en el nuevo**.

Diferencias fila a fila, todas explicadas:

| Columna | Filas | Por qué |
|---|---:|---|
| Código interno | 1.404 | bloque 2: el interno ajeno se vacía |
| Motivo de las celdas vacías | 1.404 | las mismas filas, con su motivo nuevo |
| Descripción del material | 2 | bloque 3: el intercambio de las filas 813/814, contenido idéntico |
| Nº de expediente (documento) | — | la columna ya no existe (bloque 1) |

### Auditoría

**0 errores, 6 avisos** (antes: 1 error, 7 avisos).

Los seis avisos son los de siempre, ninguno nuevo: 11 grupos de material
repetido con códigos de precio distintos (legítimos, verificados en el PDF),
19.233 huérfanas sin lote, 1.993 precios atípicos, 603 cantidades con forma de
año, 56 grupos de importe de licitación compartido y 8 de importe repetido en el
mismo expediente.

El error que quedaba (`lineas_cambian_sin_cambiar_documentos` sobre
`6.23/28510.0105`) ya no aparece. Nota honesta: en esta ejecución concreta
tampoco habría aparecido sin el arreglo, porque la auditoría compara contra la
ejecución anterior y `0105` lleva dos ejecuciones estable en 35 líneas — por eso
el bloque 4 se demuestra con el replay de los snapshots 21560/21567, que son los
que sí producían el error.

### Pendiente de decisión del cliente

1. **Los 42 internos que siguen repetidos entre expedientes distintos** vienen
   del propio listado de códigos de ADIF, que asigna un `Nº Interno` por familia
   de expedientes. No es algo que este sistema pueda arreglar sin inventar.
2. **"Órgano de contratación" y "Estado publicado" solo para 124 de 515.** Si
   hacen falta para todos, habría que guardar la ficha que muestra el buscador
   de la Plataforma, no solo el número — es una vía de descubrimiento nueva, no
   un arreglo.
3. Siguen en pie de la primera parte de la sesión: "Comentarios" con motivo fila
   a fila o la nota única del Resumen.
