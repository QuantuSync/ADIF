# Sesión 2026-09-15 — verificación de la pasada completa, tablas que no entraban y pendientes antiguos

Encargo en cinco bloques: verificar con un reproceso completo los tres
cambios de ayer que se quedaron sin pasada revisada, y comparar los
**materiales distintos** del Excel con el estado de ayer (5.519); las páginas
que "el localizador no abría" en `6.22/28510.0122` y `6.24/28510.0064`; la
tabla "LOTE 6: RAM NORTE" de `6.22/28510.0016`; tres pendientes antiguos; y
cierre.

Instantáneas de líneas (CSV de `lineas_catalogo`, mismas columnas que las
del 14-09) y Excel exportados en el scratchpad de la sesión; pasadas
completas F11-F16 siguiendo la numeración de ayer (F12 verificación, F13
con el arreglo del bloque 1, F14 con los de los bloques 2-3, F15 y F16 finales).

## Bloque 1 — los tres cambios sin verificar

**F11**, la pasada completa lanzada al cerrar ayer, se interrumpió por la
noche (reinicio de `dockerd`; el ciclo pasó a su segundo intento) y terminó
esta mañana a las 06:34. Se comprobó que la imagen del worker era el código
de `HEAD` (último cambio de motor 17:23 UTC, imagen 17:26 UTC, ficheros
clave idénticos byte a byte) y se lanzó una pasada limpia, **F12** (15 min,
358/358): **F11 = F12 byte a byte** (ids incluidos). F10 → F12: solo cambian
`4.25/28510.0207`/`0208` (−10 líneas, las huérfanas de "Lote nº1" pasan a su
lote).

### Los motivos de expediente de lote: verificados

De los 98 expedientes que conocen su lote (uno de sus lotes trae su propio
código), **0** tienen un motivo propio de "EXPEDIENTE PRINCIPAL distinto" y
**0** de "cobertura parcial". Los 10 expedientes que aún tienen el primero
(`6.22/28510.0139`/`0140`/`0142`/`0147`/`0148`/`0149`, `6.23/28510.0073`/`0074`,
`6.25/28510.0187`/`0237`) no saben cuál es su lote: su código no está entre
los lotes que declara su adjudicación. Tres expedientes que sí lo saben
(`6.19/28510.0209`, `6.20/28510.0002`/`0003`) muestran "cobertura parcial"
solo porque citan literalmente el motivo de su matriz ("la matriz … tampoco
tiene cuadro de precios ni baja: …").

### "Lote nº1": fallaba, y por otra causa

La lectura de "Lote nº1"/"Lote nº 2" es correcta en los tres documentos
(ANEJO_1 p.18 y los dos Contratos p.109, lectura en seco: 2 líneas por
lote). Pero tras F12, `0207` (LOTE 1) seguía mostrando **P-03/P-04, que son
del LOTE 2**, con la baja del LOTE 1 (0 %).

Depurado ejecutando la extracción de `0207` instrumentada: la poda del
documento no las borraba porque llevaban `heredado_de_matriz = true`.
`0207` y `0208` figuran en el Excel de códigos como pedidos de `0124`, y en
una pasada antigua (cuando `0207` no tenía líneas propias) heredaron de la
matriz las cuatro líneas del cuadro común. Dos defectos compuestos:

1. **La poda deja fuera, a propósito, las líneas heredadas** ("apuntan a un
   documento de la matriz, que el pedido nunca procesa"). Aquí el documento
   lo comparten matriz y pedido, y la herencia ya no se aplica (el pedido
   sabe su lote): nadie las volvía a escribir ni a borrar.
2. **Las marcas de origen se quedaban pegadas.** `guardar_lineas_catalogo`
   no pisa un valor con `None` ("esta pasada no trae el dato"), y eso valía
   también para `heredado_de_matriz`, `lote_heredado_de_pagina_anterior` y
   `lote_del_expediente`: un `true` de una pasada vieja era para siempre,
   aunque la línea saliera ya del propio documento y con cabecera explícita.

Arreglo:

- Las tres marcas se recalculan en cada pasada, como `motivo_revision`
  (`catalogo._MARCAS_DE_ORIGEN`). Dentro de una misma pasada, si varios
  documentos escriben la misma línea, la marca queda en `true` solo si todos
  coinciden; y no se rellena desde una fila absorbida por firma.
- `podar_lineas_heredadas_obsoletas`: al final de la extracción, las líneas
  todavía marcadas como heredadas que la herencia de esta pasada no ha
  escrito (`ResultadoHerencia.ids_tocadas`) se borran. Salvo si la herencia
  está pendiente (matriz en proceso, o ciclo): entonces se conservan hasta
  que se pueda decidir.

**F13** (15 min, con el arreglo) frente a F12: −4 líneas, las cuatro del
mismo defecto: P-03/P-04 del LOTE 2 en el LOTE 1 de `0207`, y dos
matrículas del LOTE 2 (`6.20/28510.0029`, fuera del catálogo) en el LOTE 1
de `6.20/28510.0028` (592100027, 592100008; siguen en su matriz `0195` y en
`0028` como tabla de otro lote). Ningún material desaparece. Marcas
corregidas: `heredado_de_matriz` 957 → 339 líneas (618 salían en realidad
de los propios documentos del pedido), `lote_del_expediente` 18 → 4,
herencia de lote entre páginas 5.395 → 5.284. Las marcas solo se muestran
como trazabilidad en la web; el Excel no las usa.

### Excel: materiales distintos contra ayer

| | Ayer (E5) | F13 |
|---|---:|---:|
| Filas en Materiales | 15.979 | 14.474 |
| Materiales distintos (matrícula, o descripción sin espacios ni signos) | 5.519 | 5.463 |
| — con matrícula | 3.322 | 3.234 |
| Pendientes de revisión (Resumen) | 6.136 | 5.374 |
| Anejo de criterios, fila propia en el Resumen | — | 13.288 |

14.474 + 5.374 + 13.288 = 33.136, las líneas de la base de datos.

Los 315 materiales que salen del Excel **siguen todos en la base de datos**
(ninguno "no está"). Dónde están:

| Qué son | Materiales |
|---|---:|
| Descripción del anejo de criterios de `0051`/`0060` (211) y `0236`/`0237` (5): el mismo material está en el Excel con el texto del cuadro de precios (buena parte de los 259 "nuevos" son esas mismas piezas, `0051`/`0060`) | 216 |
| Tabla de un lote que el expediente no tiene (`6.20/28510.0094`/`0141`, `6.21/28510.0017`, familia `6.21/28510.0058`/`0130`, `6.24/28510.0064` LOTE 3, `3.23/28510.0135`): antes salían atribuidas a otro lote | 65 |
| Tabla de un hermano fuera del catálogo (`6.21/28510.0066`, "LISTADO LOTE 1" de `0065`) | 17 |
| Tabla sin cabecera de lote (`6.21/28510.0017`, familia `0058`/`0130`) | 16 |
| Con lote, fuera del Excel por otro motivo | 1 |

Todo ese movimiento es de la tercera parte de ayer (pasadas F1-F10), no del
arreglo de hoy: F12 y F13 solo difieren en las 4 líneas de arriba. **Lo que
decide si el catálogo se entrega** son los ~98 materiales de la segunda a
la cuarta fila: están en tablas de lotes cuyo expediente no está en el
catálogo, o sin lote, y por eso no salen en el Excel de nadie. Es la
decisión pendiente desde el 12-09 (bloque 4).

## Bloque 2 — las páginas "que el localizador no abría"

**La premisa no se sostiene: el localizador sí abre esas páginas.**

- **`6.24/28510.0064`, p.115-119**: están en los dos Contratos (144 p., el
  pliego entero), no en ningún anejo (el ANEJO_1 tiene 29 páginas; es su
  p.19-23). Las abre (densidad 0,16-0,21, cinco grupos de marcadores) y
  `pdfplumber` las lee limpias: "Lote 1: Cables señalización", P-001…P-1xx.
  Las líneas del LOTE 1 están en el catálogo, pero su página de origen es
  la p.128-135: la tabla de "impacto del fallo en la seguridad" del anejo 2,
  que repite los mismos códigos con los mismos precios, se procesa después
  y se queda el ancla de página. No se pierde nada (verificado: los mismos
  precios en las dos tablas).
- **Contratos de `6.22/28510.0122`**: el localizador abre las 22 páginas de
  los dos cuadros (p.117-138 y 116-137). Lo que falla es `pdfplumber`: la
  tabla no tiene líneas horizontales entre filas, solo cortes en las
  verticales, y la extrae como **una única fila con 41 códigos en una
  celda** y los precios repartidos en tres filas (16+13+12). Una fila así no
  cuenta como fila de datos (`_es_fila_de_datos`), la tabla se descarta por
  espuria y el Contrato no aporta ninguna línea de esas 22 páginas, salvo
  tres restos sin lote en p.123/134 (122/133), fuera del Excel.

**Medida en el corpus:**

| | Páginas | Documentos |
|---|---:|---:|
| Con filas de datos que el localizador no abre (mismo criterio que la medición del 14-09: identificador de fila e importe en la misma línea) | 246 → 10 → **6** con los arreglos de abajo | 30 → 8 → **4** |
| Con tablas de filas fundidas por `pdfplumber` (una celda con 3+ códigos) | **62** | **8** |

- De las 10 que no se abren: 5 son las fórmulas del modelo indexado de
  carril ("P1 PPT 99,55 €/M", no una tabla); 1 (`3.23/28510.0135` p.5) trae
  dos filas que ya están en el catálogo; y 4 perdían material de verdad:
  - **La tabla de carril de `6.21/28510.0041`** (ANEJO p.3 y Contrato
    p.113), que el expediente perdía entera (sus dos carriles, 500.000 €):
    cabecera "Mat. | Designación | Medición estimada | Precio unitario |
    IMPORTE", con un único grupo de marcadores reconocible y solo dos filas.
    **Arreglado**: "Mat." cuenta como marcador de matrícula. Medido antes de
    aplicarlo sobre el corpus entero: abre 3 páginas más, las dos de esa
    tabla y una sin tabla. (Añadir "designación" y "medición" abría 77
    páginas y 129 filas nuevas, sobre todo los presupuestos por lote de
    `3.23/28510.0135`: ampliación de alcance, descartada.)
  - **Los cuadros de precios de balasto de `6.20/28510.0080` (Contrato
    p.106) y `6.19/28510.0025` (ANEJO p.29)**: un cuadro de cinco filas en
    mitad de una página de prosa, con densidad 0,023, por debajo del mínimo
    (0,025). El P-4 (m³·km de transporte, 0,12 €) solo está ahí; el
    presupuesto de la página siguiente no lo trae. **Arreglado**: la regla
    de "tres filas con identificador e importe en la misma línea" vale
    también por debajo de la densidad. Medido: entran exactamente esas 2
    páginas en todo el corpus.
- De los 8 documentos con filas fundidas, **6 no pierden nada**: sus
  códigos están todos en el catálogo del expediente, sacados limpios del
  anejo (los 407 de la familia `0122`; los 20 de `0126`/`0125`/`0094`; los
  102 P-2xx de `0064`, que son del LOTE 2 y es correcto que falten en `0073`,
  LOTE 1). Los otros dos: `6.24/28510.0208` p.99 no es un cuadro de precios
  (referencias de fabricante, sin importes; sus filas ya están, fundidas y
  con motivo), y `6.21/28510.0152` p.114 (rodillos) tiene sus 4 materiales
  en el catálogo desde el anejo y otro Contrato, **pero dejaba una línea
  basura en su LOTE 1 con cantidad 600.200.201**: las cuatro cantidades de
  la celda fundida ("600\n200\n20\n1") pegadas en un número.
  **Arreglado**: `parsear_numero_es` rechaza una celda con dos o más cifras
  completas, una por línea ("varios valores, uno por línea"); un número
  partido por el ancho de columna ("1.234\n,56 €", "34.100,00\n€") sigue
  siendo uno.

Separar de verdad las filas fundidas (reextraer la tabla por posiciones de
texto) no se ha hecho: en el corpus actual no recupera ningún material que
falte.

## Bloque 3 — la tabla "LOTE 6: RAM NORTE"

**`pdfplumber` sí la detecta, pero recortada**: su caja empieza en x=151 y
le falta la primera columna, la de los códigos P-1…P-4. Sin ningún código,
`extraer_tablas_pagina` la descarta por espuria. La causa está en los
trazos del PDF: el ajuste que "imanta" en una sola coordenada las líneas
verticales separadas por menos de 3 pt (`snap_tolerance`) se aplica a la
página entera. El borde izquierdo de la tabla del LOTE 5, justo encima
(x≈96), arrastra el del LOTE 6 (x≈99,1-99,7) hasta x=95,9. Sus líneas
horizontales empiezan en x=99,7, a 3,8 pt del borde, más que la tolerancia
de intersección: ya no se cortan y la primera columna no forma celdas.

**Arreglo**: un segundo intento con `snap_x_tolerance=1` (sin imantar en
horizontal), **solo para las tablas que el primero descarta**, aceptando
del segundo intento solo las que traen filas de datos, se solapan con una
descartada y no con una ya aceptada. Las tablas que hoy salen no se tocan
nunca: ni se vuelven a extraer. Medido sobre el corpus entero antes de
aplicarlo: el segundo intento recupera **exactamente una tabla**, esta.
Resultado en seco: P-1 65.000 m³ a 14,20 €, P-2 64.000 a 16,50 €, P-3
65.000 a 1,10 €, P-4 100.000 m³·km a 0,12 €, los cuatro precios leídos ayer
del PDF.

La unidad de esa tabla viene partida ("m3x\nkm") y salía como "m3x km";
de paso, una unidad partida en dos líneas se une cuando la primera es una
sola palabra y la segunda sigue en minúscula ("m3xkm", "€/transporte"; "t x
km", 72 líneas, no se toca; "ud\nud\nud", tres filas fundidas, tampoco).

**F14** (con "Mat.", celdas de varios valores y el segundo intento) frente a
F13: +6 líneas, las dos de carril de `6.21/28510.0041` y las cuatro del
LOTE 6 de `0016`. Pero F14 destapó dos cosas, las dos corregidas antes de
F15:

- **Una regresión de la regla de "varios valores"**: en `6.21/28510.0108`
  (anejo 588, p.29-30) la celda de precio es "80.500,3\n5" -- 80.500,35 €
  partido tras el primer decimal --, y la primera versión la tomaba por dos
  valores. Al no poder leer el precio, la recuperación de columna fantasma
  se quedó con la cantidad de al lado: **30 líneas de la familia
  `0108`-`0113` pasaron de 85.050 / 90.174 / 80.500,35 € a 4 o 5 € en F14**.
  La regla exige ahora que todas las líneas tengan la misma forma (mismos
  decimales, o ninguno); F15 las repone (verificado abajo).
- Las líneas de carril salían sin cantidad: la medición y su unidad vienen
  juntas ("2211,67 m") en la columna que el mapeo da por unidad, con la de
  cantidad vacía, y se descartaban como unidad numérica. Ahora se leen como
  cantidad y unidad (misma forma que ya se leía en la celda de cantidad,
  `_UNIDAD_EMBEBIDA_EN_CANTIDAD_RE`), con motivo.

## Bloque 4 — pendientes antiguos

### Líneas de lotes no declarados: decisión del cliente, sin forzar

**2.161 líneas** sin lote porque su tabla declara un "LOTE N" que el
expediente no tiene: 1.227 en expedientes que ya saben cuál es su lote (son
tablas de los otros lotes de la licitación: familia del acuerdo marco
`6.24/28510.0130`/`0152`/`0153`, balasto `0015`/`0016`/`0143`/`0144`, repuestos
`6.21/28510.0130`/`0136`, `6.20/28510.0059`/`0060`...) y 934 en principales o
expedientes sin lote propio (`6.21/28510.0058`/`0135`/`0137`/`0138`,
`6.22/28510.0103`/`0105`...). Ningún documento de esos expedientes dice que
el lote quedara desierto (búsqueda de "desierto/a" junto a "lote N" en todo
su texto): son lotes adjudicados cuyo expediente no está en el catálogo.

Dos decisiones distintas, las dos del cliente:

1. **Cómo se cuentan.** Hoy van a "pendientes de revisión" con "Que alguien
   compare con el documento y corrija el número de lote". Para las 1.227 de
   expedientes que saben su lote no hay nada que corregir: el documento dice
   de qué lote son, y ese lote no es este expediente. La propuesta del 12-09
   era una categoría propia en el Resumen ("tabla de otro lote de la
   licitación, cuyo expediente no está en el catálogo") que no pida
   revisión, igual que ya se hace con el anejo de criterios y con los
   hermanos fuera del catálogo (461 líneas).
2. **Si deben verse en el Excel.** Unos 65 materiales (matrícula o
   descripción) solo están en esas tablas (bloque 1), así que hoy no salen
   en el Excel de nadie. Mostrarlos exigiría ponerlos bajo un lote cuyo
   expediente no está, sin baja ni adjudicatario.

### `6.22/28510.0058` sin importe — resuelto, y en general

(El encargo dice `6.20/28510.0058`; el pendiente documentado ayer es
`6.22/28510.0058`, LOTE 2 de tornillería. `6.20/28510.0058` es otro caso:
uno de los 6 lotes de traviesas de `0054`, sin ningún documento que diga
cuál es el suyo, que ya muestra su motivo de revisión.)

Su única adjudicación con importe es el RESUELVE con la errata de número,
que desde ayer no se atribuye a ningún lote. Pero su Contrato lo declara, en
una redacción fija de la plantilla: "Ascendiendo el importe de licitación
del lote 2 a 2.400.000,00 € (IVA excluido)" y "CUARTO. El importe del
contrato es de: - Base imponible ... 2.400.000,00 €". Medido sobre los 98
expedientes que conocen su lote: 40 no tenían importe de adjudicación y 92
ninguno de licitación; el Contrato propio trae el importe del contrato en
47, y **en los 24 que ya tenían importe de adjudicación coincide siempre**.

`IdentidadContrato` lee ahora los dos importes de la cabecera del Contrato
(el de licitación solo si su "lote N" es el del propio Contrato: el de
`6.21/28510.0016` dice "del lote 1" siendo el LOTE 2), y
`_completar_importes_con_contrato` los usa **solo para rellenar huecos**,
nunca pisando un importe de la adjudicación o del Anuncio, en los dos
caminos (lotes declarados y lote implícito del Contrato propio), cada uno
con su traza a la página del Contrato.

### Filas desalineadas de `ANEJO_ce1df15b39efdb8c.pdf`: mirado, sin tocar

p.21 y p.36 (doc 586, compartido por `6.21/28510.0108`-`0113`): los códigos
van unas veces en la fila de sus datos y otras en una fila propia justo
debajo, mezclados con trozos del sello de verificación ("ps", "adila",
"v/vsc/se.b"). Las líneas que salen de ahí ya se quedan fuera del Excel
(mapeo incoherente, o sin lote en `0112`/`0113`) y **esos materiales entran
bien desde el anejo 588**. Emparejar cada código con la fila de datos de
encima es heurístico, y un emparejamiento equivocado fundiría dos
materiales distintos bajo la misma clave (el precio de uno en el otro): no
compensa para lo que aporta.

## Bloque 5 — cierre

**F15**, pasada completa con todo el código de la sesión (358/358).
Frente a F14:

- **+15 líneas**: el P-4 (m³·km de transporte, 0,12 €) de los 14 expedientes
  de balasto que comparten el anejo de `6.19/28510.0025` (p.29) y de
  `6.20/28510.0080` (Contrato p.106).
- **La regresión de F14, corregida**: las 30 líneas de `0108`-`0113` vuelven
  a 80.500,35 / 85.050 / 90.174 €.
- Carril de `6.21/28510.0041`: cantidad 2.211,67 y 7.800 m.
- Unidades "m3xkm" y "€/transporte" (15 líneas). Y un efecto no buscado:
  "Precio mensual" (`4.26/28510.0020`, 6 líneas) salió como
  "Preciomensual"; la unión exige ahora que la primera línea no sea una
  palabra corriente (lleve cifra o símbolo). Corregido para F16.
- **Importes de lote**: de los 98 expedientes que conocen su lote, sin
  importe de adjudicación 40 → 17 y sin importe de licitación 92 → 39
  (`6.22/28510.0058`: 2.400.000 € de licitación y de adjudicación).
- **Bajas derivadas nuevas**: en `3.23/28510.0135` (lotes 2 y 6: 30,95 % y
  5,67 %) y `4.26/28510.0020` (lotes 1 y 2: 2,58 % y 3,10 %) no hay baja
  declarada, y ahora hay los dos importes (uno de ellos del Contrato) y son
  distintos: `calcular_baja_efectiva` deriva la baja de los importes, como
  ya hacía en otros 83 lotes del corpus (p.ej. `2.23/28510.0010`, 35,27 %).
  59 líneas pasan de precio adjudicado "pendiente" a uno derivado. Es la
  regla que ya aplicaba el sistema; se señala porque es un cambio visible.

**Valores antiguos de celdas con varios valores**: "un `None` no pisa un
valor ya conocido" impide que el reproceso borre lo que una pasada antigua
guardó pegando los valores (600.200.201 en `0152`; 111 y 1111 en `0208`,
cuatro "1" pegados). Mismo criterio que la sesión del 07-09 con las
unidades: corregidos en base de datos, las 3 filas cuyo motivo de hoy dice
"la celda trae varios valores", con copia previa (`varios_valores_antes.csv`
en el scratchpad). La extracción ya no los vuelve a producir.

**Auditoría de F15**: los mismos avisos de siempre, el "error" conocido de
las 11 parejas de códigos distintos con el mismo texto y precio que el
propio documento repite (`0051`/`0060`, y `4.25/28510.0132`, Cod0005/Cod0013)
y el de "líneas que cambian sin cambiar documentos" en los 15 expedientes
del P-4 de balasto (cambio de código, esperado). Y un aviso que se disparó:
"importe de licitación compartido entre expedientes" pasó de 31 a 275
grupos. 221 eran el mismo lote visto desde el principal y desde su propio
expediente (mismo código de lote), justo lo que el importe del Contrato
completa bien. **Acotado**: solo avisa si el mismo importe del mismo
documento está en lotes que no son el mismo (un lote sin código cuenta como
distinto de todos).

**Hallazgo previo, no de hoy, sin tocar**: `trazas_origen` añade las trazas
de lote en cada pasada sin borrar las anteriores (7.848 filas de
`baja_declarada` para 440 distintas). No afecta al catálogo ni al Excel,
pero choca con la idempotencia (invariante 9).

## Pendiente al cerrar

- **Decisión del cliente: las 2.161 líneas de lotes no declarados** (bloque
  4): cómo se cuentan en el Resumen y si los ~65 materiales que solo están
  en ellas deben verse en el Excel. Junto con las tablas de hermanos fuera
  del catálogo (decidido el 14-09: se conservan sin lote) y las tablas sin
  cabecera de lote (pendientes de revisión), es lo que deja materiales
  fuera del entregable; todos siguen en la base de datos.
- **Filas fundidas por `pdfplumber`** (62 páginas, 8 documentos): sin
  pérdida de material en el corpus actual; separarlas de verdad
  (reextracción por posiciones de texto) solo compensaría si un documento
  así fuera la única fuente de su cuadro.
- **Ancla de página del LOTE 1 de `6.24/28510.0064`**: apunta a la tabla de
  impacto (p.128-135), no al cuadro (p.115-119); mismos códigos y precios.
- **`trazas_origen` duplica las trazas de lote en cada pasada** (hallazgo
  previo, bloque 5).
- **Filas desalineadas de `ANEJO_ce1df15b39efdb8c.pdf`**: mirado, sin
  impacto en el Excel; no se toca.
- `6.20/28510.0058`: 6 lotes de traviesas sin ningún documento que diga cuál
  es el suyo (ya con su motivo).

## Cierre (a petición del cliente, sin terminar el bloque 5)

**F16** (pasada final con todo el código, incluidos la unión de unidades
corregida y la auditoría acotada) terminó 358/358 con su auditoría, **sin
revisar**: no se ha comparado con F15, ni exportado el Excel final, ni hecho
la comparación de materiales distintos contra ayer con ese estado. La última
comparación medida es la de F13: 5.519 → 5.463 materiales distintos, los 315
que salen siguen en la base de datos (bloque 1). Lo esperado de F16 frente a
F15: solo "Precio mensual" en 6 líneas de `4.26/28510.0020`, y que no
reaparezcan los 3 valores corregidos en base de datos.
