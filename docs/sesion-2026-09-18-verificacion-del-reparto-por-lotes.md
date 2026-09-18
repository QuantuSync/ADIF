# Sesión 2026-09-18 (sexta parte) — Verificar el reparto por lotes, y los avisos viejos de la auditoría

Nueve bloques. Continúa `docs/sesion-2026-09-18-reproceso-glifos-y-conciliacion.md`.
El bloque 1 era condición para todo lo demás: **cuadra, y no se ha revertido nada**.

---

## 1 — La demostración aritmética del reparto por lotes

### Qué se ha comprobado, y contra qué

Para cada uno de los **14 expedientes** en los que entró el reparto por lotes
del propio cuadro (`_lotes_candidatos_del_cuadro`) y para cada uno de sus
lotes: **suma de cantidad × precio unitario de las filas atribuidas a ese
lote**, contra el **presupuesto de licitación que el anuncio declara para ese
lote**. Las sumas salen de las filas que de verdad están en la hoja
"Materiales" del Excel entregado, no de la base de datos en bruto.

**70 tablas de lote** en total (5 expedientes × 6 lotes + 5 × 6 + 2 + 2 + 2 + 4).

| Resultado | Tablas de lote |
|---|---:|
| Cuadra **al céntimo** | **54** |
| Cuadra con diferencia menor del 0,002 % | 6 |
| No cuadra: discrepancia **dentro del propio documento de ADIF** | 5 |
| No cuadra: **un dígito mal leído por reconocimiento óptico**, demostrado | 1 |
| No se puede cerrar: el documento no publica cantidad para todas sus filas | 4 |

Que 54 de 70 sumas caigan **exactamente** sobre el presupuesto publicado del
lote, al céntimo, es la prueba: una atribución equivocada no produce eso ni
por casualidad.

### Lote a lote

**`6.20/28510.0054`, `0055`, `0056`, `0057`, `0058`** (traviesas monobloque, 6
lotes cada uno; los cinco publican el mismo `ANEJO_8.pdf` con los seis cuadros).
Presupuesto por lote declarado en `ANEJO_1.pdf` p.4 y `ANEJO_2.pdf` p.4, y
repetido en los dos Contratos (p.103) — las tres fuentes coinciden:

| Lote | Suma cantidad × precio | Presupuesto declarado | Diferencia |
|---|---:|---:|---:|
| 1 — Á.T. Centro | 7.200.000,00 € | 7.200.000,00 € | **0,00 €** |
| 2 — Á.T. Noroeste | 7.400.000,00 € | 7.400.000,00 € | **0,00 €** |
| 3 — Á.T. Norte | 8.230.002,13 € | 8.200.000,00 € | +30.002,13 € (+0,366 %) |
| 4 — Á.T. Noreste | 7.200.001,60 € | 7.200.000,00 € | +1,60 € (+0,00002 %) |
| 5 — Á.T. Este | 5.400.000,00 € | 5.400.000,00 € | **0,00 €** |
| 6 — Á.T. Sur | 6.600.000,00 € | 6.600.000,00 € | **0,00 €** |
| **Total** | **42.030.003,73 €** | **42.000.000,00 €** | +30.003,73 € |

Y una segunda prueba independiente del mismo cuadro: la **partida alzada a
justificar para imprevistos** de cada lote es **exactamente el 3,0000 % del
presupuesto de ese lote** en los seis (215.999,16 / 7.200.000; 221.999,85 /
7.400.000; 245.999,90 / 8.200.000; 215.999,16 / 7.200.000; 161.999,04 /
5.400.000; 197.999,69 / 6.600.000). Cada partida alzada cayó en su lote.

**Las dos diferencias son del documento, no de la lectura.** Se comprobó fila
a fila contra el texto de `ANEJO_8.pdf`: las cantidades raras (2408, 2392,
1999, 2001, 2250, 2501, 2502, 2504…) **están así en el PDF**, y son el ajuste
con el que ADIF hace que cada cuadro caiga sobre su presupuesto. En el lote 4
ese ajuste se quedó a 1,60 €; en el lote 3, sus filas de material suman
30.002,23 € más del 97 % que le tocaría, y su partida alzada es aun así el 3 %
exacto: **el cuadro del lote 3 se pasa de su propio presupuesto en el
documento original**. No hay nada que revertir, hay algo que contar al cliente.

**`6.21/28510.0141`, `6.22/28510.0011`, `0012`, `0013`, `0014`** (balasto, 6
lotes; presupuesto por lote en `ANEJO_1.pdf` p.6, confirmado lote a lote por
los dos Contratos):

| Lote | Suma cantidad × precio | Presupuesto declarado | Diferencia |
|---|---:|---:|---:|
| 1 — Jefatura de Barcelona | 1.231.500,00 € | 1.231.500,00 € | **0,00 €** |
| 2 — Jefatura de Córdoba | 2.739.900,00 € | 2.739.900,00 € | **0,00 €** |
| 3 — Jefatura de Burgos | 1.673.700,00 € | 1.673.700,00 € | **0,00 €** |
| 4 — Jefatura de Irún | 2.377.700,00 € | 2.377.700,00 € | **0,00 €** |
| 5 — Jefatura de Valladolid | 1.911.000,00 € | 1.911.000,00 € | **0,00 €** |
| 6 — RAM Norte | 2.062.500,00 € | 2.062.500,00 € | **0,00 €** |

**Seis de seis, al céntimo, en los cinco expedientes.**

**`6.23/28510.0139`** (balasto, 2 lotes; `ANEJO_1.pdf` p.6 y los dos Contratos):

| Lote | Suma | Declarado | Diferencia |
|---|---:|---:|---:|
| 1 — Base de La Gineta | 590.256,00 € | 590.256,00 € | **0,00 €** |
| 2 — Base de Almussafes | 1.291.698,00 € | 1.291.698,00 € | **0,00 €** |

**`6.25/28510.0097`** (poleas, 4 lotes; `ANEJO_1.pdf` p.5 y `ANEJO_2.pdf` p.3):

| Lote | Suma material | Partida alzada del lote | Total | Declarado | Diferencia |
|---|---:|---:|---:|---:|---:|
| 1 | 180.000,00 € | 20.000,00 € | 200.000,00 € | 200.000,00 € | **0,00 €** |
| 2 | 33.232,50 € | 15.000,00 € | — | 150.000,00 € | *no cierra* |
| 3 | 23.757,30 € | 10.000,00 € | — | 100.000,00 € | *no cierra* |
| 4 | 180.005,00 € | 19.995,00 € | 200.000,00 € | 200.000,00 € | **0,00 €** |

Los lotes 2 y 3 no cierran porque **el documento no publica cantidad para 12 y
20 de sus filas** (los conjuntos de contrapesos marcados "(\*)"), no porque la
atribución falle. Y la prueba independiente vuelve a cerrar sola: la partida
alzada de cada lote es **exactamente el 10 % del presupuesto de ese lote** en
los cuatro (20.000 / 200.000, 15.000 / 150.000, 10.000 / 100.000, 19.995 /
200.000). Los cuatro `P-60` cayeron en su lote.

**`6.22/28510.0094`** (aparatos genéricos de vía, 2 lotes). Su `ANEJO_1.pdf` es
literalmente "ANEJO Nº1: PRECIOS UNITARIOS — *los cuadros de precios unitarios
de cada uno de los lotes*", con "Lote 1. NORTE…" en la p.15 y "Lote 2. SUR…"
en la p.21: **dos cuadros distintos, uno por lote**, con precios que no son
idénticos (`P-002` vale 122.624,14 € en el lote 1 y 107.297,32 € en el lote 2).

| Lote | Suma | Declarado (`ANEJO_1.pdf` p.5 y los dos Contratos) | Diferencia |
|---|---:|---:|---:|
| 1 — NORTE | 5.899.901,11 € | 5.900.000,00 € | −98,89 € (−0,0017 %) |
| 2 — SUR | 4.654.054,81 € | 5.900.000,00 € | *no cierra* |

Los −98,89 € del lote 1 tienen nombre y apellidos: son **los 98,88 € de
diferencia en el precio de `P-002`**, que el anejo de criterios técnicos
(`ANEJO_3.pdf`, sin columna de cantidad) sobrescribe sobre el del cuadro real.
El lote 2 no cierra porque **128 de sus 165 filas entregadas no traen cantidad
en el documento** (su columna dice "0" o está vacía).

**`6.17/28510.0056`** (aparatos de vía, 2 lotes). Aquí el propio documento
titula las dos tablas **"10.1. Presupuesto lote 1"** y **"10.2. Presupuesto
lote 2"**: la atribución la dice el documento con todas las letras.

| Lote | Suma | Presupuesto de Ejecución Material del propio documento | Diferencia |
|---|---:|---:|---:|
| 1 | 2.976.473,96 € | 2.975.673,96 € | +800,00 € |
| 2 | *no cierra* (el reconocimiento óptico perdió la columna "UD") | 2.375.604,06 € | — |

Los **+800,00 € del lote 1 son un dígito mal leído**, y el propio documento lo
demuestra: la fila `P-7` (encarriladora de vía) trae precio `56.555,91 €` y un
IMPORTE de `451.647,28 €` para 8 unidades — y 451.647,28 / 8 = **56.455,91**.
El reconocimiento óptico leyó un `5` donde el PDF pone un `4`. Con esa cifra,
el lote 1 suma **2.975.673,96 €, exactamente el Presupuesto de Ejecución
Material que el documento declara**, y ×1,15 (9 % de gastos generales + 6 % de
beneficio industrial) da **3.422.025,06 €, exactamente el importe sin impuestos
que el anuncio publica para el lote 1**. El lote 2 cierra igual de bien con las
cantidades del documento: 9×88.882,55 + 17×79.379,15 + 3×58.738,52 + 50.000 =
**2.375.604,06 €**, su Presupuesto de Ejecución Material exacto — lo único que
falta es que el reconocimiento óptico recupere esa columna.

**Ese dígito no se ha corregido a mano.** Corregir un precio a partir de la
columna de importes del documento sería un mecanismo nuevo que reescribiría
precios en todo el corpus: queda anotado al final, para decidirlo.

### Duplicación real: qué son de verdad esas filas

Sobre las **1.537 filas** que los 14 expedientes tienen hoy en "Materiales":

| | Filas |
|---|---:|
| Mismo material, **mismo precio**, **distinta cantidad** en cada lote | **1.220** |
| Mismo material, **precio distinto** en cada lote | **68** |
| Mismo material, mismo precio **y misma cantidad** en varios lotes | **102** |
| Material que aparece **una sola vez** | **147** |

Es decir: **1.288 de 1.537 aportan un dato propio de su lote** (su cantidad, su
precio, o los dos). Las **102** que repiten material, precio y cantidad son la
repetición pura — y aun esas dicen algo que antes se perdía: que ese material
también forma parte de ese lote. Ejemplo de las 102: "m³ × km de balasto
transportado a punto de carga diferente al ofertado", 100.000 × 0,12 € en los
seis lotes de `6.21/28510.0141`.

### Reparto de las 1.151 filas nuevas, con una corrección

De las 1.151, **1.133 son del reparto por lotes** (los 14 expedientes) y **18
no**: son las que `6.20/28510.0040` hereda de su acuerdo marco
`6.18/28510.0003` por el mecanismo de siempre. La quinta parte las contaba
juntas.

### Veredicto

**No se revierte ningún expediente.** El reparto cuadra contra el presupuesto
publicado en 54 de 70 lotes al céntimo, y en los 16 restantes la causa está
identificada y no es la atribución: dos discrepancias del propio documento de
ADIF, un dígito de reconocimiento óptico y cuatro tablas a las que el documento
no les pone cantidad.

---

## 2 — Los candidatos al reparto que no entraron

### Cuántos son de verdad

El "91" de la cuarta parte contaba expedientes que cumplen **la primera**
condición (declaran más de un lote y no tienen ninguno identificado por
número). Medido hoy sobre los 613 expedientes, **238 declaran más de un lote**,
y de ellos:

| | Expedientes |
|---|---:|
| Ya tienen sus N lotes numerados (entre ellos los 14 que entraron) | 52 |
| Su único lote no es el sentinela: son ellos mismos un lote concreto | 79 |
| Tienen varios lotes pero no los N | 40 |
| **El lote sentinela ya lleva un dato atribuido (baja o importe)** — el reparto ni se intenta | **38** |
| **Candidatos vivos: se intenta y la comprobación dura lo rechaza** | **29** |

Los **38** se descartan antes de mirar el cuadro, y es la garantía que más
importa: partir en N un lote que ya lleva una baja o un importe convertiría un
dato del conjunto de la licitación en un dato del lote 1 — exactamente el
error de `6.24/28510.0088` que CONTEXTO.md sección 26 describe.

### Los 29 que lo intentan, por causa

Se reprocesó cada uno **en seco** (con los N lotes candidatos, sin escribir
nada) para ver qué produciría su cuadro:

| Causa | Expedientes | Ejemplo |
|---|---:|---|
| **El cuadro sí declara lotes pero deja filas huérfanas** | **16** | `6.19/28510.0052` y 11 hermanos: su cuadro (documento común, 40 lotes) atribuye **164 filas y cubre los 40 lotes**, y solo **4 filas** quedan huérfanas |
| **El cuadro no declara ningún lote**: todas sus filas quedarían huérfanas | **7** | `6.21/28510.0108`-`0111` (196 filas, 0 lotes); `4.23/28510.0058` (4 filas, 0 lotes) |
| **El expediente no aporta ni una línea**: no hay cuadro que repartir | **5** | `6.15/28510.0080` (17 lotes declarados, 0 líneas en todo el corpus) |
| **Cobertura parcial**: el cuadro declara 1 de los 2 lotes y deja 47 huérfanas | **1** | `6.19/28510.0196` (129 líneas, solo el lote 2) |

### Qué pasaría si se relajara la garantía

**No se ha tocado.** Medido: si se aceptara el intento aunque dejara filas
huérfanas (manteniendo la exigencia de cubrir los N lotes), **entrarían 15
expedientes** y el Excel ganaría **~1.971 filas netas**:

| Expedientes | Hoy | Con la garantía relajada |
|---|---:|---:|
| Los 11 de `6.19/28510.00xx` + `6.18/28510.0109` (40 lotes) | 5 filas cada uno | **160 cada uno** (+1.860) |
| `6.22/28510.0173` | 184 | **368** (+184) |
| `6.19/28510.0166` | 30 | **48** (+18) |
| `6.25/28510.0171` | 21 | **21** (=) |
| **`4.25/28510.0132`** | **119** | **28** (**−91**) |

Y ahí está el motivo de que la garantía exista: **uno de los quince pierde 91
filas**. Los que hoy tienen 5 filas las tienen porque, fundidas en un solo
lote, 164 filas con el mismo código colapsan en 5 por clave — así que ganar es
mucho, pero la regla no puede distinguir a priori un caso del otro. Decisión
del cliente.

---

## 3 — Los 15 que no se pudieron enlazar

### Los 15, con su documento y su motivo

Se comprobaron **uno a uno**, ejecutando el extractor de identidad de Contrato
(`app.extraccion.lotes.extraer_identidad_contrato`) sobre los Contratos del
expediente que los menciona:

| Expedientes | Mencionado en | Qué es de verdad | ¿Un Contrato lo declara lote? |
|---|---|---|---|
| `6.16/28510.0088`, `0089`, `0090`, `0091`, `0092`, `0096` | `CONTRATO_1.pdf` de `6.15/28510.0080` | El campo "Número de Contrato" de un anuncio de formalización | **no** |
| `6.17/28510.0020`, `0021` | `CONTRATO_1.pdf` de `6.16/28510.0164` | Ídem | **no** |
| `6.19/28510.0203` | `CONTRATO_1.pdf` de `6.19/28510.0202` | Ídem | **no** |
| `6.20/28510.0013` | `CONTRATO_1.pdf` de `6.19/28510.0184` | Ídem | **no** |
| `6.17/28510.0031` | `CONTRATO_1.pdf` y `ADJUDICACION_1.pdf` de `6.20/28510.0043` | Es la **matriz** de ese pedido, no un lote suyo | **no** |
| `6.26/28510.0002` | `ANEJO_3.pdf` y `ANEJO_4.pdf` de `6.25/28510.0221` | Un anuncio de fechas ("se retoma la licitación") | **no** |
| **`4.23/28510.0081`** | `CONTRATO_1.pdf` de `4.23/28510.0058` | **Sí es un lote** | **sí**: "Contrato nº: 4.23/28510.0081 … LOTE 2" |
| **`6.19/28510.0213`** | `CONTRATO_2.pdf` de `6.19/28510.0196` | **Sí es un lote** | **sí**: "Contrato nº: 6.19/28510.0213 … LOTE 1" |
| **`6.19/28510.0216`** | `CONTRATO_1.pdf` de `6.19/28510.0196` | **Sí es un lote** | **sí**: "Contrato nº: 6.19/28510.0216 … LOTE 2" |

Los doce primeros quedan confirmados de forma independiente: **ninguno de sus
Contratos declara una identidad de lote**, así que no hay nada que forzar.

### Corrección a la quinta parte: el extractor sí reconoce esa redacción

La quinta parte anotó que los tres últimos no se enlazaban porque *"la
redacción no es la que el extractor reconoce"*. **Es falso, y se comprobó
ejecutándolo**: `extraer_identidad_contrato` devuelve los tres, con su número
de lote y su código, sin tocar una sola línea de código.

Lo que los perdía está en otro sitio:
`app.extraccion.orquestador._extraer_lotes` solo abre candidatos con una
**Resolución de Adjudicación, una Propuesta LC.27 o una Propuesta DT**; si el
expediente no trae ninguna de las tres — y `4.23/28510.0058` y
`6.19/28510.0196` no la traen (su "adjudicación" es un Acuerdo del Consejo de
Administración, que cae en `otro`) — devuelve lista vacía **sin mirar las
identidades de los Contratos**, y con ella se tira el hecho leído.

### Por qué el arreglo grande NO es limpio

Hacer que `_extraer_lotes` caiga a las identidades de Contrato cuando no hay
adjudicación **toca 40 expedientes**, y en varios crearía lotes nuevos donde
hoy hay un sentinela con todas sus líneas dentro: `6.21/28510.0111` tiene 221
filas en su lote sentinela y las identidades que sus documentos declaran son
las de sus **hermanos** (`6.21/28510.0112` y `0113`), porque ADIF publica los
Contratos de todos los lotes en la ficha de cada uno. Se midió antes de
escribir nada y **no se ha hecho**.

### Lo que sí se ha hecho: que la hoja diga la verdad, sin crear ningún lote

Migración **0038**: `documentos.identidad_lote_codigo` y
`documentos.identidad_lote_identificador` guardan, en el propio documento, lo
que un Contrato firmado declara de sí mismo ("Contrato nº: X … LOTE N").
`_clasificar_documentos` lo calcula una sola vez y lo persiste — y de paso
`_identidades_de_contratos` y el bucle de identidades del orquestador lo
reutilizan, en vez de recorrer el documento entero tres veces por expediente.

`app.conciliacion._lotes_en_ficha_de_otro` usa ese dato como **segunda
fuente**, detrás de `Lote.codigo_expediente_lote` y nunca por delante. Efecto:
los tres expedientes pasan de no salir en la hoja a salir con la situación
**"Publicado dentro de la ficha de otro expediente"** y su motivo real. **No se
crea ningún lote, no se mueve ninguna línea, no cambia ningún precio.**

---

## 4 — El reproceso "sin red" tocaba la red por dos sitios, no por uno

La quinta parte midió que un reproceso con `sindicacion_desactivada` y
`busqueda_desactivada` hacía **cuatro peticiones** a la Plataforma y las
atribuyó todas al reintento de los `sin_publicar`. **Eran dos mecanismos
distintos**, y se vio al relanzar el reproceso de esta sesión:

| Expedientes | Vía | Por qué |
|---|---|---|
| `2.25/28520.0161`, `3.25/27520.0055` | `_reintentar_sin_publicar` | `sin_publicar` cuyo plazo venció |
| `6.14/28510.0177`, `6.14/28510.0148` | **el bucle de frescura de siempre** | constan publicados pero su ficha **no publica ni un documento descargable**, así que `debe_descargar` los devuelve en cada ciclo — y su "descarga" es literalmente una búsqueda por su número |

Las dos vías están cerradas con la misma bandera (`app.mantenimiento.ciclo`):
`busqueda_desactivada` apaga ahora **las cuatro vías de red del ciclo** —
sindicación, barrido del buscador, reintento de `sin_publicar` y descarga del
bucle de frescura. Deliberadamente **solo la bandera del payload**, nunca
`BUSQUEDA_DESCUBRIMIENTO_ACTIVO`: esa configura si se barre el buscador
buscando expedientes nuevos, que es otra decisión — apagarla no debe dejar de
reintentar los `sin_publicar` que ya se conocen.

**Las cuatro pruebas nuevas revientan si alguien llega a la red.** El doble no
se pone en "¿se encoló el trabajo?" sino en `app.scraping.job.scrape_expediente`,
el único punto por el que se abre el navegador contra la Plataforma: si mañana
apareciera una quinta vía, el test la cazaría igual. Y las dos mitades: sin la
bandera, el mismo montaje **sí** llega a ese punto.

---

## 5 — Las 19.233 huérfanas sin lote: la anatomía

### Lo primero: **ninguna está en un expediente de un solo lote**

Las 19.233 están en **108 expedientes, todos multilote**. No hay ni una sola
huérfana en un expediente de lote único: ahí no hay nada que decidir.

### Por causa

| Causa | Líneas | Combinaciones distintas | Expedientes |
|---|---:|---:|---:|
| **A. Anejo de criterios técnicos**, que el documento declara del conjunto de los lotes | **13.432** | 7.094 | 43 |
| **B. La tabla declara un LOTE N que este expediente no declara** (es el cuadro de un hermano) | **2.438** | 1.356 | 65 |
| **C. La franja anterior a la tabla no nombra ningún lote** | **1.814** | 656 | 24 |
| **D. Banda vacía: posible continuación de tabla partida entre páginas** | **938** | 602 | 7 |
| **F. Otros** (columna fantasma, descripción recuperada, tabla de otro lote cuyo expediente no está…) | **611** | 541 | — |

**A y B, que son 15.870 de las 19.233 (82,5 %), no deben tener lote**: el
anejo de criterios es del conjunto de los lotes y lo dice él mismo
(CONTEXTO.md sección 7), y las tablas de la causa B son el cuadro de otro lote
de la licitación, que ya sale con su lote en el expediente de ese otro lote.

### Y una cifra que cambia la lectura del aviso

Las 19.233 líneas son **8.804 combinaciones distintas** de expediente + código
+ descripción + precio. El resto es **el mismo cuadro leído dos o tres veces**,
porque un Contrato firmado incluye el pliego entero: `6.21/28510.0112` tiene
las mismas 196 filas de criterios técnicos en `ANEJO_3.pdf`, `CONTRATO_1.pdf`
y `CONTRATO_2.pdf`.

Más aún: **6.229 de las 19.233 son copia exacta** (mismo expediente, código,
descripción y precio) de una fila que **ya está en "Materiales" con su lote**.
No falta ese material en el entregable; sobra esa copia.

### El subconjunto que sí debería tener lote

**Las causas C y D: 2.752 líneas (1.258 combinaciones distintas) en 29
expedientes.** No se ha aplicado nada.

| Expediente | C | D | Declara | Lotes creados | Líneas con lote hoy |
|---|---:|---:|---:|---|---:|
| `6.21/28510.0113` | 637 | 318 | 5 | `5` | 21 |
| `6.21/28510.0112` | 637 | 318 | 5 | `4` | 82 |
| `6.23/28510.0097` | 210 | 0 | 5 | `4`, `5` | 83 |
| `4.26/28510.0020` | 0 | 184 | 2 | `1`, `2` | 34 |
| `6.20/28510.0059` / `0060` | 48 | 0 | 6 | `5` / `6` | 35 |
| `6.24/28510.0130` / `0152` / `0153` | 0 | 37 | 13 | varios | 2-10 |
| `6.21/28510.0058` / `0130` / `0135`-`0138` | 30 | 0 | 9 | varios | 7-73 |
| *(otros 16, de 1 a 14 líneas cada uno)* | 32 | 7 | | | |

**Qué haría falta.** Son dos problemas distintos:

- **Causa D (938)**: la tabla continúa en la página siguiente y su banda está
  vacía. Hoy la regla se niega a inferir a propósito. Bastaría con heredar el
  lote de la tabla inmediatamente anterior cuando no hay **ningún** rastro de
  la palabra "LOTE" por medio — que es justo lo que ya hace
  `lote_heredado_de_pagina_anterior` dentro de una misma tabla, extendido al
  salto de página. Verificable de una vez contra `4.26/28510.0020` (184 líneas
  seguidas de un mismo cuadro).
- **Causa C (1.814)**: la tabla no lleva cabecera de lote y el expediente sabe
  cuál es el suyo, pero el documento es el Contrato de otro lote o la última
  mención anterior es de otro lote. Aquí no hay atajo: haría falta abrir los
  dos documentos grandes (`6.21/28510.0112`/`0113`, 637 líneas cada uno, el
  70 % de la causa) y decidir a mano de qué lote es cada tabla.

---

## 6 — Las cantidades con forma de año y los precios atípicos

### Las cantidades con forma de año: **son cantidades reales**

Cifra actual **941** (el encargo citaba 603, de la tercera parte de esta
sesión: las 338 nuevas son del reparto por lotes, que multiplicó por seis las
filas de traviesas). **No es una columna mal mapeada**, y la muestra es
suficiente:

- **801 de las 941 (85 %)** están en los siete expedientes de traviesas
  (`6.20/28510.0054`-`0060`). Se leyó su `ANEJO_8.pdf` fila a fila: la columna
  se llama **"CANTIDAD DE REFERENCIA"** y sus valores son 2000, 2001, 1999,
  1996, 2002, 2004, 2005… **traviesas**. Es el ajuste con el que cada cuadro
  cae sobre su presupuesto (bloque 1). Son reales.
- Las **140 restantes**, en 25 expedientes, traen la cantidad en su propia
  columna y **la columna de importe del propio documento lo confirma**:
  `2.000 × 1,0000 € = 2.000,00 €`, `2.000 × 5,96 € = 11.920,00 €`,
  `2.000 × 1,08 € = 2.160,00 €`, `1.960 × 93,60 €` (vagón de bogies/día)…
- Ni un solo caso en que el valor coincidiera con un año de una columna de
  normativa o de edición, que es la forma que tendría el defecto de columna.

**No se ha cambiado nada.** El aviso sigue saliendo: 941 cantidades que caen en
[1900, 2100] son, en este corpus, cantidades de traviesas y de toneladas de
balasto.

### Los precios atípicos: 2.005 → **1.493**, quitando lo que ya se sabía legítimo

Clasificados por causa, sobre las 2.005 que señalaba el aviso:

| Causa | Líneas |
|---|---:|
| **Partida alzada / a justificar para imprevistos** | **331** |
| **Precio en una unidad de medida distinta de la del resto del expediente** (t·km de transporte contra un cuadro de desvíos; bobinas por unidad contra cable por metro) | **181** |
| **Heterogeneidad real del cuadro** (mismo tipo de unidad: un tornillo de 2,60 € y un útil de 1.600 € en el mismo pliego) | **1.489** |
| **Error de lectura** (ver abajo) | **4** |

Las dos primeras familias **dejan de salir**, con una regla clara cada una:

1. **La partida alzada queda fuera.** CONTEXTO.md sección 2 la define como
   línea legítima: es una reserva presupuestaria, no un artículo, y por
   definición vale órdenes de magnitud más que cualquier pieza del cuadro
   (250.000 € frente a una mediana de 16,09 € en `6.24/28510.0064`).
2. **La mediana con la que se compara es la de las líneas con la MISMA unidad
   de medida.** CONTEXTO.md sección 7, aviso del cliente: un precio unitario
   no significa nada sin su unidad. Si el expediente no tiene al menos tres
   líneas con esa unidad, la línea **no se juzga** — no hay vara de medir, y
   la del expediente entero es una vara de otra magnitud.

Un aviso del que se sabe de antemano que una cuarta parte es correcta no se
mira; ese era el problema.

### Los 4 errores de lectura, y su arreglo

`3.16/28510.0158` y `6.16/28510.0178` imprimen, **debajo del cuadro de precios
de verdad**, la tabla que rellena el licitador: cabecera `Ref. | Denominación
| Licitación | Oferta`, con la columna "Oferta" marcada con su hueco ("P10f",
"M20f"). Sus filas no son artículos: repiten los precios del cuadro de arriba
(P1, P2) y añaden **mediciones globales** (M1 "Cantidad global de balasto …
27.500,00 Tn", M2 "Medición de la cantidad de transporte … 4.455.000,00
TnXKm"). Entraban al catálogo como si 27.500 y 480.000 fueran euros por unidad.

Es la misma familia que el "modelo de proposición económica en blanco" del
acuerdo marco de EPIs (quinta parte, bloque 4): **una tabla para rellenar, no
una tabla de datos**. `app.extraccion.tabla` la descarta ahora por su cabecera
— que nombre a la vez, en columnas distintas, "Licitación" y "Oferta" —, una
señal que ningún cuadro de precios real tiene.

---

## 7 — Los importes compartidos y repetidos

### Los "56 grupos" son **9 familias de expedientes**

El aviso cuenta un grupo por cada **(documento, importe)**, y una licitación
comparte 7-8 documentos entre sus expedientes: las 9 familias reales producen
56 grupos. La cifra del aviso multiplica por seis lo que hay.

| Familia | Importe | Qué es |
|---|---:|---|
| `6.20/28510.0136` + 6 pedidos suyos | 10.000.000 € | **Acuerdo marco**: el techo del AM heredado por cada pedido derivado |
| `6.25/28510.0016` + `0191` + `0234` | 11.700.000 € | Ídem (AM de carril) |
| `6.23/28510.0051` + `0060` | 2.400.000 € | Principal + su lote |
| `6.22/28510.0033` + `0057` + `0058` | 2.400.000 € | Principal + sus dos lotes |
| `6.22/28510.0122` + `0155` + `0156` | 5.900.000 € | Ídem |
| `6.22/28510.0125` + `0126` | 5.900.000 € | Ídem |
| `6.24/28510.0088` + `0114` | 1.000.000 € | Ídem |
| `6.20/28510.0002` + `0003` | 750.000 € | Ídem |
| **`19/28510` + `6.19/28510.0129`** | 7.800.000 € | **No son dos expedientes: son el mismo** |

Las seis familias de "principal + sus lotes" son **legítimas y verificadas en
el documento**: cada lote tiene su propio `codigo_expediente_lote` y la
licitación les da de verdad el mismo presupuesto.

Las dos de acuerdo marco son el mecanismo de herencia de siempre
(`baja_heredada_de_matriz`): el importe del AM se presenta como el de cada
pedido. **No afecta a ningún precio del catálogo** (los precios salen del
cuadro del AM), pero la columna de importe de licitación de esos 8 pedidos
dice el techo del acuerdo marco, no el suyo.

### El único hallazgo real: `19/28510`

`19/28510` y `6.19/28510.0129` **son el mismo expediente**: mismo título, los
**mismos dos documentos** (mismo hash), mismo importe, misma adjudicación,
misma baja, y se crearon con **0,1 s de diferencia** el 16-09 en la misma
ejecución del barrido del buscador. `19/28510` es el número real recortado.
Pasa el criterio del cliente (`app.criterio_expediente`: "entra todo expediente
cuyo código contenga los dígitos del departamento, **sin mirar la forma del
resto del código**"), así que **no es un fallo del extractor sino una
consecuencia medida de ese criterio**, y sacarlo del entregable es cambiar el
criterio. Queda anotado al final.

### Los 8 "importe repetido en el mismo expediente": los 8 legítimos

Cada uno es el expediente principal declarando dos de sus lotes con el mismo
presupuesto, y **el documento lo dice literalmente**:

| Expediente | Lotes | Importe | Dónde lo dice |
|---|---|---:|---|
| `2.24/28510.0050` | 3 y 4 | 35.490,00 € | `CONTRATO_1.pdf` p.95: "TOTAL LOTE 1/2/3/4 … 35.490,00 €" |
| `6.21/28510.0026` | 1 y 2 | 35.000,00 € | Los dos Contratos, p.1, uno por lote |
| `6.22/28510.0033` | 1 y 2 | 2.400.000,00 € | Presupuesto de 4.800.000 € en 2 lotes |
| `6.22/28510.0122` | 1 y 2 | 5.900.000,00 € | `ANEJO_1.pdf` p.5: "Lote 1. NORTE; 5.900.000,00 €. Lote 2. SUR; 5.900.000,00 €" |
| `6.23/28510.0051` | 1 y 2 | 2.400.000,00 € | Ídem |
| `6.23/28510.0105` | 6 y 9 | 15.000,00 € | Los dos Contratos, p.2, uno por lote |
| `6.24/28510.0088` | 1 y 2 | 1.000.000,00 € | CONTEXTO.md sección 4 |
| `6.25/28510.0214` | 4 y 6 | 51.000,00 € | `CONTRATO_1.pdf` p.8: "Lote 4/5/6/7 51.000,00 €" |

**Ninguno esconde un error de extracción.**

---

## 8 — Pendientes antiguos

### `6.21/28510.0152` p.114: **resuelto**, ya no es "no viable"

Las cuatro filas de rodillos de aguja que `pdfplumber` funde en una salían como
**una sola línea ilegible** desde el 15-09, porque la columna de códigos se
llama **"CODIFICACIÓN DEL PRECIO"** y nadie la mapeaba: ni el determinista
("codificacion" no contiene "codigo") ni el modelo, que resuelve esa firma y la
deja sin asignar. Sin `codigo_precio`, `_dividir_fila_multiple` no puede
separar la fila.

**Por qué el intento anterior falló y este no.** Añadir "codificacion del
precio" a los alias hacía que el mapeo **determinista** resolviera esa firma y,
con ella, que el cuadro de balasto multi-lote dejara de ir al modelo — y ahí el
determinista se equivoca, porque solo mira la posición en la cabecera y esa
tabla tiene una columna fantasma desplazada de forma distinta entre cabecera y
datos. La corrección tenía que mirar **los datos**, no el nombre de la columna.

`completar_codigo_precio_por_contenido` (simétrica de la que ya existía para la
matrícula) se aplica **después** del mapeo: si `codigo_precio` no tiene
columna y hay **exactamente una** columna libre en la que **todas** las líneas
tienen forma de código de precio, se le asigna. Con cero o más de una, no se
adivina. El test de guarda del balasto sigue verde.

Resultado sobre el documento real: la fila se separa en **cuatro líneas** con
su código (`P-1`…`P-4`), su matrícula (`619900701`, `702`, `703`), su cantidad
(600, 200, 20, 1) y su precio (366,00 / 466,00 / 155,00 / 34.100,00 €). La
descripción no se reparte (el documento la envuelve en 9 líneas para 4
artículos) y las cuatro van a revisión con su motivo, como manda la regla.

### La errata CONTRAGUJA / CONTRAAGUJA: **no se ha unificado**

| | En la base de datos | En la hoja "Materiales" |
|---|---:|---:|
| Descripción que dice **CONTRAAGUJA** | 1.990 líneas, 18 expedientes | **156 filas**, 8 expedientes |
| Descripción que dice **CONTRAGUJA** | 540 líneas, 9 expedientes | **120 filas**, 7 expedientes |
| Columna "Código del material" = CONTRAGUJA | 264 líneas | **0 filas** (las 264 son huérfanas de `6.21/28510.0112`/`0113`) |

**La errata solo vive en la columna "Descripción del material"**, que es
literal del documento y tiene que seguir siéndolo. La columna "Código del
material" ya unifica las dos formas en **CONTRAAGUJA** (515 filas del Excel):
quien agrupe por código de material ya las ve juntas hoy.

**Propuesta para el cliente**, en una pregunta: *"En sus pliegos conviven dos
grafías de la misma pieza — 'contraaguja' (156 filas del Excel, 8 expedientes,
entre ellos `6.21/28510.0108`-`0111` y `6.20/28510.0041`) y 'contraguja' (120
filas, 7 expedientes, entre ellos `6.22/28510.0122`/`0155`/`0156`). La columna
'Código del material' ya las agrupa a las dos como CONTRAAGUJA, así que buscar
por ahí no pierde nada. ¿Prefieren que la columna 'Descripción del material'
siga diciendo lo que dice cada documento — que es lo que hace hoy, y lo que
permite cotejar la fila con el PDF — o que unifiquemos la grafía en el
entregable y guardemos la original aparte?"* No se toca nada hasta que
contesten.

### Las unidades `PA` y `P`

| Unidad | Líneas (BD) | Filas en "Materiales" | Qué es |
|---|---:|---:|---|
| **PA** | 67 | 33 | **Partida alzada**. No es una unidad de medida: es el tipo de línea. Todas sus descripciones son "PARTIDA ALZADA…" |
| **P** | 3 | 3 | Código de unidad base **del maestro de materiales de SAP**, sin nombre completo en el fichero. Las 3 son la misma línea ("PLACA NERVADA PN-60-1:20") en `6.20/28510.0042`/`0046`/`0047`, y las 3 traen `unidad_medida_completada_desde_maestro` — no salen de ningún documento |

Las unidades reales que hay hoy en el Excel son `ud` (10.322), `m` (917),
`kg` (444), `t` (311), `m3` (124), `t·km` (82), `m3·km` (35), `dm3` (16),
`transporte` (15), `h` (11), `ud/día` (8), `m2` (8), `t·mes` (5), `mes` (4),
`Ml` (3) y `elemento·mes` (3), más `PA` (33) y `P` (3).

**No se pueden unificar con ninguna, y no se ha tocado nada.** `PA` no es "ud"
(una partida alzada no es una unidad de nada: CONTEXTO.md sección 7 dice que a
una partida alzada la unidad "no aplica"), y `P` no se puede identificar con
ninguna sin el nombre completo del maestro de SAP. Lo honesto para `PA` sería
dejar de tratarla como unidad y que la celda salga vacía con motivo "no
aplica", pero eso cambia 33 filas del entregable: decisión del cliente.

### Añadir "Código de precio" como columna del Excel: **no se ha hecho**

Medido sobre las 19.474 filas entregadas:

| | Filas | % |
|---|---:|---:|
| Tendrían valor | **8.911** | 45,8 % |
| Quedarían vacías | **10.563** | 54,2 % |

Por expediente (363 con filas): **187 la tendrían en todas sus filas**, **146
en ninguna** y **30 mezclados**.

**A favor**: es la clave real del catálogo (`expediente + lote + código de
precio`, CONTEXTO.md sección 7) y se comprobó que **no se repite ni una sola
vez** en las 8.911 filas que la tienen — es un identificador de verdad, no un
número decorativo. Permite cotejar una fila con su renglón del PDF.

**En contra**: más de la mitad de las filas la dejarían vacía, y no por un
hueco de extracción: son cuadros que **no numeran sus renglones** (los tres
grandes, `6.20/28510.0042`/`0046`/`0047`, aportan 3.882 de esas 10.563). Sería
la columna menos rellena del Excel después de la matrícula.

**Sugerencia**: merece la pena si el cliente va a cotejar filas contra el PDF;
no la merece si solo agrupa y filtra. Lo decide el cliente.

---

## 9 — Cierre

### Pruebas

**1.104 pasan** (1.091 al cerrar la quinta parte, **+13**). Ninguna saltada.
Las nuevas: 4 del bloque 4 (las dos vías de red, cada una con su mitad
contraria), 2 de la Conciliación del bloque 3 (el Contrato que basta, y el
Contrato de uno mismo que no convierte a nadie en lote de otro), 2 del modelo
de oferta en blanco, 2 de la auditoría de precios (la partida alzada fuera, la
mediana por unidad) y 3 de `completar_codigo_precio_por_contenido`.

### El reproceso completo, con la red apagada de verdad

`POST /mantenimiento/ejecutar` con `forzar: true`, `sindicacion_desactivada:
true` y `busqueda_desactivada: true`. **518 expedientes reextraídos**, 520
evaluados, **20 minutos y 39 segundos** (1.239 s).

Y esta vez la red está apagada, medido en el propio resumen del ciclo:

| | |
|---|---|
| `descargas_lanzadas` | **0** |
| `saltados_descarga` | 520 |
| `sin_publicar_reintentados` | **0** |
| `sin_publicar_desactivado` | **True** |
| `descubrimiento` | `None` |
| `descubrimiento_busqueda` | `None` |
| Trabajos `descargar_expediente` encolados | **0** |

Cero peticiones a la Plataforma, frente a las cuatro del reproceso anterior.

### Comparación con el reproceso anterior

| | Antes | Ahora |
|---|---:|---:|
| Filas de "Materiales" | 19.474 | **19.553** (+79) |
| Expedientes con filas | 363 | **363** (=) |
| Filas de "Conciliación" | 532 | **535** (+3) |
| Materiales distintos **por matrícula** (expediente + matrícula) | 11.832 | **11.832** (=) |
| Materiales distintos **por matrícula y precio** | 11.895 | **11.895** (=) |
| Materiales distintos **por lote, matrícula y precio** | 13.182 | **13.182** (=) |

**0 expedientes desaparecen, 0 expedientes nuevos, y ni un solo material se
pierde** por ninguna de las tres claves. Solo **7 expedientes** cambian de
número de filas, y los siete por un cambio hecho a propósito:

| Expediente | Antes | Ahora | Por qué |
|---|---:|---:|---|
| `6.22/28510.0173` | 184 | **272** (+88) | **Bloque 8**: su cuadro también titula la columna de códigos "CODIFICACIÓN DEL PRECIO". Con ella mapeada, 88 materiales que antes colapsaban entre sí por clave (`expediente + lote + código de precio`) recuperan su identidad. 177 de las 272 filas traen ya código de precio |
| `6.25/28510.0156` | 32 | **39** (+7) | Ídem |
| `6.24/28510.0171` | 13 | **7** (−6) | **Duplicación que desaparece**: sus 6 materiales estaban **dos veces**, con la misma matrícula y el mismo precio — una copia con cantidad y otra sin ella. Al mapearse el código de precio las dos caen en la misma clave y se funden en una, quedándose con la cantidad. 0 materiales perdidos |
| `6.26/28510.0083` | 15 | **14** (−1) | Ídem, un solo duplicado (`594200021`, tubo de cobre de 35 mm) |
| `3.16/28510.0158` | 10 | **6** (−4) | **Bloque 6**: salen las 4 filas del modelo de oferta en blanco (`P1` y `P2` repiten precios del cuadro real; `M1` y `M2` son mediciones globales que entraban como si 27.500 Tn fueran 27.500 €/ud) |
| `6.16/28510.0178` | 8 | **4** (−4) | Ídem |
| `6.21/28510.0152` | 5 | **4** (−1) | **Bloque 8**: desaparece la fila fundida ilegible ("Rodillo de presión para el talón Rodillo de presión para la punta Placa resbaladera…", sin matrícula, sin cantidad y sin precio) y sus cuatro materiales quedan cada uno en su fila, con su matrícula y su precio |

**Las 16 filas que salen del Excel, una a una**: 8 son el modelo de oferta en
blanco (4 + 4), 7 son copias exactas de un material que ya estaba en la hoja
(6 + 1) y 1 es la fila fundida ilegible. **Ninguna es del bloque 1: no se
revirtió ningún expediente.** Y ninguna de las 16 tiene matrícula propia que se
pierda — comprobado con las tres claves de la tabla de arriba.

**Un efecto lateral que conviene decir**: en `6.24/28510.0171`, al fundirse
cada pareja de duplicados, la descripción que sobrevive es la que el documento
imprime literalmente en esa celda ("DISYUNTOR EXTRARRÁPIDO MODELO UR26ED64S
DE") y no la que antes se recomponía uniendo esa celda con el trozo que se
derrama en la fila siguiente ("… DE SECHERON O EQUIVALENTE"). Son 6 filas: la
matrícula, la cantidad y el precio no cambian; solo la descripción queda más
corta. Anotado abajo.

### Cuadre de "Conciliación" con "Materiales"

```
suma de la columna de líneas de "Conciliación": 19.553
filas de la hoja "Materiales":                  19.553
```

0 expedientes sin Situación.

### Auditoría

La auditoría que corrió **dentro** del ciclo dio **1 error y 7 avisos**, y es
la regla funcionando: `lineas_cambian_sin_cambiar_documentos` sobre
`6.21/28510.0152`, `6.22/28510.0173` y `6.25/28510.0156` (los tres que cambian
de filas sin que cambien sus documentos), más
`lineas_bajan_explicado_por_poda` sobre `3.16/28510.0158`, `6.16/28510.0178`,
`6.24/28510.0171` y `6.26/28510.0083`. Los siete están explicados uno a uno en
la tabla de arriba.

La auditoría posterior, la que pedía el encargo, da **0 errores y 6 avisos**:

| Aviso | Antes | Ahora |
|---|---:|---:|
| Grupos de material repetido con códigos de precio distintos | 11 | **11** |
| Huérfanas sin lote | 19.233 | **19.233** (la misma cifra exacta) |
| Precios atípicos | 2.005 | **1.488** |
| Cantidades con forma de año | 941 | **941** |
| Grupos de importe de licitación compartido | 56 | **56** |
| Expedientes con importe repetido entre sus lotes | 8 | **8** |

### Recuento por Situación de la hoja "Conciliación"

| Situación | Expedientes | Antes |
|---|---:|---:|
| Aporta líneas | **363** | 363 |
| Publicado sin cuadro de precios | **64** | 64 |
| Los precios están en un acuerdo marco que no está publicado | **47** | 47 |
| El acuerdo marco está publicado pero no publica precios unitarios | **2** | 2 |
| **Publicado dentro de la ficha de otro expediente** | **17** | 14 |
| Documentos escaneados que no se han podido leer | **15** | 15 |
| Otro | **27** | 27 |
| Pendiente de procesar | **0** | 0 |
| **Total** | **535** | 532 |

Los 3 nuevos son exactamente los del bloque 3 — `4.23/28510.0081`,
`6.19/28510.0213` y `6.19/28510.0216` — y **ningún otro expediente se mueve de
situación**. Los que la Plataforma confirma que no publica bajan de 59 a 56.

### Excel

```
C:\dev\ADIF\catalogo_adif_2026-09-18-verificacion-reparto.xlsx
```

---

## Pendiente de decisión del cliente

1. **El cuadro del lote 3 de `6.20/28510.0054`-`0058` se pasa de su propio
   presupuesto** en 30.002,13 € (0,37 %), y el del lote 4 en 1,60 €. Es una
   discrepancia del documento de ADIF, verificada fila a fila; no hay nada que
   arreglar por nuestra parte, pero conviene que lo sepan.
2. **El dígito del reconocimiento óptico de `6.17/28510.0056`**: `P-7` dice
   56.555,91 € y la columna de importes del mismo documento demuestra que son
   56.455,91 €. Corregir un precio a partir de la columna de importes sería un
   mecanismo nuevo que reescribiría precios en todo el corpus: **no se ha
   hecho**. Y el lote 2 de ese expediente perdió su columna de cantidades en
   el reconocimiento óptico: 4 filas sin cantidad, recuperables releyéndolo.
3. **Aflojar la garantía del reparto por lotes** (bloque 2): mete 15
   expedientes y ~1.971 filas, pero `4.25/28510.0132` pierde 91.
4. **Los cuatro expedientes de balasto `6.22/28510.0011`-`0014` son ellos
   mismos un lote**, y su título lo dice con todas las letras ("Lote 1:
   Jefatura de Barcelona"), pero el sistema no lo registra: por eso cada uno
   carga con los seis cuadros de la licitación en vez de solo con el suyo.
   Igual pasa con `6.20/28510.0055`-`0058`, que cuelgan de `0054`. Leer el lote
   del título para esto no se hace hoy. El catálogo es fiel a lo publicado
   —cada uno de esos expedientes publica los seis cuadros— pero el cliente
   puede querer otra cosa.
5. **`19/28510` y `6.19/28510.0129` son el mismo expediente** (bloque 7):
   mismo título, los mismos dos documentos, mismo importe, creados con 0,1 s
   de diferencia por el barrido del buscador. `19/28510` es el número
   recortado. Sacarlo del entregable es cambiar el criterio del cliente ("sin
   mirar la forma del resto del código"), así que **no se ha tocado**.
6. **La unidad `PA`** (33 filas del Excel) no es una unidad de medida sino
   "partida alzada". Lo honesto sería dejar la celda vacía con motivo "no
   aplica" (bloque 8).
7. **La errata CONTRAGUJA / CONTRAAGUJA** (bloque 8): la pregunta está
   redactada y lista para enviarla.
8. **La columna "Código de precio" en el Excel** (bloque 8): 8.911 filas de
   19.553 la tendrían; la decisión es del cliente.
9. **Las 2.752 huérfanas de las causas C y D** (bloque 5): la D (938) tiene un
   camino claro; la C (1.814) exige revisión manual de dos documentos grandes.
10. **Las 6 descripciones de `6.24/28510.0171`** que quedan más cortas tras
    fundirse con su duplicado. El material, la matrícula, la cantidad y el
    precio no cambian.
11. Siguen en pie las decisiones abiertas de las partes anteriores que no se
    han cerrado aquí.
