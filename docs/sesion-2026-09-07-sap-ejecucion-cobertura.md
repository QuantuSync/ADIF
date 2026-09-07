# Sesión 2026-09-07: Excel de ejecución SAP, cobertura del descubrimiento y proceso de lo que falta

ADIF facilitó `Ejemplo/Input/EXPEDIENTES_EJECUCION_SAP 1.XLSX`: 367 expedientes
del departamento 28510, todos "En ejecución" según SAP, de 2014 a 2026 (tres
columnas: `Expediente ADIF`, `Título del expediente`, `Descripción del
estado`). El sistema tenía, al empezar esta sesión, 93 expedientes en base de
datos (no 52 — ese número, el que traía el encargo, quedó desactualizado por
el backfill de sindicación que ya venía corriendo de la sesión anterior).

## Bloque 1 — Estado de contrato como fuente de entrada permanente

Implementado y verificado en vivo contra el stack real:

- `expedientes.estado_contrato_sap` (texto libre, no `Enum`: el único valor
  visto es "En ejecución" pero el vocabulario real de SAP no está
  documentado) y `estado_contrato_sap_actualizado_en`, migración `0019`.
  Distinto de `estado` (procesamiento de este sistema) — un expediente puede
  estar `completado` aquí y seguir "En ejecución" para ADIF.
- `app.extraccion.estado_sap.cargar_estado_sap`: mismo mecanismo que el Excel
  de códigos (`ESTADO_SAP_PATH`, bind-mount en `docker-compose.override.yml`,
  validado al arrancar la API igual que `CODIGOS_PROYECTO_PATH`). Cruce por
  `codigo_expediente` exacto (misma normalización de espacios que
  `cruce_codigos.normalizar_codigo_expediente`), nunca por título. Upsert
  idempotente: un expediente del Excel de SAP que el sistema no conocía se da
  de alta como `pendiente` (estado de PROCESAMIENTO de siempre); uno que ya
  existía solo actualiza su estado de contrato. `nombre_proyecto` solo se
  rellena si estaba vacío — nunca pisa el "Objeto del Contrato" ya extraído
  de un PDF real.
- `POST /mantenimiento/estado-sap/cargar`: botón de recarga, síncrono (lectura
  local de ~370 filas, sin red ni PDFs — del orden de coste de
  `POST /expedientes`, no del ciclo de mantenimiento). Repetible: sustituir el
  fichero montado y volver a llamar no duplica nada.
- Visible en la web (`ExpedientesPanel.tsx`, nota "SAP: En ejecución" bajo el
  estado de procesamiento) y en el Excel exportado (columna 15,
  "Estado del contrato (SAP)", al final, sin desplazar las 14 anteriores).
- 21 tests nuevos (`engine/tests/extraccion/test_estado_sap.py`), 437 pasan en
  total (1 test existente de exportación actualizado por la columna nueva).

Carga real ejecutada contra el stack: **367 filas leídas, 0 sin código, 327
expedientes nuevos, 40 actualizados** (los 40 que ya existían en el sistema
con ese código exacto). Total de expedientes en base de datos: 93 → 420.

## Bloque 2 — Cobertura del descubrimiento automático (medida antes de procesar nada)

De los 367 expedientes del SAP:

| Pregunta | Resultado |
|---|---|
| Ya en el sistema antes de esta sesión (código exacto) | **40 / 367 (10,9 %)** |
| De esos 40, ya `completado` | 12 |
| De esos 40, `pendiente_revision` (procesados con aviso) | 20 |
| Ya cargados pero nunca procesados (recién descubiertos por sindicación en sesiones previas) | 8 |
| Aparecen en los periodos de sindicación ya ingeridos (`202408`, `202606`-`202609`) | **9 / 367 (2,5 %)** |
| Aparecerían en los periodos que el backfill está trayendo (`202409`-`202605`, 21 meses) | **sin datos todavía** — ver nota |
| Fuera de la sindicación por antigüedad | ver distribución de años abajo |

**Distribución real por año** (prefijo `N.AA/` del código): 2014:4, 2015:2,
2016:6, 2017:20, 2018:4, 2019:47, 2020:31, 2021:40, 2022:39, 2023:43,
2024:56, 2025:63, 2026:12. Un tercio del fichero (127/367) es de 2014-2020.

**Sobre el backfill de 21 meses**: ya estaba encolado desde la sesión
anterior (trabajo `1218`, `sindicacion_backfill`), pendiente de arrancar
porque el único worker seguía terminando trabajos de extracción sueltos. El
redeploy de Bloque 1 (necesario para aplicar la migración) lo interrumpió una
vez a mitad de la primera descarga -- se reclamó como huérfano y **volvió a
arrancar solo desde el principio** (mismo mecanismo de recuperación
documentado en `docs/tolerancia-reinicios-dockerd.md`), consumiendo su
segundo de tres intentos. Sigue corriendo (`en_proceso`) al cerrar esta
sesión. Al ritmo medido en la sesión anterior (~11 min/mes), se espera que
termine en 3,5-4 h desde que arrancó (15:29). **No se ha vuelto a interrumpir
el stack después de esto**, para no gastar el último intento.

**Por qué los 9 encontrados son todos de 2024-2026 y ninguno de 2014-2020**:
no es solo una cuestión de qué meses se han barrido todavía. Una entrada de
sindicación refleja un *evento* del expediente en ese mes (publicación,
adjudicación, modificación) -- un contrato adjudicado hace años que sigue
"en ejecución" sin ningún evento de contratación nuevo no genera ninguna
entrada de sindicación en ningún periodo, por muchos meses que se barran
hacia atrás. Los 127 expedientes de 2014-2020 son, con alta probabilidad,
estructuralmente invisibles para este mecanismo de descubrimiento
específico, no solo "todavía no comprobados". No se verificó contra la
ventana de retención real del archivo de sindicación (se decidió no lanzar
una comprobación de red adicional mientras el backfill de 21 meses estaba
descargando, para no competir por ancho de banda con un trabajo real ya en
curso -- ver nota de abajo).

**Conclusión del bloque 2**: el descubrimiento automático por sindicación
cubre hoy una fracción pequeña (2,5 % confirmado, con margen limitado incluso
tras el backfill dado el hallazgo de arriba) de lo que ADIF considera
vigente. El Excel de SAP no es un complemento menor al descubrimiento
automático -- para el tercio del corpus anterior a 2021, es la única fuente
de la que este sistema puede saber que el expediente existe y sigue activo.
Esto no es un defecto del mecanismo de sindicación (hace lo que se diseñó
para hacer: detectar novedades y cambios de estado, sección 24 de
CONTEXTO.md) sino un límite estructural de qué puede cubrir una fuente basada
en eventos recientes frente a un listado de vigencia real de SAP.

## Bloque 3 — Proceso de lo que falta

**Ritmo medido contra `trabajos_cola` real** (no una muestra nueva --
histórico completo del stack):

| Trabajo | Muestras | Media | Rango |
|---|---|---|---|
| `descargar_expediente` (encontrado) | 14 | 46,0 s | 13-104 s |
| `descargar_expediente` (no encontrado, `sin_publicar`) | 29 | 24,7 s | - |
| `extraer_expediente` | 1.108 | 37,6 s | 0-233 s |

**Estimación para los 335 expedientes del SAP todavía sin procesar**: con la
proporción de `sin_publicar` observada hasta ahora en el corpus (~16 %),
≈281 expedientes con descarga+extracción completas (≈106 s cada uno) y ≈54
sin encontrar (≈25 s cada uno) → **≈8,5 horas de trabajo del worker**, que se
suman a las 3,5-4 h que le queda al backfill de sindicación por delante en la
misma cola (un solo worker, un trabajo a la vez -- CONTEXTO.md sección 10).
Total estimado hasta vaciar la cola: **del orden de 12 horas**, sin
intervención.

**Lanzado, en la cola, corriendo solo:**

1. **29 descargas prioritarias** (`POST /expedientes/{id}/descargar`, una por
   una) para los expedientes con prefijo `2.`, `3.` y `4.` del SAP que
   siguen `pendiente` -- ver hallazgo del párrafo siguiente. Encoladas antes
   que el resto para que las resuelva el worker en cuanto libere el backfill,
   sin esperar a que la barrida general de mantenimiento las alcance por
   orden de `id`.
2. Un **ciclo de mantenimiento** (`POST /mantenimiento/ejecutar`,
   `sindicacion_desactivada: true` para no competir por red con el backfill
   en curso) que recorre los ~420 expedientes y encola descarga/extracción de
   todo lo que falte -- cubre el resto de los 335 nuevos del SAP, drenando la
   cola él mismo hasta vaciarla.

**Hallazgo real sobre los "25 expedientes con prefijo `2.`, `3.` y `4.`
dados por no publicados"**: verificado contra la base de datos real, la
premisa no se sostiene para estos códigos concretos. Los únicos expedientes
`sin_publicar` con esos prefijos en el sistema son 14 códigos de
departamentos **04703, 04110, 28520, 20810 y 27520** -- el conjunto fijo de
PDFs de prueba de `Ejemplo/Input/` que CONTEXTO.md sección 13 pide mantener
aparte del corpus real ("dos anuncios PCSP, dos propuestas LC.27..."),
correctamente marcados `sin_publicar` porque son códigos de ejemplo que no
existen en la Plataforma real. **Ninguno de los 25 códigos reales del
SAP con esos prefijos (todos departamento 28510) estaba en el sistema antes
de esta sesión** -- los 25 se crearon nuevos con la carga del Bloque 1, todos
`pendiente`, nunca buscados en la Plataforma hasta ahora. No hay "búsqueda
que siga sin encontrarlos" que reportar todavía: la búsqueda real para estos
25 está en cola (punto 1 de arriba) y no se ha ejecutado en esta sesión
porque el worker ha estado ocupado todo el tiempo con el backfill de
sindicación de 21 meses. Cuando termine, cada uno quedará `completado` o
`sin_publicar` con el motivo real anclado en `expediente.error`, consultable
en `GET /expedientes` sin que haga falta esta sesión para verlo.

## Estado del corpus al cerrar la sesión

No hay un recuento final real todavía -- la mayor parte del trabajo de este
bloque queda corriendo en la cola, sin supervisión, durante horas (encargo
explícito: "deja el proceso corriendo en la cola... nada de monitores ni
procesos en segundo plano"). Fotografía al cerrar:

- **420 expedientes** en base de datos (93 antes de esta sesión + 327 dados
  de alta por el Excel de SAP).
- **3.145 líneas de catálogo**, **13 matrículas repetidas entre 2+
  expedientes** -- cifra de referencia previa a que la cola de este bloque
  añada nada; crecerá con cada expediente de los ≈335 pendientes que resulte
  `completado`.
- Cola: 1 `sindicacion_backfill` en curso, 30 `descargar_expediente`
  pendientes (29 prioritarios + 1 suelto), 1 `mantenimiento_ciclo` pendiente
  que arrastrará el resto.
- Sin tocar el stack más allá de lo necesario para el Bloque 1 (una sola
  reconstrucción de imágenes y un solo redeploy), para no volver a interrumpir
  el backfill que ya gastó uno de sus tres intentos.

Próxima sesión: consultar `GET /mantenimiento/estado` y
`GET /mantenimiento/sindicacion/historial` para el resultado real de esta
tanda, y recalcular el recuento de cobertura del bloque 2 con los periodos de
sindicación que el backfill haya terminado de barrer.
