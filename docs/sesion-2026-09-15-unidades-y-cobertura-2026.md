# Sesión 2026-09-15 (cuarta parte) — unidades de medida que no lo son, cobertura de 2026 y restos de auditoría

Encargo: (1) barrido de la columna de unidad de medida (el cliente ha visto
planos y referencias normativas), arreglar lo que sea fallo de mapeo y validar
contra un vocabulario de unidades; (2) cobertura de 2026 (el cliente cuenta
14 expedientes 28510 publicados y 3 en el catálogo); (3) las 5 filas-cabecera
de `4.26/28510.0031` y la línea sin descripción de `6.25/28510.0257`.

## 1. Unidades de medida

### Barrido

34.167 líneas, 27.932 con unidad, **40 valores distintos**. Planos y normas: ya
no queda ninguno (la regla de "tres o más dígitos o empieza por dígito" de la
sesión 2026-09-14 descartó 1.273 líneas): si el cliente los ha visto, es en un
Excel exportado antes de esa regla.

Cuatro valores no son unidades:

| Valor | Líneas | Expediente | Causa |
|---|---:|---|---|
| `Fibra monomodo` | 44 | `6.24/28510.0125` | Fallo de mapeo: la caché 298 (Contrato p.99, cabecera `MATRÍCULA / ELEMENTO / PRECIO / CARACTERÍSTICAS / – / CANTIDAD ESTIMADA`, resuelta por el modelo) mapeaba la unidad a "CARACTERÍSTICAS". La misma cabecera en el Anejo (caché 299) está bien; las líneas del Anejo heredaban el valor al fusionarse por matrícula con las del Contrato. |
| `Fibra monomodo Fibra monomodo` | 7 | `6.24/28510.0125` | Mismo mapeo, en filas del Contrato con dos materiales fundidos (pp. 99-100). |
| `Precio mensual` | 6 | `4.26/28510.0020` | Mapeo correcto (`Ud.`): es el propio documento el que escribe "Precio mensual" en la columna de unidad (personal y vehículo, 48 meses). No es una unidad. |
| `UNIDAD` | 5 | `4.26/28510.0031` | La cabecera repetida en mitad de la tabla leída como línea (punto 3). |
| `ud ud ud` | 1 | `6.21/28510.0152` | Tres filas fundidas en una (`619900701619900702619900703PA`). |

Los otros 35 son unidades, simples o compuestas: `UD.`, `UN`, `ud`, `M`, `Kg`,
`t`, `m3`, `PA`, `Txkm`/`t x km`, `m3xkm`, `UD/día`, `Hora`, `h.`, `Mes`,
`Elemento x mes`, `dm3**` (llamada de nota al pie), las de precio
`€/UD`, `€/Ton`, `€/Ton*km`, `€/Ton*mes`, `€/m`, `€/h`, `€/transporte` de la
familia `6.21/28510.0108` y `P` (3 líneas, rellenada desde el maestro de SAP,
código propio de ADIF).

Además del barrido de valores, revisado a qué columna apunta `unidad_medida` en
las 239 entradas de la caché de cabeceras que la mapean: todas son "Unidad de
medida", "Ud.", "Unidades" (siempre con su propia columna de cantidades al
lado) o una columna sin título, salvo **298** ("CARACTERÍSTICAS") y **98**
("E.T.", especificación técnica: la variante de `6.20/28510.0054` que se
escapó a la corrección de la sesión 2026-09-07; sus valores ya los descartaba
la regla de dígitos). Las dos corregidas a `unidad_medida: null`.

### Validación

`app.extraccion.unidad_medida.es_unidad_conocida`: un valor es unidad solo si,
en minúsculas y sin acentos ni puntos, está en la lista o es una compuesta de
unidades de la lista (separadas por `x`, `*`, `/` o `·`), con el prefijo `€/`
y las llamadas de nota (`**`) aparte. La lista: las unidades del corpus, los
códigos del maestro de SAP y las usuales de longitud, superficie, volumen,
masa y tiempo.

- En `_construir_campos` (`app/catalogo.py`), después de las reglas de forma:
  un valor que no pasa se descarta como unidad y la línea va a revisión con el
  motivo "unidad de medida descartada por no ser una unidad conocida".
- En el relleno desde el maestro de SAP: una unidad del maestro que no pasa no
  se copia (hoy solo `001`, una fila del maestro, sin ninguna línea afectada).

Una unidad real nueva que no esté en la lista cae a revisión, no se pierde en
silencio: se añade a la lista tras verlo en el documento.

### Aplicado

Un reproceso solo no basta ("un `None` no pisa un valor ya conocido"): las 58
líneas con un valor que no pasa se vaciaron en base de datos
(`unidad_medida = NULL`) y se reprocesaron sus cuatro expedientes. Dos de los
valores eran ya restos de pasadas antiguas que el código actual no leía:
"Precio mensual" (con la caché 249 actual, la celda de `Ud.` de esas filas
viene vacía) y "ud ud ud". En `6.24/28510.0125` una tabla sin cabecera del
Contrato (p.100), que el modelo mapea en cada pasada sin caché, vuelve a tomar
"Fibra monomodo Fibra monomodo" como unidad: ahora se descarta con el motivo
nuevo (1 línea).

**Reproceso fuera de la cola.** El único worker tenía por delante 21 meses de
sindicación (~6 h, cola FIFO). Los reprocesos y la auditoría se ejecutaron en
primer plano con `app.worker.ejecutar_trabajo` sobre un trabajo creado ya
`en_proceso` (misma vía y mismo registro en `trabajos_cola`, trabajos
19281-19288). Primero se lanzaron desde el contenedor `api` (trabajos
19276-19280), que **no tiene proveedor de modelo**: las tablas sin cabecera
del Contrato de `0125` fallaron ("no se proporcionó un ModelProvider") sin
borrar nada; repetidos desde el `worker`, sin errores y sin ninguna línea
recreada. Los dos despliegues dejaron huérfanos los meses 202604 y 202603
(trabajos 19229 y 19256), que la cola ya está reintentando.

## 2. Cobertura de 2026

**24 expedientes `*.26/28510.*` en el sistema.** 21 están en la sindicación
(RES 11, ADJ 1, EV 5, PUB 4, todos de "ADIF - Presidencia" o "ADIF - Consejo
de Administración"); los 3 restantes (`2.26/28510.0029`, `5002/01`,
`5003/01`) vienen del SAP, no están en la sindicación y la Plataforma no los
tiene (negativo confirmado el 08-09). **14 aportan líneas**, los 14 con filas
en el Excel: 551 líneas en base de datos, 343 filas en el Excel.

De los 22 recuperados en la segunda parte, 4 son de 2026 (`2.26/0006`,
`3.26/0013`, `3.26/0042`, `4.26/0031`); de la primera parte, otros 6
(`6.26/0004`, `0009`, `0030`, `0040`, `0064`, `0074`).

| Expediente | Plataforma | Órgano | Estado | Líneas | Excel | Nota |
|---|---|---|---|---:|---:|---|
| `2.26/28510.0006` | EV | Presidencia | pendiente_revision | 7 | 7 | sin baja (no adjudicado) |
| `2.26/28510.0029` | — | — | sin_publicar | 0 | 0 | solo en el SAP |
| `2.26/28510.5002/01` | — | — | sin_publicar | 0 | 0 | solo en el SAP |
| `2.26/28510.5003/01` | — | — | sin_publicar | 0 | 0 | solo en el SAP |
| `3.26/28510.0013` | EV | Presidencia | pendiente_revision | 3 | 3 | sin baja (no adjudicado) |
| `3.26/28510.0042` | PUB | Presidencia | pendiente_revision | 3 | 3 | valores sin interpretar |
| `4.26/28510.0005` | RES | Presidencia | pendiente_revision | 0 | 0 | ninguna línea extraída — **sin investigar** |
| `4.26/28510.0020` | RES | Presidencia | pendiente_revision | 242 | 34 | 208 del cuadro común de la partida alzada, sin lote |
| `4.26/28510.0031` | PUB | Presidencia | pendiente_revision | 23 | 23 | valores sin interpretar |
| `6.26/28510.0004` | PUB | Presidencia | pendiente_revision | 0 | 0 | ninguna línea extraída — **sin investigar** |
| `6.26/28510.0009` | RES | Presidencia | pendiente_revision | 14 | 14 | valores sin interpretar |
| `6.26/28510.0014` | RES | Consejo | completado | 14 | 14 | hereda de la matriz `6.25/28510.0016` |
| `6.26/28510.0016` | ADJ | Presidencia | pendiente_revision | 124 | 124 | valores sin interpretar |
| `6.26/28510.0030` | EV | Presidencia | pendiente_revision | 29 | 29 | valores sin interpretar |
| `6.26/28510.0032` | RES | Consejo | completado | 39 | 39 | hereda de la matriz `6.20/28510.0136` |
| `6.26/28510.0040` | EV | Presidencia | pendiente_revision | 7 | 7 | sin baja (no adjudicado) |
| `6.26/28510.0047` | RES | Presidencia | pendiente_revision | 0 | 0 | pedido de EPIs; matriz `2.24/04110.0036` no publicada |
| `6.26/28510.0048` | RES | Presidencia | pendiente_revision | 0 | 0 | ídem, matriz `2.24/04110.0035` |
| `6.26/28510.0049` | RES | Presidencia | pendiente_revision | 0 | 0 | ídem, matriz `2.24/04110.0037` |
| `6.26/28510.0064` | PUB | Consejo | pendiente_revision | 6 | 6 | cobertura parcial de lotes |
| `6.26/28510.0068` | RES | Presidencia | pendiente_revision | 0 | 0 | ídem, matriz `4.24/04110.0189` |
| `6.26/28510.0071` | RES | Consejo | completado | 39 | 39 | hereda de la matriz `6.20/28510.0136` |
| `6.26/28510.0073` | RES | Presidencia | pendiente_revision | 0 | 0 | ídem, matriz `4.24/04110.0187` |
| `6.26/28510.0074` | EV | Presidencia | pendiente_revision | 1 | 1 | valores sin interpretar |

**El "3" del cliente** son los tres con líneas que cruzan con el Excel de
códigos de ADIF (`0014`, `0032`, `0071`): la columna "Código de expediente"
del Excel solo se rellena cuando cruza (mismo hallazgo que en la primera parte
de la sesión); el código está siempre en "Nº de expediente (documento)", y
contando por esa columna salen los 14. No hay en el sistema una cifra de 14
"publicados": son 21 en la sindicación, 12 adjudicados (RES/ADJ).

`4.26/28510.0005` (Contrato 304 pp., dos anejos de 198 y 99) y `6.26/28510.0004`
(anejos de 8 y 98 pp.) tienen texto y hablan de precios: sin revisarlos no se
puede decir si es un límite de origen o un fallo de extracción.

## 3. Restos de auditoría

- **Cinco filas-cabecera de `4.26/28510.0031`**: no eran un resto, la
  extracción las seguía produciendo. La tabla de las pp. 7, 8 y 11 tiene una
  segunda sección ("MANTENIMIENTO PREVENTIVO") con su propia cabecera
  (`CODIGO | DESCRIPCIÓN | UNIDAD | ...`). `_es_cabecera_repetida`
  (`app/catalogo.py`): una fila cuya celda de descripción es una etiqueta de
  columna de descripción ("descripción", "concepto", "designación",
  "denominación") y cuya celda de precio no trae cifras no es una línea. Tras
  el reproceso la poda borró las cinco; es el único expediente del corpus con
  líneas así.
- **P-22 sin descripción de `6.25/28510.0257`**: tampoco era un resto (borrada
  a propósito, el reproceso la volvía a crear). En la tabla de p.20 del
  Contrato, "CÓDIGO ADIF" se mapea como matrícula por contenido y el texto de
  la partida cae en esa celda: se reconoce "Partida alzada..." y se pasa a
  descripción, pero con un `∅` delante (del sello lateral de verificación, el
  mismo que pega "ilav/" al código de precio) no se reconocía. Ahora un signo
  suelto al principio no cuenta. 0 líneas sin descripción en todo el corpus.

## Cierre

| | Antes | Después |
|---|---:|---:|
| Líneas en base de datos | 34.167 | 34.162 (−5 filas-cabecera) |
| Valores distintos de unidad | 40 | 35 |
| Líneas con un valor que no es unidad | 63 | 0 |
| Excel, hoja "Materiales" | 15.308 filas | 15.303 |
| Materiales distintos en el Excel | 6.119 | 6.118 (sale el pseudo-material "descripción") |

Auditoría (trabajo 19288): un hallazgo "error", `lineas_duplicadas_exactas`, 11
grupos y 22 líneas en `4.25/28510.0132`, `6.23/28510.0051` y `6.23/28510.0060`
(las parejas de códigos distintos con el mismo texto y precio que el propio
documento repite, conocidas desde la sesión 2026-09-14). Desaparecen el grupo
de `4.26/28510.0031` y el `sin_descripcion`. 863 pruebas.

## Quinta parte — "PERSONALIZADO" y segunda revisión de la columna

**"PERSONALIZADO" no existe como unidad en el sistema.** El encargo pedía
sacar 129 líneas con esa unidad. No hay ninguna: ni en `lineas_catalogo`
(34.162 líneas, 35 valores distintos), ni en el Excel exportado antes o
después de la cuarta parte, ni en el maestro de SAP, ni en el desglose de SAP,
ni en la caché de código de material. La palabra solo aparece dentro del texto
técnico de 4 líneas de cascos (`6.21/28510.0149`/`0097`, unidad `UN`). Tampoco
figuraba en el informe de la cuarta parte. Si llegara a aparecer, la
validación de vocabulario ya la descartaría con motivo.

**Revisión de los 35 valores, línea a línea contra su material.** Todos
cuadran (carril en `M`, balasto en `T`/`Txkm`, grasas y cable en `KG`,
servicios en `Hora`/`Mes`/`UD/día`). Cuatro, discutibles, se llevaron al
cliente:

| Valor | Líneas | Expedientes | Decisión |
|---|---:|---|---|
| Prefijo `€/` (`€/UD`, `€/Ton`, `€/m`, `€/h`, `€/transporte`, `€/Ton*km`, `€/Ton*mes`) | 4.084 | `6.21/28510.0108`-`0113` | Se guarda la unidad sin el prefijo |
| `dm3**` | 15 | `6.24/28510.0088`, `0114`, `6.25/28510.0221` | Se guarda `dm3`, sin la llamada de nota |
| `PA` | 66 | 16: `4.26/0020`, `6.20/0080`, `6.24/0088`, `0094`, `0114`, `0130`, `0152`, `0153`, `0175`, `0176`, `0177`, `6.25/0088`, `0125`, `0127`, `0128`, `0129` | Sin decidir: se queda |
| `P` | 3 | `6.20/28510.0042`, `0046`, `0047` (placa nervada, del maestro de SAP) | Sin decidir: se queda |

`app.extraccion.unidad_medida.limpiar_unidad`, aplicada en `_construir_campos`
antes de las validaciones. Reprocesados los 9 expedientes (trabajos
19289-19297, desde el `worker`): mismos ids, lotes, cantidades, precios y
motivos (huella idéntica); solo cambia la unidad. 32 valores distintos, 0 con
`€/` o `**`. 873 pruebas.

Auditoría (trabajo 19298): idéntica a la de la cuarta parte (un error, las 11
parejas conocidas). Excel: 15.303 filas antes y después, cabeceras iguales,
mismas filas como conjunto; cambian 951 celdas de unidad (887 `€/UD`→`UD`, 15
`€/m`, 15 `€/Ton`, 15 `€/transporte`, 6 `€/h`, 5 `€/Ton*km`, 5 `€/Ton*mes`, 3
`dm3**`); materiales distintos 6.118, sin cambios.

**Hallazgo de paso, sin tocar:** el orden del Excel no es total. El desempate
(`codigo_expediente`, `identificador_lote`, `orden_aparicion`) se repite entre
documentos de un mismo expediente y lote (`orden_aparicion` empieza en cada
documento), así que 5 parejas de filas de `0108`/`0109`/`0111` salen en otro
orden entre dos exportaciones seguidas. Como `consultar_catalogo` pagina con
`OFFSET`, una pareja empatada en el borde de una página podría salir repetida
o faltar (esta vez no ha pasado). Arreglo propuesto: `LineaCatalogo.id` como
último desempate.

## Pendiente

- Decisión del cliente sobre `PA` y `P`.
- Orden no total del catálogo/Excel (ver la quinta parte).
- `4.26/28510.0005` y `6.26/28510.0004`: por qué no dan ninguna línea.
- En `4.26/28510.0031`, el mapeo determinista (cachés 295-297) no reconoce
  "MEDICIÓN" como cantidad: las filas P1/P2.xx de ese cuadro salen sin
  cantidad. No es la columna de unidad; no se ha tocado.
- La caché 86 mapea como unidad una columna "MEDIDA" (con "E.T." al lado): sus
  valores actuales pasan el vocabulario, no se ha comprobado en el documento.
- La medición del criterio de descubrimiento ampliado sigue en la cola (21
  meses, más los dos huérfanos de esta sesión).
