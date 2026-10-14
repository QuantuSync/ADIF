# Despliegue en la máquina de Azure (2026-10-14)

Procedimiento real, con los comandos que se usaron de verdad, para montar la
plataforma en `adif-catalogo-ineco.spaincentral.cloudapp.azure.com`
(158.158.50.88, Ubuntu 24.04, usuario `adif`). Todo se ejecutó desde el
portátil de desarrollo (Windows 11, Git Bash) por SSH. La referencia general
es [guia-de-operacion.md](guia-de-operacion.md); aquí queda lo que se hizo y
lo que hubo que cambiar.

## Bloque 1. Acceso por SSH

La clave original de la máquina se generó en Cloud Shell y se perdió. Se creó
una clave propia para esta máquina en el portátil:

```powershell
ssh-keygen -t ed25519 -f $env:USERPROFILE\.ssh\id_ed25519_adif -N '""' -C "adif-vm" -q
```

Huella: `SHA256:Oa1e+uShKV0uPfB4HlzU7s+3s50yvCIcTETQklUXT6M`. Se registró
desde Cloud Shell:

```bash
az vm user update -g <grupo> -n <vm> --username adif \
  --ssh-key-value "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIP+2E4/m6sGEZOhotvgve6t4/fT8sOUvmrCdYjkTTGZh adif-vm"
```

Para no indicar la clave en cada comando (`ssh`, `scp`, `rsync`), en
`%USERPROFILE%\.ssh\config` del portátil:

```
Host adif-catalogo-ineco.spaincentral.cloudapp.azure.com 158.158.50.88
    User adif
    IdentityFile ~/.ssh/id_ed25519_adif
    IdentitiesOnly yes
    ServerAliveInterval 30
    ServerAliveCountMax 6
```

Lo leen igual el `ssh` de Windows y el de Git Bash (`ssh -G <host>` lo
confirma). Comprobación de entrada y de `sudo` sin contraseña:

```bash
ssh -o BatchMode=yes adif-catalogo-ineco.spaincentral.cloudapp.azure.com 'whoami; sudo -n true && echo SUDO OK'
```

En `~/.ssh/authorized_keys` de `adif` había tres claves: la RSA original de
Cloud Shell (perdida), una de otro proyecto registrada por error y la nueva.
Se dejó solo la nueva, comprobando antes que estaba y sustituyendo el fichero
de una vez:

```bash
cd ~/.ssh
grep -F "AAAAC3NzaC1lZDI1NTE5AAAAIP+2E4/m6sGEZOhotvgve6t4/fT8sOUvmrCdYjkTTGZh adif-vm" authorized_keys > ak.nuevo
[ "$(wc -l < ak.nuevo)" = 1 ] && chmod 600 ak.nuevo && mv ak.nuevo authorized_keys
```

Después se volvió a entrar con la clave nueva (bien) y se probó la del otro
proyecto (`Permission denied (publickey)`).

## Bloque 2. Instalación

Estado de partida: Ubuntu 24.04.4, kernel 6.17 de Azure, sin Docker, `/opt` y
`/srv` vacíos, 246 GB libres, salida a GitHub correcta.

El repositorio es público, así que se clonó directamente de GitHub (así
`git pull` sirve para actualizar):

```bash
ssh adif-catalogo-ineco.spaincentral.cloudapp.azure.com
sudo git clone -q https://github.com/QuantuSync/ADIF.git /opt/adif
sudo git -C /opt/adif check-ignore -v deploy/.env     # .gitignore:17:.env
```

`instalar.sh` se lanzó desacoplado de la sesión SSH, con registro, para que un
corte no lo matara a medias:

```bash
sudo nohup /opt/adif/deploy/instalar.sh > ~/instalar-1.log 2>&1 < /dev/null &
grep -n "^== \|^   " ~/instalar-1.log     # para seguirlo
```

Tardó unos 6 minutos (casi todo, construir las dos imágenes). Los seis pasos
salieron como estaba previsto, sin tocar nada: Docker 29.9.0, `deploy/.env`
creado con contraseña de base al azar y permisos 600, `/srv/adif/{documentos,
copias,entrada,traspaso}`, imágenes construidas, y como la base estaba vacía
levantó todo **salvo el worker**. `adif.service` quedó habilitado (no
arrancado: arrancarlo con la base vacía levantaría el worker).

Comprobaciones:

```bash
cd /opt/adif/deploy
sudo docker compose -f docker-compose.prod.yml ps -a --format "table {{.Service}}\t{{.State}}\t{{.Status}}\t{{.Ports}}"
sudo ss -tulnp | grep -v 127.0.0
sudo docker compose -f docker-compose.prod.yml logs entrada | grep tls.obtain
```

- `api` (8000/tcp), `web` (3000/tcp) y `postgres` (5432/tcp) solo con el
  puerto interno, sin publicar; el worker igual cuando arranca. En la máquina
  escuchan solo `sshd` en el 22 y `docker-proxy` (Caddy) en el 80 y el 443.
- Caddy obtuvo el certificado de Let's Encrypt en 6 segundos (emisor `YE1`,
  válido del 14/10/2026 al 12/01/2027). El aviso `no OCSP stapling` es normal:
  los certificados de Let's Encrypt ya no traen OCSP.
- Desde fuera:

  ```bash
  curl -sI http://adif-catalogo-ineco.spaincentral.cloudapp.azure.com/catalogo   # 308 -> https://...
  curl -s -o /dev/null -w "%{http_code} %{redirect_url}\n" https://adif-catalogo-ineco.spaincentral.cloudapp.azure.com/   # 307 -> /entrar
  ```

### Servicio de IA

En `deploy/.env` (ignorado por git; se comprobó antes con `git check-ignore`):

```
MODEL_PROVEEDOR=openai
MODEL_ENDPOINT=https://ai-adif-ineco.openai.azure.com/openai/v1
MODEL_ID=vision
MODEL_API_VERSION=
MODEL_API_KEY=<clave del recurso>
```

La clave se escribió pasándola por la entrada estándar del `ssh` y de `sed`,
para que no quedara en ninguna línea de comandos. Prueba mínima desde la
máquina, leyendo la clave del propio `.env`:

```bash
sudo sed -n "s/^MODEL_API_KEY=/api-key: /p" .env | curl -sS -H @- -H "Content-Type: application/json" \
  https://ai-adif-ineco.openai.azure.com/openai/v1/chat/completions \
  -d '{"model":"vision","max_tokens":5,"messages":[{"role":"user","content":"Responde solo: OK"}]}'
```

Respondió 200 con `gpt-4.1-mini-2025-04-14`. Se aplicó con
`sudo docker compose -f docker-compose.prod.yml up -d api`, y la API lo ve:

```bash
sudo docker compose -f docker-compose.prod.yml exec -T api python -c \
  "from app.config import settings; from app.interfaces.model_provider import describir_proveedor_modelo as d; print(d(settings))"
# {'configurado': True, 'proveedor': 'openai', 'modelo': 'vision', 'lee_escaneados_nuevos': True, 'aviso': None}
```

## Bloque 3. Datos

### Copia de la base y de los documentos (en el portátil)

En una carpeta fuera del repositorio, `C:\dev\adif-traspaso`. La base, con el
`pg_dump` **16** del propio contenedor de PostgreSQL y no con el 17 del motor:
el `pg_restore` 16 que usa `restaurar-datos.sh` no sabe leer un volcado de
`pg_dump` 17 (es el desajuste ya visto con las copias automáticas).

```bash
export MSYS_NO_PATHCONV=1        # Git Bash: que no reescriba las rutas del contenedor
mkdir -p /c/dev/adif-traspaso
wsl -e docker exec adif-postgres-1 pg_dump -U adif -d adif -Fc -f /tmp/adif.dump
wsl -e docker cp adif-postgres-1:/tmp/adif.dump /mnt/c/dev/adif-traspaso/adif.dump
wsl -e docker exec adif-postgres-1 sh -c 'pg_restore -l /tmp/adif.dump | head; rm /tmp/adif.dump'
#   Dumped from database version: 16.15 / Dumped by pg_dump version: 16.15
wsl -e sh -c 'docker exec adif-api-1 tar -cf - -C /data/documentos . > /mnt/c/dev/adif-traspaso/documentos.tar
  cd /mnt/c/dev/adif-traspaso && tar -tf documentos.tar | grep -vc "/$" && sha256sum adif.dump documentos.tar > SHA256SUMS'
```

`adif.dump` 45,5 MB, `documentos.tar` 1,99 GB con 1.651 ficheros. Antes se
comprobó que la cola local no tenía trabajos pendientes ni en curso.

### Subida reanudable

Con `rsync` desde WSL (Git Bash no lo trae). WSL no puede usar la clave desde
`/mnt/c` (permisos), así que se copió a su `~/.ssh` con permisos 600 y el
mismo bloque `Host` que en Windows. El script `subir.sh` (en
`C:\dev\adif-traspaso`) repite hasta 50 veces y al final comprueba las sumas
en la máquina:

```sh
cd /mnt/c/dev/adif-traspaso
DEST=adif-catalogo-ineco.spaincentral.cloudapp.azure.com:/srv/adif/traspaso/
i=0
while [ $i -lt 50 ]; do
  i=$((i+1))
  if rsync -t --partial --append-verify --timeout=120 --info=progress2,stats1 adif.dump SHA256SUMS documentos.tar "$DEST"; then
    ssh adif-catalogo-ineco.spaincentral.cloudapp.azure.com 'cd /srv/adif/traspaso && sha256sum -c SHA256SUMS'
    exit $?
  fi
  sleep 15
done
```

```bash
wsl -e sh /mnt/c/dev/adif-traspaso/subir.sh
```

Subió los 2 GB en unos 40 segundos (≈ 55 MB/s), sin cortes; sumas `OK`. Para
comprobar que reanuda de verdad se recortó la copia remota a 900 MB
(`truncate -s 900000000 /srv/adif/traspaso/documentos.tar`) y se volvió a
lanzar: envió solo lo que faltaba (1,09 GB) y las sumas volvieron a dar `OK`.

### Restauración

```bash
cd /opt/adif/deploy && sudo ./restaurar-datos.sh
```

42 segundos, sin errores: 614 expedientes, 40.164 líneas, 1.649 documentos,
esquema 0044, 1.651 ficheros en `/srv/adif/documentos`. Arranca también el
worker; su registro dice `modelo de IA: proveedor openai, modelo vision` y no
encoló nada: el último ciclo semanal del origen es del 14/10 a las 13:46 UTC,
así que el siguiente toca el 21/10, el descubrimiento de pedidos el 19/10, y
la copia diaria el 14/10 hacia las 18:45 UTC.

### Comparación con el origen

Filas de todas las tablas, en las dos máquinas, con la misma consulta:

```sql
SELECT table_name, (xpath('/row/c/text()', query_to_xml('select count(*) as c from public.' || quote_ident(table_name), false, true, '')))[1]::text
FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE' ORDER BY 1;
```

Idénticas en las 22 tablas (expedientes 614, lotes 692, líneas de catálogo
40.164, documentos 1.649, trabajos 34.561...) salvo `usuarios` (2 → 0) y
`registro_accesos` (5 → 0), que `restaurar-datos.sh` vacía a propósito: los
usuarios de desarrollo no viajan a producción. Que los documentos se abren
desde la web se comprobó en el bloque 5, con el navegador.

## Bloque 4. Usuarios

Seis usuarios con nombre provisional (`usuario1` a `usuario6`), para
renombrarlos después con los reales. Las contraseñas temporales se llevaron
directamente a un fichero del portátil, fuera del repositorio
(`%USERPROFILE%\Documents\adif-usuarios-provisionales-2026-10-14.txt`), sin
sacarlas por pantalla:

```bash
F=/c/Users/LUCAS/Documents/adif-usuarios-provisionales-2026-10-14.txt
ssh adif-catalogo-ineco.spaincentral.cloudapp.azure.com 'cd /opt/adif/deploy
  for u in usuario1 usuario2 usuario3 usuario4 usuario5 usuario6; do
    sudo docker compose -f docker-compose.prod.yml exec -T api python -m app.usuarios crear $u |
      sed -n "s/^Usuario «\(.*\)»\. Contraseña temporal: \(.*\)$/\1\t\2/p"
  done' > "$F"
```

Seis contraseñas distintas, de 16 caracteres, todas con cambio obligatorio en
la primera entrada:

```bash
sudo docker compose -f docker-compose.prod.yml exec -T api python -m app.usuarios listar
# usuario1 ... usuario6   activo   última entrada: -  (contraseña temporal pendiente de cambiar)
```

No hay ningún otro usuario: los de desarrollo (`lucas`, `verificacion`) no
llegaron, porque `restaurar-datos.sh` vacía `usuarios`, `sesiones_usuario` y
`registro_accesos`.

Para renombrar no hay orden: se crea el usuario con el nombre real y se
desactiva el provisional (`python -m app.usuarios desactivar usuario1`).
