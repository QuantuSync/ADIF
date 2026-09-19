# Sesión 2026-09-19 — El precio que demuestra el documento, el lote que dice el título, y el expediente que era el mismo

Siete bloques. Continúa `docs/sesion-2026-09-18-verificacion-del-reparto-por-lotes.md`,
que cerró con **once decisiones pendientes del cliente**. Aquí se contestan
cuatro y se analizan dos más sin tocar nada.

---

## 1 — Las once decisiones, y cuáles siguen abiertas

| # | Decisión | Estado tras esta sesión | Líneas en juego |
|---|---|---|---:|
| 1 | El cuadro del lote 3 de `6.20/28510.0054`-`0058` se pasa de su presupuesto | **Cerrada aquí**: no hay nada que implementar | 175 filas, 0 se tocan |
| 2 | El dígito mal leído de `6.17/28510.0056` `P-7` | **Contestada** (bloque 2) | ver bloque 2 |
| 3 | Aflojar la garantía del reparto por lotes | **No se afloja** (bloque 5), análisis hecho | +1.971 / −91 |
| 4 | `6.22/28510.0011`-`0014` cargan los 6 cuadros | **Contestada** (bloque 3) | ver bloque 3 |
| 5 | `19/28510` = `6.19/28510.0129` | **Contestada** (bloque 4) | ver bloque 4 |
| 6 | La unidad `PA` no es una unidad de medida | **Abierta** | 67 líneas BD / 33 filas |
| 7 | Errata CONTRAGUJA / CONTRAAGUJA | **Abierta** | 540 líneas BD / 120 filas |
| 8 | Añadir la columna "Código de precio" al Excel | **Abierta** | 25.914 de 39.009 líneas la tienen |
| 9 | Las 2.752 huérfanas de las causas C y D | **Contestada** (bloque 6) | ver bloque 6 |
| 10 | Las 6 descripciones acortadas de `6.24/28510.0171` | **Abierta** | 6 filas |
| 11 | Las decisiones abiertas de las partes anteriores | **Abierta (bolsa)** | — |

### La que se cierra sin implementar nada: la número 1

Las 35 filas del lote 3 de cada uno de los cinco expedientes de traviesas
(175 en total) suman 8.230.002,13 € contra los 8.200.000,00 € que el anuncio
declara para ese lote. **La discrepancia es del documento de ADIF**, verificada
fila a fila contra `ANEJO_8.pdf` en la sesión anterior: las cantidades del
cuadro son las que el PDF imprime. No hay ningún cambio de código que hacer;
lo que hay es algo que contarle a ADIF. Se retira de la lista de pendientes.

### Lo que sigue vivo de las partes anteriores (decisión 11)

- `6.26/28510.0064` lote 3 `P-2`: la única línea del catálogo sin precio, por
  cifras en glifos. Solo la resuelve el documento original o ADIF.
- Si la Situación **"Otro"** (26 expedientes tras la unificación del bloque 4)
  debe partirse en las cuatro categorías reales que conviven ahí.
- **"Comentarios"**: motivo fila a fila, o la nota única del Resumen.
- Los **42 códigos internos repetidos** entre expedientes: vienen del propio
  listado de ADIF.
- **"Órgano de contratación" y "Estado publicado"** solo para 124 de 515.
- **`Precio unitario` = licitado o adjudicado** (CONTEXTO.md sección 16).

---

## 2 — El precio que reescribe la columna de importes, con las dos condiciones

### La regla, tal cual se ha implementado

Un precio unitario solo se reescribe desde la columna de importes del propio
documento cuando se cumplen **las dos condiciones a la vez**:

1. **`importe / cantidad` da exactamente el precio corregido**: división sin
   residuo y con decimales que caben en la columna (4). Con residuo no hay
   ningún precio demostrado y no se toca nada — redondear ahí sería inventar
   justo la cifra que la regla existe para no inventar.
2. **Con ese precio, el lote suma exactamente un total que el propio documento
   declara** al pie de su cuadro ("Presupuesto de Ejecución Material", "SUMA",
   "TOTAL LOTE N", "IVA", "Presupuesto Base de Licitación"...). Se recogen
   todos los del pie sin decidir cuál es cuál: son cifras de órdenes de
   magnitud distintos y que una suma recién corregida caiga al céntimo sobre
   una de ellas no ocurre por azar.

Si falta cualquiera de las dos, **la línea no se corrige** y va a revisión con
su motivo (`MOTIVO_IMPORTE_SIN_CERRAR_EL_LOTE`).

### Dónde vive

- `app.extraccion.mapeo_cabecera.completar_columna_importe`: la columna de
  importes, por coincidencia **exacta** del nombre de cabecera, nunca por
  "contiene". Medido sobre las cabeceras ya cacheadas del corpus: "IMPORTE"
  (68 tablas), "TOTAL" (11), "TOTALES" (6), "IMPORTE (€)" (4), "IMPORTE (€
  Ejecución por Contrata)" (2), "SUBTOTAL" (1). Deliberadamente fuera:
  "IMPORTE UNITARIO" (es un precio unitario, no el total del renglón),
  "IMPORTE COMPRA", "IMPORTE 2024"/"2025", "IMPORTE REPARACIÓN". Campo
  opcional fuera de `CAMPOS`, igual que `CAMPO_CODIGO_MATERIAL`: **el modelo
  nunca lo ve y no se cachea**, así que añadirlo no invalida ni una respuesta
  de cabecera ya aprendida.
- `app.catalogo.importes_de_pie_de_tabla`: los totales que el cuadro declara
  en las filas de resumen que `construir_linea_catalogo` ya descartaba.
- `app.catalogo.corregir_precio_con_importe_del_documento`: la regla, lote a
  lote, sobre las líneas de un documento entero.
- `app.extraccion.pipeline_anejo`: la llama **después** de la segunda vía de
  los glifos, con el documento ya leído entero — la condición 2 es el total
  del *lote*, que puede repartirse en varias tablas y varias páginas.

### La marca, igual que la del reconocimiento óptico

Los mismos tres sitios que `app.extraccion.ocr.marcar_linea_reconocida`:

- **`lineas_catalogo.precio_corregido_desde_importe`** (migración **0039**),
  `True` o ausente, nunca `False`. Es una marca de origen
  (`_MARCAS_DE_ORIGEN`): se recalcula en cada pasada.
- **`motivo_revision`** propio, que dice que el número no salió literal del
  cuadro y hay que confirmarlo contra el documento.
- **`[precio recalculado desde el importe del documento]`** delante del
  fragmento que ancla la línea. El fragmento sigue siendo el texto literal.

Y en la hoja "Resumen" del Excel, su propio recuento con su nota.

### El caso que lo motiva, cerrado

`6.17/28510.0056`, lote 1, `P-7` ("Encarriladora de vía, UIC-55 en recta"):
el reconocimiento óptico leyó **56.555,91 €** donde el PDF pone **56.455,91 €**.
Las dos condiciones se cumplen:

- 451.647,28 / 8 = **56.455,91**, exacto;
- con esa cifra el lote 1 suma **2.975.673,96 €**, exactamente el Presupuesto
  de Ejecución Material que el propio cuadro declara al pie de la p.19.

### Cuántas líneas cumplen cada condición, en todo el corpus

Medido sobre el reproceso completo de los 518 expedientes reextraídos:

| | Líneas | Expedientes |
|---|---:|---:|
| **Cumplen las dos condiciones y se corrigen** | **1** | 1 |
| **Cumplen la primera pero no la segunda** (no se tocan, van a revisión con su motivo) | **7** | 4 |

La única que se corrige es `6.17/28510.0056`, lote 1, `P-7`: **56.555,91 € →
56.455,91 €**, con `precio_corregido_desde_importe = True`, su motivo y el
prefijo en el fragmento (que además ya llevaba el de reconocimiento óptico,
así que la línea dice las dos cosas). Su `Precio adjudicado` sigue vacío
porque ese lote no tiene baja declarada, no por el cambio.

Las **7** que se quedan como estaban, por expediente: `6.17/28510.0123` (4),
`2.23/28510.0049` (1), `6.21/28510.0041` (1), `6.23/28510.0105` (1). En las
cuatro el documento no publica un total de lote con el que cerrar la
aritmética, así que **no se reescribe nada**: es exactamente el caso para el
que existe la segunda condición.

Que de 39.009 líneas solo una pase las dos puertas es el resultado esperado de
una regla acotada: no es un mecanismo que reescriba precios por el corpus, es
un mecanismo que solo actúa cuando el propio documento demuestra la cifra dos
veces.

**Límite conocido, anotado a propósito**: la columna de importes se reconoce
por el nombre de su cabecera, así que una página de *continuación* sin
cabecera propia no la tiene mapeada y sus renglones no entran en la
comprobación. Es el fallo seguro (no corregir) y no el peligroso (corregir mal).

---

## 3 — Los cuatro expedientes de balasto que son ellos mismos un lote

### Por qué no lo sabía el sistema

`6.22/28510.0011`-`0014` comparten **los mismos siete documentos** con sus
hermanos `0015`, `0016` y con el principal `6.21/28510.0141`. De los dos únicos
Contratos publicados en esa ficha, uno declara `6.22/28510.0016 … LOTE 6` y el
otro `6.22/28510.0015 … LOTE 5` — por eso esos dos sí saben cuál es su lote, y
los cuatro primeros no. Ni `_lote_propio` (por código declarado) ni la
identidad de Contrato los alcanzan.

**Lo único que dice qué son es su propio título**: "Lote 1: Jefatura de
Barcelona", "Lote 2: Jefatura de Córdoba", "Lote 3: Jefatura de Burgos",
"Lote 4: Jefatura de Irún".

### La regla, y sus tres condiciones de certeza estructural

`_lote_declarado_en_el_titulo` + `_aplicar_lote_propio_del_titulo`
(`app.extraccion.orquestador`):

1. El título **abre** con "Lote N" (admite "Lote nº N", "LOTE Nº N") seguido
   de su separador real (`:`, `.`, `-`) o de un espacio. Nunca "contiene la
   palabra lote": cualquier pliego multi-lote la dice en su prosa y eso no
   declara nada.
2. **El expediente carga con más de un lote.** Es el problema que la regla
   existe para arreglar. Medido: sin esta condición la regla tocaría **33**
   expedientes en vez de 4 — entre ellos `6.21/28510.0109`, cuyo único lote es
   el sentinela `LOTE_UNICO` ("1") y cuyo título dice, por casualidad, "Lote 1."
3. **El número del título está entre los lotes que el expediente ya tiene**, y
   ninguno de los sobrantes lleva dato propio (baja, importe o código de
   expediente de lote). Un lote con dato propio lo declaró un documento, y
   contra un documento el título no manda.

Con `lote_propio` puesto, `_lotes_candidatos_del_cuadro` ya no intenta el
reparto por lotes del cuadro: este expediente no es la licitación, es uno de
sus contratos.

### Qué pierde cada uno, y adónde va ese material

| Expediente | Antes | Ahora | Pierde | Lotes que suelta |
|---|---:|---:|---:|---|
| `6.22/28510.0011` (Lote 1: Jefatura de Barcelona) | 24 | **4** | **−20** | 2, 3, 4, 5, 6 |
| `6.22/28510.0012` (Lote 2: Jefatura de Córdoba) | 24 | **4** | **−20** | 1, 3, 4, 5, 6 |
| `6.22/28510.0013` (Lote 3: Jefatura de Burgos) | 24 | **4** | **−20** | 1, 2, 4, 5, 6 |
| `6.22/28510.0014` (Lote 4: Jefatura de Irún) | 24 | **4** | **−20** | 1, 2, 3, 5, 6 |
| | **96** | **16** | **−80** | |

**Comprobado material a material: no se pierde nada.** Las 80 filas son 32
combinaciones distintas de (lote, material, precio) — cuatro materiales de
balasto repetidos por lote —, y **las 32 siguen en el Excel**, cada una en el
expediente de su lote y en el principal de la licitación:

| Lote | Material | Dónde está ahora |
|---|---|---|
| 5 | Balasto sobre camión en cantera, 14,20 € | `6.21/28510.0141`, `6.22/28510.0015` |
| 5 | m³ de balasto transportado al punto de carga ofertado, 12,00 € | ídem |
| 5 | Carga y enrasado del balasto en las tolvas, 1,10 € | ídem |
| 5 | m³ × km de balasto a punto de carga distinto, 0,12 € | ídem |
| 6 | los cuatro equivalentes | `6.21/28510.0141`, `6.22/28510.0016` |
| 1-4 | ídem | `6.21/28510.0141` y el expediente de cada lote |

La familia queda por fin coherente: **cada uno de los seis expedientes de lote
lleva sus 4 filas, y el principal `6.21/28510.0141` lleva las 24** (los seis
cuadros, que es lo que de verdad publica).

Y las tres claves de material del Excel no se mueven ni una unidad: por
matrícula **11.832 = 11.832**, por matrícula y precio **11.895 = 11.895**, por
lote + matrícula + precio **13.182 = 13.182**, con **0 perdidos** en las tres.

### Cuántos más hay en la misma situación

**Once expedientes más** declaran un lote concreto en su título y cargan con
más de un lote — pero en los once **el lote del título no está entre los que
tienen**, así que la tercera condición no se cumple y **se quedan exactamente
como están**:

| Expediente | Dice el título | Lotes que tiene |
|---|---|---|
| `6.21/28510.0135` | Lote 6 | 1, 3, 7 |
| `6.21/28510.0137` | Lote 8 | 1, 3, 7 |
| `6.21/28510.0138` | Lote 9 | 1, 3, 7 |
| `6.22/28510.0139` | Lote 1 | 5, 6 |
| `6.22/28510.0140` | Lote 2 | 5, 6 |
| `6.22/28510.0142` | Lote 4 | 5, 6 |
| `6.22/28510.0147` | Lote 1 | 4, 5 |
| `6.22/28510.0148` | Lote 2 | 4, 5 |
| `6.22/28510.0149` | Lote 3 | 4, 5 |
| `6.23/28510.0073` | Lote 1 | 3, 4 |
| `6.23/28510.0074` | Lote 2 | 3, 4 (0 líneas) |

Estos **no** son el mismo caso que los cuatro del balasto: sus lotes no salen
del reparto del cuadro sino de sus propios documentos, y el número del título
no coincide con ninguno. Atribuirles el lote del título significaría borrar
todos sus lotes y quedarse sin ninguno. **Decisión del cliente pendiente**, y
mientras tanto no se tocan.

Otros **29 expedientes** tienen el título con forma "Lote N" y ya tienen
exactamente ese único lote: no multiplican nada y la regla no los toca.

---

## 4 — `19/28510` y `6.19/28510.0129`, unificados

### Lo que había

| | `6.19/28510.0129` | `19/28510` |
|---|---|---|
| `id` | 509 | 562 |
| Creado | 16/09 07:51:42,241 | 16/09 07:51:42,351 |
| Título | el mismo | el mismo |
| Importe / adjudicación / baja | 7.800.000 € / 7.800.000 € / 10,25 % | idénticos |
| Documentos | los mismos dos (mismos `id`, mismo hash) | los mismos |
| Líneas de catálogo | 0 | 0 |

Los creó la misma ejecución del barrido del buscador con **0,1 s de
diferencia**. `19/28510` es `6.19/28510.0129` recortado: el buscador de la
Plataforma devuelve subcadenas y `app.criterio_expediente` las acepta a
propósito ("sin mirar la forma del resto del código", decisión del cliente de
la sesión 2026-09-15). Confirmación independiente: el propio motivo de revisión
de `19/28510` ya decía que su documento de adjudicación *"no menciona este
expediente […] pero sí menciona otros (6.19/28510.0129)"*.

### La fusión

`app.extraccion.identidad_expediente.detectar_expediente_recortado` resuelve el
caso que el docstring de `corregir_identidad_expediente` dejaba explícitamente
fuera ("un caso de fusión, no de renombrado"). **Tres condiciones, ninguna de
parecido**:

1. su código es una **subcadena** del del otro, y más corto;
2. los dos cuelgan **exactamente del mismo conjunto de documentos**, y no está
   vacío — el mismo fichero (mismo hash) bajo los dos códigos es la prueba de
   que la Plataforma los publicó en una sola ficha;
3. declaran el **mismo título**.

Con varios candidatos no se fusiona nada. `fusionar_en` reapunta al canónico
lotes, líneas, trabajos de cola, entradas de sindicación y referencias de
matriz, borra los enlaces de documento redundantes (ya son los mismos) y borra
la fila duplicada. Se ejecuta **antes de extraer nada**: extraer un expediente
que no existe sería anclar datos a una identidad falsa.

### El resultado, comprobado

`19/28510` **ya no existe** y `6.19/28510.0129` conserva todo:

| | Antes | Ahora |
|---|---:|---:|
| Expedientes en la base | 613 | **612** |
| Documentos de `6.19/28510.0129` | 2 | **2** |
| Lotes | 1 + 1 | **1** |
| Líneas de catálogo | 0 + 0 | **0** (ninguno de los dos aportaba ninguna) |
| Trabajos de cola | 8 + 8 (+2 del ciclo) | **18**, todos en el código completo |
| `Código interno` | 19007 (solo el completo cruzaba) | **19007** |
| Filas de "Conciliación" | 535 | **534** |

**Ni una fila huérfana apuntando al código viejo.** Comprobado, `id` 562 y su
lote 1146, tabla por tabla:

```
lineas_catalogo          0      documento_expedientes   0
lotes                    0      trabajos_cola           0
sindicacion_expedientes  0      trazas_origen (exp)     0
trazas_origen (lote)     0      matriz_expediente_id    0
```

Ninguna línea de catálogo se mueve porque ninguno de los dos tenía. El único
cambio en el entregable es que la hoja "Conciliación" pasa de 535 a 534 filas:
la Situación **"Otro"** baja de 27 a 26, que era donde estaba el fantasma.

### ¿Hay más expedientes fantasma de esa forma?

**No: uno solo en los 613.** La comprobación se hizo sobre el corpus entero
buscando pares que cumplan las tres condiciones. Solo `19/28510` /
`6.19/28510.0129` las cumple.

**Un aviso de paso, de otra forma distinta**: `6.25/28510.5001/01` y
`6.25/28510.5001_01` son el mismo número escrito con dos separadores
distintos (`/` y `_`). Los dos están `sin_publicar`, **sin ningún documento y
sin ninguna línea**, y uno de los dos ni siquiera tiene título — así que la
segunda condición (el mismo fichero bajo los dos códigos) no se puede
comprobar y la fusión **no se aplica**. No afecta al entregable: ninguno de
los dos aparece en "Materiales" ni en "Conciliación". Queda anotado.

---

## 5 — Los 16 que la garantía rechaza: qué queda huérfano y por qué

**No se ha tocado la garantía.** Solo el análisis, reprocesando en seco los 29
candidatos vivos (`_lotes_candidatos_del_cuadro`) con sus N lotes declarados.

| Expediente | Declara | Documento | Líneas | Cubre | Huérfanas | Motivo de las huérfanas |
|---|---:|---|---:|---|---:|---|
| `6.18/28510.0109` + 11 hermanos `6.19/28510.00xx` | 40 | `ANEJO_2.pdf` | 164 | **40/40** | **4** | ninguna cabecera LOTE en la franja |
| `6.22/28510.0173` | 2 | `ANEJO_1.pdf` | 551 | **2/2** | **183** | **anejo de criterios técnicos, del conjunto de los lotes** |
| `6.25/28510.0171` | 2 | `ANEJO_1.pdf` | 42 | **2/2** | **21** | **anejo de criterios técnicos, del conjunto de los lotes** |
| `4.25/28510.0132` | 2 | `ANEJO_1.pdf` | 134 | **2/2** | **106** | banda vacía (93) + tabla separada por páginas (13) |
| `6.21/28510.0108`-`0111` | 5 | `ANEJO_3.pdf` | 196 | 0/5 | 196 | anejo de criterios técnicos (el cuadro no declara ningún lote) |
| `4.23/28510.0058` | 2 | `CONTRATO_1.pdf` | 4 | 0/2 | 4 | ninguna cabecera LOTE en la franja |

*(El reproceso en seco corre sin modelo, así que unos pocos expedientes salen
"sin líneas" que en el ciclo real sí las tienen; las cifras de la tabla son las
de los que sí producen cuadro.)*

### El hallazgo que el cliente pedía buscar

> *"Si en alguno la huérfana es una fila de resumen o de partida alzada que
> legítimamente no pertenece a ningún lote, dímelo, porque entonces la garantía
> se puede afinar sin aflojarla."*

**Sí, en dos, y al 100 %:**

- **`6.22/28510.0173`**: sus **183** huérfanas son, todas, del **anejo de
  criterios técnicos** — la lista de materiales que el propio documento declara
  *del conjunto de los lotes* ("materiales a suministrar en el expediente …
  N LOTES", CONTEXTO.md sección 7). Esas filas **no pueden tener lote por
  diseño**: lo tendrían igual de huérfano entrara o no el reparto.
- **`6.25/28510.0171`**: lo mismo, sus **21** huérfanas.

Es decir: **la garantía rechaza esos dos expedientes por filas que serían
huérfanas de todas formas**. Se puede afinar sin aflojar nada — no contando
como huérfanas las del anejo de criterios, que ya tienen su propia categoría
en el Resumen y su propio motivo.

Y lo que importa para la decisión 3: **`4.25/28510.0132`, el único de los
quince que perdía 91 filas, seguiría rechazado** con ese afinado. Sus 106
huérfanas son "banda vacía" (93) y "tabla separada de la anterior por páginas
sin tabla" (13), no criterios técnicos.

Las **4 huérfanas de los doce expedientes de 40 lotes** (`P-1`, `P-3`, `P-4`,
`P-5` de la p.29 del `ANEJO_2.pdf`) **no** son de criterios: son un cuadro de
precios de referencia sin cabecera de lote, y solo una de las cuatro (`P-4`,
"Partida alzada a justificar de acondicionamiento de puntos de carga") es una
partida alzada. Las otras tres son material real sin cantidad. Con el afinado
de arriba seguirían rechazando el intento.

**No se ha aplicado ningún cambio a la garantía.**

---

## 6 — Las 2.752 huérfanas que "deberían tener lote": medidas tabla a tabla

### Qué son de verdad

Se ha replicado la etapa 3.5 sobre los documentos reales de los 29 expedientes
afectados, imprimiendo, tabla a tabla, su franja, su lote asignado y su
posición. El resultado contradice la hipótesis de la sesión anterior (*"la D
tiene un camino claro"*):

| Expediente | Líneas | Qué es de verdad |
|---|---:|---|
| `6.21/28510.0112` / `0113` | 1.910 | El cuadro está en CID glifos sin tabla de caracteres: la franja es ilegible, la última mención de lote antes del cuadro es "LOTE 1", y el Contrato incluye el pliego entero. **No hay certeza estructural de ningún tipo.** |
| `6.23/28510.0097` | 210 | Continuaciones de los `ANEJO Nº 1/2/3 … LOTE 1/2/3`, que **no son lotes de este expediente** (sus lotes son el 4 y el 5). |
| `4.26/28510.0020` | 184 | Continuaciones de la tabla de la p.39, que la sesión 2026-09-14 ya determinó que **no es del lote 2**: es el cuadro de la partida alzada, común a los dos lotes, 22 páginas después. |
| `6.24/28510.0130`/`0152`/`0153` | 111 | Continuaciones de los cuadros de los **LOTE 2, 10 y 13**, que no son suyos (su lote es el 5). |
| `6.20/28510.0059` / `0060` | 96 | Continuaciones de cuadros de los lotes 1, 2 y 4. |
| `6.21/28510.0058`/`0130`/`0135`-`0138` | 180 | Continuaciones del cuadro del **LOTE 8 – SUJECIONES**. |
| Resto (18 expedientes) | 61 | Mismo patrón, de 1 a 14 líneas cada uno. |

**En todos los casos examinados, la línea huérfana es la página de continuación
del cuadro de OTRO lote.** Atribuirla al lote de este expediente metería el
material del hermano en su ficha — exactamente el error que el bloque 3 acaba
de quitarle a `6.22/28510.0011`-`0014`.

### Qué se ha hecho, entonces

**No se atribuye ninguna**, que es lo que el encargo manda cuando no hay
certeza ("La que no se pueda atribuir con certeza se queda sin lote, como está
hoy"). Lo que sí cambia es **que la línea diga la verdad**:

`ResultadoAsociacionLote.identificador_no_declarado` saca de la etapa 3.5 el
número de lote que la franja **sí** nombraba y que resultó no estar entre los
declarados; `procesar_anejo` lo arrastra por la cadena de continuaciones
(y la corta en cuanto aparece cualquier rastro propio, una tabla del conjunto
o un salto de páginas). Esas líneas pasan de

> *"ninguna cabecera LOTE N encontrada en la franja que precede a esta tabla"*

a

> *"continuación del cuadro del LOTE N, que no está entre los lotes declarados
> de este expediente: el material es de un lote hermano de la misma licitación
> y sale en el expediente de ese lote, no en este"*

con su propia categoría en la hoja "Resumen" del Excel. **Ni una línea cambia
de lote, ni entra ni sale ninguna del entregable.**

### Las cifras que pedía el encargo

| | Líneas | Expedientes |
|---|---:|---:|
| De las 2.752, **atribuidas a un lote** | **0** | 0 |
| De las 2.752, **pasan a decir de qué cuadro son** (siguen sin lote) | **1.806** | 20 |
| De las 2.752, **se quedan exactamente como estaban** | **946** | 11 |
| **Huérfanas en total al final** | **19.313** | 112 |

1.806 + 946 = 2.752, al dedillo.

Las **946** que siguen igual, por expediente:

| Expediente | C | D |
|---|---:|---:|
| `6.21/28510.0112` | 239 | 117 |
| `6.21/28510.0113` | 239 | 117 |
| `4.26/28510.0020` | 0 | 184 |
| `2.23/28510.0049` | 14 | 0 |
| `6.23/28510.0051` | 12 | 0 |
| `3.21/28510.0158` | 0 | 7 |
| `6.22/28510.0122` | 6 | 0 |
| `6.23/28510.0105` | 4 | 0 |
| `6.22/28510.0155` / `0156` | 3 + 3 | 0 |
| `3.22/28510.0048` | 1 | 0 |
| **Total** | **521** | **425** |

### Las huérfanas totales, por causa

| Causa | Líneas | Expedientes |
|---|---:|---:|
| **A.** Anejo de criterios técnicos (del conjunto de los lotes) | 13.432 | 43 |
| **B.** La tabla declara un LOTE que este expediente no declara | 2.518 | 69 |
| **B2.** Continuación del cuadro de otro lote *(categoría nueva)* | **1.806** | 20 |
| **C.** Ninguna cabecera de lote en la franja | 521 | 9 |
| **F.** Otros (columna fantasma, descripción recuperada…) | 510 | 19 |
| **D.** Banda vacía | 425 | 4 |
| **E.** Tabla separada por páginas sin tabla | 67 | 5 |
| **G.** La última mención de lote es de otro lote | 34 | 4 |
| **Total** | **19.313** | 112 |

De 19.233 a 19.313: **+80**, y son exactamente las 80 filas que el bloque 3
le quita a `6.22/28510.0011`-`0014`. No se pierden del catálogo — salen en el
expediente de su lote y en el principal (bloque 3) —, pero en estos cuatro
pasan de estar en un lote que no era el suyo a no tener lote, que es lo
correcto.

---

## 7 — Cierre

### Pruebas

**1.141 pasan** (1.104 al cerrar la sesión anterior, **+37**). Ninguna saltada.
Las nuevas: 12 del bloque 2 (las dos condiciones, cada una con su mitad
contraria: sin total declarado, con un total que difiere en un céntimo, sin
cantidad en una fila, división con residuo, precio que ya cuadra, dos lotes que
no se prestan su total), 9 del bloque 3 (las tres condiciones de certeza
estructural y las doce formas reales del título), 12 del bloque 4 (las tres
condiciones del recorte y la fusión sin dejar nada apuntando al código viejo) y
4 del bloque 6.

### El reproceso completo, con la red apagada

`POST /mantenimiento/ejecutar` con `forzar: true`, `sindicacion_desactivada:
true` y `busqueda_desactivada: true`. **518 expedientes reextraídos**, 520
evaluados, **19 minutos y 11 segundos** (1.151,3 s).

| | |
|---|---|
| `descargas_lanzadas` | **0** |
| `saltados_descarga` | 520 |
| `sin_publicar_reintentados` | **0** |
| `sin_publicar_desactivado` | **True** |
| `descubrimiento` | `None` |
| `descubrimiento_busqueda` | `None` |

Cero peticiones a la Plataforma.

### Comparación con `catalogo_adif_2026-09-18-verificacion-reparto.xlsx`

| | Antes | Ahora |
|---|---:|---:|
| Filas de "Materiales" | 19.553 | **19.473** (−80) |
| Columnas | 17 | **17** (=) |
| Expedientes con filas | 363 | **363** (=) |
| Filas de "Conciliación" | 535 | **534** (−1) |
| Materiales distintos **por matrícula** | 11.832 | **11.832** (=) |
| Materiales distintos **por matrícula y precio** | 11.895 | **11.895** (=) |
| Materiales distintos **por lote, matrícula y precio** | 13.182 | **13.182** (=) |

**0 expedientes desaparecen del Excel, 0 expedientes nuevos, y ni un material
se pierde** por ninguna de las tres claves.

**Cada diferencia, una a una:**

1. **−80 filas, en cuatro expedientes y solo cuatro** — `6.22/28510.0011`,
   `0012`, `0013`, `0014`, −20 cada uno. **Es la bajada esperada del bloque 3.**
   Ningún otro expediente cambia de número de filas.
2. **1 fila cambia de precio**: `6.17/28510.0056`, lote 1, "Encarriladora de
   vía, UIC-55 en recta", **56.555,91 → 56.455,91 €**. Es la corrección del
   bloque 2, y es la única del corpus.
3. **−1 fila en "Conciliación"** (535 → 534): la Situación "Otro" baja de 27 a
   26 porque `19/28510` deja de existir. Es la unificación del bloque 4.

No hay ninguna diferencia más. **Ninguna es inesperada.**

### Cuadre de "Conciliación" con "Materiales"

```
suma de la columna de líneas de "Conciliación": 19.473
filas de la hoja "Materiales":                  19.473
```

0 expedientes sin Situación.

### Auditoría

**0 errores y 6 avisos**, los mismos seis de siempre:

| Aviso | Antes | Ahora |
|---|---:|---:|
| Grupos de material repetido con códigos de precio distintos | 11 | **11** |
| Huérfanas sin lote | 19.233 | **19.313** (+80, bloque 3) |
| Precios atípicos | 1.488 | **1.488** |
| Cantidades con forma de año | 941 | **941** |
| Grupos de importe de licitación compartido | 56 | **54** (−2, bloque 4) |
| Expedientes con importe repetido entre sus lotes | 8 | **8** |

Los dos grupos de importe compartido que desaparecen son los que formaba
`19/28510` con `6.19/28510.0129` a través de sus dos documentos comunes: la
fusión los deshace.

### Recuento por Situación de la hoja "Conciliación"

| Situación | Expedientes | Antes |
|---|---:|---:|
| Aporta líneas | **363** | 363 |
| Publicado sin cuadro de precios | **64** | 64 |
| Los precios están en un acuerdo marco que no está publicado | **47** | 47 |
| El acuerdo marco está publicado pero no publica precios unitarios | **2** | 2 |
| Publicado dentro de la ficha de otro expediente | **17** | 17 |
| Documentos escaneados que no se han podido leer | **15** | 15 |
| Otro | **26** | 27 |
| Pendiente de procesar | **0** | 0 |
| **Total** | **534** | 535 |

**Filas totales de "Materiales": 19.473.** Líneas en la base de datos: 39.009
en 612 expedientes.

### Excel

```
C:\dev\ADIF\catalogo_adif_2026-09-19-precio-desde-importe.xlsx
```

---

## Pendiente de decisión del cliente

1. **La unidad `PA`** (33 filas del Excel) no es una unidad de medida sino
   "partida alzada". Lo honesto sería dejar la celda vacía con motivo "no
   aplica". Sin tocar.
2. **La errata CONTRAGUJA / CONTRAAGUJA**: 540 líneas de la base dicen
   "CONTRAGUJA" (120 filas del Excel). La pregunta para ADIF sigue redactada y
   lista. Sin tocar.
3. **La columna "Código de precio" en el Excel**: la tendrían 8.911 de 19.473
   filas. Sin añadir.
4. **Las 6 descripciones de `6.24/28510.0171`** que quedan más cortas tras
   fundirse con su duplicado. Sin tocar.
5. **Afinar la garantía del reparto por lotes sin aflojarla** (bloque 5): no
   contar como huérfanas las filas del anejo de criterios técnicos, que no
   pueden tener lote por diseño. Entrarían `6.22/28510.0173` y
   `6.25/28510.0171`, y `4.25/28510.0132` **seguiría rechazado** — que era el
   único que perdía filas. **Medido, no aplicado.**
6. **Los once expedientes cuyo título declara un lote que no está entre los
   suyos** (bloque 3): `6.21/28510.0135`/`0137`/`0138`,
   `6.22/28510.0139`/`0140`/`0142`/`0147`/`0148`/`0149`,
   `6.23/28510.0073`/`0074`. Sin tocar.
7. **Las 946 huérfanas de las causas C y D que quedan** (bloque 6): 712 de
   ellas están en `6.21/28510.0112`/`0113`, cuyo cuadro llega en glifos CID sin
   tabla de caracteres. Solo las resuelve una revisión manual del documento.
8. **`6.26/28510.0064` lote 3 `P-2`**: la única línea del catálogo sin precio.
9. Si la Situación **"Otro"** (26 expedientes) debe partirse en categorías con
   nombre propio.
10. **"Comentarios"**: motivo fila a fila o la nota única del Resumen.
11. **`Precio unitario` = licitado o adjudicado** (CONTEXTO.md sección 16),
    nunca confirmado por el cliente.
12. Siguen en pie las demás decisiones abiertas de las partes anteriores.
