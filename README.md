# ADIF - esqueleto

Cuatro servicios: API (FastAPI), worker, PostgreSQL y web (Next.js). Ver
`CLAUDE.md` para el contexto completo del proyecto.

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
momento se quedan huérfanos (CLAUDE.md sección 17). Corregido en
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
