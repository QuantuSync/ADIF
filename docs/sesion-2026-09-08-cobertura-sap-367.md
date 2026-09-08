# Sesión 2026-09-08: cobertura del catálogo sobre los 367 expedientes del SAP

Sesión de análisis puro, sin tocar código ni lanzar reprocesados (otra sesión
trabajaba en paralelo). Cruce contra la base de datos real en el momento de
esta consulta: **467 expedientes en total, de los cuales 367 llevan
`estado_contrato_sap` cargado** desde `EXPEDIENTES_EJECUCION_SAP_1.XLSX`
(carga descrita en `docs/sesion-2026-09-07-sap-ejecucion-cobertura.md`, sin
cambios desde entonces).

**Definición de "catálogo entregable" usada en todo este documento**: la
misma que aplica el Excel real al cliente (`generar_excel_catalogo`,
`incluir_pendientes_sin_lote=False` por defecto) — una línea de
`lineas_catalogo` cuenta solo si tiene `lote_id` asignado y no está
`descartada`. Las huérfanas sin lote no cuentan, aunque existan en base de
datos.

---

## 1. Cuántos de los 367 tienen catálogo entregable

| | Expedientes | Líneas entregables |
|---|---:|---:|
| **Con al menos una línea entregable** | **102 / 367 (27,8 %)** | **4.166** |

De esos 102: **54 ya `completado`**, **48 `pendiente_revision`** pero con
cobertura parcial (algún lote sí tiene líneas, otro del mismo expediente
está pendiente).

Para contexto: estas 4.166 líneas son el 63 % de las 6.599 líneas
entregables que tiene el sistema entero (9.701 líneas en base de datos,
incluidas las huérfanas) — los 367 del SAP concentran la mayor parte del
catálogo real.

---

## 2. Cuántos están en el sistema pero sin catálogo entregable

**203 / 367 (55,3 %)** están confirmados como publicados en la Plataforma
(`estado = pendiente_revision`) pero no aportan ninguna línea entregable
todavía. Desglose por motivo, leído de `expediente.error`:

| Motivo | Nº | Qué significa |
|---|---:|---|
| **Esperando a que se resuelva su matriz (acuerdo marco)** | 135 | El pedido depende de los datos de su acuerdo marco (baja, cuadro de precios) y esa matriz todavía no tiene lote registrado, no tiene cuadro de precios propio, forma un ciclo de referencias, o es multi-lote y el propio pedido no declara a cuál de los lotes pertenece. Se resuelve solo, procesando la matriz o corrigiendo la ambigüedad del pedido — nunca inventando el dato. |
| **Sin cuadro de precios publicado** | 22 | El expediente no trae ningún Anejo ni Pliego técnico con posible tabla de precios entre los documentos descargados (solo anuncio, contrato o resolución). Límite de lo publicado en la Plataforma, no un fallo de extracción — ya verificado en dos casos concretos en sesiones anteriores. |
| **Documento escaneado, sin capa de texto** | 17 | El único documento disponible es una imagen sin texto seleccionable. Fuera de alcance por decisión de diseño (CONTEXTO.md sección 15: no se monta OCR para un puñado de casos). |
| **Sin motivo detallado (candidato a documento compartido con expediente "hermano")** | 16 | El sistema descargó documentos pero no extrajo ninguna línea, sin más detalle. La sesión de análisis anterior confirmó que al menos un tercio de estos casos genéricos son en realidad una colisión de hash: el PDF real es idéntico al de otro expediente y la restricción de unicidad de `documentos.hash` deja al segundo expediente sin fila propia. No se ha verificado uno a uno cuál de estos 16 es cuál. |
| **El documento declara pertenecer a otro expediente ("EXPEDIENTE PRINCIPAL/ORIGEN")** | 8 | Mismo límite arquitectónico que la fila anterior, pero con la pista explícita dentro del propio documento: el PDF dice que pertenece a un expediente distinto de aquel bajo el que está archivado. Identificado en CONTEXTO.md como cambio de modelo de datos mayor (separar expedientes de lote de verdad), aparcado a propósito. |
| **Otro** | 5 | 4 son "cobertura parcial" con algún lote que sí declara baja/importe pero sin ninguna línea de tabla de precios extraída para ese lote. 1 es un error técnico real y puntual (`6.24/28510.0208`: fallo de base de datos, `value too long for character varying(32)`, al insertar una línea — este último sí es un defecto a corregir, no un límite de origen). |
| **Total** | **203** | |

**En una frase para el cliente**: de los 203, la inmensa mayoría (≈195) son
consecuencia de límites de lo que la Plataforma publica o de una dependencia
todavía sin resolver dentro del propio sistema (nunca de un dato inventado),
y solo 1 es un fallo técnico puntual identificado y localizado.

---

## 3. Cuántos no se encontraron en la Plataforma

**62 / 367 (16,9 %)** — búsqueda confirmada sin resultados en la Plataforma
de Contratación (vía correcta, "sin resultados" real, no un bloqueo
transitorio; ver nota de fiabilidad más abajo).

**Distribución por año** (prefijo del código, `N.AA/28510....`):

| Año | Nº |
|---|---:|
| 2014 | 4 |
| 2015 | 2 |
| 2016 | 6 |
| 2017 | 18 |
| 2018 | 0 |
| 2019 | 3 |
| 2020 | 1 |
| 2021 | 7 |
| 2022 | 0 |
| 2023 | 9 |
| 2024 | 6 |
| 2025 | 3 |
| 2026 | 3 |
| **Total** | **62** |

**30 de los 62 (48,4 %) son de 2014-2017** — la franja más antigua del
listado del SAP, tal como ya se sabía. No hay ningún patrón raro en años
intermedios (2018 y 2022 no aportan ninguno; el resto están repartidos).

**Nota de fiabilidad, importante para no sobreinterpretar esta cifra**:
`docs/analisis-corpus-467-expedientes.md` sección 1 deja documentado que la
verificación manual de una muestra de estos 62 quedó bloqueada por un
timeout de `ensure_form` (la Plataforma respondiendo más lenta de lo que el
scraper espera), no relacionado con si el expediente existe. Los 62 vienen
de la vía correcta del scraper (confirmación real de "sin resultados", no
del mecanismo de bloqueo transitorio que se corrigió en la sesión anterior),
así que no hay motivo concreto para dudar del conjunto en bloque — pero
tampoco se ha podido reconfirmar uno a uno con una comprobación fresca en
esta sesión (esta sesión es solo de análisis, no relanza scraping). Sigue
pendiente ampliar el presupuesto de espera de `ensure_form` y repetir la
verificación cuando eso esté hecho.

---

## 4. Cuántos del sistema no están en la lista del SAP

**100 de los 467 expedientes del sistema (467 − 367) no aparecen en el
Excel de ejecución SAP.** Se descomponen así:

| Grupo | Nº | Qué son |
|---|---:|---|
| **Códigos de prueba del repositorio, no ADIF real** | 18 | Departamentos `04703`, `04110`, `28520`, `20810`, `27520` — el conjunto fijo de PDFs de ejemplo que CONTEXTO.md pide mantener aparte del corpus real (sección 13). Los 18 están `sin_publicar` porque son códigos que no existen en la Plataforma real. **Recomendación: excluir siempre, no son datos del cliente.** |
| **Matrices de acuerdo marco (departamento 28510 real)** | 41 | Expedientes que son la cabecera de un acuerdo marco del que sí cuelgan pedidos reales — y esos pedidos **sí** están en la lista del SAP. La propia matriz nunca aparece en el extracto de "en ejecución": SAP parece trackear la ejecución en cada pedido, no en el acuerdo marco que los origina. No es una laguna del cruce, es coherente con cómo se organiza un acuerdo marco. **Recomendación: mantenerlas en el entregable** — dan de contexto la baja y el cuadro de precios que sus pedidos (sí vigentes según SAP) heredan; quitarlas rompería esa trazabilidad. |
| **Expedientes reales del departamento 28510, sin relación con ninguna matriz conocida** | 41 | 14 están publicados en la Plataforma con nombre de proyecto real (suministro de balasto, carril, traviesas, engrasadores, kits de soldadura, etc.) y aportan documentos; 27 están `sin_publicar` (llegaron al sistema por el Excel de códigos o por sindicación, pero la búsqueda en la Plataforma no los ha confirmado todavía). Ninguno declara un código de matriz propio, así que no son "pedidos derivados de acuerdo marco" en el sentido de la hipótesis del encargo. **No se puede determinar solo con los datos del sistema por qué faltan en el SAP** — puede ser que el contrato ya esté cerrado, que el extracto de SAP no cubra ese tipo de expediente, o una omisión del propio informe. **Recomendación: no filtrarlos de forma automática; confirmar con el cliente uno a uno o en bloque antes de decidir si se excluyen.** |
| **Total** | **100** | |

---

## 5. Resumen para el correo al cliente

| Pregunta | Cifra | En una frase |
|---|---:|---|
| ¿Cuántos de los 367 que ustedes dan por vigentes ya tienen catálogo de materiales? | **102 (27,8 %)**, 4.166 líneas | Poco más de una cuarta parte ya tiene precios extraídos y listos para consultar. |
| ¿Cuántos están localizados pero todavía sin catálogo? | **203 (55,3 %)** | La mayoría espera a que se resuelva su acuerdo marco, a que se publique un documento con cuadro de precios, o a una revisión puntual — casi ninguno por un fallo del sistema. |
| ¿Cuántos no aparecen en la Plataforma de contratación? | **62 (16,9 %)** | Casi la mitad son de 2014-2017; no se puede descartar con la garantía habitual hasta repetir la búsqueda tras un ajuste técnico pendiente. |
| ¿Hay expedientes en nuestro sistema que ustedes no listan como vigentes? | **100** | 18 son datos de prueba internos (a descartar); 41 son los acuerdos marco de los que sí cuelgan pedidos vigentes suyos (a mantener); 41 son expedientes reales sin explicación todavía — se confirmarán con ustedes. |

**Mensaje de una línea**: hoy el catálogo cubre de forma directa **1 de cada
4** de los 367 expedientes que ADIF considera vigentes, con otra mitad
identificada y en curso de resolverse sola a medida que se procesan sus
acuerdos marco y se completan los documentos, y un 17 % pendiente de
reconfirmar que de verdad no está publicado.

---

## Nota metodológica

Cifras obtenidas por consulta SQL directa de solo lectura contra
`adif-postgres-1` (467 expedientes, 367 con `estado_contrato_sap`, 9.701
líneas de catálogo en total) el 2026-09-08. Ninguna consulta modificó datos,
relanzó scraping ni encoló trabajos — instrucción explícita de esta sesión,
que corría en paralelo a otra sesión de código sobre el mismo sistema.
