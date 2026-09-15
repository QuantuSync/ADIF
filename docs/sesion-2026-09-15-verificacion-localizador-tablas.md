# Sesión 2026-09-15 — verificación de la pasada completa, tablas que no entraban y pendientes antiguos

Encargo en cinco bloques: verificar con un reproceso completo los tres
cambios de ayer que se quedaron sin pasada revisada, y comparar los
**materiales distintos** del Excel con el estado de ayer (5.519); las páginas
que "el localizador no abría" en `6.22/28510.0122` y `6.24/28510.0064`; la
tabla "LOTE 6: RAM NORTE" de `6.22/28510.0016`; tres pendientes antiguos; y
cierre.

Instantáneas de líneas (CSV de `lineas_catalogo`, mismas columnas que las
del 14-09) y Excel exportados en el scratchpad de la sesión; nombres F11-F14
siguiendo la numeración de ayer.

## Bloque 1 — los tres cambios sin verificar

**F11**, la pasada completa lanzada al cerrar ayer, se interrumpió por la
noche (reinicio de `dockerd`; el ciclo pasó a su segundo intento) y terminó
esta mañana a las 06:34. Se comprobó que la imagen del worker era el código
de `HEAD` (último cambio de motor 17:23 UTC, imagen 17:26 UTC, ficheros
clave idénticos byte a byte) y se lanzó una pasada limpia, **F12** (15 min,
358/358): **F11 = F12 byte a byte** (ids incluidos). F10 → F12: solo cambian
`4.25/28510.0207`/`0208` (−10 líneas, las huérfanas de "Lote nº1" pasan a su
lote).

### Los motivos de expediente de lote: verificados

De los 98 expedientes que conocen su lote (uno de sus lotes trae su propio
código), **0** tienen un motivo propio de "EXPEDIENTE PRINCIPAL distinto" y
**0** de "cobertura parcial". Los 10 expedientes que aún tienen el primero
(`6.22/28510.0139`/`0140`/`0142`/`0147`/`0148`/`0149`, `6.23/28510.0073`/`0074`,
`6.25/28510.0187`/`0237`) no saben cuál es su lote: su código no está entre
los lotes que declara su adjudicación. Tres expedientes que sí lo saben
(`6.19/28510.0209`, `6.20/28510.0002`/`0003`) muestran "cobertura parcial"
solo porque citan literalmente el motivo de su matriz ("la matriz … tampoco
tiene cuadro de precios ni baja: …").

### "Lote nº1": fallaba, y por otra causa

La lectura de "Lote nº1"/"Lote nº 2" es correcta en los tres documentos
(ANEJO_1 p.18 y los dos Contratos p.109, lectura en seco: 2 líneas por
lote). Pero tras F12, `0207` (LOTE 1) seguía mostrando **P-03/P-04, que son
del LOTE 2**, con la baja del LOTE 1 (0 %).

Depurado ejecutando la extracción de `0207` instrumentada: la poda del
documento no las borraba porque llevaban `heredado_de_matriz = true`.
`0207` y `0208` figuran en el Excel de códigos como pedidos de `0124`, y en
una pasada antigua (cuando `0207` no tenía líneas propias) heredaron de la
matriz las cuatro líneas del cuadro común. Dos defectos compuestos:

1. **La poda deja fuera, a propósito, las líneas heredadas** ("apuntan a un
   documento de la matriz, que el pedido nunca procesa"). Aquí el documento
   lo comparten matriz y pedido, y la herencia ya no se aplica (el pedido
   sabe su lote): nadie las volvía a escribir ni a borrar.
2. **Las marcas de origen se quedaban pegadas.** `guardar_lineas_catalogo`
   no pisa un valor con `None` ("esta pasada no trae el dato"), y eso valía
   también para `heredado_de_matriz`, `lote_heredado_de_pagina_anterior` y
   `lote_del_expediente`: un `true` de una pasada vieja era para siempre,
   aunque la línea saliera ya del propio documento y con cabecera explícita.

Arreglo:

- Las tres marcas se recalculan en cada pasada, como `motivo_revision`
  (`catalogo._MARCAS_DE_ORIGEN`). Dentro de una misma pasada, si varios
  documentos escriben la misma línea, la marca queda en `true` solo si todos
  coinciden; y no se rellena desde una fila absorbida por firma.
- `podar_lineas_heredadas_obsoletas`: al final de la extracción, las líneas
  todavía marcadas como heredadas que la herencia de esta pasada no ha
  escrito (`ResultadoHerencia.ids_tocadas`) se borran. Salvo si la herencia
  está pendiente (matriz en proceso, o ciclo): entonces se conservan hasta
  que se pueda decidir.

**F13** (15 min, con el arreglo) frente a F12: −4 líneas, las cuatro del
mismo defecto: P-03/P-04 del LOTE 2 en el LOTE 1 de `0207`, y dos
matrículas del LOTE 2 (`6.20/28510.0029`, fuera del catálogo) en el LOTE 1
de `6.20/28510.0028` (592100027, 592100008; siguen en su matriz `0195` y en
`0028` como tabla de otro lote). Ningún material desaparece. Marcas
corregidas: `heredado_de_matriz` 957 → 339 líneas (618 salían en realidad
de los propios documentos del pedido), `lote_del_expediente` 18 → 4,
herencia de lote entre páginas 5.395 → 5.284. Las marcas solo se muestran
como trazabilidad en la web; el Excel no las usa.

### Excel: materiales distintos contra ayer

| | Ayer (E5) | F13 |
|---|---:|---:|
| Filas en Materiales | 15.979 | 14.474 |
| Materiales distintos (matrícula, o descripción sin espacios ni signos) | 5.519 | 5.463 |
| — con matrícula | 3.322 | 3.234 |
| Pendientes de revisión (Resumen) | 6.136 | 5.374 |
| Anejo de criterios, fila propia en el Resumen | — | 13.288 |

14.474 + 5.374 + 13.288 = 33.136, las líneas de la base de datos.

Los 315 materiales que salen del Excel **siguen todos en la base de datos**
(ninguno "no está"). Dónde están:

| Qué son | Materiales |
|---|---:|
| Descripción del anejo de criterios de `0051`/`0060` (211) y `0236`/`0237` (5): el mismo material está en el Excel con el texto del cuadro de precios (buena parte de los 259 "nuevos" son esas mismas piezas, `0051`/`0060`) | 216 |
| Tabla de un lote que el expediente no tiene (`6.20/28510.0094`/`0141`, `6.21/28510.0017`, familia `6.21/28510.0058`/`0130`, `6.24/28510.0064` LOTE 3, `3.23/28510.0135`): antes salían atribuidas a otro lote | 65 |
| Tabla de un hermano fuera del catálogo (`6.21/28510.0066`, "LISTADO LOTE 1" de `0065`) | 17 |
| Tabla sin cabecera de lote (`6.21/28510.0017`, familia `0058`/`0130`) | 16 |
| Con lote, fuera del Excel por otro motivo | 1 |

Todo ese movimiento es de la tercera parte de ayer (pasadas F1-F10), no del
arreglo de hoy: F12 y F13 solo difieren en las 4 líneas de arriba. **Lo que
decide si el catálogo se entrega** son los ~98 materiales de la segunda a
la cuarta fila: están en tablas de lotes cuyo expediente no está en el
catálogo, o sin lote, y por eso no salen en el Excel de nadie. Es la
decisión pendiente desde el 12-09 (bloque 4).
