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
