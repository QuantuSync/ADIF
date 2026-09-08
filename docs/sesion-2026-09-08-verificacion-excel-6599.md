# Sesión 2026-09-08: verificación del Excel de 6.599 líneas entregadas

El cliente verificó a mano el Excel exportado (6.599 líneas entregadas,
3.102 pendientes, 3 grupos duplicados, recuentos del "Resumen" correctos) y
encargó cuatro cosas: (1) líneas sin código de expediente, (2) 38 líneas sin
descripción, (3) un precio unitario a cero, (4) analizar (sin implementar)
el motivo mayoritario de las 3.102 pendientes. Los tres primeros compartían,
total o parcialmente, una única causa raíz nunca vista con el corpus de 45
expedientes.

---

## 0. Hallazgo central: colisión de firma de cabecera vacía

`app.extraccion.tabla.extraer_tablas_pagina` localiza la cabecera de una
tabla como "todo lo que precede a la primera fila de datos reconocible"
(CONTEXTO.md, docstring del módulo). Cuando la primera fila de una tabla ya
trae, en su propia primera celda, algo con forma de matrícula (9 dígitos) —
típico de una tabla que continúa de una sección anterior sin repetir su
cabecera, o de una tabla cuya cabecera real aparece más abajo, tras filas de
otra tabla previa que no encajan en ningún patrón de fila de datos conocido
— la cabecera capturada sale **vacía** (`[]`).

`app.extraccion.firma_cabecera.calcular_firma_cabecera([])` hashea la cadena
vacía: **la misma firma para cualquier tabla sin cabecera detectada, sin
importar qué columnas traiga de verdad esa tabla en concreto.**
`app.extraccion.mapeo_cabecera.mapear_cabecera` cacheaba el mapeo del
modelo bajo esa firma igual que para cualquier cabecera real — así que la
PRIMERA tabla del corpus que cayó en este caso (durante el reproceso masivo
de esta sesión) fijó un mapeo (`cache_mapeo_cabecera` id 99:
`codigo_precio→0, matricula→2, descripcion→1, precio_unitario→4`) que se
reaplicó a ciegas a cualquier otra tabla sin cabecera del resto del corpus,
con columnas en un orden completamente distinto.

Verificado contra los documentos reales que las cuatro consecuencias
observadas por el cliente vienen todas de esta misma colisión:

| Sesión de origen | Expedientes | Sufrieron |
|---|---|---|
| `6.24/28510.0184` (ANEJO, telefonía OpenScape) | 363 | matrícula y descripción intercambiadas, código de expediente sin cruzar |
| `6.24/28510.0209` (CONTRATO, centralita analógica) | 366 | igual, + ruido de sello CSV invertido en varias celdas |
| `6.21/28510.0109` / `6.21/28510.0108` (documento compartido entre hermanos) | 237, 463 | precio_unitario leyó la columna de "cantidades estimadas" (siempre `0`) en vez de la de precio real |

**Arreglo, `app.extraccion.mapeo_cabecera.mapear_cabecera`:** una cabecera
sin ninguna celda con texto real nunca se cachea ni se lee de caché — cada
tabla sin cabecera detectada pide su propio mapeo al modelo, usando solo sus
propias filas de ejemplo, exactamente como si nunca se hubiera visto antes.
Cuesta una llamada más al modelo por cada tabla nueva de este tipo (raro:
solo 3 documentos en todo el corpus hasta ahora), a cambio de que un mapeo
aprendido de una tabla no pueda corromper ninguna otra. Dos tests nuevos en
`tests/extraccion/test_mapeo_cabecera.py`.

La fila cacheada corrupta (id 99) se borró de la base de datos real.

---

## 1. Líneas sin expediente: causa y limpieza

Todas las líneas con "Código de proyecto" vacío en el Excel Y sin matrícula
NI descripción (el patrón exacto que reportó el cliente, "solo un precio")
resultaron ser la colisión de la sección 0: 30 líneas reales en 363/366,
donde la descripción real cayó en la columna que el mapeo corrupto asignaba
a "matrícula" (se descartaba por no tener forma de 9 dígitos) y viceversa.

Aparte de estas 30, el Excel también deja "Código de proyecto" vacío para
**661 líneas más** cuyo expediente simplemente no cruza contra el Excel de
códigos de ADIF (comportamiento documentado, CONTEXTO.md sección 7: "el
sistema nunca inventa una matriz. Si no cruza, se deja vacío") — verificado
a mano que `6.24/28510.0184` y `6.24/28510.0209` (los dos expedientes de la
sección 0) genuinamente no están en `codigos_proyecto.xlsx` bajo ningún año,
no es un fallo de normalización de código. Esas 661 no forman parte de este
encargo: tienen matrícula y descripción reales, solo les falta el cruce
externo.

**Arreglo de origen:** sección 0. **Limpieza:** las 30 líneas se
recuperaron solas al reprocesar 363/366 con el mapeo corregido (misma clave
de línea, se actualizan in place). Ninguna quedó con datos degenerados tras
el reproceso — verificado con una consulta agregada contra la base de datos
real (0 líneas sin expediente cruzado, sin matrícula y sin descripción a la
vez, dentro del catálogo entregable).

---

## 2. Las 38 líneas sin descripción: cuatro causas distintas, ninguna es el guard fallando

CONTEXTO.md (sección "Residuo de duplicados...", 2026-09-06) dice "una línea
sin descripción y sin matrícula no entra al catálogo". Achicado: **si el
fragmento de origen trae contenido real (precio, código, cantidad) sí
entra, marcada para revisión** (`app.catalogo.construir_linea_catalogo`,
comentario junto al guard) — la redacción de CONTEXTO.md comprimía ese
matiz. El guard SÍ se aplica en todos los casos; lo que fallaba era, en cada
caso, otra cosa:

1. **24 líneas (363/366):** sección 0 (colisión de cabecera vacía).
2. **2 líneas con matrícula, `6.20/28510.0047`/`0042` (doc. 455, compartido
   entre hermanos):** cabecera real pero corrompida — una tabla previa con
   códigos de material no estándar (`DSF-A-45-190/129-...`) se coló en la
   franja de cabecera combinada (`_combinar_filas_cabecera`), y el modelo,
   viendo la etiqueta literal "Designación" en la columna 2 (vacía en la
   única fila de datos real) en vez de fiarse de la columna 1 (donde
   realmente cae el texto), mapeó `descripcion→2`. Verificado contra el PDF
   real: la descripción ("ENCARRILADORA METRICA EM-54-4200 RECTA") está en
   la columna 1. Corregido el mapeo cacheado (`cache_mapeo_cabecera` id
   100, `descripcion` 2→1) y reprocesado — no es un patrón repetible (la
   cabecera es literalmente única, un bloque de códigos de material
   concreto no se repite en ningún otro documento).
3. **4 líneas (174, 175 -- `6.19/28510.0194`/`0195`):** patrón nuevo, imagen
   especular del ya conocido "fila fantasma" de la sesión de
   `6.23/28510.0051` (2026-09-06). Ahí la primera línea de una descripción
   envuelta caía en la banda visual de la fila ANTERIOR; aquí es el PRECIO
   el que llega una fila tarde -- la fila con matrícula/descripción sale con
   su propia celda de precio vacía, y el precio real aparece solo, sin
   ningún otro dato, en la fila siguiente. Antes de este arreglo,
   `_recuperar_precio_columna_fantasma` (columna fantasma DENTRO de la misma
   fila) disparaba por error sobre la celda vacía y recuperaba un valor
   vecino plausible pero equivocado (la cantidad "1" de "PEDIDO INICIAL"
   como si fuera el precio, verificado en `6.20/28510.0029`) -- y la fila de
   precio huérfana se guardaba aparte, sin descripción ni matrícula.
   **Arreglo:** `app.catalogo._es_fila_precio_continuacion` +
   `construir_lineas_desde_tabla` recupera el precio de la fila siguiente
   ANTES de construir la línea (parcheando una copia de la fila), así que la
   recuperación de columna fantasma nunca llega a dispararse sobre una celda
   vacía por el motivo equivocado. Test de regresión con el fixture real.
4. **2 líneas (260 -- `6.22/28510.0039`; 414 -- `6.25/28510.0213`):** una
   partida alzada real (CONTEXTO.md sección 2: legítima, nunca lleva
   matrícula) con columnas intermedias ausentes en su fila deja su único
   texto real en la columna que el mapeo llama "código de precio" o "código
   ADIF" -- una columna que el mapeo no reclama para ningún campo en esas
   dos cabeceras concretas (o codigo_precio nunca se mapeó, o matricula
   nunca se mapeó). **Arreglo:**
   `app.catalogo._recuperar_descripcion_ultimo_recurso`: último recurso
   antes de dar una fila por "sin descripción ni matrícula" -- prueba
   cualquier columna de la fila que el mapeo no reclame para NINGÚN campo,
   y solo la acepta si hay EXACTAMENTE una candidata con pinta de
   descripción real (con dos o más, no se adivina). Tres tests nuevos
   (dos casos reales + un guard de "no adivinar con dos candidatas").
5. **6 líneas más (174, 175, 260, 414) con código de expediente cruzado pero
   sin descripción/matrícula:** resueltas por los mismos arreglos 3 y 4.

**Efecto secundario encontrado al reprocesar — gap de idempotencia real:**
`app.catalogo.guardar_lineas_catalogo` escribe por clave (CONTEXTO.md
invariante 9) pero nunca borra una fila de una extracción anterior que ya no
aparece en la nueva. Para una fila SIN `codigo_precio` NI `matrícula`, la
clave es `hash(descripción + orden_aparicion)` -- si la descripción cambia
entre dos reprocesos de la misma fila (exactamente lo que hacen los arreglos
3 y 4: pasa de `""` a un texto real), la clave cambia, y la fila vieja
(fantasma, con descripción vacía) queda huérfana en vez de sustituirse. Se
detectaron y borraron a mano 5 filas así (174: 2, 175: 2, 260: 1), cada una
verificada contra su reemplazo real (mismo lote, mismo precio, descripción
ahora correcta) antes de borrar. **No se ha tocado
`guardar_lineas_catalogo`** -- una poda automática de "claves vistas antes
pero no en esta pasada" es una decisión de diseño con más aristas (qué
pasa si solo se reprocesa un subconjunto de las tablas de un documento) que
no correspondía tomar dentro de esta sesión; queda anotada en CONTEXTO.md
sección 16 como pendiente.

---

## 3. El precio unitario a cero: confirmado como la misma colisión, no un dato real

La línea que vio el cliente y **otras 29 más** (no visibles hasta reprocesar
-- 15 en `6.21/28510.0109`, 15 en su hermano `6.21/28510.0108`, mismo
documento compartido, doc. 586) tenían todas `precio_unitario = 0` por el
mapeo corrupto de la sección 0 leyendo la columna de "cantidades estimadas
de referencia" (que en esa tabla vale sistemáticamente `0` para casi todas
las filas) en vez de la columna real de precio, la última de la fila.
Verificado contra el PDF real (`p.42`, `p.49`) que el precio real sí está
publicado (17.946,18 €, 921,90 €...). **No es un dato que el documento
declare como cero** -- de hecho, tras el reproceso, **cero líneas** del
catálogo entregable tienen precio unitario cero o negativo. El mínimo real
del catálogo pasa a ser **0,10 €** (verificado como precio legítimo, no
recalculado).

---

## 4. Las 3.102 pendientes: análisis del motivo mayoritario (sin implementar nada)

### Concentración

El motivo mayoritario, "ninguna cabecera LOTE N encontrada en la franja que
precede a esta tabla" (2.001 líneas), **no está repartido**: dos
expedientes hermanos que comparten un único documento de 37 páginas
concentran **1.594 de esas 2.001 (79,7 %)**:

| Expediente | Título | Líneas afectadas |
|---|---|---:|
| `6.22/28510.0122` | Repuestos para aparatos genéricos de vía (2 LOTES) | 797 |
| `6.22/28510.0156` | (mismo documento; "lote 2: cruzamientos y contracarriles...") | 797 |

Los mismos dos expedientes concentran, además, **las 152 líneas completas**
del motivo "varias cabeceras de lote en la franja" (76 + 76). **Entre los
dos motivos, este único documento explica 1.746 de las 3.102 líneas
pendientes del catálogo entero (56,3 %).**

El resto del motivo "ninguna cabecera" se reparte en colas mucho más
pequeñas: 86 líneas en `6.25/28510.0019` (9 lotes reales, mezcla de
motivos), y entre 5 y 54 líneas en otros 13 expedientes.

### El patrón estructural

Verificado contra el PDF real (`6.22/28510.0156`, ANEJO): la página 15 trae
literalmente "Lote 1: SEMICAMBIOS, AGUJAS Y CONTRAAGUJAS..." justo antes de
la tabla de precios de ese lote. **Esa tabla ocupa 17 páginas seguidas**
(16-32) sin que ninguna de las páginas de continuación repita la palabra
"Lote" en ningún sitio -- cada página solo trae el pie de página genérico
del documento ("...RED FERROVIARIA DE INTERES GENERAL. 2 LOTES. Pág. N de
37"), nunca el número de lote concreto.

`app.extraccion.lote_tabla` (docstring del módulo, sección "Herencia de
lote entre páginas: deliberadamente sin implementar todavía") ya identificó
este problema en una sesión anterior y decidió, explícitamente, medir antes
de implementar: **"se deja como huérfana, con un motivo distinto (banda
vacía) para poder medir cuántas líneas caen en este caso concreto sobre el
corpus real antes de decidir si vale la pena implementarla."** Con 45-52
expedientes esa medición dio 821 líneas de "banda vacía" (ninguna palabra en
absoluto en la franja) -- ya un número notable, documentado como pendiente,
nunca implementado.

**Lo que el corpus a 467 expedientes añade que antes no se veía:** la
medición original solo contempló la variante "banda vacía" (franja sin
ningún texto). Hay una **segunda variante, más grande, del mismo fenómeno**:
una página de continuación cuya franja SÍ tiene texto -- el pie de página
del documento, un pie de tabla, una nota al margen -- pero ese texto nunca
menciona "LOTE". Esa variante cae en el motivo "ninguna cabecera LOTE N
encontrada" en vez de en "banda vacía", así que las dos sesiones anteriores
(que solo midieron "banda vacía") nunca vieron el tamaño real del problema:
las 821 de banda vacía y buena parte de las 2.001 de "ninguna cabecera" son,
estructuralmente, el mismo caso -- una tabla que continúa sin repetir su
cabecera de lote -- contado en dos cubos separados porque el contenido
exacto de la franja intermedia varía.

El motivo "varias cabeceras" de estos mismos dos expedientes probablemente
también es una manifestación del mismo fenómeno: una página de transición
donde termina la tabla del Lote 1 y empieza la del Lote 2 puede traer, en su
franja, tanto el pie de página persistente de "Lote 1" (si quedó algo de
esa mención en el margen) como la nueva cabecera "Lote 2" -- dos
identificadores donde en realidad solo uno de los dos introduce una tabla
nueva. No verificado línea a línea (no se ha implementado nada), pero
consistente con que el mismo par de expedientes concentre el 100% de este
motivo también.

### Qué no se toca hoy

Por diseño explícito de una sesión anterior, `app.extraccion.lote_tabla`
**decide por posición de tabla en página, nunca por proximidad textual ni
por herencia entre páginas** -- "una regla así puede fallar de formas
silenciosas". Implementar herencia de lote entre páginas de continuación
(llevar hacia adelante el lote de la tabla anterior cuando la franja
intermedia no menciona NINGÚN lote, sea cual sea su contenido) es un cambio
de ese principio, no un arreglo puntual, y afecta potencialmente a miles de
líneas de golpe si se generaliza mal. **No implementado esta sesión, tal
como pidió el encargo** -- queda como propuesta concreta, con el tamaño real
medido, para que el cliente decida.

---

## 5. Reproceso y números finales

`VERSION_LOGICA_EXTRACCION` sube a `2026-09-08.1` (fuerza el reproceso de
todo el corpus con la lógica corregida). Reprocesados de forma dirigida y
verificados uno a uno: `363, 366, 194, 459, 174, 175, 260, 414, 237, 463`.
El resto del corpus se está reprocesando solo, en segundo plano, por el
ciclo de mantenimiento ya existente del worker (mismo mecanismo que
cualquier subida de versión anterior, CONTEXTO.md sección 16) -- no se ha
lanzado ni se está vigilando ningún proceso nuevo en esta sesión.

Verificado contra la base de datos real tras los reprocesos dirigidos:

| Comprobación | Antes | Después |
|---|---:|---:|
| Líneas sin expediente cruzado, sin matrícula y sin descripción | 30 | **0** |
| Líneas sin descripción en el catálogo entregable | 38 | **0** |
| Líneas con precio unitario ≤ 0 en el catálogo entregable | 30 (1 visible + 29 ocultas) | **0** |
| Precio unitario mínimo del catálogo | 0,00 € | **0,10 €** |

Excel regenerado (`GET /catalogo/exportar.xlsx`):

| | Antes | Después |
|---|---:|---:|
| Líneas entregadas | 6.599 | **6.643** |
| Líneas pendientes de revisión | 3.102 | **3.102** (sin cambios, sección 4 no implementada) |

El aumento de 44 líneas entregadas viene de material real que antes se
perdía sin dejar ninguna huella recuperable (descripciones/matrículas
intercambiadas o vacías por el mapeo corrupto) y ahora se guarda con su
contenido correcto.

455 tests pasan (450 antes de esta sesión + 5 nuevos: 1 de caché de cabecera
vacía, 1 de precio en fila siguiente, 3 de recuperación de descripción de
última instancia).
