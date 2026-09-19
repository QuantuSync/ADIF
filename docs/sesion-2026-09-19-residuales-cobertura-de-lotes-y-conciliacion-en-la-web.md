# Sesión 2026-09-19 (quinta parte) — Los tres residuales, las cantidades sin determinar, la cobertura parcial de lotes y la Conciliación en la web

Continúa `docs/sesion-2026-09-19-espacios-del-contrato-y-precio-adjudicado.md`.
Seis bloques.

**Lo primero, porque cambia cómo se lee el bloque 3: la premisa del encargo no
era correcta.** "Expedientes multilote donde solo algunos de sus lotes aportan
líneas" no describe a ninguno de los 14: **en los catorce, ningún lote aportaba
una sola línea al entregable**. Once tenían literalmente cero líneas en base de
datos y los otros tres (`3.21/28510.0158` con 7, `3.22/28510.0048` con 1 y
`6.23/28510.0105` con 35) las tenían todas huérfanas, sin lote, así que no
llegaban al Excel. Lo que la Situación `Licitación por lotes de la que solo se
conocen algunos lotes` dice de verdad es *"de los N lotes que declara la
licitación, solo de algunos se conoce la baja o el importe"* — nada sobre
líneas. Se contesta abajo la pregunta que el encargo quería hacer (qué lotes
faltan, si su cuadro está publicado y por qué no entra) con esa corrección
delante.

---

## Bloque 1 — Los tres residuales

### 1.1 Las 13 filas de cantidad

Las 13 son, exactamente, las líneas con la cantidad vacía de esos cinco
expedientes. **5 se arreglan, 8 no, y cada una con su motivo.**

| Expediente | Filas | Veredicto |
|---|---:|---|
| `6.24/28510.0173` p.9 | **5** | **Arregladas.** Su cantidad cae en la columna fantasma de al lado, igual que su descripción y su precio. |
| `6.26/28510.0030` p.11 | 5 | Legítimas. |
| `3.18/28510.0082` p.238 | 2 | No se arreglan solas: ver abajo. |
| `6.24/28510.0125` p.9 | 1 | Legítima. |
| `6.17/28510.0116` | 0 | No tenía ninguna línea; entra por 1.2. |

**Las 5 de `6.24/28510.0173`, arregladas.** Su cabecera es "PARTIDA |
MATRÍCULA | [fantasma] | DESIGNACIÓN | [fantasma] | [fantasma] | PRECIO
ADQUISICIÓN | [fantasma] | CANTIDAD ESTIMADA" (10 columnas) y en esas cinco
filas la descripción, el precio **y la cantidad** caen cada uno un sitio a la
izquierda de la columna que la cabecera etiqueta. La descripción y el precio ya
se recuperaban (`_recuperar_descripcion_y_precio_columna_fantasma`); la
cantidad se perdía por **puro orden de ejecución**:
`app.catalogo._construir_campos` solo intenta recuperarla si la descripción ya
está resuelta —guarda deliberada, para no confundir un desplazamiento de una
celda con uno de la fila entera— y en estas filas la descripción no se resuelve
hasta después. Ahora la misma recuperación de una sola columna se intenta
también ahí, con sus mismas guardas.

Una guarda nueva, y hace falta: `_parece_cantidad_recuperable` se apoya en
`parsear_numero_es`, que saca el número aunque la celda traiga texto alrededor
("Ancho 1668" → 1668). Para esta vía eso no vale, así que se usa un predicado
estricto (`_parece_cantidad_limpia`: la celda es **solo** el número). El
predicado de siempre no se toca — cambiarlo quitaría cantidades ya guardadas
por las vías anteriores, y eso es un cambio de datos que nadie ha pedido.

**Las 5 de `6.26/28510.0030` son legítimas, y el motivo importa.** Su cuadro
trae **dos** pares de columnas: "Precio suministro | Cantidad estimada" y
"Precio reparación | Cantidad estimada". En esas cinco filas el documento
imprime `-` en el precio de suministro —la convención administrativa de "no
aplica", CONTEXTO.md sección 8— y deja su cantidad en blanco. El
`1.473,52 €` que sí traen es el **precio de reparación**, otro concepto y otro
par de columnas que el esquema del catálogo no modela. Escribirlo como precio
unitario de suministro sería inventar.

**La de `6.24/28510.0125` es legítima:** su fila (`666060000`, armario
repartidor de fibra óptica) deja la celda de cantidad en blanco en el propio
PDF, mientras las trece filas de su misma tabla traen `1`.

**Las 2 de `3.18/28510.0082` no se arreglan, y no por la cantidad.** Su tabla
es "MATRICULA | DESIGNACIÓN | U | IMPORTE": el `75` y el `1` de la columna "U"
son la cantidad, y el mapeo da esa columna a `unidad_medida` (de ahí que los
descarte como unidad no conocida). Rellenar solo la cantidad dejaría la fila
**descuadrada con su propio IMPORTE**, porque la columna que hoy es "Precio
unitario" es en realidad el importe del renglón: 75 × 27.918,75 € no es
27.918,75 €. El arreglo completo es derivar el precio del importe
(27.918,75 / 75 = 372,25 € exacto, y las ocho filas de la tabla dividen
exactas), y eso **cambia precios**, no cantidades: no está en el encargo y
queda anotado.

### 1.2 `6.17/28510.0116` — los precios sin decimales, demostrados

**Se demuestran, y entran: 3 líneas nuevas.** La regla que pidió el cliente,
implementada en `app.extraccion.tabla`: un precio escrito sin decimales y sin
símbolo (`5.400`) solo se acepta si existe **exactamente un** presupuesto de
licitación publicado que sea múltiplo entero exacto de la suma de los precios
del cuadro.

La demostración es de su propio `ANEJO_1`:

- p.3 §3 *"Las cantidades a suministrar serán las indicadas en el objeto (2
  CELDAS DE LÍNEA, 2 CELDAS DE MEDIDA Y 2 CELDAS DE LÍNEA CON TRANSFORMADOR)"*.
- p.3 §4 *"La dotación presupuestaria [...] se eleva a un total de 49.560 € sIn
  IVA"* (y su `ANEJO_2` p.2 lo repite: "Base Imponible Cifra: 49.560,00 €").
- p.9, el cuadro: 5.400 + 9.480 + 9.900 = 24.780.

**2 × 24.780 = 49.560,00 €, al céntimo.** Las tres líneas entran con su precio
y con la baja del 35 % ya aplicada (3.510,00 / 6.162,00 / 6.435,00 €).

Tres cautelas, cada una con su prueba en el test: una tabla que **mezcla**
importes de verdad y cifras peladas se descarta entera (la cifra pelada no es
un precio sin demostrar, es otra cosa); **sin presupuesto publicado el cuadro
se queda fuera**, literalmente lo que pidió el cliente; y si dos presupuestos
dividen exactos a la vez, el multiplicador es ambiguo y se descarta. Un entero
corto y suelto ("16", "2") nunca entra por esta vía: se exige al menos un grupo
de miles.

**Lo que sigue sin leerse de este expediente, anotado:** sus tres matrículas
llevan una letra al final (`69520000N`) y se descartan con su motivo.
Aceptarlas exige tirar un carácter que el documento imprime — es un cambio de
datos del catálogo que no está en el encargo.

### 1.3 `3.16/28510.0044` — relectura con un modelo mejor

**Coste real: 0,17 $.** Muy por debajo de los 5 $ que pedían aviso previo:
17.880 tokens de entrada y 3.108 de salida con `claude-opus-5` (5 $/25 $ por
millón), 47 s para seis páginas.

Se releyeron **solo sus páginas de cuadro**, las 14-19 del `ANEJO_1` de 130
páginas (el "ANEXO 1: DETALLE DEL PRESUPUESTO"). **4 se sustituyen** (15, 17,
18, 19) y 2 se quedan como estaban (14 y 16, que vuelven vacías con los dos
modelos).

La diferencia de lectura es la que esperaba el encargo. Con
`claude-haiku-4-5`, la p.17 daba *"Acondicionamiento e reemplazos Suministro de
acondicionas hasta 350kW [...] Etiqueta articulo la 13 trams de Mbs"* y una
tabla con las columnas cruzadas. Con `claude-opus-5` da la tabla entera, con su
cabecera real ("Nº Orden | Código | ... | MEDICIÓN PRESUPUESTADA | P.UNITARIO |
TOTAL") y sus filas cuadrando.

**14 líneas entran, y la aritmética cierra sola:**

| | |
|---|---:|
| Filas del cuadro que cuadran (cantidad × precio = total) | **15** |
| Líneas que entran al catálogo | **14** |
| Suma de cantidad × precio de las 14 | **822.343,17 €** |
| TOTAL que declara el propio cuadro (p.19) y su resumen (p.15) | **824.323,67 €** |
| Diferencia | **1.980,50 €** |

Los 1.980,50 € son **una sola fila**, la `12.01` de Seguridad y Salud, cuya
celda de descripción vuelve vacía (el rótulo "Seguridad y Salud" cae en la fila
anterior) y por eso no llega a ser una línea. 822.343,17 + 1.980,50 =
824.323,67 € exacto: no falta nada más.

#### Lo que hizo falta para que esas 14 líneas entren

La relectura por sí sola no bastaba: el cuadro **es un cuadro de precios que
ninguna etapa de la cascada reconocía**. Dos cambios, los dos acotados a la
evidencia que el propio documento da:

1. **Etapa 3 (localizador).** Ni "P.UNITARIO" contiene "precio", ni "MEDICIÓN"
   estaba entre los alias de cantidad, ni la columna de descripción lleva por
   rótulo otra cosa que el título del cuadro; y las p.18-19 no repiten
   cabecera. La señal que sí trae —y es la condición que puso el cliente— es
   **la aritmética de sus propias filas**: cada línea acaba en cantidad, precio
   e importe, y cantidad × precio = importe al céntimo. Tres líneas así en la
   misma página abren la página; una basta si la anterior ya está abierta.
   Medido en este documento: abre **3 páginas más** (17, 18, 19) y **no** la 15,
   que es el resumen de presupuesto.
2. **Etapa 4.** La misma identidad, columna a columna: si existen tres columnas
   (cantidad, precio, importe) de izquierda a derecha tales que **toda** fila
   que las trae rellenas cumple la cuenta, y hay al menos dos de esas filas, la
   tabla no es espuria. Cuatro guardas: una sola tripleta (si dos combinaciones
   cumplen, el mapeo es ambiguo y se descarta), ni una fila que la contradiga,
   **al menos una fila con cantidad distinta de 1** (sin ella la identidad es
   gratis: "1 × X = X" la cumple cualquier lista de conceptos a tanto alzado), y
   la tabla se devuelve por el camino normal —con su cabecera— para que la
   etapa 5 siga siendo la que traduce "P.UNITARIO" a `precio_unitario`.

Y **solo salen las filas que pasan la comprobación de su propia fila**, que es
la condición literal del encargo: las 9 filas de sección del presupuesto
("Obra civil", "Energía", "Gestión de Red"…) no traen cantidad ni precio, no
son materiales, y entraban como líneas sin precio hasta que se añadió ese
filtro.

#### La quinta guarda, y los dos defectos que la auditoría destapó

La primera versión de esta vía pasó las pruebas y el reproceso completo con
todo en verde, y **aun así estaba mal**: la auditoría de fin de ciclo dio
**2 errores**, y uno era real — **45 líneas de catálogo sin descripción** en
`2.23/28510.0098`, `6.22/28510.0051` y `6.22/28510.0159`. Su cuadro es
"TIPO | CANTIDAD | PRECIO UD. | PRECIO TOTAL" y la columna "TIPO" no es una
designación, es la **referencia de la herramienta**
("SFT01-2388L-PH-6920", "WCMX-04 02 08-R53", "SNC-55 R16 T03 IN6530"): las
filas cuadran (20 × 24,00 = 480,00) y entraban como líneas sin nada que leer
en almacenes, que es justo lo que la comprobación permanente de
`construir_linea_catalogo` existe para impedir (sesión 2026-09-06, bloque 2).

La guarda que faltaba, en dos mitades (`_tiene_columna_de_descripcion`):

- **A nivel de tabla**: alguna columna fuera de la tripleta tiene que ser una
  columna de **designación**, y la distinción no es "tiene letras" ni "tiene un
  espacio" — "sft" ya son tres letras y "WCMX-04 02 08-R53" ya tiene espacios.
  Lo que separa una designación de una referencia es que la designación son
  **varias palabras con letras de verdad**, y que lo son en **la mayoría de las
  filas**: en el cuadro de `2.23/28510.0098` solo 1 de sus 19 filas lo cumple;
  en el de `3.16/28510.0044`, todas.
- **A nivel de fila**: una fila solo llega a ser línea si trae letras en alguna
  columna fuera de la tripleta. Así la fila `12.01` de `3.16/28510.0044` p.19
  —que cuadra, pero cuya celda de descripción vuelve vacía— no sale, y el
  cuadro de esa página sí.

**Y el segundo defecto, que el primero destapó y es más de fondo: un hueco de
idempotencia real.** Con la guarda puesta, las 45 líneas **seguían en base de
datos**: `podar_lineas_obsoletas_de_documento` vivía dentro del
`if resultado.lineas:` del orquestador, así que un documento que deja de
aportar nada —porque una guarda nueva rechaza su tabla— conservaba para siempre
las líneas de la pasada anterior. Contra el invariante 9 de CONTEXTO.md, y
silencioso: no hay nada en el resultado del ciclo que lo señale. La poda corre
ahora siempre que el documento se procesa, con `ids_tocadas` vacío si no
produjo nada; `procesar_anejo` extrae el documento entero en una pasada, así
que "ninguna línea" significa "este documento ya no aporta nada", no "solo se
ha reprocesado una parte". Verificado: los tres expedientes vuelven a 0 líneas
(15, 10 y 10 podadas) y `3.16/28510.0044` se queda con sus 14.

**Queda anotado, sin decidir**: los tres cuadros de "TIPO | CANTIDAD | PRECIO
UD. | PRECIO TOTAL" son cuadros de precios de verdad, con 19, 13 y 13
artículos y su total al pie. Lo único que tienen por texto es la referencia del
inserto o de la fresa. Aceptarlos exige decidir que esa referencia es la
"Descripción del material" del catálogo — un cambio de datos que no está en
este encargo.

#### El sexto defecto: una cabecera que no dice nada, y un precio falso

Lo destapó la auditoría del quinto reproceso, con **1 error**: 4 líneas de
catálogo **sin descripción** en `2.22/28510.0075`. Son las 4 filas de su p.96,
que la vía aritmética acepta con razón —"1.1 | SERVICIO DE DESMONTAJE Y
POSTERIOR MONTAJE… | 5.200,00 € | 1 | 5.200,00 €", y la cuenta cuadra— pero
cuya **cabecera es `['PRESUPUESTO', None, None, None, None]`**: una palabra y
cuatro celdas vacías. Con eso la etapa 5 no tiene nada que traducir, y el mapeo
cayó entero un sitio a la izquierda:

| Campo del catálogo | Lo que le tocó | Lo que era |
|---|---|---|
| `descripcion` | `"5.200,00 €"` | el servicio |
| `cantidad` | `"SERVICIO DE DESMONTAJE…"` | `1` |
| `precio_unitario` | `1` | `5.200,00 €` |
| `codigo_precio` | `"5.200,00€"` | `1.1` |

La regla de "una descripción que es solo una cifra no es una descripción"
descartaba la cifra —bien— pero la red de rescate solo mira columnas que el
mapeo no reclama, y aquí la designación había caído en la que el mapeo llama
`cantidad`. Resultado: cuatro líneas sin descripción en el entregable.

**La fila ya no llega a ser línea.** Si la columna de descripción trae un
importe, el mapeo de esa cabecera está demostrado mal, y entonces **tampoco
valen el precio, la cantidad ni el código de precio de esa misma fila**:
publicar 1,00 € por un servicio de 5.200,00 € es peor que no publicarlo. Es
distinto del caso de 2026-09-14/16 —la fila sin descripción que **sí** se
conserva para revisión—: allí la fila no dice qué material es; aquí dice algo y
es falso. Son 4 filas en todo el corpus, y `2.22/28510.0075` se queda con la
única línea que ya tenía.

#### Una sexta guarda que se probó y se ha retirado

Los tres cuadros de referencia de herramienta no son el único caso en que la
tripleta aritmética acierta la cuenta y falla el sentido. Se probó una guarda
más: **exigir que la primera columna de la tripleta —la cantidad— no traiga
símbolo de moneda ni forma de importe**, que es lo que distingue "20 × 24,00 =
480,00" de una fila donde lo primero que hay es un precio.

**Se ha retirado, porque quita más de lo que arregla.** Excluía 4 líneas
dudosas y se llevaba por delante **9 buenas**: el cuadro de `2.19/28510.0214`
está rotulado "Concepto | Precio unitario | Cantidad | Presupuesto" —el precio
va **antes** que la cantidad, y es un cuadro perfectamente legítimo— y lo mismo
pasa en `2.20/28510.0083`. El orden de las columnas no es una propiedad de los
cuadros de precios, y la aritmética ya no depende de él: `_tripleta_que_cuadra`
busca (q, p, t) de izquierda a derecha sin presuponer cuál es cuál.

La evidencia queda en la prueba
`test_un_cuadro_con_el_precio_antes_que_la_cantidad_tambien_se_demuestra`, para
que la guarda no vuelva a ponerse sin ver primero qué se lleva.

#### La relectura, como mecanismo

`app.extraccion.ocr_relectura`, trabajo de cola `ocr_relectura` y
`POST /mantenimiento/ocr/releer` (`documento_id`, `paginas`, `modelo`
opcional). Vive en el worker porque es el único proceso con proveedor de modelo
(CONTEXTO.md sección 10). Cuatro condiciones:

- **Solo las páginas que se le nombran.** Releer las 130 costaría veinte veces
  más y las otras 124 ya están bien leídas.
- **Solo con el modelo que se le nombra** (payload, o `OCR_MODELO_RELECTURA`).
  Sin ninguno de los dos **falla**: releer con el modelo de siempre daría el
  mismo resultado, y hacerlo en silencio sería gastar por nada.
- **Nunca empeora lo que había.** Una página cuya relectura vuelve con error o
  vacía se deja como estaba.
- **Queda escrito de dónde sale cada página**: cada página releída guarda su
  `modelo` dentro de `CacheOcrDocumento.paginas`, y el `modelo` de la caché
  sigue siendo el base, que es el que gobierna su validez.

No se dispara solo y no tiene programación propia: releer con un modelo más
caro es una decisión por documento, tomada mirando la lectura que hay.

---

## Bloque 2 — Las cantidades que no se pueden relocalizar por código ni matrícula

La tercera parte dejó **173 sin determinar** de las 6.645 vacías: no se pudo
encontrar su fila en el PDF porque se buscaba por código de precio o matrícula
exactos y esas líneas no tienen ninguno de los dos. Esa clasificación no se
guardó, así que aquí se ha rehecho sobre el **conjunto reproducible que las
contiene**: las líneas del entregable con la cantidad vacía y **sin código de
precio y sin matrícula** — las únicas que, por construcción, no se pueden
localizar por esa vía. Son **285**, en 40 documentos.

**La vía nueva: página y posición de la traza de origen.** Se vuelve a correr
la cascada de cada documento con un espía sobre `construir_linea_catalogo`, que
guarda para cada línea producida la **fila cruda** y el **mapeo de columnas**
con que se construyó —es decir, su posición exacta dentro de la tabla de su
página— y se empareja con la línea guardada por (página, descripción).

**Relocalizadas: 285 de 285. Ninguna se queda sin determinar.**

| Veredicto | Filas | |
|---|---:|---|
| Su documento no declara ninguna columna de cantidad en ninguna de sus tablas | **103** | legítima |
| Su fila deja la celda de cantidad vacía en el PDF | **93** | legítima |
| Esta tabla no declara columna de cantidad y su fila no trae ninguna | **79** | legítima |
| Señaladas como posible hueco | **10** | ver abajo |

**De las 10 señaladas, 4 no son un hueco**: son las partidas alzadas de
`6.20/28510.0115` (p.18 y p.20), cuya celda en la columna de cantidad trae un
**importe** ("1.467,20 €", "3.457,00 €") porque su texto ocupa menos columnas
que el resto de la tabla. La regla de 2026-09-14 ya lo lee como el precio de la
partida ("una cantidad nunca lleva el símbolo €"), y la fila no tiene cantidad:
legítima.

**6 huecos reales, los 6 arreglados:**

- **5 filas, la misma partida alzada** ("PARTIDA ALZADA A JUSTIFICAR PARA
  IMPREVISTOS", 20.000,00 €) del `ANEJO_3.pdf` p.3 que comparten cinco
  expedientes hermanos (`6.21/28510.0058`, `0130`, `0135`, `0137`, `0138`). Su
  fila va desplazada +1 en descripción y precio, pero su **última** columna —la
  de cantidad— sigue en su sitio con el `1` que imprime el documento;
  desplazada, apuntaría a la columna 10, que no existe, y `_mapeo_desplazado`
  la dejaba en `None`, apagando también la recuperación de columna fantasma.
  `_cantidad_del_borde_derecho` la lee en su columna **sin desplazar**, y solo
  si ese índice existe, ningún campo del mapeo desplazado lo reclama y el valor
  es solo un número. Por construcción no hay otro sitio donde pueda estar: una
  columna que el desplazamiento empuja más allá del borde derecho de la fila es
  la no desplazada o no es nada.
- **1 fila de `4.26/28510.0031`** (p.8, "Partida Alzada Repuestos estufas").
  Causa: **"MEDICIÓN" no estaba en el vocabulario de cantidad de
  `app.extraccion.mapeo_cabecera`**, aunque `app.extraccion.tabla` y
  `app.extraccion.localizador` ya lo trataran como tal desde 2026-09-15. Una
  cabecera perfectamente legible ("SUMINSTRO CODIGO | DESCRIPCIÓN | UNIDAD |
  MEDICIÓN | Precio Unitario | IMPORTE") resolvía determinista con `cantidad`
  a `None`. Añadido el alias y borradas las **2** entradas de caché que lo
  traían con ese mapeo. La cantidad que aparece es `0`, que es lo que imprime
  el documento (y su IMPORTE es 0,00 €: la fila cuadra consigo misma).

---

## Bloque 3 — Los 14 de cobertura parcial de lotes

### Qué son de verdad, uno a uno

La Situación no habla de líneas, habla de **lotes con baja o importe conocido**
sobre los que la licitación declara. Casi todos son compras multi-lote del
Laboratorio Central de ADIF, donde cada lote tiene su propio expediente
correlativo y el nuestro solo carga con algunos.

| Expediente | Lotes que registra | de N declarados | ¿Cuadro publicado? | Por qué no entra(ba) |
|---|---|---:|---|---|
| `2.19/28510.0145` | 4 | 4 | Sí, `ANEJO_1` p.17 | Su único cuadro es un **modelo de oferta en blanco** ("Consumible \| Precio Licitación \| % de baja€ \| Precio Ofertado"), que la sesión 2026-09-18 descarta a propósito |
| `3.18/28510.0047` | 8 | 8 | **No legible**: sus tres documentos de contenido son escaneados y el `ANEJO_1` no tiene página candidata | Límite de origen |
| `3.19/28510.0198` | 1, 2 | 2 | **No**: su `ANEJO_1` es escaneado y su `ANEJO_2` (77 pág.) no publica cuadro | Límite de origen |
| `3.19/28510.0218` | 3, 4 | 4 | Sí | **4 líneas nuevas**, todas huérfanas: sus tablas son de los lotes 1 y 2, que no son suyos |
| `3.21/28510.0096` | 1, 2 | 2 | Sí, `ANEJO_1` p.6 | **3 líneas nuevas en el lote 1** |
| `3.21/28510.0098` | 1, 3 | 3 | Sí, `CONTRATO` p.106 y `ANEJO_1` p.6 | **1 línea nueva en el lote 3**; la del lote 1 la rechaza la prueba aritmética |
| `3.21/28510.0158` | 1, 5 | 5 | Sí | **14 líneas**, todas huérfanas: sus cuadros son de los lotes 2, 3 y 4 |
| `3.22/28510.0009` | 2, 3 | 3 | Sí, `ANEJO_1` p.6-8 | **13 líneas, 7 en el lote 2** |
| `3.22/28510.0048` | 1, 3, 5 | 5 | Sí, `ANEJO_1` p.6-7 | **5 líneas, 4 en el lote 1** |
| `3.22/28510.0106` | 3, 5 | 5 | Sí, `ANEJO_1` p.6 | **5 líneas, 2 en sus lotes 3 y 5** (las dos cuadran al céntimo); las otras 3 son de los lotes 1, 2 y 4, que no son suyos |
| `6.19/28510.0206` | 2, 3 | 3 | **No**: las dos tablas de su `ANEJO_2` (p.54 y p.63) son **formularios en blanco** -- "DESCRIPCIÓN \| PRECIO UNITARIO \| Nº DE UNIDADES \| PRODUCTO PARCIAL" con todas las celdas de datos vacías, y una tabla de porcentajes por mes | No hay cuadro con precios que leer |
| `6.23/28510.0074` | 3, 4 | 4 | Sí, `CONTRATO` p.5-17 | Sus documentos declaran `EXPEDIENTE PRINCIPAL` `6.23/28510.0066`, otro expediente |
| `6.23/28510.0105` | 3, 4, 6, 9 | 9 | Sí, `ANEJO_1` p.3-13 | **207 líneas** (eran 35), todas huérfanas: ninguna cabecera "LOTE N" en su franja |
| `6.24/28510.0113` | 2 | 2 | **No**: su único documento es la Resolución de Adjudicación | Límite de origen |

**Tres tienen un límite de origen real** (`3.18/28510.0047`,
`3.19/28510.0198`, `6.24/28510.0113`): el cuadro no está publicado o no es
legible, y no hay nada que recuperar sin inventarlo.

### La recuperación, por geometría

El cuadro de precios de estas compras **mete todos sus lotes en una sola tabla**
de `pdfplumber`, cada uno encabezado por una fila cuya única celda es la
etiqueta del lote:

```
['LOTE 1', '', '']
['Concepto', 'Unidades', 'Importe']
['Calibrador multiproducto con opción de calibración', '3', '210.000,00 €']
['LOTE 2', '', '']
['Concepto', 'Unidades', 'Importe']
['Calibrador de comprobadores de seguridad eléctrica', '1', '23.000,00 €']
['LOTE 3', '', '']
['Divisor de tensión y Multímetro de alta tensión', '1', '10.000,00 €']
['TOTAL: 243.000,00 €', '', '']
```

La tabla entera se descartaba como espuria porque su **primera** fila no es una
cabecera de columnas y no hay ni código de precio ni matrícula. Y aunque se
aceptara, las líneas de los tres lotes quedarían mezcladas o huérfanas: la
etapa 3.5 busca el "LOTE N" en la franja de página que **precede** a la tabla,
y aquí las etiquetas van dentro.

`_bloques_por_fila_de_lote` la parte en un bloque por etiqueta. Es certeza
estructural por geometría, no por parecido ni por proximidad: el documento pone
cada bloque debajo de su propia etiqueta, en orden de lectura, y cada bloque
sale con **su propia caja** (calculada de la geometría de sus filas) para que
la etapa 3.5 avance de arriba abajo sin franjas de altura negativa. La etiqueta
viaja en `TablaExtraida.titulo_propio`, aparte de la cabecera de columnas, para
que la firma de cabecera —y con ella la caché del mapeo— siga siendo la misma
para los N bloques de un cuadro que repite la misma cabecera.

Guardas: cada bloque tiene que ser un cuadro de precios por sí mismo (con las
guardas de siempre); un bloque sin cabecera propia usa la del anterior (el
lote 3 del ejemplo no la repite, y es la MISMA tabla con las mismas columnas);
el pie de totales corta; y **esta vía solo se prueba cuando ninguna de las de
siempre acepta la tabla**, así que no puede quitar ni una fila de las que ya
salían.

**Un defecto encontrado al verificar, y corregido antes de reprocesar en
serio.** La primera versión dejaba que la franja de página decidiera, como
siempre, y los cinco bloques de `3.22/28510.0106` se quedaban **con el lote del
anterior**: entre el bloque del lote N y el del N+1 ese documento imprime *"El
presupuesto base del lote N es de VEINTISEIS MIL EUROS (26.000,00 €), IVA
excluido"*, y esa frase es una mención de lote perfectamente válida para la
etapa 3.5. Ahora **la etiqueta que la propia tabla trae encima de sus filas
gana sobre la franja** (`asociar_lote_tabla(texto_lote_propio=...)`): está
dentro de la tabla, justo encima de sus datos, y no hay declaración más
específica que eso. Sin etiqueta propia, la franja sigue mandando como siempre;
las dos cosas tienen su prueba. El cuadro de ese expediente cuadra ahora al
céntimo en sus dos lotes (1 × 15.000,00 € y 1 × 29.000,00 € contra presupuestos
de 15.000,00 € y 29.000,00 €).

### La prueba aritmética que exigió el cliente

`descartar_bloques_de_lote_que_no_cuadran`: las líneas recuperadas por esta vía
**solo entran si la suma de cantidad × precio unitario del lote cuadra con el
presupuesto de licitación publicado de ese lote**, cuando ese presupuesto
existe. Sin presupuesto publicado no hay con qué comprobar y entran, igual que
en la verificación del reparto por lotes de 2026-09-18.

Lo caza en el sitio: el cuadro de `3.21/28510.0098` es "Concepto | Unidades |
Importe" y su tercera columna es el **importe del renglón**, no el precio
unitario, así que 3 × 210.000,00 € da el triple del presupuesto de su lote 1
(210.000,00 €). Esa línea no entra, con su motivo. La del lote 3 —1 ×
10.000,00 € contra un presupuesto de 10.000,00 €— **cuadra al céntimo** y sí
entra.

### Dos lotes cuya suma no cuadra, y no es un error de lectura

Son líneas que entran por la vía del bloque 1 (la tabla demostrada por la
aritmética de sus filas), cuya condición es **por fila** y la cumplen todas. Su
suma por lote, en cambio, no cuadra con el presupuesto registrado, y las dos
veces por la misma razón medible:

- **`3.22/28510.0009` lote 2**: sus 7 líneas suman **21.500,00 €** y el
  presupuesto registrado para el lote 2 es 71.000,00 €. Pero las 6 líneas que
  el documento pone bajo "LOTE 1" suman **71.000,00 € exactos**, y 21.500,00 €
  es exactamente el presupuesto registrado para su lote 3. Es decir: **la
  numeración de lotes del cuadro y la de la adjudicación van desplazadas una
  posición.**
- **`3.21/28510.0096` lote 1**: sus 3 líneas suman **20.700,00 €** de un
  presupuesto de 22.200,00 €. Los 1.500,00 € que faltan son **una cuarta fila**
  del mismo cuadro ("Potenciómetro rotatorio", 10 × 150,00 €) cuyas celdas van
  desplazadas una columna y por eso no pasa la comprobación de su propia fila.
  20.700 + 1.500 = 22.200,00 € exacto. Y su segunda tabla, rotulada otra vez
  "LOTE 1." pero cuyo total (8.250,00 €) es el presupuesto del **lote 2**, la
  rechaza la prueba aritmética.

**No se toca ninguno de los dos.** Las líneas están demostradas fila a fila por
el propio documento; lo que no cuadra es la numeración de lotes del documento
contra la de la adjudicación, y eso es una pregunta para ADIF, no una decisión
de extracción.

### Un defecto de paso, corregido

`3.22/28510.0009` tumbaba la extracción de su `ANEJO_1` entero con
`UniqueViolation` en `cache_codigo_material`: dos tablas del mismo documento
derivan el término "CEPILLO" y la segunda inserción reventaba.
`guardar_codigo_material_cacheado` tolera ahora el duplicado y devuelve la
entrada existente sin pisar su valor — la primera respuesta del modelo para un
término es la que vale.

---

## Bloque 4 — El signo "!" que la fuente Calibri escribe por un espacio

**Celdas del catálogo actual que contienen un `!`: cero. En ninguna columna.**

Contado campo a campo sobre las 39.874 líneas, los 612 expedientes y sus lotes:
`codigo_precio`, `matricula`, `descripcion`, `codigo_material`,
`unidad_medida`, `unidad_medida_original`, `comentarios`, `clave_linea`,
`codigo_expediente`, `codigo_matriz`, `nombre_proyecto`, `codigo_interno`,
`estado_contrato_sap`, `estado_adif`, `identificador_lote`, `adjudicatario`,
`codigo_expediente_lote` — y también `fragmento`, que conserva el literal del
documento a propósito. **0 en todas.**

**Ninguna comparación de claves está fallando por eso**, y se puede afirmar sin
matices porque no hay ni un `!` que comparar: 0 líneas con `!` en la descripción
o en el código de precio, así que 0 pares que la recomposición pudiera unir o
separar. La regla de la cuarta parte
(`_recomponer_espacios_del_signo_admiracion`) ya dejó las 5 descripciones de
`4.26/28510.0005` recompuestas, y al coincidir con las del anejo la fusión por
firma las unió: el duplicado desapareció y con él el último `!` del catálogo.

**No hay más afectadas que las de `4.26/28510.0005`**, así que no hay nada que
corregir. El fenómeno sigue siendo amplio a nivel de corpus (78 de 1.642
documentos con texto cacheado producen algún `!`, 175.424 en total), pero
**esas páginas casi nunca son cuadro de precios**: mismo patrón que las cifras
en glifos CID de 2026-09-18, donde 178 documentos las traían y solo 1 llegaba
al catálogo. La regla queda armada para cuando llegue otro.

---

## Bloque 5 — La web

### Lo que había, comprobado antes de tocar nada

| Pregunta del encargo | Estado |
|---|---|
| ¿Muestra "Código de precio"? | **Sí, pero mal rotulado.** La columna era `codigo_precio` desde siempre y el encabezado decía "Código" a secas — indistinguible de "Código del material", que es otra cosa. |
| ¿Muestra "Estado según ADIF"? | **No.** `estado_adif` no estaba ni en `ExpedienteOut`: la API no lo servía, así que ninguna pantalla podía mostrarlo. |
| ¿Sigue mostrando la columna que se quitó? | **No.** "Nº de expediente (documento)" no aparece en ninguna pantalla; la sesión 2026-09-18 la quitó bien. |
| ¿Existe alguna vista de la Conciliación? | **No.** Ni pantalla ni ruta de API: la hoja solo se podía mirar abriendo el Excel. |
| ¿Qué acciones hay en la revisión de líneas? | **Las cuatro.** Confirmar, Corregir, **Descartar con motivo obligatorio** y Pendiente de consulta con nota obligatoria. Lo que se pidió en su día está hecho: una línea puede marcarse como errónea con su motivo y deja de estar pendiente para siempre. |

### Lo que se ha arreglado

- **"Código de precio"** con su nombre, el mismo que el Excel.
- **"Código del material"** como columna propia del catálogo: estaba en el
  Excel y en la API desde el principio y no se mostraba en ninguna pantalla,
  con su motivo de celda vacía ("no aplica" en una partida alzada, "no consta"
  cuando el vocabulario no casa la descripción todavía).
- **"Estado según ADIF"** en `/expedientes`, junto al de SAP y **nunca
  mezclado con él**: son dos volcados de SAP distintos (212 códigos en común,
  155 solo en uno, 146 solo en el otro) y juntarlos dejaría cada valor sin
  procedencia. Cada uno con su `title` explicando de qué listado sale.

### Las 18 columnas del Excel, y dónde está cada una en la web

Comprobado columna a columna, que es lo que pedía el encargo ("que la web
refleje exactamente lo que dice el Excel"):

| Columna del Excel | Dónde está |
|---|---|
| Código interno | Trazabilidad de la línea (`/catalogo`, al pulsar la fila) |
| Código de expediente | Columna "Expediente" de `/catalogo` |
| Código matriz | Trazabilidad de la línea, y columna propia en `/expedientes` |
| Título expediente | Columna "Título expediente" de `/catalogo` |
| Matrícula del material | Columna propia |
| Descripción del material | Columna propia |
| Código del material | **Columna propia, añadida en esta sesión** |
| Cantidad | Columna propia |
| Precio unitario | Columna propia |
| Lote | Columna propia |
| Precio adjudicado | Columna propia |
| Baja del lote | Trazabilidad de la línea (con la derivación escrita: precio × (1 − baja)) |
| Unidad de medida | Columna "Unidad" |
| Estado del contrato (SAP) | `/expedientes`, junto al estado de procesamiento |
| Objeto del contrato (documento) | Columna "Título expediente" (es el mismo dato) |
| Código de precio | **Columna propia, con su nombre desde esta sesión** |
| Motivo de las celdas vacías | En cada celda vacía, con su icono y su explicación al pasar el puntero (mismo criterio de tres motivos que el Excel) |
| Comentarios | Trazabilidad de la línea, y editable desde la cola de revisión |

Más "Estado según ADIF", que es columna de la hoja "Conciliación" y ahora está
en `/expedientes` y en la vista nueva.

### La vista de Conciliación

`/conciliacion`, `GET /conciliacion` (`app.routers.conciliacion`). Las 534
filas con su situación y su motivo, **filtrable por situación** con el recuento
de cada una a la vista, más una búsqueda por código o título.

Dos reglas que no se rompen:

1. **La columna de líneas no se consulta aparte.** Sale del mismo recuento que
   escribe la hoja "Materiales": `app.exportacion.contar_filas_de_materiales`
   con el mismo criterio de inclusión (`linea_sale_en_materiales`, extraído
   para que viva en un solo sitio) y los mismos filtros
   (`app.catalogo_consulta.filtros_del_entregable`, las dos listas de exclusión
   incluidas). Si las dos cifras pudieran discrepar, la vista dejaría de servir
   para lo único que existe.
2. **La API no decide nada.** `app.conciliacion` sigue siendo el único sitio
   donde se decide la Situación y el motivo; el router llama, cuenta y filtra.

**De 2 minutos a 0,18 s.** La primera versión reutilizaba el bucle del Excel
(paginar el catálogo de 500 en 500 con cuatro joins y el orden de completitud):
correcto pero inservible para una pantalla. Contar no necesita nada de eso, así
que `contar_filas_de_materiales` hace una sola consulta de tres columnas con
los mismos filtros.

El recuento por Situación es siempre el del **total**, no el del filtro: es la
cifra que se compara contra el Excel. Y la pantalla no se sondea cada tres
segundos como las otras cuatro: esto solo cambia cuando corre un ciclo.

Debajo de la tabla, **de cuándo es el registro**: el mismo texto que el Resumen
del Excel (departamentos, boletines de sindicación y su fecha, última búsqueda
directa y cuántos expedientes devolvió, y el reparto publicados / no publicados
/ publicados dentro de la ficha de otro). Una cifra de cobertura sin decir de
cuándo es no sirve para decidir nada.

**Criterio de diseño:** no hacía falta nada nuevo. `globals.css` ya es blanco,
negro y grises fríos con el verde ADIF como único acento, tipografía de palo
seco (Archivo / Public Sans / IBM Plex Mono), radios de 2-4 px y números
tabulares alineados a la derecha. La pantalla reutiliza sus clases tal cual
(`search-panel`, `filtro-estado`, `table`, `status`, `dato-vacio`), así que no
se parece a las otras cuatro: es la misma.

Un detalle de lectura: el motor escribe el valor y, entre paréntesis, de dónde
sale ("Adjudicada (lo prueba su Resolución...)"). En el Excel la celda es ancha
y se lee bien; en una tabla de once columnas convierte cada fila en un párrafo.
La pantalla muestra el valor con un indicador y la explicación en el `title`.

---

## Bloque 6 — Cierre

### Pruebas

**1.259 pasan** (1.213 al cerrar la cuarta parte, **+46**). Ninguna saltada.
Las nuevas, en `engine/tests/test_decisiones_2026_09_19_quinta.py` (37) y
`engine/tests/test_relectura_optica_y_conciliacion_web.py` (8), más una de
regresión en `tests/extraccion/test_orquestador.py` para el hueco de
idempotencia de la poda. Cada mecanismo con su contraejemplo: el presupuesto
que no es múltiplo exacto, la tabla que mezcla importes y cifras peladas, el
resumen de presupuesto que no se demuestra, la identidad gratis de "1 × X =
X", las dos tripletas ambiguas, la tabla sin columna de designación, la fila
sin descripción dentro de un cuadro bueno, la frase de pliego que cita un
precio, la tabla sin etiquetas de lote, el bloque que no es un cuadro, el lote
que no cuadra con su presupuesto, la línea que ya salía y no se toca, la
franja que sigue mandando cuando la tabla no trae etiqueta propia, y el cuadro
que pone el precio antes que la cantidad y aun así se demuestra —la prueba que
guarda la guarda retirada—.

### El reproceso completo, con la red apagada

`POST /mantenimiento/ejecutar` con `forzar: true`, `sindicacion_desactivada:
true` y `busqueda_desactivada: true`.

| | |
|---|---|
| Expedientes reextraídos | **517** (519 evaluados) |
| Tiempo | **21 min 16 s** (1.276,4 s) |
| `descargas_lanzadas` | **0** |
| `saltados_descarga` | 519 |
| `sin_publicar_reintentados` | 0 |
| `descubrimiento` / `descubrimiento_busqueda` | `None` / `None` |

**Hicieron falta seis reprocesos completos, y los cinco primeros son la razón
de que existan la quinta guarda de la etapa 4, el arreglo de la poda, la regla
de la descripción que es una cifra y la guarda de moneda que NO está.**

| Ciclo | Qué pasó |
|---|---|
| 26436 | Cancelado a mitad al encontrar, verificando `3.22/28510.0106`, que los bloques de lote se quedaban con el lote del bloque anterior |
| 26957 | Terminó con todo en verde —Conciliación cuadrando, la comparación limpia— y **aun así estaba mal**: su auditoría de fin de ciclo dio 2 errores y uno era real, las **45 líneas sin descripción** |
| 27490 | Con la quinta guarda y el arreglo de la poda. Destapó las 4 líneas cuya "descripción" era solo una cifra (`2.22/28510.0075`) |
| 28010 | Con la guarda de moneda puesta. Sirvió para **medir lo que se llevaba** —9 líneas buenas por 4 dudosas— y retirarla |
| 28543 | Sin la guarda de moneda. Su auditoría dio **1 error**: las 4 líneas sin descripción de `2.22/28510.0075`, el sexto defecto |
| **29063** | **El definitivo**, el que produce el entregable de abajo |

(26956 no llega a contar: falló al arrancar porque el ciclo cancelado había
dejado 230 `extraer_expediente` en cola, y hubo que cancelarlos a mano.)
Los defectos están contados arriba, en el bloque 1.

### Excel

```
C:\dev\ADIF\catalogo_adif_2026-09-19-residuales-y-conciliacion.xlsx
```

### Comparación con `catalogo_adif_2026-09-19-adjudicado-y-espacios.xlsx`

| | Antes | Ahora | |
|---|---:|---:|---|
| Filas de "Materiales" | 19.865 | **19.997** | **+132** |
| Columnas | 18 | **18** | = |
| Expedientes con filas | 373 | **387** | +14 |
| Filas de "Conciliación" | 534 | **534** | = |
| Materiales distintos **por matrícula** | 5.307 | **5.307** | **=** |
| Materiales distintos **por matrícula y precio** | 7.923 | **7.990** | +67 |
| Materiales distintos **por lote, matrícula y precio** | 9.238 | **9.314** | +76 |

**0 expedientes desaparecen y 0 materiales perdidos por ninguna de las tres
claves.** El orden relativo de las 18 columnas es el mismo.

**Los 17 expedientes que cambian de número de filas: los 17 suben, ninguno
baja.** Comprobado sobre los 17: **0 líneas sin descripción** —en el
entregable entero, 0 de 19.997—, y la cuenta de cada fila contra el importe que
trae su propia fila cuadra en todas las que lo publican.

| Expediente | Antes | Ahora | Por qué |
|---|---:|---:|---|
| `2.24/28510.0118` | 5 | **34** | +29. Cuadro de tamices ("Tamiz malla de 0,063 mm, acero inox., Ø300 mm", 3 × 345,00 €) que ninguna cabecera de la etapa 3 reconocía: entra por la aritmética de sus filas |
| `2.23/28510.0138` | 11 | **34** | +23. El mismo cuadro de tamices de su expediente hermano |
| `3.16/28510.0044` | 0 | **14** | Bloque 1.3: la relectura con `claude-opus-5` |
| `3.20/28510.0071` | 0 | **11** | +11. Cuadro de obra civil de canales de salida, por aritmética |
| `6.20/28510.0102` | 0 | **8** | +8. Muelas y consumibles de rectificado, por aritmética |
| `2.26/28510.0006` | 7 | **9** | +2. Dos conceptos más del mismo desglose de servicios |
| `3.22/28510.0009` | 0 | **7** | Bloque 3: sus 7 líneas del lote 2 |
| `3.22/28510.0048` | 0 | **7** | Bloque 3 |
| `3.19/28510.0141` | 0 | **6** | +6. Cuadro de grupos SAI modulares, por aritmética |
| `2.20/28510.0083` | 0 | **6** | +6. Soporte de software de gestión de red, por aritmética |
| `2.24/28510.0219` | 0 | **4** | +4. Gasóleo C por anualidad, a 1,2020 €/L |
| `2.19/28510.0214` | 0 | **3** | +3. Mascarillas FFP2 y material de protección |
| `3.21/28510.0096` | 0 | **3** | Bloque 3 |
| `3.19/28510.0016` | 0 | **3** | +3. Herramienta de desbaste y consumibles |
| `6.17/28510.0116` | 0 | **3** | Bloque 1.2: los tres precios demostrados por el presupuesto |
| `3.22/28510.0106` | 0 | **2** | Bloque 3: sus lotes 3 y 5, los dos al céntimo |
| `3.21/28510.0098` | 0 | **1** | Bloque 3: su lote 3, al céntimo |

**Las celdas que cambian de valor en filas comparables: 37, y ninguna es un
precio ni una descripción.**

| Cambio | Celdas | Explicación |
|---|---:|---|
| Cantidad | **17** | Los 6 huecos del bloque 2 y las 5+5 del bloque 1.1, más las de `6.22/28510.0122`/`0155` que comparten el mismo documento |
| Motivo de las celdas vacías | **20** | Consecuencia de las anteriores: la celda que se rellena deja de tener motivo, y en `4.26/28510.0031` pasa de "no consta" a "pendiente" |

**Filas cuyo precio unitario cambia de un número a otro: 0. Descripciones que
cambian: 0.**

### Cuadre de "Conciliación" con "Materiales"

```
suma de la columna de líneas de "Conciliación": 19.997
filas de la hoja "Materiales":                  19.997
```

**0 expedientes sin Situación.** `comprobar_cuadre` revienta la exportación si
alguna de las dos cosas falla, así que el Excel no habría salido de otro modo.

### Auditoría

**0 errores y 6 avisos.**

| Aviso | Afectados | Antes |
|---|---:|---:|
| Grupos de material repetido con códigos de precio distintos | 12 grupos, 4 expedientes | 11 grupos, 3 |
| Huérfanas sin lote | 19.758 líneas en 118 expedientes | 19.558 en 114 |
| Precios atípicos | 1.545 líneas en 84 expedientes | 1.521 en 79 |
| Cantidades con forma de año | 941 líneas en 32 expedientes | igual |
| Grupos de importe de licitación compartido | 54 grupos, 24 expedientes | igual |
| Expedientes con importe repetido entre sus lotes | 8 | igual |

La auditoría que corre al final del propio ciclo dio **0 errores y 7 avisos**:
los mismos seis, más `lineas_bajan_explicado_por_poda` sobre **1 expediente**,
`2.22/28510.0075`, que baja de 5 líneas a 1 porque la regla nueva descarta sus
4 filas de cabecera rota. Es el aviso que existe justo para eso: la bajada la
explica exactamente el balance de su propia reextracción de este ciclo, así
que no es una pérdida silenciosa. La regla "cualquier subida es error, sin
excepción" se deja intacta a propósito.

### Recuento por Situación y total de filas

| Situación | Expedientes | Antes |
|---|---:|---:|
| Aporta líneas | **387** | 373 |
| Publicado sin cuadro de precios | **57** | 63 |
| Los precios están en un acuerdo marco que no está publicado | **47** | 47 |
| Publicado dentro de la ficha de otro expediente | **17** | 17 |
| Licitación por lotes de la que solo se conocen algunos lotes | **9** | 14 |
| Documentos escaneados que no se han podido leer | **6** | 8 |
| El acuerdo marco del que depende tampoco publica precios | **3** | 3 |
| Sus documentos son de expedientes hermanos y ninguno es el suyo | **3** | 3 |
| Otro | **3** | 4 |
| El acuerdo marco está publicado pero no publica precios unitarios | **2** | 2 |
| Pendiente de procesar | **0** | 0 |
| **Total** | **534** | 534 |

**Filas totales de "Materiales": 19.997.** Líneas en la base de datos: 39.978
en 612 expedientes, 391 de ellos con alguna línea.

### La web

Las **seis** pantallas abiertas con Chromium de verdad (el del scraping, no
`curl`): `/`, `/catalogo`, `/conciliacion`, `/revision`,
`/revision/candidatos-matricula` y `/mantenimiento`. Todas pintan datos
reales, **0 banners de error** y **0 errores de consola**.

Y la comprobación que pedía el encargo: la vista de Conciliación da **las
mismas cifras que el Excel** — 534 filas, **19.997 líneas sumadas** (la
pantalla lo escribe así: "534 expedientes · 19.997 filas en el catálogo
entregado") y el mismo recuento en las once Situaciones.

---

## Lo que queda anotado, y no se ha tocado

Cinco cosas medidas que cambian datos del catálogo y **no estaban en el
encargo**:

1. **`3.18/28510.0082`**: su columna "IMPORTE" es el importe del renglón, no el
   precio unitario, y sus ocho filas dividen exactas por la columna "U"
   (49.604,00 / 16 = 3.100,25; 27.918,75 / 75 = 372,25…). Arreglarlo es
   cambiar **precios**, no cantidades.
2. **Las tres matrículas con letra final de `6.17/28510.0116`** (`69520000N`):
   aceptarlas exige tirar un carácter que el documento imprime.
3. **La numeración de lotes desplazada de `3.22/28510.0009`** (y la segunda
   tabla rotulada "LOTE 1." de `3.21/28510.0096`, cuyo total es el presupuesto
   del lote 2): el cuadro y la adjudicación no numeran igual. Es una pregunta
   para ADIF.
4. **La fila `12.01` de `3.16/28510.0044`** (1.980,50 €): su descripción vuelve
   vacía de la relectura porque el rótulo cae en la fila anterior. Es la única
   fila del cuadro que no llega al catálogo.
5. **La cuarta fila del cuadro del lote 1 de `3.21/28510.0096`**
   ("Potenciómetro rotatorio", 10 × 150,00 €): sus celdas van una columna
   desplazadas respecto de las otras tres filas de su misma tabla.

Y siguen en pie las decisiones abiertas de las partes anteriores: los **once
expedientes cuyo título declara un lote que no está entre los suyos**, la
errata **CONTRAGUJA / CONTRAAGUJA**, las **946 huérfanas** de las causas C y D,
**`6.26/28510.0064` lote 3 `P-2`**, si **"Comentarios"** va fila a fila o con
la nota única del Resumen, y si **`Precio unitario`** es el licitado o el
adjudicado. Más el pendiente que no depende de nosotros: el fichero de los
**83 vigentes con remanente**.
