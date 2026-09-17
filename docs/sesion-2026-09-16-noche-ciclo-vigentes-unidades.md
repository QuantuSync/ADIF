# Sesión 2026-09-16 (noche) — Ciclo completo, vigentes con remanente, 2026 del SAP, unidades y duplicados

Seis bloques. Cifras medidas contra la base de datos y el Excel real.

## Bloque 1 — Ciclo completo de mantenimiento

**Antes de lanzar:**

- Copia de seguridad: `/backups/adif_20260916_antes_ciclo_noche.dump`
  (volumen `copias_seguridad_bd`, `pg_dump --format=custom`).
- Foto del relleno por columna (34.210 líneas, 272 expedientes con líneas):

| Columna | Líneas con valor |
|---|---|
| codigo_precio | 24.907 |
| matricula | 17.354 |
| descripcion | 34.210 |
| codigo_material | 22.028 |
| cantidad | 16.087 |
| precio_unitario | 33.522 |
| unidad_medida | 27.869 |
| baja_lote | 8.827 |
| precio_adjudicado | 8.645 |
| lote_id | 15.517 |

  Expedientes: 129 `pendiente`, 342 `pendiente_revision`, 44 `completado`,
  81 `sin_publicar`. Excel previo: 15.351 filas en "Materiales".

- **Control de ritmo:** el espaciado entre peticiones a la Plataforma
  (`scraping_separacion_minima_segundos`, turno compartido por descargas,
  búsquedas y pasos de página) no se podía cambiar sin tocar código; ahora
  es `SCRAPING_SEPARACION_MINIMA_SEGUNDOS` en el worker, **10 s** por defecto
  en `docker-compose.yml` (el código sigue en 5 s).

Lanzado a mano (`POST /mantenimiento/ejecutar`, trabajo 19321, sin forzar:
la subida de `VERSION_LOGICA_EXTRACCION` a `2026-09-16` ya obliga a
reextraer todo). Sindicación del mes: 8 del departamento, 0 nuevos.
Búsqueda por `28510`: 368 códigos válidos (2 descartados por dígitos
pegados), todos ya conocidos.

**Resultado.** El ciclo terminó sin fallar en 1 h 47 min (21:15-23:02
UTC): 129 descargas del ciclo, todas con éxito, y la reextracción de todo el
corpus. Durante el ciclo se detectaron y corrigieron dos defectos, desplegados
al terminar (ver abajo).

**Los 129 expedientes nuevos:**

| | Expedientes |
|---|---|
| Encontrados y descargados en la Plataforma | **129** |
| No encontrados | **0** |
| Con documentos | 127 (2 sin ningún documento seleccionable: `6.14/28510.0148`, `0177`) |
| Con líneas de catálogo | **34** — **1.110 líneas** |
| Con filas en el Excel | 31 — **644 filas** |
| Estado final | 6 `completado`, 123 `pendiente_revision` |

Los que más aportan: `6.22/28510.0173` (184 filas), `6.23/28510.0097` (83),
`2.23/28510.0108` (82), `6.22/28510.0163` (54), `6.22/28510.0034` (33).
Casi todos son de 2019-2023; los de 2013-2018 apenas aportan.

Los **95 sin líneas**, por motivo:

| Motivo | Expedientes |
|---|---|
| Documentos escaneados, sin capa de texto (fuera de alcance, sección 15) | 47 |
| Sin anejo ni pliego técnico con cuadro de precios | 15 |
| Documentos con texto pero sin cuadro de precios legible | 8 |
| Pedido cuya matriz no está publicada | 7 |
| Anuncio de adjudicación multi-lote sin bloque propio identificable | 7 |
| Cobertura parcial de lotes / documento compartido con hermanos / adjudicación de otro expediente | 9 |
| Sin ningún documento seleccionable | 2 |

Los escaneados son la mitad: con documentos anteriores a 2020 el límite de
OCR (sección 15) pasa de ser un caso aislado a ser la causa principal.

**Dos defectos encontrados en caliente, corregidos y desplegados:**

1. **Objeto del contrato desbordado.** `6.21/28510.0040`, `6.15/28510.0081`,
   `3.17/28510.0124` y `6.17/28510.0123` fallaban enteros: su anuncio no
   repite el objeto en una línea "Descripción", la expresión seguía hasta
   "Descripción de Programas de Financiación" y el título no cabía en
   `nombre_proyecto` (255). El objeto termina ahora también en la siguiente
   etiqueta fija ("Valor estimado del contrato", "Presupuesto base de
   licitación", "Clasificación CPV", "Tipo de Contrato"), y
   `nombre_proyecto` y `trazas_origen.valor_extraido` pasan a texto
   (migración 0033: hay títulos reales de 292 caracteres). Reextraídos:
   `0040` aporta 16 líneas; ninguno guardaba antes un título con basura.
2. **Filas de totales como líneas sin descripción.** `6.22/28510.0174`
   ("PRESUPUESTO DE LICITACIÓN | … | 59.960,00 €", la etiqueta en la columna
   de código) y `6.21/28510.0026` ("21% IVA 7.350,00 €" pegado en la columna
   de cantidad, leído como **217.350 €**). Una fila sin descripción ni
   matrícula cuyo único texto, quitadas cifras y símbolos, es una etiqueta de
   total, es pie de tabla. Solo afectaba a esos dos en todo el corpus; la
   auditoría deja de dar el error "líneas sin descripción".

**Fuera de los 129**, el ciclo solo cambia: 10 expedientes pasan de
`pendiente_revision` a `completado` (tenían el falso "posible duplicación"
del guard de integridad anterior al arreglo de ayer), `6.25/28510.0246` gana
3 líneas, y el descubrimiento de matrices de pedidos da de alta 4
(`6.17/28510.0031`, `2.21/23108.0113`, `2.18/04703.0026` sin publicar;
`2.19/23108.0127` escaneado).

## Bloque 2 — Vigentes con remanente

<!-- RESULTADO_BLOQUE_2 -->

## Bloque 3 — Los 13 expedientes de 2026 del SAP del cliente

| Expediente | En el sistema antes | En la Plataforma |
|---|---|---|
| `6.26/28510.0002` | no | no |
| `6.26/28510.0003` | no | no (solo `6.17/` y `6.18/28510.0003`) |
| `6.26/28510.0009` | sí, 6 documentos, 14 líneas | sí |
| `6.26/28510.0040` | sí, 3 documentos, 7 líneas | sí |
| `6.26/28510.0057` | no | no |
| `6.26/28510.0083` | no | no (solo `6.23/`, `2.20/`, `2.18/`) |
| `6.26/28510.0087` | no | no (solo `6.23/`) |
| `6.26/28510.0088` | no | no (solo `6.25/`, `6.24/`, `6.23/`) |
| `6.26/28510.0089` | no | no (solo `6.22/`, `6.20/`, `2.18/`) |
| `6.26/28510.0090` | no | no (solo `6.22/`) |
| `6.26/28510.0091` | no | no (solo `6.22/`) |
| `6.26/28510.0092` | no | no (solo `6.22/`) |
| `6.26/28510.0103` | no | no (solo `6.24/`, `6.22/`, `2.20/`) |

**Por qué faltaban: no están publicados en la Plataforma.** Buscados uno a
uno por el fragmento `28510.NNNN` (el campo "Nº de expediente" busca por
subcadena y trata `/`, `.` y `_` como equivalentes: `26_28510` devuelve los
21 `*.26/28510.*`), la Plataforma devuelve el mismo número de otros años,
nunca el de 2026. Probadas también otras formas (`26.28510.0057`,
`2026/28510`, `28510/2026`, `626/28510`): nada. La búsqueda por `28510` del
propio ciclo de esta noche (368 códigos) tampoco los trae. No es un fallo del
descubrimiento: ni la sindicación ni la búsqueda pueden ver lo que no está
publicado.

**Corrección:** los 11 quedan dados de alta en el sistema (`POST
/expedientes`) y con su búsqueda encolada. Pasan a `sin_publicar` confirmado,
y el ciclo semanal los vuelve a buscar cada 14 días
(`SIN_PUBLICAR_REINTENTO_DIAS`): en cuanto ADIF los publique, entran solos.
Si el cliente tiene los documentos, la vía para cargarlos antes es la
ingesta local (`INGESTA_LOCAL_PATH`).

**Qué producen los dos que sí están** (tras la reextracción de esta noche):

- `6.26/28510.0009` — "Suministro de elementos de control para subestaciones
  móviles", resuelto (RES), adjudicado a Ribodel SL. 6 documentos, **14
  líneas** del Anejo 1 (P-01 a P-14), baja del lote 28,50 %, precio
  adjudicado derivado en las 14. Cantidad vacía en 13: el cuadro la da
  distinta en el Contrato y en el Anejo para el mismo código ("pendiente",
  decisión del cliente de la sesión 2026-09-14).
- `6.26/28510.0040` — relés de protección de subestaciones de tracción, **en
  evaluación** (EV): 3 documentos (pliego y anejos), **7 líneas** con precio
  de licitación, sin baja ni precio adjudicado porque todavía no hay
  adjudicación. Es el estado real, no un hueco.

## Bloque 4 — Una forma única por unidad de medida

32 valores distintos (más el vacío) antes. Verificado contra el catálogo
antes de unificar lo que no era obvio: `M` es metro (cable, carril,
pletina) y `T` tonelada (balasto).

`app.extraccion.unidad_medida.normalizar_unidad` lleva cada unidad a su forma
única, parte a parte en las compuestas ("·" para el producto, "/" para el
cociente). `lineas_catalogo.unidad_medida_original` (migración 0032) guarda
el valor tal como venía; la web lo enseña en el detalle de la línea cuando
difiere. Se aplica en la extracción, en el relleno desde el maestro de SAP
(que además compara ya en forma única al buscar discrepancias) y en la
herencia de matriz. Lo ya guardado se normaliza en la propia migración, sin
reextraer.

| Forma única | Valores que agrupa | Líneas |
|---|---|---|
| `ud` | UD., UN, UD, ud, Ud., Unidad | 25.305 |
| `m` | M, m | 980 |
| `t` | t, T, Ton | 591 |
| `kg` | Kg, KG | 478 |
| `t·km` | Txkm, t x km, Ton*km | 184 |
| `m3` | m3, m³ | 75 |
| `h` | h, Hora, h. | 29 |
| `dm3` | dm3, DM3 | 28 |
| `t·mes` | Ton*mes | 23 |
| `m3·km` | m3xkm | 16 |
| `ud/día` | UD/día | 8 |
| `m2` | m² | 7 |
| `mes` | Mes | 4 |
| `elemento·mes` | Elemento x mes | 3 |
| `transporte` | transporte | 69 |
| `PA` | PA | 66 |
| `P` | P | 3 |

(Medido sobre la copia de la base previa al ciclo con la migración aplicada.)
**De 32 valores distintos a 17.**

**Separados a propósito** (no son claramente lo mismo): `PA` (partida
alzada) no es `ud`; `P` (3 líneas, viene del maestro de SAP sin nombre
completo) no se da por `PA` ni por `ud`; `transporte` se queda como
unidad propia; `ml` (metro lineal o mililitro) y `pieza` no se unifican si
aparecen.

**Aplicado en la base real** (migración 0032 desplegada tras el ciclo):
35.323 líneas, 17 valores distintos de unidad, 28.100 con valor original
guardado. En el Excel: 17 valores más la celda vacía (antes 32).

## Bloque 5 — Los 11 grupos duplicados

Los 11 grupos (22 filas) del Excel son **duplicados legítimos del
documento**, verificados en el PDF. Se dejan.

- `6.23/28510.0051` y `6.23/28510.0060` (el mismo `CONTRATO_2`, 5 grupos cada
  uno): el cuadro de precios repite la misma descripción y el mismo precio
  bajo dos códigos distintos — P-0166/P-0178 "Semicambio izq (sencillo)
  DIRD-B1-54-190-0.11-CR-D" (p. 117 y 118), P-0167/P-0179 "Semicambio dcha",
  P-0458/P-0476 "Corazón sencillo", P-0459/P-0477 "Contracarril directa" y
  P-0460/P-0478 "Contracarril desviada" (p. 130 y 131). Por la serie de
  alrededor (P-0180 ya es `DIRI-…-CR-I`), P-0178/P-0179 y P-0476-P-0478
  parecen una errata del pliego que debía decir la variante izquierda
  (`DIRI…-I`), pero el documento dice lo que dice: no se corrige.
- `4.25/28510.0132` (1 grupo): el anejo, p. 38, trae "JUEGO DE TIMONERÍA DE
  MANDO Y COMPROBACIÓN" a 1.262,94 € dos veces, Cod0005 y Cod0013.

**Por qué se ven como duplicados:** la clave del catálogo es el código de
precio (sección 7 de CONTEXTO.md) y son códigos distintos, pero el Excel no
lleva la columna de código de precio, así que las dos filas salen idénticas.
Si el cliente quiere distinguirlas a simple vista, la opción es añadir
"Código de precio" como columna al final (sin tocar el orden de las once
originales) — decisión suya, no tomada. La auditoría los sigue contando como
su único "error" conocido.

## Bloque 6 — Cierre: auditoría, Excel y comparación

Copia posterior al ciclo, antes de desplegar:
`/backups/adif_20260917_despues_ciclo_antes_despliegue.dump`.

**Base de datos, antes → después:**

| Columna | Antes | Después |
|---|---|---|
| Líneas | 34.210 | **35.323** (+1.113) |
| codigo_precio | 24.907 | 25.215 |
| matricula | 17.354 | 17.995 |
| codigo_material | 22.028 | 22.569 |
| cantidad | 16.087 | 17.045 |
| precio_unitario | 33.522 | 34.398 |
| unidad_medida | 27.869 | 28.100 |
| baja_lote | 8.827 | 9.046 |
| precio_adjudicado | 8.645 | 8.843 |
| lote_id | 15.517 | 16.164 |
| Expedientes con líneas | 272 | 306 |

**Excel ("Materiales"), antes → después:** 15.351 → **15.998 filas**;
expedientes con filas 272 → 303; matrícula 9.598 → 10.037; cantidad 10.438 →
10.940; precio unitario 15.144 → 15.752; baja del lote 8.827 → 9.046.
**Materiales distintos 6.616 → 7.034: 0 perdidos, 418 nuevos. Ningún
expediente pierde filas.** Unidades distintas en el Excel: 32 → 17.

**Auditoría** (trabajo 19991): un solo error, los 11 grupos duplicados
legítimos del bloque 5. Los avisos de siempre (huérfanas sin lote, precios
atípicos, cantidades con forma de año, importes compartidos). Los tres
expedientes con "líneas que cambian sin cambiar documentos" son los arreglos
de esta noche (`6.21/28510.0040` recupera 16; `0026` y `0174` pierden las
filas de totales).

## Pendiente al cerrar

- **Bloque 2 sin hacer**: el fichero
  `Ejemplo/Input/EXPEDIENTES_VIGENTES_CON_REMANENTE.xlsx` no estaba en el
  repositorio en ningún momento de la sesión. El script de cruce está
  preparado; en cuanto esté el fichero es una pasada corta.
- 47 de los 129 nuevos solo tienen documentos escaneados: si el cliente los
  quiere, es la decisión de OCR/modelo multimodal de la sección 15.
- Los 11 expedientes de 2026 del SAP no publicados: preguntar al cliente si
  se tramitan fuera de la Plataforma (contrato menor, otro órgano) o si
  puede aportar los documentos por la ingesta local.
- "Código de precio" como columna del Excel para distinguir los duplicados
  legítimos: decisión del cliente.
- `PA` (66 líneas) y `P` (3) siguen pendientes de decisión (sesión anterior).
