# Análisis del corpus real: 186 documentos, 45 expedientes

Sesión de análisis puro (2026-09-03). No se ha tocado código de producción,
ni datos, ni tests: solo lectura contra el stack real (Postgres real, los
186 PDFs reales en el volumen `documentos`, vía scripts puntuales ejecutados
dentro del contenedor `api` y borrados al terminar). Todo lo que sigue está
verificado contra el corpus real salvo que se diga explícitamente lo
contrario.

**Estado de partida:** 45 expedientes procesados, 0 fallidos, 5
`completado`, 40 `pendiente_revision`, 1.731 líneas de catálogo.

**Metodología.** Para cada documento se reejecutó, como librería y sin
modificarla, la cascada real: `clasificar`, `localizar_paginas_candidatas`,
`extraer_tablas_pagina` y `mapear_cabecera` (solo la parte determinista —
nunca se llamó al modelo desde este análisis). Para el bloque ciego 1 se
reabrió cada PDF con `pdfplumber` sin el filtro de "código de precio con
forma P-NNN" que aplica `app/extraccion/tabla.py`, para ver qué encuentra
`find_tables()` de verdad y no solo lo que el motor actual sabe interpretar.

---

## Resumen ejecutivo, por impacto

| # | Hallazgo | Expedientes afectados | Esfuerzo |
|---|---|---|---|
| 1 | **Unión de los dos bloques ciegos** | **35 / 45 (78%)** | — (diagnóstico, no una causa única) |
| 2 | Guion Unicode (`‐` U+2010) en el código `P‑NNN`: el regex de `tabla.py` solo acepta el guion ASCII | 9 expedientes, 11 documentos | **Ajuste pequeño** |
| 3 | Pedidos derivados de acuerdo marco: expediente sin cuadro de precios ni baja propios, ambos viven en la MATRIZ | 14 expedientes (7 sin ningún documento + 7 con solo 2 anuncios PCSP) | **Desarrollo nuevo** (depende de la matriz) |
| 4 | Tercera plantilla de adjudicación (`L9_CM.32-FE`, Dirección Técnica) sin regla de clasificación propia: cae en `otro` o, peor, en un falso positivo de `pliego` — y por tanto nunca se le busca la baja aunque la traiga en texto claro | 2 expedientes confirmados | **Ajuste pequeño** |
| 5 | Segunda familia de baja: fórmula `Ct = Oferta × Kt × Coeficiente de baja` por pedido, no una baja única de lote | al menos 3 expedientes | **Desarrollo nuevo** (requiere diseño, sección 16 de CLAUDE.md) |
| 6 | Otros formatos de código de precio sin prefijo `P-` reconocible (`P1`, `L01-T01`, tablas sin columna de código) | 9 expedientes adicionales (dentro del bloque ciego 1) | **Desarrollo medio** (necesita muestreo, no hay un patrón único) |
| 7 | Cabeceras de cuadro de precios: la cascada funciona como está diseñada — 39/44 firmas resueltas por el mapeo determinista, las 5 restantes ya resueltas por el modelo y cacheadas | 0 (no es un problema, es la confirmación de que la sección 6 de CLAUDE.md funciona) | — |
| 8 | 8 documentos que no encajan en ningún patrón (`otro`), descritos uno a uno | 6 expedientes | Ver ficha por documento |

Los puntos 2 y 4 son los dos hallazgos con mejor relación impacto/esfuerzo:
juntos tocan 11 expedientes con cambios acotados a una función cada uno.
Los puntos 3, 5 y 6 son estructurales y no se resuelven con un parche.

---

## 1. Inventario de formatos

Agrupado por lo que **encuentra el clasificador actual hoy**, no por el
`tipo_documento` que el scraper le puso al fichero (CLAUDE.md sección 3).
186 documentos, ningún error de lectura ni de extracción de texto.

| Tipo (clasificador) | Subtipo real (marcador que ganó) | Docs | Expedientes | ¿Lo reconoce el clasificador? |
|---|---|---|---:|---:|---|
| `contrato` | contrato firmado | 41 | 28 | Sí |
| `pliego` | Pliego de Prescripciones Técnicas | 28 | 27 | Sí |
| `pliego` | Documento de Pliegos (índice PCSP) | 27 | 27 | Sí — pero es un índice sin datos de adjudicación, ver sección 3 |
| `pliego` | Pliego de Cláusulas Administrativas | 27 | 26 | Sí (1 de los 27 es un falso positivo, ver hallazgo 4) |
| `propuesta_lc27` | Propuesta de Adjudicación (LC.27) | 21 | 21 | Sí |
| `anuncio_pcsp` | Anuncio de adjudicación | 11 | 11 | Sí |
| `anuncio_pcsp` | Anuncio de formalización de contrato | 10 | 10 | Sí |
| `anejo` | Anejo suelto ("Criterios técnicos...") | 9 | 9 | Sí |
| `otro` | Sin patrón — 8 documentos distintos | 8 | 6 | No — ver sección 5 |
| `resolucion_adjudicacion` | Resolución (L9_AF.01-FE, con "resuelve") | 4 | 4 | Sí |

**Verificado, no en CLAUDE.md todavía:**

- La familia PCSP (`anuncio_pcsp`) se reparte casi por la mitad entre
  "Anuncio de adjudicación" (11) y "Anuncio de formalización de contrato"
  (10) — confirma la nota del docstring de `clasificador.py` de que ambos
  títulos comparten anatomía y merecen la misma ruta de extracción.
- "Documento de Pliegos" (27 docs, 27 expedientes — prácticamente uno por
  expediente) es en sí mismo un formulario PCSP sin datos de adjudicación
  (docstring de `clasificador.py`); no aporta ni importe ni baja ni cuadro
  de precios en ningún caso muestreado. Es ruido necesario de descartar,
  no una fuente de datos.
- **Tercera plantilla de adjudicación, `L9_CM.32-FE` / "INFORME-PROPUESTA
  DE ADJUDICACIÓN DE CONTRATO" (Dirección Técnica), confirmada con 2
  documentos reales** (`6.23/28510.0104` y `6.24/28510.0047`): misma
  anatomía en los dos — presupuesto, tabla "RAZÓN SOCIAL / BAJA OFERTADA /
  ORDEN CLASIFICATORIO" con los licitadores clasificados, y la frase
  "con una baja del N% a todos los precios unitarios" para el
  adjudicatario. Es al mismo tipo de hecho que una Propuesta LC.27 o una
  Resolución (declara baja y adjudicatario), pero el clasificador no la
  reconoce como tal: **cae en `otro` en el mejor caso, y en un falso
  positivo de `pliego` en el peor** — ver hallazgo 4 más abajo.
- El marcador `L9_AF.01-FE` (plantilla real de la Resolución de
  Adjudicación, CLAUDE.md sección 17) aparece exactamente en los 4
  documentos clasificados como `resolucion_adjudicacion`: coherente, sin
  sorpresas ahí.

---

## 2. Los dos bloques ciegos

### 2a. Expedientes sin ninguna línea de catálogo: 33 de 45 (73%)

Causas, sin usar la categoría `tipo_documento` como filtro — se reabrió
cada PDF con `pdfplumber` puro:

| Causa | Expedientes | Esfuerzo |
|---|---:|---|
| Hay tablas con código de precio, pero en formato **`P‐NNN` con guion Unicode** (U+2010), no el guion ASCII que exige `_CODIGO_PRECIO_RE` de `tabla.py` | **9** | **Ajuste pequeño** |
| Hay tablas con código de precio en **otro formato** (sin prefijo `P-`, o sin columna de código reconocible) | **9** | Desarrollo medio |
| Página(s) candidatas por densidad numérica, pero `pdfplumber.find_tables()` no encuentra ninguna tabla real en ellas | **8** | Desarrollo medio — ver más abajo |
| Ninguna página candidata en ningún documento del expediente | **7** | Estructural — ver hallazgo 3 |

**Verificado: el guion Unicode (hallazgo #2).** El código de precio en
varios documentos reales (balasto, carril, armarios eléctricos, cableado)
se extrae de `pdfplumber` como `P‐001`, `P‐1`, `P‐017` — el carácter entre
`P` y el número es U+2010 (HYPHEN), no U+002D (HYPHEN-MINUS). El regex
`^P-\d+$` de `app/extraccion/tabla.py` (`_CODIGO_PRECIO_RE`) exige el ASCII
literal, así que `_es_fila_de_datos` nunca encuentra la fila de datos,
`extraer_tablas_pagina` descarta la tabla entera como "espuria" y el
documento no aporta ninguna línea. Confirmado tabla a tabla en 9
expedientes / 11 documentos (`6.23/28510.0018`, `0066`, `0102`, `0109`,
`0129`, `0139`, `6.24/28510.0117`, `0124`, `0130`) — en varios de ellos la
misma cabecera ya está resuelta correctamente por el mapeo determinista, el
único fallo es el filtro de fila de datos. **Arreglo acotado a una función**:
aceptar en el regex los guiones Unicode habituales en texto extraído de PDF
(U+2010 HYPHEN, U+2011 NON-BREAKING HYPHEN, U+2012 FIGURE DASH, U+2013 EN
DASH) o normalizar el carácter antes de comparar.

**Otros formatos de código (9 expedientes restantes de la misma causa).**
Sin patrón único — muestras reales:
- `6.24/28510.0047_ANEJO_1.pdf`: códigos `P1`, `P2` (sin separador alguno).
- `6.24/28510.0094_Documento_de_Pliegos_1.pdf`: códigos `L01-T01`,
  `L02-T01`, `L03-T01` (traviesas, prefijo de lote+tipo, no de precio).
- `6.24/28510.0008_ANEJO_3.pdf`: la tabla no trae columna de precio ni de
  código en absoluto — es la tabla de características técnicas sin precio
  ya documentada en CLAUDE.md sección 17.2 (comportamiento correcto, esta
  tabla no debería aportar líneas: el expediente `6.24/28510.0008` **no**
  está en este bloque ciego porque su `ANEJO_1.pdf` sí aporta las líneas
  reales).

No hay una única expresión regular que cubra los tres casos: antes de tocar
código aquí hace falta muestrear más documentos con este síntoma para saber
si `P1`/`P2` y `L01-T01` son variantes puntuales o una familia con volumen
propio.

**Páginas candidatas sin tabla real (8 expedientes).** Todos del mismo
patrón: expedientes con solo 2 documentos (`ADJUDICACION_1.pdf` +
`CONTRATO_1.pdf`, ambos de 3 páginas, ambos clasificados `anuncio_pcsp`,
~18 KB). El localizador marca 1-2 páginas como candidatas (probablemente
por la densidad numérica de las cifras de presupuesto en la propia página
del formulario), pero no hay ningún cuadro de precios real que extraer:
son formularios PCSP puros, no traen anejo. **Esto coincide exactamente con
el patrón "pedido derivado de acuerdo marco" del hallazgo 3** — ver abajo.

**Ninguna página candidata en absoluto (7 expedientes).** Los 7 expedientes
tienen **0 documentos descargados** en la base de datos
(`3.24/28520.0129`, `2.25/28520.0161`, `4.24/27520.0090`,
`2.24/28520.0128`, `3.24/20810.0090`, `6.25/28510.5001_01`,
`3.25/27520.0055`). No es un problema de extracción: es un hueco de
scraping/descarga, categoría distinta a las tres anteriores. **Sin
verificar la causa raíz** (no se ha investigado por qué el scraping no
descargó nada para estos 7 — fuera de alcance de esta sesión de análisis
puro).

**Hallazgo 3, estructural: pedidos derivados de acuerdo marco (14
expedientes entre las dos últimas filas de la tabla).** Los 7 expedientes
con "páginas candidatas sin tabla real" tienen todos la misma huella: 2
documentos PCSP únicamente, `codigo_expediente` con formato de MATRIZ
(`2.18/04703.00NN`, `2.24/04110.00NN` — no el formato habitual
`6.2N/28510.0NNN`), y el propio texto del Anuncio PCSP declara un "Número
de Expediente" **distinto** del `codigo_expediente` guardado (p.ej.
`2.18/04703.0019` en base de datos, pero el Anuncio dice "Número de
Expediente 6.24/28510.0103" dentro del texto). **Esto es exactamente el
caso ya documentado en CLAUDE.md sección 17.1** (el pedido derivado
`6.24/28510.0103`, cuya matriz es `2.18/04703.0019`) — confirma con 7
casos más que no es una anomalía aislada, sino un patrón recurrente del
corpus: el cuadro de precios y la baja de un pedido derivado de acuerdo
marco no están en los documentos del pedido, están en los de la MATRIZ.
Mientras el motor no sepa "seguir" a la matriz cuando el pedido no trae
sus propios datos, estos expedientes seguirán vacíos por diseño, no por
un fallo puntual. Es la pieza pendiente más grande del sistema: no se
arregla con un ajuste local, necesita decidir cómo (y si) el motor cruza
un pedido con el catálogo de su matriz.

### 2b. Expedientes con licitación = adjudicación pero sin baja: 12 de 45 (27%, tras descartar 1 falso positivo)

La consulta bruta devolvió 13, pero **`6.25/28510.0027` es un falso
positivo de esta pregunta**: es el expediente multi-lote ya resuelto en
CLAUDE.md sección 19 (LOTE 1 al 7,13%, LOTE 3 al 1,18%) — `baja_global`
queda `None` **a propósito** porque los lotes tienen bajas distintas
(`baja_variable_por_lote = true`, verificado en base de datos), no porque
no se haya encontrado ninguna baja. Los 12 restantes sí son un vacío real.

**Solapamiento con el bloque ciego 1: 10 de los 12 son también expedientes
sin catálogo** (los 7 pedidos derivados de acuerdo marco + `6.23/28510.0018`,
`0102`, `6.24/28510.0047`). Solo 2 casos (`6.23/28510.0104`,
`6.25/28510.0016`) tienen catálogo completo pero les falta la baja — son
las fichas más limpias para entender la causa aislada de este bloque, sin
mezclarla con el bloque 1.

Se buscó, con un patrón mucho más laxo que `_BAJA_RE` (cualquier frase con
"baja" como palabra completa, sin exigir la forma "baja del N% ...
precios unitarios"), qué redacciones reales existen en estos 12
expedientes. 208 fragmentos con "baja" real (se descartaron ~260 falsos
positivos: el regex ingenuo `baja` como substring cae dentro de
"tra**baja**dores/tra**baja**dor/tra**baja**r", que aparece decenas de
veces en las cláusulas de plantilla laboral de cada pliego). De los 208,
las redacciones agrupadas relevantes son:

| Redacción / patrón | Expedientes | Ya la captura `_BAJA_RE` |
|---|---|---|
| "con una baja del **N%** a todos los precios unitarios" (tabla RAZÓN SOCIAL / BAJA OFERTADA de la 3ª plantilla, hallazgo 4) | `6.23/28510.0104` (20%), `6.24/28510.0047` (0,13%) | **No la alcanza**: el documento nunca llega a `extraer_baja_declarada` porque su `tipo_documento` no es de los tres que se escanean (`propuesta_lc27`, `resolucion_adjudicacion`, `contrato`) |
| "Se han excluido ofertas por ser anormalmente bajas" (boilerplate del formulario PCSP, sin ningún % de baja real) | 7 pedidos derivados de acuerdo marco | No aplica — no es la baja del expediente, es una cláusula estándar |
| Fórmula **`Ct = (Oferta) × Kt × Coeficiente de baja`** por pedido, con "Coeficiente de baja... ofertado por el licitador para cada pedido, debe ser un valor ≤ 1" | `6.23/28510.0018`, `6.23/28510.0102`, `6.25/28510.0016` | No — es un modelo de baja **distinto**, ver más abajo |
| "Baja Media (BM)" / "Baja de Referencia (BR)" — fórmula de cálculo de ofertas anormalmente bajas a efectos de exclusión, boilerplate del pliego | mismos 3 expedientes de la fila anterior | No aplica — cláusula de admisión de ofertas, no la baja adjudicada |

**Hallazgo 4 (repetido del inventario, con el dato de baja ya
verificado).** `6.23/28510.0104` es un caso especialmente claro del bug de
clasificación: su `ADJUDICACION_1.pdf` es la 3ª plantilla
(`L9_CM.32-FE`), y termina clasificado como `pliego` — no `otro` como el
resto de esa familia — por un **falso positivo concreto y verificado**: la
página 1 contiene, en prosa, la frase "el determinado en **Pliego de
Cláusulas Administrativas Particulares** del contrato" (hablando del plazo
de ejecución, nada que ver con el tipo de documento). El clasificador
(`_buscar`, sección 5 de la cascada) solo comprueba si el marcador aparece
en *cualquier parte* de la página, no si es el título — así que una
mención de pasada de "Pliego de Cláusulas Administrativas" en medio de un
párrafo dispara la regla 5 antes de que el documento llegue a la regla 6
(`otro`). El texto de esta misma página trae, literal, "con una baja del
**20%** a todos los precios unitarios" — el dato que se busca está a la
vista, pero el documento nunca se somete a `extraer_baja_declarada` por la
doble barrera: mal clasificado, y aunque no lo estuviera, `pliego` no
está entre los tipos que se escanean para baja. **Arreglo acotado**: dar a
la 3ª plantilla su propia regla en `clasificador.py` (marcador
`"l9_cm.32-fe"` o `"informe-propuesta de adjudicacion de contrato"`,
verificados en los dos documentos reales) y añadir su tipo (o alias) a
`_TIPOS_CON_BAJA_DECLARADA` en `orquestador.py`. `_BAJA_RE` ya captura la
redacción sin cambios ("con una baja del N% a todos los precios
unitarios" encaja en el patrón existente).

**Hallazgo 5, segunda familia de baja (`6.23/28510.0018`, `0102`,
`6.25/28510.0016`).** Estos tres contratos (todos de importe muy alto:
11.700.000 € de licitación y adjudicación, idénticos) no declaran una
baja única de lote — declaran una **fórmula de cálculo por pedido**,
`Ct = (Oferta presentada por el licitador) × Kt × Coeficiente de baja`,
donde el "Coeficiente de baja" lo oferta el licitador en cada pedido
individual bajo el acuerdo marco, con la restricción de ser ≤ 1. Esto
coincide con la sospecha, sin verificar, de la sección 16 de CLAUDE.md
("puede haber una segunda familia con precio ofertado por línea"): aquí no
es "por línea", es **por pedido dentro del acuerdo marco**, pero el efecto
es el mismo — no hay una sola baja de lote que aplicar a todos los precios
unitarios del expediente. **No se ha intentado extraer un valor concreto
de baja de estos tres**: no hay uno solo que extraer, es un modelo de
cálculo, no un dato declarado. Diseñar cómo (o si) el catálogo representa
"baja variable por pedido, calculada con esta fórmula" es trabajo de
diseño, no un ajuste de extracción.

---

## 3. Dónde vive cada dato en cada formato

Verificado por formato — "—" significa que ese dato **no existe** en ese
tipo de documento en ningún caso muestreado, no que falte extraerlo.

| Formato | Importe licitación | Importe adjudicación | Baja declarada | Cuadro de precios | Identificación de lote |
|---|---|---|---|---|---|
| Anuncio PCSP | Etiqueta fija "Presupuesto base de licitación → Importe (sin impuestos)" | Etiqueta fija "Importes de Adjudicación → Importe total ofertado" | — (nunca la declara; solo la cláusula boilerplate de "ofertas anormalmente bajas") | — | — |
| Propuesta LC.27 | Etiqueta fija "Presupuesto de licitación:" | Etiqueta fija "Base imponible" | Texto libre, patrón `_BAJA_RE` | — | Solo si multi-lote ("En el LOTE N", CLAUDE.md sección 19); nunca visto en LC.27 real en este corpus |
| Resolución (`L9_AF.01-FE`) | Tabla "Presupuesto de licitación: LOTE N ... €" (solo si multi-lote) | Bloque "RESUELVE" por lote, o etiqueta "Base imponible" a nivel de expediente | Texto libre, mismo patrón que LC.27 ("con una baja del N% aplicable al conjunto de precios unitarios") | — | Sí, es la única plantilla con el patrón multi-lote verificado en el corpus |
| **3ª plantilla `L9_CM.32-FE`** (Dirección Técnica) | "(A) BASE IMPONIBLE" en la cabecera del formulario | Implícito (mismo importe que la licitación en los 2 casos verificados) | **Sí, en texto claro** ("con una baja del N% a todos los precios unitarios") — hoy inalcanzable, ver hallazgo 4 | — | No visto |
| Contrato firmado | **No se extrae hoy** (`_extraer_campos_expediente` no tiene rama para `contrato`) | **No se extrae hoy** | Texto libre, mismo patrón `_BAJA_RE` — sí se escanea | Ocasional: `find_tables()` encuentra tablas en la portada ("PARTES CONTRATANTES") o en anualidades, nunca el cuadro de precios real | No visto |
| Pliego (Cláusulas / Prescripciones / Documento de Pliegos) | — | — | — | **Sí — es donde vive el cuadro real** en la mayoría de expedientes (el `*_ANEJO_N.pdf` es casi siempre, en realidad, un pliego completo, CLAUDE.md sección 3) | Solo si multi-lote, por cabecera "LOTE N" en la franja que precede a la tabla |
| Anejo suelto | — | — | — | Sí, cuando existe como documento independiente | Igual que pliego |

**Gap verificado y no documentado hasta ahora: el Contrato firmado no
aporta importes.** `_extraer_campos_expediente` en `orquestador.py` solo
tiene ramas para `anuncio_pcsp` y para `(propuesta_lc27,
resolucion_adjudicacion)` — un expediente cuyo **único** documento con
etiquetas fijas fuera el contrato (sin Anuncio PCSP, sin Propuesta LC.27,
sin Resolución) se quedaría sin importe de licitación ni de adjudicación
de ningún sitio, aunque el contrato normalmente sí declara la baja. No se
ha encontrado ningún expediente real en este corpus que dependa
exclusivamente del contrato para el importe (siempre hay al menos un
Anuncio PCSP o una Propuesta/Resolución), así que hoy es un hueco teórico,
no un caso fallado — pero es la misma clase de hueco que ya se cerró para
importes de Propuesta/Resolución (CLAUDE.md sección 18, "de paso, mismo
cambio").

---

## 4. Cabeceras de cuadro de precios

**44 firmas de cabecera distintas**, contadas solo sobre tablas que ya
pasan el filtro de "fila de datos con código `P-NNN` en ASCII" (es decir,
**no incluye** las cabeceras de las tablas afectadas por el guion Unicode
del hallazgo 2 — esas nunca llegan a `extraer_tablas_pagina`, así que sus
cabeceras reales son, hoy, un universo no contado; arreglar el hallazgo 2
añadirá cabeceras nuevas a este catálogo, probablemente ya cubiertas por
los mismos alias deterministas visto que el resto de la columna es idéntica
en las muestras — pero sin verificar hasta que se arregle).

| | Firmas | Apariciones (tabla × página) |
|---|---:|---:|
| Resueltas por el mapeo determinista | **39** | 352 |
| Necesitan modelo | **5** | 34 |
| Irreconocibles (ni determinista ni modelo) | **0** | 0 |

Las 5 que necesitan modelo **ya están resueltas y cacheadas** en
`cache_mapeo_cabecera` con `origen = "modelo"` de un procesamiento real
anterior — confirma en vivo que la cascada de la sección 6 de CLAUDE.md
funciona como está diseñada: cero cabeceras irreconocibles, el modelo se
llama solo cuando hace falta y una vez por firma.

Por qué esas 5 no resuelven en determinista, verificado caso a caso:

- **3 firmas (22 apariciones), balasto/similar**: cabecera
  `"CODIFICACIÓN DEL PRECIO"` — normalizado a `codificacion del precio`,
  que **no contiene la subcadena `codigo`** (contiene `codific...`, no
  `codig-o`), así que ningún alias de `_ALIAS_DETERMINISTAS["codigo_precio"]`
  la reconoce. Es un alias real y verificado que falta en
  `mapeo_cabecera.py` — **ajuste pequeño**: añadir `"codificacion del
  precio"` (o `"codificacion"`) a la lista de alias de `codigo_precio`.
  Con este único alias añadido, las 3 firmas pasarían a resolverse en
  determinista sin tocar nada más.
- **2 firmas (2 apariciones), `6.24/28510.0008_ANEJO_3.pdf`**: la tabla de
  características técnicas sin columna de precio ya documentada en
  CLAUDE.md sección 17.2 — **no es un fallo**, es exactamente el caso que
  el mapeo determinista está diseñado a rechazar (`CAMPOS_OBLIGATORIOS`
  exige `precio_unitario`, que aquí no existe) para que decida el modelo,
  que ya devuelve `null` correctamente.

**Ruido de extracción visible en las propias cabeceras** (no afecta a la
resolución, pero vale la pena registrarlo): al menos 4 firmas de las 44
traen una doble letra inicial por columna — `"CCÓDIGO DE PRECIO"`,
`"NNº MATRÍCULA"`, `"DDESCRIPCIÓN..."` — un artefacto de extracción de
`pdfplumber` en ciertos documentos (probablemente una celda de cabecera
solapada con un borde de tabla). El mapeo determinista las resuelve igual
porque los alias son subcadenas (`"codigo de precio"` sigue apareciendo
dentro de `"ccodigo de precio"`), así que no es un problema práctico hoy,
pero explica por qué hay más firmas (44) que variantes de redacción reales
del corpus.

---

## 5. Lo que no encaja en nada

8 documentos, 6 expedientes. Descritos uno a uno — son pocos y heterogéneos,
no forman un patrón nuevo:

1. **`6.23/28510.0139_ANEJO_3.pdf`** — "ANEJO Nº 2: CRITERIOS TÉCNICOS
   PARA SUMINISTRO DE BALASTO...". Es un anejo real con nombre de anejo,
   pero no dispara la regla 6 del clasificador (`"criterios tecnicos para
   el suministro"`, sin la "de" que trae este título exacto:
   "CRITERIOS TÉCNICOS **PARA** SUMINISTRO"). Variante de redacción del
   mismo marcador, no un documento distinto — **ajuste trivial** si
   interesa reconocerlo (no aporta cuadro de precios él mismo, es
   descriptivo).
2. **`6.24/28510.0047_ADJUDICACION_1.pdf`** y su gemelo clasificado
   `pliego` — la 3ª plantilla `L9_CM.32-FE`, ya cubierta en el hallazgo 4.
   No hace falta repetirla aquí como "sin patrón": tiene patrón, solo le
   falta la regla.
3. **`6.24/28510.0117_ANEJO_4.pdf`** (1 página) — "NOTA ACLARATORIA":
   una fe de erratas suelta sobre qué debe contener el sobre nº 2. No es
   ninguna de las plantillas del dominio, es correspondencia administrativa
   puntual. No se le conoce un patrón repetible en el resto del corpus.
4. **`6.24/28510.0117_ANEJO_3.pdf`** (13 páginas) — "JUSTIFICACIÓN DE
   PARTIDAS ALZADAS EN CONTRATOS DE SERVICIOS Y SUMINISTROS": documento de
   justificación de partida alzada (CLAUDE.md sección 2, "es legítima, no
   un error") como anejo independiente en vez de sección de un pliego. Sin
   otro caso igual en el corpus muestreado — no se sabe si es un patrón con
   volumen propio o un documento aislado de este expediente.
5. **`6.24/28510.0124_ANEJO_3.pdf`** (3 páginas) — "INFORMACIÓN A ADJUNTAR
   A LA LICITACIÓN", con fecha y una lista de tres expedientes distintos en
   la cabecera (`6.24/28510.0124`, `3.24/27510.0138`, `3.24/27510.0181`):
   parece un anejo compartido entre varios expedientes relacionados, no
   propio de este. Sin verificar si los otros dos expedientes citados están
   en el corpus.
6. **`6.24/28510.0203_ANEJO_3.pdf`** (1 página) — "Nota aclaratoria" sobre
   descarga de traviesas en destino: mismo patrón que el documento 3
   (correspondencia puntual de una página), expediente distinto.
7. **`6.20/28510.0136_ANEJO_2.pdf`** (**100 páginas**, primera línea
   vacía) — el documento más grande y más opaco del corpus: 100 páginas
   sin que ninguna alcance el umbral de página candidata y sin ningún
   marcador de clasificación en las 2 primeras páginas. **Sin
   inspeccionar el contenido completo** (fuera del alcance de esta
   sesión de análisis a nivel de corpus) — solo se sabe que no dispara
   ninguna regla existente y que no parece traer cuadro de precios. Es el
   documento con más incertidumbre de todo el hallazgo 5: antes de decidir
   nada sobre él hace falta abrirlo y leerlo, no inferir desde fuera.
8. **`6.20/28510.0136_ANEJO_4.pdf`** (1 página) — una corrección de código
   CPV ("se entiende que figura el código CPV: 313000009, en lugar del
   código 3494700000-8"): fe de erratas administrativa, mismo patrón que
   los documentos 3 y 6.

**Patrón dentro de "lo que no encaja":** de los 8, 5 son notas/fes de
erratas de una sola página (documentos 3, 6, 8, y en menor medida el 1) —
correspondencia administrativa puntual sin cuadro de precios ni dato de
adjudicación, que probablemente conviene reconocer como categoría propia
("nota aclaratoria") solo para que dejen de contar como ruido en la cola
de revisión, no porque aporten datos. Los otros 3 (partidas alzadas,
información compartida entre expedientes, y el documento de 100 páginas)
son heterogéneos y no forman categoría.

---

## Lo que queda sin verificar

- Causa raíz de por qué 7 expedientes no tienen ningún documento
  descargado (fuera de alcance: es un problema de scraping, no de
  extracción).
- Si `P1`/`P2` (sin separador) y `L01-T01` son variantes con volumen propio
  o casos aislados — hace falta más muestra.
- Contenido completo de `6.20/28510.0136_ANEJO_2.pdf` (100 páginas).
- Si el importe de licitación puede depender solo del Contrato en algún
  expediente fuera de este corpus fijo (hoy es un hueco teórico, sin caso
  real que lo confirme).
- Si `2.18/04703.00NN` y `2.24/04110.00NN` son siempre matrices de acuerdo
  marco, o si alguno de los 7 es un expediente propio con un problema de
  scraping distinto — no se ha cruzado cada uno contra la Plataforma para
  confirmarlo uno a uno, se infiere del patrón (2 documentos, formato de
  código, "Número de Expediente" distinto en el texto) que se repite
  idéntico en los 7.

---

## Arreglos de los hallazgos 2 y 4 (sesión 2026-09-03)

Sesión de código sobre los dos hallazgos de mejor relación impacto/esfuerzo
del resumen ejecutivo. Verificado contra el stack real (contenedor Linux,
Postgres real, worker real) reprocesando los 45 expedientes desde cero
después del cambio, no solo con tests aislados.

### 1. Guion Unicode en el código de precio

`_CODIGO_PRECIO_RE` seguía exigiendo el guion ASCII. Arreglo de fondo, no
solo la expresión regular: `app.extraccion.normalizacion.normalizar_guiones`
es ahora el único punto de esa normalización (U+2010 HYPHEN, U+2011 NON-BREAKING
HYPHEN, U+2012 FIGURE DASH, U+2013 EN DASH, U+2014 EM DASH → guion ASCII), y
lo usan tanto el filtro de fila de datos de `tabla.py` como
`limpiar_codigo_celda` — así el `codigo_precio` que llega al catálogo queda
siempre igual sin importar qué guion trajera la extracción (verificado en
producción: `P‐01` en el PDF real se guarda como `P-01`). Revisadas todas las
demás expresiones regulares del proyecto que tocan guiones
(`_NO_DIGITO_NI_SEPARADOR` de importes, ninguna otra con forma `P-\d+`):
ninguna otra tenía el mismo defecto.

### 2. Tercera plantilla L9_CM.32-FE

Nuevo tipo `TipoDocumento.propuesta_dt` (migración `0008`, no un alias de
`propuesta_lc27`: declara el mismo tipo de hecho pero con anatomía propia).
Regla de clasificador nueva por el marcador único `"l9_cm.32-fe"`, insertada
antes de la regla de pliego. `propuesta_dt` añadido a
`_TIPOS_CON_BAJA_DECLARADA` en el orquestador — sin esto, aunque el
clasificador reconociera la plantilla, su baja nunca se llegaba a buscar.
`_BAJA_RE` capturó la redacción de los dos documentos reales sin ningún
cambio, confirmando la hipótesis del hallazgo 4.

**Falso positivo de `pliego` corregido de forma general, no solo para este
caso.** Se midió la posición de "pliego de clausulas administrativas" en las
188 páginas del corpus completo: las 23 apariciones reales como título
abren la página en la posición 0 del texto normalizado; las 3 apariciones
que son solo una mención de pasada (`6.23/28510.0104_ADJUDICACION_1.pdf`,
`6.20/28510.0136_CONTRATO_1.pdf`, `6.25/28510.0016_CONTRATO_1.pdf`) aparecen
en la posición 265, 607 y 1662. `_buscar_titulo` (nueva, en
`clasificador.py`) exige que el marcador esté a 50 caracteres o menos del
principio de la página — solo para esta frase: se comprobó que
"pliego de prescripciones tecnicas" y "documento de pliegos" sí aparecen
lejos del principio en documentos reales correctamente clasificados
(portadas con índice antes del título), así que la restricción no se aplicó
ahí para no romper ningún caso ya correcto.

### Verificación: los 45 expedientes reprocesados desde cero

Estado antes de esta sesión: 5 `completado`, 40 `pendiente_revision`, 0
`fallido`, 1.731 líneas de catálogo. Después de reconstruir las imágenes de
`api`/`worker` con el código nuevo, aplicar la migración `0008` y reencolar
`extraer_expediente` para los 45:

| | Antes | Después |
|---|---:|---:|
| `completado` | 5 | **10** |
| `pendiente_revision` | 40 | **35** |
| `fallido` | 0 | 0 |
| Líneas de catálogo | 1.731 | **2.041** (+310) |

**Los 9 expedientes del guion Unicode**: los 9 pasan a tener líneas de
catálogo (0 antes, con `_es_fila_de_datos` descartando la tabla entera como
espuria). 4 quedan `completado` (`6.23/28510.0066` 9 líneas baja 3,00 %;
`6.23/28510.0109` 8 líneas baja 7,20 %; `6.23/28510.0129` 6 líneas baja
0,50 %; `6.24/28510.0124` 6 líneas baja 4,50 %, esta última ya declarada por
su Resolución, ajena al guion). Los otros 5 siguen en `pendiente_revision`,
pero ya no por falta de líneas — por motivos distintos y ya documentados en
este informe, no por el arreglo:

- `6.23/28510.0018` (26 líneas) y `6.23/28510.0102` (26 líneas): sin baja
  declarada porque son, tal como predice el hallazgo 5, dos de los tres
  expedientes de la segunda familia de baja (fórmula `Ct = Oferta × Kt ×
  Coeficiente de baja` por pedido, sin una baja única de lote que extraer)
  — confirmado ahora con datos reales del catálogo, no solo con el patrón de
  texto.
- `6.23/28510.0139` (6 líneas), `6.24/28510.0117` (103 líneas) y
  `6.24/28510.0130` (120 líneas): la validación de la sección 12 de CLAUDE.md
  hizo su trabajo — la baja declarada en texto no cuadra con la que resulta
  de licitación/adjudicación (5,07 % declarado contra 68,64 % de los
  importes en `0139`; 24,99 % contra 90,00 % en `0117`; 0,00 % contra
  84,44 % en `0130`), así que van a revisión en vez de aceptarse en
  silencio. Los saltos tan grandes entre importes apuntan al mismo patrón
  del hallazgo 3 (pedido derivado de acuerdo marco) más que a un error de
  transcripción; sin verificar caso a caso, fuera de alcance de esta sesión.

**Los 2 expedientes de la plantilla L9_CM.32-FE** (no 3: el corpus completo
solo trae 2 documentos reales con este marcador, confirmado consultando
`documentos.tipo_documento = 'propuesta_dt'` tras el reproceso —
`6.23/28510.0104` y `6.24/28510.0047`, los mismos dos que ya citaba el
hallazgo 4). `6.23/28510.0104` queda `completado`, baja 20,00 %: el falso
positivo de `pliego` está resuelto de punta a punta, no solo en el test
unitario. `6.24/28510.0047` extrae su baja correctamente (0,13 %) pero
sigue en `pendiente_revision` por un motivo ajeno a la clasificación: ningún
documento de este expediente aporta líneas de catálogo (no hay cuadro de
precios reconocible en sus otros documentos) — mismo síntoma que otros
expedientes sin `ANEJO`/`Pliego` con tabla real, no una regresión de este
arreglo.

**Matrículas que aparecen en más de un expediente**: de las 2.041 líneas,
solo 13 matrículas se repiten entre expedientes distintos — las 13 de
carril (`601020180`…`613000033`), compartidas entre `6.23/28510.0018`,
`6.23/28510.0102` y `6.25/28510.0016`. Ningún otro material del catálogo
actual aparece en más de un expediente. Dato notable: dos de los tres
expedientes que comparten estas matrículas (`0018` y `0102`) no tenían
ninguna línea de catálogo antes de esta sesión — el arreglo del guion
Unicode es lo que hace posible, por primera vez, cruzar el precio de estos
materiales entre expedientes (la pregunta real de ADIF, CLAUDE.md sección
11.5).

### Fixtures de regresión añadidos

`engine/tests/fixtures/pdfs/`, con su entrada en `tests/fixtures/__init__.py`
y tests que fallarían sin el arreglo correspondiente:

- `6.23_28510.0018_ANEJO_1.pdf` (`ANEJO_PRECIOS_CARRILES_GUION_UNICODE`):
  página 12, cuadro de precios de carriles con código `P‐01`..`P‐13` en
  guion Unicode real — `tests/extraccion/test_tabla.py`.
- `6.23_28510.0104_ADJUDICACION_1.pdf`
  (`PROPUESTA_DT_CON_FALSO_POSITIVO_PLIEGO`): el documento real que
  destapó el falso positivo de `pliego` — `tests/extraccion/test_clasificador.py`
  y `tests/extraccion/test_baja.py`.
- `6.24_28510.0047_ADJUDICACION_1.pdf` (`PROPUESTA_DT_SIN_FALSO_POSITIVO`):
  mismo formato sin la mención de pasada al pliego — mismos dos ficheros de
  test.
