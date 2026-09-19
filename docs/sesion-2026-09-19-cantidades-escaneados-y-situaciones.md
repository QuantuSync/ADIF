# Sesión 2026-09-19 (tercera parte) — Las cantidades que faltan, los escaneados que sí se leen y "Otro" partido en sus causas

Continúa `docs/sesion-2026-09-19-decisiones-aplicadas-y-garantia-afinada.md`.
Siete bloques: lo que el cliente había pedido y no estaba cubierto, o no estaba
medido.

---

## Bloque 1 — Las cantidades que faltan

### El punto de partida del cliente, y lo que dice el Excel de verdad

El cliente se quejó de **889 artículos sin cantidad**. Medido sobre el
entregable de la sesión anterior
(`catalogo_adif_2026-09-19-decisiones-aplicadas.xlsx`, 19.569 filas), la cifra
real es **6.645 filas con la cantidad vacía (34,0 %)**. La diferencia no es un
desacuerdo: 889 no corresponde a ningún dato que el sistema produzca hoy — ni
filas, ni materiales distintos, ni expedientes.

**Ninguna de las 6.645 celdas está sin motivo.** Los motivos que escribe
`app.celdas_vacias` son exactamente dos:

| Motivo, literal del Excel | Filas | Expedientes |
|---|---:|---:|
| `Cantidad: no consta` | **6.466** | 156 |
| `Cantidad: pendiente (el documento da una cantidad distinta para cada lote y falta saber cuál es la de este)` | **179** | 29 |

Los que más aportan al primero: `6.20/28510.0042`, `0046` y `0047` (1.274 filas
cada uno, el mismo documento compartido), `6.18/28510.0116` (228),
`6.22/28510.0125` (200), `6.16/28510.0042` y `6.19/28510.0122` (182 cada uno).
Al segundo: `6.25/28510.0218` (29), `2.24/28510.0218` (17), `6.25/28510.0221` y
`6.26/28510.0009` (13 cada uno).

### Separar lo legítimo de lo que no hemos leído bien

"No consta" es un solo texto para dos cosas muy distintas: el documento no
publica cantidad, o sí la publica y no la hemos leído. Para separarlas se
clasificaron **las 6.645 una a una contra su propio PDF**, buscando la fila
concreta de cada línea por su código de precio o su matrícula exactos (nunca
por parecido de descripción) y mirando la celda que la cabecera de esa tabla
llama cantidad. Cuando la página no trae cabecera (una continuación), la
columna se deduce de las filas de esa misma página que **sí** tienen cantidad,
o de la última cabecera vista en el documento.

| Veredicto | Filas | |
|---|---:|---|
| **Pendiente**: el documento da un valor distinto por lote (decisión del cliente de 2026-09-14) | 179 | legítima |
| Su documento no declara ninguna columna de cantidad en ninguna de sus tablas | 1.787 | legítima |
| No se identifica columna de cantidad en su página (verificadas a mano: ninguna la tiene) | 289 | legítima |
| Su fila deja la celda de cantidad vacía en el PDF | 4.097 | legítima |
| **Hueco real: su fila imprime la cantidad y la perdimos** | **120** | **arreglable** |
| No se pudo localizar su fila en el PDF (casi todas de reconocimiento óptico) | 173 | sin determinar |
| **Total** | **6.645** | |

**6.352 de las 6.645 (95,6 %) son legítimas**: el documento no publica esa
cantidad. De las 173 que no se pudieron volver a localizar en el PDF, las que
se miraron a mano también lo eran (su tabla no tiene columna de cantidad); se
cuentan aparte para no dar por legítimo lo que no se ha comprobado. Los casos
verificados de uno en uno contra el PDF:

- **`6.20/28510.0042`/`0046`/`0047`** (1.274 filas cada uno, 3.822 en total): su cuadro **sí** tiene una
  columna "Cantidad estimada de referencia" (cabecera en la p.3 del
  `ANEJO_3`), y el documento la deja en blanco en casi todos sus renglones.
  Medido sobre `6.20/28510.0042`: de sus 1.294 líneas de ese documento, 1.274
  no traen cantidad — y de esas, **1.216 dejan la celda vacía en el propio
  PDF**, 13 son hueco real y 45 no se pudieron volver a localizar. No es un
  hueco de lectura: es un cuadro de precios unitarios que solo estima cantidad
  para unos pocos renglones.
- **`6.21/28510.0108`-`0111`** (57 filas cada uno, 228 en total): su anejo de criterios técnicos no
  tiene columna de cantidad en absoluto. Su cabecera es "TIPOLOGÍA APARATO |
  CÓDIGO DEL ELEMENTO | REPUESTO | DESCRIPCIÓN | PESO en toneladas | PRECIO DEL
  ELEMENTO | UNIDAD DE MEDIDA | IMPACTO". Los números sueltos de sus filas
  (`17.000`, `10.000`, `4,5`, `3,8`) son el radio de la tipología y el peso,
  no cantidades — y son justo los que reventaron el primer intento de
  clasificarlas por contenido.
- **`6.16/28510.0161`** (131 filas): documento escaneado. Su cuadro, leído por
  reconocimiento óptico, es "matrícula | designación | plano | E.T. | precio".
  No hay columna de cantidad que perder.
- **`6.24/28510.0203`, `6.25/28510.0019`, `6.25/28510.0097`**: son **partidas
  alzadas** ("Partida alzada a justificar…"), que por definición no llevan
  cantidad (CONTEXTO.md sección 2).
- **`6.20/28510.0136`** y **`6.22/28510.0074`**: su fila del cable de feeder
  deja vacía la celda "CANTIDADES DE REFERENCIA" que la tabla sí declara,
  mientras la fila de encima (740540003) trae "37962 Kg".

### La causa raíz de los 120 huecos reales

Medida, no supuesta, instrumentando `construir_linea_catalogo` sobre el
documento del trío (`ANEJO_abd69efbdd39b552`, 61 páginas, 1.302 líneas):

```
1222 lineas  {'cantidad': None, 'matricula': 0, 'descripcion': 1, 'precio_unitario': 4}
  51 lineas  {'cantidad': 6,    'matricula': 0, 'descripcion': 1, 'precio_unitario': 4}
```

Las 51 son las de la p.3, la única con cabecera. **En las otras 60 páginas el
mapeo no reclama ninguna columna para `cantidad`**: la cabecera va vacía (es
una continuación), el modelo la resuelve con dos o tres filas de ejemplo, y en
esas dos o tres filas la celda de cantidad está en blanco — como en el 94 % de
la tabla. Con `cantidad` sin columna,
`app.catalogo._recuperar_cantidad_columna_fantasma` **no llega a dispararse
nunca**, porque exige que la cabecera sí declare el campo.

### El arreglo, y por qué no puede inventar una cantidad

`app.extraccion.mapeo_cabecera.completar_cantidad_por_contenido`, hermana de
`completar_matricula_por_contenido` y `completar_codigo_precio_por_contenido`.
Se llama solo para una tabla **sin cabecera propia**, y solo cuando **otra
tabla del MISMO documento ya declaró una columna de cantidad en su cabecera**
(`cantidad_declarada_en_el_documento`, estado por documento en
`pipeline_anejo`). Entonces, si hay **exactamente una** columna que ningún otro
campo reclama y en la que **todos** los valores no vacíos tienen forma de
cantidad pequeña (hasta cuatro dígitos enteros, sin separador de miles, sin
símbolo de euro), se le asigna. Con cero o más de una, no se adivina.

**La certeza la da el documento, no una heurística sobre el contenido.** Se
probó con sus contraejemplos en `engine/tests/test_cantidades_que_faltan.py`:
una referencia normativa con puntos (`03.361.140.1`), un radio de tipología
(`17.000`), una matrícula de nueve cifras y un precio con euro nunca pasan.

Y `_UMBRAL_RELLENO_MINIMO` de `clasificar_columnas` no servía para esto: la
columna que se busca está vacía en el 95 % de sus filas **por diseño del propio
cuadro**, así que esa clasificación la ve como "vacía".

### La primera versión de la regla estaba mal, y lo destapó el reproceso

Merece contarse porque es el motivo de que la regla exija hoy **enteros**. La
primera versión aceptaba cualquier cantidad de hasta cuatro dígitos con
decimales opcionales, y la guarda que se creía suficiente era "el documento
declara una columna de cantidad en otra de sus tablas".

**No lo era.** El reproceso completo destapó que `6.21/28510.0108`-`0111`
ganaban **5 líneas cada uno con el PESO EN TONELADAS del aparato de vía
metido en la columna de cantidad** (`P-30` → 4, `P-33` → 3,3, `P-35` → 2,9…):
justo el contraejemplo que la regla pretendía impedir, y encima sin motivo de
revisión, porque la propia función no tenía nada que objetar.

La razón de que la guarda no lo protegiera es sutil y vale anotarla: **ninguna
cabecera de ese documento dice literalmente "cantidad"** —se comprobó tabla
por tabla—, pero el **modelo** sí acaba mapeando `cantidad` en alguna de sus
tablas con cabecera a partir de las filas de ejemplo. La guarda mira el mapeo
resultante, no el literal de la cabecera, así que se activaba igual.

El arreglo: **la columna candidata solo vale si todos sus valores son enteros**.
Una "cantidad estimada de referencia" de este corpus es un recuento (0, 1, 2,
3, 13, 32.000); un peso lleva decimales, y basta un "3,3" en la columna para
descartarla entera. Es una restricción deliberada — si algún día aparece un
cuadro con cantidades decimales en una tabla sin cabecera, esta vía no lo
recuperará — y es claramente preferible a escribir un peso donde va una
cantidad. Verificado tras el cambio: las cinco líneas de cada uno de los
cuatro vuelven a quedarse sin cantidad, y las de los tres documentos que sí
son cuadros de cantidad no se pierden.

### Efecto medido antes de desplegar, documento por documento

| Expediente (documento) | Con cantidad antes | Después | Ganan | Valores nuevos |
|---|---:|---:|---:|---|
| `6.20/28510.0042` (`ANEJO_3`, compartido con `0046`/`0047`) | 4 | 22 | **+18** | 2 (×9), 3 (×8), 1 (×1) |
| `6.22/28510.0125` (`ANEJO_1`, compartido con `0094`/`0126`) | 90 | 418 | **+328** | 0 (×293), 1 (×33), 2 (×2) |
| `6.24/28510.0125` (`ANEJO_1`) | 64 | 97 | **+33** | 1 (×33) |
| `6.21/28510.0108` (`ANEJO_3`) | 0 | 0 | 0 | — (su documento nunca declara cantidad) |
| `4.26/28510.0031`, `6.24/28510.0173`, `6.26/28510.0030` | igual | igual | 0 | — (su cabecera sí declara cantidad: otra causa) |

**Ninguna cantidad ya guardada cambia de valor.** Comprobado explícitamente en
la medición antes/después: 0 cambios, solo celdas vacías que se rellenan.

### Los 293 ceros: lo que hay que saber

De las cantidades nuevas de `6.22/28510.0125` (y sus dos hermanos que comparten
el documento), **la mayoría son `0`**. No es un fallo: su `ANEJO_1` declara en
la p.15 la cabecera "CÓDIGO DEL ELEMENTO | Nº MATRÍCULA | DESCRIPCIÓN | UNIDAD
DE MEDIDA | **CANTIDADES ESTIMADAS DE REFERENCIA** | PRECIO UNITARIO DE
REFERENCIA", y en las páginas 16-20 imprime `0` para casi todos los renglones y
`1` o `2` para unos pocos. Un `0` ahí significa "elemento del catálogo sin
pedido estimado en este contrato".

Se escribe porque el documento lo publica y porque el sistema ya está diseñado
para distinguir un cero real de un dato ausente (verificado en la sesión
2026-09-09, bloque 1, en las cuatro capas).
`app.catalogo._cantidad_parece_implausible` ya tenía su texto exacto — *"cantidad
es 0: confirmar si es un valor real del documento (p.ej. un elemento de
catálogo sin pedido estimado en este contrato) o un dato perdido"* — así que
ninguna de esas filas pasa como dato confirmado sin que nadie la mire: van a la
cola de revisión con ese motivo.

**Queda dicho por si el cliente prefiere lo contrario**: si ver `0` en la
columna "Cantidad" le resulta peor que verla vacía, la vuelta atrás es una
condición de una línea en el predicado. No se ha tomado esa decisión aquí
porque el documento publica el dato y esconderlo sería peor.

### El número de antes, el de después, y cuántas quedan legítimas

| | Antes | Después |
|---|---:|---:|
| Filas de "Materiales" | 19.569 | **19.870** |
| Filas con la cantidad vacía | **6.645** (34,0 %) | **6.424** (32,3 %) |
| De ellas, "no consta" | 6.466 | 6.241 |
| De ellas, "pendiente" (valor distinto por lote) | 179 | 183 |
| Filas con cantidad **0** | 2.359 | 2.775 |

**Celdas de cantidad que cambian de valor: 513**, todas en filas que existen en
los dos entregables:

| Antes → después | Celdas |
|---|---:|
| vacía → **0** | 416 |
| vacía → 1 | 46 |
| vacía → 3 | 24 |
| vacía → 2 | 23 |
| vacía → 32.000 | 1 |
| 55.000 → vacía | 2 |
| 54.000 → vacía | 1 |

Las tres que pasan a vacía son de `6.22/28510.0011` y **no son una pérdida de
lectura**: al abrirse más páginas de su documento compartido, el mismo código
de precio aparece con cantidades distintas dentro del mismo lote y salta la
guarda de choques que el cliente decidió en 2026-09-14 ("valor vacío con
motivo, nunca el último gana"). Antes se mostraba un valor sin saber que era
el suyo, porque no habíamos abierto el otro cuadro. El mismo mecanismo le
quita el precio a su `P-2`.

**El 0 no es nuevo en el entregable**: ya había 2.359 filas con cantidad 0
antes de esta sesión (809 en `6.23/28510.0051`, 547 en `6.23/28510.0060`, 138
en cada uno de `6.21/28510.0108`-`0111`). Lo que cambia es que ahora también
lo tienen las de `6.22/28510.0125`/`0094`/`0126`, cuyo documento lo imprime y
cuya columna no se estaba leyendo.

**Cuántas de las que quedan son legítimas**: la clasificación se hizo sobre las
6.645 de partida y dio **6.352 legítimas (95,6 %)**, 120 huecos reales y 173
sin determinar. De los 120, el arreglo cubre los que tenían la causa medida; de
los que quedan, los cuatro casos concretos están listados abajo. La proporción
de legítimas sobre las 6.424 que quedan es, por tanto, aún mayor que el 95,6 %
de partida.

### Lo que sigue sin arreglar de este bloque

- **`6.24/28510.0173`** p.9 (5 filas), **`6.26/28510.0030`** p.11 (1),
  **`6.24/28510.0125`** p.8 (4 de las 5): su cabecera **sí** declara la columna
  de cantidad, así que la causa es otra — la celda con el valor cae a dos o más
  columnas de distancia de la que el mapeo señala, fuera del alcance de
  `_recuperar_cantidad_columna_fantasma`, que solo prueba la contigua. Medido y
  anotado; no tocado.
- **`6.17/28510.0116`** (3 artículos): su cuadro escaneado trae matrículas con
  una letra al final (`69520000N`) y precios sin decimales ni símbolo
  (`5.400`). Ni la matrícula pasa el patrón de 8-9 cifras ni el precio pasa por
  importe. Aceptar "5.400" como importe es exactamente lo que no se debe hacer
  a ciegas: podría ser una cantidad o una referencia de plano.
- **`3.18/28510.0082`** p.238 (2 filas): su tabla es "MATRICULA | DESIGNACIÓN |
  U | IMPORTE" y el `16` de la columna "U" es la cantidad, con el IMPORTE como
  total (49.604,00 € = 16 × 3.100,25). Es a la vez un hueco de cantidad y un
  precio que habría que derivar del importe. No tocado.

### El caso pendiente de `6.18/28510.0071`

Lo pedía el encargo explícitamente, y **la causa no era la cantidad**: su cuadro
de precios, leído por reconocimiento óptico, es **"Designación | Plano |
PRECIO"** en seis páginas del `ANEJO_1` (p.12-17). No tiene columna de
cantidad, y no por un fallo de lectura: su propio pliego declara que es un
**Pedido Abierto** *"sin compromiso de compra en firme […] al ser estas
cantidades estimadas"*. La razón de que sus artículos no llegaran al catálogo
era la etapa 4 de la cascada, que exigía descripción **+ cantidad +** precio
para aceptar una tabla sin códigos. Se resuelve en el bloque 3.

---

## Bloque 2 — Los 83 vigentes con remanente

**El grupo está registrado; el fichero del que salía nunca llegó.** No se
inventa nada y no se puede cruzar.

La búsqueda cubre `CONTEXTO.md`, los 52 documentos de `docs/` y el árbol
completo del repositorio. Lo que hay, literal:

- `docs/sesion-2026-09-16-noche-ciclo-vigentes-unidades.md`, sección
  "Pendiente al cerrar": *"**Bloque 2 sin hacer**: el fichero
  `Ejemplo/Input/EXPEDIENTES_VIGENTES_CON_REMANENTE.xlsx` no estaba en el
  repositorio en ningún momento de la sesión. El script de cruce está
  preparado; en cuanto esté el fichero es una pasada corta."*
- El mismo doc tiene el encabezado del bloque (`## Bloque 2 — Vigentes con
  remanente`) con un marcador vacío, `<!-- RESULTADO_BLOQUE_2 -->`, sin una
  sola cifra debajo.
- `docs/sesion-2026-09-17-escaneados-codigo-material.md` lo arrastra como
  pendiente: *"vigentes con remanente (falta el fichero)"*.
- `CONTEXTO.md` lo cierra igual: *"**Sin hacer:** el cruce con los 83 vigentes
  con remanente (el fichero no llegó a estar en `Ejemplo/Input/`)"*.

**Comprobado además que el grupo no está escondido en otro fichero de
entrada.** Los cinco ficheros que el sistema lee de `Ejemplo/Input` se
inspeccionaron hoja a hoja: ninguno tiene 83 filas ni ninguna columna que
hable de remanente.

| Fichero | Hojas | Filas | Columnas |
|---|---:|---:|---|
| `Códigos de proyecto.xlsx` | 1 | 666 | Nº Interno, Nº Expediente, MATRIZ, ESPECIALIDAD/DISCIPLINA, DESCRIPCIÓN |
| `EXPEDIENTES_EJECUCION_SAP 1.XLSX` | 1 | 368 | Expediente ADIF, Título del expediente, Descripción del estado |
| `estados_expedientes_28510_20260918.xlsx` | 1 | 359 | Título del expediente, Expediente ADIF, Fecha de creación, Descripción del estado |
| `LISTADO_MATERIALES_UNIDAD_,MEDIDA.xlsx` | 1 | 32.117 | Material, Denominación, UM base |
| `contratos traviesas.XLSX` | 1 | 186 | expediente, Documento compras, Posición, Indicador de borrado, Última modificación, Material, Texto breve, Centro, Cantidad prevista, Precio neto pedido, … |

**Lo que hace falta para cerrarlo**: que Álvaro vuelva a enviar el fichero (el
nombre que se registró en su día es `EXPEDIENTES_VIGENTES_CON_REMANENTE.xlsx`).
Con él, el cruce contra las situaciones de la hoja "Conciliación" y la búsqueda
en la Plataforma de los que no aparezcan es una pasada corta: los 534 códigos
de la hoja ya están calculados y la búsqueda por subcadena del buscador ya
resuelve un departamento entero de una vez.

---

## Bloque 3 — Los 15 expedientes con escaneados ilegibles

### Coste: cero dólares

**Los 15 pasaron ya por el reconocimiento óptico**, entre 1 y 4 documentos cada
uno, y su resultado está en la caché por hash de documento
(`cache_ocr_documento`). Volver a leerlos no llama al modelo, así que **el coste
de este bloque es 0 $** y no hacía falta autorización previa. Ninguno de los 15
necesitaba pasar por el reconocimiento: ninguno se lo había saltado.

### Por qué falló cada uno

Dos causas distintas, y conviene no confundirlas:

**(a) El documento escaneado es el pliego administrativo, y saltárselo es
correcto.** En los 15, sin excepción, el `ANEJO_2.pdf` (34-84 páginas) tiene 2
páginas leídas y `completo=False`. No es un fallo: el reconocimiento lee dos
páginas, pregunta al clasificador, y **si dice pliego administrativo se para
ahí** (diseño de la sesión 2026-09-17). Ese documento nunca trae cuadro de
precios.

**(b) El cuadro de precios sí se leyó, y lo rechazaba la etapa 4 de la
cascada.** Cinco de los 15 tienen su cuadro perfectamente legible en la caché
del reconocimiento y no llegaba al catálogo porque no tiene ni código de precio
ni matrícula ni columna de cantidad — los tres requisitos que la etapa 4 pedía.

**(c) Y en cuatro de los 15 el problema no es el escaneado en absoluto.**
`2.18/28510.0089`, `2.19/28510.0015`, `3.19/28510.0017` y `6.19/28510.0131`
tienen su `ANEJO_1` con capa de texto (44.032, 14.191, 10.353 y 23.709
caracteres), leído por la vía normal; su único documento escaneado es el
pliego administrativo. Llamarlos "escaneados que no se han podido leer" es
falso.

Y dos de esos cuatro **sí tenían cuadro de precios**, en un documento con capa
de texto que la etapa 3 no abría: `6.19/28510.0131` aporta ahora **91 filas**
de pequeño material de fibra óptica y `2.19/28510.0015` **3** (reglas de
inducción). Es decir: su Situación en la Conciliación era doblemente
equivocada — ni eran un problema de escaneado ni estaban sin cuadro.

Uno a uno:

| Expediente | Por qué no aportaba líneas |
|---|---|
| `2.18/28510.0089` | Su único escaneado es el PCAP (2 páginas leídas, parada correcta). Su `ANEJO_1` tiene capa de texto y no trae cuadro de precios. **No es un caso de escaneado.** |
| `2.19/28510.0015` | PCAP escaneado; su cuadro está en un documento con capa de texto que la etapa 3 no abría. **No es un caso de escaneado, y sí tenía cuadro: 3 líneas.** |
| `3.16/28510.0044` | Su `ANEJO_1` (130 páginas) se leyó entero. **La lectura es mala de verdad**: tabla apaisada con celdas fundidas y texto corrompido ("Transmísión", "cabezado a panl", "Etiqueta articulo la 13 trams de Mbs"). Es el único de los 15 donde el reconocimiento no da un resultado usable. |
| `3.16/28510.0156` | Cuadro legible en `ANEJO_1` p.19 ("REF. \| DENOMINACIÓN \| PRECIO") y p.21 ("REF. \| MEDIC. \| DENOMINACIÓN \| PRECIO \| IMPORTE"). Rechazado por falta de columna de cantidad reconocible ("MEDIC." abreviado). **Resuelto: 14 líneas.** |
| `3.17/28510.0008` | Sus cuatro documentos escaneados se leyeron; ninguno trae una tabla con precios. |
| `3.17/28510.0028` | Cuadro legible en `ANEJO_1` p.19 ("Elemento \| Precio (€)") y p.20 ("Elemento \| Medición \| Importe"). **Sigue sin entrar**: llama "Elemento" a la columna de descripción, y ningún alias la reconoce. Ver "lo que no se ha tocado". |
| `3.17/28510.0094` | Sus cuatro escaneados se leyeron; su `ANEJO_1` (16 páginas) no tiene ninguna página candidata a cuadro de precios. |
| `3.19/28510.0017` | PCAP escaneado; `ANEJO_1` con texto (10.353 caracteres) sin cuadro. **No es un caso de escaneado.** |
| `3.19/28510.0201` | Cuadro legible en `ANEJO_1` p.10 ("CONCEPTO \| PRECIO"). **Resuelto: 3 líneas.** |
| `6.17/28510.0012` | Sus cuatro escaneados se leyeron; ninguna página candidata a cuadro. |
| `6.17/28510.0045` | Cuadro en `ANEJO_1` p.19, con la cabecera fundida en una sola celda ("CUADRO DE PRECIOS" a lo ancho de cuatro columnas). **Resuelto: 4 líneas.** |
| `6.17/28510.0116` | Cuadro legible en `ANEJO_1` p.9 ("MATRÍCULA \| DESIGNACIÓN \| PRECIO DE REFERENCIA €/ud", 3 artículos). **Sigue sin entrar**: sus matrículas llevan una letra al final (`69520000N`) y sus precios no traen decimales ni símbolo (`5.400`). |
| `6.18/28510.0064` | Cuadro legible en `ANEJO_1` p.10 ("MATRÍC. \| DESIGNACIÓN \| ACREDITACIÓN FERROVIARIA \| ET \| CRÍTICO \| PLANO DE REFERENCIA \| PRECIO DE REFERENCIA"). La página no se abría: de sus siete rótulos el localizador solo reconocía uno. **Resuelto: 2 líneas.** |
| `6.18/28510.0071` | Cuadro de 6 páginas en `ANEJO_1` (p.12-17), "Designación \| Plano \| PRECIO", ~68 artículos. Pedido Abierto, sin cantidades por diseño. **Resuelto: 78 líneas.** |
| `6.19/28510.0131` | PCAP escaneado; su cuadro de pequeño material de fibra óptica está en un documento con capa de texto que la etapa 3 no abría. **No es un caso de escaneado, y sí tenía cuadro: 91 líneas.** |

### Los tres cambios, y sus guardas

**1. La etapa 4 ya no exige columna de cantidad**
(`app.extraccion.tabla._filas_cuadro_sin_codigo`). Lo que la sustituye, por
condición explícita del cliente: **cuando el cuadro trae su propia columna de
IMPORTE además de la de precio, cada fila tiene que cuadrar** (cantidad ×
precio = importe, tolerancia de un céntimo). Una fila que no cuadra no entra y
corta la tabla; nunca se corrige nada. Y sin columna de cantidad se exige un
**mínimo de tres filas**: con una o dos, "descripción + importe" no se
distingue de un resumen de presupuesto. Con cantidad se mantiene el criterio de
2026-09-15, que aceptaba el cuadro de un solo artículo.

Las demás guardas siguen intactas y son las que impiden que entre una tabla de
resumen: la descripción tiene que traer letras de verdad, el precio tiene que
ser un importe, y la primera fila con etiqueta de pie ("Total", "Suma", "IVA",
"Presupuesto"…) corta la tabla.

**2. La etapa 3 reconoce esa misma cabecera**
(`app.extraccion.localizador`). Sin esto la página no se abre y la etapa 4 no
llega a verla nunca — era el caso de `6.18/28510.0071`, cuyas seis páginas de
cuadro quedaban fuera de las candidatas. Dos correcciones:

- Una línea que nombra descripción **y** precio (sin cantidad) cuenta como
  cabecera de cuadro, **con un tope de diez palabras**. Ese tope es lo que
  sustituye a la exigencia de cantidad: una frase de pliego que menciona de
  pasada "la descripción" y "el precio" no pasa. Probado con el
  contraejemplo.
- Esa comprobación solo vivía en la rama de densidad numérica **baja** (se
  escribió para un cuadro pequeño perdido en una página de prosa). Ahora se
  hace también en la rama de densidad alta: `6.18/28510.0071` p.12 tiene
  densidad 0,26 —diez veces el umbral— y un solo grupo de marcadores, y se
  quedaba fuera aunque su primera línea sea literalmente "Designación Plano
  PRECIO".

**3. "Designación" y "Denominación" cuentan como columna de descripción** en
los marcadores del localizador. Son los otros dos nombres que el corpus da a
esa columna, y `app.extraccion.tabla` ya los trataba como equivalentes desde
2026-09-15; el grupo de marcadores se había quedado solo con "descripcion".
Esto es lo que abre la página de `6.18/28510.0064`, cuya tabla ya pasaba la
etapa 4 sin tocar nada.

### Resultado

**7 de los 15 pasan a aportar líneas: 182 filas del entregable.**

| Expediente | Filas en "Materiales" |
|---|---:|
| `6.19/28510.0131` | **91** |
| `6.18/28510.0071` | **73** |
| `3.16/28510.0156` | **7** |
| `2.19/28510.0015` | **3** |
| `3.19/28510.0201` | **3** |
| `6.17/28510.0045` | **3** |
| `6.18/28510.0064` | **2** |
| **Total** | **182** |

La Situación "Documentos escaneados que no se han podido leer" baja de **15 a
8**. Las líneas que vienen de un documento leído por imagen llevan la misma
marca que las demás (`lineas_catalogo.texto_reconocido`, su `motivo_revision`
y el prefijo `[reconocimiento óptico]` en el fragmento), tal y como pedía el
encargo; las de `6.19/28510.0131` y `2.19/28510.0015` no la llevan porque su
cuadro no es un escaneado, sino un documento con capa de texto que la etapa 3
no abría.

### Lo que no se ha tocado, y por qué

- **`3.17/28510.0028`**: su cuadro llama "Elemento" a la columna de
  descripción. Aceptarlo exige añadir "elemento" como alias de descripción, y
  eso choca de frente con "CÓDIGO DEL ELEMENTO", que ya es alias de
  `codigo_precio` — en una tabla con las dos, el alias genérico le robaría la
  columna. Es una decisión que cambia datos del catálogo y no estaba en el
  encargo: queda anotada.
- **`6.17/28510.0116`** y **`3.16/28510.0044`**: explicados arriba. El primero
  necesita aceptar una matrícula con letra final y un precio sin decimales; el
  segundo, una lectura mejor del escaneado.

---

## Bloque 4 — Los 64 publicados sin cuadro de precios

### Cómo se ha comprobado

Uno a uno, **documento a documento**, con el código nuevo del bloque 3: qué
documentos tiene cada uno, cuáles se salta el clasificador y por qué, cuántas
páginas abre el localizador de cada uno, y cuántas líneas produce la cascada
completa. **64 expedientes, 192 documentos**, ninguno ausente del
almacenamiento y 7 de ellos leídos por reconocimiento óptico.

### Resultado

| | |
|---|---:|
| Se confirman sin cuadro de precios | **63** |
| Sí tenían una tabla con precios que no se estaba leyendo | **1** |
| Filas que aporta ese 1 en el entregable, tras arreglarlo | **10** (5 de su anejo + 5 de su contrato) |

La Situación "Publicado sin cuadro de precios" baja de **64 a 63**.

**No es el clasificador el que no lo encuentra.** Lo que se salta, se salta con
motivo y verificado: de los 192 documentos, los únicos que la cascada no abre
son **42 pliegos administrativos** — 22 portadas PCSP ("Documento de Pliegos",
3-7 páginas) y 20 Pliegos de Cláusulas Administrativas (70-99 páginas) —, los
dos marcadores que `es_pliego_sin_precios` reconoce y que el corpus ya
confirmó vacíos de precios en su día (0 de ~75 documentos con esos marcadores
han aportado nunca una línea). **El pliego técnico (`ANEJO_1`) nunca se salta.**
Los otros 150 se abren, se les localizan páginas candidatas y se les extraen
las tablas.

Dos de los 64 no tienen ningún documento: **`6.14/28510.0148` y
`6.14/28510.0177`**, con seis búsquedas cada uno en la Plataforma y su ficha
localizada, publican cero documentos descargables. Ya estaba medido; se
reconfirma.

### El único que sí lo tenía: `4.26/28510.0005`

*"Servicio de mantenimiento de instalaciones de seguridad y detección de
incendios en instalaciones ferroviarias en red convencional."* Su `ANEJO_1`
p.198 y su `CONTRATO_1` p.304 traen el mismo cuadro de cinco conceptos:

| Concepto | Precio |
|---|---:|
| Precio Mensual de Mantenimiento | 75.194,99 € |
| Hora Técnico jornada laboral | 42,00 € |
| Hora Técnico jornada nocturna | 50,00 € |
| Hora Técnico jornada festiva | 61,00 € |
| Gestión de reparación | 105,00 € |

Es un cuadro de precios de **servicios**, no de materiales, y entra por la
misma vía que el corpus ya aceptaba para otros desgloses de servicios
(`2.26/28510.0006`, sesión 2026-09-15). No tenía cantidad, y por eso se
descartaba.

**Un defecto de paso, medido y no arreglado**: en el `CONTRATO_1` la fuente del
PDF mapea el espacio al signo `!`, así que sus cinco descripciones salen
`Precio!Mensual!de!Mantenimiento!`. El `ANEJO_1` trae las mismas cinco
limpias. Queda anotado.

---

## Bloque 5 — Los 26 de la situación "Otro"

### Desglose con el estado de hoy

Los 26 se han desglosado por su motivo técnico real y se ha comprobado, con la
misma pasada documento a documento del bloque 4, si alguno tiene un arreglo
limpio que le dé líneas. **No lo tiene ninguno**: 23 de los 26 tienen
literalmente cero líneas en la base de datos, y los otros tres
(`6.23/28510.0105` con 35, `3.21/28510.0158` con 7, `3.22/28510.0048` con 1)
las tienen todas sin lote, así que no llegan al entregable. Lo que les falta no
es lectura: es el documento que traería el precio de **su** lote.

Así que el arreglo limpio que sí hay es el que pedía el encargo: **que la
Conciliación diga su motivo real en vez de "Otro"**.

### Las tres situaciones nuevas

Condición del cliente: una situación nueva solo si hay al menos 3 expedientes
del mismo tipo. Se cumple en tres grupos:

| Situación nueva | Expedientes al desglosar | En el entregable final |
|---|---:|---:|
| `Licitación por lotes de la que solo se conocen algunos lotes` | **14** | **14** |
| `El acuerdo marco del que depende tampoco publica precios` | **5** | **3** |
| `Sus documentos son de expedientes hermanos y ninguno es el suyo` | **4** | **3** |
| `Otro` (los que no llegan a 3 del mismo tipo) | **3** | **4** |
| Pasan a "Aporta líneas" | — | **2** |

La última columna es la del Excel de esta sesión, y difiere de la primera
porque dos de los 26 (`6.19/28510.0179` y `6.19/28510.0210`) **pasan a aportar
líneas** con los arreglos del bloque 3, y con ello `6.19/28510.0209` —que se
clasificaba por el problema de su matriz `0179`— cambia de motivo y vuelve a
"Otro". **"Otro" pasa de 26 a 4.**

- **Cobertura parcial de lotes (14)**: `2.19/28510.0145`, `3.18/28510.0047`,
  `3.19/28510.0198`, `3.19/28510.0218`, `3.21/28510.0096`, `3.21/28510.0098`,
  `3.21/28510.0158`, `3.22/28510.0009`, `3.22/28510.0048`, `3.22/28510.0106`,
  `6.19/28510.0206`, `6.23/28510.0074`, `6.23/28510.0105`, `6.24/28510.0113`.
  Casi todos son compras multi-lote del Laboratorio Central de ADIF.
- **La matriz tampoco publica precios (5)**: `2.20/28510.0118`,
  `6.19/28510.0209`, `6.19/28510.0210`, `6.20/28510.0002`, `6.20/28510.0003`.
- **Documentos de hermanos (4)**: `6.19/28510.0179`, `6.19/28510.0230`,
  `6.20/28510.0089`, `6.25/28510.0219`.
- **Siguen en "Otro" (3)**: `3.20/28510.0071` y `6.15/28510.0080` (su Anuncio
  agrupa 4 y 17 lotes en un solo documento y no se puede identificar cuál es el
  suyo — solo 2 del mismo tipo) y `6.19/28510.0228` (su lote 2 no trae baja ni
  importe en ningún documento — 1 solo). Los tres siguen con su motivo técnico
  a la vista, que es para lo que "Otro" existe.

### El orden de las ramas, que no es cosmético

Un motivo real puede traer los tres textos a la vez. Caso medido,
`6.19/28510.0210`: su motivo empieza por el problema de los hermanos, sigue por
la cobertura parcial y **arrastra íntegro el motivo de su matriz**
`6.19/28510.0179`, que tiene el mismo problema de hermanos. Si ganara la rama
del hermano, el pedido se clasificaría por la causa de su matriz y el cliente
no sabría a qué documento preguntar. Así que la matriz va primero, y hay un
test que fija esa premisa (`assert MOTIVO_HERMANO in MOTIVO_MATRIZ`).

Los tres textos se escriben para alguien de almacenes, con el mismo test de
jerga prohibida que `app.celdas_vacias`, y cada uno termina diciendo **qué
documento haría falta** para completarlo.

La hoja "Resumen" recoge las tres nuevas sin tocar nada:
`_escribir_bloque_conciliacion` recorre `SITUACIONES`.

---

## Bloque 6 — Preparar las preguntas al cliente

En **`docs/preguntas-cliente-lotes-del-titulo-y-ficheros-de-entrada.md`**, con
las dos cosas que pedía el encargo. No es un mensaje al cliente: es la
información para que la pregunta la formule quien habla con ADIF.

**El hallazgo que reorienta la pregunta de los once**: su título **no sale de
ningún documento publicado**. `trazas_origen` guarda documento y página para
los 186 expedientes cuyo título se leyó del campo *Objeto del Contrato*;
**ninguno de los once tiene esa traza**. Su título lo escribió la carga de los
listados que ADIF nos envió (columna *Título del expediente* de
`estados_expedientes_28510_20260918.xlsx` y de `EXPEDIENTES_EJECUCION_SAP
1.XLSX`), y se ha comprobado uno a uno que los once están ahí con ese literal.

Así que la contradicción es entre **lo que el SAP de ADIF llama a ese
expediente** y **los lotes que declaran los contratos que la Plataforma publica
bajo su número** — no entre dos lecturas nuestras. El documento lleva, para
cada uno de los once, el título literal, los lotes registrados, y el documento,
la página y el fragmento exactos de los que sale cada lote.

Re-comprobado en esta sesión: el `ANEJO_3.pdf` de `6.21/28510.0135` trae en su
**página 6** la sección "LOTE 6 - PLACAS ASIENTO PAE…", palabra por palabra su
título.

El inventario de ficheros de entrada cubre los cinco que el sistema lee de
`Ejemplo/Input` (columna a columna, para qué se usa cada una) más la lista de
exclusión, que existe como mecanismo y hoy está vacía. **Ningún origen es
desconocido**: cuatro son de SAP, uno es de otro sistema de ADIF, y la lista de
exclusión la haría el cliente. De la Plataforma no entra ningún fichero por esa
carpeta.

La pregunta de CONTRAGUJA/CONTRAAGUJA no se repite: ya está en
`docs/pregunta-cliente-contraguja-contraaguja.md`.

---

## Bloque 7 — Cierre

### Pruebas

**1.202 pasan** (1.171 al cerrar la sesión anterior, **+31**). Ninguna saltada.
Las nuevas: 12 en `test_cantidades_que_faltan.py` (incluidos los
contraejemplos que impiden tomar una referencia normativa, un radio de
tipología, una matrícula, un precio con euro o **un peso en toneladas** por
una cantidad), 11 en `test_cuadro_sin_cantidad.py` (con la fila que no cuadra
con su importe, el pie de totales que corta la tabla y la prosa de pliego que
no es una cabecera) y 8 en `test_situaciones_de_otro.py` (incluido el orden de
las ramas y el test de jerga prohibida). Una prueba existente se actualizó:
`test_un_documento_escaneado_no_tapa_la_causa_real_del_expediente` afirmaba
`OTRO` para una causa que ahora tiene situación propia.

### El reproceso completo, con la red apagada

`POST /mantenimiento/ejecutar` con `forzar: true`, `sindicacion_desactivada:
true` y `busqueda_desactivada: true`.

| | |
|---|---|
| Expedientes reextraídos | **517** (519 evaluados) |
| Tiempo | **20 min 22 s** (1.222,2 s) |
| `descargas_lanzadas` | **0** |
| `saltados_descarga` | 519 |
| `sin_publicar_reintentados` | 0 (`sin_publicar_desactivado: True`) |
| `descubrimiento` / `descubrimiento_busqueda` | `None` / `None` |

**Hubo dos reprocesos, y el primero es la razón de que el guard exija
enteros.** El primero (21 min 4 s, también con 0 descargas) terminó con todas
las comprobaciones en verde —Conciliación cuadrando, auditoría a 0 errores— y
**aun así estaba mal**: al revisar celda a celda salieron las 20 cantidades con
el peso en toneladas del bloque 1. Se corrigió, se relanzó, y de paso quedó una
lección anotada: **un `None` no pisa un valor ya guardado**, así que las 20
celdas que escribió la versión con el defecto sobrevivieron al segundo
reproceso y hubo que limpiarlas en base de datos — el mismo caso y el mismo
remedio que la sesión 2026-09-07 con las 36 líneas de unidad ajena.
Comprobado después reextrayendo `6.21/28510.0108`: las cinco siguen vacías,
así que el estado es idempotente.

### Excel

```
C:\dev\ADIF\catalogo_adif_2026-09-19-cantidades-y-escaneados.xlsx
```

### Comparación con `catalogo_adif_2026-09-19-decisiones-aplicadas.xlsx`

| | Antes | Ahora | |
|---|---:|---:|---|
| Filas de "Materiales" | 19.569 | **19.870** | +301 |
| Columnas | 18 | **18** | = |
| Expedientes con filas | 363 | **373** | +10 |
| Filas de "Conciliación" | 534 | **534** | = |
| Materiales distintos **por matrícula** | 12.121 | **12.201** | +80 |
| Materiales distintos **por matrícula y precio** | 15.047 | **15.200** | +153 |
| Materiales distintos **por lote, matrícula y precio** | 16.844 | **17.025** | +181 |

**0 expedientes desaparecen. 0 materiales perdidos por matrícula.**

Las dos cifras de "perdidos" que salen en las otras dos claves están
explicadas y no son pérdidas:

- **Por lote+matrícula+precio, 53**: las 53 son de `6.19/28510.0196` y son las
  mismas matrículas contadas ahora en su lote 2 en vez de en el 1 (el reparto
  por lotes del cuadro entra en ese expediente por primera vez). Por matrícula
  a secas no se pierde ninguna.
- **Por matrícula+precio, 1**: es la fila `P-2` de `6.22/28510.0011`, que se
  queda sin precio por la guarda de choques (ver más abajo). No es un material
  distinto: es la misma fila sin uno de sus dos datos.

### Los 14 expedientes que cambian de número de filas, uno a uno

Los 14 suben; **ninguno baja**.

| Expediente | Antes | Ahora | Por qué |
|---|---:|---:|---|
| `6.19/28510.0131` | 0 | **91** | Bloque 3. Su cuadro de pequeño material de fibra óptica está en un documento con capa de texto que la etapa 3 no abría. Ni era un problema de escaneado ni estaba sin cuadro. |
| `6.18/28510.0071` | 0 | **73** | Bloque 3. El cuadro "Designación / Plano / PRECIO" de seis páginas, Pedido Abierto sin cantidades por diseño. Es el caso que pedía el encargo. |
| `6.19/28510.0210` | 0 | **35** | Bloque 5. Uno de los 26 de "Otro": su cuadro entra ahora y pasa a "Aporta líneas". |
| `6.19/28510.0179` | 0 | **35** | Bloque 5. Igual; es además la matriz de `0209` y `0210`. |
| `6.19/28510.0196` | 95 | **128** | El reparto por lotes del propio cuadro entra en este expediente al abrirse más páginas: sus 128 filas se reparten en lote 1 (48) y lote 2 (80), donde antes estaban todas en el 1. **+33 filas y 0 materiales perdidos.** |
| `4.26/28510.0005` | 0 | **10** | Bloque 4. El único de los 64 que sí tenía cuadro: cinco conceptos de servicio, leídos dos veces (su anejo y su contrato). |
| `3.16/28510.0156` | 0 | **7** | Bloque 3. "REF. / DENOMINACIÓN / PRECIO". |
| `2.19/28510.0015` | 0 | **3** | Bloque 3. Reglas de inducción; documento con capa de texto. |
| `3.19/28510.0201` | 0 | **3** | Bloque 3. "CONCEPTO / PRECIO". |
| `6.17/28510.0045` | 0 | **3** | Bloque 3. Cuadro de balasto con la cabecera fundida. |
| `6.16/28510.0178` | 4 | **7** | Las 3 nuevas son la misma tabla de balasto leída en su segunda página, con el código en minúsculas (ver "lo que queda anotado"). |
| `3.23/28510.0135` | 25 | **27** | Dos materiales nuevos con su precio: `P-20` (equipo de ultrasonidos phased array, 27.335,30 €) y `P-21` (equipo TFM, 36.950,25 €). |
| `6.18/28510.0064` | 0 | **2** | Bloque 3. Pararrayos de óxido metálico; la página no se abría por el vocabulario de marcadores. |
| `6.16/28510.0174` | 10 | **11** | Un carril nuevo (`60104155`, CARRIL 54E1 R260 90 M.). El `60106180` cambia de descripción por un espacio ("CARRIL 60 E1" → "CARRIL 60E1"). |

### Las celdas que cambian de valor

| Cambio | Celdas | Explicación |
|---|---:|---|
| Cantidad | **513** | Bloque 1, desglosadas arriba. |
| Descripción del material | **2** | Las dos mejoran: `6.24/28510.0188` `P-001` gana el paréntesis que le faltaba ("…TIPO AS **(ARMARIO DE SECCIONAMIENTO)**") y `4.26/28510.0020` `P-12` pierde un punto final. |
| Precio unitario | **1** | `6.22/28510.0011` `P-2`: la guarda de choques. El documento da precios distintos para ese código dentro del mismo lote y no se puede atribuir ninguno con certeza. |
| Precio adjudicado | **1** | `4.26/28510.0020` `P-12` del lote 1. **Diagnosticado**: el precio adjudicado se deriva al construir la línea, con la baja que se conoce en ese momento; la baja de su lote 1 (2,5794 %) es de las que se derivan de los importes y se conoce después. Al cambiar qué documento aporta la línea, ahora se construye antes de saberla. Su precio unitario (5.335 €) y su baja siguen en la fila, así que el dato es recalculable; la fragilidad de orden es anterior a esta sesión y queda anotada, no tocada. |

**Filas cuyo precio unitario cambia de un número a otro: 0.** El único cambio
de precio es el que pasa a vacío.

### Cuadre de "Conciliación" con "Materiales"

```
suma de la columna de líneas de "Conciliación": 19.870
filas de la hoja "Materiales":                  19.870
```

**0 expedientes sin Situación.** `comprobar_cuadre` revienta la exportación si
alguna de las dos cosas falla, así que el Excel no habría salido de otro modo.

### Auditoría

**0 errores y 6 avisos**, los seis de siempre:

| Aviso | Afectados |
|---|---:|
| Grupos de material repetido con códigos de precio distintos | 3 expedientes, 11 grupos, 22 líneas |
| Huérfanas sin lote | 19.558 líneas en 114 expedientes |
| Precios atípicos | 1.522 líneas en 79 expedientes |
| Cantidades con forma de año | 941 líneas en 32 expedientes |
| Grupos de importe de licitación compartido | 54 grupos, 24 expedientes |
| Expedientes con importe repetido entre sus lotes | 8 |

*(La auditoría que corre al final del propio ciclo del segundo reproceso ya dio
0 errores. La del primero dio 1 error —los 16 expedientes que cambiaban de
número de líneas— y es la regla funcionando: "cualquier subida es error, sin
excepción", que se deja intacta a propósito.)*

### Recuento por Situación y total de filas

| Situación | Expedientes | Antes |
|---|---:|---:|
| Aporta líneas | **373** | 363 |
| Publicado sin cuadro de precios | **63** | 64 |
| Los precios están en un acuerdo marco que no está publicado | **47** | 47 |
| Publicado dentro de la ficha de otro expediente | **17** | 17 |
| **Licitación por lotes de la que solo se conocen algunos lotes** | **14** | — (nueva) |
| Documentos escaneados que no se han podido leer | **8** | 15 |
| Otro | **4** | 26 |
| **El acuerdo marco del que depende tampoco publica precios** | **3** | — (nueva) |
| **Sus documentos son de expedientes hermanos y ninguno es el suyo** | **3** | — (nueva) |
| El acuerdo marco está publicado pero no publica precios unitarios | **2** | 2 |
| Pendiente de procesar | **0** | 0 |
| **Total** | **534** | 534 |

**Filas totales de "Materiales": 19.870.** Líneas en la base de datos: 39.651
en 612 expedientes.

Los cuatro que siguen en "Otro": `3.20/28510.0071` y `6.15/28510.0080` (su
Anuncio agrupa 4 y 17 lotes en un solo documento), `6.19/28510.0228` (su lote 2
no trae baja ni importe) y `6.19/28510.0209`, que entra en "Otro" por efecto de
que su matriz `6.19/28510.0179` ya aporta líneas y su motivo ha cambiado.

Los ocho que siguen como escaneados ilegibles: `2.18/28510.0089`,
`3.16/28510.0044`, `3.17/28510.0008`, `3.17/28510.0028`, `3.17/28510.0094`,
`3.19/28510.0017`, `6.17/28510.0012` y `6.17/28510.0116`. Cada uno con su
porqué en el bloque 3.

---

## Lo que queda anotado, y no se ha tocado

Cinco cosas medidas que cambian datos del catálogo y **no estaban en el
encargo**, así que no se han decidido aquí:

1. **Los 416 ceros de cantidad.** El documento los imprime y el sistema ya
   mostraba 2.359 antes de esta sesión, así que no es una convención nueva —
   pero si ver `0` en la columna "Cantidad" resulta peor que verla vacía, la
   vuelta atrás es una condición de una línea.
2. **Cuatro filas duplicadas que solo difieren en mayúsculas del código de
   precio**: `p-3` frente a `P-3` en `6.16/28510.0178` (3) y `p-1` frente a
   `P-1` en `6.17/28510.0045` (1). El reconocimiento óptico lee el mismo cuadro
   en dos páginas con el código en distinto caso. Unificar el caso quitaría los
   cuatro duplicados **pero dejaría sin precio a dos filas más**, porque las
   dos páginas de `0178` dan precios distintos (1,12 y 1,08: probablemente
   licitación y oferta) y saltaría la guarda de choques. Medido: en todo el
   corpus solo hay **4 grupos** en esos dos expedientes; los otros 143 códigos
   en minúsculas (`Cod0001`… de `4.25/28510.0132`, `P-001b`… de
   `6.24/28510.0185`) no chocan con nada y son el literal del documento.
3. **Las cinco descripciones `Precio!Mensual!de!Mantenimiento!` de
   `4.26/28510.0005`**: la fuente de su contrato mapea el espacio al signo
   `!`. Su anejo trae las mismas cinco limpias, así que no se pierde material,
   pero el Excel enseña los cinco conceptos dos veces. Medido: **5 filas en un
   solo expediente** de las 19.870.
4. **El precio adjudicado de `4.26/28510.0020` `P-12` (lote 1)**: la fragilidad
   de orden descrita arriba. Una celda.
5. **`3.17/28510.0028`**: aceptar su cuadro exige añadir "elemento" como alias
   de descripción, que choca con "CÓDIGO DEL ELEMENTO" (ya alias de código de
   precio).

Y siguen en pie las decisiones abiertas de las partes anteriores: los once
expedientes cuyo título declara un lote que no está entre los suyos (bloque 6),
la errata CONTRAGUJA/CONTRAAGUJA, las 946 huérfanas de las causas C y D,
`6.26/28510.0064` lote 3 `P-2`, "Comentarios" fila a fila o nota única, y si
`Precio unitario` es el licitado o el adjudicado.
