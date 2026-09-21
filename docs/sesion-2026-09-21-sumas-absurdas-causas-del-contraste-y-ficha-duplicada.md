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
