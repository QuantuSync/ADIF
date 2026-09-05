# Mantenimiento automático

Registro histórico movido desde `CLAUDE.md` (split de sesión 2026-09-05).
Ver `CLAUDE.md` para el contexto vivo del proyecto.

Bloque 2 (descubrimiento por sindicación): ver `docs/hallazgos-sindicacion.md`, sección 24.

---

## 23. Mantenimiento automático — bloque 1: ejecución incremental (sesión 2026-09-04)

Cambia el objetivo del sistema: de herramienta que se lanza a mano a sistema
que se mantiene solo. Este bloque es la base de los otros dos (descubrimiento
por sindicación y ejecución programada): sin ejecución incremental, un ciclo
periódico rehace el trabajo de todos los expedientes cada vez que corre, lo
que lo vuelve inviable en la práctica (`docs/hallazgos-scraping.md` sección 17: la Plataforma es
lenta y frágil; una extracción completa de ~40 expedientes reales tarda del
orden de 25 minutos, medido en esta misma sesión — ver más abajo).

### Modelo y decisión

Cuatro columnas nuevas en `expedientes` (migración `0011`):
`descargado_en`, `extraido_en`, `version_logica_extraccion`,
`huella_documentos`. Las estampa **`app.worker`** (`procesar_descargar_expediente`
/ `procesar_extraer_expediente`), nunca `app.scraping.job` ni
`app.extraccion.orquestador` — ninguno de los dos se toca en esta sesión
(encargo explícito: "no toques el motor de extracción"). Los dos manejadores
envuelven las funciones ya existentes sin modificarlas: llaman, y después (o
en un `finally`, para la extracción) estampan frescura solo si de verdad
hubo un intento real — ver docstrings de `app.mantenimiento.frescura.
debe_estampar_extraccion` para las dos excepciones (`esperando_matriz`,
`sin_publicar`, `docs/identidad-expediente.md` secciones 20 y 22).

`app.mantenimiento.frescura` (puro, sin I/O salvo los dos `estampar_*` con
`db.commit()`) decide:

- **`debe_descargar(expediente, documentos)`**: `True` solo si el expediente
  no tiene ningún documento. Deliberadamente **sin** parámetro `forzar`: el
  punto 4 del encargo ("lo necesito yo para desarrollo") es casi siempre
  forzar la RE-EXTRACCIÓN tras un cambio de código, no volver a golpear la
  Plataforma real para un expediente que ya tiene sus documentos íntegros —
  forzar eso contradiría el propio punto 2 del encargo ("cada descarga
  evitada cuenta"). Forzar una redescarga real sigue disponible a mano, sin
  tocar nada, con el endpoint ya existente `POST /expedientes/{id}/descargar`.
- **`debe_extraer(expediente, documentos, forzar)`**: `True` si `forzar`, si
  `extraido_en` es `None` (nunca se extrajo, o se quedó `esperando_matriz` —
  ver arriba, así un pedido derivado de acuerdo marco se reintenta solo en
  cada ciclo hasta que su matriz esté lista, sin regla aparte), si
  `version_logica_extraccion` no coincide con la constante vigente
  (`VERSION_LOGICA_EXTRACCION`, que un desarrollador sube a mano cuando un
  cambio en `app.extraccion.*` deba forzar reproceso general), o si
  `huella_documentos` (hash del conjunto de `Documento.hash`, `docs/hallazgos-scraping.md` sección 17:
  la ruta de almacenamiento ya va por hash de contenido) no coincide con la
  huella actual. Deliberadamente **no** mira si el expediente tiene
  documentos: un pedido derivado sin ningún documento propio también
  necesita que se intente su extracción — es su único camino para cruzar
  con el Excel de códigos y heredar de su matriz (CLAUDE.md sección 3 y
  `docs/identidad-expediente.md` sección 20).

### El ciclo como trabajo de la cola, no como script

`app.mantenimiento.ciclo.ejecutar_ciclo_mantenimiento` es un tipo de trabajo
más (`mantenimiento_ciclo`, CLAUDE.md sección 10: "no un script suelto"),
encolable por `POST /mantenimiento/ejecutar` (payload opcional `{"forzar":
bool, "forzar_expedientes": [id, ...]}`). Por cada expediente (excepto
`sin_publicar`, fuera de alcance por diseño desde `docs/identidad-expediente.md` sección 22) decide y
**encola** `descargar_expediente`/`extraer_expediente` con la misma
`encolar_trabajo` de siempre — y después **drena la cola de forma síncrona**
(`app.queue.ejecutar_trabajo`, extraído de `app.worker` a un despachador
genérico parametrizado por una tabla de manejadores, para que el worker y el
drenaje del ciclo compartan una sola implementación) hasta vaciarla. El
drenaje recoge también la extracción que `app.scraping.job` encadena solo al
terminar una descarga con éxito, así que el bucle de decisión nunca la
encola por duplicado: si un expediente no tenía documentos, su extracción se
deja a la cadena existente en vez de repetirla (comentario en
`ejecutar_ciclo_mantenimiento`). `tomar_siguiente_trabajo` gana un parámetro
`excluir_tipos` para que este drenaje nunca se recoja a sí mismo (evita
recursión); el bucle normal del worker no lo pasa, que es como llegan a
ejecutarse los ciclos programados del bloque 3.

### Verificación contra el stack real (dos ejecuciones seguidas)

Migración `0011` aplicada sobre la base de datos real de desarrollo (53
expedientes acumulados de sesiones anteriores, 14 de ellos ya `sin_publicar`
— más de los 45/31 del corpus fijo de `docs/analisis-corpus.md` porque esta
base lleva varias sesiones de pruebas manuales encima; no se ha limpiado,
no es el objeto de esta sesión). Con las cuatro columnas nuevas a `NULL` en
las 53 filas, dos ejecuciones seguidas de `POST /mantenimiento/ejecutar`:

| | 1ª ejecución | 2ª ejecución |
|---|---:|---:|
| Duración de pared (creación del trabajo → `completado`) | **1567 s (~26 min)** | **3,5 s** |
| Duración interna del ciclo (`resultado.duracion_segundos`) | 1531,7 s | **0,005 s** |
| Expedientes evaluados | 39 | 38 |
| Descargas lanzadas | 1 | 0 |
| Extracciones lanzadas | 38 | 0 |
| Saltados (descarga / extracción) | 0 / 0 | 38 / 38 |
| Trabajos drenados | 39 | 0 |

La 1ª ejecución hizo el trabajo real: reextrajo los 38 expedientes con
documentos (estableciendo su huella y versión por primera vez) e intentó
descargar el único expediente sin documentos que no estaba ya marcado
`sin_publicar` — el intento falló (`ExpedienteNoPublicadoError`, `docs/identidad-expediente.md` sección 22:
no encontrado en la Plataforma por ninguna variante de búsqueda) y lo dejó
`sin_publicar`, sin encadenar ninguna extracción (coherente:
`app.scraping.job` solo encadena tras una descarga con éxito) — por eso
`trabajos_drenados` es 39 y no 40, y por eso la 2ª ejecución evalúa 38
expedientes, no 39 (ese ya queda excluido por estar `sin_publicar`). La 2ª
ejecución, con las cuatro columnas ya estampadas y sin ningún documento ni
versión cambiados, no encoló nada: terminó en milisegundos de trabajo real,
con los ~3,5 s de pared explicados casi enteros por el intervalo de sondeo
del worker (`WORKER_POLL_INTERVAL_SECONDS=3`), no por trabajo hecho.
Verificado también que los 199 tests (176 anteriores + 23 de este bloque)
pasan igual dentro del contenedor `api`, no solo en local.

### Fixtures de regresión

`engine/tests/mantenimiento/test_frescura.py` (17 casos: huella estable
frente al orden, cambia si cambia el conjunto de documentos, las cuatro
ramas de `debe_extraer`, `debe_descargar` sin y con documentos,
`debe_estampar_extraccion` en los tres estados terminales y en las dos
excepciones, los dos `estampar_*`) y
`engine/tests/mantenimiento/test_ciclo.py` (5 casos, con manejadores falsos
— sin scraping ni modelo reales, igual que el resto de esta cascada: la
extracción encadenada por una descarga se drena sin duplicarse, un
expediente al día no lanza nada, `forzar` global reprocesa aunque todo
coincida, `sin_publicar` queda fuera del ciclo, un segundo trabajo de ciclo
pendiente no se recoge a sí mismo). `tests/test_queue.py` gana 3 casos para
`excluir_tipos` y el despachador genérico `ejecutar_trabajo`. Ningún PDF
nuevo — este bloque no toca la cascada de extracción, solo decide cuándo
llamarla.

---

## 25. Mantenimiento automático — bloque 3: ejecución programada (sesión 2026-09-04)

Cierra la sesión de mantenimiento automático (bloques 1 y 2 arriba y en
`docs/hallazgos-sindicacion.md` sección 24, base de este). El ciclo completo — descubrir, descargar lo
que falte, extraer lo que falte — ya existía como trabajo de la cola
(`mantenimiento_ciclo`); este bloque lo dispara solo, sin intervención,
respetando CLAUDE.md sección 10 ("cuatro procesos, ni uno más").

### Dónde vive el planificador: dentro del worker que ya existe

`app.mantenimiento.programacion.verificar_y_lanzar_ciclo_programado` se
llama en cada vuelta de `app.worker.bucle_principal` (cada
`WORKER_POLL_INTERVAL_SECONDS`, unos segundos) — no hay un quinto proceso
"scheduler", ni un cron del sistema operativo, ni Redis. Es una comprobación
barata (dos `SELECT` contra `trabajos_cola`, nada de red ni de Playwright
en la propia comprobación):

1. Si ya hay un trabajo `mantenimiento_ciclo` `pendiente` o `en_proceso`
   (programado **o disparado a mano**, da igual el origen) no se lanza
   otro — "sin solaparse consigo mismo" (punto 2) sale gratis de la misma
   cola que ya existía, sin bloqueo nuevo.
2. Si no, se compara `ahora` contra `última_ejecución.created_at +
   MANTENIMIENTO_INTERVALO_SEGUNDOS` (semanal por defecto, cualquier
   trabajo `mantenimiento_ciclo` cuenta como "última ejecución" para este
   cálculo, sea programado o manual). Si toca, se encola uno nuevo con
   `payload.disparado_por = "programado"` — el histórico (punto 4)
   distingue así por qué corrió cada ejecución.

**El histórico es la propia `trabajos_cola`, sin tabla nueva.** CLAUDE.md
sección 10 ya la describe como "consultable con SQL para la pantalla de
seguimiento" — duplicar esa información en una tabla aparte solo la
desincronizaría. `GET /mantenimiento/historial` la expone tal cual, más
reciente primero; `GET /mantenimiento/estado` añade lo calculado (próxima
ejecución, si hay una en curso) que no está en ninguna fila por sí sola.

**Límite conocido, no un descuido**: con un único proceso `worker`
(arquitectura de cuatro procesos de la sección 10), la comprobación no
compite consigo misma. Si algún día hubiera varias réplicas del worker, dos
podrían decidir lanzar en la misma vuelta antes de que ninguna llegue a
insertar — no se ha construido un bloqueo distribuido para un caso que la
arquitectura actual no tiene.

### Web: `/mantenimiento`

Página nueva (`web/app/mantenimiento/`), enlazada en la barra de
navegación. Muestra la frecuencia configurada, cuándo fue la última
ejecución (y quién la disparó), si hay una en curso ahora mismo, cuándo
tocaría la próxima, un resumen de lo que encontró la última ejecución
(nuevos, descargas, extracciones, y el resumen de sindicación si lo trae) y
el botón "Lanzar ciclo ahora" (`POST /mantenimiento/ejecutar`, el mismo
endpoint que dispara la programación en sí, solo que `disparado_por` queda
como `"manual"`) — y la tabla de histórico completa. Sondeo cada 4 s, mismo
patrón que el resto de la web (CLAUDE.md, encargo de la sesión de
identidad, "Expedientes").

### Verificación contra el stack real, intervalo corto

`MANTENIMIENTO_INTERVALO_SEGUNDOS=45` (frente al valor de producción,
604800 = una semana) durante ~9 minutos, contra la base de datos real de
desarrollo (59 expedientes de las sesiones de los bloques 1 y 2, sin
limpiar). **Cuatro ejecuciones programadas seguidas, ninguna solapada,
histórico correcto de principio a fin** — verificado con el propio
`GET /mantenimiento/historial` sondeado cada 20 s, no solo mirando la base
de datos:

| Trabajo | Encolado | Terminado | Duración |
|---|---|---:|---:|
| 369 | 04:56:34 | 04:58:43 | 129 s |
| 372 | 04:58:46 (3 s después de que 369 terminara) | 05:01:55 | 189 s |
| 375 | 05:01:58 (3 s después de que 372 terminara) | — | — |
| 378 | 05:05:16 (tras 375) | — | — |

**Cada ciclo real tardó entre 2 y 3 minutos** — muy por encima del
intervalo de prueba de 45 s — porque cada uno descarga de verdad el ZIP de
sindicación del mes en curso (~23 MB, periodo `202609` parcial) antes de
evaluar frescura. El mecanismo de "sin solaparse" hizo exactamente lo que
tenía que hacer en ese caso: en vez de lanzar un ciclo cada 45 s y
amontonarlos, cada ejecución programada arrancó **inmediatamente después**
de que terminara la anterior (siempre a los 3 s, el intervalo de sondeo del
worker) — la cadencia real queda acotada por abajo por cuánto tarda el
propio ciclo, nunca por debajo de eso, sin necesitar ninguna lógica
adicional para conseguirlo. Ninguna de las cuatro ejecuciones duplicó
trabajo: `descubrimiento.expedientes_nuevos` fue `0` en las tres que
llegaron a completarse (los 4 expedientes del departamento 28510 del
periodo en curso ya eran conocidos desde antes de empezar esta prueba).

**Hallazgo real de paso, no un fallo de este bloque**: las tres ejecuciones
completadas relanzaron la descarga del mismo expediente
(`6.24/28510.0106`) en cada pasada. Verificado en base de datos: es un
pedido derivado de acuerdo marco (`codigo_matriz = 6.20/28510.0136`,
`matriz_expediente_id` resuelto) sin ningún documento propio — sus
importes vienen heredados de la matriz (`docs/identidad-expediente.md` sección 20), así que
`app.mantenimiento.frescura.debe_descargar` lo reintenta en cada ciclo
exactamente como está diseñado (bloque 1: "sin documentos propios, merece
un intento nuevo"). Coste real, no gratis: un intento de scraping real
contra la Plataforma por ciclo hasta que se resuelva o quede
`sin_publicar` — esperable para este patrón, ya documentado, no nuevo de
esta sesión.

**Recuperación de trabajo huérfano, verificada en vivo por segunda vez en
esta sesión** (la primera fue en el bloque 2): al reconstruir el
contenedor del worker para volver al intervalo de producción, el trabajo
que estaba `en_proceso` en ese instante quedó huérfano y
`reclamar_trabajos_huerfanos` lo recuperó solo pasado el umbral — sin
intervención manual.

225 tests en verde (218 del bloque 2 + 7 de este bloque —
`tests/mantenimiento/test_programacion.py`: nunca corrió lanza ahora, no
lanza antes de tiempo, lanza cuando toca, no solapa con uno en curso
propio ni con uno disparado a mano, desactivado nunca lanza, `obtener_
estado` refleja lo real), dentro del contenedor.

### Variables de entorno nuevas

`MANTENIMIENTO_INTERVALO_SEGUNDOS` (segundos, 604800 por defecto) y
`MANTENIMIENTO_PROGRAMADO_ACTIVO` (`true`/`false`) — **añadidas tanto al
servicio `worker` (quien decide) como al servicio `api`** (quien las
expone en `GET /mantenimiento/estado`): un descuido real de esta sesión,
detectado en la propia verificación en vivo, fue añadirlas solo al
`worker` y dejar que la API siguiera leyendo el valor por defecto de
`app/config.py` — la web habría mostrado "semanal" aunque el worker
estuviera de verdad lanzando cada 45 segundos. Corregido antes de dar el
bloque por cerrado, no después.
