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
