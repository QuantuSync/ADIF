# Sesión 2026-09-09 — Auditoría del último reproceso, mapeo de cabeceras, documentos de adjudicación

Encargo en cinco bloques: evaluar si el crecimiento de 16.647 a 22.097 líneas
del catálogo aportaba valor real; investigar y, si se podía, arreglar el
mapeo incorrecto sobre tablas sin cabecera en `6.20/28510.0042/0046/0047`;
implementar una caché de mapeo entre tablas sin cabecera del mismo documento;
comprobar si el documento de adjudicación equivocado de `6.22/28510.0126/
0125/0094` era un patrón más amplio; y cerrar con auditoría + Excel + estado
final.

---

## Bloque 1 — Evaluación del reproceso (16.647 → 22.097 líneas)

Comparación por `id` entre el catálogo actual y la copia de seguridad
`adif_20260909_102317.dump` (restaurada en una base `adif_scratch_cmp`
temporal, borrada al cerrar la sesión): 6.880 líneas nuevas, 1.430
desaparecidas (net +5.450, coincide con el enunciado).

Perfil de las 6.880 líneas nuevas frente a las 15.217 ya existentes:

| Campo | Nuevas | Ya existentes |
|---|---|---|
| descripción | 97,0% | 100,0% |
| cantidad | 36,0% | 82,1% |
| unidad de medida | 51,8% | 82,9% |
| precio adjudicado | 28,5% | 66,5% |
| con lote (entra en Excel) | 81,5% | 94,2% |
| con motivo de revisión | 89,4% | 61,8% |

Desglose por origen de las líneas nuevas:

- **`6.20/28510.0042`/`0046`/`0047` (3.183 líneas, 46% del total nuevo):**
  1,8% cantidad, 7,3% unidad, 0% precio adjudicado, pero **con lote al
  100%** — contaminaban el Excel entregado sin apenas datos útiles. Exacto
  el problema del Bloque 2.
- **`6.22/28510.0122`/`0155`/`0156` (1.008 líneas):** 0% cantidad, pero
  **0% con lote** (huérfanas de banda vacía) — ya correctamente excluidas
  del Excel por el mecanismo existente, no contaminaban nada.
- **`6.22/28510.0033`/`0057`/`0058` (921 líneas) y una cola de 21
  expedientes más (478 líneas):** completitud buena o superior a la media
  (71-100% cantidad, matrícula por encima de la media) — aportación
  legítima.
- **`6.23/28510.0051` y `6.24/28510.0064` (1.290 líneas):** churn casi neto
  cero (1.071 nuevas / 1.069 desaparecidas, 219/219) — reproceso de
  expedientes ya conocidos, sin aportar volumen real.

**Decisión: no restaurar la copia de seguridad.** La mayoría del crecimiento
bruto es basura de un solo grupo de expedientes (0042/46/47), pero es un
problema *localizado y arreglable* (Bloque 2), no un fallo general del
reproceso — y ya en esta misma sesión deja de contaminar el Excel. El resto
del crecimiento (≈2.400 líneas de los grupos 0033/57/58 y la cola larga) es
aportación real y de calidad igual o mejor que la media del catálogo.
Restaurar la copia habría tirado también esa parte buena.

---

## Bloque 2 — Mapeo incoherente sobre tabla sin cabecera (0042/0046/0047)

Los tres expedientes comparten el mismo `ANEJO_abd69efbdd39b552.pdf`
(hermanos, mismo cuadro de precios). Su tabla real es de 5 columnas
(matrícula, designación, plano, norma técnica, precio), repartida en ~45
páginas — solo la primera trae cabecera legible; el resto son continuaciones
sin cabecera (`cabecera_sin_senal`, nunca cacheadas por diseño desde la
sesión 2026-09-08).

Verificado contra el PDF real: sobre esas páginas sin cabecera, el modelo
—guiado solo por 2-3 filas de ejemplo, sin ningún nombre de columna que lo
ancle— desplazaba el mapeo una columna (matrícula→codigo_precio,
designación→matrícula, plano→descripción), produciendo líneas sin
descripción real y con la norma técnica leída como cantidad
(`"03.360.101.4"` → `33601014`).

**Implementado:** `evaluar_coherencia_mapeo` (`app/extraccion/
mapeo_cabecera.py`) valida el mapeo de una tabla sin cabecera contra TODAS
sus filas (no solo las 2-3 que vio el modelo) antes de aceptarlo: (1)
`descripcion`/`precio_unitario` no pueden estar vacíos en la mayoría de las
filas; (2) si `matricula` tiene columna asignada, sus valores no vacíos
deben tener forma de matrícula (9 dígitos) en la mayoría de las filas — este
segundo chequeo fue necesario porque el primero por sí solo no bastaba (la
columna "Plano" pasa el umbral de vacío por azar en algunas páginas).

Si el mapeo resulta incoherente, la línea se marca (`MOTIVO_MAPEO_
INCOHERENTE`) y `app.exportacion` la excluye del Excel — **sin tocar su
`lote_id`/`clave_linea`**, a propósito: una primera versión que sí movía la
línea a huérfana (mismo mecanismo que una tabla de lote ambiguo) duplicaba
cientos de filas en cada reproceso, porque no existe mecanismo que limpie la
fila vieja cuando una línea pasa de "resuelta" a "huérfana" (al revés del
caso que sí cubre `_limpiar_huerfana_superada`, sesión 2026-09-08).

**Verificado contra el corpus real:** tres reprocesos sucesivos de los tres
expedientes sin duplicar filas (idempotencia confirmada); las 207 líneas sin
descripción del hallazgo original quedan 100% marcadas y excluidas — 0 de
1.581 filas del trío en el Excel final se quedan sin descripción.

---

## Bloque 3 — Caché de mapeo entre tablas sin cabecera del mismo documento

`app/extraccion/firma_estructural.py`: `calcular_firma_estructural` clasifica
cada columna por su CONTENIDO sobre todas las filas de la tabla (matrícula,
precio, texto único de alta cardinalidad, código repetido de baja
cardinalidad, vacía — con un umbral de relleno mínimo para que una única
fila con un valor suelto no defina el tipo de toda la columna). El caché
vive en un diccionario local a cada llamada de `procesar_anejo` — nunca se
persiste ni se comparte entre documentos.

Un intento anterior (comentario retirado de `mapeo_cabecera.py`, Bloque 5 de
la sesión 2026-09-09 previa) heredaba por número de columnas a secas y
corrompió `6.22/28510.0126_ANEJO_57694f5d5dacb236.pdf`: la tabla con
cabecera real de la p.15 y las tablas sin cabecera de la p.19/20 tienen las
dos 8 columnas, pero en posiciones distintas (una trae una columna fantasma
antes de la descripción, la otra no) — heredar el mapeo desplaza
`descripcion` sobre la columna de `unidad` ("UD." en vez de la designación
real).

**Verificado contra ese caso exacto:** la firma estructural ya distingue las
dos formas por sí sola (p.15 ≠ p.19/20/24/25 con el mismo número de
columnas; p.19==p.20==p.24==p.25 correctamente reconocidas como la misma
forma). Cada mapeo heredado se revalida además con `evaluar_coherencia_
mapeo` (Bloque 2) contra las filas de la tabla actual, como red de
seguridad. Reprocesado el expediente real completo: 0 líneas con
`descripcion="UD."`, 0 grupos duplicados nuevos en la auditoría.

---

## Bloque 4 — Documento de adjudicación equivocado: el planteamiento no se sostenía

**Hallazgo que cambia el encargo** (memoria de la sesión: pausar cuando algo
contradice el planteamiento, y seguir sin bloquear la sesión — instrucción
explícita del cliente para esta sesión larga).

`6.22/28510.0126`/`0125`/`0094` comparten
`ADJUDICACION_5c030c40c37b1ba9.pdf`, un boletín de 19 páginas del Consejo de
Administración de ADIF, clasificado `otro` (plantilla no reconocida por el
clasificador). Verificado byte a byte: la página 17 **sí** menciona los tres
expedientes, con su baja real (23,90% para el lote NORTE, adjudicatario
Talleres Alegría S.A.). **No es un documento equivocado** — es el acto de
adjudicación genuino, de una familia de plantilla (boletín multi-contrato de
Consejo) que la cascada de extracción todavía no sabe leer, así que su baja
nunca llega al catálogo.

Escaneados los 16 documentos reales del corpus con el mismo patrón
(`ADJUDICACION_*.pdf` clasificado `otro`, filtrando por si el propio código
del expediente —o el de su matriz— aparece en el texto):

- **10 de 16** mencionan su propio expediente o su matriz — genuinamente
  relevantes, mismo caso que 0126/0125/0094.
- **6 de 16** (`6.18/28510.0051`, `6.18/28510.0071`, `6.19/28510.0194`,
  `6.19/28510.0231`+`6.20/28510.0025` —comparten un mismo documento—,
  `6.21/28510.0017`, `6.21/28510.0046`) no traen NINGÚN código de
  expediente legible en su texto — pero no porque mencionen a otro
  expediente: el texto extraído está vacío, con codificación de fuente
  rota (`(cid:...)`), o es solo el pie de verificación CSV de una plantilla
  corta (`L9_AF.02-FE`, misma familia que `L9_CM.32-FE`, CONTEXTO.md
  sección 3). **Cero de los 16 documentos reales examinados es un caso
  confirmado de "documento de otro expediente"** en el sentido literal del
  encargo.

**Implementado igualmente, como red de seguridad genérica** (el patrón no se
confirmó en esta muestra, pero el mecanismo de detección es barato y de
solo-lectura, coherente con la filosofía de auditoría del proyecto):
`app.extraccion.orquestador._detectar_documento_adjudicacion_no_relacionado`
compara, para cualquier documento cuyo nombre de fichero indica que el
scraper lo trajo como ADJUDICACION, los códigos de expediente de su propio
texto contra el código (y matriz) del expediente al que está ligado — si
trae códigos legibles pero ninguno es el propio, se añade a
`motivo_revision`. **De paso, corrigió un hallazgo real distinto:**
`6.24/28510.0109` y `6.24/28510.0216` estaban `completado` con este mismo
boletín adjunto sin que nadie lo supiera (matriz correctamente identificada
tras aplicar el chequeo, así que no disparan el aviso, pero el mecanismo ya
existe si algún día aparece un caso real).

**No implementado, fuera de alcance:** extracción de baja para la plantilla
de boletín de Consejo de Administración (sería una sexta plantilla en la
cascada, CONTEXTO.md sección 5 — sesión propia) ni descarga automática de un
documento distinto (exigiría releer la Plataforma en vivo).

---

## Bloque 5 — Auditoría y estado final

Auditoría automática (`POST /mantenimiento/auditoria/ejecutar`): 0 errores
nuevos fuera de lo ya conocido — 51 grupos duplicados / sin descripción
siguen señalados en `0042/46/47` (correcto: la auditoría es de solo lectura
sobre TODA la base, y ve incluso las líneas que el Bloque 2 ya excluyó del
Excel), 23 huérfanas sin lote, 118 precios atípicos, 27 cantidades con forma
de año, 31 grupos de importe de licitación compartido — todas categorías ya
conocidas, ninguna nueva.

**Estado del catálogo (base de datos completa, 22.097 líneas):**

| Columna | Relleno |
|---|---|
| Descripción | 99,1% |
| Matrícula | 40,7% |
| Cantidad | 67,7% |
| Unidad de medida | 73,2% |
| Precio unitario | 99,3% |
| Precio adjudicado | 54,7% |
| Código de precio | 83,9% |
| Baja de lote | 55,5% |
| Con lote asignado | 90,2% |

**Estado del Excel entregable (vista filtrada, 18.097 de las 22.097
líneas — 4.000 excluidas y explicadas en la hoja "Resumen"):**

| Columna | Relleno en el Excel |
|---|---|
| Descripción | 100,0% |
| Matrícula | 44,7% |
| Cantidad | 78,4% |
| Unidad de medida | 76,2% |
| Precio unitario | 99,2% |
| Precio adjudicado | 66,8% |
| Baja de lote | 67,8% |
| Código del material | 67,3% |
| Código matriz | 66,4% |

**Comparación con el estado anterior a esta sesión:** las cifras de relleno
de la base de datos completa (67,7% cantidad, 54,7% precio adjudicado)
siguen siendo las mismas que al abrir la sesión — esperado: los arreglos de
los Bloques 2-4 se **verificaron contra una muestra representativa real**
(los tres expedientes de cada bloque, más ~15 expedientes adicionales
elegidos por ser headerless-heavy o multi-lote), no contra el corpus
completo de 467 expedientes, porque un reproceso completo tarda del orden de
4-5 horas (ritmo medido en sesiones anteriores, ~24 min por cada 42
expedientes) — fuera del alcance práctico de esta sesión. La cifra que
mejora de verdad, y que sí es representativa del efecto de los arreglos, es
la del **Excel entregado**: 0 de 1.581 filas del trío 0042/46/47 salen sin
descripción (antes: 207 en toda la base, gran parte con lote y por tanto
visibles en el Excel).

**Recomendación:** el Excel actual (18.097 líneas) es entregable tal cual —
la exclusión automática ya protege al cliente de las líneas de baja
confianza, y la hoja "Resumen" explica en lenguaje llano por qué faltan las
4.000 excluidas. **Pendiente, para la próxima sesión:** lanzar un reproceso
forzado del corpus completo (`POST /mantenimiento/ejecutar` con
`forzar: true`, sin sindicación) para que los Bloques 2 y 3 corrijan el
resto de expedientes headerless-heavy del corpus más allá de la muestra
verificada aquí — el estimado de 4-5 horas encaja bien como ciclo nocturno
de mantenimiento, mismo patrón que el backfill de sindicación de sesiones
anteriores.

---

## Pendiente / no resuelto en esta sesión

- Reproceso completo del corpus (467 expedientes) con los arreglos de los
  Bloques 2 y 3 — verificado en una muestra representativa, no en el
  corpus entero, por coste de tiempo.
- Extracción de baja para la plantilla de boletín de Consejo de
  Administración (Bloque 4) — nueva plantilla en la cascada, sesión propia.
- Los 6 documentos `ADJUDICACION_*.pdf` sin ningún código de expediente
  legible en su texto (`6.18/28510.0051`, `6.18/28510.0071`,
  `6.19/28510.0194`, `6.19/28510.0231`/`6.20/28510.0025`,
  `6.21/28510.0017`, `6.21/28510.0046`) — texto vacío o codificación de
  fuente rota, no se pudo confirmar ni descartar si son el documento
  correcto. Candidatos a revisión manual contra la Plataforma.
