# Sesión 2026-09-08: auditoría automática del catálogo, duplicado de
# `6.23/28510.0051` y 708 líneas sin código interno

Continuación de la sesión de herencia de lote entre páginas de continuación
(mismo día, `docs/sesion-2026-09-08-herencia-lote-continuacion.md`, 3.102 →
494 pendientes). Estado del catálogo al empezar esta sesión: 9.914 líneas
entregadas, 494 pendientes, 467 expedientes.

---

## Bloque 1 — Auditoría automática

### Motivación

Cada vez que el corpus ha crecido han aparecido fallos que nadie buscaba
(colisión de hash entre expedientes hermanos, firma de cabecera vacía
compartida entre tablas de estructura distinta, líneas sin
expediente/descripción/lote, precios a cero, duplicados por clave inestable
— CONTEXTO.md sección 16), siempre encontrados a mano. Encargo: montar una
auditoría que corra sola al terminar cada ciclo de mantenimiento y avise
cuando algo no cuadre, **sin corregir nada por su cuenta**.

### Diseño

Nuevo módulo `engine/app/mantenimiento/auditoria.py`, mismo patrón que
`app.mantenimiento.copia_seguridad`/`app.mantenimiento.ciclo`: un tipo de
trabajo más de la cola (`auditoria_catalogo`), nunca un script aparte.
`app.mantenimiento.ciclo.ejecutar_ciclo_mantenimiento` la encola y la
ejecuta ella misma, síncronamente, justo después de que el drenaje normal
del ciclo termine — audita el catálogo ya con las descargas/extracciones de
esa misma pasada aplicadas, y un fallo suyo nunca tira el resto del ciclo
(try/except propio, igual que el bloque de descubrimiento por sindicación).
También se puede lanzar a mano (`POST /mantenimiento/auditoria/ejecutar`) y
consultar (`GET /mantenimiento/auditoria/estado`,
`GET /mantenimiento/auditoria/historial`) — visible en `/mantenimiento`
junto al resto.

Ocho comprobaciones de solo lectura, cada una con su propio umbral
justificado contra hallazgos ya verificados en sesiones anteriores (nunca
inventado): duplicadas exactas dentro de expediente+lote, líneas sin
descripción/sin lote, precios a cero/negativos/desproporcionados frente a
la mediana del expediente (>50x o <1/50x, mismo criterio que la sesión de
verificación del Excel 2026-09-06), cantidades con forma de año, bajas
fuera de rango (negativa/≥100% como error, >90% como aviso — el máximo real
del corpus es 47,87%), firma de cabecera cacheada vacía o no reproducible
(regresión del arreglo de la sesión de verificación del Excel de 6.599
líneas), líneas de un expediente que cambian de número sin que cambie su
huella de documentos (comparado contra la ejecución anterior de la propia
auditoría, no contra la de `app.mantenimiento.frescura` que ya vigila esto
expediente a expediente en el momento de reprocesar), y campos vacíos por
columna que crecen más de 5 puntos porcentuales respecto a la ejecución
anterior. 13 tests nuevos (`engine/tests/mantenimiento/test_auditoria.py`),
478 tests totales del proyecto pasan.

### Primer informe real, ejecutado sobre el estado actual (10.408 líneas,
467 expedientes)

**0 errores, 4 avisos:**

- **494 líneas huérfanas sin lote** (12 expedientes) — estado esperado del
  sistema (cola de revisión), no un error por sí solo.
- **504 líneas con precio a más de 50x/menos de 1/50x la mediana de su
  expediente** (95 expedientes) — mismo patrón ya verificado en la sesión
  de 2026-09-06 (partidas alzadas, precio por unidad de medida distinta),
  a confirmar caso a caso.
- **290 líneas con cantidad en forma de año** (19 expedientes) — mismo
  hallazgo de la sesión 2026-09-07, puede ser una "CANTIDAD DE REFERENCIA"
  real y ambigua del documento.
- **17 lotes con baja por encima del 90%** — a confirmar contra el
  documento de origen.

**0 duplicadas exactas, 0 firmas de cabecera vacías o corruptas, 0 líneas
sin descripción.** Vacío por columna: `lote_id` 4,75%, `cantidad` 11,11%,
`codigo_precio` 25,28%, `unidad_medida` 30,28%, `precio_unitario` 1,35%.

---

## Bloque 2 — Dos hallazgos del Excel

### 1. Duplicado exacto en `6.23/28510.0051`

**Síntoma reportado:** `P-0058`/`P-0059`, misma línea repetida con idéntico
precio y lote (`CAM1H-60-1500-TC-D CAM1H-60-1500-TC-I`, 306.351,49 € en las
dos, `lote_id=197`).

**Causa raíz, verificada contra el PDF real** (página 57 del ANEJO_1):
`pdfplumber` funde dos filas simples y consecutivas de la tabla en una sola
fila extraída (mismo mecanismo que el arreglo de la sesión 2026-09-06 para
`P-0090`/`P-0091`, `app.catalogo._dividir_fila_multiple`). Ese arreglo ya
separa correctamente el código y el precio en sus N líneas reales, pero
**nunca repartía la descripción** — por diseño, para no arriesgarse a
emparejar mal cuando el número de líneas de descripción no coincide con el
de códigos (el caso real que sí motivó esa cautela, `P-0090`/`P-0091`, donde
la descripción trae 4 líneas para solo 2 códigos). El resultado en
`6.23/28510.0051`: las dos líneas separadas se quedaban con el bloque
íntegro de descripción repetido, indistinguibles entre sí salvo por su
código de precio.

Comprobado contra el PDF (`pdfplumber`) que en este caso concreto **la
descripción sí se divide limpiamente en 2 líneas, una por código**
(`"CAM1H-60-1500-TC-D\nCAM1H-60-1500-TC-I"` para
`"P-0058\nP-0059"`) — el mismo patrón D/I (derecha/izquierda) que las dos
filas sin fusionar dos posiciones más arriba en la misma tabla
(`P-0056`/`P-0057`, `CAMH-60-1500-TC-D`/`CAMH-60-1500-TC-I`, también al
mismo precio).

**Arreglo:** `_dividir_fila_multiple` reparte también la descripción 1:1
cuando (y solo cuando) se divide en exactamente el mismo número de líneas
que el código y el precio — si no coincide, se mantiene el comportamiento
anterior (bloque completo + motivo de revisión). 5 tests actualizados/
nuevos en `engine/tests/test_catalogo.py` para cubrir los dos casos (limpio
y ambiguo) por separado.

**Limpieza:** expediente reprocesado contra el stack real
(`POST /mantenimiento/ejecutar`, `forzar_expedientes: [18]`). Las dos
líneas duplicadas quedan ahora con su propia descripción
(`CAM1H-60-1500-TC-D` / `CAM1H-60-1500-TC-I`), sin motivo de revisión por
ambigüedad. Efecto de paso, correcto y esperado: al tener ya descripciones
distintas, cada una vuelve a pasar por `_firma_material` (antes excluida a
propósito mientras compartían el bloque) y cada una funde con una segunda
mención real del mismo material sin matrícula en otra tabla del mismo
documento (páginas 16 y 25, "CAM1H-60-1500" — verificado con `pdfplumber`),
el mismo mecanismo ya documentado de tablas de impacto/normativa que repiten
un material con su mismo precio bajo un `codigo_precio` distinto.

### 2. 708 líneas sin código interno ni código de proyecto

22 expedientes, 708 líneas entregables (9.914 del total menos las
excluidas del Excel por descarte o por no tener lote). Ambas columnas del
Excel dependen del mismo campo, `expediente.codigos_cruzados`: si es
`False`, las dos se dejan vacías por diseño (`app.exportacion`, "el sistema
nunca inventa una matriz").

Comprobado uno a uno contra `codigos_proyecto.xlsx` (665 filas, cargado
completo, `Nº Expediente` y `MATRIZ` indexados):

- **19 de los 22 no figuran en el Excel de ADIF en absoluto** — ni como
  `Nº Expediente` ni como `MATRIZ`, en ninguna de las dos claves por las que
  cruza el sistema. No es un fallo del cruce: el propio Excel de ADIF no
  trae esos expedientes. Lista completa:
  `6.24/28510.0184` (113), `6.22/28510.0160` (106), `6.25/28510.0121` (64),
  `6.24/28510.0208` (54), `6.21/28510.0093` (46), `6.26/28510.0016` (41),
  `6.24/28510.0173` (34), `6.24/28510.0096` (34), `6.24/28510.0209` (31),
  `4.26/28510.0020` (24), `4.23/28510.0140` (21), `6.24/28510.0067` (18),
  `6.25/28510.0265` (18), `6.25/28510.0251` (14), `4.25/28510.0132` (12),
  `6.23/28510.0137` (4), `3.25/28510.0164` (3), `6.25/28510.0118` (2),
  `6.25/28510.0190` (1) — número entre paréntesis, líneas afectadas.
- **3 de los 22 sí son un fallo real de cruce**, no una ausencia del
  Excel: `6.26/28510.0032` (39 líneas), `6.26/28510.0071` (39) y
  `6.26/28510.0014` (14). Los tres son pedidos derivados de acuerdo marco,
  descubiertos por el mecanismo de descubrimiento inverso matriz → pedidos
  (sesión 2026-09-07). Su `codigo_matriz` (`6.20/28510.0136` los dos
  primeros, `6.25/28510.0016` el tercero) **sí figura en el Excel de
  ADIF** — verificado en vivo: `cruzar_codigo_proyecto` con sus valores
  actuales de `codigo_matriz` cruza correctamente los tres (código interno
  `20012`, `20012`, `24036`). La causa es una carrera de orden: el cruce
  (`asegurar_cruce_codigos`) se intenta una sola vez por expediente y nunca
  se reintenta (`codigos_cruzados` pasa de `None` a `True`/`False` para
  siempre, por diseño — mismo mecanismo que ya causó el bug del bind-mount
  roto de la sesión 2026-09-06), pero para un pedido descubierto por el
  mecanismo inverso, `codigo_matriz` puede resolverse **después** de que el
  primer intento de cruce ya se ejecutara y fallara. No implementado
  (fuera del encargo de esta sesión, que pedía diagnóstico: "dime de qué
  expedientes son y si el problema es que no figuran... o que el cruce
  falla"): un reintento de cruce cuando `codigo_matriz` cambia después del
  primer intento fallido.
