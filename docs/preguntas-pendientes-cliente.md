# Preguntas pendientes para el cliente

Bloque 4 del encargo de la sesión 2026-09-19 (sexta parte): **todas** las
preguntas abiertas, reunidas en un solo documento, cada una con su contexto,
los expedientes y filas afectados, y qué haremos según lo que contesten.
**Ampliado con las cuatro de la séptima parte** (12 a 15: las unidades
`transporte` y `P`, las matrículas que el maestro no recoge y las tres erratas
de matrícula del propio pliego).

**Esto no es un mensaje para el cliente.** Es la información medida para que
la pregunta la formule quien habla con ADIF. Cada cifra está medida contra la
base de datos y los documentos reales del 2026-09-19, y cada dato dice de
dónde sale.

Los dos documentos anteriores siguen siendo válidos y no se repiten entero
aquí; este los índice y añade lo que faltaba:

- `docs/pregunta-cliente-contraguja-contraaguja.md` — la pregunta 1, ya
  redactada palabra por palabra.
- `docs/preguntas-cliente-lotes-del-titulo-y-ficheros-de-entrada.md` — el
  detalle completo de las preguntas 2 y 6, con sus tablas de trazas.
- `docs/entradas-pendientes-del-cliente.md` — la forma exacta que espera cada
  uno de los tres ficheros de la pregunta 7.

---

## Índice

| # | Pregunta | Qué toca | Afectado |
|---|---|---|---:|
| 1 | CONTRAGUJA frente a CONTRAAGUJA | Descripción del material | 540 líneas |
| 2 | Los 11 expedientes cuyo título de SAP nombra un lote que sus contratos no publican | Lote | 11 expedientes |
| 3 | La numeración de lotes desplazada de `3.21/28510.0096` (`3.22/28510.0009` quedó contestada por el documento el 21/09) | Lote y precios | 1 expediente |
| 4 | El código de las traviesas | Código del material | 1.963 líneas |
| 5 | La lista de códigos internos de almacenes y las palabras para excluir por título | Qué sale en el entregable | Sin medir hasta tenerla |
| 6 | Qué ficheros de entrada podemos seguir usando | Todas las columnas de cruce | 5 ficheros |
| 7 | Los tres ficheros que esperamos | Tres cruces nuevos | 83 contratos + 358 expedientes + su catálogo |
| 8 | Las 946 huérfanas de las causas C y D | Filas que no llegan al entregable | 946 líneas |
| 9 | `6.26/28510.0064` lote 3 `P-2` | Precio | 1 línea |
| 10 | "Comentarios": fila a fila o nota única | Una columna del Excel | Todo el Excel |
| 11 | `Precio unitario`: ¿licitado o adjudicado? | La columna 9 del Excel | Todo el Excel |
| 12 | `transporte` como unidad de medida | Unidad de medida | 15 líneas |
| 13 | Qué es la unidad `P` del maestro de materiales | Unidad de medida | 3 líneas |
| 14 | Las matrículas que el maestro no recoge | Matrícula del material | 2.893 líneas |
| 15 | Las tres erratas de matrícula del propio documento | Matrícula del material | 7 líneas |
| 16 | La Cantidad de los cuadros con «cantidad mínima por pedido» y «pedido inicial» | Cantidad | 451 líneas, 22 expedientes |

---

## 1 — CONTRAGUJA frente a CONTRAAGUJA

**El hecho.** En los pliegos de ADIF conviven dos grafías de la misma pieza.
Medido hoy en la base de datos: **714 líneas de 13 expedientes** dicen
"contraaguja" en su descripción y **540 de 9 expedientes** dicen "contraguja".
La columna "Código del material" ya agrupa las dos bajo `CONTRAAGUJA` en 1.445
líneas de 14 expedientes; las 264 que quedaron con `CONTRAGUJA` son todas
huérfanas de `6.21/28510.0112`/`0113` y no salen al Excel.

**Dónde vive la errata.** Solo en "Descripción del material", que es literal
del documento y tiene que seguir siéndolo mientras no digan lo contrario: es
la columna que permite poner la fila del Excel al lado de su renglón del PDF y
comprobar que coinciden palabra por palabra.

**La pregunta**, ya redactada en
`docs/pregunta-cliente-contraguja-contraaguja.md`: ¿la descripción sigue
diciendo lo que dice cada documento, o unificamos la grafía en el entregable y
guardamos la original aparte?

**Qué haremos según contesten.**

- *Que siga literal*: nada. Es el comportamiento de hoy.
- *Que se unifique*: se normaliza la grafía en la columna "Descripción del
  material" y el literal original pasa a una columna propia, para no perder la
  trazabilidad contra el PDF. Son 540 filas; ningún precio, matrícula ni
  cantidad cambia.

---

## 2 — Los once expedientes cuyo título de SAP nombra un lote que sus contratos no publican

**El hecho, y el hallazgo que reorienta la pregunta.** Once expedientes tienen
un título que empieza por "Lote N", y ese N **no está entre los lotes que
declaran sus documentos publicados**. Y el título no sale de ningún documento
de la Plataforma: sale del propio SAP de ADIF (ninguno de los once tiene traza
de `nombre_proyecto` desde un documento, y los once están en los dos listados
que ADIF nos envió).

La tabla completa —qué lote dice el título, qué lotes tiene registrados, qué
lotes declara la licitación, cuántas filas aporta— y las trazas literales
(documento, página y frase) están en
`docs/preguntas-cliente-lotes-del-titulo-y-ficheros-de-entrada.md`, apartado 1.
Resumen: `6.21/28510.0135`, `0137`, `0138`; `6.22/28510.0139`, `0140`, `0142`,
`0147`, `0148`, `0149`; `6.23/28510.0073`, `0074`.

**La pista incómoda.** El `ANEJO_3.pdf` de `6.21/28510.0135` sí trae, en su
página 6, una sección titulada "LOTE 6 - PLACAS ASIENTO PAE..." palabra por
palabra el título que ADIF le da. El cuadro del lote 6 está publicado dentro
de un documento de ese expediente; lo que no hay es ningún documento que ligue
el número `6.21/28510.0135` al lote 6.

**Qué preguntar**, en este orden:

1. ¿Por qué los lotes que declaran los contratos publicados bajo estos once
   números no incluyen el que su propio título nombra?
2. ¿Cuál es el número de expediente del lote que el título nombra? Si existe
   uno propio, es el que debería llevar esas líneas.
3. ¿La Plataforma publica los contratos de estos lotes bajo el número del
   expediente principal en vez del suyo? Es el mecanismo ya confirmado para
   otros 17 expedientes (Situación "Publicado dentro de la ficha de otro
   expediente").

**Qué NO preguntar**: "¿les ponemos el lote del título?". El sistema no puede
aplicarlo sin inventar: borraría los lotes que un contrato firmado declara y
crearía uno que ningún documento les asigna.

**Qué haremos según contesten.**

- *Nos dan el número del expediente de ese lote*: se busca en la Plataforma
  por la vía normal y sus líneas salen bajo su propio expediente.
- *Nos confirman que la Plataforma los publica bajo la ficha del principal*:
  se enlaza con el mecanismo que ya existe (`Lote.codigo_expediente_lote`), que
  enlaza solo por certeza estructural, nunca por encontrar el número suelto en
  un texto.
- *No lo saben*: se quedan como están. No se pierde nada: las filas siguen en
  el entregable con el lote que sus documentos les dan, y el material de los
  lotes que les faltan sale en el expediente hermano que sí los declara.

---

## 3 — La numeración de lotes desplazada de `3.22/28510.0009` y `3.21/28510.0096`

**El hecho.** En estos dos expedientes, **el cuadro de precios y la
adjudicación no numeran los lotes igual**, y no hay ningún documento que diga
cuál de las dos numeraciones manda.

`3.22/28510.0009` — **contestada por el propio documento (sesión 2026-09-21,
tercera parte), ya no hace falta preguntarla.** El cuadro rotula cada tabla
con su lote ("LOTE 2 - EQUIPOS PARA REPARACIÓN DE REGLAS…", "LOTE 3 - EQUIPOS
Y HERRAMIENTAS…", ANEJO p.7) y con esos rótulos el lote 2 suma 71.000,00 € y
el lote 3 21.500,00 €, exactamente los presupuestos de sus contratos. La
discrepancia era nuestra: el lote de cada tabla salía de la franja de texto de
encima ("El presupuesto base del lote 1 es de…"), no del rótulo de la propia
tabla. Desde esa sesión el rótulo de la tabla manda y los dos lotes cuadran al
céntimo.

`3.21/28510.0096` — lotes registrados **1** (22.200,00 €) y **2**
(8.250,00 €). Su `ANEJO_1` p.6 imprime **dos** cuadros y **rotula los dos
"LOTE 1"**: el primero (cuatro artículos de repuestos de reglas de medida)
suma 22.200,00 € exactos, que es el presupuesto del lote 1; el segundo (una
llave dinamométrica, 15 × 550,00 €) suma 8.250,00 €, que es el presupuesto del
**lote 2**. El documento llama "LOTE 1" a los dos.

**Por qué no lo tocamos.** El sistema tiene una garantía aritmética para estos
cuadros: las líneas de un bloque de lote solo entran si la suma de
cantidad × precio unitario cuadra con el presupuesto publicado **de ese lote**.
Aquí esa cuenta dice, en negro sobre blanco, que la etiqueta del cuadro y el
número del contrato no son la misma cosa. Cambiar la etiqueta por la que
cuadra sería decidir por ADIF cuál de sus dos documentos está mal.

**Qué preguntar.** ¿Cuál de las dos numeraciones es la buena: la del cuadro de
precios del anejo, o la del contrato y la adjudicación? En `3.21/28510.0096`,
¿el segundo cuadro rotulado "LOTE 1" es en realidad el del lote 2?

**Qué haremos según contesten.**

- *Manda el contrato*: se reasignan esas líneas al lote que dice el contrato,
  y la garantía aritmética pasa a comprobarse contra ese presupuesto. En
  `3.21/28510.0096` entrarían las líneas del segundo cuadro (hoy, sus 4 líneas
  son solo las del primero).
- *Manda el cuadro*: entonces faltan lotes por registrar en esos dos
  expedientes, y hace falta que nos digan sus números.
- *No lo saben*: se quedan como están, contados y explicados.

---

## 4 — El código de las traviesas

**El hecho.** La columna "Código del material" sale, cuando el cuadro la trae,
de la columna de tipo de pieza del propio documento (decisión del cliente de la
sesión 2026-09-14: "REPUESTO": Semicambio, Aguja, Cruzamiento...). En las
traviesas hay dos formas de rellenarla y hoy conviven:

- **1.963 líneas** con `TRAVIESA`, derivado del sustantivo principal de la
  descripción.
- **2 líneas** con `SURFV`, que es el literal de la columna de tipo de su
  propio cuadro (las traviesas sintéticas; en el corpus aparecen también las
  siglas `PRBA` y `PRFV`, hoy sin líneas propias).

**La pregunta.** Para las traviesas sintéticas, ¿el "Código del material" debe
ser la sigla que imprime su cuadro (`SURFV`, `PRBA`, `PRFV`) o la palabra
`TRAVIESA`, como el resto?

**Por qué importa.** Es la columna por la que se agrupa el mismo material entre
expedientes distintos. Con las siglas, una traviesa sintética y una de hormigón
no se agrupan juntas; con `TRAVIESA`, se pierde la distinción de tipo que el
documento sí publica.

**Qué haremos según contesten.**

- *La sigla*: el literal de la columna de tipo ya manda sobre la derivación
  (es el comportamiento implementado), así que no hay nada que cambiar más allá
  de comprobar que todas las traviesas sintéticas traen esa columna.
- *`TRAVIESA` siempre*: se saca esa familia de siglas del literal y se deja la
  derivación por sustantivo. Afecta a 2 líneas hoy, y a las que aparezcan.

---

## 5 — La lista de códigos internos de almacenes y las palabras para excluir por título

**El hecho.** El sistema tiene montadas, desde la sesión 2026-09-09, **dos
listas de exclusión** que hoy están vacías porque el cliente no las ha
entregado. Las dos esconden expedientes de `/catalogo` y del Excel entregado,
**nunca de la base de datos** ni de las pantallas de gestión y revisión.

| Lista | Variable | Formato |
|---|---|---|
| Expedientes | `EXCLUSION_EXPEDIENTES_PATH` | Texto plano, una entrada por línea: código exacto (`6.24/28510.0088`), departamento completo (`28520`) o código interno (`INTERNO:24038`). `#` para comentarios |
| Palabras del título | `EXCLUSION_PALABRAS_TITULO_PATH` | Texto plano, una palabra o frase por línea; excluye por coincidencia de subcadena en el título, sin acentos ni mayúsculas |

**Lo que sí sabemos.** Hay **196 códigos internos distintos** repartidos en
**321 expedientes** cruzados. Es el número por el que almacenes agrupa, y el
propio listado de ADIF asigna uno por familia de expedientes.

**Qué preguntar.**

1. ¿Cuáles de esos 196 códigos internos son de su equipo y cuáles no? Lo que
   nos den entra tal cual como `INTERNO:NNNNN`, sin tocar código.
2. ¿Qué palabras del título marcan un contrato que no es material
   (arrendamientos, gestión de residuos, limpieza...)? Una por línea.

**Qué haremos según contesten.** Se deja el fichero en `Ejemplo/Input`, se
apunta la variable y se recrean los contenedores: no hay despliegue de código
ni migración. La medición del efecto (cuántas filas y expedientes desaparecen
del entregable) se hace en el momento, antes de entregar.

---

## 6 — Qué ficheros de entrada podemos seguir usando

**El hecho.** El sistema lee hoy **cinco** ficheros de `Ejemplo/Input`. Su
procedencia está medida y escrita, columna a columna, en
`docs/preguntas-cliente-lotes-del-titulo-y-ficheros-de-entrada.md`, apartado 2.
**Cuatro son volcados de SAP y uno es de otro sistema de ADIF**; ninguno es de
origen desconocido.

| Fichero | Origen | Para qué se usa |
|---|---|---|
| `Códigos de proyecto.xlsx` | Otro sistema de ADIF | "Código interno" y "Código matriz" del Excel |
| `EXPEDIENTES_EJECUCION_SAP 1.XLSX` | SAP | "Estado del contrato (SAP)"; **da de alta** expedientes |
| `estados_expedientes_28510_20260918.xlsx` | SAP, autorizado expresamente | "Estado según ADIF" |
| `LISTADO_MATERIALES_UNIDAD_,MEDIDA.xlsx` | SAP | Completa la unidad de medida por matrícula |
| `contratos traviesas.XLSX` | SAP | Cargado y deliberadamente sin explotar |

**Por qué se pregunta.** En su día se nos indicó **no utilizar volcados de
SAP**. Para el listado de estados del 18/09/2026 se preguntó expresamente en el
grupo y nos autorizaron. Los otros tres volcados de SAP llegaron antes de esa
conversación y **no tienen una autorización escrita equivalente**.

**Qué preguntar.**

1. ¿Podemos seguir usando los cuatro volcados de SAP, con la misma
   autorización que dieron para el listado de estados?
2. **Los dos volcados de SAP se solapan pero no coinciden**: 212 códigos en
   común, 155 solo en el de 2026-09-07, 146 solo en el de 2026-09-18; en los
   212 comunes el estado coincide en los 212. ¿El segundo sustituye al
   primero, o son dos consultas distintas que hay que mantener las dos?
3. **Los 358 códigos del listado de estados coinciden exactamente con los
   nuestros** (`md5` de las dos listas ordenadas, `016a98f7…`). Conviene
   confirmar que **ese fichero no se generó a partir de nuestro catálogo**
   antes de presentar el "0 discrepancias" como prueba de cobertura.

**Qué haremos según contesten.**

- *Podemos usarlos*: nada. Queda escrita la autorización, que es lo que falta.
- *No podemos usar alguno*: se quita su variable de entorno y se mide qué
  columnas del entregable quedan vacías. `Códigos de proyecto.xlsx` no es SAP y
  no se ve afectado.
- *El segundo sustituye al primero*: se deja de cargar el de 2026-09-07 y la
  columna "Estado del contrato (SAP)" queda vacía en los 155 que solo estaban
  ahí — hay que avisarlo antes de hacerlo.

---

## 7 — Los tres ficheros que esperamos

Los tres están **montados, probados y documentados**; lo único que falta es el
fichero. `docs/entradas-pendientes-del-cliente.md` dice, para cada uno, qué
forma espera el sistema, qué hace si llega con otra, y el comando exacto para
meterlo.

| Fichero | Qué se hará con él |
|---|---|
| `EXPEDIENTES_VIGENTES_CON_REMANENTE.xlsx` (83 contratos) | Para cada uno, su Situación en la Conciliación; los que no estén, se buscan en la Plataforma |
| El listado de estados **con presupuesto de licitación** | Hoja nueva del Excel comparando su presupuesto con el importe que leemos de los documentos: coincidencias, diferencias de mayor a menor y expedientes sin importe |
| El catálogo antiguo de ADIF | Informe **aparte**: materiales solo suyos, solo nuestros, y diferencias de precio |

**Qué preguntar.**

1. ¿Nos pueden mandar la lista de los 83 vigentes con remanente? Vale
   cualquier formato de Excel: basta con que traiga una columna de códigos de
   expediente.
2. ¿Pueden añadir la columna de presupuesto de licitación al listado de
   estados que ya nos mandan? Con eso se puede contrastar expediente a
   expediente lo que dice su SAP contra lo que publica la Plataforma.
3. ¿Nos pueden mandar el catálogo antiguo de materiales, en el formato que
   sea? El cruce está preparado para leerlo sin saber su forma de antemano.

---

## 8 — Las 946 huérfanas de las causas C y D

**El hecho.** De las líneas que no llegan al entregable por no saberse de qué
lote son, quedan 946 en dos causas que no se pueden cerrar desde aquí. **712
están en `6.21/28510.0112` y `6.21/28510.0113`**, cuyo cuadro de precios llega
en glifos CID sin tabla de caracteres: el PDF no dice qué letra es cada
símbolo, así que ni el texto ni las cifras se pueden leer con certeza. Esos dos
expedientes suman hoy 1.654 y 1.593 líneas en la base de datos.

**Qué preguntar.** ¿Pueden facilitar esos dos documentos en un formato con
texto legible (el original de ofimática, o una exportación con fuentes
incrustadas)? Es lo único que los resuelve sin revisión manual página a página.

**Qué haremos según contesten.**

- *Nos dan el documento legible*: entra por la ingesta manual
  (`INGESTA_LOCAL_PATH`), que ya existe, y se reprocesa el expediente.
- *No*: se quedan como están, contadas y explicadas en el Resumen del Excel.
  No se inventa un lote ni un precio a partir de glifos sin descodificar.

---

## 9 — `6.26/28510.0064` lote 3 `P-2`

**El hecho.** Es **la única línea del catálogo sin precio**. El material ("T de
balasto transportado a punto de carga ofertado", 27.000 t) aparece con precio
en los lotes 1, 2, 4, 5 y 6 del mismo expediente (13,50 / 28,80 / 16,20 /
33,30 / 21,60 €) y **solo en el lote 3** su celda llega en glifos sin
descodificar. El sistema ya intenta resolverla con el mismo código de precio de
otro lote del mismo documento, y aquí no puede: cada lote tiene un precio
distinto, así que copiar el de otro sería inventarlo.

**Qué preguntar.** ¿Cuál es el precio unitario del lote 3 de ese expediente?

**Qué haremos según contesten.** Se corrige a mano por la cola de revisión, que
tiene esa salida desde el principio ("corregir el dato a mano"), y la línea
queda marcada como corregida por un humano. Si no contestan, se queda vacía con
su motivo: es una línea de 19.997.

---

## 10 — "Comentarios": fila a fila o nota única

**El hecho.** La columna "Comentarios" es la última del Excel y está pensada
para que la rellene una persona. Hoy sale vacía siempre. La información de por
qué una celda está vacía va en "Motivo de las celdas vacías", y la de por qué
una línea quedó fuera va en la hoja "Resumen".

**Qué preguntar.** ¿"Comentarios" debe traer el motivo de revisión de cada
fila, o quedarse vacía para que ellos escriban, con la explicación general en
el Resumen?

**Qué haremos según contesten.**

- *Fila a fila*: se vuelca `motivo_revision` en esa columna. Son textos largos;
  el Excel gana ancho y pierde legibilidad.
- *Vacía*: nada, es el comportamiento de hoy.

---

## 11 — `Precio unitario`: ¿licitado o adjudicado?

**El hecho.** La columna 9 del Excel, "Precio unitario", es **el precio
licitado**: el que imprime el cuadro de precios del pliego. El precio
adjudicado va en su propia columna, derivado (`precio licitado × (1 − baja del
lote)`), junto a la baja que lo produce. Esto **nunca lo confirmó el cliente**:
fue una decisión de sesión, y está anotado como pendiente en CONTEXTO.md
sección 16 desde entonces.

**Qué preguntar.** ¿"Precio unitario" tiene que seguir siendo el licitado, con
el adjudicado en su columna aparte, o al revés?

**Qué haremos según contesten.**

- *Licitado*: nada. Es lo que hace hoy, y las tres columnas (licitado,
  adjudicado, baja) permiten reconstruir la otra.
- *Adjudicado*: se intercambian los contenidos de las dos columnas sin cambiar
  sus nombres ni su orden. Afecta a las 9.116 filas que tienen precio
  adjudicado; las demás quedarían sin precio, porque su lote no tiene baja
  conocida — eso hay que decírselo antes de hacerlo.

---

## 12 — `transporte` como unidad de medida

**El hecho.** 15 líneas del entregable (`6.21/28510.0108`-`0112`, tres
conceptos repetidos entre cinco expedientes hermanos) llevan `transporte` en la
columna "Unidad de medida". No es un valor colado de otra columna: el cuadro de
precios escribe **`€/transporte`** en su columna de precio, exactamente igual
que escribe `€/Ton*km` en las filas que sí se pagan por tonelada-kilómetro.
Es el denominador del precio: lo que cuesta cada transporte.

Las tres líneas son "Importe mínimo de un transporte por ferrocarril"
(10.000,00 €), "Transporte por camión especial hasta 300 Km de distancia"
(1.900,00 €) y "… a una distancia mayor a 300 Km" (6.400,00 €).

**Qué preguntar.** ¿`transporte` se queda como unidad, o prefieren otra cosa?

**Qué haremos según contesten.**

- *Se queda*: nada. Es el comportamiento de hoy y lo que imprime el documento.
- *`viaje`*: se unifica a esa palabra, un cambio de vocabulario de una línea.
  El literal seguiría en `unidad_medida_original`.
- *Vacía con su motivo*: se pierde un dato que el documento sí publica, y las
  15 filas quedarían con la unidad en blanco.
- **No es `t·km`**, y eso conviene decírselo: `t·km` es la unidad de las OTRAS
  filas del mismo cuadro. Poner `t·km` aquí diría que 1.900,00 € es el precio
  de un camión **por tonelada y kilómetro**, cuando es el precio del viaje
  entero.

---

## 13 — Qué es la unidad `P` del maestro de materiales

**El hecho.** Tres líneas del entregable (`6.20/28510.0042`/`0046`/`0047`,
matrícula `612860020`, "PLACA NERVADA PN-60- 1:20") tienen `P` en la columna
"Unidad de medida". **Ese valor no sale de ningún documento**: el cuadro de
precios de esas filas no tiene columna de unidad (`MATRÍCULA | DESIGNACIÓN |
PLANO | ET | PRECIO`, comprobado contra la imagen). Llega del maestro de
materiales que ADIF nos envió, donde la "UM base" de esa matrícula es `P`.

**16 materiales del maestro usan `P`**, y el fichero no trae en ninguna parte
el nombre completo de ese código.

**Qué preguntar.** ¿Qué unidad es `P` en SAP?

**Qué haremos según contesten.**

- *Nos dan el nombre*: entra en el vocabulario de unidades con su forma única,
  como `ud` o `t`, y las tres celdas pasan a mostrarla.
- *No lo saben / no importa*: se queda el código tal cual, que es lo que ADIF
  tiene registrado. Nunca se traduce por analogía.

---

## 14 — Las matrículas que el maestro no recoge

**El hecho.** **2.893 líneas del entregable** llevan una matrícula que el
documento publica y el maestro de materiales de ADIF no recoge: **382** con el
formato antiguo de 8 cifras y **2.511** de 9 cifras. Están comprobadas contra
la imagen de los PDF —no son errores de lectura— y se entregan literales, cada
una con su motivo.

Las **2.893** lo llevan. Once se quedaban sin él por dónde se calculaba el
motivo (líneas heredadas de un acuerdo marco y filas cuya matrícula guardada
no era la de la última pasada); está corregido y comprobado en el cierre de
la sesión.

El maestro está **incompleto artículo a artículo**, no por familias: de las
1.133 matrículas de 9 cifras que faltan, solo 12 no tienen ninguna compañera en
el maestro con sus cuatro primeras cifras, y un pliego llega a comprar 28
referencias correlativas de las que el maestro trae 5. Medición completa en
`docs/matriculas-8-digitos-y-el-maestro.md` y
`docs/matriculas-de-9-digitos-fuera-del-maestro.md`.

**Qué preguntar.** ¿Pueden enviarnos un maestro completo, o al menos decirnos
de qué fecha y de qué transacción sale el que tenemos? Y: ¿existe una tabla de
equivalencia entre el formato de 8 cifras y el de 9?

**Qué haremos según contesten.**

- *Maestro nuevo*: se recarga por el endpoint de siempre y el motivo
  desaparece solo de las filas que ya figuren. Nada que programar.
- *Tabla de equivalencia*: se aplica **por clave exacta**, nunca por parecido.
  Lo que este sistema no hará en ningún caso es deducirla: `64571017` casa por
  sufijo con `645710170` (una palomilla) y con `645710175` (unas antenas), y
  en `6.17/28510.0023` conviven `66441037` y `664410373` con descripción
  idéntica, dos fabricantes y dos precios.
- *No hay nada más*: las filas se quedan como están, con su motivo, que ya
  explica el caso a quien abra el Excel.

---

## 15 — Las tres erratas de matrícula del propio documento

**El hecho.** Tres matrículas que el pliego imprime mal, comprobadas contra su
imagen. No son fallos de lectura y el sistema no las toca.

| Expediente(s) | Lo que imprime | Lo que parece que quiso decir | Por qué |
|---|---|---|---|
| `6.20/28510.0042`/`0046`/`0047` p.12 | `61286119` (8 cifras) | `612860119` | Toda su columna es de 9 cifras y la designación es "PLACA NERVADA ESPECIAL PNE-60-119" |
| `6.18/28510.0003` y `6.20/28510.0040` p.11 | `642190440` | `642910440` | Las otras siete filas del cuadro son `6429104xx`, y el maestro trae `642910440` con la misma pieza |
| `6.22/28510.0094` y `6.22/28510.0126` p.24, `P-138` | `6110500075` (**10 cifras**) | `611050075` | Las filas siguientes son `611050076`, `611050077`, `611050078`. Hoy el sistema se queda con las nueve primeras (`611050007`) y lo marca; ninguno de los dos números está en el maestro, así que no se ha creado ningún cruce falso |

**Qué preguntar.** ¿Confirman que son erratas del pliego y cuál es la matrícula
buena de cada una?

**Qué haremos según contesten.** Se corrigen **una a una, por confirmación
suya**, nunca por la inferencia de arriba. Si no lo confirman, se quedan
literales: el catálogo entrega lo que publica el documento.

---

## 16 — La Cantidad de los cuadros con «cantidad mínima por pedido» y «pedido inicial»

**El hecho.** Hay cuadros de precios que no publican la cantidad que se va a
comprar. Traen dos columnas: la **cantidad mínima a suministrar por pedido** y
el **pedido inicial** (la familia de las grifas, los aisladores, los
detectores, la regulación de tensión…). Ninguna de las dos es la cantidad
total del contrato; el presupuesto es un techo de gasto.

La columna **Cantidad** del Excel trae una de las dos, la que el sistema tomó
por cantidad al leer la tabla. **Casi siempre es la mínima por pedido, pero no
siempre**, y a veces cambia dentro del mismo cuadro: en las grifas
(`6.19/28510.0135`, `0175`, `0177`), la página con la cabecera da la mínima y
las páginas siguientes, escaneadas, el pedido inicial.

Desde el 21/09/2026, **cada una de esas filas dice cuál de las dos es y qué
trae la otra**, en la columna "Motivo de las celdas vacías": *"Cantidad: es la
columna «CANTIDAD MÍNIMA A SUMINISTRAR POR PEDIDO» del cuadro, no la cantidad
total a comprar; su columna «PEDIDO INICIAL» trae 200 en esta fila"*. La
Cantidad no se ha cambiado.

**Afectado.** **451 filas de "Materiales" en 22 expedientes** (Excel del
21/09/2026): en 406 la Cantidad es la mínima por pedido y en 45 el pedido
inicial. Casi todos son de 2019 (`6.19/28510.0115`, `0126`, `0134`, `0135`,
`0136`, `0157`-`0163`, `0166`, `0167`, `0175`, `0177`, `0181`, `0195`,
`0202`, `0215`, `0231`) más `6.20/28510.0025` y `0028`. Siete filas de
`6.19/28510.0177` (p.22) todavía no llevan la nota: su tabla empieza en una
fila con dos matrículas pegadas en la misma celda, que el sistema toma por una
cabecera nueva. Queda anotado para corregirlo (hace falta un reproceso).

**Qué preguntar.** ¿Qué quieren ver en la columna Cantidad de estos cuadros:
la mínima por pedido, el pedido inicial, o ninguna de las dos (celda vacía con
su motivo, porque ninguna es la cantidad total)?

**Qué haremos según contesten.** Es un cambio de una regla y un reproceso: la
columna elegida se toma siempre, en todas las páginas del cuadro, y la otra
sigue diciéndose en el motivo. Si prefieren la celda vacía, las dos cifras van
al motivo.

