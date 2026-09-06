# Copias de seguridad automáticas (sesión 2026-09-06)

## El problema

No había ninguna copia de seguridad periódica de la base de datos, solo
volcados puntuales hechos a mano antes de cada limpieza. Con un entorno que
se reinicia solo varias veces al día (`docs/diagnostico-caidas-dockerd.md`,
`docs/tolerancia-reinicios-dockerd.md`), perder el volumen `postgres_data`
se llevaría por delante los 43 expedientes procesados y más de 3.000 líneas
de catálogo sin ningún respaldo.

## El diseño

Mismo mecanismo que el ciclo de mantenimiento (`docs/mantenimiento-automatico.md`):
un tipo de trabajo más de la cola (`copia_seguridad`), lanzado desde el
propio bucle del worker -- ningún quinto proceso, ningún cron del sistema
operativo (CONTEXTO.md sección 10). `app.mantenimiento.programacion`, que ya
llevaba el algoritmo de "cada cuánto, sin solaparse consigo mismo, con
histórico en la propia cola" para el ciclo de mantenimiento, se generalizó
por tipo de trabajo (`_ultimo_trabajo`, `_hay_trabajo_en_curso`,
`_debe_lanzar`, `_obtener_estado`, todas parametrizadas por `tipo` en vez
de fijas a `mantenimiento_ciclo`) en vez de duplicar el algoritmo en un
módulo aparte que habría podido divergir con el tiempo.

`app.mantenimiento.copia_seguridad.ejecutar_copia_seguridad` vuelca la base
de datos completa con `pg_dump --format=custom` (formato binario propio de
PostgreSQL, comprimido de por sí y restaurable con `pg_restore` sin
depender de que un volcado en texto plano cuadre carácter a carácter -- el
formato que PostgreSQL recomienda para copias que se van a restaurar, no
solo a inspeccionar). `settings.database_url` viene en formato SQLAlchemy
(`postgresql+psycopg://...`), que `pg_dump` no acepta como argumento
directo: se parte a mano (`parametros_desde_url`) y se pasa como variables
de entorno estándar de libpq (`PGHOST`, `PGPORT`...).

Guardadas en un volumen de Docker propio, `copias_seguridad_bd`, montado en
`/backups` solo en el contenedor `worker` -- deliberadamente distinto de
`postgres_data`, para que perder el volumen de datos no se lleve las copias
por delante (encargo explícito de la sesión). Retención configurable
(`BACKUP_RETENCION`, 14 por defecto): tras cada copia con éxito,
`purgar_copias_antiguas` borra las que sobren, ordenando por el propio
nombre de archivo (`adif_AAAAMMDD_HHMMSS.dump`, ya cronológico sin mirar la
fecha de modificación del fichero).

`postgresql-client` (paquete de Debian, instalado en `engine/Dockerfile`)
trae `pg_dump`/`pg_restore` en una versión más nueva que el servidor
(`postgres:16-alpine`) -- la dirección de compatibilidad que sí está
soportada por PostgreSQL: un cliente más nuevo sabe volcar/restaurar un
servidor más antiguo, no al revés. No se usó el repositorio APT de PGDG
para fijar una versión exacta -- verificado en esta misma sesión (ver
abajo) que la versión de Debian basta.

## Verificación en vivo

Contra el stack real (`docker compose`), con la base de datos de desarrollo
real (58 expedientes, 3.007 líneas de catálogo, 222 documentos, 1.038
trabajos de cola):

1. **Disparo manual** (`POST /mantenimiento/copias/ejecutar`): copia
   creada en ~2-3 s, `.dump` de ~300 KB, visible en
   `docker exec adif-worker-1 ls /backups`.
2. **Disparo programado**: con ninguna copia previa, la primera vuelta del
   bucle del worker la lanzó sola (mismo criterio que el ciclo de
   mantenimiento: "nunca ha corrido" cuenta como "ya toca").
3. **Retención**: con `BACKUP_RETENCION=3` y 5 copias ya en el volumen, la
   siguiente copia purgó las 2 más antiguas y dejó exactamente 3 -- las más
   recientes. Confirmado también que un ciclo de mantenimiento en curso
   (`en_proceso`) no bloquea la copia programada: "sin solaparse consigo
   mismo" es por tipo de trabajo, no global (`test_copia_no_lanza_si_ciclo_de_mantenimiento_esta_en_curso`).
4. **Restauración completa, probada de verdad**: se restauró la última
   copia en una base de datos limpia del mismo servidor
   (`CREATE DATABASE adif_restore_test`, `pg_restore --no-owner`) y se
   comparó contra el origen:
   - Recuentos por tabla idénticos: `expedientes` (58), `lineas_catalogo`
     (3.007), `documentos` (222), `trabajos_cola` (1.038).
   - `md5(string_agg(...))` de todas las filas de `expedientes`
     (`codigo_expediente` + `baja_global`) y de `lineas_catalogo`
     (`descripcion` + `precio_unitario` + `precio_adjudicado`) **idéntico
     byte a byte** entre el origen y la copia restaurada -- no solo mismo
     recuento, mismo contenido.
   - `alembic_version` igual en las dos (`0016`).
   - Único aviso durante `pg_restore`: `ERROR: unrecognized configuration
     parameter "transaction_timeout"` / `warning: errors ignored on
     restore: 1` -- diferencia de versión cliente/servidor sobre un ajuste
     de sesión (el cliente v17 de Debian emite un `SET transaction_timeout`
     que el servidor v16 no reconoce), sin ningún efecto sobre los datos,
     confirmado por los `md5` idénticos de arriba. Documentado en
     `README.md` como aviso esperado, no un fallo a investigar.
   - Base de datos de prueba borrada al terminar (`DROP DATABASE`).

363 tests en verde dentro del contenedor `api` (los 348 anteriores + 15 de
este bloque: 9 en `tests/mantenimiento/test_copia_seguridad.py` --
parseo de la URL de conexión, nombre de archivo cronológico, listado y
purga de copias con `tmp_path`, éxito/purga/fallo de
`ejecutar_copia_seguridad` con `subprocess.run` sustituido -- y 7 en
`tests/mantenimiento/test_programacion.py`, mismos siete casos que ya
cubrían el ciclo de mantenimiento, aplicados a `copia_seguridad`).

## Hallazgo de paso durante esta sesión: README desactualizado

Al documentar dónde quedan las copias se encontró que `README.md`
("Dónde vive el proyecto para `docker compose`") todavía instruía a
sincronizar el repositorio a `~/adif` dentro de WSL y levantar
`docker compose` desde esa copia -- exactamente el patrón que CONTEXTO.md
invariante 11 prohíbe ("ya ha pasado dos veces" que una copia suelta del
árbol acabara sirviendo los contenedores reales sin que nadie lo dejara
escrito). El stack real de esta sesión se construyó y se verificó
construido directamente desde `/mnt/c/dev/ADIF`
(`docker inspect --format '{{json .Config.Labels}}'`), no desde `~/adif`
(que, comprobado, ni siquiera existía ya en esta máquina). Corregido en la
misma sesión: la sección ahora indica explícitamente la ruta única
permitida y la referencia al invariante 11, con `git worktree` como única
vía de escape documentada si el rendimiento de compilar contra `/mnt/c/...`
llega a ser un problema real. De paso, se añadió al README la mención de
la tarea programada `ADIF-WSL-Docker-Watchdog` (existe y está activa en
esta máquina, verificado con `Get-ScheduledTask`), que faltaba desde que se
creó en la sesión de tolerancia a reinicios de `dockerd`.
