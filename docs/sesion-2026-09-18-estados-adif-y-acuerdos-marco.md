# Sesión 2026-09-18 (tercera parte) — Listado de estados de ADIF, los 3 expedientes del 6.26 que faltaban, los acuerdos marco de EPIs y la validación por contraste

Siete bloques. El catálogo pasa de **37.638 a 37.705 líneas** y el Excel de
**18.239 a 18.293 filas**: **0 filas perdidas, 0 materiales desaparecidos**.

---

## Bloque 1 — El listado de estados de ADIF

### Nombre y renombrado

El fichero estaba en `Ejemplo/Input/` con **doble extensión**:

```
estados_expedientes_28510_20260918.xlsx.XLSX   →   estados_expedientes_28510_20260918.xlsx
```

### Procedencia (escrita aquí y en CONTEXTO.md, tal cual)

**Nos lo envió ADIF el 18/09/2026. Su origen es una transacción de SAP
ejecutada por ellos.** En su día se nos indicó no utilizar volcados de SAP, así
que preguntamos expresamente en el grupo si podíamos usar este, y **nos
autorizaron a usarlo**. **No lo hemos sacado nosotros de ningún sistema.**

### Qué trae

Una sola hoja, rango `A1:D359`, **cuatro columnas**, sin columnas ocultas
(comprobado sobre el XML crudo del `.xlsx`, no solo con la librería):

| Columna | Contenido |
|---|---|
| Título del expediente | texto |
| Expediente ADIF | código |
| Fecha de creación | 19/04/2016 – 23/06/2026 |
| Descripción del estado | En ejecución 213, Finalizado 95, Desierto 20, En finalización 13, En adjudicación 8, En licitación 8, Desistido 1 |

**358 filas, 358 códigos distintos, 0 repetidos, los 358 del departamento
28510.** Ninguna fila sin código, sin título, sin fecha ni sin estado.

### Lo que NO trae, y paró parte del encargo

**No trae presupuesto de licitación ni órgano de contratación.** Tampoco los
trae ningún otro fichero de ADIF que ya tengamos (el de ejecución SAP son 3
columnas, el de códigos 5, el de traviesas 11; ninguno con importe de
licitación). Consecuencias, consultadas con el cliente antes de seguir:

- **Bloque 3**: "Órgano de contratación" **no se puede rellenar** desde aquí.
- **Bloque 7**: la validación de importes **no se puede hacer** tal como estaba
  escrita. Decisión del cliente: sustituirla por el contraste de estados (ver
  bloque 7) y dejar dicho qué haría falta para la de importes.

### Cómo entra en el sistema

Módulo propio, `app.extraccion.estados_adif` (`ESTADOS_ADIF_PATH`,
bind-mount, `POST /mantenimiento/estados-adif/cargar`, repetible), migración
**0037** (`expedientes.estado_adif`, `estado_adif_creado_en`,
`estado_adif_actualizado_en`). Tres decisiones deliberadas:

1. **No decide si un expediente está publicado.** Esa lógica sigue apoyándose
   solo en la Plataforma (`app.conciliacion.consta_publicado`: sindicación,
   búsqueda directa o documento descargado). Requisito explícito del encargo.
2. **No da de alta ningún expediente.** `estado_sap.cargar_estado_sap` sí lo
   hace (y debe: en su día era la única fuente de la que el sistema podía saber
   que 327 expedientes existían). Aquí, crear lo que no tenemos convertiría la
   pregunta del bloque 2 en una que se contesta sola y en falso.
3. **No escribe en `estado_contrato_sap`.** Las dos fuentes son volcados de SAP
   y comparten vocabulario, pero **son volcados distintos**: 212 códigos en
   común, 155 solo en el anterior, 146 solo en este. (En los 212 comunes el
   estado coincide en los 212 — las dos fuentes no se contradicen.) Compartir
   campo dejaría cada valor sin procedencia.

Carga real: `filas_leidas: 358`, `codigos_distintos: 358`,
`expedientes_actualizados: 358`, **`sin_expediente_en_el_sistema: 0`**.

---

## Bloque 2 — Sus 358 contra los nuestros

Las tres listas que pedía el encargo, medidas expediente a expediente contra el
Excel entregado ayer (`catalogo_adif_2026-09-18-conciliacion.xlsx`):

| Lista | Recuento | Códigos |
|---|---:|---|
| En su listado y **no existen** en nuestro sistema | **0** | **lista vacía** |
| En su listado, existen y **no aportan ninguna línea** | **0** | **lista vacía** |
| **Aportan líneas** y no están en su listado | **0** | **lista vacía** |

**Las tres salen vacías, y no por casualidad: los dos conjuntos son el mismo.**
Comprobado por igualdad de conjuntos y por `md5` de las dos listas ordenadas:

```
md5 de sus 358 códigos              016a98f7aa967276dcb76df24b235b15
md5 de nuestros 358 con filas       016a98f7aa967276dcb76df24b235b15
```

**Esto hay que decírselo al cliente tal cual, porque cambia lo que el cruce
prueba.** Un listado sacado de SAP no tiene por qué coincidir, expediente a
expediente, con "los expedientes de los que hemos conseguido extraer líneas":
son dos criterios sin relación (el segundo depende de qué publica la Plataforma
de cada uno — anejo de precios, documento escaneado, acuerdo marco no
publicado). Que coincidan los 358 de 358 admite dos lecturas: o el listado se
generó a partir de nuestro propio catálogo, o es una coincidencia
extraordinaria. **Conviene confirmarlo con ADIF antes de presentar el "0
discrepancias" como prueba de cobertura**: si el fichero no es independiente,
el cruce no demuestra nada sobre lo que falta.

Los 358 de su listado están, además, **los 358 en la hoja "Conciliación"**.

### Después del trabajo de hoy

Los bloques 5 y 6 añaden 4 expedientes que aportan filas y **no** están en su
listado — coherente, porque su listado es anterior a que se publicaran:

| Expediente | Filas nuevas en el Excel | De dónde sale |
|---|---:|---|
| `6.26/28510.0057` | 7 | bloque 5 |
| `6.26/28510.0083` | 15 | bloque 5 |
| `6.26/28510.0096` | 26 | bloque 5 |
| `6.25/28510.0081` | 6 | bloque 6 (herencia por lote declarado) |

---

## Bloque 3 — La hoja "Conciliación" completada

### Columna nueva, nunca mezclada

`COLUMNAS_CONCILIACION` pasa de 10 a **11**: entra **"Estado según ADIF"**,
justo detrás de "Estado que consta publicado en la Plataforma" y **en columna
aparte**. Son dos hechos distintos y de dos fuentes distintas — el estado del
anuncio frente al estado del contrato — y juntarlos haría imposible saber cuál
se está leyendo. El Resumen lo dice con todas las letras:

> La columna "Estado según ADIF" de esa hoja NO sale de la Plataforma: es el
> estado de contratación que ADIF nos envió el 18/09/2026 […] sacado por ellos
> de una transacción de SAP y facilitado con su autorización expresa. […] Ese
> listado no interviene en ningún momento en decidir si un expediente consta
> publicado o no — eso lo decide solo la Plataforma.

Un expediente que no figura en su listado no sale con la celda en blanco:
*"no consta (este expediente no figura en el listado de estados que ADIF envió
el 18/09/2026)"*.

### Cobertura final

| | Filas de "Conciliación" |
|---|---:|
| Total | **518** |
| Con **Estado según ADIF** | **358** |
| Con **Estado publicado en la Plataforma** (sindicación) | **124** |
| Con **los dos** | 102 |
| **Sin estado por ninguna de las dos vías** | **138** |

**"Órgano de contratación" sigue en 124 de 518**, y no puede mejorar con este
fichero: no trae esa columna. Para rellenarlo haría falta guardar la ficha que
muestra el buscador de la Plataforma, no solo el número — sigue siendo una vía
de descubrimiento nueva, no un arreglo.

---

## Bloque 4 — Los grupos que no se explican solos

### Los 2 "Pendiente de procesar": procesados, y la etiqueta estaba mal

`6.14/28510.0148` y `6.14/28510.0177`. Relanzados hoy (quinta y sexta búsqueda
real): la Plataforma **los encuentra** (`encontrado_como` con su propio número)
y devuelve **cero documentos descargables**, igual que las cuatro veces
anteriores (16/09 21:19, 17/09 07:54, 08:44, 10:09).

```
{"documentos": {"ANEJO": 0, "PLIEGO": 0, "CONTRATO": 0, "ADJUDICACION": 0},
 "enlaces_nuevos": 0, "encontrado_como": "6.14/28510.0177", "documentos_nuevos": 0}
```

No hay nada pendiente que hacer con ellos, así que llamarlos "Pendiente de
procesar" prometía un trabajo que no existe. `_situacion` distingue ahora las
dos causas de "cero documentos":

- **nunca se ha ido a buscar** (`descargado_en is None`) → sigue siendo
  "Pendiente de procesar";
- **ya se buscó y su ficha no publica ningún documento** → "Publicado sin
  cuadro de precios", con el motivo *"Se ha buscado en la Plataforma y su ficha
  aparece, pero no publica ningún documento que se pueda descargar: ni anuncio,
  ni contrato, ni anejo de precios. No es que falte leerlo, es que no hay nada
  publicado que leer."*

**"Pendiente de procesar" queda en 0.**

### Los 19 de "Otro", con su motivo real y si tienen arreglo

| Expedientes | Qué les pasa de verdad | ¿Arreglo? |
|---|---|---|
| `2.19/28510.0145`, `3.19/28510.0218`, `3.21/28510.0096`, `3.21/28510.0098`, `3.21/28510.0158`, `3.22/28510.0009`, `3.22/28510.0048`, `3.22/28510.0106`, `6.19/28510.0206`, `6.23/28510.0105`, `6.24/28510.0113` (11) | cobertura parcial: de los N lotes declarados, solo algunos traen baja o importe | **No a corto plazo.** Es el pendiente mayor ya abierto en CONTEXTO.md sección 16: separar de verdad cada lote en su expediente propio. Cambio de modelo de datos, no un arreglo. |
| `3.20/28510.0071` (4 lotes) | el Anuncio de adjudicación agrupa varios lotes en un documento y no se puede atribuir el bloque a este expediente sin adivinar | **No sin riesgo.** Atribuir por parecido de texto es justo lo que el sistema se niega a hacer. |
| `6.19/28510.0228` | su lote propio (lote 2) no trae baja ni importe en ningún documento | **No.** El dato no está publicado. |
| `6.19/28510.0230`, `6.25/28510.0219` | bajas declaradas en documentos compartidos con expedientes hermanos, cada uno con su "Contrato nº" y ninguno el suyo | **Quizá.** Haría falta casar "Contrato nº" con el expediente; hoy se descarta para no atribuir la baja de otro lote. |
| `6.20/28510.0002`, `6.20/28510.0003` | su matriz `6.19/28510.0230` tampoco tiene cuadro ni baja | **No** mientras la matriz siga así. |
| `6.23/28510.0074` | el documento declara "EXPEDIENTE PRINCIPAL/ORIGEN" `6.23/28510.0066`, distinto del expediente bajo el que está archivado | **Quizá**, decidiendo qué manda cuando el documento y el archivo discrepan. |
| `6.25/28510.0081` | su matriz `6.25/28510.0028` es multi-lote (6) y el pedido "no declaraba" a cuál pertenece | **SÍ, arreglado hoy** (bloque 6): declara "Lote 2: Base en Sanchidrián" en su propio título publicado. **6 líneas y baja 0,10 %.** Pasa a "Aporta líneas". |

### Los 31 de documentos escaneados: el grupo se reduce a **15**

Páginas y reconocimiento óptico de los 31, medido documento a documento
(154 documentos, 3.165 páginas en total):

| Expediente | Docs | Págs. | Escaneados | Págs. escaneadas | Con OCR parcial |
|---|---:|---:|---:|---:|---:|
| `19/28510` | 2 | 91 | 1 | 89 | 0 |
| `2.18/28510.0089` | 5 | 70 | 1 | 46 | 1 |
| `2.19/28510.0015` | 7 | 103 | 1 | 42 | 1 |
| `2.20/28510.0118` | 2 | 5 | **0** | 0 | 0 |
| `3.16/28510.0044` | 5 | 171 | 2 | 164 | 1 |
| `3.16/28510.0156` | 7 | 162 | 3 | 117 | 2 |
| `3.17/28510.0008` | 7 | 60 | 4 | 53 | 1 |
| `3.17/28510.0028` | 4 | 68 | 2 | 63 | 1 |
| `3.17/28510.0094` | 7 | 161 | 4 | 153 | 3 |
| `3.18/28510.0047` | 5 | 127 | 3 | 114 | 1 |
| `3.19/28510.0016` | 6 | 53 | 2 | 44 | 1 |
| `3.19/28510.0017` | 5 | 52 | 1 | 38 | 1 |
| `3.19/28510.0141` | 5 | 402 | 1 | 81 | 1 |
| `3.19/28510.0198` | 6 | 93 | 1 | 6 | 0 |
| `3.19/28510.0201` | 3 | 72 | 1 | 10 | 0 |
| `6.15/28510.0080` | 4 | 76 | 1 | 36 | 1 |
| `6.15/28510.0094` | 4 | 45 | 1 | 38 | 0 |
| `6.17/28510.0012` | 7 | 86 | 4 | 79 | 2 |
| `6.17/28510.0045` | 4 | 78 | 2 | 73 | 1 |
| `6.17/28510.0116` | 5 | 65 | 2 | 58 | 1 |
| `6.18/28510.0050` | 2 | 4 | 1 | 2 | 0 |
| `6.18/28510.0051` | 2 | 3 | 1 | 1 | 0 |
| `6.18/28510.0064` | 6 | 171 | 2 | 94 | 1 |
| `6.18/28510.0071` | 6 | 189 | 3 | 182 | 1 |
| `6.19/28510.0129` | 2 | 91 | 1 | 89 | 0 |
| `6.19/28510.0131` | 7 | 141 | 1 | 75 | 1 |
| `6.19/28510.0179` | 8 | 135 | 1 | 16 | 0 |
| `6.19/28510.0209` | 8 | 135 | 1 | 16 | 0 |
| `6.19/28510.0210` | 8 | 135 | 1 | 16 | 0 |
| `6.20/28510.0040` | 2 | 4 | **0** | 0 | 0 |
| `6.20/28510.0089` | 3 | 117 | 1 | 1 | 0 |
| **Total** | **154** | **3.165** | **50** | **1.796** | **22** |

Dos hallazgos:

1. **Dos de los 31 no tienen ni un solo documento escaneado** (`2.20/28510.0118`
   y `6.20/28510.0040`): entraban en el grupo porque la palabra "escaneado"
   aparecía en el motivo… de su **matriz**, no de ellos.
2. **Los 22 documentos con reconocimiento óptico incompleto son todos
   `ANEJO_2/3/4.pdf` clasificados como pliego administrativo.** No es un hueco:
   `app.extraccion.ocr` lee las primeras páginas, decide que es un pliego sin
   precios (CONTEXTO.md sección 5) y no gasta el resto. No hay nada que ganar
   ahí.

**Causa de que el grupo estuviera inflado.** La rama de `_situacion` decía
`documentos_ocr > 0 or "escaneado" in motivo_tecnico`, e iba **por delante** de
todas las demás: bastaba un anejo cualquiera leído por imagen para tapar la
explicación real que el propio sistema ya había escrito. Ahora se exige lo que
la etiqueta significa: **que hubiera documentos que leer, que alguno de ELLOS
hiciera falta leerlo por imagen, y que el sistema no tenga ninguna otra
explicación** (el motivo es exactamente `"no se extrajo ninguna línea de
catálogo de los documentos descargados"`, comparado por igualdad, no por
subcadena).

Los **16** que salen del grupo van a donde su motivo dice:

| A dónde van | Cuántos | Cuáles |
|---|---:|---|
| "Publicado sin cuadro de precios" (su motivo dice que el expediente no trae ningún Anejo ni Pliego técnico) | 6 | `3.19/28510.0016`, `3.19/28510.0141`, `6.15/28510.0094`, `6.18/28510.0050`, `6.18/28510.0051`, `6.19/28510.0129` |
| "Otro" (cobertura parcial de lotes, baja en documento compartido, matriz sin cuadro, anuncio que agrupa lotes, documento equivocado del scraper) | 10 | `19/28510`, `2.20/28510.0118`, `3.18/28510.0047`, `3.19/28510.0198`, `6.15/28510.0080`, `6.19/28510.0179`, `6.19/28510.0209`, `6.19/28510.0210`, `6.20/28510.0040`, `6.20/28510.0089` |

### Recuento por Situación, antes y después

| Situación | Antes | Después |
|---|---:|---:|
| Aporta líneas | 358 | **362** |
| Publicado sin cuadro de precios | 56 | **64** |
| Los precios están en un acuerdo marco que no está publicado | 49 | 49 |
| Documentos escaneados que no se han podido leer | 31 | **15** |
| Otro | 19 | **28** |
| Pendiente de procesar | 2 | **0** |
| **Total** | **515** | **518** |

"Otro" crece de 19 a 28 y eso es lo correcto: son 10 expedientes que estaban
mal etiquetados (menos `6.25/28510.0081`, que sale de "Otro" porque ya aporta
líneas). Cada uno lleva en "Motivo" lo que el sistema anotó al leerlo; ninguno
es un silencio. **Queda pendiente de decisión del cliente** si "Otro" debe
partirse en categorías con nombre propio (cobertura parcial de lotes / baja en
documento compartido / matriz sin cuadro legible / anuncio que agrupa lotes),
que son los cuatro motivos reales que hoy conviven ahí.

---

## Bloque 5 — Los 3 expedientes 6.26 que no teníamos

Buscados uno a uno en la Plataforma, descargados y procesados hoy:

| Expediente | ¿Existía? | Documentos | Líneas en el catálogo | Filas en el Excel |
|---|---|---:|---:|---:|
| `6.26/28510.0057` | **sí, marcado `sin_publicar`** | 4 enlaces, 3 documentos | 7 | 7 |
| `6.26/28510.0083` | **sí, marcado `sin_publicar`** | 3 enlaces, 3 documentos | 15 | 15 |
| `6.26/28510.0096` | **no, nuevo** | 3 enlaces, 3 documentos | 39 | **26** |

- `0057`: *Suministro de disyuntores con entrega a través de los almacenes de
  Adif*. 2.420.000 € (sin impuestos). Sin baja todavía (está en plazo de
  presentación, no hay adjudicación).
- `0083`: *Suministro de pletinas, tubos y varillas de cobre…*.
- `0096`: *Suministro de material de telecomunicaciones (cajas de empalme y
  armarios de fibra óptica)*. De sus 39 líneas, **13 no salen al Excel**: la
  columna de precio de esa tabla no se mapeó con confianza
  (`MOTIVO_MAPEO_INCOHERENTE`) y el criterio de siempre es no entregar una fila
  cuyo precio no se sabe leer.

Los tres declaran **plazo de presentación hasta el 14/10/2026**, como decía el
cliente.

**Con estos tres, la hoja "Conciliación" tiene ahora exactamente 18 expedientes
`6.26/28510`** — los 18 que el cliente ve publicados en la Plataforma.

### ¿Estaban marcados en falso? No

`0057` y `0083` se buscaron el **16/09/2026 a las 21:21** y la Plataforma
devolvió *"no encontrado ni por matriz ni por expediente"*. Hoy, 18/09, la
misma búsqueda los encuentra con su ficha completa. El anuncio de `0057`
declara **"Fecha de envío \[al DOUE\] 14/09/2026"** y su "Documento de Pliegos"
lleva **"Publicado en la Plataforma […] el 18-09-2026"**. **El negativo del
16/09 era correcto en ese momento**: el expediente todavía no era recuperable
por número en el buscador. No hay marca falsa que corregir.

Lo que sí queda a la vista es el **plazo de reintento**: `sin_publicar` no es
definitivo (`SIN_PUBLICAR_REINTENTO_DIAS`, 14 días por defecto), así que un
expediente publicado justo después de un negativo puede quedar invisible hasta
dos semanas. Estos tres se habrían encontrado solos el 30/09.

### Cuántos más hay con esa marca

De los 75 que la Conciliación daba por no publicados, **quedan 73** (`0057` y
`0083` ya no lo están). Repartidos por año del código:

```
2014: 4   2015: 2   2016: 6   2017: 19   2019: 3   2020: 1
2021: 7   2023: 9   2024: 6   2025: 4    2026: 12
```

Los **12 de 2026** son los únicos con riesgo real de ser un negativo caducado;
**9 de ellos llevan el mismo negativo del 16/09/2026** que `0057` y `0083`
(`6.26/28510.0002`, `0003`, `0087`, `0088`, `0089`, `0090`, `0091`, `0092`,
`0103`), más `6.17/28510.0031` del mismo día.

**Relanzada hoy la búsqueda de los 10, uno a uno: los 10 siguen sin
encontrarse** ("no encontrado en la Plataforma ni por matriz ni por
expediente"). Es decir, **`0057` y `0083` eran los dos únicos negativos
caducados de aquella tanda**, y ya están corregidos. Los 73 restantes siguen
siendo, hasta donde la Plataforma contesta hoy, no publicados de verdad.

---

## Bloque 6 — Los acuerdos marco de equipos de protección individual

### Lo que dicen los títulos publicados, campo a campo

Extraído del campo fijo *"Licitación basada en el acuerdo marco → Expediente"*
y del *"Objeto del Contrato"* de cada anuncio, **no** por parecido de texto:

| Pedido | Acuerdo marco (campo fijo del anuncio) | Expediente principal declarado en el título | Lote declarado | Objeto del lote |
|---|---|---|---|---|
| `6.26/28510.0047` | `2.24/04110.0036` | — | **2** | Chaqueta impermeable y softshell AV contra el frío extremo (−50 °C) |
| `6.26/28510.0048` | `2.24/04110.0035` | — | **1** | Chaqueta impermeable y softshell AV contra el frío (−5 °C) |
| `6.26/28510.0049` | `2.24/04110.0037` | — | **3** | Chalecos de alta visibilidad |
| `6.26/28510.0068` | `4.24/04110.0189` | **`4.23/04110.0256`** | **6** | Crema o leche de protección solar |
| `6.26/28510.0073` | `4.24/04110.0187` | **`4.23/04110.0256`** | **4** | Guantes de protección contra riesgos mecánicos |

**Los cinco números de lote coinciden con los que traía el encargo.** Lo que no
coincide es de qué acuerdo marco cuelgan.

### Búsqueda en la Plataforma, uno a uno

| Expediente | Resultado |
|---|---|
| `4.23/04110.0256` | **Encontrado.** 6 enlaces, 6 documentos descargados. |
| `4.24/04110.0187` | **No encontrado** ("ni por matriz ni por expediente"). |
| `4.24/04110.0189` | **No encontrado.** |
| `2.24/04110.0036` | **No encontrado.** |
| `2.24/04110.0035` (añadido: es la matriz de `0048`) | **No encontrado.** |
| `2.24/04110.0037` (añadido: es la matriz de `0049`) | **No encontrado.** |

### `4.23/04110.0256` no publica ningún cuadro de precios

*"Acuerdo Marco para el suministro de equipos de protección individual
2024-2025 (8 lotes)"*. Seis documentos, 234 páginas, todos con capa de texto:

| Documento | Págs. | Qué es |
|---|---:|---|
| `ADJUDICACION_1.pdf` | 3 | Resolución de adjudicación **solo del Lote nº5** |
| `ANEJO_1.pdf` | 78 | PPT — especificaciones técnicas. **1 sola página menciona un importe** |
| `ANEJO_2.pdf` | 135 | PCAP — aquí está lo más parecido a un cuadro de precios |
| `ANEJO_3.pdf` | 3 | Fe de erratas |
| `CONTRATO_1.pdf` | 5 | Anuncio de formalización, **solo del Lote 3** |
| `PLIEGO_1.pdf` | 9 | Documento de Pliegos |

Lo que el PCAP publica por lote (páginas 17-22) **no es un cuadro de precios:
es el modelo de proposición económica en blanco.** Trae las unidades y deja
vacía la columna que el licitador tiene que rellenar:

```
LOTE 4: GUANTES DE PROTECCIÓN CONTRA RIESGOS MECÁNICOS…
PROPOSICIÓN ECONÓMICA   UNIDADES   PRECIO UNITARIO   TOTAL
GUANTES DESTREZA           4.393        (en blanco)
GUANTES PROTECCIÓN FRENTE AL CORTE  3.977  (en blanco)
```

**Los precios unitarios adjudicados de este acuerdo marco no están publicados
en la Plataforma.** Lo que sí está es el presupuesto de licitación por lote
(Lote 1 287.678,40 €, Lote 2 304.114,00 €, Lote 3 169.001,00 €, Lote 4
61.402,20 €, Lote 5 91.064,40 €, Lote 6 72.960,00 €, Lote 7 43.797,60 €, Lote 8
109.500,00 €; total 1.139.517,60 €) — un techo de gasto, no un precio unitario.

### El lote: qué se puede afirmar y qué no

- **`0068` (lote 6) y `0073` (lote 4) sí cuelgan de `4.23/04110.0256`**, con
  certeza estructural triple: su título declara el expediente principal por
  número, declara el lote por número, y **el objeto de ese lote coincide con el
  que el PCAP de `0256` asigna a ese mismo número** (lote 6 = crema solar, lote
  4 = guantes). Además, la numeración de los contratos por lote lo confirma: el
  Anuncio de formalización de `0256` da "Número de contrato 4.24/04110.0186/1"
  para el **lote 3** → `0187` = lote 4 y `0189` = lote 6, exactamente las dos
  matrices de `0073` y `0068`.
- **`0047`, `0048` y `0049` NO cuelgan de `4.23/04110.0256`.** Sus títulos no
  lo nombran, sus matrices son de otra serie (`2.24/04110.0035/0036/0037`, con
  la misma correspondencia lote 1/2/3) y **sus objetos no casan con los lotes
  1, 2 y 3 de `0256`**, que son botas, polos/sudaderas y pantalones — no
  chaquetas, chaquetas y chalecos. Pertenecen a **otro acuerdo marco de EPIs
  cuyo expediente principal no aparece en ningún documento publicado de estos
  tres pedidos**. Siguiendo el encargo: **no se asocian, quedan a revisión y se
  dice aquí.**

### Líneas que aporta cada uno de los 5: **0**

| Pedido | Líneas | Por qué |
|---|---:|---|
| `6.26/28510.0047` | 0 | su acuerdo marco `2.24/04110.0036` no está publicado |
| `6.26/28510.0048` | 0 | ídem, `2.24/04110.0035` |
| `6.26/28510.0049` | 0 | ídem, `2.24/04110.0037` |
| `6.26/28510.0068` | 0 | su acuerdo marco `4.24/04110.0189` no está publicado, y el expediente principal `4.23/04110.0256`, que sí lo está, **no publica cuadro de precios** |
| `6.26/28510.0073` | 0 | ídem, `4.24/04110.0187` / `4.23/04110.0256` |

Su motivo lo dice ahora entero, sin abrir el PDF:

> la matriz 4.24/04110.0187 no tiene ningún lote registrado (estado:
> sin_publicar); el anuncio de este pedido declara además el expediente
> principal 4.23/04110.0256, lote 4

### De los 49 "precios en acuerdo marco no publicado": **0 se resuelven**

El grupo sigue en 49. La razón es la de arriba: el único acuerdo marco de los
seis que sí está publicado no publica precios unitarios. **Para completar estos
cinco haría falta que ADIF facilitara el cuadro de precios adjudicado del
acuerdo marco**, exactamente lo que la columna "Motivo" ya dice.

### Lo que sí se ha ganado: herencia desde una matriz multi-lote

`app.extraccion.lote_declarado` + `intentar_heredar_de_matriz`: cuando la
matriz tiene varios lotes y **el pedido declara el suyo en el "Objeto del
Contrato" publicado**, se hereda ese lote y solo ese. Reglas deliberadamente
estrechas (docstring del módulo): el número va **detrás** de la palabra "lote"
(*"(8 LOTES)"* es el número de lotes de la licitación y no dispara); si el
título nombra dos lotes distintos no se devuelve ninguno; si el número
declarado no casa con ningún lote de la matriz, **a revisión diciendo qué se
leyó y qué lotes hay**, nunca al más parecido.

**Efecto medido: `6.25/28510.0081`** (*"Lote 2: Base en Sanchidrián"*, matriz
`6.25/28510.0028`, balasto, 6 lotes) pasa de `pendiente_revision` sin líneas a
**`completado` con 6 líneas y baja 0,10 %**. Es el caso que llevaba abierto en
"Otro" desde ayer.

---

## Bloque 7 — Dos expedientes concretos y la validación por contraste

### `6.26/28510.0014`: no hay baja que leer, y es por diseño del contrato

Las tres hipótesis del encargo, contestadas:

| Hipótesis | Respuesta |
|---|---|
| ¿No se descargó el documento? | **No.** Tiene 2 documentos de la Plataforma, descargados el 07/09 (`ADJUDICACION_1.pdf` y `CONTRATO_1.pdf`, 3 páginas cada uno). |
| ¿No se reconoció el formato? | **No.** Los dos se clasifican como `anuncio_pcsp` y sus campos fijos se extrajeron bien: adjudicatario *Arcelormittal España SA*, importes, y el campo *"Identificador contrato original 6.25/28510.0016"*. |
| ¿La baja está en el acuerdo marco? | **El modelo de precio sí; el número, no está en ninguna parte.** |

`6.26/28510.0014` es el *"Pedido nº3 acuerdo marco de suministro de carril
nuevo…"* y cuelga de `6.25/28510.0016`, uno de los **tres acuerdos marco de
carril de ArcelorMittal** que usan la **segunda familia de precio**
(CONTEXTO.md sección 16): `P(t) = Precio ofertado × Kt × Coeficiente de baja`,
fijado pedido a pedido. Su lote está correctamente marcado
`modelo_precio = indexado_por_pedido` y su `baja_lote` es `NULL` **a propósito**.

Ya quedó cerrado en la sesión 2026-09-07, comprobado contra los documentos
reales de los 9 pedidos de las 3 matrices: **el "Coeficiente de baja" no está
publicado en ningún documento de la Plataforma, ni de la matriz ni del pedido.**
ADIF y el adjudicatario lo pactan fuera. Los importes lo confirman: licitación
y adjudicación son **el mismo número, 3.005.618,56 €**, con una sola oferta
recibida — el caso de "techo de gasto" de CONTEXTO.md sección 4, donde
`1 − adjudicado/licitación` daría 0 % y sería falso.

**La baja que sale: ninguna, y no es un hueco.** Lo que sí estaba en nuestra
mano y estaba mal es **cómo se decía**: las 14 filas del Excel llevaban
*"Baja del lote: no consta"* y *"Precio adjudicado: pendiente (falta la baja
del lote)"* — dos frases que mandan al cliente a buscar en la Plataforma un
número que nunca se publicó. `app.celdas_vacias` distingue ahora el caso:

> Baja del lote: **no aplica** (este contrato no tiene una baja única: su precio
> se revisa pedido a pedido con un coeficiente que ADIF pacta con el proveedor
> fuera de la Plataforma)

### `6.26/28510.0064`: no, no son los 6 lotes leídos como materiales

*"Suministro de balasto con entrega a través de los almacenes de Adif (zona
norte). 6 lotes"*. Documentos publicados:

| Documento | Págs. | Qué es |
|---|---:|---|
| `PLIEGO_1.pdf` | 7 | Documento de Pliegos |
| `ANEJO_1.pdf` | 36 | **PPT con el cuadro de precios, uno por lote** |
| `ANEJO_2.pdf` | 91 | Criterios técnicos para el suministro de balasto |

**Sí trae cuadro de precios**, y las 6 líneas **no son los 6 lotes**: son los
**6 conceptos de precio** que el cuadro repite para cada lote, con su código
propio:

```
P-1  Balasto sobre camión en cantera                                    t       30.000
P-2  T de balasto transportado a punto de carga ofertado                t       27.000
P-3  T x km de balasto transportado a punto de carga diferente     t x km      450.000
P-4  Lavado de balasto                                                  t        3.000
P-5  Remonte de balasto                                                 t        3.000
P-6  Enrasado de balasto en tolva                                       t        3.000
```

El documento trae **seis bloques** idénticos en estructura, encabezados
`LOTE 1` … `LOTE 6`, cada uno con esos mismos seis códigos y **precios
distintos**. Son 36 filas reales, y el sistema las vio todas
(*"ANEJO_1.pdf: 36 línea(s) con un valor que no se pudo interpretar"*); se
quedaron en 6 porque ninguna pudo atribuirse a su lote y las repetidas
colapsaron bajo el lote único del expediente.

**Por qué no hay precio unitario:** el PDF no tiene mal el número, lo tiene
**sin descodificar**. La fuente del documento no trae tabla `ToUnicode`, así
que la celda sale como identificadores de glifo:

```
fragmento real: P-1 | Balasto sobre camión en cantera | t | 30.000 |
                (cid:1005)(cid:1005),(cid:1013)(cid:1011)(cid:1004)(cid:1004) € |
                (cid:1007)(cid:1009)(cid:1013).(cid:1005)(cid:1004)(cid:1004),(cid:1004)(cid:1004) €
```

La correspondencia es una traslación fija, `cid:1004+N` → dígito `N`, y **se
puede comprobar sola con la aritmética de la propia fila**:
`11,9700 × 30.000 = 359.100,00`, que es justo el total de esa línea. El sistema
hace bien en no inventarse el número hoy: lo marca
(*"precio unitario no interpretable: la celda trae identificadores de glifo sin
decodificar (fuente sin ToUnicode), no un número"*).

**Qué habría que hacer (no aplicado, como pedía el encargo):**

1. **Descodificar los `(cid:N)` con verificación aritmética**, nunca a ciegas:
   aceptar la traslación solo cuando `precio unitario × cantidad == total` en
   la misma fila, que es una comprobación que se valida a sí misma y no depende
   de adivinar el desplazamiento de la fuente.
2. **Atribuir cada bloque a su cabecera `LOTE N`**, para que las 36 filas sean
   36 líneas repartidas en 6 lotes en vez de 6 colapsadas en uno.

Con las dos cosas, este expediente pasaría de 6 líneas sin precio a 36 con
precio.

### Validación por contraste de estados (en lugar de la de importes)

Su listado no trae presupuesto de licitación, así que la validación pedida no
se puede hacer (bloque 1). En su lugar, y con el visto bueno del cliente, se
cruza **el dato que sí trae**: su *"Descripción del estado"* (el ciclo de vida
del contrato en SAP) contra **el estado que consta publicado en la Plataforma**
(el del anuncio, leído de la sindicación).

**102 expedientes tienen los dos estados.** Tabla de contingencia completa, sin
interpretar:

| Plataforma | ADIF | Expedientes |
|---|---|---:|
| Resuelta | En ejecución | 44 |
| Resuelta | Finalizado | 31 |
| Resuelta | Desierto | 6 |
| En plazo de presentación | En licitación | 4 |
| Pendiente de adjudicación | En licitación | 4 |
| Resuelta | En adjudicación | 3 |
| Adjudicada | Finalizado | 3 |
| Pendiente de adjudicación | En adjudicación | 2 |
| Resuelta | En finalización | 2 |
| Adjudicada | En adjudicación | 2 |
| Pendiente de adjudicación | Finalizado | 1 |

Los dos vocabularios no son el mismo, así que compararlos por igualdad no
diría nada. Se comparan por **fase del procedimiento**, con la escala escrita
aquí para que cualquiera pueda rehacer el cálculo:

- Plataforma: *En plazo de presentación* = 1, *Pendiente de adjudicación* = 2,
  *Adjudicada* y *Resuelta* = 3 (procedimiento resuelto).
- ADIF: *En licitación* = 1, *En adjudicación* = 2, y *En ejecución*,
  *En finalización*, *Finalizado*, *Desierto* y *Desistido* = 3 (el
  procedimiento ya se resolvió, con contrato o declarándolo desierto).

| Resultado | Expedientes |
|---|---:|
| **Coinciden** (misma fase) | **92** |
| **Desfase de una fase** | **10** |
| **Contradicción (dos o más fases)** | **0** |

**Ninguno de los 102 se contradice.** Los 10 desfases, uno a uno, con la fecha
del boletín de sindicación del que sale nuestro estado:

| Expediente | Plataforma (boletín) | ADIF | A qué se debe |
|---|---|---|---|
| `6.24/28510.0188` | Pendiente de adjudicación (04/2026) | En licitación | la Plataforma ya cerró el plazo; SAP aún no ha movido el expediente a adjudicación |
| `6.26/28510.0030` | Pendiente de adjudicación (06/2026) | En licitación | ídem |
| `6.26/28510.0040` | Pendiente de adjudicación (06/2026) | En licitación | ídem |
| `6.26/28510.0074` | Pendiente de adjudicación (09/2026) | En licitación | ídem |
| `3.25/28510.0241` | Adjudicada (03/2026) | En adjudicación | la adjudicación está publicada; SAP no ha registrado aún el contrato |
| `6.26/28510.0016` | Adjudicada (09/2026) | En adjudicación | ídem, publicada hace ocho días |
| `3.25/28510.0012` | Resuelta (03/2025) | En adjudicación | ídem, con más de un año de diferencia |
| `6.25/28510.0156` | Resuelta (06/2026) | En adjudicación | ídem |
| `6.26/28510.0009` | Resuelta (08/2026) | En adjudicación | ídem |
| `6.25/28510.0221` | Pendiente de adjudicación (07/2026) | **Finalizado** | **el único donde SAP va por delante**: el contrato está terminado y el último boletín que lista este expediente (07/2026) todavía es el de antes de adjudicar. O la adjudicación se publicó después y ningún boletín ingerido la ha listado, o no se ha publicado. |

**Los 9 primeros son el mismo fenómeno, en el mismo sentido**: nuestro estado
es "el de la última vez que un boletín mensual habló de este expediente" — un
boletín refleja un evento de ese mes, no "sigue vigente" (CONTEXTO.md sección
16). El décimo va al revés y es el único que merece una comprobación en la
Plataforma.

**Qué prueba y qué no prueba este contraste.** Prueba que, donde tenemos las
dos fuentes, **lo que la app ha leído de la Plataforma no contradice ni una sola
vez el estado que ADIF lleva en su propio sistema**. No prueba cobertura, por
lo dicho en el bloque 2: mientras no se confirme que el listado es independiente
de nuestro catálogo, el "0 discrepancias" del bloque 2 no puede presentarse
como prueba de que no falta nada.

**Para la validación de importes que se le ofreció al cliente basta con una
columna más en este mismo listado: el presupuesto de licitación de cada
expediente.** Con eso, el cruce es inmediato — nosotros ya lo extraemos de los
documentos publicados.

---

## Cierre

### Pruebas

**1.046 pasan** (1.012 antes, **+34**). Ninguna saltada.

Las nuevas, por bloque: 9 de `estados_adif` (incluida la que fija que **no da
de alta ningún expediente**), 13 de `lote_declarado` (los cinco títulos reales
de los pedidos de EPIs, el de balasto, y los casos que **no** deben disparar),
3 de herencia desde matriz multi-lote, 7 de la hoja "Conciliación" (columna
nueva, atribución en el Resumen, y las tres reglas nuevas de Situación) y 2 de
`celdas_vacias` para el precio indexado.

### Excel

```
C:\dev\ADIF\catalogo_adif_2026-09-18-estados-adif.xlsx
```

Tres hojas: `Materiales` (17 columnas, **18.293 filas**), `Conciliación`
(**11 columnas**, **518 filas**) y `Resumen`.

### Comparación con `catalogo_adif_2026-09-18-conciliacion.xlsx`

| | Ayer | Hoy |
|---|---:|---:|
| Filas de "Materiales" | 18.239 | **18.293** (+54) |
| Expedientes con filas | 358 | **362** (+4) |
| Materiales distintos (expediente + matrícula + descripción) | 17.269 | **17.323** (+54) |
| Columnas de "Materiales" | 17 | 17 |
| Filas de "Conciliación" | 515 | **518** |
| Columnas de "Conciliación" | 10 | **11** |

**0 expedientes pierden filas, 0 materiales desaparecen.** Las cuatro
diferencias son altas, todas explicadas:

| Expediente | Ayer | Hoy | Por qué |
|---|---:|---:|---|
| `6.26/28510.0057` | 0 | 7 | bloque 5: publicado el 18/09, descargado y extraído hoy |
| `6.26/28510.0083` | 0 | 15 | ídem |
| `6.26/28510.0096` | 0 | 26 | ídem (nuevo en el sistema) |
| `6.25/28510.0081` | 0 | 6 | bloque 6: herencia del lote 2 de su matriz, que ya declaraba |

### Cuadre de "Conciliación" con "Materiales"

```
suma de la columna de líneas de "Conciliación": 18.293
filas de la hoja "Materiales":                  18.293
```

Comprobado además por `comprobar_cuadre`, que revienta la exportación si no
cuadra o si algún expediente se queda sin Situación: **0 sin Situación**.

### Auditoría

**1 error, 6 avisos.**

El error es **`lineas_cambian_sin_cambiar_documentos` sobre
`6.25/28510.0081`**: 0 → 6 líneas sin que cambiaran sus documentos. Es real y
está explicado: las 6 líneas no vienen de leer nada nuevo, vienen del arreglo
de herencia del bloque 6, que hoy sabe elegir el lote declarado. **La regla que
lo marca es deliberada y no se toca** — la sesión anterior fijó que *"cualquier
SUBIDA es error, sin excepción: ni la poda ni un filtro suman líneas"*,
precisamente para que la atribución automática no se convierta en una puerta de
atrás. Verificado a mano que no hay duplicación: el lote 2 de la matriz
`6.25/28510.0028` tiene exactamente 6 líneas, y 6 son las heredadas.

Los seis avisos son los de siempre, ninguno nuevo: 11 grupos de material
repetido con códigos de precio distintos (legítimos), 19.233 huérfanas sin
lote, 1.995 precios atípicos, 606 cantidades con forma de año, 56 grupos de
importe de licitación compartido y 8 de importe repetido en el mismo
expediente.

### Pendiente de decisión del cliente

1. **Confirmar con ADIF de dónde sale su listado de 358** (bloque 2). Si no es
   independiente de nuestro catálogo, el "0 discrepancias" no sirve como prueba
   de cobertura.
2. **Pedir el presupuesto de licitación** como columna más de ese mismo
   listado, para poder hacer la validación de importes ofrecida.
3. **Pedir el cuadro de precios adjudicado de los acuerdos marco de EPIs**
   (`2.24/04110.0035/0036/0037`, `4.24/04110.0187/0189`), ninguno publicado en
   la Plataforma; sin él, los 5 pedidos no pueden aportar líneas.
4. **Preguntar de qué acuerdo marco cuelgan `0047`, `0048` y `0049`**: sus
   objetos no casan con los lotes de `4.23/04110.0256` y ningún documento
   publicado lo dice.
5. **¿Partir "Otro" en categorías con nombre propio?** Los 28 de hoy son cuatro
   motivos distintos conviviendo.
6. Sigue en pie de ayer: "Órgano de contratación" solo para 124 de 518, y los
   42 internos repetidos que vienen del propio listado de códigos de ADIF.
