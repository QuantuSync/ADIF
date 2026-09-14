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

## Pendiente al cerrar la primera parte

Los cuatro primeros puntos de esta lista se trataron en la continuación
(abajo); los dos últimos siguen abiertos.

- **Tornillería:** `6.21/28510.0015` es solo el Lote 1 y `0016` solo el
  Lote 2, pero cada uno muestra los dos lotes (79 + 26 líneas), con el lote 1
  ligado a `0016` y baja 0 %. → Continuación, bloque C1.
- **Identidad de lote en documentos compartidos.** La guarda de choques deja
  vacío (y marcado) lo que antes era un valor de otro lote presentado en
  silencio. → Se mantiene así por decisión del cliente (continuación).
- **El Excel no explica el precio vacío** de una línea con choque. →
  Continuación, bloque C3.
- **Huérfanas nuevas** en expedientes multi-lote cuyas tablas no dicen a
  qué lote pertenecen. → Continuación, bloque C2.
- **Residuo del localizador:** 10 páginas en 8 documentos con 2-4 líneas de
  filas de datos que siguen sin abrirse (colas cortas tras una página que no
  es candidata, por debajo del umbral de 3 filas del arranque sin cabecera).
- **Filas desalineadas por `pdfplumber`** en `ANEJO_ce1df15b39efdb8c.pdf`
  p.21 y p.36 (el código de cada fila cae una fila por debajo de sus datos):
  la validación de coherencia las rechaza y quedan fuera del Excel; los
  mismos materiales entran bien desde el anejo 588.

---

# Continuación — respuesta del cliente al reproceso

Decisiones y encargos:

- **Precios y cantidades con choque: se quedan vacíos y marcados.** En los
  cuatro casos revisados contra el PDF el valor era de otro lote; un hueco
  explicado es mejor que un número falso.
- **Pero el Excel tiene que explicar ese hueco**, con el mismo criterio de
  los tres motivos (no aplica / no consta / pendiente): una cantidad vacía
  porque el valor era de otro lote no puede leerse igual que una que el
  documento no trae (bloque C3).
- **Revisar las 519 huérfanas nuevas contra el criterio de herencia entre
  páginas** (bloque C2).
- **Tornillería:** que `0015` y `0016` dejen de mostrar los dos lotes,
  "el mismo problema que ya se resolvió para otros expedientes" (bloque C1).
- El BOM del asunto del commit anterior se deja como está.

## C1 — Identidad de lote en expedientes hermanos

**Lo que había de verdad, antes de tocar nada.** Lo resuelto para otras
familias (CONTEXTO.md sección 27) es el código propio de cada lote
(`lotes.codigo_expediente_lote`): en casi todas estaba bien. Pero **ningún
expediente del corpus se restringía a su propio lote**: un expediente que
es el LOTE N de una licitación (su código es el "EXPEDIENTE Nº" de ese
lote) comparte los documentos con sus hermanos y guardaba las líneas, la
baja y el importe de todos los lotes — medido tras el arreglo: 39
expedientes de 12 familias mostraban 4.955 líneas de lotes ajenos (los 7
expedientes de lote de `6.25/28510.0019` con catálogo, de `0039` a `0047`,
llevaban cada uno las ~460 líneas de los nueve lotes). Tornillería tenía
además la identidad mal.

**La fuente con autoridad: el Contrato.** "Contrato nº: X" en la cabecera
y, justo debajo del título, "LOTE N: <descripción>" — la relación "Contrato
⟷ lote" de la sección 27. De 170 documentos con "Contrato nº", 104 declaran
así su lote (83 con baja). Contrastados con lo que guardaba el motor, tres
familias discrepan, las tres por el documento, no por azar:

| Familia | Qué dice el documento | Qué guardaba el motor |
|---|---|---|
| Tornillería (`6.20/28510.0115`: `0015` LOTE 1, `0016` LOTE 2) | La única Resolución es la del LOTE 2; su RESUELVE lo llama "LOTE 1: ANCLAJES DE SEGURIDAD. EXPEDIENTE Nº: 6.21/28510.0016" (errata) | Los dos lotes ligados a `0016`; el LOTE 1 con la baja (0 %) y el importe (15.000 €) del LOTE 2 |
| `6.22/28510.0033` (`0057` LOTE 1 Norte, `0058` LOTE 2 Sur) | "LOTE 2: SUR Y, EN CASO DE URGENCIA QUE NO PUEDA SER TENDIDA POR EL ADJUDICATARIO DEL LOTE1, NORTE · EXPEDIENTE Nº 0058"; y la Resolución del LOTE 2 copia en su RESUELVE "LOTE 1 … 0057" con la empresa y la baja del LOTE 2 (TECNOLOGÍA SEÑALÉTICA, 0,50 %). Contratos: `0057` INDUSTRIAS LANEKO 10,50 %, `0058` TECNOLOGÍA SEÑALÉTICA 0,50 % | LOTE 1 → `0058` sin baja, LOTE 2 → `0057` con 0,50 %: identidades cruzadas, y las líneas del LOTE 1 sin precio adjudicado |
| `6.22/28510.0122` (`0155` LOTE 1, `0156` LOTE 2) | La misma referencia cruzada en la Propuesta del LOTE 2, único documento de lotes. Contratos: `0155` 24,90 %, `0156` 24,99 % | LOTE 1 → `0156` con la baja del LOTE 2 (24,99 %); LOTE 2 sin código ni baja |

**Arreglos** (`app/extraccion/lotes.py`, `orquestador.py`, `baja.py`):

1. La referencia cruzada "adjudicatario del LOTE N" ya no abre ventana de
   lote (se llevaba el código y la baja del lote que describe), pero sí
   cuenta como lote nombrado, sin datos. Mismo criterio que ya aplicaba la
   asociación de tablas a la cláusula de "urgencia mutua" (sesión del 08-09).
2. `extraer_identidad_contrato` y `_identidades_de_contratos`: lo que cada
   Contrato del expediente dice de sí mismo; si dos Contratos se contradicen
   no se usa ninguno. Con ello: una ventana de la adjudicación cuyo código
   propio un Contrato ata a otro número es una errata de número y va al lote
   del Contrato (tornillería); un lote nombrado sin código ni baja los toma
   de su Contrato; si el Contrato de un lote declara una baja distinta de la
   que le da la adjudicación, **gana el Contrato** — el único documento que
   habla solo de ese lote — y el adjudicatario y el importe de ese bloque
   dejan de atribuirse, con motivo de revisión (`0033` lote 1: único caso en
   el corpus). **Nunca añaden un lote que la adjudicación no nombra**:
   probado en seco, habría convertido `6.23/28510.0051` en multi-lote y su
   cuadro común de 1.080 líneas, sin ningún "LOTE N", se habría quedado
   entero sin lote.
3. "La baja ofertada **de** 0,00 %" (sin "del"): 8 Contratos del corpus con
   esa redacción, en ninguno se encontraba la baja (el del LOTE 1 de
   tornillería entre ellos).
4. **Un expediente de lote guarda solo su lote.** Si exactamente uno de los
   lotes declarados trae como código el del propio expediente, los demás
   son de sus hermanos: no se guardan en él (ni sus líneas, ni su baja, ni
   su importe; lo que guardó una pasada anterior se borra). Las tablas de
   los otros lotes siguen sirviendo para asociar cada tabla a su "LOTE N"
   (si no, se leerían como de un lote no declarado); sus líneas solo se
   descartan al guardar. La cobertura se mide sobre su lote, y deja de
   pedir revisión por "EXPEDIENTE PRINCIPAL distinto": es lo esperado en un
   lote. El expediente principal (su código no es el de ningún lote) sigue
   con todos. Ninguna línea se pierde: todas siguen en el principal y en el
   hermano correspondiente (comprobado abajo).

**Resultado** (corpus completo, contrastado con los documentos):

- **Tornillería:** `0015` guarda solo el LOTE 1 (código `0015`, baja 0,00 %
  de su Contrato, 79 líneas: 78 matrículas y la partida alzada); `0016`
  solo el LOTE 2 (`0016`, 0,00 %, 15.000 €, 26 líneas: los 25 anclajes y la
  partida alzada); `6.20/28510.0115`, el principal, los dos con sus códigos
  correctos. 78 + 25 = las 103 matrículas del pliego.
- **`6.22/28510.0033`:** `0057` es el LOTE 1 con el 10,50 % de su Contrato
  (136 líneas, que antes no tenían precio adjudicado: 4,29 € × (1 − 0,105)
  = 3,8396 €) y un motivo que explica la contradicción con la Resolución;
  `0058` el LOTE 2 con 0,50 % (135 líneas).
- **`6.22/28510.0122`:** `0155` LOTE 1 con 24,90 %, `0156` LOTE 2 con 24,99 %
  (407 líneas cada uno), ya no cruzados.
- 19 lotes con el código corregido o completado desde su Contrato, y 2.190
  líneas con la baja corregida o completada (bajas contrastadas con el texto
  de cada Contrato: `0238` 9,67 %, `0002` 30,00 %, `0176` 0,00 %, `0057`
  10,50 %, `0155` 24,90 %, y el 1 % de `6.20/28510.0080`, una de las 8
  redacciones "baja ofertada de").
- **39 expedientes de lote de 12 familias dejan de mostrar 4.955 líneas de
  lotes ajenos.** Ningún contenido se pierde: comprobado clave a clave que
  todo lo que desaparece sigue en el catálogo del principal o del hermano
  (las únicas "ausencias" son líneas que ahora se funden con la misma línea
  de otro documento del mismo expediente).

## C2 — Las 519 huérfanas nuevas, contra el criterio de herencia

Recorridas tabla a tabla en el mismo orden que el motor, anotando qué
asocia la franja, qué habría para heredar y qué texto hay entre la tabla
anterior y cada una (script de auditoría de la sesión, fuera del
repositorio):

| Familia | Huérfanas nuevas | Qué son | ¿Legítimas? |
|---|---:|---|---|
| `4.26/28510.0020` (CONTRATO y ANEJO, 2 lotes) | 267 (de 291 sin lote en total) | El presupuesto de cada lote (83) y el cuadro de precios para la partida alzada, común a los dos lotes (208) | **Las 83 del presupuesto, no**: el "LOTE N" que abre cada presupuesto no está en la franja sobre la tabla. El cuadro común, sí |
| `6.24/28510.0130`/`0152`/`0153` | 213 (71 × 3) | Tablas de los lotes 1-3 y 7-13 del acuerdo marco (el expediente declara 4-6) y sus continuaciones; y el anejo de criterios técnicos común a los 13 | Sí |
| `6.22/28510.0122`/`0155`/`0156` | 33 | Anejo de criterios técnicos, común a los dos lotes: ningún "LOTE N" en todo el documento antes de la tabla | Sí |
| `6.22/28510.0033`/`0057`/`0058` | 33 | Ídem | Sí |
| Tornillería | −27 | — | — |

En `4.26/28510.0020` la cabecera de sección está en dos sitios que la
franja no mira, los dos igual de exclusivos de la tabla:

- **Dentro de la caja de la tabla**, en sus filas de título:
  `pdfplumber` devuelve "… LOTE 1: SUBDIRECCIÓN DE OPERACIONES ESTE Ref.
  CAPITULO I: MEDIOS HUMANOS" como cabecera.
- **Al final de la página anterior**, debajo de su última tabla: "El
  Presupuesto Base de Licitación del Lote 1 asciende a … LOTE 2:
  SUBDIRECCIÓN DE OPERACIONES NORESTE", y la tabla del LOTE 2 empieza en la
  página siguiente (la regla de "urgencia mutua" ya distingue la cabecera
  "LOTE 2:" de la referencia "del Lote 1").

`asociar_lote_tabla` los consulta, en ese orden y solo con la franja limpia
(la franja con rastro manda como siempre); la cola de la página anterior,
solo si es la contigua.

**Hallazgo verificando el arreglo:** una vez resuelto el LOTE 2 en la p.17
del ANEJO, el cuadro de precios de la partida alzada (p.39-46, común a los
dos lotes) **heredaba el LOTE 2 a 22 páginas de distancia**. La herencia
solo miraba la franja de la página actual, así que saltaba cualquier
número de páginas sin tabla. Revisando el reproceso salió otro caso igual
en `6.25/28510.0214`: la tabla de criterios técnicos (p.30, común a los 8
lotes) heredaba el LOTE 8 de la p.24 — cinco páginas por medio y ningún
"LOTE N" con número entre ellas, así que tampoco lo cortaba un rastro de
lote. El criterio aprobado son las **páginas de continuación**: ahora solo
se hereda si la tabla anterior está en la misma página o en la contigua;
con páginas sin tabla por medio, la tabla queda sin lote (motivo propio,
explicado en la hoja Resumen) y la cadena se corta.

El mismo documento de `0214` confirma que el "LOTE N" al pie de página es
la cabecera de la primera tabla de la página siguiente (el "LOTE 1" está
encima de la primera tabla de la p.20, y cada "LOTE N" siguiente encima de
la suya o al pie de la página anterior): la p.23 heredaba el LOTE 5 cuando
es el 6, y la p.24 el 7 cuando es el 8. Con la cola de la página anterior
quedan bien.

**Resultado.** `4.26/28510.0020` recupera el presupuesto de sus dos lotes
(17 líneas cada uno, antes 0; 291 → 208 sin lote, que son el cuadro común
de la partida alzada). Y la regla de contigüidad saca de los lotes, en toda
la base, tablas comunes que se venían heredando desde siempre: el anejo de
criterios técnicos que sigue al cuadro de precios en
`6.25/28510.0019` (229 líneas que `0047` y el principal mostraban como
LOTE 9, cuyo cuadro real son 4 líneas), en la familia `6.25/28510.0088`
(28, como LOTE 5), en la familia `6.24/28510.0203` (27, que además pisaban
las líneas reales del LOTE 6 — el "CANTIDAD 50" que la primera parte de la
sesión dejó en blanco con la guarda de choques: ahora el LOTE 6 vuelve a
tener sus cantidades reales, hasta 2.500, sin ningún choque —) y en
`6.25/28510.0214` (10, que dejaban sin precio P-01 y P-02 del LOTE 8).
Todas pasan a la cola de revisión como lo que son, tablas sin lote, con el
motivo nuevo explicado en el Resumen.

## C3 — El Excel explica cada celda vacía

`app/celdas_vacias.py` decide, en el motor y en un solo sitio, por qué está
vacía cada celda de datos de una línea, con los tres motivos de la web:

- **No aplica**: partida alzada (matrícula, código de material, unidad).
- **No consta**: el documento no trae el dato.
- **Pendiente**: depende de otro dato. En Cantidad o Precio unitario, el
  documento da un valor distinto para cada lote bajo el mismo código de
  precio (el motivo de la guarda de choques, `MOTIVO_VALOR_DE_OTRO_LOTE`); en
  Precio adjudicado, falta la baja del lote o el precio unitario.

En el Excel las celdas siguen vacías — un marcador de texto rompería las
columnas numéricas, decisión anterior del cliente —, y el motivo va en una
columna nueva, **"Motivo de las celdas vacías"**, justo antes de
"Comentarios" (que sigue la última): p.ej. "Matrícula del material: no
consta; Cantidad: pendiente (el documento da una cantidad distinta para
cada lote y falta saber cuál es la de este)". La hoja Resumen explica los
tres motivos y cuenta las líneas con Cantidad o Precio unitario pendiente.
La API devuelve lo mismo por línea (`celdas_vacias`) y la web lo usa en
Cantidad y Precio unitario (catálogo y revisión); Precio adjudicado sin
precio unitario pasa de celda en blanco a "Pendiente", igual que en el
Excel.

## Reproceso y verificación

Copia de seguridad previa: `adif_20260914_104029.dump`. Instantánea del
catálogo antes de tocar nada. Seis pasadas completas forzadas (358
expedientes, sin descargas), cada una verificada contra los documentos
antes de la siguiente:

- **E1** — identidad de lote, expediente de lote, título/cola de página y
  "baja ofertada de".
- **E2** — con la guarda de la cifra imposible: **idéntica a E1 línea a
  línea** (determinismo). El doc 702 seguía sin guardarse: además de la
  cantidad, la unidad ("UD. UD. …", 111 caracteres) tampoco cabía.
- **E3** — herencia solo entre páginas contiguas y unidad que no cabe.
  Revisándola salieron dos cosas: 48 filas de solo importes de esa misma
  tabla, ya guardándose, como líneas sin descripción (error de la
  auditoría), y 10 líneas duplicadas en `6.25/28510.0251` — ver abajo.
- **E4** — mismo código que E3: **idéntica a E3 línea a línea**.
- **E5** — versión final (filas de solo importes y matrícula partida).
- **E6** — mismo código que E5: **idéntica a E5 línea a línea**, y la
  auditoría automática a **0 errores** (4 avisos de categorías ya
  conocidas).

**Las 10 líneas de `6.25/28510.0251`, un defecto de la primera parte de la
sesión, no de esta.** La p.18 del ANEJO trae dos columnas de código
("CODIFICACIÓN DEL PRECIO" con P-01… y "CÓDIGO ADIF" con la matrícula), y
el mapeo cacheado desde el 08-09 manda `codigo_precio` a la de la
matrícula. La corrección matrícula/código no lo detectaba porque
`pdfplumber` parte la matrícula en dos líneas ("59420000\n0"): sin un
número de 9 dígitos seguidos, la columna no "tenía forma de matrícula". Las
10 filas se guardaban con la matrícula en `codigo_precio`, duplicando las
P-01…P-10 de la p.23. Comprobado restaurando la copia de antes de esta
continuación en una base aparte y extrayendo `0251` con el código del
commit anterior: ya salían esas 24 líneas (el catálogo guardado de `0251`
era de una pasada anterior a ese código, por eso no se había visto). Ahora
`tiene_forma_de_matricula` limpia la celda igual que la construcción de la
línea (`limpiar_codigo_celda`, sin espacios ni saltos de línea) y `0251`
vuelve a sus 14 líneas.

**Resultado final (E5) frente al estado de partida de esta continuación,
corpus completo:**

| | Antes | Después | |
|---|---:|---:|---|
| Líneas de catálogo | 24.339 | 22.115 | −4.955 de lotes ajenos; +34 del presupuesto de `4.26/28510.0020`; +24 de los LOTES 6 y 8 de `0214`, que antes se fundían en el 5 y el 7; y las tablas comunes (−508 que se mostraban como de un lote) y los dos anexos de `0122` (+936) pasan a la cola |
| Sin lote (cola de revisión) | 2.694 | 5.875 | +2.328 tablas comunes a todos los lotes que se heredaban como de un lote; +936 anexos de precios de los Contratos de `0122` que antes no se guardaban; −83 presupuesto de `4.26/28510.0020` |
| Excel: filas en Materiales | 21.384 | 15.979 | casi todo, el mismo material repetido en cada expediente hermano |
| Excel: con matrícula | 11.924 | 10.190 | |
| Excel: con código de material | 14.563 | 10.243 | |
| Excel: expedientes con líneas | 232 | 233 | `4.26/28510.0020` entra |
| Excel: Cantidad o Precio unitario "pendiente" por valor de otro lote | — | 274 líneas | explicado en su celda de motivo |
| Resumen: líneas pendientes de revisión | 2.955 | 6.136 | |

**Determinismo:** E1 = E2, E3 = E4 y E5 = E6 línea a línea (mismos ids y
valores); E5 frente a E4 solo cambia lo esperado (`0251` −10 duplicadas,
familia `0122` −48 filas de solo importes). **Auditoría automática:** tras
E4 quedaban solo las 48 líneas sin descripción (error), resueltas en E5;
tras E6, 0 errores.

**Tests:** 718 → 743, todos pasan: identidad de contrato y errata de número
(tornillería), referencia cruzada (`0033`, `0122`), baja del Contrato
contra la de la adjudicación (`0033`), expediente de lote de punta a punta
con el anejo real de `0156` (solo su lote, principal con los dos,
idempotencia), título/cola de página y tabla separada por páginas
(`4.26/28510.0020`, recorte nuevo de 6 páginas), celdas vacías (motor,
Excel y API), cifra/unidad imposibles y filas de solo importes, matrícula
partida. Ocho recortes de página reales nuevos en `engine/tests/fixtures`
(el mayor, 296 KB).

## Pendiente al cerrar la continuación

- **Expedientes de lote cuyo documento de lotes es el de un hermano (decisión
  del cliente).** 36 expedientes cuyo propio Contrato dice "soy el LOTE N"
  no tienen guardado ningún lote con su código: el único documento de lotes
  archivado con ellos es la adjudicación de OTRO lote (p.ej.
  `6.21/28510.0003`, LOTE 2, guarda el LOTE 1 de `0002`; `6.23/28510.0060`,
  LOTE 1, guarda las 1.069 líneas bajo el LOTE 2 de `0061` y su baja del
  25,10 % en vez del 25,31 % de su Contrato), o no hay ninguno y todas las
  tablas del anejo compartido caen en su lote implícito (familia
  `6.21/28510.0108`, anejo 588: `0112` y `0113` con 221 líneas cada uno).
  2.713 líneas en total, todos ya en `pendiente_revision`. Resolverlo como
  C1 (guardar solo su lote) exige decidir antes qué hacer con las tablas
  que no dicen de qué lote son en un expediente de lote: si el cuadro es
  común a todos los lotes (`0060`) son suyas; si es de otro lote sin
  cabecera, no. Sin esa decisión, aplicar C1 aquí dejaría sin catálogo a
  `0060`.
- **Huérfanas de lotes no declarados en un expediente de lote**
  (`6.24/28510.0151`/`0152`/`0153`: las tablas de los lotes 1-3 y 7-13 del
  acuerdo marco, 221 por expediente): ya se sabe que no son suyas, pero
  siguen en la cola de revisión. Es la decisión de producto que ya dejó
  abierta la sesión del 12-09 ("pertenece a otro lote del acuerdo marco").
- **`6.22/28510.0058`** (LOTE 2) se queda sin importe de adjudicación: el
  único bloque que lo traía es el RESUELVE con la errata, que ya no se
  atribuye a ningún lote.
- **`6.23/28510.0051` y `6.23/28510.0060` no refrescan tres documentos**
  (ANEJO_1, CONTRATO_1, CONTRATO_2): al guardar, una línea encontrada por
  firma de material se re-etiqueta a "P-0996", que ya tiene otra línea del
  mismo lote (`uq_linea_lote_clave`) — el desfase de filas conocido de ese
  anejo. El código lo deja reventar a propósito ("un problema de datos
  real que conviene que reviente aquí"), pero el efecto es que el documento
  entero se deshace y el catálogo de esos dos expedientes se queda con los
  valores de una pasada anterior. Ya ocurría en el estado de partida de esta
  continuación; no se ha tocado.
- **Anexos de precios de los dos Contratos de la familia `6.22/28510.0122`**
  (doc 702 del LOTE 2 y doc 703 del LOTE 1, 150 líneas cada uno, más unas
  pocas filas de su tabla de aplicabilidad): ahora se guardan (antes una
  cifra imposible tumbaba cada documento entero), pero sin lote — la tabla
  no dice de qué lote es, aunque el documento entero sea el Contrato de uno
  —, así que van a la cola de revisión en los tres expedientes. Atribuirlas
  al lote del Contrato sería otra regla (identidad de documento → lote) con
  un riesgo propio, sin verificar todavía: si los precios del anexo no son
  los del cuadro de precios del anejo, al fundirse pisarían los de
  referencia.
- Siguen abiertos los dos últimos puntos de la primera parte (residuo del
  localizador y filas desalineadas de `ANEJO_ce1df15b39efdb8c.pdf`).

**Resueltos en la tercera parte (abajo):** los 36 expedientes, `0051`/`0060`
(P-0996) y los anexos de los Contratos de `0122`, que resultaron no ser un
anexo de precios.

---

# Tercera parte — expedientes que saben cuál es su lote

Respuesta del cliente al cierre de la continuación:

- **Los 36 expedientes:** "si el propio Contrato dice «soy el LOTE N», ese
  expediente tiene lote conocido. Las tablas que no declaran lote dentro de
  un expediente que sabe cuál es el suyo, son suyas". Que `0060` se quede
  sin catálogo teniendo 1.069 líneas propias sería peor que el problema.
- **1.** Antes de nada, cuántas de las 5.875 líneas sin lote son tablas
  comunes legítimas y cuántas se recuperarían: ¿la caída del Excel es
  corrección o se pierde material?
- **2.** Arreglar la clave duplicada P-0996 de `0051`/`0060`.
- **3.** Los anexos de los Contratos de `0122`: si su expediente tiene lote
  conocido, entran con la misma regla.
- Al terminar, reproceso, auditoría y Excel, con la comparación de
  **materiales distintos**, no solo de filas.

## T1 — Las 5.875 líneas sin lote, contra los documentos

| Qué son | Líneas |
|---|---:|
| Anejo de **criterios técnicos** del conjunto de los lotes ("detallar los materiales a suministrar en el expediente “… N LOTES”"): la lista de materiales de la licitación entera, con su propia numeración — `0019` (9 expedientes), `0122`, `0033`, `0130`, `0088`, `0203`, `0214` | 4.239 |
| Cuadro de precios de la partida alzada de `4.26/28510.0020`, común a sus dos lotes (principal) | 208 |
| Tablas con cabecera explícita de un lote que el expediente no tiene, y sus continuaciones (`0130`, `0027`, `0028`) | 492 |
| "Anexos" de los Contratos de `0122` (156 × 2 × 3 expedientes) | 936 |

**No se perdía material.** En el Excel, materiales distintos (matrícula, o
descripción sin espacios ni signos) 5.512 al empezar la continuación →
5.519 después; el único que "desaparece" es la errata del anejo de criterios
de `0019` ("Biela Izquierda tipo AV4 para 1º, **2**, 3º…"), que sigue en su
lote como P-706, mismo código y precio, con "2º". La caída de filas era el
mismo material repetido en cada hermano y el anejo de criterios mostrado
como si fuera de un lote.

**Tres correcciones a lo que dijo la continuación, verificadas en el PDF:**

- **`0060` no es un cuadro común sin "LOTE N".** Su anejo trae "Lote 1:
  ANCHO MIXTO" (p.14) y "Lote 2: ANCHO METRICO" (p.38); lo que no trae lote
  es el anejo de criterios (p.55-97). Con su lote identificado por su
  Contrato, `0060` se queda su LOTE 1 por la cabecera explícita. La regla
  "nunca añadir un lote que la adjudicación no nombra" nació de esa misma
  lectura equivocada: su principal `0051` mostraba el LOTE 2 como LOTE 1.
- **Los "anexos de precios" de los Contratos de `0122` son el anejo de
  criterios** (Grupo 2, con la columna de impacto en la seguridad): 150 de
  cada 156 líneas. Las otras 6 son tablas sueltas de los cuadros de cada
  lote (p.122 del LOTE 1, p.133 del LOTE 2), cuyas cabeceras ("LLote 1:",
  negrita simulada) están en páginas que el localizador no abre.
- **El anejo de criterios no es "de nadie":** dice de sí mismo que es de
  todos los lotes, y en `0122` añade que "no coincide" con el cuadro de
  precios. Aplicar la regla a esas tablas contradecía el documento: `0047`
  (LOTE 9, 4 precios) recibía 229 líneas, 225 con códigos de los lotes
  1-8; en `0203`/`0088` la cifra es la "cantidad mínima a incluir en cada
  pedido" y volvía la "CANTIDAD 50" sobre el LOTE 6 real; y en `0051` el
  anejo numera distinto (ver T3). **Decisión del cliente: la regla se
  aplica salvo al anejo de criterios**, "el documento dice de sí mismo que
  es del conjunto de lotes y que no coincide con el cuadro de precios, así
  que atribuirlo a uno sería contradecirlo". Y dos encargos más: arreglar
  el principal `0051`, y acotar la fusión por firma entre criterios y
  cuadro (T3).

## T2 — La regla, aplicada

**Lote propio** (`orquestador._lote_propio`): el de un expediente cuando
exactamente uno de los lotes declarados trae su código. **Los lotes que
solo nombra un Contrato se registran** (antes no): `0060` recupera su LOTE
1 (25,31 % de su Contrato) aunque su único documento de lotes sea la
adjudicación de `0061`; `0051` pasa a tener sus dos lotes. **Sin ningún
documento de lotes** (17 expedientes, p.ej. `6.21/28510.0112`), el lote
implícito deja de ser "1": es el LOTE N del Contrato propio, con su código,
y los demás Contratos archivados con él son de sus hermanos.

**Asociación de tablas** (`pipeline_anejo`, `lote_tabla`), en un
expediente con lote propio — también con un solo lote conocido, porque los
documentos compartidos traen las tablas de todos:

- Tabla con cabecera de lote: la de siempre. Si es de otro lote, sus
  líneas no se guardan (hermano) o quedan sin lote (lote no declarado).
- **Tabla sin ningún rastro de lote: es del expediente**
  (`lineas_catalogo.lote_del_expediente`, migración 0030, para poder
  encontrarlas todas), salvo que:
  - sea del **anejo de criterios del conjunto**
    (`del_conjunto_de_lotes`): la frase "detallar los … a suministrar en el
    expediente “… N LOTES”" (61 documentos del corpus, cuatro redacciones)
    en el texto que la precede, sin cabecera de lote después — sigue siendo
    del conjunto hasta la próxima tabla con cabecera, aunque haya páginas
    sin tabla por medio; en cualquier expediente, no solo en los de lote;
  - siga, sin páginas por medio, a una tabla de otro lote o ambigua (es su
    continuación);
  - la **última mención de lote** en las páginas que la separan de la tabla
    anterior (o en todo el documento hasta ella, si es la primera) sea de
    otro lote: la cabecera de su sección está en una página que el
    localizador no abrió (`6.21/28510.0109_ANEJO_1`: "Lote 1. Semicambios…"
    en la p.18, su tabla en la p.19 sin cabecera);
  - el documento sea el **Contrato de otro lote** (su "Contrato nº" no es el
    código del expediente): sus tablas sin cabecera son de ese lote.

Verificado en seco, antes de reprocesar, contra los documentos: `0051`
ANEJO_1 (p.14-38 LOTE 1, 577 líneas; p.38-51 LOTE 2, 496; p.55-97 criterios,
1.033), los Contratos de `0122` en `0155` y `0156` (la tabla de la p.122 es
del LOTE 1 en los dos Contratos; la de la p.133 del LOTE 2), `0112`
(ANEJO_1: p.19-26 del LOTE 1 fuera; p.42 y siguientes, su LOTE 4), `0059`,
`0047`, `0011`, `0057`, `0214`.

**Lo que salió al revisar la primera pasada (F1), contra los documentos:**

- **Líneas de un hermano que no está en el catálogo.** `6.21/28510.0066`
  (LOTE 2) guarda el Contrato del LOTE 1 (`0065`), que trae el "LISTADO
  LOTE 1" (p.116, 17 materiales) y el "LISTADO LOTE 2" (p.117, 9). Con el
  LOTE 1 registrado desde ese Contrato, sus 17 líneas eran de un hermano y
  se descartaban -- pero `0065` no está en el catálogo, y desaparecían de
  todas partes. La continuación descartaba las líneas de hermanos porque
  "siguen en el hermano y en el principal"; eso solo vale si están. Ahora
  solo se descartan si el expediente del hermano existe; si no, se
  conservan en este expediente sin lote, con su motivo ("tabla del LOTE 1
  (6.21/28510.0065), otro lote de la licitación cuyo expediente no está en
  el catálogo"), fuera del Excel y con su categoría en el Resumen.
- **"Lote 1." con punto.** `6.22/28510.0125`/`0126`: "Lote 1. NORTE y, en
  caso de urgencia que no pueda ser atendida por el adjudicatario del lote
  2, SUR." -- la cláusula de urgencia mutua de siempre, con punto en vez de
  dos puntos; la regla que la resuelve pedía los dos puntos. Antes daba
  igual (todo iba a su único lote implícito); en cuanto `0125` supo que es
  el LOTE 1, sus tablas quedaban ambiguas y se quedaba sin catálogo (209 →
  0). Con el punto aceptado, 209 líneas en su LOTE 1 (p.15-20 del ANEJO_1),
  las del LOTE 2 para `0126`.
- **`6.22/28510.0016` (balasto, LOTE 6) se queda sin líneas en su lote, y
  es correcto.** Sus 4 líneas de antes eran P-1…P-4 de las tablas de los
  lotes 1-5 fundidas (con precio "pendiente" por la guarda de choques). Su
  propia tabla, "LOTE 6: RAM NORTE" (ANEJO_1 p.21: P-1 65.000 m³ a 14,20 €,
  P-2 64.000 a 16,50 €, P-3 65.000 a 1,10 €, P-4 100.000 m³·km a 0,12 €),
  **no la detecta `pdfplumber`** como tabla -- solo la del LOTE 5 que tiene
  encima. Hueco de detección de tablas que ya existía, antes escondido.
- **P-0167 y P-0179** de `0051`/`0060` salen en la auditoría como
  "duplicadas exactas", y el documento las repite así: "Semicambio dcha
  (sencillo) DIRD-B1-54-190-0.11-CR-D", 22.712,17 €, dos códigos (Contrato
  del LOTE 2, p.118). Se quedan las dos, con su código.

## T3 — P-0996

La p.49 del ANEJO_1 de `0051` (cuadro de precios) y la p.95 (anejo de
criterios) numeran distinto: "ENF-54 Curva", matrícula 618050403, es P-0994
en el cuadro y P-0996 en criterios; y P-0996 es en el cuadro otro material
("ESF-B1-UIC54-186-1/10.5- CR-I-E:3500", 204.094,04 €). Con los dos lotes y
los criterios en un único lote, la fusión por firma (misma matrícula,
descripción y precio) juntaba las dos filas y se quedaba con el último
código visto: la clave pasaba a "P-0996", ya ocupada, y el documento entero
se deshacía en cada reproceso (`uq_linea_lote_clave`; 97 líneas de `0051`
seguían con código y clave distintos de una pasada antigua).

Con la identidad de lote, el anejo de criterios ya no entra en ningún lote
y el choque no se da. Además, **acotada la fusión** (`catalogo.
_combinar_por_clave`): fundida por firma, una fila con otro código propio
no le pasa ese código a la línea del cuadro — sigue siendo el mismo
material, con el código de la tabla que lo trajo primero. Bloquear la
fusión sin más habría duplicado el caso de `6.24/28510.0180` (la tabla de
impacto en la seguridad repite "PN004" como "PN004ps", test existente), que
además quedaba con el código de la tabla de impacto. Y una red en el
guardado: nunca se renombra una clave a otra que ya tiene otra línea del
lote. Test con las filas reales: con el código anterior, `IntegrityError`.

**Y dos acotamientos más, que salieron al revisar la segunda pasada.** El
cuadro del LOTE 1 de `0051` trae parejas de códigos con el mismo texto y
precio ("Semicambio izq (sencillo) DIRD-B1-54-190-0.11-CR-D", 22.712,17 €:
P-0166 en la p.21 y P-0178 en la p.22; y "dcha": P-0167 y P-0179). Son dos
entradas del catálogo, y la fusión por firma las juntaba:

- **Dentro de una misma tabla** (sus páginas de continuación incluidas,
  también las que repiten la misma cabecera en cada página, como este
  cuadro: la tabla nueva empieza cuando cambia el texto de la cabecera) dos
  códigos propios de verdad distintos ya no se funden nunca (el mismo código
  con ruido delante, "VP-63"/"P-63" en `6.21/28510.0109`, sí) -- el mismo principio que
  el guard de página que ya existía (`6.22/28510.0125`, P-133/P-137), para
  toda la tabla. Entre tablas distintas (el eco de una tabla de criterios o
  de impacto con su propia numeración, `6.24/28510.0180`) se sigue fundiendo,
  con el código de la primera.
- **Al guardar**, una línea que esta misma pasada ya guardó desde otro
  documento, con otro código propio, no se absorbe: el Contrato, que trae la
  misma tabla, se tragaba al guardar su P-0167 la P-0179 que acababa de
  guardar el anejo, y la borraba. Los restos de pasadas anteriores (códigos
  con ruido de pie de página, `6.23/28510.0042`) se siguen absorbiendo.

**"Lote nº1".** Revisando las líneas que la regla atribuía al expediente
(solo 20 en todo el corpus, una vez excluido el anejo de criterios):
`4.25/28510.0207` (LOTE 1) y `0208` (LOTE 2) se quedaban cada uno las
cuatro líneas de su cuadro, pero el documento dice "• Lote nº1:
Arrendamiento de vagones de bogies" (P-01, P-02) y "• Lote nº 2: …" (P-03,
P-04). El patrón de "LOTE N" no leía la forma "nº" (35 menciones en 6
documentos), y esas tablas parecían sin cabecera. Ya la lee: cada lote con
sus dos líneas, por la cabecera explícita. (Antes de esta parte los dos
expedientes mostraban también las cuatro, en su lote implícito.)

**Determinismo.** Con los dos acotamientos, dos pasadas seguidas daban el
mismo contenido línea a línea, pero 24 líneas cambiaban de `id` en cada
pasada (se borraban y se recreaban): el segundo miembro de cada pareja de
`0051`/`0060` (al guardar P-0166, la búsqueda por firma se tragaba la
P-0178 de la pasada anterior, que esa misma llamada iba a volver a
escribir), y 4 huérfanas de `4.25/28510.0208` (su Contrato y el del LOTE
1 tienen la misma tabla en la misma posición: guardar la del primero en su
lote borraba, por la clave de huérfana, la del segundo). Arreglados los
dos: la protección cubre también las claves que la propia llamada va a
escribir, y la limpieza de huérfanas superadas mira el documento.

Y una recuperación más, del mismo tipo de defecto de columnas: en el
ANEJO_1 de `0126` (p.23, LOTE 2), `pdfplumber` funde en 17 filas con
matrícula la celda de descripción con la anterior (`['P-101', '618050300',
'EN-54', None, 'UD.', ...]`). Antes lo tapaba la fusión con la línea del
mismo código del LOTE 1; separados los lotes, se quedaban sin descripción.
La recuperación "columna anterior" ya existente acepta ahora también esa
huella (celda en `None`, fila con matrícula).

## T4 — Excel

Las líneas del anejo de criterios tienen su propio motivo y su propia fila
en el Resumen, fuera de "pendientes de revisión" (no esperan ninguna
revisión: el documento dice de quién son), y ya no mandan su expediente a
revisión. Categorías nuevas también para "tabla sin título de lote, detrás
de la sección de otro lote" y "tabla de otro lote, cuyo expediente no está
en el catálogo".

## Pendiente al cerrar la tercera parte

- **Tabla no detectada:** "LOTE 6: RAM NORTE" de `6.22/28510.0016`
  (ANEJO_1 p.21), ver arriba. `pdfplumber` solo ve la tabla del LOTE 5 de
  esa página.
- **Residuo del localizador, visto de nuevo:** los Contratos de `0122` traen
  el pliego entero y el localizador solo abre sueltas las páginas de sus
  cuadros (p.122, 133); el ANEJO de `6.24/28510.0064` no abre las p.115-119
  del cuadro del LOTE 1 (sus materiales entran por el anejo de criterios,
  que en ese pliego sí va por lotes con cabecera).
- **El anejo de criterios se guarda una vez por documento y expediente**
  (el ANEJO y los dos Contratos de `0051` lo traen entero: 3 × 1.033 líneas
  sin lote en cada expediente de la familia). No sale en el Excel ni manda
  a revisión; es volumen en la base de datos, no un hueco.
- Siguen abiertos: huérfanas de lotes no declarados en un expediente de lote
  (decisión de producto del 12-09), `0058` sin importe de adjudicación, y
  las filas desalineadas de `ANEJO_ce1df15b39efdb8c.pdf`.
