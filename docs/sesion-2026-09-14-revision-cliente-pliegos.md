# Sesión 2026-09-14 — revisión del cliente sobre el Excel: código del material y matrículas

El cliente revisó el Excel del viernes y facilitó tres pliegos
(`Ejemplo/revision_alvaro/Adif 1.pdf`, `Adif 2.PDF`, `Adif 3.pdf`) con dos
observaciones textuales:

1. Sobre el primero: "Aquí puedes encontrar un pliego en el que ya existe la
   columna del tipo de material (Código del material para nuestro Excel).
   Creo que el código ha cogido más la columna de Repuesto que la columna de
   tipo."
2. Sobre los otros: "Con respecto a las matrículas. Hay muchas que no
   están, sí, pero hay otras que sí que están. En este primer pliego puedes
   verlo, en el segundo hay cosas que no me cuadran con el Excel, échale un
   ojo."

Resumen ejecutivo en `CONTEXTO.md` sección 16; aquí el detalle, las cifras
y la verificación contra el documento.

---

## Bloque 1 — Identificación de los tres documentos

Ninguno de los tres trae el número de expediente escrito: son pliegos
técnicos ("Criterios técnicos..." / "Pliego de prescripciones técnicas..."),
no documentos administrativos. Identificados por el código seguro de
verificación (CSV) de la banda lateral y por contenido, comparados página a
página contra los documentos ya descargados.

| Fichero del cliente | Qué es | Documento del sistema | Expedientes |
|---|---|---|---|
| `Adif 1.pdf` (46 pp., escaneado, sin capa de texto) | Criterios técnicos para el suministro de repuestos de aparatos de vía ancho estándar, 5 lotes (mayo 2021), CSV `PT44JV7HF6BFJT3ZWM3HW38E54` | `ANEJO_7bfc92005f43e68e.pdf` (id 588), mismo CSV; también reproducido dentro de los dos CONTRATO de la familia (582/583) | `6.21/28510.0108` (matriz) y `0109`-`0113` (sus 5 lotes) |
| `Adif 2.PDF` (22 pp., con texto) | Pliego de prescripciones técnicas + Anejo 1 de criterios técnicos, tornillería, material auxiliar y anclajes de seguridad, 2 lotes (nov. 2020) | `ANEJO_e40fc4e4546ec90b.pdf` (id 495) — **mismo fichero, mismo hash SHA-256** | `6.21/28510.0015` (lote 1), `6.21/28510.0016` (lote 2), `6.20/28510.0115` |
| `Adif 3.pdf` (22 pp., escaneado en grises) | **El mismo documento que `Adif 2`**, impreso/escaneado: mismos CSV en cada página y contenido idéntico página a página (verificado a ojo en pp. 1, 11, 13, 16 y 20) | id 495 | los mismos tres |

Los tres expedientes ya estaban procesados, todos en `pendiente_revision`.
"El primer pliego" y "el segundo" de la observación 2 son, por tanto, dos
copias del mismo documento.

---

## Bloque 2 — Código del material (Adif 1)

**La columna.** El pliego no tiene ninguna columna llamada "tipo de
material". Trae "TIPOLOGÍA APARATO" (tipo de desvío: "17.000", "GAV 1500",
"Tipo G 500", "Doble diagonal...") y "REPUESTO" (tipo de pieza:
"Semicambio", "Aguja", "Contraaguja", "Cruzamiento", "Contracarril",
"Cruzamiento obtuso"...).

**Lo que hacía el sistema.** No leía ninguna de las dos: el "Código del
material" se derivaba siempre del sustantivo principal de la descripción
(CONTEXTO.md sección 6). Por eso coincidía con REPUESTO casi siempre — la
descripción empieza por la misma palabra. Comparación fila a fila, antes
del arreglo, sobre las 148 filas con código "P-NN" del documento:

- 59 estaban en el catálogo; **89 no estaban** (bloque 4).
- De las 40 con REPUESTO que sí estaban, 35 coincidían con REPUESTO y 5 no:
  P-69/P-70 ("CORAZÓN" frente a "Cruzamiento") y P-130/P-133/P-136
  ("CRUZAMIENTO" frente a "Cruzamiento obtuso").
- Las 19 de la tabla de la p.34 no traen ninguna de las dos columnas.

**Decisión del cliente (vía Lucas):** REPUESTO es el Código del material.
Encaja con lo que el cliente entiende por ese campo y con el Excel de
referencia (sustantivos genéricos: BRIDA, PLACA, SUPLEMENTO).

**Implementado:** `app.extraccion.mapeo_cabecera.intentar_mapeo_determinista`
reconoce una columna cuyo nombre es exactamente "REPUESTO" (nunca
"contiene": "PRECIO DEL REPUESTO" no es esta columna) y la añade al mapeo
como campo opcional `codigo_material`, fuera del esquema del modelo (el
modelo ni la ve ni la devuelve: cambiar su esquema invalidaría todas las
respuestas cacheadas sin beneficio). `app.catalogo._codigo_material_de_
columna` toma su valor literal en mayúsculas; celda vacía → derivación por
descripción de siempre. Las 4 entradas de `cache_mapeo_cabecera` con esa
cabecera (129-132) se borraron para que el determinista las recalculara con
la columna nueva.

**Cuántos expedientes tienen el patrón.** Buscado en el texto de todo el
corpus (no solo en las cabeceras ya cacheadas, que solo cubren páginas que
se abrieron): solo la familia `6.21/28510.0108` — la matriz y sus 5 lotes,
en el anejo 588 y en los dos CONTRATO que lo reproducen. Los otros dos
candidatos del barrido eran falsos positivos (un "repuesto" en prosa de un
anuncio PCSP; "TIPO DE TRAVIESA" de `6.24/28510.0094`, composición del
material sin columna de descripción).

---

## Bloque 3 — Matrículas (Adif 2 / Adif 3)

Documento 495, verificado contra el propio PDF (tablas con `pdfplumber` y
cotejo visual con la copia escaneada): **103 matrículas**, 78 del Lote 1
(pp. 13-18) y 25 del Lote 2 (pp. 19-20), más una partida alzada por lote.

En el catálogo, antes del arreglo, para cada uno de los tres expedientes:

| | Nº |
|---|---|
| Matrículas del documento | 103 |
| Matrículas en el campo `matricula` del catálogo | **0** |
| Coinciden | 0 |
| Están en el catálogo pero en el campo equivocado (`codigo_precio`) | 34 |
| No están en el catálogo en absoluto | 69 |
| En el catálogo y no en el documento | 0 |

**No era límite de origen: eran tres fallos nuestros, encadenados.**

1. **La cabecera de la tabla está en una fuente sin mapa Unicode**:
   `pdfplumber` devuelve "(cid:69)(cid:465)(cid:3)(cid:68)..." en vez de
   "Nº MATRÍCULA", "REF. ADIF", "PLANO DE REFERENCIA"... El localizador no
   veía ningún marcador en la p.13 y **no abría ni esa página ni las cuatro
   de continuación** (pp. 14-17): 69 materiales del Lote 1 nunca se leyeron.
   La p.18 sí entraba, solo porque la tabla de la partida alzada que trae
   debajo tiene cabecera legible.
2. **Esa cabecera ilegible se mandó al modelo**, que puso `codigo_precio` en
   la columna de la matrícula y `matricula` en "REF. ADIF" ("RT58",
   "Pa1"...), y el mapeo quedó cacheado (`cache_mapeo_cabecera` 103, 104).
   `corregir_confusion_matricula_codigo_precio` no lo corregía porque la
   columna "REF. ADIF" no está vacía.
3. El plano de referencia ("03PAI-032-01") acababa en `unidad_medida`.

Además, en esta tabla una matrícula viene escrita con puntos
("643.910.630") y las partidas alzadas ocupan menos columnas (su importe
cae en la de cantidad).

---

## Bloque 4 — Páginas de continuación que nunca se abrían (hallazgo de paso)

Comparando el anejo 588 fila a fila salió un fallo más grande que los dos
del encargo: **el localizador descartaba las páginas de continuación de
tablas con descripciones largas**. Una página que continúa una tabla sin
repetir la cabecera solo se aceptaba con densidad numérica ≥ 0,20; las
descripciones de repuestos de aparatos de vía (20-40 líneas de prosa
técnica por fila) dejan esas páginas en 0,10-0,20. Medido sobre la caché de
texto de todo el corpus: **246 páginas con filas reales en 30 documentos, 46
expedientes**. En el anejo 588 se perdían 89 de 148 filas; en el cuadro de
precios real de la misma familia (586), 26 páginas.

Dos defectos más, en las mismas páginas una vez abiertas:

- **Códigos con sufijo de variante** ("P-39B", "P-41 A": aguja y
  contraaguja del mismo desvío). `app.extraccion.tabla` no los reconocía
  como fila de datos y descartaba la tabla entera como espuria (pp. 15-22
  del 588). Solo se acepta la mayúscula: una minúscula pegada es el sello
  CSV invertido ("P-13\np").
- **El sello CSV comparte celda con el código** ("P-43 A\npsj", "fireV\nP-46
  A"): la recuperación de ruido existente trabajaba sobre la celda sin
  espacios y se comía el sufijo — P-43, P-43 A y P-43 B se fundían en una
  línea. Ahora se intenta primero sobre la celda cruda.

**Riesgo encontrado al abrir más páginas, y guarda añadida.** Un documento
compartido por expedientes de un solo lote puede traer los cuadros de todos
los lotes (`6.19/28510.0025_ANEJO_02234c396aba465d.pdf`, balasto, 14
expedientes: un "PRESUPUESTO ... LOTE N" por lote, "P-2" a 1,80 € en uno y
6,60 € en otro). Sin lotes que separar, todas esas tablas caen en el único
lote del expediente y `_combinar_por_clave` se quedaba con la última, sin
avisar. Ahora, mismo código de precio + mismo lote + mismo documento con
precios o cantidades distintos → el valor queda vacío (`INVALIDADO`, borra
también el "último gana" guardado antes) y la línea lleva un motivo
explícito. Saber qué lote del documento corresponde a cada expediente sigue
siendo el pendiente ya conocido de identidad de lote (CONTEXTO.md sección
16), no se resuelve aquí.

**La guarda, verificada contra los documentos antes de darla por buena**
(primer reproceso completo): cuatro formas reales de choque, revisadas una
a una en el PDF.

- `6.24/28510.0088` (P-008..P-012): "LOTE 1" (700 ud) y "LOTE 2" (650 ud)
  del mismo anejo, mismo precio, en un expediente registrado con un solo
  lote (el pendiente conocido "separar 0088 en expedientes de lote reales").
  Antes el catálogo se quedaba con la cantidad del último lote visto.
- `6.24/28510.0203` lote 6: el cuadro del lote 6 (2.500 ud) y la tabla de
  criterios técnicos del mismo anejo (sin mención de lote, heredada), cuya
  columna "CANTIDAD" vale 50 para todo. Antes se guardaba 50.
- `6.23/28510.0051`/`0060`: el desfase de fila ya conocido de ese anejo
  (P-0994 es "ENF-54 Curva" en la p.49 y "DSFH-C1-54..." en la p.95). Antes
  se guardaba el precio de la tabla desalineada.
- **Excepción necesaria:** `6.23/28510.0051_ANEJO_3` es una **nota de
  subsanación** ("Donde aparece: 62.171,96 € … Debiendo ser: 136.315,00
  €"). Ahí "el último gana" acertaba, y la guarda habría vaciado el precio
  corregido de 6 partidas. `app.extraccion.pipeline_anejo` reconoce ahora
  una nota de subsanación (las dos redacciones reales del corpus: "donde
  aparece / debiendo ser" y "donde dice / debe decir", en las primeras
  páginas; 4 documentos de 1-2 páginas en todo el corpus) y se queda solo
  con la última aparición de cada código, la corrección.

---

## Bloque 5 — Arreglos

Todos en la cascada de siempre, sin tocar ningún documento:

| Módulo | Cambio |
|---|---|
| `app/extraccion/localizador.py` | Continuación: basta con un identificador de fila (código P-NN con o sin sufijo, COD, L-T, matrícula) si la página anterior es candidata; la densidad deja de ser requisito. Arranque sin cabecera legible: ≥ 3 líneas con identificador e importe. |
| `app/extraccion/tabla.py` | Sufijo de variante en mayúscula; celda de cabecera ilegible (`(cid:NN)` sin ninguna palabra legible) → `None`, así la cabecera entera cuenta como "sin señal": nunca va al modelo ni se cachea. Geometría de columnas (`columnas_x`) en cada tabla. |
| `app/extraccion/mapeo_cabecera.py` | `heredar_mapeo_por_geometria`: una tabla sin cabecera cuyas columnas caen en las mismas posiciones que la última tabla con cabecera del mismo documento hereda su mapeo, validado contra sus filas. Columna REPUESTO → `codigo_material`. Cuarta variante de la confusión matrícula/código (columna "matrícula" sin ningún valor con forma de matrícula). |
| `app/extraccion/pipeline_anejo.py` | Usa la herencia geométrica antes que la derivación por contenido y el modelo. La marca "este mapeo corrigió una confusión matrícula/código" viaja con el mapeo cuando otra tabla lo reutiliza (caché estructural o geometría): sin ella, en la p.20 del doc 495 el `codigo_precio` viejo (la matrícula) sobrevivía al reproceso en 12 líneas — encontrado verificando el primer reproceso contra el documento. |
| `app/catalogo.py` | Código de material desde REPUESTO; sufijo válido en `codigo_precio`; recuperación de ruido sobre la celda cruda; matrícula con puntos; importe con € caído en la columna de cantidad → precio; unidad con 3 o más dígitos descartada; choque de precio/cantidad bajo la misma clave → `INVALIDADO` con motivo. |
| `app/extraccion/firma_estructural.py` (+ `mapeo_cabecera`) | `tiene_forma_de_matricula`: una celda con exactamente un número de 9 dígitos entre ruido del sello CSV cuenta como matrícula al clasificar la columna — encontrado revisando el primer reproceso: en `6.24/28510.0209` (CONTRATO p.95-98) 11 de 18 celdas de la columna de matrícula llevan el sello colado, la columna no llegaba al 50% y 28 matrículas se quedaban fuera de su campo. |
| `app/extraccion/mapeo_cabecera.py` + `pipeline_anejo.py` | `completar_matricula_por_contenido`: si el mapeo no asigna matrícula y hay exactamente una columna libre que por contenido es de matrícula, se le asigna. Caso real: la columna se llama "CÓDIGO ADIF" (`6.25/28510.0251`, `6.25/28510.0213`), ningún alias la reconocía y el mapeo determinista cacheado la dejaba fuera. |
| `app/catalogo.py` | Matrícula en la columna fantasma de al lado (`6.24/28510.0173` p.9-10: según la fila, la matrícula cae en "MATRÍCULA" o en la columna sin nombre contigua), con la forma estricta de 9 dígitos como prueba. Era la variante que la sesión del 12-09 dejó pendiente. |
| `app/exportacion.py` | La nota de la hoja Resumen sobre "Código del material" explica ahora la columna REPUESTO; ya no dice "vacía en la mayoría de las filas", falso desde la ampliación del vocabulario. |
| `app/mantenimiento/frescura.py` | `VERSION_LOGICA_EXTRACCION` → `2026-09-14.1`. |

**Caché de mapeo limpiada:** de las 198 entradas, 4 contienen glifos
`(cid:`. Dos (103, 104) venían de cabeceras enteras ilegibles, con el mapeo
equivocado del bloque 3 — borradas. Las otras dos (81, 82) son cabeceras
legibles con un "(€)" en glifos dentro de una celda; su mapeo determinista
es correcto y se conservan. Se borró además la 128: su "cabecera" eran dos
filas de datos ("P-67 A", "P-68 A") tomadas por cabecera por el defecto del
sufijo.

**Unidad de medida:** 1.273 líneas (8 expedientes, 366 valores distintos)
tenían en `unidad_medida` un plano, una norma o un precio ("P16.2180.00",
"DIN 934", "1.000,00 €"); ninguna era una unidad real. La nueva validación
impide que se vuelvan a guardar, y los valores ya guardados se limpiaron en
base de datos antes del reproceso (la regla "un `None` no pisa un valor
conocido" impide que el reproceso solo los borre), copia en el registro de
la sesión. Verificando el reproceso salió una variante más: el trozo de
plano cortado a final de página ("03PME-", 2 dígitos, la otra mitad cae en
la página siguiente) — ninguna unidad real empieza por un dígito, y eso se
añadió a la misma validación (9 líneas).

Tests: 682 → 718, todos pasan — incluidos dos de punta a punta sobre
recortes reales nuevos (`6.21_28510.0109_ANEJO_repuesto_continuacion_
p3-5.pdf`: continuaciones abiertas, mapeo heredado por geometría y
REPUESTO, sin ninguna llamada al modelo; `6.21_28510.0016_ANEJO_cabecera_
ilegible_p19-20.pdf`: cabecera ilegible fuera del prompt y de la caché,
matrícula en su campo aunque el modelo devuelva el mapeo equivocado real).

---

## Bloque 6 — Reproceso completo y resultado

Copia de seguridad previa: `adif_20260914_083336.dump`. Instantánea del
catálogo antes de tocar nada, comparada línea a línea con la de después.
Cuatro reprocesos completos forzados (358 expedientes, sin descargas), todos
sin ningún fallo:

- **A** — primera versión; verificándolo contra los documentos salieron la
  nota de subsanación, la marca de corrección que no viajaba (12 líneas de
  la p.20 del doc 495) y el trozo de plano como unidad.
- **B** y **C** — misma versión de código, dos pasadas seguidas: **24.340
  líneas idénticas, mismos ids y mismos valores** (la única diferencia, 9
  líneas con el motivo del trozo de plano, la explica esa regla, que entró
  entre las dos). Determinismo confirmado. Ninguna llamada real al modelo:
  todas las respuestas salen de la caché en disco.
- **D** — versión final, con las tres correcciones de matrícula encontradas
  revisando B (sello CSV en la columna, "CÓDIGO ADIF", matrícula en la
  columna fantasma).

**Resultado final (D) frente a la instantánea previa, corpus completo:**

| | Antes | Después | |
|---|---|---|---|
| Líneas de catálogo | 22.445 | 24.339 | +1.894 |
| Líneas con matrícula | 12.720 | 13.244 | +524 |
| Pares (expediente, matrícula) | 9.934 | 10.420 | +486 nuevos, 0 perdidos |
| Matrículas atrapadas en `codigo_precio` | 199 | 0 | 199 pasan a su campo |
| Líneas con código de material | 14.248 | 16.074 | +1.826 |
| Líneas con unidad de medida | 18.708 | 21.492 | +2.784 (incluye 2.482 completadas del maestro de SAP) |
| Huérfanas sin lote (cola de revisión) | 2.175 | 2.694 | +519 |

- 2.061 líneas salen de páginas que antes no aportaban nada (18
  documentos, 43 expedientes): 298 con matrícula, 1.954 con código de
  material. Las que más: anejo 588 (906), `6.24/28510.0130` (213), doc 495
  (207), `4.26/28510.0020` (267 entre sus dos documentos).
- 30 códigos de material cambian en líneas que ya existían, todos por
  REPUESTO en la familia 0108: CRUZAMIENTO → CRUZAMIENTO OBTUSO (18),
  CORAZÓN → CRUZAMIENTO (12).
- Las huérfanas nuevas son líneas reales de expedientes multi-lote cuyas
  tablas no dicen a qué lote pertenecen (`4.26/28510.0020`, +267) o de
  otros lotes del mismo acuerdo marco (familia `0130`/`0152`/`0153`, +71
  cada uno) — por la regla de no adivinar el lote, a la cola de revisión.
- **Guarda de choques:** 368 líneas marcadas en 74 expedientes (66 por
  precio, 302 por cantidad). De las 294 que ya existían, 49 pierden un
  precio y 285 una cantidad que antes se mostraban con "el último gana".
  Revisados cuatro casos contra el PDF (arriba): en todos el valor era de
  otro lote o de otra tabla. Decisión revisable si se prefiere conservar el
  valor y solo marcarlo.
- Sin pérdidas: las líneas que desaparecen entre reprocesos son siempre
  sustituciones 1:1 (clave con ruido del sello CSV → clave limpia con su
  matrícula, mismo precio y descripción) o copias sin matrícula de un
  material que sigue en el catálogo con matrícula y el mismo precio
  (verificado caso a caso en `6.24/28510.0184` y `6.25/28510.0118`).

**Excel entregable:** 19.898 → 21.384 filas en Materiales; matrícula
11.386 → 11.924; código de material 13.141 → 14.563; unidad 16.612 →
18.746; expedientes con líneas 215 → 232. Pendientes en Resumen 2.547 →
2.955.

**Verificación contra el documento:** `6.21/28510.0015`/`0016`/
`6.20/28510.0115`: 103/103 matrículas, 0 de más, precio y cantidad
idénticos al pliego en las 103. `6.21/28510.0109`: 203/203 filas del anejo
588, código de material = REPUESTO en las 172 que lo traen. Correcciones de
matrícula: `6.24/28510.0173` 27 → 43, `6.24/28510.0209` 21 → 49,
`6.25/28510.0213` 0 → 5, `6.25/28510.0251` 0 → 10.

**Auditoría automática:** 0 errores tras C y D (5 avisos de categorías ya
conocidas).

---

## Pendiente, sin resolver en esta sesión

- **Probable resto de "cosas que no me cuadran" en el pliego de
  tornillería:** `6.21/28510.0015` es solo el Lote 1 y `0016` solo el Lote
  2, pero cada uno muestra los dos lotes (79 + 26 líneas), con el lote 1
  ligado a `0016` y baja 0 %. Es el pendiente conocido de separar
  expedientes de lote reales (CONTEXTO.md sección 16), no algo de esta
  sesión.
- **Identidad de lote en documentos compartidos.** La guarda de choques deja
  vacío (y marcado) lo que antes era un valor de otro lote presentado en
  silencio, pero el valor correcto para cada expediente solo se podrá dar
  cuando se sepa qué "LOTE N" del documento es cada expediente (pendiente
  conocido, CONTEXTO.md sección 16).
- **El Excel no explica el precio vacío** de una línea con choque: el motivo
  solo se ve en la cola de revisión. Decisión de producto: ¿nota en la hoja
  Resumen, o marcador en la celda?
- **Huérfanas nuevas**: parte de lo recuperado cae en expedientes
  multi-lote cuyas tablas no dicen a qué lote pertenecen ("banda vacía",
  "ninguna cabecera LOTE N") — están en la cola de revisión, fuera de la
  hoja Materiales, por la regla de no adivinar el lote.
- **Residuo del localizador:** 10 páginas en 8 documentos con 2-4 líneas de
  filas de datos que siguen sin abrirse (colas cortas tras una página que no
  es candidata, por debajo del umbral de 3 filas del arranque sin cabecera).
- **Filas desalineadas por `pdfplumber`** en `ANEJO_ce1df15b39efdb8c.pdf`
  p.21 y p.36 (el código de cada fila cae una fila por debajo de sus datos):
  la validación de coherencia las rechaza y quedan fuera del Excel; los
  mismos materiales entran bien desde el anejo 588.
