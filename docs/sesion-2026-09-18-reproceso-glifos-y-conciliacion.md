# Sesión 2026-09-18 (quinta parte) — Reproceso completo, expedientes que cuelgan de la ficha de otro, y la columna de estado

Seis bloques. Continúa `docs/sesion-2026-09-18-barrido-no-publicados-y-glifos.md`.

---

## 1 — Decisión del cliente: hasta dónde puede llegar el sistema con el estado

**Isabel Ibáñez (ADIF)**, por escrito en el grupo de trabajo, el **18/09/2026**:
sin acceso a SAP, el último estado que la herramienta puede conocer es
**Resuelta o adjudicado**; los estados posteriores del contrato los indicarán
ellos manualmente. **Aceptado.**

Guardado en `docs/decisiones-cliente.md` sección 27 (quién, cuándo, qué cambia)
y reflejado en **CONTEXTO.md sección 7**, con la tabla de qué hecho puede saber
el sistema y de dónde sale cada uno. Es además el techo de la escalera de
estados del bloque 6: la columna "Estado que consta publicado en la Plataforma"
no puede pasar de *Resuelta* porque no hay ningún documento publicado del que
leer un estado posterior.

---


## 2 — Reproceso completo: qué afloró de verdad por las cifras en glifos

### Cómo se lanzó, y una salvedad sobre "sin búsqueda en la Plataforma"

`POST /mantenimiento/ejecutar` con `forzar: true`, `sindicacion_desactivada:
true` y `busqueda_desactivada: true`. **518 expedientes reextraídos**, 520
evaluados, 0 descubrimientos nuevos.

**Salvedad, medida y no escondida.** Esas dos banderas apagan el descubrimiento
por sindicación y el barrido del buscador, pero **no el reintento de los
`sin_publicar`**, que es un tercer mecanismo independiente
(`app.mantenimiento.ciclo._reintentar_sin_publicar`, plazo por antigüedad desde
la cuarta parte de esta sesión). Ese reintento **sí tocó la red, para 4
expedientes**, y no encontró nada nuevo:

| Expediente | Resultado |
|---|---|
| `6.14/28510.0177` | encontrado, **0 documentos nuevos** (su ficha no publica ninguno, ya conocido) |
| `6.14/28510.0148` | ídem |
| `2.25/28520.0161` | no encontrado (expediente de otro departamento, del conjunto fijo de prueba) |
| `3.25/27520.0055` | ídem |

91 quedaron "en plazo" y no se reintentaron.

### Cuánto tarda

**21 minutos y 46 segundos** (1.305 s) para los 518 expedientes, sin descargas
de documentos. Es **un orden de magnitud menos que las 4-5 horas** que costaba
un reproceso completo antes de la caché de texto por documento (migración 0029,
sesión 2026-09-12): ~2,5 s por expediente.

### La respuesta al encargo: **0 expedientes nuevos**

De los **197 expedientes** que referencian alguno de los 178 documentos con
cifras en glifos, **ninguno nuevo aporta una sola línea por esta vía**. El
único expediente del corpus con cifras en glifos dentro de un cuadro de precios
sigue siendo `6.26/28510.0064`:

| Expediente | Líneas con precio por glifos | Por aritmética de su fila | Por el mismo código en otro lote | A revisión |
|---|---:|---:|---:|---:|
| `6.26/28510.0064` | **35** | 30 | 5 | **1** |
| *(cualquier otro)* | 0 | 0 | 0 | 0 |

**Por qué era previsible y aun así había que medirlo.** La cuarta parte ya
decía que los 196 restantes eran *"el techo de lo que podría aparecer en un
reproceso completo, no una previsión"*: casi todas esas cifras están en páginas
que no son cuadro de precios —el cuerpo de un Contrato firmado de 100 páginas,
sobre todo— y la etapa 3 de la cascada solo abre como tabla las páginas
candidatas. El reproceso convierte ese techo en un número: **es 1, y era el que
ya conocíamos.**

**La única línea que sigue a revisión por esta causa** es `P-2` del lote 3 de
`6.26/28510.0064` (el transporte), y su motivo dice exactamente por qué: su
tabla no publica columna de totales y ninguna de las dos lecturas posibles de
su celda coincide con ningún precio verificado del mismo código. Detalle
completo en el bloque 5.

### La comprobación dura se respetó en las 19.474 filas

Ninguna cifra en glifos entró al catálogo sin que la aritmética de una fila del
propio documento la demostrara: 30 por la suya propia, 5 por la de la fila del
mismo código en otro lote del mismo cuadro (bloque 5). La que no cuadra está
fuera, con su motivo.

### Lo que sí cambió el reproceso, y no son los glifos

El reproceso **añade 1.151 filas al Excel** (18.323 → 19.474), y **ninguna es
de los glifos**. Vienen de **el reparto por lotes del propio cuadro de precios**
(`_lotes_candidatos_del_cuadro`), el otro arreglo de la cuarta parte, que
también *"solo actúa al reextraer"* y que este reproceso ejecuta por primera vez
sobre todo el corpus — era el punto 2 de los pendientes que dejó aquella sesión.
Está medido y explicado en el cierre.

---

## 3 — Expedientes cuyos documentos cuelgan de la ficha de otro

### El mecanismo, y por qué no es "buscar el número en el texto"

Buscar el número suelto en el texto de todos los documentos **encuentra
demasiado**: encuentra el número de contrato que un anuncio de formalización
asigna a otra cosa, encuentra el acuerdo marco del que cuelga un pedido, y
encuentra una nota de "se retoma la licitación". Ninguna de las tres dice "este
expediente es un lote de aquel". El barrido de texto se hizo igualmente, pero
solo **para medir**, nunca para decidir.

Lo que decide es `app.conciliacion._lotes_en_ficha_de_otro`: la relación sale de
`Lote.codigo_expediente_lote`, que es el campo que el sistema rellena cuando un
documento de adjudicación o un contrato **liga por número un lote a su
expediente** (`app.extraccion.lotes`, generalizado en
`docs/identidad-expediente.md` sección 27). Es la misma evidencia que ya
sostenía el hallazgo de `6.26/28510.0003` — su Resolución de Adjudicación dice
literalmente *"LOTE 2 … EXPEDIENTE Nº 6.26/28510.0003"* — solo que el índice se
usa ahora al revés: de quién cuelga este número.

### Qué cambia en la hoja

Estos expedientes **entraban antes en la frase del registro que decía que la
Plataforma "confirmó que no publica"**, y eso era falso: lo que no está
publicado es su *ficha*, no sus documentos. Ahora salen en la hoja, con una
Situación propia:

> **Publicado dentro de la ficha de otro expediente**
>
> Este expediente es el lote 2 de la licitación 6.25/28510.0221, y así lo
> declara por su número un documento publicado de 6.25/28510.0221. Sus
> documentos (adjudicación, contrato, cuadro de precios) se publican dentro de
> la ficha de 6.25/28510.0221, no bajo su propio número: buscarlo en la
> Plataforma por este número no devuelve nada, y eso no significa que no esté
> publicado. Lo que aporte al catálogo se cuenta en la fila de
> 6.25/28510.0221.

Y el registro de la hoja "Resumen" lo dice aparte, en vez de meterlos en el
saco de los no publicados.

**No se toca `EstadoExpediente.sin_publicar`.** Es correcto: la Plataforma, en
efecto, no devuelve nada al buscarlos, y el reintento periódico
(`app.mantenimiento.frescura`) debe seguir intentándolo. Lo que cambia es lo
que el entregable *dice* de ellos, no el estado del sistema.

**Tampoco se arrastran los documentos del principal al lote.** Sería la otra
forma de "enlazarlos", y se descarta: haría que el lote empezara a aportar
líneas propias duplicando las del principal, justo lo que
`docs/identidad-expediente.md` sección 27 ya decidió no hacer.

### Las cifras

| | |
|---|---:|
| Expedientes del departamento dados por no publicados | **73** |
| De ellos, **mencionados por su número en un documento publicado de otro expediente** | **29** |
| De esos 29, **con enlace estructural** (un lote de otro los declara por número) | **14** |
| De esos 29, **solo mencionados en el texto** — no se fuerza nada | **15** |
| Expedientes en situación "acuerdo marco no publicado" (49 antes del bloque 4) | **47** |
| De esos 47, mencionados en un documento publicado de otro expediente | **0** |

**Los 14 que sí se enlazan**, y de quién cuelga cada uno:

| Expediente | Es el lote | de la licitación |
|---|---:|---|
| `2.24/28510.0080` | 1 | `2.24/28510.0050` |
| `2.24/28510.0081` | 2 | `2.24/28510.0050` |
| `2.24/28510.0082` | 3 | `2.24/28510.0050` |
| `2.24/28510.0083` | 4 | `2.24/28510.0050` |
| `2.26/28510.0029` | 2 | `4.26/28510.0020` |
| `6.23/28510.0114` | 4 | `6.23/28510.0105` |
| `6.23/28510.0116` | 6 | `6.23/28510.0105` |
| `6.23/28510.0119` | 9 | `6.23/28510.0105` |
| `6.23/28510.0124` | 4 | `6.23/28510.0097` |
| `6.23/28510.0125` | 5 | `6.23/28510.0097` |
| `6.24/28510.0161` | 1 | `6.24/28510.0125` |
| `6.24/28510.0162` | 2 | `6.24/28510.0125` |
| `6.25/28510.0250` | 2 | `6.25/28510.0201` |
| `6.26/28510.0003` | 2 | `6.25/28510.0221` |

**Los 15 que NO se enlazan, y qué es de verdad cada mención.** Se miraron una a
una, no se cuentan a bulto:

| Expedientes | Dónde aparece el número | Qué es en realidad |
|---|---|---|
| `6.16/28510.0088`, `0089`, `0090`, `0091`, `0092`, `0096` | `CONTRATO_1.pdf` de `6.15/28510.0080` | El campo **"Número de Contrato"** del anuncio de formalización: *"Número de Contrato 6.16/28510.0088/01"*. Es el número del **contrato**, no el de un expediente de lote. |
| `6.17/28510.0020`, `0021` | `CONTRATO_1.pdf` de `6.16/28510.0164` | Ídem, *"Número de Contrato 6.17/28510.0020/01"*. |
| `6.19/28510.0203` | `CONTRATO_1.pdf` de `6.19/28510.0202` | Ídem. |
| `6.20/28510.0013` | `CONTRATO_1.pdf` de `6.19/28510.0184` | Ídem. |
| `6.17/28510.0031` | `CONTRATO_1.pdf` y `ADJUDICACION_1.pdf` de `6.20/28510.0043` | *"Licitación basada en el acuerdo marco — Expediente 6.17/28510.0031"*: es la **matriz** de ese pedido, no un lote suyo. Relación que el sistema ya conoce (`codigo_matriz`). |
| `4.23/28510.0081` | `CONTRATO_1.pdf` de `4.23/28510.0058` | *"Contrato nº: 4.23/28510.0081 … EXPEDIENTE PRINCIPAL Nº 4.23/28510.0058"*. **Sí es un lote**, pero el sistema no lo tiene registrado como tal: es un contrato firmado, no una resolución de adjudicación, y el extractor de lotes no lo captura hoy. |
| `6.19/28510.0213`, `0216` | `CONTRATO_2.pdf` y `ADJUDICACION_1.pdf` de `6.19/28510.0196` | *"Contrato nº: 6.19/28510.0213 … (Nº EXPEDIENTE: 6.19/28510.0196). LOTE 1"*. **También son lotes**, con la misma causa: la redacción no es la que el extractor reconoce. |
| `6.26/28510.0002` | `ANEJO_3.pdf` y `ANEJO_4.pdf` de `6.25/28510.0221` | *"Se retoma la licitación … LOTE 1 … expediente 6.26/28510.0002"*. Es un **anuncio de fechas**, no un acto de adjudicación: dice que existe, no le adjudica nada. |

**Tres de los quince (`4.23/28510.0081`, `6.19/28510.0213`, `6.19/28510.0216`)
son lotes de verdad** y el sistema podría llegar a registrarlos si el extractor
de lotes reconociera esas dos redacciones de Contrato. **No se toca en esta
sesión**, por lo que pedía el encargo: enlazar por una regex nueva sin
verificarla contra más casos es forzar. Queda anotado como pendiente.

Los otros doce **no son lotes**: seis+dos+uno+uno son números de contrato, uno
es una matriz y otro un anuncio de fechas. Llamarlos "publicados en la ficha de
otro" sería tan falso como llamarlos "no publicados".

---

## 4 — Los 49 de acuerdo marco, partidos en dos

**La señal, estructural.** Cuando la matriz del campo fijo del anuncio no está
publicada, el propio título del pedido declara a veces el **expediente
principal** de la licitación por lotes de la que cuelga
(`app.extraccion.lote_declarado.extraer_expediente_principal_declarado`, que ya
existía desde la cuarta parte de esta sesión pero solo se usaba para redactar
el motivo). Si ese principal **sí** está publicado, la situación no es la
misma: hay documentos publicados, descargados y leídos enteros; lo que no hay
en ellos es un precio unitario.

El caso real es `4.23/04110.0256`, el acuerdo marco de EPIs 2024-2025 (8
lotes), verificado documento a documento en la cuarta parte: lo que su PCAP
publica por lote (p.17-22) **es el modelo de proposición económica en blanco**,
con las unidades puestas y la columna "PRECIO UNITARIO" vacía, que es la que
rellena cada licitador.

**La situación nueva**, literal:

> **El acuerdo marco está publicado pero no publica precios unitarios**
>
> Es un pedido que se hace contra el acuerdo marco 4.24/04110.0187. El anuncio
> de este pedido declara además el expediente principal de ese acuerdo marco,
> 4.23/04110.0256, que sí está publicado y cuyos documentos se han descargado
> y leído enteros. Lo que publica no es un cuadro de precios: es el modelo de
> proposición económica en blanco […]. No hay ningún precio unitario publicado
> que leer. Para completarlo haría falta que ADIF facilitara los precios
> adjudicados de ese acuerdo marco.

### El reparto

| Situación | Expedientes |
|---|---:|
| Los precios están en un acuerdo marco que no está publicado | **47** |
| El acuerdo marco está publicado pero no publica precios unitarios | **2** |
| **Total (los 49 de antes)** | **49** |

Los dos son `6.26/28510.0068` (lote 6, crema solar) y `6.26/28510.0073`
(lote 4, guantes), los dos del acuerdo marco `4.23/04110.0256`. Los otros 47
cuelgan de 13 acuerdos marco distintos, **ninguno publicado** y ninguno con un
expediente principal publicado detrás: para esos no hay absolutamente nada que
leer, y su texto sigue diciendo exactamente lo que decía.

---

## 5 — Las 6 filas del lote 3 de `6.26/28510.0064`

### Qué se buscó, y dónde

El encargo: *"busca si ese mismo precio aparece verificado en otro lote del
mismo cuadro o en otro documento del expediente"*. Las dos mitades:

**En otro documento del expediente: no hay nada.** El expediente tiene tres
documentos y **solo `ANEJO_1.pdf` trae glifos y trae cuadro de precios**.
`ANEJO_2.pdf` (el PCAP, 91 páginas) publica presupuestos por lote
(*"Lote 3 1.027.740,00 €"*) pero **ningún precio unitario**, y `PLIEGO_1.pdf`
(7 páginas) solo el importe máximo. No hay segunda fuente dentro del
expediente.

**En otro lote del mismo cuadro: sí, en cinco de los seis conceptos.** El
cuadro repite los mismos seis conceptos en los seis lotes, y cinco de ellos
valen lo mismo en todos; el sexto, el transporte, vale distinto en cada uno:

| Código | Lote 1 | Lote 2 | Lote 4 | Lote 5 | Lote 6 | Lote 3 (en glifos) |
|---|---:|---:|---:|---:|---:|---:|
| P-1 Balasto sobre camión en cantera | 11,97 | 11,97 | 11,97 | 11,97 | 11,97 | **11,97** |
| P-2 T de balasto transportado | 13,50 | 28,80 | 16,20 | 33,30 | 21,60 | **20,88** |
| P-3 T×km de balasto transportado | 0,18 | 0,18 | 0,18 | 0,18 | 0,18 | **0,18** |
| P-4 Lavado de balasto | 5,96 | 5,96 | 5,96 | 5,96 | 5,96 | **5,96** |
| P-5 Remonte de balasto | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | **1,00** |
| P-6 Enrasado de balasto en tolva | 1,00 | 1,00 | 1,00 | 1,00 | 1,00 | **1,00** |

### Qué se ha implementado, y qué NO

`app.extraccion.glifos_cid.confirmar_con_precio_conocido` +
`app.catalogo.resolver_glifos_con_precio_de_otro_lote`, una pasada por
documento que corre en `procesar_anejo` cuando ya se ha leído el documento
entero.

**No se copia ningún precio de ninguna parte.** Es importante, porque la
diferencia entre las dos cosas es la diferencia entre leer un documento e
inventárselo. El número que se escribe sigue siendo **el de los glifos de esa
misma celda**; lo único que aporta la otra tabla es **confirmar con qué
desplazamiento hay que leerlos**, que es exactamente lo que a una tabla sin
columna de totales le falta. Y se exige que ese desplazamiento sea **el único**
de los posibles que produce un precio ya conocido para ese mismo código: si dos
lecturas distintas dieran cada una un precio conocido, no se elige ninguna.

La cuenta, en el caso real:

- `P-1` → `(cid:1005)(cid:1005),(cid:1013)(cid:1011)(cid:1004)(cid:1004)`. Los
  identificadores van de 1004 a 1013: **un único desplazamiento posible**
  (1004), que da `11,9700`. Coincide con el P-1 de los otros cinco lotes.
- `P-5`/`P-6` → `(cid:1005),(cid:1004)(cid:1004)(cid:1004)(cid:1004)`. Solo dos
  identificadores distintos, así que por sí sola la celda **admite nueve
  lecturas** (desplazamientos 996 a 1004). Solo una, la de 1004, da `1,0000`,
  que es un precio ya verificado para ese código. Las otras ocho dan
  `2,1111`, `3,2222`… y ninguna coincide con nada.
- `P-2` → `(cid:1006)(cid:1004),(cid:1012)(cid:1012)(cid:1004)(cid:1004)`. Dos
  desplazamientos posibles: 1004 da `20,8800` y 1003 da `31,9911`. **Ninguno de
  los dos coincide** con ninguno de los cinco P-2 conocidos (13,50 / 28,80 /
  16,20 / 33,30 / 21,60), porque el transporte vale distinto en cada lote. **No
  se escribe nada y la fila se queda como estaba**, con su motivo de siempre.

### Sobre la regla dura del bloque 2

El encargo dice, y con razón, que *"ninguna línea puede escribirse sin haber
pasado la comprobación de cantidad por precio unitario igual a importe"*. Estas
cinco filas **no tienen** esa comprobación en su propia fila: su tabla no
publica totales. Lo que sí tienen es que **el número que se les escribe es un
número que sí pasó esa comprobación**, fila por fila, en las tablas de los
otros lotes del mismo cuadro — `11,97` se verificó con `30.000 × 11,97 =
359.100,00`, que trae la fila del lote 1. Ninguna cifra entra al catálogo sin
que la aritmética de alguna fila del documento la haya demostrado.

Aun así **no se dan por buenas en silencio**: las cinco llevan su motivo, que
dice de dónde viene la confirmación y pide comprobarla contra el documento:

> precio unitario descodificado de identificadores de glifo (el PDF no trae
> tabla de caracteres) y esta tabla no publica columna de totales con la que
> comprobarlo: confirmado porque el mismo código de precio (P-1) vale 11,97 €
> en la tabla del lote 1 del mismo cuadro, y es la única lectura posible de
> esta celda que coincide con él — confirmar contra el documento antes de darlo
> por bueno

### Resultado

| Lote | Filas | Con precio (antes) | Con precio (ahora) |
|---|---:|---:|---:|
| 1, 2, 4, 5, 6 | 30 | 30 | 30 |
| **3** | 6 | **0** | **5** |
| **Total** | **36** | **30** | **35** |

`P-2` del lote 3 es la única de las 36 que sigue sin precio, y con el motivo
exacto de por qué.

---

## 6 — La columna de estado publicado

### Qué se ha aplicado

`app.conciliacion._estado_publicado`. La columna "Estado que consta publicado
en la Plataforma" sigue saliendo del boletín mensual de sindicación, **salvo
cuando el sistema ya tiene descargado de la Plataforma un documento que prueba
una etapa posterior**, y entonces manda el documento.

Lo que prueba cada documento, y nada más:

| Documento descargado de la Plataforma | Prueba |
|---|---|
| Resolución de Adjudicación / Propuesta LC.27 / Propuesta DT | **Adjudicada** |
| Contrato / Anuncio de formalización | **Resuelta** |

La escalera es `Anuncio previo < En plazo < Pendiente de adjudicación <
Adjudicada < Resuelta`, y **termina ahí por la decisión del bloque 1**: sin SAP
no hay nada publicado de lo que leer un estado posterior.

### Las tres garantías, que son lo que hace que este cambio sea pequeño

1. **La columna solo avanza de etapa, nunca retrocede.** Si el boletín va por
   delante del documento, o empatan, manda el boletín.
2. **"Anulada" no está en la escalera.** Un código que no está en ella
   (`ANUL`, o uno que la Plataforma añada mañana) **no se compara**: manda el
   boletín. Sin esta condición, cualquier documento pasaría por delante de una
   anulación — lo detectó el test `test_la_columna_de_estado_nunca_baja_de_etapa`
   antes de salir de la sesión.
3. **No se toca `Expediente.estado`.** Esto cambia lo que la columna informa,
   no el estado del sistema. CONTEXTO.md sección 12 ("un contraste externo no
   tiene autoridad para cambiar el estado de un expediente") sigue intacta: esa
   regla protege al documento del contraste, y aquí manda el documento.

### La celda lo dice

Cuando manda el documento, la celda dice también lo que decía el boletín, para
que nadie se encuentre un valor cambiado sin explicación:

> Adjudicada (lo prueba su Resolución/Propuesta de Adjudicación, descargada de
> la Plataforma; el último boletín de sindicación de 07/2026 todavía decía
> "Pendiente de adjudicación", y un boletín refleja el mes en que se publicó,
> no lo que sigue vigente)

Y la hoja "Resumen" lleva una nota fija nueva (`_NOTA_ESTADO_PUBLICADO`) que
explica la regla entera, incluido el techo de "Resuelta" y de dónde viene.

---

### Cuántas filas cambian, y 5 ejemplos

**252 de las 532 filas** de la Conciliación cambian de valor en esa columna:

| Antes | Ahora | Filas |
|---|---|---:|
| *no consta* | Resuelta | **214** |
| *no consta* | Adjudicada | **33** |
| Adjudicada | Resuelta | **3** |
| Pendiente de adjudicación | Adjudicada | **2** |

**247 de las 252 rellenan una celda que estaba vacía**, y ese es el efecto
grande que no se esperaba: son expedientes antiguos que la sindicación mensual
nunca ha listado (sus eventos de contratación cayeron en meses anteriores a los
boletines ingeridos, CONTEXTO.md sección 16), así que la columna decía *"no
consta"* aunque el sistema tuviera su contrato firmado descargado. Las 5
restantes son el desfase que motivó el encargo.

Cinco ejemplos, uno por tipo de cambio:

| Expediente | Antes | Ahora |
|---|---|---|
| `6.20/28510.0054` | Adjudicada | **Resuelta** — lo prueba su Contrato/Anuncio de formalización; el boletín de **09/2026** todavía decía "Adjudicada" |
| `3.26/28510.0013` | Pendiente de adjudicación | **Adjudicada** — lo prueba su Resolución de Adjudicación; el boletín de **07/2026** todavía decía "Pendiente de adjudicación" |
| `19/28510` | *no consta* | **Adjudicada** — lo prueba su Resolución de Adjudicación; la sindicación no ha listado nunca este expediente |
| `2.19/28510.0015` | *no consta* | **Resuelta** — lo prueba su Contrato/Anuncio de formalización; ídem |
| `2.18/28510.0083` | *no consta* | **Adjudicada** — ídem |

---

## Cierre

### Pruebas

**1.091 pasan** (1.078 al cerrar la cuarta parte, **+13**). Ninguna saltada.
Las nuevas: 8 de la segunda vía de los glifos (`confirmar_con_precio_conocido`,
incluida la que **no** debe confirmarse por variar de lote a lote, la que
admite nueve desplazamientos y solo uno cuadra, y la de ambigüedad con dos
precios conocidos) y 6 de la Conciliación (lote en la ficha de otro, mención
sin enlace que no fuerza nada, las dos situaciones de acuerdo marco, el
documento que manda sobre un boletín viejo y el que **no** debe mandar sobre
una anulación).

### Excel

```
C:\dev\ADIF\catalogo_adif_2026-09-18-reproceso-y-conciliacion.xlsx
```

### Comparación con `catalogo_adif_2026-09-18-glifos-y-lotes.xlsx`

| | Antes | Ahora |
|---|---:|---:|
| Filas de "Materiales" | 18.323 | **19.474** (+1.151) |
| Expedientes con filas | 362 | **363** (+1) |
| Materiales distintos (expediente + matrícula + descripción) | 17.323 | **17.408** (+85) |
| Filas de "Conciliación" | 518 | **532** (+14) |

**0 expedientes pierden filas. 0 materiales desaparecen. 0 expedientes
desaparecen.** Las 1.151 filas nuevas están en **15 expedientes**, y cada uno
tiene su causa medida:

| Expediente | Antes | Ahora | Por qué |
|---|---:|---:|---|
| `6.20/28510.0054` … `0058` (5) | 39 | **210** | reparto por lotes del cuadro: su `ANEJO_8.pdf` publica **6 tablas con cabecera "LOTE N: ÁREA TERRITORIAL OPERATIVA …"** (Centro, Noroeste, Norte, Noreste, Este, Sur) con los mismos 35 materiales cada una. Antes se fundían todas en el lote sentinela y quedaban 39 filas sin saber de qué lote era cada precio. |
| `6.21/28510.0141`, `6.22/28510.0011`-`0014` (5) | 4 | **24** | ídem, 6 lotes × 4 materiales |
| `6.22/28510.0094` | 146 | **311** | ídem, 2 lotes |
| `6.17/28510.0056` | 8 | **12** | ídem, 2 lotes (8 + 4) |
| `6.23/28510.0139` | 6 | **12** | ídem, 2 lotes |
| `6.25/28510.0097` | 29 | **32** | ídem, 4 lotes (4 + 22 + 28 + 9) |
| `6.20/28510.0040` | 0 | **18** | **no es el reparto por lotes**: es un pedido que hereda las 18 líneas de su acuerdo marco `6.18/28510.0003`, que se reextrajo en el mismo ciclo (`intentar_heredar_de_matriz`, mecanismo de siempre) |

**Catorce de los quince son el reparto por lotes del propio cuadro de precios**
(`_lotes_candidatos_del_cuadro`), el arreglo de la cuarta parte de esta sesión
que *"solo actúa al reextraer"*. Era el punto 2 de sus pendientes: *"reprocesar
los 91 candidatos y medir en cuántos entra"*. **La respuesta es 14 de 91**; los
otros 77 no pasan la comprobación dura (que el cuadro atribuya TODAS sus filas
a un lote y cubra los N) y se quedan exactamente como estaban, por construcción.

**Ninguno de los 15 gana filas por los glifos.** Los glifos no añaden ni una
fila en todo el corpus: lo que hacen es **rellenar el precio de 35 filas que ya
existían** en `6.26/28510.0064`, 5 de ellas nuevas respecto al Excel anterior
(bloque 5).

Los 85 materiales distintos nuevos son de `6.20/28510.0040` (18, heredados de
su acuerdo marco), `6.22/28510.0094` (63) y `6.17/28510.0056` (4): materiales
que ya estaban en el documento y ahora sí llegan con su lote.

### Cuadre de "Conciliación" con "Materiales"

```
suma de la columna de líneas de "Conciliación": 19.474
filas de la hoja "Materiales":                  19.474
```

0 expedientes sin Situación.

### Auditoría

**0 errores, 6 avisos.** Los seis son los de siempre: 11 grupos de material
repetido con códigos de precio distintos, 19.233 huérfanas sin lote (**la misma
cifra exacta que antes del reproceso**: el reparto por lotes no ha creado ni
una), 2.005 precios atípicos, 941 cantidades con forma de año, 56 grupos de
importe de licitación compartido y 8 de importe repetido en el mismo
expediente.

**La auditoría que corrió dentro del propio ciclo de reproceso sí dio 1 error**,
y conviene decirlo: `lineas_cambian_sin_cambiar_documentos` sobre **exactamente
los 15 expedientes de la tabla de arriba**. Es la regla funcionando como debe —
"cualquier subida es error, sin excepción", la que impide que la atribución
automática se convierta en una puerta de atrás— y los 15 están explicados uno a
uno. La auditoría posterior, la que pedía el encargo, ya no lo marca porque
compara contra esa ejecución: la subida es ya la línea de base.

### Recuento por Situación de la hoja "Conciliación"

| Situación | Expedientes | Antes |
|---|---:|---:|
| Aporta líneas | **363** | 362 |
| Publicado sin cuadro de precios | **64** | 64 |
| Los precios están en un acuerdo marco que no está publicado | **47** | 49 |
| **El acuerdo marco está publicado pero no publica precios unitarios** | **2** | — |
| Documentos escaneados que no se han podido leer | **15** | 15 |
| **Publicado dentro de la ficha de otro expediente** | **14** | — |
| Otro | **27** | 28 |
| Pendiente de procesar | **0** | 0 |
| **Total** | **532** | 518 |

### Pendiente de decisión del cliente

1. **Tres expedientes que sí son lotes de otro y el sistema no los registra
   como tales**: `4.23/28510.0081` (lote de `4.23/28510.0058`),
   `6.19/28510.0213` y `6.19/28510.0216` (lotes 1 y 2 de `6.19/28510.0196`).
   Su Contrato firmado lo dice con todas las letras, pero con una redacción que
   el extractor de lotes no reconoce hoy. Enlazarlos exige ampliar ese
   extractor y verificarlo contra más casos: **no se ha tocado**, por no
   forzar.
2. **Los 77 candidatos al reparto por lotes del cuadro que no entraron.**
   Medidos ya (14 de 91 entran); los 77 restantes no pasan la comprobación dura
   y se quedan como están. Si el cliente quiere que entren, habría que aflojar
   esa comprobación, y eso sí podría perder filas.
3. **`6.26/28510.0064`, lote 3, `P-2`**: la única línea del catálogo sin precio
   por cifras en glifos. Solo se resolvería con el documento original o con que
   ADIF diga el precio.
4. Siguen en pie las de las partes anteriores que no se han cerrado aquí.
