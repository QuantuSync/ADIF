# Sesión 2026-09-21 (tercera parte) — Los valores viejos, las lecturas malas pendientes y las líneas que faltan

Cinco bloques. El registro de la sesión anterior es
`docs/sesion-2026-09-21-sumas-absurdas-causas-del-contraste-y-ficha-duplicada.md`.

---

## Bloque 1 — Valores viejos que un vacío no pisa

### Cómo se hizo

Una base aparte, `adif_reconstruccion`, copia de producción, a la que se le
quitó todo lo extraído (`app.mantenimiento.reconstruccion --vaciar`: líneas,
lotes, trazas, presupuestos por lote, importes y bajas del expediente, lo que
la extracción anota en cada documento) y se le dejaron los documentos, las
cuatro cachés (texto, reconocimiento óptico, mapeo de cabecera, código de
material), los listados de entrada y la sindicación. Un contenedor de la imagen
del worker en una red Docker `--internal` —sin salida a Internet— reconstruyó
el catálogo con el código de producción: **dos pasadas** (22 min cada una, 517
expedientes, `descargas_lanzadas: 0`), más el paso de las unidades del
maestro. La segunda pasada hace falta porque varias reglas solo se activan
sobre el estado que deja la primera (la del lote del título, por ejemplo); la
comparación que vale es la del estado estable. Producción no se tocó hasta
tener la clasificación. Procedimiento repetible en CONTEXTO.md sección 13.

### Qué salió

El Excel reconstruido tiene **exactamente las mismas 19.857 filas** que el de
producción. Diferencias celda a celda en "Materiales":

| Columna | Celdas | Causa | Qué se hizo |
|---|---:|---|---|
| Matrícula | 86 | Valor viejo: la matrícula llegó al lote 3 de `6.25/28510.0237`/`0238` fundiéndose con la fila del mismo código en el **anejo de criterios técnicos del conjunto** (ANEJO p.24, CONTRATO p.113). Desde el 2026-09-14 esa tabla no es de ningún lote —su numeración es propia— y la fila del cuadro del lote (p.18) no trae matrícula | Corregida (vaciada) |
| Matrícula | 5 | Valor viejo: la celda de matrícula de la fila está vacía en el documento (`6.23/28510.0051` P-0009, P-0019, P-0033, P-0409; `6.24/28510.0128` P-001) | Corregida (vaciada) |
| Código de precio | 28 | Valor viejo: el código guardado es la propia matrícula de la fila, el defecto de mapeo conocido (`6.24/28510.0184`, 23; `0173`, 5) | Corregido (vaciado) |
| Cantidad | 7 | Valor viejo: 30.000 en `6.25/28510.0156`; la fila no trae ninguna cantidad ("… \| ALTO \| 16,40 € \| Kg") | Corregida (vaciada) |
| Precio unitario y adjudicado | 3 + 3 | Los **precios de la oferta** (bloque 2): `3.23/28510.0135` lote 6 P-20 y P-21 (27.335,30 y 36.950,25 €), `4.26/28510.0020` lote 1 P-12 (5.335,00 €); el fragmento de la fila tiene la celda de precio vacía | Corregidos (vaciados) |
| Cantidad | 83 | **No es un valor viejo**: `6.26/28510.0016` pp.11-12, "CANTIDAD ESTIMADA" = 1 en cada fila del documento; el código actual ya no la lee en las páginas de continuación y el valor sobrevive porque la línea nueva se funde con la guardada por su firma | No se toca: fallo de lectura del código actual, anotado |
| Unidad de medida | 74 | **No es un valor viejo**: "Ud." / "UD." está en la fila (`4.26/28510.0020`, `6.22/28510.0094`, `0122`, `0155`, `0156`); el código actual no la lee | No se toca, anotado |
| Unidad de medida | 3.222 | La **unidad del maestro** que en producción no se ha vuelto a aplicar desde que se cargó el maestro: es un paso manual (`POST /mantenimiento/maestro-materiales/completar-unidades`) y las líneas nuevas desde entonces no la tienen | No se toca: es una decisión (ver el final) |
| Motivo de las celdas vacías | 3.508 | Consecuencia de las anteriores | — |

Fuera del Excel (líneas sin lote): **428 cantidades** de `6.21/28510.0112`/`0113`
que sí están en su fila ("… \| 13 \| 91.537,95 \| €/UD") y el código actual no
lee (no se tocan), y dos confirmaciones manuales de la cola de revisión (una
matrícula aceptada y un rechazo de candidatos), que no se tocan.

**Cómo se distinguió un valor viejo de un fallo de lectura**: comprobando, fila
a fila y para las 769 celdas, si el valor guardado aparece en alguna celda del
fragmento literal de su propia fila. Si no aparece, es viejo; si aparece, el
documento lo respalda y es el código actual el que no lo lee.

### La corrección

**132 celdas** (91 matrículas, 28 códigos de precio, 7 cantidades, 3 precios y
sus 3 adjudicados), menos de 200, así que se corrigieron sin esperar: un
`UPDATE` por campo, línea a línea por su `id` y comprobando que el valor
guardado seguía siendo el medido (las 129 comprobaciones dieron 129
coincidencias). Copia previa de la base en el contenedor de PostgreSQL,
`/tmp/prod_antes_bloque1_20260921.dump`.

### Lo que queda anotado

- Los tres fallos de lectura del código actual (83 cantidades de
  `6.26/28510.0016`, 212 unidades de cinco expedientes, 428 cantidades de filas
  sin lote de `6.21/28510.0112`/`0113`): el valor guardado es el correcto; si
  algún día se reprocesa desde cero, se perdería. Hay que arreglar la lectura.
- La unidad del maestro pendiente de aplicar en producción (5.786 líneas, 3.222
  celdas de "Materiales").

---

## Bloque 2 — Las 10 lecturas malas pendientes

Ver el cierre para las cifras finales de cada lote.

- **Los 5 lotes de anejos escaneados** (`6.19/28510.0135`, `0175`, `0177`;
  `6.19/28510.0231`, `6.20/28510.0025`). El expediente sabe qué lote de la
  licitación es por el bloque «Nº Lote» de su anuncio cuyo objeto es su título
  —el mismo emparejamiento que ya le daba su presupuesto—; con él, el anejo se
  reparte por los rótulos «LOTE N» del texto leído, por geometría y rótulo, y
  solo si **todas** las filas quedan atribuidas y el anejo cubre todos los lotes
  de la licitación. Cada expediente se queda con su lote; las filas de los
  demás se guardan sin lote, con su motivo. **Ninguno cuadra después**: los
  cinco cuadros son de "cantidad mínima a suministrar por pedido" y "pedido
  inicial" (comprobado en sus cabeceras), así que su causa pasa a "cantidades
  estimadas" con su suma nueva.
  **Decisión tuya en la sesión**: la misma regla alcanzó a dos expedientes
  fuera del encargo, `6.20/28510.0041` (pasa a cuadrar al céntimo, 500.000,00 €,
  y 336 filas de otros lotes salen de "Materiales") y `6.19/28510.0195` (8 filas
  que ya tiene su hermano). Elegiste aplicarla a todos.
- **Los 2 rótulos de lote dentro de una tabla ya aceptada**
  (`3.22/28510.0048` lote 1, `3.23/28510.0135` lote 2). La tabla se parte por
  sus filas de rótulo sin ganar ni perder ninguna. Los dos cuadran al céntimo,
  y con ellos `3.22/28510.0009` lotes 2 y 3 (la pregunta 3 abierta a ADIF: era
  un error de lectura nuestro, no una numeración distinta del documento).
- **`2.23/28510.0138`**: no se puede demostrar. El cuadro del presupuesto no suma
  su propio TOTAL (sus filas dan 33.015,00 €, el TOTAL impreso 32.740,00 €). La
  explicación de ayer ("sobran dos de otra tabla, 440 y 275 €") era inexacta:
  sobra una (440 €); los 275 € son del propio cuadro. Su causa pasa a
  "discrepancia del propio documento".
- **Los 2 precios de oferta**: limpiados en el bloque 1 con el criterio medido.
  `3.23/28510.0135` lote 6 cuadra al céntimo con los precios del anejo;
  `4.26/28510.0020` lote 1 queda con P-12 sin precio ("faltan cantidades"),
  porque la fila del presupuesto del anejo no se lee.

## Bloque 3 — Los 27 lotes a los que les faltan líneas

Toda línea recuperada **solo se queda si con ella el lote cuadra al céntimo
con su presupuesto publicado** (`descartar_recuperadas_que_no_cuadran`). Las
recuperaciones, por su causa medida contra el documento:

| Causa | Lotes | Mecanismo |
|---|---|---|
| Partida alzada que la tabla no lee | `6.20/28510.0094`/`0141` lote 2 (8.987,26 €), `6.20/28510.0131` lote 1 y `6.21/28510.0017` (4.850,00 €), `6.20/28510.0131` lote 2 (2.866,30 €) | Leída del texto de las páginas del lote, la única cuyo importe es lo que le falta (`partida_alzada_del_lote`) |
| La fila que se queda de cabecera | `6.25/28510.0141`/`0186`/`0187` lote 2 (P-1, 661.850,00 €), `6.24/28510.0185` (P-030b, 530,00 €) | Código pegado a la cabecera o con sufijo en minúscula, siempre el anterior al de la primera fila |
| La primera fila de una página de continuación | `2.26/28510.0006` (49.400,00 €), `2.24/28510.0118` (Precintos verdes, 1.350,00 €) | Recompuesta por las columnas de la tabla y demostrada por su aritmética (`fila_sobre_la_tabla`) |
| Referencias sin tres letras seguidas y decimales con punto | `2.23/28510.0098` (4 filas), `6.22/28510.0051`/`0159` (10 filas) | En la tabla demostrada por su aritmética |
| Filas que el cuadro repite | `2.23/28510.0108`, `2.24/28510.0068` | La repetición en la misma tabla y página ya no se funde (`filas_repetidas`) |

**No se recuperan (6)**, cada uno con su razón: `4.19/28510.0212` (su
presupuesto suma 16.680,00 € de mantenimiento que no es ninguna fila, y falta
el cuadro de Granada), `6.20/28510.0042`/`0046`/`0047` lote 2 (su cuadro no
publica cantidades: no puede cuadrar), `6.25/28510.0097` lotes 2 y 3 (páginas
de continuación sin precio).
**No les faltaba ninguna línea (5)**: `6.21/28510.0058`, `0130`, `0135`, `0137`,
`0138` lote 1. Su cuadro suma exactamente 200.000,00 € con la partida alzada
de 20.000,00 € incluida y no trae más filas; el presupuesto publicado es
220.000,00 €. Causa corregida a "discrepancia del propio documento".

## Bloque 4 — Cantidad mínima por pedido y pedido inicial

La Cantidad no cambia. Cada fila de un cuadro que solo trae esas dos columnas
dice, en "Motivo de las celdas vacías" (y en su motivo de revisión), cuál de
las dos es y qué trae la otra. Hallazgo al medirlo: **la premisa "la Cantidad
muestra la mínima por pedido" no se cumple siempre** — en dos cabeceras
cacheadas el mapeo dio la Cantidad al pedido inicial, y en las grifas la
página con cabecera da la mínima y las de continuación, escaneadas, el pedido
inicial. La nota dice en cada fila la que es. Pregunta 16 en
`docs/preguntas-pendientes-cliente.md`.

---

## Bloque 5 — Cierre

### Pruebas, imagen y el único reproceso

- **1.402 pruebas en verde** (1.369 al empezar).
- Imágenes `api` y `worker` reconstruidas con el código final, desde
  `/mnt/c/dev/ADIF`.
- **Antes del reproceso de producción, dos pasadas más en la base aparte** con
  el código nuevo (la tercera y la cuarta) para medir su efecto en todo el
  corpus. Destaparon tres cosas que se arreglaron antes de tocar producción:
  los lotes del reparto tenían que ser todos los que declara la licitación (el
  anuncio de la regulación de tensión solo trae los bloques 4 y 5); el
  presupuesto publicado faltaba en los lotes que crea el reparto del propio
  cuadro (`6.20/28510.0131`); y la fila repetida conservada alternaba entre
  pasadas (84 → 82 → 84 líneas), porque al guardar su gemela la tomaba por su
  duplicado. Y la pregunta sobre el alcance de la regla del bloque 2.
- **Un único reproceso completo de producción** (trabajo 32525, `forzar`,
  sindicación y búsqueda apagadas): 517 expedientes, **22 min 20 s**,
  **`descargas_lanzadas: 0`**, ningún documento fallido. Cuatro expedientes
  consultaron al modelo el código de material de una palabra nueva
  ("R-245…", "Horas…"), la llamada cacheada de siempre.

### Auditoría: 0 errores

La del propio ciclo dio 2 errores: `lineas_cambian_sin_cambiar_documentos` (18
expedientes, los cambios de esta sesión, como siempre que cambia la
extracción) y `lineas_duplicadas_exactas` (2 expedientes: las filas que el
propio cuadro repite y que se conservan). La segunda se corrigió en la
auditoría, que ahora las cuenta como aviso propio
(`lineas_repetidas_por_el_propio_cuadro`). **Repetida: 0 errores, 7 avisos**
(los seis de siempre y el nuevo).

### El entregable, descargado desde la web

`C:\dev\ADIF\catalogo_adif_2026-09-21-valores-viejos-y-lineas-que-faltan.xlsx`,
descargado con Chromium desde `/catalogo` pulsando "Exportar Excel", sin
avisos de error ni errores de consola. **Idéntico a la exportación de la API
salvo `docProps/core.xml`** (fecha de creación). Se descargó dos veces: la
segunda, tras dar a la hoja "Resumen" una categoría propia para las filas del
cuadro de otro lote (la primera las contaba como "ambigüedad de otro tipo");
entre las dos solo cambia esa hoja.

### Comparación con `catalogo_adif_2026-09-21-causas-del-contraste.xlsx`

| | Antes | Ahora |
|---|---:|---:|
| Filas de "Materiales" | 19.857 | **19.333** (−570 +46) |
| Expedientes con filas | 390 | **390, los mismos** |
| "Conciliación" | 19.857 = 19.857 | **19.333 = 19.333** |
| Líneas pendientes de revisión (Resumen) | 6.561 | 7.164 |

**Filas que salen (570)**, todas del bloque 2:

| Expediente | Filas | Por qué | ¿El material sigue en "Materiales"? |
|---|---:|---|---|
| `6.20/28510.0041` | −336 | Es el lote 2 del anuncio; se queda con su cuadro, que suma 500.000,00 €, su presupuesto. **Tu decisión** | No: ningún otro expediente del catálogo es de esos lotes. Siguen en la base, sin lote |
| `6.19/28510.0135`, `0175`, `0177` | −47, −29, −48 | Cada uno se queda con su lote del anejo escaneado de las grifas | Sí, las 124: cada fila está en el expediente de su lote |
| `6.19/28510.0231`, `6.20/28510.0025` | −32, −45 | Lo mismo en el anejo escaneado de la regulación de tensión | Las de los lotes 4 y 5, sí; las 32 de los lotes 1, 2, 3 y 6 no (esos expedientes no están en el catálogo) |
| `3.23/28510.0135` | −22 | Filas de los lotes 1, 3, 4, 5, 7 y 8 de la tabla del anejo; el expediente solo tiene los lotes 2 y 6 | 2 sí, 20 no |
| `3.22/28510.0048` | −2 | La tabla del LOTE 2; el expediente no tiene lote 2 | No |
| `6.19/28510.0195` | −8 | Filas del lote 1; el expediente es el lote 2 | Sí, las 8 |
| `3.22/28510.0009` | −1 | Una fila que pasa del lote 2 a sin lote al leer los rótulos | — |

**Filas que entran (46)**: las recuperaciones del bloque 3 (39 filas en 16
lotes, cada lote cuadrando al céntimo) y 7 filas de `3.22/28510.0009` que
pasan de estar sin lote a su lote (bloque 2).

**Celdas que cambian** en filas que siguen: las 132 del bloque 1 (91
matrículas, 28 códigos de precio, 7 cantidades, 3 precios y sus 3
adjudicados; los dos precios de `3.23/28510.0135` lote 6 pasan además a los
del anejo, 28.549,40 y 39.596,70 €), las filas de `3.22/28510.0009` que cambian
de lote, y 578 celdas de "Motivo de las celdas vacías" (la nota del bloque 4 y
las consecuencias de lo anterior).

### La hoja "Contraste de presupuestos", antes y después

| Resultado | Antes | Después |
|---|---:|---:|
| Cuadra al céntimo | 249 | **271** |
| Cuadra con diferencia menor del 0,01 % | 13 | 13 |
| No cuadra: lectura del catálogo pendiente de corregir | 10 | **0** |
| No cuadra: el presupuesto publicado es otra cifra | 0 | 0 |
| No cuadra: cantidades estimadas, el presupuesto es un máximo | 80 | 84 |
| No cuadra: faltan líneas del lote en el catálogo | 27 | **6** |
| No cuadra: el presupuesto incluye partidas que el cuadro no trae | 2 | 2 |
| No cuadra: discrepancia del propio documento | 6 | 11 |
| No cuadra: causa sin determinar | 0 | 0 |
| No se puede cerrar: faltan cantidades | 98 | 99 |
| **Total** | 485 | 486 |

Los +22 de "Cuadra al céntimo": 16 del bloque 3, 3 del bloque 2 del encargo
(`3.22/28510.0048` lote 1, `3.23/28510.0135` lotes 2 y 6) y 3 que el bloque 2
arregla de paso (`3.22/28510.0009` lotes 2 y 3, `6.20/28510.0041`). El total
sube a 486 porque el lote 3 de `3.22/28510.0009` pasa a tener filas.

**De los 10 del bloque 2 cuadran 3**; no cuadran los 5 escaneados (cuadros de
"cantidad mínima por pedido"), `2.23/28510.0138` (el documento no suma su
propio TOTAL) y `4.26/28510.0020` lote 1 (P-12 se queda sin precio al quitar
el de la oferta). **De los 27 del bloque 3 cuadran 16.**

### La web da las mismas cifras que el Excel

Leído con Chromium: `/conciliacion`, 534 filas, 0 que no coincidan en líneas
con la hoja; `/contraste-presupuestos`, 486 filas, 0 que no coincidan en
resultado, y los once botones con el recuento del Excel (271 / 13 / 0 / 0 / 84
/ 6 / 2 / 11 / 0 / 99). Ningún aviso de error ni error de consola.

## Decisiones que no se han tomado aquí

1. **La unidad del maestro pendiente de aplicar**: 5.786 líneas con matrícula
   del maestro sin unidad, 3.222 celdas de "Materiales". Es el paso manual
   `completar-unidades`; no se ha lanzado.
2. **Los tres fallos de lectura del código actual** que el bloque 1 destapó (el
   valor guardado es el bueno y se ha dejado): 83 cantidades de
   `6.26/28510.0016` pp.11-12, 212 unidades en cinco expedientes y 428
   cantidades de filas sin lote de `6.21/28510.0112`/`0113`. Arreglar la
   lectura cambiaría datos.
3. **Siete filas de `6.19/28510.0177` sin la nota del bloque 4** (su tabla
   empieza en una fila con dos matrículas en la misma celda); necesita un
   reproceso.
4. **Los materiales que salen de "Materiales" sin estar en otro expediente**:
   336 de `6.20/28510.0041`, 32 de la regulación de tensión, 20 de
   `3.23/28510.0135` y 2 de `3.22/28510.0048`. Siguen en la base; saldrían el
   día que se den de alta los expedientes de esos lotes.
5. **La pregunta 16** (qué cantidad mostrar en esos cuadros) y la **pregunta 3**
   que queda (`3.21/28510.0096`).
