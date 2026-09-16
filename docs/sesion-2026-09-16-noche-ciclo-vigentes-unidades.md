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

<!-- RESULTADO_BLOQUE_1 -->

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

<!-- RESULTADO_BLOQUE_3 -->

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

<!-- RESULTADO_BLOQUE_4 -->

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

<!-- RESULTADO_BLOQUE_6 -->
