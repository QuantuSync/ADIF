# Sesión 2026-09-21 (segunda parte) — Las sumas absurdas, las causas de lo que no cuadra y la ficha duplicada

El contraste de presupuestos de la primera parte
(`docs/sesion-2026-09-21-contraste-de-presupuestos-en-ejecucion-y-clasificacion.md`)
destapó problemas del catálogo. El Excel de esa sesión no se entrega hasta
resolverlos. Cuatro bloques.

---

## Bloque 1 — Las 3 sumas absurdas

### Qué líneas las producen

| Lote | Suma | Línea que la produce | Qué pone el documento |
|---|---:|---|---|
| `6.25/28510.0019` y `0041`, lote 3 | 13.457.044.000,00 € | P-323, "Partida alzada a justificar para imprevistos": cantidad **116.000** × precio **116.000,00** | Un solo importe, `116.000,00 €`, en la columna de precio (CONTRATO_2.pdf p.118; ANEJO_1.pdf p.26) |
| `6.24/28510.0188`, lote 1 | 507.926.862,96 € | P-002, la misma partida alzada: cantidad **22.532,4** × precio **22.532,40** | Un solo importe, `22.532,40 €` (ANEJO_1.pdf p.11) |
| `6.20/28510.0042`/`0046`/`0047`, lote 1 | 863.821.702.015,56 € | 14 filas por expediente con cantidad **33.601.014**, **33.601.013** o **33.611.302** | La columna **E.T.** (especificación técnica) de la fila: `03.360.101.4`, `03.360.101.3`, `03.361.130.2`. El cuadro no tiene columna de cantidad en esa página (ANEJO_3.pdf p.27) |

Las cuatro se miraron sobre la imagen de la página, no solo sobre el texto
extraído.

**La sospecha del encargo se confirma en parte.** No había años ni
matrículas. Sí había **códigos** (la referencia E.T.) e **importes totales
leídos como cantidad**, y no como precio unitario.

### Dos defectos distintos

**A. Una referencia E.T. que ya no se lee como cantidad, pero cuyo valor viejo
seguía guardado.** Desde el 2026-09-10, `parsear_numero_es` rechaza
`03.360.101.4` (agrupación de miles no válida). Se comprobó ejecutando la
extracción actual sobre el documento, sin guardar nada: las 14 filas salen hoy
con **cantidad vacía**. Los 33.601.014 los escribió una pasada anterior a ese
arreglo, y **un `None` no pisa un valor ya guardado** (CONTEXTO.md sección 9).
Es el mismo remedio que ya hubo que aplicar el 2026-09-07 y el 2026-09-19
(tercera parte): limpiar esas celdas en la base de datos. Medido en todo el
catálogo: **42 celdas, las 14 de cada uno de los tres expedientes, y ninguna
más** (cantidad igual a un código con puntos de su propia fila, leído sin los
puntos).

**B. El importe de una partida alzada tomado como cantidad, en código hoy.**
La fila de la partida alzada trae un solo importe, y la recuperación de
columna fantasma lo alcanzaba dos veces: como cantidad y como precio. El código
ya decía que "una cantidad nunca lleva el símbolo de euro", pero solo para la
columna mapeada, no para la recuperación. **Arreglado** en
`app.catalogo._construir_campos`: la cantidad recuperada de una columna
fantasma no puede traer `€`, y si la fila no tiene precio, ese importe **es**
su precio (la misma regla que la rama que ya existía). En todo el catálogo son
**7 líneas**: las 3 de arriba y **4 más que nadie había señalado**. Estas 4
salían con el importe en la cantidad **y sin precio**: la partida de repuestos
de `6.20/28510.0096` lotes 1 y 2 y de `6.21/28510.0002` y `0003` (42.948,65 € y
4.492,78 €). Sus cantidades viejas también se limpiaron, por la misma razón que
en A.

Las 49 celdas (42 + 7) se eligieron con los dos criterios de arriba, sin
lista a mano. Antes de aplicar se contaron: 49, exactamente las medidas. Se
reprocesaron **solo los 9 expedientes afectados**.

### La prueba: los lotes cuadran al céntimo

| Lote | Antes | Después |
|---|---|---|
| `6.25/28510.0019` lote 3 | 13.457.044.000,00 €, No cuadra | **1.160.000,00 €, Cuadra al céntimo** |
| `6.25/28510.0041` lote 3 | 13.457.044.000,00 €, No cuadra | **1.160.000,00 €, Cuadra al céntimo** |
| `6.24/28510.0188` lote 1 | 507.926.862,96 €, No cuadra | **240.345,60 €, Cuadra al céntimo** |
| `6.20/28510.0096` lote 1 | faltaba el precio de la partida | **45.000,00 €, Cuadra al céntimo** |
| `6.21/28510.0002` lote 1 | faltaba el precio de la partida | **45.000,00 €, Cuadra al céntimo** |
| `6.20/28510.0042`/`0046`/`0047` lote 1 | 863.821.702.015,56 € | 3.815.877,27 €, sigue en "faltan cantidades" |

Un matiz del encargo: el lote 1 del trío **sí tenía presupuesto** en la hoja
del 21/09 (4.500.000 €, PLIEGO_1.pdf p.4). No salía como "No cuadra" porque
1.258 de sus 1.293 filas no tienen cantidad, así que la suma absurda nunca
llegó a compararse. Ahora le faltan cantidades a 1.272 filas: las 1.258 de
antes más las 14 limpiadas. Es lo correcto, porque el documento deja esa
columna en blanco ("Cantidad estimada de referencia", sesión 2026-09-19,
tercera parte).

### Las 941 cantidades con forma de año, revisadas

La cifra de 941 es de toda la base de datos. **631 llegan a "Materiales"**; las
otras 310 no salen en el entregable. Las 631 se han revisado contra su propia
fila, a la luz de los dos defectos de arriba:

| | Líneas |
|---|---:|
| La cifra es **su propia celda**, limpia (sin `€`, sin puntos de código) | **595** |
| Cable de 2.000 m (y 1 de 1.990 m) cuyo fragmento es el del anejo de criterios, que no tiene columna de cantidad | 36 |

Las 36 **se localizaron en el cuadro de precios de su propio expediente**, con
el mismo código de precio y la cantidad impresa en la fila: por ejemplo,
`6.24/28510.0064` P-017, "TIPO CCPSSP CON FR 0.3 (Fca) 2000 5,26 €", o
`6.25/28510.0201` P-104, "650650090 M 1990". **Ninguna es un año, un código ni
un importe.** Se dieron por reales el 18/09 y lo siguen siendo.

---

## Bloque 2 — Los 139 lotes que no cuadran

### Primero se midió: la clasificación

Cada lote se comprobó contra su documento: la suma del catálogo, el presupuesto
publicado, el total que el propio cuadro declara cuando lo declara, la
diferencia buscada como cifra impresa en el documento, la suma comparada con
los presupuestos de los otros lotes y, donde hizo falta, fila a fila. Los 136
que quedaban tras el bloque 1 son **81 familias** (expedientes que comparten
documentos y dan la misma suma).

| Causa | Lotes | Ejemplo |
|---|---:|---|
| **Lectura mala del catálogo** | **24** | `6.21/28510.0058` lote 7: la tabla del lote 8 lleva el rótulo "LLOTE 8" y heredaba el lote 7; 1.353.000 € = 143.000 del 7 + 1.210.000 del 8 |
| Presupuesto comparado contra la cifra equivocada (IVA, gastos generales, beneficio) | **0** | Ningún lote cae en un factor 1,21, 1,15, 1,19 ni sus combinaciones |
| **Cantidades estimadas: el presupuesto es un máximo** | **80** | `6.23/28510.0034`: "CANTIDAD REFERENCIA ESTIMADA" = 1 por referencia, la suma es 54,35 € de 400.000 € |
| **Faltan líneas del lote en el catálogo** | **27** | `6.20/28510.0094` lote 2: falta la partida alzada de 8.987,26 € (CONTRATO_2.pdf p.105), exactamente la diferencia |
| **El presupuesto incluye partidas que el cuadro no trae** | **2** | `6.24/28510.0067`: 150.000,77 € = 100.050,24 € de suministro (la suma) + 49.950,53 € de reparaciones |
| **Discrepancia del propio documento** | **6** | Los cinco lotes 3 de las traviesas (comprobados el 18/09) y `3.22/28510.0009` lote 2, cuyo cuadro numera los lotes distinto que la adjudicación |
| **Total** | **139** | |

Las lecturas malas son 24, **menos de 30**, así que se arreglaron las
demostradas y se siguió sin parar, como decía el encargo.

### Las lecturas malas: 14 arregladas, 10 pendientes

**Arregladas (14 lotes)**, todas demostradas porque el lote pasa a cuadrar al
céntimo:

| Lotes | Qué pasaba | Arreglo |
|---|---|---|
| 3 (bloque 1) | La E.T. y el importe de la partida alzada leídos como cantidad | Bloque 1 |
| 9 (`6.21/28510.0058`, `0135`-`0138`, lotes 3 y 7) | La negrita simulada duplica la "L" de la cabecera que va encima de la tabla ("LLOTE 4", "LLOTE 8") y la tabla heredaba el lote de la página anterior | `app.extraccion.lote_tabla._LOTE_CABECERA_RE` acepta la "L" doble, igual que ya la aceptaba el texto entre tablas |
| 2 (`6.24/28510.0171`, `6.25/28510.0203`) | Cuadro con dos columnas de cantidad: "CANTIDADES A INCLUIR OBLIGATORIAMENTE EN EL PEDIDO INICIAL" y "CANTIDADES ESTIMADAS DE REFERENCIA". La extracción parte la palabra ("CANTIDADE S ESTIMADAS") y el mapeo daba la cantidad a la obligatoria. Con la estimada: 2.340.000,00 € y 1.725.000,00 €, los presupuestos exactos | `app.extraccion.mapeo_cabecera.corregir_cantidad_obligatoria_por_estimada`, sobre el mapeo final venga de donde venga. De las 28 cabeceras cacheadas con las dos columnas, 3 estaban mal, las 3 deterministas |

**La decisión que hubo que pedir.** Arreglar "LLOTE" deja las tablas de los
lotes 4 y 8 sin lote: ninguno de los cinco expedientes tiene esos lotes en el
sistema (aunque el título de `6.21/28510.0137` diga "Lote 8. Sujeciones", la
pregunta que ya tiene ADIF). Eso saca de "Materiales" 42 filas por
expediente, que siguen en la base de datos, pendientes y con su motivo.
Chocaba con "ningún material puede desaparecer", y se preguntó: **el cliente
eligió mantener el arreglo.**

**Pendientes (10 lotes)**, cada uno con su causa en la hoja:

| Lotes | Qué pasa | Por qué no se ha arreglado |
|---|---|---|
| `6.19/28510.0135`, `0175`, `0177` (grifas) y `6.20/28510.0025`, `6.19/28510.0231` (5) | El anejo escaneado trae los cuadros de todos los lotes (LOTE 1 en la p.15, LOTE 2 en la 19, LOTE 3 en la 21) y cada expediente los tiene todos como un único lote | El reparto por lotes de las tablas leídas por reconocimiento óptico no existe: es un mecanismo nuevo |
| `3.22/28510.0048` lote 1, `3.23/28510.0135` lote 2 (2) | Los rótulos "LOTE N –" son filas dentro de la misma tabla; la tabla se acepta por sus códigos de precio, y la partición por rótulos solo se prueba con las tablas que no se aceptan | Extender la partición a tablas ya aceptadas es un cambio de todo el corpus, y su propio docstring dice que nunca debe poder quitar filas que ya salen. Las sumas lo demuestran: 12.900 + 68.400 €; P-6 a P-8 = 8.545,90 € |
| `3.23/28510.0135` lote 6, `4.26/28510.0020` lote 1 (2) | Precio de la **oferta** del adjudicatario ("ANEJO Nº 1 Bis. JUSTIFICACIÓN DE LA PROPOSICIÓN ECONÓMICA PRESENTADA", que cierra con "TOTAL OFERTADO (SIN IVA)") leído como precio de licitación | La regla nueva (abajo) ya no lo escribe, pero el valor guardado se queda: la fila de licitación no se lee en esas dos filas, y un `None` no pisa. No se ha escrito ningún precio a mano |
| `2.23/28510.0138` (1) | Faltan dos filas del cuadro y sobran dos de otra tabla (+75,00 €) | Filas de otra tabla mezcladas: sin arreglo acotado |

**La oferta del adjudicatario, excluida por regla**
(`app.extraccion.pipeline_anejo.paginas_de_la_oferta`): desde el título hasta
su "TOTAL OFERTADO (SIN IVA)", como mucho 5 páginas, una fila **con precio**
no entra. La fila sin precio (el modelo en blanco) sigue como hasta ahora:
`3.24/28510.0063` no tiene otras líneas. Medido: 17 documentos. Efecto en
este reproceso: 23 filas sin lote de `3.23/28510.0135`, basura de la oferta,
salen de la base de datos; ninguna de "Materiales".

### El reproceso de verificación

Solo los afectados: **178 expedientes** (12 con "LLOTE", 159 con las dos
columnas de cantidad —el criterio es amplio a propósito—, 12 con la oferta).
Antes y después, línea a línea:

| Expedientes | Cambio |
|---|---|
| `6.21/28510.0058`, `0135`, `0137`, `0138` | 42 filas por expediente pasan de los lotes 3/7 a sin lote (la decisión de arriba) |
| `6.21/28510.0136` | 37 filas del lote 7 pasan a sin lote |
| `6.21/28510.0130` | 37 filas nuevas sin lote (la tabla del lote 8, que antes no guardaba) |
| `6.24/28510.0171` | 6 cantidades: 26/0/0/0/6/0 → 125/72/72/62/70/48 |
| `6.25/28510.0203` | 2 cantidades: 200/50 → 600/200 |
| `6.25/28510.0218` lote 3 | 3 cantidades de 10 a vacía: otra tabla del documento da la estimada, distinta de la "cantidad mínima" (10), y la guarda de choques de siempre deja la celda vacía con su motivo |
| `3.23/28510.0135`, `6.22/28510.0146` | 23 y 3 filas sin lote que salen (ninguna en "Materiales") |

Ningún otro de los 178 cambia una sola celda.

### Cada fila de la hoja lleva su causa

"No cuadra" a secas desaparece. La hoja, la API y la web tienen siete
resultados de "No cuadra", uno por causa, y **una explicación de una línea**
con la cifra que la demuestra. La causa está escrita en
`app.contraste_presupuestos._CAUSAS_COMPROBADAS`, con la misma regla que ya
tenía el texto de los lotes comprobados a mano: **solo se escribe si la suma y
el presupuesto son los que se comprobaron**; si cambia cualquiera, la fila pasa
a "causa sin determinar". Además, un lote con filas que no salen en
"Materiales" dice "faltan líneas" sin necesidad de estar en la lista: es un
hecho de los datos.

| Resultado | Antes (21/09, primera parte) | Ahora |
|---|---:|---:|
| Cuadra al céntimo | 233 | **249** |
| Cuadra con diferencia menor del 0,01 % | 13 | 13 |
| No cuadra | 139 | — |
| No cuadra: lectura del catálogo pendiente de corregir | — | **10** |
| No cuadra: el presupuesto publicado es otra cifra | — | **0** |
| No cuadra: cantidades estimadas, el presupuesto es un máximo | — | **80** |
| No cuadra: faltan líneas del lote en el catálogo | — | **27** |
| No cuadra: el presupuesto incluye partidas que el cuadro no trae | — | **2** |
| No cuadra: discrepancia del propio documento | — | **6** |
| No cuadra: causa sin determinar | — | **0** |
| No se puede cerrar: faltan cantidades | 100 | **98** |
| **Total contrastados** | 485 | 485 |

Los +16 de "Cuadra al céntimo" son los 14 arreglos y los dos lotes que el
bloque 1 cerró sin estar en la lista (`6.20/28510.0096` y `6.21/28510.0002`,
lote 1, que pasan de "faltan cantidades" a cuadrar).

El significado de cada resultado vive en un solo sitio
(`app.contraste_presupuestos.SIGNIFICADO`): lo escribe la hoja debajo del
recuento, lo devuelve la API y lo pinta la pantalla `/contraste-presupuestos`
(en cada botón y en "Qué significa cada resultado"). El diccionario del Excel
lo recoge.

---

## Bloque 3 — La ficha duplicada de `6.25/28510.5001/01`

Las dos fichas, antes de unificar:

| Campo | `6.25/28510.5001/01` (id 375) | `6.25/28510.5001_01` (id 45) |
|---|---|---|
| Título | Suministro de repuestos de equipos de engrasadores de pestaña… | — |
| Código interno | 24037 (cruza por su fila propia) | — (no cruza) |
| Estado del contrato (SAP) | En ejecución | — |
| En ejecución según ADIF | Sí, acta de 26/03/2025 (listado del 21/09) | — |
| Estado | `sin_publicar` | `sin_publicar` |
| Última búsqueda sin resultado | 18/09 13:27:34 | 18/09 13:28:06 |
| Alta | **07/09/2026** | **03/09/2026** |
| Lotes | ninguno | 1 (el "1" del sistema, vacío) |
| Trabajos de cola | 5 | 9 (6 extracciones del 03/09 y 3 búsquedas) |
| Líneas, documentos, trazas | ninguna | ninguna |

**De dónde sale la del guion bajo.** No está en ningún fichero de entrada. Se
dio de alta el 03/09 desde un nombre de carpeta (`6.25_28510.5001_01`) al que
solo se le devolvió la primera barra. La regla de carpetas de hoy
(`app.ingesta_local._CARPETA_EXPEDIENTE_RE`) ya no admite ese nombre, así que
no hay ninguna vía que la vuelva a crear.

**Cómo se unificó.** Con la forma de la barra, la del listado de ADIF, y con
una función nueva y probada, `app.extraccion.identidad_expediente.
unificar_ficha_duplicada`. Cada campo que la de la barra no tiene lo toma de
la otra, y la fecha de alta es la más antigua de las dos. Los enlaces a
documentos y las trazas pasan si no los tiene ya, y el resto (lotes, líneas,
trabajos, sindicación, pedidos) lo mueve `fusionar_en`, la de la sesión
2026-09-19. Resultado: **una ficha**, `6.25/28510.5001/01`, con alta del
03/09, su lote y los 14 trabajos de cola. Después **ninguna fila de ninguna
tabla** apunta a la ficha borrada. Solo se ha perdido una cifra redundante: la
hora de la búsqueda sin resultado de la forma con guion bajo (13:28:06),
32 segundos después de la de la barra. Queda escrita arriba.

**Un defecto al hacerlo, corregido.** El primer intento falló sin guardar
nada. `fusionar_en` mueve los lotes por atributo, y al borrar el duplicado la
relación `Expediente.lotes`, ya cargada, les ponía `expediente_id` a NULL. La
función nueva los mueve con un UPDATE.
