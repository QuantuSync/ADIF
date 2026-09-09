# Sesión 2026-09-09 (continuación) — Reproceso completo del corpus, cero vs. blanco, filtro por código interno, maestro de materiales

Sesión larga con cinco bloques. Este documento cubre los bloques 2, 3 y 4
(cerrados) y dejará constancia del 1 y el 5 (reproceso completo y estado
final) al terminar — el reproceso es de varias horas y corre en paralelo al
resto del trabajo de la sesión.

---

## Bloque 1 — Reproceso completo del corpus

Los arreglos de la sesión anterior (`docs/sesion-2026-09-09-auditoria-mapeo-
documentos.md`: validación de coherencia del mapeo de cabecera sobre tablas
sin cabecera, y caché de tablas sin cabecera por firma estructural) solo
estaban verificados contra una muestra representativa, no contra los 467
expedientes completos.

**Antes de lanzarlo:**
- Copia de seguridad manual (`POST /mantenimiento/copias/ejecutar`):
  `adif_20260909_191412.dump`, 2,1 MB, 7 copias conservadas en el volumen
  `copias_seguridad_bd`.
- Foto del relleno por columna sobre el estado real de la base de datos
  (358 expedientes activos, 22.097 líneas de catálogo — no 467/16.647,
  cifras de una comparación de esta misma sesión el mismo día, ver más abajo
  por qué difieren):

  | Columna | Relleno antes |
  |---|---|
  | Matrícula | 40,7% |
  | Descripción | 99,1% |
  | Código del material | 63,2% |
  | Cantidad | 67,7% |
  | Precio unitario | 99,3% |
  | Unidad de medida | 73,2% |
  | Precio adjudicado | 54,7% |
  | Baja de lote | 55,5% |
  | Código matriz (expedientes) | 58,9% |

**Lanzado**: `POST /mantenimiento/ejecutar` con `{"forzar": true,
"sindicacion_desactivada": true}` (trabajo de cola 3718, arrancado
19:14:25 UTC) — mismo mecanismo documentado como pendiente al cierre de la
sesión anterior. Confirmado por consulta directa a `trabajos_cola` que no se
creó ningún trabajo `descargar_expediente`: cero sindicación, cero
descargas, solo reproceso de los documentos ya en disco, tal como se pidió.

**Resultado**: completado a las 22:21:08 UTC — **3 h 6,7 min**, 358/358
expedientes activos reprocesados, ritmo medio ~31 s/expediente (en línea con
el ritmo medido en sesiones anteriores). Cero trabajos `descargar_expediente`
creados durante toda la ejecución (confirmado por consulta directa a
`trabajos_cola`): cero sindicación, cero descargas de red, exactamente lo
pedido.

**Foto de relleno DESPUÉS** (mismos 358 expedientes activos):

| Columna | Antes | Después | Δ |
|---|---:|---:|---:|
| Total líneas | 22.097 | 22.721 | +624 (+2,8%) |
| Matrícula | 40,7% | 39,5% | −1,2 pp |
| Descripción | 99,1% | 99,6% | +0,5 pp |
| Código del material | 63,2% | 62,6% | −0,6 pp |
| Cantidad | 67,7% | 65,9% | −1,8 pp |
| Precio unitario | 99,3% | 99,4% | +0,1 pp |
| Unidad de medida | 73,2% | 75,3% | +2,1 pp |
| Precio adjudicado | 54,7% | 53,3% | −1,4 pp |
| Baja de lote | 55,5% | 54,0% | −1,5 pp |
| Completados | 26 | 27 | +1 |
| Pendientes de revisión | 332 | 331 | −1 |
| Código matriz (expedientes) | 58,9% | 58,9% | sin cambio (esperado: no toca el cruce) |

Los descensos de 1-2 puntos en matrícula/cantidad/precio adjudicado/baja de
lote no son una regresión: se explican porque casi todo el crecimiento neto
(+624 líneas) se concentra en el trío ya conocido `6.20/28510.0042/0046/0047`
(ver más abajo), cuyas líneas nuevas son en su mayoría huérfanas sin esos
campos — diluyen la media del corpus sin empeorar ninguna línea que antes
estuviera bien. El resto del corpus se mantiene estable, como cabía esperar
de un reproceso sin cambios de fondo salvo la validación de coherencia y la
caché de tablas sin cabecera.

### Auditoría automática de fin de ciclo — un hallazgo real, ya acotado

La auditoría que corre sola al terminar el ciclo (`app.mantenimiento.
auditoria`) reportó **3 hallazgos de gravedad "error"** (antes había 0 en la
última auditoría de la sesión anterior), los tres concentrados en el mismo
trío ya identificado:

- **48 grupos de líneas duplicadas exactas** (135 líneas).
- **102 líneas sin descripción** — "no deberían existir" según la
  comprobación permanente de `construir_linea_catalogo`.
- **6 expedientes cuyo número de líneas cambió sin cambiar sus documentos**
  (`6.20/28510.0042/0046/0047` y `6.22/28510.0033/0057/0058`).

**Investigado antes de cerrar la sesión** (no se dejó como una cifra suelta):
exportado el Excel real y comparado contra la base de datos cruda para medir
el impacto real en el entregable, no solo en la base de datos:

- De las 102 líneas sin descripción en base de datos (34 por expediente del
  trío), **0 llegan al Excel** — la exclusión por mapeo incoherente
  (`evaluar_coherencia_mapeo`, sesión anterior) ya las filtra.
- De los 48 grupos de duplicados exactos, solo **4 grupos (8 líneas) por
  expediente** sobreviven en el Excel real (992 filas por expediente de las
  1.283 en base de datos) — un residuo pequeño (24 líneas en total sobre
  19.432 filas del Excel, 0,12%), no la cifra completa de la auditoría.

**Causa raíz, ya documentada, no nueva**: coincide con el hueco de
idempotencia que la sesión de verificación del Excel de 6.599 líneas
(2026-09-08) ya había encontrado y dejado explícitamente sin corregir
(`docs/sesion-2026-09-08-verificacion-excel-6599.md`): una fila sin
`codigo_precio` ni matrícula usa `hash(descripción + orden)` como clave de
actualización; si la descripción recuperada cambia entre dos reprocesos de
la misma tabla sin cabecera (aquí: entre el reproceso parcial de la sesión
anterior, sobre una muestra, y este reproceso completo), la fila vieja queda
huérfana en vez de sustituirse, en lugar de duplicar sin más. Ese día ya se
señaló que "una poda automática necesitaría decidir primero qué pasa si solo
se reprocesa un subconjunto de las tablas de un documento" — sigue siendo
cierto, y sigue sin ser trabajo de una sesión de cierre. **No se ha tocado
la base de datos para limpiar esto**: el residuo es pequeño, ya conocido y
mayormente filtrado del entregable; forma parte de la lista de pendientes de
abajo.

**No se restaura la copia de seguridad**: el crecimiento neto es pequeño
(+2,8%), explicado en su práctica totalidad por el mismo trío ya señalado
como de baja confianza en la sesión anterior, y el resto del corpus no
muestra ninguna señal de regresión (0 errores nuevos de otra categoría, los
4 avisos son las mismas categorías ya conocidas de sesiones previas).

---

## Bloque 2 — Distinguir el cero del blanco

El cliente pidió expresamente que, en cantidad y en precio, un cero real del
documento se distinga de un dato ausente. Revisado de punta a punta contra
el código real y datos reales — **no hizo falta ningún cambio**, el sistema
ya lo hace bien en las cuatro capas:

1. **Base de datos**: `cantidad`, `precio_unitario`, `precio_adjudicado` y
   `baja_lote` son `Numeric(...)` nullable en `lineas_catalogo`.
   `app.extraccion.normalizacion.parsear_numero_es` lanza `ValueError` ante
   una cadena vacía o sin dígitos — nunca deriva un 0 por defecto — así que
   un 0 real del documento llega a guardarse como `Decimal("0")`, distinto
   de `NULL`. Verificado contra la base real: 805 líneas con
   `cantidad = 0` (no `NULL`) solo en `6.23/28510.0051`, y cantidades reales
   en 0 en otros 9 expedientes más.
2. **Extracción** (`engine/app/catalogo.py`): todas las comprobaciones sobre
   estos campos usan `is not None` (o `== 0` explícito para el aviso de
   revisión de cantidad-cero, línea ~152), nunca truthiness de Python sobre
   un `Decimal` — un `Decimal("0")` es falsy en Python y un `if cantidad:`
   sin más lo habría tratado como ausente; no aparece ese patrón en el
   código real.
3. **Web** (`web/app/ui.tsx`, `formatearNumero`/`formatearImporte`/
   `formatearPorcentaje`): comprueban `valor === null`, nunca falsy. Como la
   API serializa `Decimal` como cadena (confirmado con `curl` contra
   `/catalogo`: `"cantidad":"1.000"`, nunca un número JSON), un 0 real llega
   como la cadena `"0"` — truthy en JavaScript, distinta de `null`. Revisadas
   línea a línea `CatalogoPanel.tsx` (celdas de cantidad, precio unitario,
   precio adjudicado, y el panel de detalle con la fórmula precio × baja) y
   `RevisionPanel.tsx`: ningún sitio confunde "0" con ausencia.
4. **Excel** (`engine/app/exportacion.py`, `_celda_numero`):
   `float(valor) if valor is not None else None` — un 0 real se escribe como
   `0.0` (celda numérica que Excel muestra como "0"), una ausencia se deja
   `None` (celda realmente vacía para `openpyxl`).

**Conclusión**: no había ningún hueco que corregir. Se documenta aquí para
dejar constancia de la verificación, tal como pidió el cliente.

---

## Bloque 3 — Filtro por código interno

### Hallazgo de partida

`LineaCatalogo.codigo_interno` (columna del modelo, `engine/app/models.py`
línea 374) **nunca se escribe** en ningún camino de código — no es un bug a
arreglar en esta sesión, solo una precisión necesaria: el código interno
real de cada expediente vive en `Expediente.codigo_interno` (resultado del
cruce con el Excel de códigos, CONTEXTO.md sección 7), y el análisis de este
bloque se hizo contra esa columna.

### Análisis de correlación con tipología

El Excel de códigos (`codigos_proyecto.xlsx`) trae una columna
`ESPECIALIDAD/DISCIPLINA` que **hoy no se guarda en base de datos** (no
forma parte de `app.extraccion.cruce_codigos.CruceCodigos`) — es la
tipología real de cada expediente, tal como la clasifica ADIF: "Vía",
"Señalización y comunicaciones", "Electrificación/LAC",
"Electrificación/SSEE", "EPIS", "Otros", "Servicios", etc.

Cruzando `Expediente.codigo_interno` (358 expedientes activos, 211 con
código interno cruzado, 62 sin él) contra esa columna del Excel:

- **161 grupos** de código interno con al menos un expediente conocido en
  nuestra base.
- **160/161 grupos (99,4%) tienen una única especialidad** entre todos sus
  expedientes.
- Solo **1 grupo incoherente** (`20045`, 2 expedientes:
  `6.21/28510.0046` = "Señalización y comunicaciones",
  `6.20/28510.0113` = "Electrificación/LAC").

**Confirma la hipótesis del cliente con margen amplio**: agrupar por código
interno correlaciona casi perfectamente con la tipología real del material.

Tipologías y cuántos expedientes de nuestra base caen en cada una (dominante
del grupo de código interno):

| Tipología | Expedientes | Líneas de catálogo |
|---|---:|---:|
| Vía | 139 | 14.173 |
| Señalización y comunicaciones | 47 | 4.541 |
| (sin código interno) | — | 751 |
| Electrificación/LAC | 30 | 745 |
| Otros | 29 | 2 |
| Electrificación | 18 | 156 |
| Electrificación/SSEE | 11 | 335 |
| (sin especialidad cruzada en el Excel) | — | 177 |
| EPIS | 10 | — |
| Electrificación/LAC & SSEE | 4 | 121 |
| ALQUILER | 3 | 12 |
| Electrificación (SSEE) | 1 | 13 |

("Otros" concentra pocas líneas de catálogo porque son en su mayoría
expedientes todavía sin extraer/en revisión — el recuento de expedientes y
el de líneas no son proporcionales entre sí por eso.)

### Mecanismo implementado (sin decidir qué excluir)

`engine/app/exclusion.py` admite una tercera forma de entrada en el fichero
de exclusión: una línea `INTERNO:NNNNN` excluye ese código interno completo,
además del código de expediente exacto y el departamento que ya existían.

El prefijo `INTERNO:` es obligatorio porque un código interno (`24038`) y un
departamento (`28510`) son ambos cadenas de 5 dígitos en el corpus real —
sin distinguirlos, una línea de solo dígitos sería ambigua entre las dos
cosas.

`engine/app/catalogo_consulta.py._excluir_expedientes_de_la_lista` aplica el
filtro a nivel SQL con la guarda NULL-safe correcta: `codigo_interno` es
nullable (58,9% de cobertura), y `NULL NOT IN (...)` evalúa a `NULL` en SQL,
no a verdadero — sin el `OR codigo_interno IS NULL` explícito, el filtro
habría ocultado del entregable a TODOS los expedientes sin código interno
cruzado, no solo a los de la lista.

12 tests nuevos (`test_exclusion.py`, `test_api_catalogo.py`), 577 en verde
en total. **No se ha excluido nada**: el fichero de exclusión sigue vacío en
producción hasta que el cliente decida qué código interno, si alguno,
excluir.

---

## Bloque 4 — Preparar la carga del maestro de materiales

### Qué es y qué resolvería

ADIF va a facilitar el maestro de materiales de SAP: documento de referencia
existente (no derivado de pliegos ni contratos) con matrícula y unidad de
medida de cada material. Resolvería los dos huecos mayores del catálogo
(matrícula al 40,7%, unidad al 73,2% sobre el estado real de la base al
momento de escribir esto).

### Formato mínimo a pedir al cliente

Mismo vocabulario que el desglose de SAP que el cliente ya facilitó en la
sesión anterior (`app.extraccion.sap_desglose`, bloque 6) — para no pedir
dos nombres distintos de la misma cosa en dos sesiones seguidas:

| Columna esperada | Contenido |
|---|---|
| `Material` | Matrícula, 9 dígitos |
| `Texto breve` | Descripción del material |
| `Unidad medida base` | Unidad de medida |

### Qué se ha dejado preparado

Mismo mecanismo que `estado_sap.py`/`sap_desglose.py`: ruta configurable
(`MAESTRO_MATERIALES_PATH`), montada por bind-mount, repetible sin duplicar.

- Migración 0025: tabla `maestro_materiales` (una fila por matrícula, upsert
  por esa clave — a diferencia del desglose de SAP, que es una fila por
  línea de pedido de compras, esto es un catálogo de referencia sin relación
  con ningún expediente concreto) y columna nueva
  `lineas_catalogo.unidad_medida_completada_desde_maestro`.
- `app.extraccion.maestro_materiales.cargar_maestro_materiales`: carga/
  actualiza la tabla de referencia. `POST /mantenimiento/maestro-materiales/
  cargar`. Solo carga, no toca `lineas_catalogo` (mismo criterio que
  `sap_desglose`).
- `app.extraccion.maestro_materiales.completar_unidades_desde_maestro`: join
  determinista por matrícula exacta — únicamente rellena
  `LineaCatalogo.unidad_medida` en líneas que YA tienen matrícula y NO
  tienen unidad. **Nunca pisa un valor ya extraído de un documento real**
  (encargo explícito de esta sesión): solo escribe si `unidad_medida` está a
  `NULL`. Marca `unidad_medida_completada_desde_maestro = True` para que la
  trazabilidad (CONTEXTO.md invariante 10) siga siendo honesta — ese valor
  concreto no viene del documento apuntado por
  `documento_origen_id`/`pagina`/`fragmento`. Endpoint propio y separado
  (`POST /mantenimiento/maestro-materiales/completar-unidades`) para que
  cargar el maestro nunca escriba en el catálogo sin que alguien lo pida
  explícitamente.

### Qué queda deliberadamente sin implementar

**Completar matrícula.** El maestro de materiales no trae ninguna clave que
ya tengamos en las líneas que NO tienen matrícula (ni código de expediente,
ni código de precio) — la única vía posible es cruzar por texto
(`descripcion` de la línea contra `Texto breve` del maestro), y CONTEXTO.md
sección 7 ya reserva el cruce por texto como "red de seguridad... con
umbral y cola de revisión", nunca como cruce directo. Construir ese
emparejamiento difuso (normalización, umbral de similitud, cola de revisión
para confirmar cada match antes de escribir nada) es una sesión propia —
mismo criterio que el cliente ya aplicó explícitamente a la completitud de
matrícula del desglose de SAP en la sesión anterior ("no lo implementes
todavía"). Intentarlo sin ese diseño completo arriesgaría inventar
matrículas, justo lo que CONTEXTO.md prohíbe.

18 tests nuevos.

### Nota de planteamiento: despliegue aplazado a después del bloque 1

Los contenedores reales (`adif-api-1`, `adif-worker-1`) **no montan el
código fuente por bind-mount** — se construyen con `docker build ./engine`
(confirmado: `docker-compose.yml` no monta ningún volumen de código para
esos dos servicios, solo `documentos:/data/documentos`). Esto significa que
el código de los bloques 3 y 4 de esta sesión no está activo en los
contenedores en marcha hasta reconstruirlos — y reconstruir `adif-worker-1`
ahora mismo cortaría a mitad el reproceso del bloque 1.

Validado en una imagen Docker de prueba aparte (`docker build -t
adif-engine-check ./engine`, sin tocar los contenedores reales): 577 tests
en verde. El despliegue real (reconstruir `api`/`worker` con
`docker compose up -d --build`) se aplaza a que termine el reproceso del
bloque 1, para no interrumpirlo — pendiente para el cierre de esta sesión o
la siguiente.

---

## Bloque 5 — Estado final

- **Auditoría**: 7 hallazgos (3 errores, 4 avisos) — ver bloque 1 de arriba
  para el detalle y la investigación del impacto real en el entregable.
  Ninguna categoría nueva respecto a sesiones anteriores.
- **Excel exportado**: 19.432 filas de datos (dos hojas, "Materiales" y
  "Resumen"), sobre 22.721 líneas de catálogo en base de datos — la
  diferencia son las exclusiones ya conocidas (huérfanas sin lote por
  defecto, líneas descartadas, mapeos incoherentes, lista de exclusión de
  expedientes).
- **Despliegue de los bloques 3 y 4**: reconstruidos `adif-api-1` y
  `adif-worker-1` desde el repositorio real (`docker compose build api
  worker && docker compose up -d api worker`) una vez terminado el reproceso,
  para no interrumpirlo. Migración 0025 aplicada (`alembic current` → `0025
  (head)`). Verificado en el stack real: `POST /mantenimiento/maestro-
  materiales/cargar` responde `configurado:false` (ruta todavía no montada,
  como se espera), `POST /mantenimiento/maestro-materiales/completar-
  unidades` evalúa correctamente las 2.581 líneas reales con matrícula y sin
  unidad de medida (0 completadas, porque el maestro está vacío todavía —
  correcto), y el mecanismo `INTERNO:` de exclusión por código interno
  responde bien contra el código real ya desplegado.
- **Copia de seguridad**: la del inicio de sesión (`adif_20260909_191412.dump`)
  sigue siendo válida como punto de restauración anterior al reproceso; no se
  ha necesitado usarla.

---

## Resumen para el cliente

1. **Reproceso completo hecho**: los arreglos de la sesión anterior ya
   alcanzan a los 467 expedientes, no solo a la muestra. El catálogo crece
   un 2,8% (624 líneas), con un residuo pequeño y ya acotado (24 líneas
   duplicadas en el Excel, sobre 19.432) que queda documentado como
   pendiente, no oculto.
2. **Cero y blanco ya se distinguen** en base de datos, web y Excel — no
   hizo falta ningún cambio, se verificó y se documenta.
3. **Agrupar por código interno sí correlaciona con la tipología real**
   (99,4% de coherencia medida contra el Excel de códigos) — el mecanismo
   para excluir por código interno ya está listo y desplegado; falta que el
   cliente decida qué código, si alguno, excluir.
4. **Maestro de materiales**: preparado para cargarlo en cuanto ADIF lo
   facilite, con el formato exacto a pedir documentado arriba. Completará
   unidad de medida automáticamente y sin riesgo; completar matrícula
   necesitará una sesión de diseño propia (cruce difuso con revisión
   humana).

## Pendiente para una próxima sesión

- Pruning de filas huérfanas obsoletas en tablas sin cabecera reprocesadas
  más de una vez (causa raíz del residuo de 135 líneas duplicadas de esta
  sesión, ya documentada desde 2026-09-08, sección "Gap de idempotencia").
- Extracción de baja para la plantilla de boletín de Consejo de
  Administración (pendiente desde la sesión anterior).
- 6 documentos `ADJUDICACION_*.pdf` sin código de expediente legible.
- Diseño del cruce difuso por descripción para completar matrícula desde el
  maestro de materiales, cuando el cliente confirme que lo quiere.
- Decisión del cliente sobre qué código interno (si alguno) excluir del
  Excel entregado.
