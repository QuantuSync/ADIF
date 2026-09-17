# Sesión 2026-09-17 — Documentos escaneados, código del material, pendientes

Cifras medidas contra la base de datos real y los PDF reales.

## Bloque 1 — Expedientes con documentos escaneados (análisis, sin implementar)

### Cuántos

"Escaneado" = el criterio del sistema (`app.extraccion.texto.es_documento_escaneado`:
menos de 10 caracteres de texto en todo el documento), medido sobre la caché
de texto de los 1.623 documentos del corpus. Solo hay 1 documento más con la
mitad de las páginas sin texto (7 páginas): el fenómeno es de documento
entero, no de páginas sueltas.

| | Corpus completo |
|---|---|
| Documentos escaneados | **140** (de 1.623) |
| Páginas | **5.298** |
| Expedientes con algún documento escaneado | **113** |
| … de ellos, sin ninguna línea de catálogo | **85** |
| … con líneas (el escaneado es un documento secundario) | 28 |

Por año del código (los 113): 2015 2, 2016 10, 2017 15, 2018 15, **2019 60**,
2020 4, 2024 3, 2025 3. Los de 2024-2025 comparten un único pliego
administrativo escaneado (100 páginas, `6.20/28510.0136_ANEJO_2.pdf`) y ya
tienen sus líneas por otros documentos. **Es un fenómeno de 2016-2019**, no
algo que vaya a crecer con las publicaciones nuevas.

### Qué documentos son

Clasificados mirando las páginas (primera, ¼, ½, ¾ y última de cada uno):

| Tipo | Documentos | Aporta catálogo |
|---|---|---|
| Pliego de prescripciones técnicas (PPT) | **60** | sí, casi siempre al final |
| Pliego administrativo / cuadro de características | **60** | no ("Relación de artículos: NO PROCEDE", modelo DEUC en blanco) |
| Resolución de adjudicación / contrato | 10 | no, pero traen la baja |
| Actas de mesa, criterios de solvencia, informes | 8 | no |
| Planos / fichas técnicas (una de 670 páginas) | 2 | no |

El nombre del fichero no ayuda: tanto el PPT como el administrativo se llaman
`ANEJO_1`/`ANEJO_2` según el expediente.

### Cuántas líneas se pierden

Se contaron, página a página, las filas de artículo de los cuadros de los 60
PPT (todas sus 1.362 páginas renderizadas):

- **~1.800 filas con precio** (y ~50 sin precio) en 54 de los 60 PPT; 6 no
  traen cuadro (solo presupuesto global o normas).
- **Todas son de expedientes que hoy tienen 0 líneas**: ningún expediente
  con líneas pierde filas por esto. **67 expedientes** ganarían catálogo
  (39 de los 129 del descubrimiento por búsqueda del 16-09 y 28 que ya
  estaban). Los otros 18 de los 85 sin líneas tienen escaneado solo el
  administrativo o la adjudicación: su falta de líneas es otra.
- Los más grandes: `6.18/28510.0116` (190 filas, red SDH/WDM),
  `6.19/28510.0122` (185, traviesas de madera), `6.16/28510.0042` (170,
  traviesas), `6.17/28510.0024` (130, red IP), `6.16/28510.0161` (125,
  tornillos y tirafondos), `6.19/28510.0008` (90), `6.19/28510.0152` (80).
- Seis PPT son de licitaciones por lotes compartidas entre 2-4 expedientes
  hermanos: cada expediente de lote se quedaría con su lote, así que las
  líneas de catálogo serían del mismo orden que las filas.

**Estimación: ~1.800-2.000 líneas de catálogo** (+5 % sobre 35.323) y del
orden de **+1.700 filas en el Excel** (+11 % sobre 15.998); expedientes con
líneas 306 → ~373. De esos 67, **solo 21 tienen baja** declarada en un
documento legible: sin leer también las adjudicaciones escaneadas, dos
tercios de esas líneas saldrían sin precio adjudicado.

### Qué haría falta

La vía que ya prevé CONTEXTO.md sección 15: rasterizar la página y pasarla a
un modelo con visión. Nada de OCR tradicional (no hay `tesseract` en la
imagen; `pypdfium2` para rasterizar ya está instalado).

1. **Interfaz de modelo con imagen** (invariante 2: intercambiable, mañana un
   modelo autoalojado con visión). Hoy `ModelProvider.completar` solo acepta
   texto.
2. **Localizar las páginas del cuadro**: clasificar cada página escaneada a
   baja resolución ("¿hay un cuadro de artículos con precios?").
3. **Transcribir** las páginas del cuadro con salida estructurada (código de
   precio, matrícula, descripción, unidad, cantidad, precio y las cabeceras
   "LOTE N"), cacheado por hash del documento + página.
4. **Encajarlo en la cascada**: las filas transcritas entran por el mismo
   `construir_linea_catalogo`/`guardar_lineas_catalogo`, con página y
   transcripción como traza, y **marcadas para revisión** (ver calidad).
5. **La baja de las adjudicaciones escaneadas**, si se quiere precio
   adjudicado para los 46 que no la tienen.
6. Verificación contra los 67 expedientes.

**Choca con una regla escrita**: CONTEXTO.md sección 6 ("el modelo se llama
para traducir una cabecera nunca vista, para nada más"). Esto sería leer
datos con el modelo, así que es una decisión de alcance, no un arreglo.

### Coste

**Piloto real** (una página densa escaneada de `6.16/28510.0161`, 21 filas,
renderizada a 1.191×1.685, `claude-haiku-4-5`, el modelo configurado): 9,4 s,
1.639 tokens de entrada y 1.749 de salida. Matrículas (de 8 cifras, formato
antiguo real), referencias, normas y los 21 precios, correctos; **un dígito
mal** en una medida de la descripción ("M22X265" leído "M22X266").

Con los precios de la API (Haiku 4.5: 1 $ / 5 $ por millón de tokens de
entrada/salida; Sonnet 5: 2 $ / 10 $; la API por lotes, a mitad de precio):

| Paso | Volumen | Haiku 4.5 | Sonnet 5 |
|---|---|---|---|
| Clasificar páginas (estimado, ~700 tokens/página) | 5.298 páginas | ~4 $ | ~8 $ |
| Transcribir cuadros (medido: ~0,010 $/página Haiku) | ~150 páginas | ~1,5 $ | ~3 $ |
| **Total, una vez** | | **~6 $** | **~11 $** |

Tiempo de proceso: ~25 min para transcribir, ~3 h para clasificar en serie
(o asíncrono por lotes). Es un coste de una sola vez: la caché por hash
impide repetirlo y los documentos nuevos (2020 en adelante) traen texto.

**Desarrollo**: del orden de 2-3 sesiones como las de este proyecto (interfaz
y transcripción con caché; integración en la cascada con lotes y trazas;
verificación contra los 67), +1 si se quiere también la baja de las
adjudicaciones escaneadas.

**Riesgo principal**: la calidad. Una cifra mal leída en un precio no se
detecta sola (el piloto acertó los 21 precios, pero es una página). Por eso
las líneas deberían entrar marcadas como "leídas de imagen", visibles en la
cola de revisión.

## Bloque 2 — Código del material

### Cómo se obtenía y dónde fallaba

Tres vías, en orden: la columna "REPUESTO" del cuadro si existe (decisión
del cliente, 2026-09-14), la primera palabra de la descripción contra el
vocabulario, y si no casa, el modelo, una vez por palabra y cacheado.

Antes: **22.569 de 35.323 líneas con código (63,9 %)**; en el Excel, 10.366
de 15.998 filas (64,8 %). De las 12.754 líneas sin código, **12.270 tenían la
respuesta "no es material" del modelo en caché** para su primera palabra, y
casi todas eran **siglas de la nomenclatura de aparatos de vía** (`CZI`,
`SCI`, `AC`, `CAC`, `CC`, `AR`, `CAR`, `DSF`, `CZV`, `ES`, `DMRDH`…), que el
vocabulario excluía a propósito ("identifican un modelo, no una categoría").
El resto: 442 partidas alzadas (vacías por diseño), marcas y servicios.

**Las siglas sí nombran la pieza**, verificado en el propio corpus, no
supuesto: en `6.20/28510.0046` el mismo cuadro trae "CAC-12000/SCI-A-…"
junto a "CONTRAAGUJA CURVA-A-54-…" y "AR-11250/SCI-A-54-…" junto a "AGUJA
RECTA-A-54A-11,250M", con la misma serie de matrículas y la misma norma; "CC
33" es el contracarril de perfil UIC-33; y los precios separan limpiamente
desvío de semicambio: los `DS`/`DSH` y la familia `D??D/I(H)` sin más texto
cuestan 60.000-360.000 € (el desvío entero), y los `SCI`/`SCV` y los `D??D/I`
cuya descripción dice "Semicambio" (`6.23/28510.0051` p.117), 22.700-57.000 €.

**Columna propia de tipo de material.** Buscada en todas las cabeceras del
corpus: además de "REPUESTO" (familia `6.21/28510.0108`) solo existe **"TIPO
DE TRAVIESA"** (`6.24/28510.0094`/`0175`/`0176`/`0177`), que no se usaba (la
cabecera la resolvía el modelo, que nunca devuelve esa columna). "TIPOLOGÍA
APARATO" va en la misma tabla que REPUESTO y es el aparato, no la pieza.

**Defecto de paso, más grave que un hueco**: la caché del modelo es por
primera palabra, pero el modelo contestó mirando una descripción concreta.
Reutilizada a ciegas, repartía códigos falsos: "X" → BALASTO en 231 líneas de
equipos Ethernet y postes ("8X10/100B ETHERNET", "X2B-P POSTE"), "CARGA" →
BALASTO en cargas de radiofrecuencia, "SUMINISTRO" → HERRAJE en el gasóleo,
"L" → PROCESSOR en un jabón, "DMRIH" → RIEL en desvíos (1.049 líneas en 127
palabras). Y como un `None` no pisaba el valor guardado, nunca se corregía.

### Qué se cambió (`app.extraccion.codigo_material`, `mapeo_cabecera`, `catalogo`)

- Tabla de siglas verificadas → pieza: AGUJA (`AC`, `AR`), CONTRAAGUJA
  (`CAC`, `CAR`), CONTRACARRIL (`CC`), CRUZAMIENTO (`CZ`, `CZI`, `CZV`),
  SEMICAMBIO (`SC`, `SCI`, `SCV`…), DESVÍO (`DS`, `DSH`, `DSF`… y la familia
  `D??D/I(H/L)`), ESCAPE (`ES`, `ESH`, `ESF`…), TRAVESÍA (`TUD`, `TSU`, `TUS`,
  `T.S.U.`…), APARATO (`AD`, `ADH`, `ADM`…, como ya se codificaba "APARATO DE
  DILATACIÓN"), JUNTA (`JAE`, `J.A.E.`), TRAVIESA (`TR`, `TRAV.`), PLACA
  (`PL.`). La sigla debe ir en mayúsculas y seguida de algo con forma de
  código. Si detrás de un desvío la descripción nombra la pieza
  ("Semicambio", "Corazón", "Contracarril"), manda la palabra. Siglas que no
  se pudieron verificar igual (`CI`, `CAM`, `ENM`, cables `EAPSP`) se quedan
  sin código.
- Vocabulario: AGUJA, CONTRAAGUJA, CRUZAMIENTO, DESVÍO, ESCAPE, TRAVESÍA,
  PALASTRO, ENCARRILADORA. Los ordinales ("SEGUNDA PLACA DE TALÓN") se saltan.
- "TIPO DE TRAVIESA" es columna de código del material, con su valor literal
  como REPUESTO ("SURFV / PRBA / PRFV"), para cualquier vía de mapeo.
- La respuesta cacheada del modelo solo se aplica si la descripción nombra
  esa pieza, o si es la propia palabra abreviada ("CONJ." → CONJUNTO).
- El código del material se recalcula en cada pasada: un código que ya no
  sale se borra, salvo que otro documento de la misma pasada lo haya escrito.

`VERSION_LOGICA_EXTRACCION` = `2026-09-17`. Ciclo completo sin descargas de
sindicación (trabajo 19992): 516 expedientes reextraídos en 21 min, 0 fallos.

### Antes y después

| | Antes | Después |
|---|---|---|
| Líneas con código del material | 22.569 (63,9 %) | **33.461 (94,7 %)** |
| Filas del Excel con código | 10.366 (64,8 %) | **14.982 (93,6 %)** |
| Resto de columnas y nº de líneas (35.323) | | idénticos |

Los más frecuentes ahora: SEMICAMBIO 4.336, CRUZAMIENTO 3.183, CONTRACARRIL
2.744, DESVÍO 2.038, PLACA 1.864, AGUJA 1.859, CONTRAAGUJA 1.445. Siguen sin
código 1.862 líneas: 442 partidas alzadas y el resto marcas, servicios
(transporte, acopio, descarga) y siglas no verificadas.

**Para confirmar con el cliente**: "SURFV / PRBA / PRFV" como código del
material de las traviesas sintéticas (literal de su columna de tipo, como
REPUESTO) o "TRAVIESA"; y "CONTRAGUJA" (264 líneas, errata literal de la
columna REPUESTO) frente a "CONTRAAGUJA".

## Bloque 3 — Unidades y duplicados

Ya hechos en la sesión anterior (`docs/sesion-2026-09-16-noche-ciclo-vigentes-unidades.md`
bloques 4 y 5); comprobado de nuevo con los datos de hoy, sin trabajo nuevo:

- **Unidades**: 18 valores distintos en la base de datos (39 formas
  originales guardadas en `unidad_medida_original`), 17 más la celda vacía en
  el Excel. El único valor nuevo desde ayer es `l` (litro, 4 líneas).
  `PA`, `P` y `transporte` siguen separados a la espera del cliente.
- **Duplicados**: los mismos 11 grupos (22 filas) del Excel, en
  `6.23/28510.0051`/`0060` y `4.25/28510.0132`: el propio pliego repite texto
  y precio con dos códigos de precio distintos (verificado en el PDF ayer). Se
  dejan; distinguirlos exige la columna "Código de precio" en el Excel,
  decisión del cliente.

## Bloque 4 — Pendientes antiguos

### Trazas duplicadas en cada pasada: resuelto

No eran solo las de lote: cada extracción volvía a añadir **todas** las
trazas aunque fueran idénticas. Antes: **36.912 trazas** (`importe_licitacion`
de expediente 8.360 para 374 distintas, `baja_declarada` de lote 8.294 para
460, adjudicatario 7.129 para 324…), contra el invariante 9.

- `app.extraccion.traza.registrar_traza`: una traza idéntica (entidad, campo,
  documento, página, fragmento y valor) sustituye a la anterior; la más
  reciente sigue siendo la de `id` mayor (la que leen la herencia de matriz y
  la web). Una traza con otro valor u otro documento se conserva. Usada en
  los tres sitios que escribían trazas (orquestador, herencia de matriz,
  identidad de expediente).
- Migración 0034: borra lo acumulado quedándose con la copia más reciente, e
  índice por (entidad, id, campo). **36.912 → 2.106 trazas** (baja de lote
  12.652 → 611 contando las de expediente).
- Verificado con un reproceso completo (trabajo 20512, 516 expedientes, 25
  min, 0 fallos): **2.106 antes y después**, y en cada campo filas = distintas.
  Test nuevo: reextraer dos veces deja las mismas trazas (falla sin el arreglo).

### Filas que `pdfplumber` funde: resuelto en lo acotado

Medido en el catálogo real: 3 casos.

| Caso | Qué pasaba | Resultado |
|---|---|---|
| `6.24/28510.0208` p.99 (módulos de telefonía) | 6 filas con 2-4 módulos fundidos cada una; la tabla no tiene precios y la división exigía precio | **separadas: 6 → 15 líneas** (+9 en catálogo y Excel), cada una con su código y descripción |
| `6.21/28510.0152` p.114 (rodillos de aguja) | 4 artículos en una fila; columna "CODIFICACIÓN DEL PRECIO" no reconocida y 3 unidades para 4 filas | **sin resolver**: añadir ese alias ya se probó y revirtió en una sesión anterior (rompe el cuadro de balasto multi-lote, test de guarda). La división con unidades de menos queda lista para cuando la columna se mapee |
| Contratos de `6.22/28510.0122`/`0155`/`0156` | tabla sin líneas horizontales: 28 códigos, una matrícula y una descripción en una fila | **sin tocar**: ya documentado el 15-09, sin pérdida de material (el anejo trae el mismo cuadro limpio) |

Cambio en `app.catalogo._dividir_fila_multiple`: una fila sin ningún precio
se divide solo si código, matrícula y descripción se dividen los tres en el
mismo N; cantidad y matrícula se reparten cuando cuadran en N; si la unidad no
cuadra, la fila se divide igual, sin unidad, y todas a revisión. Códigos de
precio fundidos ("P-914P-2018…") en el catálogo: **0**.

## Bloque 5 — Cierre

Copias: `/backups/adif_20260917_antes_codigo_material.dump` y
`/backups/adif_20260917_antes_bloque4.dump`. `VERSION_LOGICA_EXTRACCION`
`2026-09-17.2`. 952 tests.

**Base de datos, inicio de sesión → final:**

| | Antes | Después |
|---|---|---|
| Líneas | 35.323 | 35.332 (+9, las de `0208`) |
| codigo_material | 22.569 (63,9 %) | **33.470 (94,7 %)** |
| codigo_precio | 25.215 | 25.224 |
| cantidad | 17.045 | 17.056 |
| baja_lote | 9.046 | 9.055 |
| lote_id | 16.164 | 16.173 |
| matricula, precio_unitario, unidad_medida, precio_adjudicado | 17.995 / 34.398 / 28.100 / 8.843 | iguales |
| Expedientes con líneas | 306 | 306 |
| Trazas | 35.602 | **2.106** |

**Excel ("Materiales"), mañana → final:** 15.998 → **16.007 filas**;
código del material 10.366 → **14.991 (93,6 %)**; título/objeto del
contrato 13.638 → 13.765; motivo de celdas vacías 13.287 → 11.813 filas
(menos celdas vacías que explicar); expedientes con filas 303 = 303; **ningún
expediente pierde filas** (solo cambia `6.24/28510.0208`, 54 → 63); ningún
material desaparece (las 6 filas fundidas se sustituyen por sus 15 módulos).
Unidades: 17 + vacía. Resumen: 5.893 líneas pendientes de revisión, 13.432
del anejo de criterios, 221 con cantidad o precio pendiente.

**Auditoría** (trabajo 21031): dos errores, ambos explicados — los 11 grupos
duplicados legítimos de siempre y "líneas que cambian sin cambiar documentos"
en `6.24/28510.0208`, que es el arreglo de filas fundidas.

## Pendiente al cerrar

- **Decisión del cliente sobre los escaneados** (bloque 1): 67 expedientes,
  ~1.800 filas, ~6-11 $ de proceso, 2-3 sesiones; choca con la regla de la
  sección 6 de CONTEXTO.md.
- Código del material: "SURFV / PRBA / PRFV" literal o "TRAVIESA";
  "CONTRAGUJA" (errata literal de REPUESTO, 264 líneas); siglas sin verificar
  (`CI`, `CAM`, `ENM`, cables `EAPSP`/`CCPSSP`).
- `6.21/28510.0152` p.114: 4 artículos fundidos sin separar (columna
  "CODIFICACIÓN DEL PRECIO").
- `POST /mantenimiento/ejecutar` no reenvía `busqueda_desactivada` al ciclo
  (las dos pasadas de hoy repitieron la búsqueda en la Plataforma, 0 nuevos).
- Los de sesiones anteriores: vigentes con remanente (falta el fichero), los
  11 de 2026 del SAP no publicados, "Código de precio" como columna, `PA`/`P`.
