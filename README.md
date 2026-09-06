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
4. **`restart: unless-stopped` en los cuatro servicios de
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

El repositorio se edita en `C:\dev\ADIF` (Windows). Pero `docker compose` se
ejecuta contra una **copia dentro del filesystem nativo de WSL**, en
`~/adif` (dentro de la distro), no contra `/mnt/c/dev/ADIF`. Trabajar sobre
`/mnt/c/...` desde Docker-en-WSL es notablemente más lento (cada `COPY` del
build cruza el puente 9p) y arrastra permisos raros (todo sale `777`). La
carpeta `Ejemplo/` (los PDFs de referencia) se queda fuera de esa copia
porque no la necesita ningún build.

Cada vez que cambies algo en `C:\dev\ADIF`, resincroniza antes de levantar:

```
wsl -d Ubuntu-24.04 -u lucas -- bash -lc "rsync -a --exclude='Ejemplo' /mnt/c/dev/ADIF/ ~/adif/"
```

Y los comandos de `docker compose` de las secciones siguientes se ejecutan
así, desde esa copia:

```
wsl -d Ubuntu-24.04 -u lucas -- bash -lc "cd ~/adif && docker compose up --build -d"
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
