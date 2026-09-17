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

## Reconocimiento óptico: etapa implementada y piloto (misma sesión, decisión del cliente)

**Implementado** (`app.extraccion.ocr`, `app.extraccion.ocr_pdf`, migración 0035):
- **Desactivable**: `OCR_MODO` = `escaneados` (por defecto) o `desactivado`.
  Solo entra un documento que `es_documento_escaneado` marca como tal.
- **Lectura**: cada página se rasteriza (`pypdfium2`, lado largo 1.568 px) y
  el modelo configurado (`claude-haiku-4-5`) la transcribe en bloques de texto
  y tablas con sus celdas, 4 páginas a la vez. Se leen primero 2 páginas; si
  el clasificador dice pliego administrativo, se para ahí. Documentos de más
  de `OCR_MAX_PAGINAS` (150) no se leen enteros.
- **Caché por hash** (`cache_ocr_documento`, con segundos y tokens por
  página): una segunda pasada no vuelve a llamar al modelo.
- **Cascada sin cambios**: con lo leído se genera un PDF con capa de texto y
  rejilla, página a página con la misma numeración, que recorre localizador,
  tablas, lotes y mapeo como cualquier otro documento.
- **Marcado**: `lineas_catalogo.texto_reconocido`, motivo de revisión propio
  en cada línea y en el expediente, y prefijo `[reconocimiento óptico]` en el
  fragmento de la línea y de las trazas del documento.
- 6 tests nuevos (958 en total).

Desplegado con `OCR_MODO=desactivado` en `.env` para que el ciclo automático
no lea nada antes de validar el piloto; el piloto se lanzó con un script que
lo activa solo en su proceso.

**Piloto: `6.18/28510.0066` (fusibles AT) y `6.16/28510.0161` (tornillería)**, 5
documentos escaneados, 67 páginas leídas:

| Documento | Páginas leídas | Segundos de modelo | s/página | Tokens entrada / salida |
|---|---|---|---|---|
| `0066` CONTRATO_1 | 2 de 2 | 50,7 | 25,3 | 4.302 / 2.651 |
| `0066` ANEJO_1 (PPT fusibles) | 10 de 10 | 74,4 | 7,4 | 21.510 / 6.581 |
| `0066` ANEJO_2 (PCAP) | **2 de 82** (parado) | 33,3 | 16,6 | 4.302 / 2.008 |
| `0161` ANEJO_1 (PPT tornillería) | 19 de 19 | 269,7 | 14,2 | 40.869 / 14.432 |
| `0161` ANEJO_2 (pliego de *condiciones* administrativas) | 34 de 34 | 600,3 | 17,7 | 73.134 / 33.266 |
| **Total** | **67** | **1.028** | **15,3** | **144.117 / 58.938** |

- **Tiempo**: 15,3 s por página de modelo; con 4 en paralelo, ~5 s de reloj
  por página. **Coste real: 0,44 $ (0,0066 $/página)**.
- **Calidad, comprobada celda a celda contra la imagen**:
  - Fusibles p.10: 28 filas × 8 columnas, **224 celdas, 0 errores**.
  - Tornillería p.16 (11 filas): matrículas y precios correctos; **2 errores**
    en celdas que no son de catálogo: "M22X265" leído "M22X266" en una
    descripción y "99'12-R-29" leído "89'12-R-29" en la referencia del plano.
  - Tablas leídas: 138 filas en el PPT de tornillería, 48 en el de fusibles
    (incluidas la de índice y la de firmas).
- **Líneas de catálogo obtenidas: 0.** No por la lectura, sino por la
  cascada: estos cuadros de 2016-2018 **no traen código de precio, sus
  matrículas son de 8 cifras** ("59020019", "69161624", verificado en la
  imagen: es el formato antiguo, y no están en el maestro de SAP) y **no tienen
  columna de cantidad** — y la etapa 4 descarta como espuria una tabla sin
  código de precio ni matrícula de 9 cifras, salvo que su cabecera nombre
  descripción, cantidad y precio. Es la misma regla que para un documento con
  texto; hace falta decidir si se acepta la matrícula de 8 cifras.
- **Parada temprana**: funcionó con el PCAP de `0066` (2 de 82 páginas), pero
  no con el de `0161`, que se titula "Pliego de *Condiciones* Administrativas
  Particulares" y el clasificador no lo reconoce: se leyeron las 34 páginas
  (0,25 $ y 10 min de modelo desperdiciados).

## Matrícula de 8 cifras, parada en pliegos administrativos y lanzamiento sobre el corpus

**Matrícula de 8 cifras (decisión del cliente: en todos los documentos).**
Aceptada en la línea (`app.catalogo._MATRICULA_VALIDA_RE`), como identificador
de fila en el localizador y, en la extracción de tablas, cuando la cabecera
nombra la matrícula o al menos 3 filas la traen. **Alcance en documentos con
texto, medido antes de cambiar nada: pequeño.** 9 líneas guardadas (4
expedientes: rodillos de aguja de `6.20/28510.0041`, placa nervada de
`0042`/`0046`/`0047`) a las que se les descartaba la matrícula, y un cuadro de
carril de `6.19/28510.0113` descartado entero. Después del reproceso: 16
líneas de documentos con texto con matrícula de 8 cifras, y `0113` pasa de 0 a
12 líneas. En el texto plano del corpus solo aparecen 23 filas así, frente a
9.207 con matrícula de 9.

**Títulos de pliego administrativo.** Buscados en las dos primeras páginas de
todo el corpus: "pliego de condiciones administrativas" (43 documentos) y
"pliego de condiciones generales" se añaden, en posición de título y solo en
las dos primeras páginas. "Cuadro de características" se probó y se descartó
(solo lo abren notas de aclaración de una página). Con texto, cambian 3
documentos, ninguno con líneas. En el lanzamiento, 53 de los 130 documentos
leídos se pararon tras las primeras páginas.

**Lanzamiento** (ciclo 21032, 2 h 33 min, versión `2026-09-17.3`, reproceso de
los 516 expedientes con el reconocimiento activo):

| | Antes (sin piloto) | Después |
|---|---|---|
| Líneas de catálogo | 35.332 | **37.660 (+2.328)** |
| … leídas por reconocimiento óptico | 0 | **2.316** |
| Expedientes con líneas | 306 | **361 (+55)**: 54 por reconocimiento, 1 por matrícula de 8 cifras (`6.19/28510.0113`) |
| Filas del Excel | 16.007 | **18.260 (+2.253)** |
| Materiales distintos en el Excel | 9.848 | 12.003 (0 perdidos) |
| Expedientes con filas en el Excel | 303 | 358 |

Las 2.316 líneas reconocidas: precio 98,5 %, matrícula 94 %, lote 97 %, código
del material 77 %, cantidad 34 %, unidad 7 % (estos cuadros antiguos casi
nunca las traen), baja 10 % (sin adjudicación legible en la mayoría). Las 54
quedan en `pendiente_revision` con el motivo de reconocimiento óptico. Mayores:
`6.18/28510.0116` 228, `6.16/28510.0042` 182, `6.19/28510.0122` 182,
`6.16/28510.0161` 133, `6.19/28510.0152` 123. Los tres hermanos de grifas
`6.19/28510.0135`/`0175`/`0177` (62 cada uno) no tienen ningún documento
legible que declare sus lotes, así que cada uno se queda el cuadro entero: la
misma limitación que para documentos con texto (~124 líneas repetidas).

**Coste real**: 1.798 llamadas de lectura en el lanzamiento, 3,87 M tokens de
entrada y 1,29 M de salida, **10,30 $** (sumado de los registros del worker),
más 0,44 $ del piloto: **~10,75 $**. De eso, ~2,4 $ se perdieron: un documento
(`6.18/28510.0071`, 181 páginas en dos PDF) se leyó entero tres veces porque
una página no cabía en la respuesta y tiraba el documento. 16.919 s de modelo
para 1.367 páginas en caché: 12,4 s por página, ~5 s de reloj leyendo 4 a la vez.

**Fallos y arreglos durante el lanzamiento:**
- **Saldo de la API agotado al final**: 5 expedientes fallidos
  (`3.16/28510.0044`, `6.15/28510.0094`, `6.17/28510.0012`, `6.15/28510.0080`,
  `2.19/23108.0127`). Hace falta recargar crédito y relanzarlos.
- **Una página que falla ya no tira el documento** (commit `f6ab430`): se
  guarda con su error; si es transitorio (saldo, red) lo leído queda en caché,
  el trabajo falla visible y el reintento solo relee esa página; si no cabe en
  la respuesta, queda anotada como ilegible y no se reintenta. `0071` es el
  sexto fallido y, con el arreglo, se completará en el próximo intento.
- **Resumen de presupuesto al pie del cuadro** (ejecución material, gastos
  generales, beneficio industrial, suma, presupuesto base) entraba como líneas
  sin descripción en `6.17/28510.0056`: ahora es pie de tabla (19 → 14 líneas).

Auditoría del ciclo: los 11 duplicados legítimos de siempre y "líneas que
cambian sin cambiar documentos" en los expedientes que ganan líneas por el
reconocimiento (esperado); el error "sin descripción" era el de `0056`, ya
corregido. 966 tests.

## Relanzamiento de los 6 fallidos y cierre (tras recargar crédito)

Relanzados uno a uno (trabajos 21553-21558): **los 6 completan sin error**, con
290 lecturas de página y **1,72 $**. Los 140 documentos escaneados del corpus
quedan ya en caché (1.657 páginas; 57 marcados incompletos a propósito, casi
todos pliegos administrativos dejados tras sus primeras páginas).
**Ninguno de los 6 aporta líneas**, por dos motivos distintos:

- `6.18/28510.0071` (señalización): la lectura es buena (p.12-15, 68 artículos
  con designación, plano y precio), pero el cuadro **no trae código de precio,
  matrícula ni cantidad**, y la etapa 4 solo acepta un cuadro sin código si su
  cabecera nombra descripción, **cantidad** y precio. Es la misma regla para
  documentos con texto: aceptar cuadros sin cantidad sería otra decisión.
- `3.16/28510.0044`: es un presupuesto por partidas en una tabla apaisada muy
  densa (p.17), no un cuadro de catálogo, y **ahí la lectura es mala** ("€"
  leído "ψ", texto sin sentido). Primera página del corpus donde la calidad
  cae de forma visible.
- `6.15/28510.0094`, `6.17/28510.0012`, `6.15/28510.0080`, `2.19/23108.0127`:
  sus escaneados son pliegos administrativos, contratos o anexos sin cuadro
  (como ya decía la clasificación del bloque 1); `0080` además no identifica su
  bloque en el anuncio multi-lote.

**Coste total real del reconocimiento: ~12,5 $** (piloto 0,44 + lanzamiento
10,30 + relanzamiento 1,72).

**Auditoría** (trabajo 21560): un único error, los 11 duplicados legítimos; el
de "sin descripción" de `6.17/28510.0056` ya no aparece. Avisos frente a la
auditoría previa al reconocimiento: cantidad con forma de año 602 → 603,
precios atípicos 1.941 → 2.009, líneas sin lote 19.159 → 19.234 (75 de ellas
leídas por reconocimiento).

**Comparación final** (Excel previo al reconocimiento → cierre): 16.007 →
**18.260 filas**; expedientes con filas 303 → **358**; materiales distintos
9.848 → 12.003, **0 perdidos**; **ninguno de los 303 expedientes que ya tenían
filas cambia**; precio unitario 15.752 → 17.981, baja 9.055 → 9.296, precio
adjudicado 8.843 → 9.084, duplicados 11 = 11. Base de datos: 37.660 líneas en
361 expedientes; matrícula 20.200, código del material 35.272 (93,7 %),
trazas 2.111.

## Filas de resumen de presupuesto (aviso del cliente)

El cliente encontró filas de resumen de presupuesto como líneas de material,
con importes de millones, en `6.17/28510.0056` ("Presupuesto Base de
Licitación" 3.305.653, "Suma" 2.731.944, "Presupuesto de Ejecución Material"
2.375.604) y `6.17/28510.0007` ("TOTAL PRESUPUESTO" 1.382.753, "SUMA"
1.142.771, "PRESUPUESTO DE EJECUCIÓN MATERIAL" 993.714). **La corrección
anterior de `0056` era parcial**: cubría las filas con la etiqueta fuera de la
columna de descripción (p.19), no las que la traen dentro (p.20), y `0007` no
estaba cubierto.

**Medido en todo el catálogo antes de limpiar**: descripción que, quitadas
cifras, porcentajes y símbolos, solo contiene palabras de concepto de
presupuesto. **22 líneas en 6 expedientes** (18 leídas por reconocimiento, 21
en el Excel): `6.17/28510.0007` (6), `6.17/28510.0056` (6), `6.17/28510.0123`
(3), `6.19/28510.0064` (3), `3.21/28510.0052` (3, con texto) y
`6.23/28510.0105` (1, "Total", con texto). Una búsqueda más amplia (descripciones
que *empiezan* por total, suma, presupuesto, IVA, gastos generales, beneficio
industrial, importe total, base imponible, ejecución material, valor estimado)
no encontró ninguna más; las 22 revisadas una a una, ninguna es un material.

**Arreglo** (`app.catalogo._es_concepto_de_presupuesto`): esa misma regla por
palabras, en la descripción y en el fragmento de la fila, además de las
etiquetas exactas de siempre. Nunca por "contiene": "Suministro de balasto
según presupuesto de ejecución" o "Partida alzada total" siguen siendo líneas
(test). Pasada sobre todo el catálogo antes de desplegar: caza exactamente esas
22. Reprocesados los 6: catálogo 37.660 → **37.638 líneas**, 0 restantes;
Excel 18.260 → **18.239 filas**, 358 expedientes con filas. 968 tests.

**Rectificación de una cifra**: el script de comparación usaba la celda de
matrícula vacía (exportada como un espacio) como clave, y los "materiales
distintos" que se dieron más arriba (9.848 → 12.003) estaban mal. Con la clave
corregida (expediente + matrícula, o descripción si no hay): **14.980 antes
del reconocimiento → 17.223 tras él → 17.202 ahora**. Frente al Excel previo al
reconocimiento, 12 claves desaparecen y ninguna es un material perdido: 9 son
los mismos rodillos, chapas y placas nervadas de `6.20/28510.0041`/`0042`/
`0046`/`0047`, que ahora se identifican por su matrícula de 8 cifras, y 3 son
filas de resumen de `3.21/28510.0052`.

Excel exportado a `C:\dev\ADIF\catalogo_adif_2026-09-17.xlsx` (sin subir al
repositorio).
