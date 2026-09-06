# ADIF - esqueleto

Cuatro servicios: API (FastAPI), worker, PostgreSQL y web (Next.js). Ver
`CONTEXTO.md` para el contexto completo del proyecto.

## Docker corre dentro de WSL, no en Windows directamente

Esta máquina no tiene Docker Desktop. Docker Engine está instalado dentro de
la distro WSL `Ubuntu-24.04`, con systemd habilitado. **`dockerd` no arranca
solo al abrir la distro** — hay que arrancarlo explícitamente:

```
wsl -d Ubuntu-24.04 -u root -- systemctl start docker
```

(`systemctl enable docker` ya está aplicado, así que si la propia distro WSL
se reinicia con systemd activo debería levantarse sola; el arranque manual de
arriba es la red de seguridad si no fue así.) Comprobar que responde:

```
wsl -d Ubuntu-24.04 -u lucas -- docker ps
```

### La VM de WSL se suspende sola y se lleva `dockerd` por delante

Ajuste de esta máquina, no del proyecto: sin tocar nada, la VM ligera de WSL2
se suspende tras un rato sin actividad (`vmIdleTimeout` de Windows, no algo
de esta distro ni de Docker). Cuando pasa, `dockerd` se cae con ella —
síntoma verificado en sesión: los cuatro servicios de `docker compose ps`
en `Exited` y `dockerd` con un `Active: ... since` de segundos antes, sin que
nadie tocara nada. Los trabajos de la cola que estaban `en_proceso` en ese
momento se quedan huérfanos (CONTEXTO.md sección 17). Corregido en
`C:\Users\<usuario>\.wslconfig` (fuera del repo, uno por máquina):

```ini
[wsl2]
vmIdleTimeout=-1
```

`-1` desactiva la suspensión por inactividad. Solo se aplica arrancando la VM
de nuevo, nunca en caliente:

```
wsl --shutdown
wsl -d Ubuntu-24.04 -u root -- systemctl start docker
```

### Segunda causa de caída: reanudación del modo de espera moderno de Windows

Diagnóstico completo en `docs/diagnostico-caidas-dockerd.md`. Resumen: tras
corregir lo de arriba, la VM seguía sin caerse por inactividad, pero al
reanudar el portátil desde el modo de espera moderno (S0ix) — típicamente
al abrir la tapa — WSL fuerza un reinicio limpio del *init* de la distro
(systemd, y con él `dockerd` y todos los contenedores) sin reiniciar la VM
ni el kernel. **Solo se dispara al reanudar de una suspensión real: si el
portátil se queda enchufado y despierto, no debería ocurrir.**

Dos cambios de esta máquina (no del proyecto) mitigan esto para el día de
la demo:

1. **Cierre de tapa en corriente no hace nada** (antes suspendía, y
   `powercfg /query` no expone esta opción en la UI de esta máquina —
   se cambió directamente por GUID):
   ```
   powercfg /setacvalueindex SCHEME_CURRENT SUB_BUTTONS 5ca83367-6e45-459f-a27b-476b1d01c936 0
   powercfg /setactive SCHEME_CURRENT
   ```
   El valor de fábrica de Windows para esta acción suele ser `1`
   (Suspender). **Si no era ese el valor original de esta máquina antes
   del cambio, no quedó registrado** — la opción ya estaba oculta en la UI
   antes de tocarla, así que no se pudo leer el valor previo con
   `powercfg /query`. Para revertir al valor de fábrica más probable:
   ```
   powercfg /setacvalueindex SCHEME_CURRENT SUB_BUTTONS 5ca83367-6e45-459f-a27b-476b1d01c936 1
   powercfg /setactive SCHEME_CURRENT
   ```
   (En corriente continua/batería no se tocó nada: la tapa sigue
   suspendiendo el equipo con batería, comportamiento normal fuera de la
   demo.)
2. **Suspensión por inactividad en corriente ya estaba en "Nunca"**
   (`STANDBYIDLE` = `0x00000000` para AC) — no fue necesario cambiar nada
   ahí, solo se confirmó.
3. **Tarea programada `ADIF-WSL-Docker-Autostart`** (Programador de
   tareas de Windows, solo para el usuario actual): arranca
   `wsl -d Ubuntu-24.04 -u root -- systemctl start docker` al iniciar
   sesión, para no tener que levantarlo a mano. Verificada en esta sesión:
   terminar la distro (`wsl --terminate Ubuntu-24.04`) y disparar la tarea
   la deja `Running` con `docker.service` `active` de nuevo. Para
   revertirla:
   ```
   Unregister-ScheduledTask -TaskName "ADIF-WSL-Docker-Autostart" -Confirm:$false
   ```
4. **Tarea programada `ADIF-WSL-Docker-Watchdog`** (Programador de tareas
   de Windows, se repite cada minuto): reasegura que `dockerd` sigue activo
   dentro de la distro, para cubrir el hueco entre que WSL se reinicia y la
   tarea de arranque de sesión (punto 3) llega a ejecutarse. Ambas tareas
   arrancan `wsl.exe` a través de `wscript.exe` + un script `.vbs` (no
   directamente), para no abrir una ventana de consola visible en cada
   disparo (`docs/tolerancia-reinicios-dockerd.md`). Para revertirla:
   ```
   Unregister-ScheduledTask -TaskName "ADIF-WSL-Docker-Watchdog" -Confirm:$false
   ```
5. **`restart: unless-stopped` en los cuatro servicios de
   `docker-compose.yml`** (postgres, api, worker, web): cierra el hueco
   que dejaban los tres puntos anteriores. Con esto, si un contenedor
   muere por su cuenta (crash, `dockerd` reiniciándose), Docker lo vuelve
   a levantar sin que nadie ejecute `docker compose up` — incluido el caso
   completo de la demo: tapa cerrada → WSL cae → tarea programada levanta
   WSL y `dockerd` → `dockerd`, al arrancar, recupera él solo los cuatro
   contenedores que tenían esta política. Verificado en sesión con las dos
   pruebas siguientes:
   - Matar el proceso principal de un contenedor desde dentro (simulando
     un crash real) → Docker lo reinicia solo en segundos.
   - Un `docker kill`/`docker stop` explícito **no** lo reinicia — es el
     comportamiento correcto de `unless-stopped`: distingue una caída de
     una parada intencionada (`docker compose down` incluido), así que
     parar el stack a propósito sigue funcionando como siempre.

   Terminar la distro entera y disparar la tarea programada (sin ejecutar
   nada más a mano) dejó los cuatro contenedores arriba y la API y la web
   respondiendo (`GET /health` → `200`, `GET /` de la web → `200`).

### Dónde vive el proyecto para `docker compose`

**Una sola copia del árbol de trabajo: el repositorio en `C:\dev\ADIF`,
montado en WSL como `/mnt/c/dev/ADIF`.** `docker compose` se ejecuta
directamente contra esa ruta — nunca contra una copia sincronizada aparte
(`~/adif` o cualquier otra ruta nativa de WSL). Una sesión anterior de este
README recomendaba precisamente eso (`rsync` a `~/adif` para evitar la
penalización de compilar sobre el puente 9p de `/mnt/c/...`), y es
exactamente el patrón que `CONTEXTO.md` (invariante 11) prohíbe: una
segunda copia del árbol puede divergir del repositorio versionado sin que
`git status` lo note, y ya ha pasado dos veces en este proyecto que los
contenedores reales acabaran sirviendo esa copia suelta en vez del código
que de verdad estaba en `git`. Los tiempos de build medidos contra
`/mnt/c/dev/ADIF` en esta sesión (API/worker/web, con caché de capas) están
en el orden de segundos a un minuto — no justifican el riesgo.

Si alguna vez el rendimiento de compilar contra `/mnt/c/...` se vuelve un
problema real, la única vía permitida es un `git worktree` del mismo
repositorio (`git worktree add /ruta/nativa/wsl <rama>`) — nunca una copia
de ficheros (`cp`/`rsync`) que pueda quedar desincronizada. Antes de confiar
en un contenedor reconstruido, verifica desde qué ruta se construyó:

```
docker inspect --format '{{json .Config.Labels}}' adif-web-1
```

`com.docker.compose.project.working_dir` debe apuntar a `/mnt/c/dev/ADIF`
(o a un `git worktree` suyo) — si apunta a cualquier otro sitio, para y
averigua de dónde salió esa copia antes de seguir.

Los comandos de `docker compose` de las secciones siguientes se ejecutan
así, desde el propio repositorio:

```
wsl -d Ubuntu-24.04 -u lucas -- bash -lc "cd /mnt/c/dev/ADIF && docker compose up --build -d"
```

## Levantar

```
docker compose up --build
```

- Web: http://localhost:3000
- API: http://localhost:8000/docs
- Postgres: localhost:5432 (usuario/clave por defecto en `.env.example`)

La API aplica las migraciones de Alembic al arrancar. La web solo llama a la
API por HTTP, nunca toca la base de datos ni ficheros.

Probar la cola de trabajos:

```
curl -X POST http://localhost:8000/trabajos/ping
```

Encola un trabajo de tipo `ping`, que no hace nada útil. El worker lo recoge
en unos segundos (bloqueo por fila en PostgreSQL, sin Redis ni Celery) y lo
marca `completado`.

## Parar

```
docker compose down
```

Los datos de Postgres y los documentos persisten en volúmenes con nombre y
sobreviven a `docker compose down`. Para borrarlos también: `docker compose down -v`.

## Variables de entorno

Copiar `.env.example` a `.env` y ajustar si hace falta. `API_URL` es la
dirección que usa la web para llamar a la API: cambia sin tocar código.

## Copias de seguridad

Con un entorno que se reinicia solo varias veces al día (ver arriba), no
había ninguna copia periódica de la base de datos hasta esta sesión —
perder el volumen `postgres_data` se llevaba por delante los expedientes
procesados y el catálogo entero sin ningún respaldo.

### Cómo funciona

El worker lanza una copia de seguridad completa (`pg_dump --format=custom`)
como un tipo de trabajo más de la cola (`copia_seguridad`, mismo mecanismo
que el ciclo de mantenimiento — ver `CONTEXTO.md` sección 10, "cuatro
procesos, ni uno más": ningún proceso ni cron nuevo). Diaria por defecto,
configurable sin tocar código:

| Variable | Por defecto | Qué hace |
|---|---|---|
| `BACKUP_ACTIVO` | `true` | Desactiva la copia programada sin tocar código (el disparo manual, más abajo, sigue funcionando). |
| `BACKUP_INTERVALO_SEGUNDOS` | `86400` (diario) | Cada cuánto se lanza sola. |
| `BACKUP_RETENCION` | `14` | Cuántas copias se conservan (la más reciente cuenta como una) antes de borrar las más antiguas. |

Las copias se guardan en el volumen de Docker **`copias_seguridad_bd`**,
montado en `/backups` dentro del contenedor `worker` — **un volumen
distinto del de PostgreSQL (`postgres_data`)**, a propósito: si se pierde
el volumen de datos, las copias no se van con él.

Disparar una copia a mano (sin esperar al intervalo) y consultar su
estado/histórico:

```
curl -X POST http://localhost:8000/mantenimiento/copias/ejecutar
curl http://localhost:8000/mantenimiento/copias/estado
curl http://localhost:8000/mantenimiento/copias/historial
```

Listar las copias que hay ahora mismo:

```
docker compose exec worker ls -la /backups
```

### Cómo restaurar

**Probado de verdad en esta sesión** (sesión 2026-09-06): se generó una
copia contra la base de datos real (58 expedientes, 3.007 líneas de
catálogo, 222 documentos, 1.038 trabajos de cola), se restauró en una base
de datos limpia del mismo servidor, y se comprobó que los datos volvían
completos — recuentos por tabla idénticos, un `md5` de todas las filas de
`expedientes` y de `lineas_catalogo` idéntico byte a byte entre el origen y
la copia restaurada, y `alembic_version` igual en las dos. Procedimiento,
con `<archivo>` el nombre real del `.dump` (`docker compose exec worker ls
/backups`):

```
# 1. Base de datos limpia para restaurar (nunca la de producción directamente
#    hasta haber verificado que la copia está bien).
docker compose exec postgres psql -U adif -d postgres \
  -c "CREATE DATABASE adif_restaurada;"

# 2. Restaurar la copia en esa base limpia.
docker compose exec worker pg_restore --no-owner \
  -h postgres -U adif -d adif_restaurada /backups/<archivo>

# 3. Comprobar que los datos están completos antes de dar la copia por buena.
docker compose exec postgres psql -U adif -d adif_restaurada \
  -c "select count(*) from expedientes; select count(*) from lineas_catalogo;"
```

**Aviso esperado, no un fallo real:** `pg_restore` puede imprimir `ERROR:
unrecognized configuration parameter "transaction_timeout"` con `warning:
errors ignored on restore: 1`. Es una diferencia de versión entre el
cliente (`postgresql-client` de Debian, más nuevo) y el servidor
(`postgres:16-alpine`) sobre un ajuste de sesión, no sobre datos —
verificado en esta misma sesión que los datos restaurados quedan idénticos
pese a ese aviso.

Cuando la copia restaurada está verificada, para promoverla a la base real
(**parada la API y el worker antes**, para que nada escriba a mitad):

```
docker compose stop api worker
docker compose exec postgres psql -U adif -d postgres \
  -c "ALTER DATABASE adif RENAME TO adif_anterior; ALTER DATABASE adif_restaurada RENAME TO adif;"
docker compose start api worker
```

(`adif_anterior` queda como red de seguridad -- bórrala a mano una vez
confirmado que todo funciona con la restaurada.)
