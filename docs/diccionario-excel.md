# Diccionario del Excel del catálogo

Bloque 5 del encargo de la sesión 2026-09-19 (sexta parte). **Escrito para
quien no sabe nada del sistema**: qué contiene cada hoja y cada columna, de
dónde sale cada dato, cuándo puede quedar vacío, y qué significa cada motivo y
cada situación.

Está al día con el Excel del cierre de esta sesión. Si alguna cifra concreta se
cita, es la de ese Excel; la estructura no depende de las cifras.

---

## Qué es este Excel

Es **un solo catálogo para todos los expedientes**, no uno por expediente. Cada
fila de la hoja "Materiales" es **un artículo, de un lote, de un expediente**,
con el precio que el pliego publicó para él.

Todo lo que hay en él sale de **documentos publicados en la Plataforma de
Contratación del Sector Público** o de **listados que ADIF nos ha enviado**.
Cada cifra está anclada al documento, la página y el fragmento de texto de los
que se leyó. **El sistema nunca inventa un dato**: lo que no puede demostrar
contra un documento, lo deja vacío y explica por qué.

El Excel es **una vista que se regenera a demanda**, no la fuente. Los datos
viven en la base de datos con su traza; el fichero se puede volver a exportar
en cualquier momento y sale igual.

### Las hojas

| Hoja | Qué contiene |
|---|---|
| **Materiales** | El catálogo. Una fila por artículo, lote y expediente |
| **Conciliación** | Una fila por expediente publicado del departamento, aporte líneas o no, con qué se descargó, qué se leyó y por qué no aportó nada si no lo hizo |
| **Resumen** | Las cifras del Excel y la explicación, en lenguaje llano, de por qué hay líneas que no están en "Materiales" |
| **Presupuestos ADIF** | *Solo aparece cuando ADIF nos manda su listado de estados con la columna de presupuesto de licitación.* Compara ese presupuesto con el importe que el sistema lee de los documentos |

---

## Hoja "Materiales" — las 18 columnas

En este orden exacto. Las once primeras son el formato original que pidió el
cliente y **nunca se reordenan**; las siete siguientes se añadieron después,
siempre al final.

### 1. Código interno

**Qué es.** El `Nº Interno` con el que ADIF agrupa este expediente en su propio
listado de códigos de proyecto. Es el número por el que almacenes busca.

**De dónde sale.** Del cruce con `Códigos de proyecto.xlsx`, por número de
expediente exacto.

**Cuándo queda vacío.** Tres causas distintas, y la columna "Motivo de las
celdas vacías" dice cuál de las tres:

- *no consta (este expediente no aparece en el listado de códigos de ADIF)*.
- *no consta (el listado de códigos de ADIF no trae número interno para este
  expediente)*: la fila existe, pero esa celda viene vacía en su listado.
- *no consta (este expediente no figura por sí mismo en el listado de códigos
  de ADIF)*: se le encuentra una fila, pero es la de **otro** expediente de su
  misma familia (se le encuentra por la columna del acuerdo marco, no por su
  propio número). Escribir ese número aquí sería peor que dejarlo vacío,
  porque en almacenes llevaría al expediente equivocado.

**Un aviso.** El mismo código interno **se repite entre expedientes distintos**:
es el propio listado de ADIF el que asigna uno por familia de expedientes, no
un error. No sirve como clave.

### 2. Código de expediente

**Qué es.** El número del expediente, en el formato de ADIF
(`6.24/28510.0088`).

**De dónde sale.** Del propio sistema: del documento que lo declara, del
listado de SAP que lo dio de alta o de la sindicación que lo descubrió. **No
sale del listado de códigos** y **no depende de ningún cruce**.

**Cuándo queda vacío.** Nunca en la práctica: si el expediente existe en el
sistema, tiene número.

> Hasta el 18/09/2026 esta columna solo se rellenaba si el expediente cruzaba
> con el listado de códigos, y el cliente concluyó tres veces que faltaban
> expedientes que sí estaban (2.381 filas de 92 expedientes). Se corrigió: la
> columna es el número, y se rellena siempre.

### 3. Código matriz

**Qué es.** El expediente del **acuerdo marco** del que cuelga este pedido,
cuando lo hay. Un mismo código puede ser expediente en una fila y matriz en
otra.

**De dónde sale.** Del campo fijo *"Licitación basada en el acuerdo marco →
Expediente"* del anuncio de la Plataforma, o de la columna `MATRIZ` del listado
de códigos.

**Cuándo queda vacío.** *no consta (no se conoce ningún acuerdo marco del que
dependa este expediente)* — que es lo normal: la mayoría de los expedientes no
cuelgan de ninguno. **El sistema nunca inventa una matriz.**

### 4. Título expediente

**Qué es.** El objeto del contrato.

**De dónde sale.** Del campo *Objeto del Contrato* del anuncio publicado. Si el
documento no lo trae, del título que traen los listados que ADIF nos envía.

**Cuándo queda vacío.** *no consta (no se ha encontrado el título en los
documentos de este expediente)*.

### 5. Matrícula del material

**Qué es.** El código de 9 cifras con el que ADIF identifica el artículo (en
pliegos antiguos, de 8: `59020019`).

**De dónde sale.** De la columna de matrícula del cuadro de precios del
documento.

**Cuándo queda vacío.**

- *no aplica (partida alzada)*: la fila es una reserva presupuestaria a tanto
  alzado, no un artículo de almacén. No tiene matrícula por definición.
- *no consta*: el cuadro de precios de ese documento no publica matrículas.
  Pasa en un tercio largo de las filas y **es normal**: no todos los pliegos
  las traen.

**Cuidado: la matrícula no es la clave del catálogo.** Falta en demasiadas
filas. La clave es *expediente + lote + código de precio*.

**Un caso concreto que se puede ver en el Excel.** Algunos pliegos imprimen una
matrícula con una letra al final (`69520000N`). No es una matrícula válida, así
que la celda se queda vacía — pero el literal **no se pierde**: va al final de
la Descripción del material, entre corchetes y diciendo lo que es
(`[matrícula impresa en el documento, no válida: 69520000N]`). 33 filas.

**Dos avisos sobre las matrículas que sí salen, y que el Resumen cuenta.** Hay
filas cuya matrícula es correcta —es la que imprime el pliego, comprobada
contra la imagen del documento— y que **no aparecen en el maestro de
materiales que ADIF nos envía**. Salen igual, con su matrícula literal, y
llevan su explicación:

| Aviso | Qué significa |
|---|---|
| *matrícula con formato antiguo de 8 dígitos, no figura en el maestro actual de ADIF* | El pliego es de 2016-2018 y usa el formato de 8 cifras (`59020019`). El maestro de hoy solo trae de 9. **382 filas de 20 expedientes** |
| *no figura en el maestro de materiales de ADIF* | La matrícula es de 9 cifras, del formato actual, y el maestro sencillamente no la trae. No es un fallo de lectura ni una errata: ese listado está incompleto **artículo a artículo** dentro de familias que sí conoce — hay un pliego que compra 28 referencias correlativas de las que el maestro trae 5. **2.511 filas de 55 expedientes** |

**Lo que NO se hace, y conviene saberlo**: no se "completa" ni se corrige
ninguna matrícula para que case con el maestro. Añadir un dígito al final de
`64571017` da a la vez `645710170`, que es una palomilla, y `645710175`, que
son unas antenas: el parecido no demuestra nada. La medición completa está en
`docs/matriculas-8-digitos-y-el-maestro.md` y
`docs/matriculas-de-9-digitos-fuera-del-maestro.md`.

### 6. Descripción del material

**Qué es.** La designación del artículo, **literal del documento**. Es lo que
permite poner la fila del Excel al lado de su renglón del PDF y comprobar que
coinciden palabra por palabra.

**De dónde sale.** De la columna de descripción / designación / denominación
del cuadro de precios.

**Cuándo queda vacío.** Nunca: **una línea sin descripción y sin matrícula no
entra en el catálogo**. Es una comprobación permanente, no un filtro
opcional — una fila sin descripción no sirve en almacenes.

**Tres cosas que se pueden ver en esta columna y tienen explicación:**

- **Dos grafías de la misma pieza**: "contraaguja" y "contraguja" conviven en
  los pliegos de ADIF. No se unifica sin que ADIF lo diga; la columna "Código
  del material" ya agrupa las dos.
- **Una referencia de fabricante en vez de una frase** (`SFT01-2388L-PH-6920`,
  `WCMX-04 02 08-R53`): son cuadros de insertos y herramienta de mecanizado
  cuya **única columna de texto es esa**. El documento no publica otra
  descripción. Esas líneas van marcadas en la cola de revisión y contadas en el
  Resumen.
- **El sufijo entre corchetes de la matrícula no válida** (arriba, columna 5).

### 7. Código del material

**Qué es.** La familia de la pieza (`SEMICAMBIO`, `AGUJA`, `CRUZAMIENTO`,
`BRIDA`, `PLACA`…). Sirve para agrupar el mismo tipo de material entre
expedientes distintos.

**De dónde sale**, en este orden:

1. De la **columna de tipo de pieza del propio cuadro** cuando el documento la
   trae ("REPUESTO", "TIPO DE TRAVIESA"): su valor literal manda.
2. Si no, del **sustantivo principal de la descripción**, con un vocabulario
   controlado que crece con el uso, e incluyendo las siglas de aparatos de vía
   verificadas contra el corpus (`AC`/`AR` aguja, `CAC`/`CAR` contraaguja,
   `CZ*` cruzamiento, `SC*` semicambio…).

**Cuándo queda vacío.** *no consta*, cuando la descripción no casa con ningún
término conocido: marcas comerciales, servicios (transporte, acopio, descarga)
y siglas no verificadas. **No es un dato perdido**: el vocabulario es todavía
corto y se amplía con el uso. La hoja "Resumen" lo dice también.

### 8. Cantidad

**Qué es.** Las unidades de ese artículo que el cuadro de precios estima o
compromete.

**De dónde sale.** De la columna de cantidad / medición / unidades del cuadro.

**Cuándo queda vacío.**

- *no aplica (partida alzada)*.
- *pendiente (el documento da una cantidad distinta para cada lote y falta
  saber cuál es la de este)*.
- *no consta*: el cuadro **de verdad no publica cantidad**. Es más frecuente de
  lo que parece y casi siempre legítimo: hay pliegos con una columna "Cantidad
  estimada de referencia" que el propio documento deja en blanco, y "Pedidos
  Abiertos" que declaran por escrito que no hay compromiso de compra en firme.

**Un valor que sorprende y es correcto**: hay filas con cantidad **0**. Es lo
que imprime el documento, y el cliente decidió mantenerlo.

### 9. Precio unitario

**Qué es.** El **precio licitado** del artículo: el que el pliego publica como
precio máximo, antes de aplicar la baja de la oferta ganadora.

**De dónde sale.** Del cuadro de precios del documento. Es el que imprime la
celda, con **una sola excepción**: cuando el documento demuestra por su propia
aritmética que el precio impreso no cuadra con su renglón y que el que sí
cuadra cierra además un total declarado. Esas filas van marcadas y contadas en
el Resumen.

**Cuándo queda vacío.**

- *no aplica (partida alzada)* — raro: casi todas traen su importe.
- *pendiente (el documento da un precio distinto para cada lote y falta saber
  cuál es el de este)*.
- *no consta*.

> **Pendiente de confirmar con ADIF**: que "Precio unitario" sea el licitado y
> no el adjudicado fue una decisión de sesión, nunca confirmada por el cliente.
> Ver `docs/preguntas-pendientes-cliente.md`, pregunta 11.

### 10. Lote

**Qué es.** La subdivisión del expediente a la que pertenece el artículo. Cada
lote da lugar a un contrato independiente y **tiene su propia baja**.

**De dónde sale.** De la cabecera del cuadro de precios, del título de la
sección que lo precede, o del anuncio.

**Cuándo queda vacío.** *no consta*. Y aquí hay algo importante: **una línea
sin lote no sale en esta hoja**. Si ve la columna vacía es porque el Excel se
exportó a propósito con las líneas pendientes incluidas.

> Cuidado con la palabra "lote": en una licitación multi-lote es la subdivisión
> en contratos; en un pedido derivado de acuerdo marco, "Lote 4" puede ser una
> **categoría de producto** del catálogo del acuerdo marco, sin ninguna
> subdivisión en contratos. Son dos cosas distintas con el mismo nombre.

### 11. Precio adjudicado

**Qué es.** Lo que de verdad se paga por unidad: `precio unitario × (1 − baja
del lote)`.

**De dónde sale.** **Es una derivación, no un dato leído.** No existe ninguna
tabla de precios adjudicados en los pliegos, y no hay que buscarla: el
licitador oferta **una sola baja porcentual por lote**, aplicable a todos los
precios unitarios de ese lote.

**Cuándo queda vacío.**

- *pendiente (falta el precio unitario)*.
- *pendiente (falta la baja del lote)*.
- *no aplica (este contrato no tiene una baja única: su precio se revisa pedido
  a pedido con un coeficiente que ADIF pacta con el proveedor fuera de la
  Plataforma)* — los acuerdos marco de carril.

### 12. Baja del lote

**Qué es.** El porcentaje de rebaja que ofertó el adjudicatario de ese lote.

**De dónde sale.** **Se lee del texto** de la propuesta de adjudicación o del
contrato ("baja del 0,50 % … precios unitarios"), nunca se calcula.

**Cuándo queda vacío.** *no consta*, o *no aplica* en los contratos de precio
indexado (arriba).

> **Por qué no se calcula.** La cuenta ingenua `1 − adjudicado/licitación` da
> 0 % en la mayoría de estos contratos, porque el presupuesto es un techo de
> gasto que no cambia. Ejemplo real: `6.24/28510.0088`, licitación
> 1.000.000 €, adjudicación 1.000.000 €, baja real 0,50 %.
>
> **Una baja de 0,00 % puede ser real.** Las que hay están ancladas al
> fragmento exacto del documento que las declara ("baja económica del
> 0,00 % …"). La extracción nunca guarda 0 por defecto.

### 13. Unidad de medida

**Qué es.** En qué se mide la cantidad y el precio (`ud`, `m`, `kg`, `t`, `h`,
`t·km`…). Sin ella, una Cantidad de 2.000 o un Precio unitario de 0,142 no
significan nada: pueden ser metros de cable o toneladas de balasto.

**De dónde sale.** De la columna de unidad del cuadro; si el documento no la
trae, del maestro de materiales de SAP por matrícula exacta (**nunca pisa** una
unidad leída de un documento real).

**Tres valores de esta columna que sorprenden y tienen explicación:**

- **`m` donde el documento escribe `Ml`**: `Ml` es metro lineal, y se unifica
  con `m` como `UD.`/`UN` se unifican con `ud`. Son 3 filas de obra civil
  (lámina geotextil, muro de contención, zona de paso), en un cuadro que usa
  `m3` y `m2` para volumen y superficie en las filas de al lado.
- **`transporte`**: el cuadro escribe el precio como `€/transporte`, igual que
  escribe `€/Ton*km` en las filas de al lado. Es el denominador del precio: lo
  que se paga por cada transporte. 15 filas de `6.21/28510.0108`-`0112`.
- **`P`**: es el único valor de esta columna que **no sale de ningún
  documento**. El cuadro de esas 3 filas no publica unidad, y el valor viene
  del maestro de materiales de ADIF, donde la unidad base de esa matrícula es
  `P` — un código propio de SAP cuyo nombre completo el listado no trae.

**Cuándo queda vacío.**

- *no aplica (partida alzada)*: el documento escribe `PA` ahí, pero "PA" no es
  una unidad, es el **tipo de línea**.
- *no consta*: el cuadro no declara ninguna columna de unidad.

Solo se guarda un valor del vocabulario de unidades conocidas. Cualquier otro
se descarta y la línea va a revisión — así una referencia normativa o un
número desplazado de otra columna no acaban aquí haciéndose pasar por una
unidad.

### 14. Estado del contrato (SAP)

**Qué es.** En qué punto está el contrato dentro de SAP ("En ejecución",
"Recepcionado"…). **No es el estado de procesamiento de este sistema.**

**De dónde sale.** Del Excel de expedientes en ejecución que ADIF nos envió el
07/09/2026.

**Cuándo queda vacío.** *no consta (este expediente no aparece en el listado de
contratos en ejecución de SAP)*.

### 15. Objeto del contrato (documento)

**Qué es.** El mismo título de la columna 4, repetido aquí por el orden de
columnas que pidió el cliente.

### 16. Código de precio

**Qué es.** El identificador del renglón dentro de su cuadro (`P-001`,
`P-067`). **Es la clave real del catálogo**, junto con el expediente y el lote:
es lo único que lleva una fila del Excel a su renglón exacto del PDF.

**De dónde sale.** De la primera columna del cuadro de precios.

**Cuándo queda vacío.** *no consta (el cuadro de precios de este documento no
numera sus renglones)*. Más de la mitad de las filas lo dejan vacío, y **no es
un hueco de extracción**: hay cuadros que simplemente no numeran.

**Comprobado antes de publicarla**: dentro de un mismo expediente y lote, el
código **no se repite ni una vez**.

### 17. Motivo de las celdas vacías

**Qué es.** Por qué está vacía cada celda de esa fila. Es la columna que
convierte un hueco en una explicación.

**Cómo se lee.** Una entrada por celda vacía, con el nombre del dato y uno de
**tres motivos**:

| Motivo | Qué significa |
|---|---|
| **no aplica** | Ese dato **no existe** para este tipo de línea. Una partida alzada no tiene matrícula; un contrato de precio indexado no tiene una baja única. No falta nada |
| **no consta** | El documento **no lo publica**. No es un fallo de lectura: ahí no hay nada que leer |
| **pendiente** | El dato existe pero **falta otro** para poder darlo: un precio adjudicado sin su baja, o una cantidad que el documento da distinta para cada lote |

Muchas entradas llevan además un detalle entre paréntesis que dice exactamente
cuál de las causas posibles es la de esa fila.

**Por qué la celda se queda vacía en vez de traer un marcador de texto**:
poner "N/D" en la columna de Precio unitario la convertiría en texto y rompería
cualquier suma o filtro numérico del Excel.

### 18. Comentarios

**Qué es.** La única columna que rellena **una persona a mano**. Sale siempre
vacía. Está la última para que no estorbe a las columnas que sí vienen del
documento.

---

## Hoja "Conciliación" — las 11 columnas

**Para qué existe.** Contesta la pregunta *"¿cómo sabemos que la app ha leído
todo lo que hay publicado?"*. Hasta que existió, un expediente que no aportaba
ninguna línea simplemente no aparecía en el Excel — indistinguible de uno que
el sistema nunca hubiera visto.

**Qué lista.** **Una fila por cada expediente del departamento que consta
publicado en la Plataforma**, aporte líneas o no. De cualquier año, en
cualquier estado y de cualquier tipo de procedimiento. Más, siempre, cualquier
expediente que haya aportado filas a "Materiales" aunque no cumpla el criterio
de departamento.

**Qué NO es.** No es un recuento paralelo. La columna de líneas la rellena el
mismo recuento que escribió la hoja "Materiales", nunca una consulta propia: si
las dos cifras pudieran discrepar, la hoja dejaría de servir para lo único que
existe. **La exportación falla si no cuadran.**

**De dónde sale la lista de lo publicado.** De las dos vías de descubrimiento
juntas —el boletín mensual de sindicación y la búsqueda directa en el buscador
de la Plataforma— más la evidencia más fuerte de las tres: haberle descargado
al menos un documento. Queda fuera lo que la Plataforma confirmó que no tiene.

| # | Columna | Qué es |
|---|---|---|
| 1 | Código de expediente | |
| 2 | Título | |
| 3 | Órgano de contratación | Quien licita, según el anuncio |
| 4 | Estado que consta publicado en la Plataforma | Ver abajo |
| 5 | Estado según ADIF | Lo que dice el listado de SAP que ADIF nos envía. **Nunca se mezcla con la anterior** |
| 6 | Documentos descargados | Cuántos ficheros se bajaron de su ficha |
| 7 | Documentos leídos con reconocimiento óptico | De esos, cuántos eran imágenes sin texto y hubo que leerlos con un modelo |
| 8 | Líneas que aporta al catálogo | Las filas que este expediente pone en "Materiales" |
| 9 | Baja y de dónde sale | En una frase, con el fragmento literal del documento que la declara |
| 10 | Situación | Ver la tabla de abajo |
| 11 | Motivo | La explicación concreta de esa fila, en lenguaje llano |

### Las dos columnas de estado, y por qué son dos

**"Estado que consta publicado en la Plataforma"** llega como mucho hasta
*Resuelta*: la Plataforma publica la licitación, la adjudicación y la
formalización del contrato, y nada de lo que le pase al contrato después.
Valores posibles: *Anuncio previo*, *En plazo de presentación*, *Pendiente de
adjudicación*, *Adjudicada*, *Resuelta*, *Anulada*.

**"Estado según ADIF"** es donde caben los estados posteriores (en ejecución,
recepcionado, facturado, cerrado…), porque salen del SAP de ADIF.

**Es una decisión escrita del cliente** (Isabel Ibáñez, ADIF, 18/09/2026): sin
acceso a SAP, el último estado que la herramienta puede conocer es *Resuelta o
adjudicado*; los posteriores los indican ellos a mano. Juntarlas haría
imposible saber cuál de las dos se está leyendo.

Un detalle: si el sistema ya tiene descargada de la Plataforma la Resolución de
Adjudicación o el Contrato, la columna 4 usa eso en vez del último boletín —
un boletín refleja el evento de su mes, no "sigue vigente". **Nunca al revés**:
la columna solo sube de etapa, jamás baja.

### Las once Situaciones

| Situación | Qué significa |
|---|---|
| **Aporta líneas** | Se han leído sus documentos y ha puesto N líneas de material en el catálogo, con su precio |
| **Publicado sin cuadro de precios** | Sus documentos están descargados y leídos, y **ninguno trae un cuadro de precios unitarios**. La Plataforma publica de él la adjudicación y el contrato, pero no el anejo de precios. También cubre el caso de la ficha que aparece pero no publica ningún documento descargable |
| **Los precios están en un acuerdo marco que no está publicado** | Es un pedido contra un acuerdo marco cuyos documentos no están en la Plataforma: no hay de dónde leer el precio. Haría falta que ADIF facilitara el cuadro de precios de ese acuerdo marco |
| **El acuerdo marco está publicado pero no publica precios unitarios** | El acuerdo marco sí está y se ha leído entero, pero lo que publica es el **modelo de proposición económica en blanco**: las unidades puestas y la columna de precio vacía, que es la que rellena cada licitador |
| **El acuerdo marco del que depende tampoco publica precios** | El acuerdo marco está publicado y leído, y tampoco él trae cuadro de precios ni baja. El precio no está publicado ni aquí ni allí |
| **Documentos escaneados que no se han podido leer** | Sus documentos son copias escaneadas (imágenes). Se han pasado por reconocimiento óptico y no se ha podido recomponer de ellos un cuadro fiable. Haría falta el original electrónico, o revisarlo a mano |
| **Publicado dentro de la ficha de otro expediente** | Es un lote de una licitación, y sus documentos se publican bajo el número del expediente principal, no bajo el suyo. Buscarlo por su número no devuelve nada, **y eso no significa que no esté publicado**. Lo que aporte se cuenta en la fila del principal |
| **Sus documentos son de expedientes hermanos y ninguno es el suyo** | Los documentos publicados bajo su número son los de sus lotes hermanos: cada uno declara su propio número de contrato y ninguno es el de este expediente. Se han leído enteros, y por eso **no** se les toma ni la baja ni el cuadro: serían los de otro lote |
| **Licitación por lotes de la que solo se conocen algunos lotes** | De los documentos publicados solo se puede leer la baja o el importe de algunos lotes, y no del que corresponde a este expediente |
| **Pendiente de procesar** | O no se ha descargado todavía ningún documento suyo, o están descargados y aún no se han terminado de leer. Es trabajo pendiente de verdad |
| **Otro** | Se han leído sus documentos, no ha aportado nada, y la causa no encaja en ninguna de las anteriores. **Obliga a explicarse**: la columna "Motivo" trae lo que el sistema anotó al leerlo. No es un cajón de sastre silencioso |

El orden de arriba es también el orden en que se comprueban: **la primera
situación que se cumple es la que de verdad explica el caso**.

### De cuándo es el registro

Debajo de la tabla, el Excel escribe **de qué fecha es el registro de lo
publicado y qué cubre**: los departamentos, los boletines de sindicación
cargados y su fecha, cuándo fue la última búsqueda directa y cuántos
expedientes devolvió, y el reparto entre publicados / no publicados /
publicados dentro de la ficha de otro. Una cifra de cobertura sin decir de
cuándo es no sirve para decidir nada.

---

## Hoja "Resumen"

Las cifras del propio Excel y, sobre todo, **por qué hay líneas que no están en
"Materiales"**.

| Fila | Qué es |
|---|---|
| Líneas en este catálogo | Las filas de "Materiales" |
| Líneas pendientes de revisión (no incluidas arriba) | Las que existen en la base de datos y no salen |
| Líneas del anejo de criterios técnicos, común a todos los lotes | La lista de materiales de la licitación entera, con su propia numeración. **No son de ningún lote por diseño**, y cada material figura con su precio en el cuadro del lote que lo compra |
| Líneas con Cantidad o Precio unitario pendiente | El documento da un valor distinto para cada lote |
| Líneas cuyo Precio unitario se ha recalculado desde la columna de importes | Ver abajo |
| Líneas cuya Descripción del material es la referencia del documento | Ver abajo |
| Líneas cuya Matrícula tiene el formato antiguo de 8 dígitos y no figura en el maestro actual de ADIF | Ver la columna 5 |
| Líneas cuya Matrícula (9 dígitos) no figura en el maestro de materiales de ADIF | Ver la columna 5 |

Después, una tabla de **tres columnas** —*Qué ha pasado* / *Líneas* / *Qué
haría falta para resolverlo*— con una fila por cada causa. Las causas, en
lenguaje llano, son casi siempre de un mismo tipo: **materiales de los que no
se sabe con seguridad a qué lote pertenecen**. Se dejan fuera para no mostrar
el mismo material varias veces sin poder distinguir una repetición real de un
error de lectura del documento. **Siguen guardados: no se han perdido.**

Dos de esas categorías merecen leerse:

- **"duplicado de material ya incluido"**: no es un hueco real. Es la misma
  matrícula, descripción y precio que ya aparece en "Materiales" desde otro
  documento del mismo expediente.
- **"cuadro de precios sin cabecera, columnas mal identificadas"** y **"cuadro
  sin precio unitario: solo publica el importe de cada renglón"**: el sistema
  no ha podido identificar con confianza qué columna es cada dato, o el
  documento solo publica el importe total del renglón y la división entre la
  cantidad no queda demostrada. Para no inventar valores, esas filas se
  descartan del Excel aunque sigan guardadas.

### Las cuatro marcas que el Resumen cuenta

**"Precio unitario recalculado desde la columna de importes del propio
documento".** El precio que imprime la celda no cuadra con su propio renglón
(cantidad × precio ≠ importe) y el que sale de dividir el importe entre la
cantidad sí. Solo se reescribe cuando se cumplen **las dos condiciones a la
vez**: que esa división sea exacta, y que con el precio corregido el lote sume
exactamente uno de los totales que el documento declara. Si falta cualquiera de
las dos, no se toca nada.

**"Descripción del material tomada de la referencia del documento".** El cuadro
de precios no publica ninguna descripción en prosa: su única columna de texto
es la referencia del artículo. No falta ninguna descripción — el documento no
publica otra.

**"Matrícula que no figura en el maestro de materiales de ADIF"**, en sus dos
variantes (8 y 9 dígitos). La matrícula que el documento imprime se entrega
literal; lo que falta es su fila en el listado de materiales de ADIF. Ver la
columna 5, "Matrícula del material". El día que ADIF mande un maestro más
completo, estas dos cifras bajan solas.

Las cuatro marcas, además de contarse aquí, van en el motivo de revisión de
cada línea; las dos primeras, además, en el fragmento de traza que la ancla a
su documento, igual que las líneas leídas por reconocimiento óptico.

---

## Hoja "Presupuestos ADIF"

**Solo aparece si ADIF nos ha mandado su listado de estados con la columna de
presupuesto de licitación.** Mientras no llegue, la hoja no se escribe: una
hoja vacía haría pensar que falta un dato que nadie ha mandado.

| Columna | Qué es |
|---|---|
| Código de expediente | |
| Título expediente | |
| Presupuesto de licitación según ADIF | Lo que dice su listado |
| Importe de licitación leído de los documentos | Lo que el sistema leyó de un documento publicado, con su traza |
| Diferencia (ADIF − documentos) | |
| Diferencia relativa | Sobre el presupuesto de ADIF |
| Resultado | *Coincide* / *Difiere* / *Sin importe leído de los documentos* |

**El orden**: primero las coincidencias, después las diferencias de mayor a
menor, y al final los expedientes sin importe.

**Las dos cifras no se mezclan nunca**: el presupuesto de ADIF vive en su
propio campo y jamás escribe en el importe leído de los documentos. Una
diferencia no dice cuál de las dos está mal: dice que hay que mirar ese
expediente.

---

## Preguntas frecuentes

**¿Por qué el mismo material aparece en varias filas?** Porque el catálogo es
por **artículo, lote y expediente**. El mismo material comprado en dos
expedientes son dos filas, con su precio y su fecha cada una — que es
precisamente la pregunta que ADIF quería poder contestar: cómo evoluciona el
precio de un material.

**¿Por qué hay expedientes en "Conciliación" que no están en "Materiales"?**
Porque están publicados pero no aportan ninguna línea. La columna "Situación"
dice por qué, y la columna "Motivo" lo explica caso por caso.

**¿Por qué hay celdas vacías?** Porque el documento no publica ese dato, o
porque no aplica a ese tipo de línea, o porque falta otro dato del que depende.
La columna "Motivo de las celdas vacías" lo dice fila a fila. **El sistema
prefiere una celda vacía explicada a un número inventado.**

**¿Puedo fiarme de un precio concreto?** Sí, y se puede comprobar: cada fila
tiene su expediente, su lote y su código de precio, que llevan al renglón
exacto del documento publicado. Las filas cuyo precio no salió literal de su
celda están marcadas y contadas en el Resumen.

**¿Dónde están los expedientes que no son de mi equipo?** Se pueden esconder
del Excel y de la pantalla de catálogo con una lista de exclusión, que el
cliente entrega y que se puede cambiar sin tocar el código. Hoy esa lista está
vacía. Lo excluido **nunca se borra** de la base de datos.
