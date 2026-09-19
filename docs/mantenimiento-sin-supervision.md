# El mantenimiento sin nadie delante

Bloque 3 del encargo de la sesión 2026-09-19 (sexta parte): "cuando esto pase
al servidor va a funcionar solo. Compruébalo y dime."

Todo lo de aquí está **medido contra el stack real** de esta sesión, no
deducido del código. Las cuatro comprobaciones del encargo, en su orden, y al
final lo que se ha encontrado y lo que no hace falta arreglar.

---

## 1 — Qué ciclos automáticos existen, cada cuánto y qué hace cada uno

**Ninguno es un proceso aparte.** Los cuatro viven dentro del bucle del worker
que ya existe (`app.worker._vuelta_bucle_principal`), que da una vuelta cada
`WORKER_POLL_INTERVAL_SECONDS` = **3 s**. No hay un quinto proceso "scheduler",
ni cron del sistema operativo, ni Redis (CONTEXTO.md sección 10). Cada vuelta
son dos `SELECT` contra `trabajos_cola`: nunca red, nunca Playwright en la
comprobación misma.

| Ciclo | Tipo de trabajo | Cada cuánto | Qué hace |
|---|---|---|---|
| **Mantenimiento** | `mantenimiento_ciclo` | `MANTENIMIENTO_INTERVALO_SEGUNDOS` = **604.800 s (7 días)** | Descubre expedientes nuevos (sindicación mensual + búsqueda directa), decide por frescura qué descargar y qué reextraer, reintenta los `sin_publicar` que ya tocan, **drena la cola** de todo lo que ha encolado y, al terminar, encola y ejecuta la auditoría |
| **Copia de seguridad** | `copia_seguridad` | `BACKUP_INTERVALO_SEGUNDOS` = **86.400 s (24 h)** | `pg_dump --format=custom` de la base entera al volumen `copias_seguridad_bd`, y purga las que sobren de `BACKUP_RETENCION` = **14** |
| **Descubrimiento inverso de pedidos** | `descubrimiento_pedidos` | 604.800 s (7 días), por defecto de `app.config` | Busca en la Plataforma los pedidos que cuelgan de cada acuerdo marco conocido, por su adjudicatario |
| **Auditoría del catálogo** | `auditoria_catalogo` | **Sin programación propia**: se encola sola al final de cada ciclo de mantenimiento | Comprueba el catálogo entero (huérfanas, precios atípicos, duplicados, cantidades con forma de año, importes compartidos…) y deja sus hallazgos en el resultado del trabajo |

**Más una tarea de vigilancia, en cada vuelta**:
`reclamar_trabajos_huerfanos` recupera todo trabajo `en_proceso` cuyo
`bloqueado_en` supere `WORKER_ORPHAN_THRESHOLD_SECONDS` = **300 s** (ver el
punto 4).

**"Sin solaparse consigo mismo" sale gratis de la propia cola**: si ya hay un
trabajo de ese tipo `pendiente` o `en_proceso` —programado o disparado a
mano— no se encola otro. Es **por tipo**, no global: una copia de seguridad no
espera a que termine un ciclo de mantenimiento.

**El histórico es la propia `trabajos_cola`**, sin tabla aparte. Medido hoy
sobre la base real:

| Tipo | Ejecuciones | Desde | Última |
|---|---:|---|---|
| `extraer_expediente` | 27.693 | 2026-09-03 | hoy |
| `descargar_expediente` | 1.468 | 2026-09-03 | 2026-09-18 |
| `auditoria_catalogo` | 112 | 2026-09-08 | hoy |
| `mantenimiento_ciclo` | 103 | 2026-09-04 | hoy |
| `sindicacion_backfill` | 30 | 2026-09-07 | 2026-09-15 |
| `copia_seguridad` | 22 | 2026-09-06 | hoy |
| `descubrimiento_pedidos` | 7 | 2026-09-07 | 2026-09-14 |
| `ingesta_local` | 5 | 2026-09-12 | 2026-09-12 |
| `ocr_relectura` | 1 | 2026-09-19 | hoy |

`sindicacion_backfill`, `ingesta_local` y `ocr_relectura` **no son ciclos**:
son trabajos que solo se lanzan a mano por su endpoint, y están en la tabla
para que se vea que la cola es una sola.

---

## 2 — La caducidad de la marca de "no publicado"

**Funciona como se diseñó.** Un expediente que la Plataforma confirma que no
tiene se marca `sin_publicar` con la fecha y la versión de la lógica de
búsqueda que lo confirmó. A partir de ahí:

| Caso | Cuándo se vuelve a buscar |
|---|---|
| Negativo **sin confirmar** (de antes del arreglo de límite de tasa: sin versión de búsqueda) | **Ya**, sin plazo |
| Confirmado, expediente del **año en curso o el anterior** (`SIN_PUBLICAR_ANIOS_RECIENTES` = 1) | **3 días** (`SIN_PUBLICAR_REINTENTO_DIAS_RECIENTES`) |
| Confirmado, expediente **más antiguo** | **14 días** (`SIN_PUBLICAR_REINTENTO_DIAS`) |
| Código del que no se puede leer el año | 14 días — lo que no se sabe leer se rebusca **menos**, no más |

Con un tope de `SIN_PUBLICAR_REINTENTOS_POR_CICLO` = **50** por ciclo, y con
los no confirmados y los más antiguos primero.

**La prueba que pidió el encargo.** Las dos ramas ya estaban probadas sobre la
función pura; lo que faltaba era comprobarlo **dentro del ciclo real**, que es
quien decide a quién se le vuelve a pedir una búsqueda a la Plataforma. Añadida
`test_la_caducidad_corta_y_la_larga_del_sin_publicar_deciden_dentro_del_ciclo`
(`engine/tests/mantenimiento/test_ciclo.py`): dos expedientes idénticos salvo
en el año de su código, los dos marcados hace **cuatro días** y los dos
confirmados con la lógica vigente. El ciclo rebusca **solo el del año en
curso**; el de 2014 se cuenta como "en plazo" y no gasta ni una búsqueda.

Y su otra mitad,
`test_la_bandera_de_busqueda_desactivada_no_deja_salir_a_la_red_ni_por_esta_via`:
un reproceso lanzado sin red tampoco lanza esta búsqueda, que es la tercera vía
de red del ciclo y hasta la sesión 2026-09-18 era la única que ninguna bandera
apagaba.

**Por qué el plazo corto existe**, con su caso real: `6.26/28510.0057` se buscó
el 16/09 y no estaba; el 18/09 ya estaba publicado. Con catorce días se habría
encontrado el 30/09.

---

## 3 — La copia de seguridad

**Se hace sola.** Medido sobre el histórico real: copias programadas
(`disparado_por: "programado"`) los días 15, 16, 17 y 18 de septiembre, y
manuales el 14 y el 19. La del 19 la lanzó esta sesión para poder restaurarla.

**Dónde se guarda.** En el volumen de Docker `copias_seguridad_bd`, montado en
`/backups` **solo en el contenedor `worker`** y deliberadamente **distinto de
`postgres_data`**: perder el volumen de datos no se lleva las copias por
delante.

**Cuántas se conservan.** `BACKUP_RETENCION` = **14**. Comprobado en vivo: la
copia de las 19:46 de hoy devolvió
`{"copias_eliminadas": ["adif_20260914_130922.dump"], "copias_conservadas": 14}`
— purgó la más antigua y dejó exactamente catorce. El fichero de hoy pesa
**44.175.749 bytes** (~42 MiB).

**La restauración de prueba, hecha de verdad en una base aparte.**

```
CREATE DATABASE adif_restore_test;
pg_restore --no-owner -h postgres -U adif -d adif_restore_test /backups/adif_20260919_194630.dump
```

| Comprobación | Base real | Restaurada |
|---|---:|---:|
| `expedientes` | 612 | **612** |
| `lineas_catalogo` | 40.016 | **40.016** |
| `documentos` | 1.638 | **1.638** |
| `lotes` | 695 | **695** |
| `trazas_origen` | 2.108 | **2.108** |
| `trabajos_cola` | 29.442 | **29.442** |
| `cache_mapeo_cabecera` | 497 | **497** |
| `cache_ocr_documento` | 140 | **140** |
| `md5` de todos los expedientes (código + baja) | `e4eba3d9…` | **`e4eba3d9…`** |
| `md5` de todas las líneas (id + descripción + precio + adjudicado) | `9565c99b…` | **`9565c99b…`** |
| `alembic_version` | 0041 | **0041** |

**Idéntico byte a byte**, no solo mismo recuento. El único mensaje de
`pg_restore` es el ya conocido y **inofensivo**: `unrecognized configuration
parameter "transaction_timeout"`, porque el cliente (`postgresql-client` de
Debian) es más nuevo que el servidor (`postgres:16-alpine`) — la dirección de
compatibilidad que PostgreSQL sí soporta. Termina con `EXIT=0`.

**Un detalle que conviene saber.** La retención ordena por el nombre del
fichero, y en el volumen conviven copias automáticas
(`adif_AAAAMMDD_HHMMSS.dump`) con copias manuales de nombre propio
(`adif_20260917_antes_ocr.dump`). Las manuales **cuentan para la retención** y
se purgan como cualquier otra cuando les toca por orden de nombre. No es un
defecto —son copias de la misma base, en el mismo sitio— pero si alguna se
quiere conservar indefinidamente, hay que sacarla del volumen.

---

## 4 — Si un ciclo falla a mitad

**Demostrado en vivo, matando el worker a mitad de un ciclo real.** No
simulado: `docker compose kill worker` (SIGKILL, sin apagado ordenado) sobre un
ciclo de mantenimiento que estaba drenando 40 extracciones forzadas.

### La cronología medida

| Hora (UTC) | Qué pasó |
|---|---|
| 19:47:38 | Ciclo `29657` empieza. Encola 40 `extraer_expediente` y las drena una a una |
| **19:47:44** | **`docker compose kill worker`** — SIGKILL en mitad de la extracción número 11 |
| 19:47:44 | Estado en ese instante: ciclo `en_proceso` (`bloqueado_en` 19:47:44), **10 extracciones completadas**, **1 `en_proceso`** (huérfana), **29 `pendiente`** |
| 19:47:53 | `docker compose start worker` |
| 19:47:58 | El worker **ya está drenando** las pendientes por su bucle normal, sin esperar a nadie |
| 19:52:09 | Las **39 extracciones pendientes, completadas solas**. Los dos huérfanos (el ciclo y su extracción 11) siguen `en_proceso`, esperando el umbral |
| **19:52:44** | Se cumplen los 300 s desde `bloqueado_en` |
| 19:52:48 | `reclamar_trabajos_huerfanos` los recupera: la extracción vuelve a `pendiente` y se completa; el ciclo pasa a `pendiente` con `intentos` 1 → 2 y el error *"trabajo huérfano: bloqueado_en superó el umbral de 300s sin completarse (worker caído o reiniciado a mitad de ejecución)"*, y arranca de nuevo |
| 19:52:5x | **Segundo intento del ciclo, completado en 9,7 s** |

### Qué queda en la cola, exactamente

- **Lo que estaba `pendiente` se queda `pendiente`** y lo recoge el bucle
  normal del worker en cuanto vuelve — **sin esperar al ciclo siguiente**, sin
  intervención y sin perder nada. Es la razón de que la cola esté en PostgreSQL
  y no en memoria.
- **Lo que estaba `en_proceso`** (el trabajo que el worker tenía en la mano al
  morir, y el propio ciclo) queda bloqueado por un worker que ya no existe, y
  `tomar_siguiente_trabajo` nunca lo miraría porque solo busca `pendiente`.
  Para eso está la reclamación por `bloqueado_en`: **a los 300 s vuelve solo**.
- **Nunca se reinician los intentos.** Un huérfano vuelve a `pendiente` si le
  quedan intentos de sus `max_intentos` = 3, y a `fallido` si ya los agotó —
  para no darle una oportunidad extra que un fallo corriente no tendría.

### Y el siguiente ciclo, ¿se recupera solo?

**Sí, y sin rehacer el trabajo ya hecho.** El segundo intento del ciclo
`29657`:

```
expedientes_evaluados: 519
saltados_extraccion:   516
extracciones_lanzadas:   1
trabajos_drenados:       3
duracion_segundos:     9.676
```

De los 40 expedientes forzados, **39 no se volvieron a extraer**: el primer
intento ya los había completado. Lo hace la resumibilidad de
`debe_extraer(..., ciclo_creado_en=trabajo.created_at)` — si `extraido_en` ya
es posterior al `created_at` del propio ciclo, ese expediente ya se hizo en un
intento anterior de **este mismo** ciclo, y se salta **incluso con
`forzar=True`**. Sin esa guarda, un reinicio a mitad de un ciclo de 20 minutos
lo empezaría desde cero cada vez.

**El ciclo renueva su propio bloqueo mientras drena** (`_renovar_bloqueo`), así
que un ciclo largo —los reprocesos completos duran ~20 min, muy por encima de
los 300 s del umbral— nunca se reclama a sí mismo por error.

---

## Qué se ha arreglado y qué no hacía falta arreglar

**No se ha encontrado nada roto en los cuatro puntos.** Los cuatro mecanismos
—programación, caducidad de `sin_publicar`, copias y recuperación de
huérfanos— hacen lo que dicen, y ahora está medido en vivo en vez de deducido.

Lo único que faltaba era **cobertura de prueba**: la caducidad 3/14 estaba
probada sobre la función pura pero no dentro del ciclo, que es quien decide.
Añadidas dos pruebas (`engine/tests/mantenimiento/test_ciclo.py`).

**Lo que sí conviene saber antes de pasar al servidor**, ninguna de las tres
cosas un defecto:

1. **Con un único worker la programación no compite consigo misma.** Si algún
   día hubiera varias réplicas, dos podrían decidir lanzar en la misma vuelta
   antes de que ninguna llegue a insertar. No se ha construido un bloqueo
   distribuido para un caso que la arquitectura de cuatro procesos no tiene.
2. **Un ciclo que se quede huérfano tres veces seguidas acaba `fallido`** y no
   vuelve a intentarse hasta que toque el siguiente programado (7 días). Es lo
   que dicta `max_intentos`, y es deliberado: tres caídas seguidas del worker
   en el mismo ciclo no son algo que un reintento automático arregle.
3. **Las copias manuales cuentan para la retención de 14** (ver punto 3).
