# Preguntas pendientes para el cliente

Bloque 4 del encargo de la sesión 2026-09-19 (sexta parte): **todas** las
preguntas abiertas, reunidas en un solo documento, cada una con su contexto,
los expedientes y filas afectados, y qué haremos según lo que contesten.

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
| 3 | La numeración de lotes desplazada de `3.22/28510.0009` y `3.21/28510.0096` | Lote y precios | 2 expedientes |
| 4 | El código de las traviesas | Código del material | 1.963 líneas |
| 5 | La lista de códigos internos de almacenes y las palabras para excluir por título | Qué sale en el entregable | Sin medir hasta tenerla |
| 6 | Qué ficheros de entrada podemos seguir usando | Todas las columnas de cruce | 5 ficheros |
| 7 | Los tres ficheros que esperamos | Tres cruces nuevos | 83 contratos + 358 expedientes + su catálogo |
| 8 | Las 946 huérfanas de las causas C y D | Filas que no llegan al entregable | 946 líneas |
| 9 | `6.26/28510.0064` lote 3 `P-2` | Precio | 1 línea |
| 10 | "Comentarios": fila a fila o nota única | Una columna del Excel | Todo el Excel |
| 11 | `Precio unitario`: ¿licitado o adjudicado? | La columna 9 del Excel | Todo el Excel |

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

`3.22/28510.0009` — lotes registrados **2** (71.000,00 €) y **3**
(21.500,00 €), los que declaran sus contratos. Su cuadro de precios está
partido en bloques rotulados "LOTE 1", "LOTE 2"... y la suma de cada bloque no
cuadra con el presupuesto del lote del mismo número. 15 líneas, 8 de ellas sin
lote.

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
