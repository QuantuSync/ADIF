# Sesión 2026-09-15 — expedientes de 2026 que faltaban (departamento 28510)

Encargo: el cliente cuenta en la sindicación 9 adjudicados de 2026 del
departamento 28510 y solo 3 en el catálogo (`6.26/28510.0014`, `0032`, `0071`,
los tres de "ADIF - Consejo de Administración"). Faltaban `0009`, `0047`,
`0048`, `0049`, `0068` y `0073`, los seis de "ADIF - Presidencia". Además hay
6 publicados sin adjudicar, 15 en total. Hipótesis del encargo: el filtro de
descubrimiento discrimina por órgano, y quizá por estado de tramitación.

## Las dos hipótesis, contra el código y la base de datos

**Órgano: no discrimina entre órganos de ADIF.** `_es_adif`
(`app/sindicacion/descubrimiento.py`) solo exige que el órgano contenga
"adif", y después filtra por departamento (`SINDICACION_DEPARTAMENTOS_ADIF`).
Los 15 códigos `6.26/28510.*` están en `sindicacion_expedientes` y en
`expedientes`: 11 de "ADIF - Presidencia", 4 de "ADIF -Consejo de
Administración". No se tocó el filtro. El requisito "adif" no separa
Presidencia de Consejo: impide que entre otro organismo cuyo código tenga la
misma forma `N.AA/28510.NNNN`.

**Estado de tramitación: no descarta nada.** La sindicación guarda los cuatro
estados vistos (RES 9, ADJ 1, EV 2, PUB 3 de los 15) y el scraper busca solo
por número de expediente, sin ningún filtro de estado.

## La causa real

| Expedientes | Estado antes | Causa |
|---|---|---|
| `0009` (RES), `0004`, `0064`, `0074` (PUB), `0030`, `0040` (EV) | `sin_publicar` | Búsqueda del 2026-09-07 17:17 UTC, antes del arreglo de límite de tasa (`eeab48b`, 19:50 UTC). Ese defecto convertía un timeout o un bloqueo en "no publicado". El ciclo de mantenimiento no vuelve a intentar nunca un `sin_publicar` (`app/mantenimiento/ciclo.py`, consulta de expedientes a evaluar). |
| `0047`, `0048`, `0049` (Presidencia) | `pendiente_revision`, 0 líneas | Pedidos del acuerdo marco de EPIs `2.24/04110.0036`/`0035`/`0037` (departamento 04110). Sus documentos propios son dos formularios PCSP sin cuadro de precios: los precios están en la matriz, y la matriz no aparece en la Plataforma. |
| `0068`, `0073` (Presidencia) | `pendiente_revision`, 0 líneas | Lo mismo, matrices `4.24/04110.0189`/`0187`. |

Los tres de Consejo tienen líneas porque sus matrices (`6.25/28510.0016`,
`6.20/28510.0136`) están en el catálogo y heredan de ellas.

## Proceso

Se volvieron a buscar en la Plataforma los 6 `sin_publicar` y las 5 matrices
04110 (trabajos 19150-19160; extracciones encadenadas 19161-19166).

- **Los 6 `sin_publicar` se encuentran y se descargan todos**: eran falsos
  negativos.
- **Las 5 matrices 04110 siguen sin resultados**, esta vez con la búsqueda
  corregida, que solo da "sin publicar" cuando la Plataforma lo confirma en
  cada variante del código. Los PDF de `Ejemplo/Input/2.24_04110.003*` no son
  de la matriz: son del pedido nº 1 de cada lote (`6.25/28510.0215`, `0175`,
  `0248`), archivados con el nombre de la matriz (sección 8 de CONTEXTO.md).

| Expediente | Estado PCSP | Líneas | Estado final |
|---|---|---|---|
| `6.26/28510.0009` | RES | 14 | pendiente_revision (valores sin interpretar) |
| `6.26/28510.0030` | EV | 29 | pendiente_revision (valores sin interpretar) |
| `6.26/28510.0040` | EV | 7 | pendiente_revision (sin baja: no adjudicado) |
| `6.26/28510.0064` | PUB | 6 | pendiente_revision (cobertura parcial de lotes) |
| `6.26/28510.0074` | PUB | 1 | pendiente_revision |
| `6.26/28510.0004` | PUB | 0 | pendiente_revision (ninguna línea extraída) |

**Entran 6 expedientes, 5 de ellos con líneas: 57 líneas en total**, todas con
lote. Base de datos: 33.157 → 33.214 líneas. Excel, hoja "Materiales":
14.495 → 14.552 filas. No se ha revisado por qué `0004` no da ninguna línea.

De los 15, 10 tienen ya líneas en el Excel (los 3 de antes, `0016` y los 5
nuevos). Los 5 que no las tienen son los pedidos de Presidencia con matriz
04110.

## Una causa de lectura del Excel

`6.26/28510.0016` ya estaba en el Excel con 124 filas antes de esta sesión,
pero el cliente no lo contó. La columna 2, "Código de expediente", solo se
rellena cuando el expediente cruza con el Excel de códigos de ADIF (sección 7).
`0016` no cruza, y tampoco los 6 nuevos. El código siempre está en la columna
"Nº de expediente (documento)". Contando por la columna 2 se ven justo los 3
que cruzan (`0014`, `0032`, `0071`).

## Pendiente, fuera de este encargo

- **Otros `sin_publicar` con búsqueda anterior al arreglo**: 24 expedientes
  del departamento 28510 que figuran en la sindicación, entre ellos 4 de 2026
  con otros prefijos (`2.26` EV, `3.26` EV y PUB, `4.26` PUB). Por lo visto hoy,
  lo más probable es que sean falsos negativos. Volver a buscarlos cuesta
  unos 40 s por expediente.
- **El ciclo no vuelve a buscar nunca un `sin_publicar`**. Un expediente mal
  marcado se queda fuera para siempre.
- **Los precios de los 5 pedidos de EPIs**: habría que localizar la ficha del
  acuerdo marco por otra vía (p. ej. el enlace "Acuerdo Marco" de la ficha del
  pedido) o pedir los documentos a ADIF. El sistema no inventa la matriz.

## Segunda parte — reintento de los `sin_publicar` anteriores al arreglo, y reintento periódico

Encargo: (B) reintentar los `sin_publicar` marcados antes del arreglo del
2026-09-07 ("43" según el encargo) y (C) que `sin_publicar` deje de ser
definitivo, con reintento periódico y un estado que distinga el negativo
confirmado con la búsqueda corregida del que viene de antes.

### Cuántos eran: 34, no 43

Cronología de las búsquedas del 2026-09-07 en `trabajos_cola`: de 17:00 a
18:50 UTC, 425 "no encontrado" y ningún éxito (el bloqueo de la Plataforma);
el worker vuelve a arrancar con el arreglo y a las 20:00 UTC ya descarga con
éxito. Los `sin_publicar` cuya última búsqueda es anterior a ese corte son
**34**: 22 del departamento 28510 que están en la sindicación, 1 del 28510
que no está (`6.25/28510.5001_01`) y 11 de otros departamentos (04703, 20810,
27520 y 28520: los códigos de carpeta del conjunto de prueba). Ninguna cifra
del sistema da 43. Se reintentaron los 34 (trabajos 19167-19200).

**Aparecen 22 de los 34: justo los 22 del 28510 que están en la
sindicación**, en cualquier estado (14 RES, 2 ADJ, 4 EV y 2 PUB).
No aparecen los 11 de otros departamentos ni `6.25/28510.5001_01` (código
con sufijo que no está en la sindicación); esta vez son negativos
confirmados con la búsqueda corregida.

**Aportan 710 líneas** (33.214 → 33.924 en base de datos, que cuadra con la
suma de los 22), de las que **515 llegan al Excel** (hoja "Materiales":
14.552 → 15.067 filas). Las 195 restantes no tienen lote y van a la cola de
revisión (`0141`: 6, `0220`: 108, `0257`: 81). 14 de los 22 aportan
líneas; 8 entran con 0.

| Expediente | Estado PCSP | Líneas | En el Excel | Estado final / motivo |
|---|---|---:|---:|---|
| `6.25/28510.0201` | RES | 239 | 239 | pendiente_revision (valores sin interpretar) |
| `6.25/28510.0220` | RES | 158 | 50 | pendiente_revision (cobertura parcial de lotes) |
| `6.24/28510.0125` | RES | 106 | 106 | pendiente_revision (valores sin interpretar) |
| `6.25/28510.0257` | ADJ | 86 | 5 | pendiente_revision (cobertura parcial de lotes) |
| `6.25/28510.0156` | RES | 32 | 32 | pendiente_revision (valores sin interpretar) |
| `6.25/28510.0218` | ADJ | 32 | 32 | pendiente_revision (cobertura parcial de lotes) |
| `6.25/28510.0141` | RES | 17 | 11 | pendiente_revision (cobertura parcial de lotes) |
| `6.25/28510.0221` | EV | 13 | 13 | pendiente_revision (cobertura parcial de lotes) |
| `4.26/28510.0031` | PUB | 11 | 11 | pendiente_revision (valores sin interpretar) |
| `3.24/28510.0063` | RES | 5 | 5 | completado |
| `3.26/28510.0013` | EV | 3 | 3 | pendiente_revision (sin baja: no adjudicado) |
| `3.26/28510.0042` | PUB | 3 | 3 | pendiente_revision (valores sin interpretar) |
| `6.25/28510.0203` | RES | 3 | 3 | completado |
| `6.24/28510.0188` | EV | 2 | 2 | pendiente_revision (valores sin interpretar) |
| `2.24/28510.0050` | RES | 0 | 0 | licitación = adjudicación sin baja declarada |
| `2.25/28510.0005` | RES | 0 | 0 | ninguna línea extraída |
| `2.26/28510.0006` | EV | 0 | 0 | sin Anejo ni Pliego técnico con precios |
| `3.24/28510.0027` | RES | 0 | 0 | ninguna línea extraída |
| `3.24/28510.0126` | RES | 0 | 0 | ninguna línea extraída |
| `3.24/28510.0132` | RES | 0 | 0 | ninguna línea extraída |
| `3.25/28510.0012` | RES | 0 | 0 | ninguna línea extraída |
| `6.17/28510.0056` | RES | 0 | 0 | Anuncio con varios lotes sin asignar |

No se ha investigado por qué esos 8 no dan líneas. Tras el reintento no
queda ningún `sin_publicar` con búsqueda anterior al arreglo.

### C: `sin_publicar` ya no es definitivo

- **Estado.** `estado` sigue siendo `sin_publicar`. Dos columnas nuevas
  (migración 0031): `sin_publicar_en` guarda cuándo confirmó la Plataforma el
  negativo, y `sin_publicar_version_busqueda` con qué versión de la búsqueda
  (`app.mantenimiento.frescura.VERSION_LOGICA_BUSQUEDA`, hoy "2026-09-07").
  Sin versión, o con otra, es un negativo **sin confirmar**. El relleno de la
  migración pone la fecha de la última búsqueda "no encontrado" de cada uno,
  y la versión solo si esa búsqueda es posterior a las 20:00 UTC del
  2026-09-07. La API expone además `sin_publicar_confirmado` y
  `sin_publicar_reintento_desde`, y la web lo dice en cada fila del grupo
  "No publicado": "confirmado el …; se vuelve a buscar a partir del …" o "sin
  confirmar (búsqueda anterior al arreglo del 07/09/2026)".
- **Reintento.** El ciclo de mantenimiento (semanal) vuelve a buscar en la
  Plataforma los `sin_publicar` que toca (`_reintentar_sin_publicar`):
  - los no confirmados, en seguida;
  - los confirmados, pasados 14 días (`SIN_PUBLICAR_REINTENTO_DIAS`), es
    decir, en ciclos alternos.

  Van primero los no confirmados y los más antiguos, con un tope de 50 por
  ciclo (`SIN_PUBLICAR_REINTENTOS_POR_CICLO`; unos 40 s por búsqueda). El
  resumen del ciclo cuenta los reintentados, los aplazados por el tope y los
  que siguen dentro de plazo. Si la búsqueda lo encuentra, la descarga
  encadena la extracción como siempre y vacía las dos columnas.
- **Fallo transitorio en un reintento.** Un timeout o un bloqueo al volver a
  buscar un `sin_publicar` ya no lo pasa a `fallido`: se queda
  `sin_publicar` con la fecha y la versión que tenía, y el ciclo lo vuelve a
  intentar. Solo un "sin resultados" confirmado en todas las variantes
  estampa un negativo nuevo.
- **Desplegado y verificado en vivo.** Migración 0031 aplicada: 81
  `sin_publicar`, todos confirmados (el reintento de la primera parte
  confirmó los que venían de antes), ninguno fuera de su estado con las
  columnas puestas. Con el plazo de 14 días, el ciclo volverá a buscar 64
  a partir del 22-09 (tope de 50: 14 pasan al ciclo siguiente) y 17 a
  partir del 29-09. Prueba en vivo: `2.18/04703.0019` marcado a mano como
  sin confirmar → la API lo da como `sin_publicar_confirmado: false`,
  "toca ya" → búsqueda real → sigue sin resultados y queda confirmado con
  la fecha de hoy y la versión `2026-09-07`.
- Pruebas: 12 nuevas en `test_frescura.py` (incluida la salida de la API),
  `test_ciclo.py` y `test_job.py`. La que exigía excluir siempre los
  `sin_publicar` del ciclo se sustituye. 801 en total.
