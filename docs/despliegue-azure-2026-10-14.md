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

La clave se pasó por la entrada estándar del `ssh`, para que no quedara en
ninguna línea de comandos del portátil ni en el historial; en la máquina, el
`sed` que la escribe en `.env` la lleva un instante en sus argumentos. Prueba mínima desde la
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

## Bloque 5. Comprobación

Todo con un navegador real (Chromium de Playwright, desde el portátil) contra
`https://adif-catalogo-ineco.spaincentral.cloudapp.azure.com`, nunca contra
`localhost`.

### Acceso

- Cualquier página sin sesión (`/`, `/catalogo`, `/revision`,
  `/mantenimiento`, una inventada) responde 307 a `/entrar?siguiente=...`. Lo
  primero que se ve es la pantalla de entrada (el único error de consola es
  que falta `favicon.ico`).
- `usuario1` con su contraseña temporal lleva a `/cambiar-contrasena`. Desde
  ahí, ir a `/catalogo` devuelve al cambio, y la API contesta 403
  `cambio_contrasena_obligatorio`. Cambiada la contraseña, entra.
- Rutas de la API sin sesión: se sacó la lista completa del propio contenedor
  (`app.main.app.routes`, 57 rutas) y se llamó a cada una por el dominio
  público sin cookie. 54 dan 401; las otras tres son las que deben ir
  abiertas y no dan datos: `GET /health` (`{"status":"ok"}`),
  `POST /auth/entrar` (422 sin usuario) y `POST /auth/salir`.
  `/api/openapi.json`, `/api/docs` y `/api/redoc` dan 404.

### Catálogo y Excel

El catálogo se ve: 40.164 líneas, 1.607 páginas. El Excel, pulsando
«Exportar Excel»:

| Prueba | Tiempo hasta tener el fichero | Resultado |
|---|---:|---|
| Un usuario solo, con los límites nuevos de Caddy | **234 s** | Completo |
| Dos usuarios a la vez (`usuario1` y `usuario2`, sesiones distintas) | **327 s** cada uno | Los dos completos |

Cada fichero se comprobó entero, no solo el 200: zip íntegro, y celda a celda
**idéntico** al que genera `generar_excel_catalogo` sobre la base del
portátil. Materiales 19.352 filas (19.351 de datos más la cabecera),
Conciliación 539, Contraste de presupuestos 514, Resumen 73.

Durante las dos exportaciones a la vez se vigiló la API cada 8 s: 100 % de un
núcleo (es un solo proceso), memoria de 700 a 854 MB, `healthy`, 0
reinicios, y `/api/health` siguió contestando por el dominio en menos de
0,25 s.

**Límites de tiempo.** La exportación tarda varios minutos y no manda nada
hasta el final. Ni Caddy 2.8 (sin límite en `reverse_proxy` ni en `write`) ni
uvicorn la cortan, así que no cortaban nada. Aun así se dejaron escritos a 10
minutos en `deploy/Caddyfile` (`servers { timeouts { write 10m; idle 10m } }`
y `transport http { response_header_timeout 10m; read_timeout 10m }`). Las
versiones posteriores de Caddy añaden `write_idle`, de 1 minuto por defecto,
que la 2.8.4 no reconoce: está anotado en el propio fichero. Se llevó a la
máquina escribiendo **sobre el mismo fichero**, porque está montado suelto en
el contenedor y uno nuevo no lo vería:

```bash
ssh adif-catalogo-ineco.spaincentral.cloudapp.azure.com 'sudo tee /opt/adif/deploy/Caddyfile > /dev/null' < deploy/Caddyfile
sudo docker compose -f docker-compose.prod.yml exec -T entrada caddy validate --config /etc/caddy/Caddyfile
sudo docker compose -f docker-compose.prod.yml restart entrada
```

No se tocó nada más de la arquitectura (ni varios procesos de API ni
rendimiento). Lo que queda: con 4 o más exportaciones a la vez se llegaría a
los 10 minutos, y Firefox deja de esperar a los 5 minutos por su cuenta.

### Documentos

Desde el panel de una línea del catálogo, «Origen documental» abre el PDF en
una pestaña nueva (`/api/documentos/<id>/archivo`, `application/pdf`,
`inline`). Se comprobaron tres (1623, 1515 y 1468, de 0,26 a 12,8 MB): mismo
tamaño y misma SHA-256 que los ficheros de `/srv/adif/documentos`.

### Mantenimiento y servicio de IA

La pantalla dice «Modelo de IA para escaneados y cabeceras nuevas: openai ·
vision», sin aviso. Ciclo cada 7 días, el siguiente el 21/10/2026 a las
15:46 (hora peninsular). No se pulsó «Lanzar ciclo ahora».

### Móvil y escritorio

`/catalogo`, `/mantenimiento` y `/revision` cargan bien a 360×800, 390×844,
412×915 y 1366×900. En móvil, Mantenimiento (815 px) y la cola de revisión
(502 px) se salen de ancho, igual que en local con el mismo código. No es del
despliegue y no se tocó.

### Reinicio de la máquina

```bash
sudo systemctl reboot
```

Volvió en unos 20 segundos sin hacer nada. Docker y `adif.service` activos
(`up -d` con código 0) y los cinco contenedores arriba, con la API `healthy`.
http sigue redirigiendo a https. Caddy usó el certificado guardado (mismo
número de serie, una sola emisión en todo su registro). El worker volvió con
`modelo de IA: proveedor openai, modelo vision`. La sesión abierta del
navegador siguió valiendo, porque las sesiones están en la base.

Copias diarias tras el reinicio: el programador las tenía activas, cada
86.400 s, la próxima a las 18:45 UTC. Para no esperar se forzó una por la API
con la sesión de `usuario1`
(`POST /api/mantenimiento/copias/ejecutar`): `adif_20261014_165628.dump`,
45,6 MB, hecha por `pg_dump` 17.11 contra el servidor 16.15, y el
`pg_restore` del motor la lee entera (22 tablas con datos). La siguiente
automática queda 24 horas después de esa. La guía decía que había un botón
para esto en Mantenimiento y no lo hay; corregido.

### Reextracción de `6.26/28510.0066` (la única)

Era la única extracción fallida desde el 22/09. El ciclo del 14/10 en el
portátil (13:46 UTC, antes de esta sesión) la dejó con 0 líneas: `ANEJO_1.pdf`
dio `401 invalid x-api-key` con la clave antigua. Se lanzó en la máquina solo
la extracción (sin volver a descargar), con la sesión de `usuario1`, como el
botón de la web:

```js
fetch('/api/expedientes/624/extraer', {method: 'POST', credentials: 'include'})   // trabajo 34777
```

Resultado en 4 s de trabajo: **22 líneas nuevas**, todas con lote y en
`sin_revisar`. El expediente queda en `pendiente_revision` por «no se pudo
determinar la baja de ningún lote» (aún sin adjudicación; es un aviso, no un
fallo de lectura). **2 llamadas al servicio de Azure, las dos `200 OK`** (503
y 423 tokens de entrada, 32 de salida, fin `stop`), para traducir dos
cabeceras nunca vistas, que quedaron en caché.

`ANEJO_1.pdf` **no es escaneado** (`aviso_documento_escaneado: null`), así
que esta extracción no probó la lectura de imágenes. Para probarla sin
reprocesar nada, un script de solo lectura (`prueba_vision.py`, copiado en el
worker y borrado después) leyó con `_rasterizar` y `_leer_pagina` de
`app.extraccion.ocr` la página 1, sin capa de texto, de un escaneado ya leído
(`6.18_28510.0071/ADJUDICACION_f35b04b217a64bad.pdf`), sin escribir en la
base. `vision` la leyó en 11 s (1.681 tokens de entrada, 785 de salida, sin
error), con un 89,6 % de parecido con la lectura guardada de
`claude-haiku-4-5`.

### Al terminar

- `usuario1` y `usuario2`, usados en las pruebas, se reiniciaron
  (`python -m app.usuarios reiniciar`): contraseña temporal nueva, cambio
  obligatorio y sesiones cerradas. El fichero del portátil está al día. Los
  seis quedan sin estrenar.
- Borrado `/srv/adif/traspaso/*` y los ficheros de prueba de `/tmp`.
- Después se recogió todo lo que había quedado fuera del repositorio. Lo que
  sigue sirviendo está en `privado/`, que `.gitignore` excluye: el script de
  subida (`privado/traspaso/subir.sh`, ya con la ruta nueva) y la lista de
  usuarios. Se borraron `C:\dev\adif-traspaso` entero (el volcado y el
  paquete de documentos ya no son la referencia, y los Excel de prueba eran
  copias idénticas), la copia de la clave en el `~/.ssh` de WSL y los
  temporales de las pruebas en los contenedores locales. Para repetir una
  subida: `wsl -e sh -c 'mkdir -p ~/.ssh && cp /mnt/c/Users/LUCAS/.ssh/id_ed25519_adif ~/.ssh/ && chmod 600 ~/.ssh/id_ed25519_adif'`,
  más el bloque `Host` del bloque 1 en `~/.ssh/config` de WSL.
- `az` (instalado con winget) no llegó a iniciar sesión: la cuenta entró en
  su directorio por defecto, sin suscripciones, y el código de dispositivo
  contra el directorio de la suscripción (`83cd3889-...`) caducó sin
  usarse. No hizo falta para nada.

## Diferencia con el Excel entregado el 22/09

El 22/09: 19.333 filas en Materiales (sin contar la cabecera) y 40.133 líneas
en la base. Antes de la reextracción de `0066`: 19.351 y 40.164, es decir,
**18 filas** (no 19: el 19.352 cuenta la cabecera) y **31 líneas** más. Se
compararon fila a fila los dos Excel
(`catalogo_adif_2026-09-22-reconstruccion-identica-a-produccion.xlsx` y el de
hoy) y la base. Todo viene de los ciclos semanales del 30/09, del 07/10 y del
14/10:

| Expediente | Excel 22/09 → hoy | Líneas en la base | Qué pasó |
|---|---|---|---|
| `6.26/28510.0105` | 0 → 13 | 0 → 13 | Expediente nuevo (ciclo del 30/09), extracción `completado` |
| `6.25/28510.0221` | 13 → 18 | 13 → 31 | Reextraído el 30/09 (23 creadas, 8 actualizadas, 5 podadas): cantidades nuevas y filas que pasan del lote 2 al 1. 13 de las 31 quedan sin lote y van a «Resumen», no a Materiales, como todas las huérfanas |
| `6.26/28510.0030` | 29 → 29 | 29 | Mismo número; llega la adjudicación (ciclo del 14/10): precio adjudicado y baja |
| `6.24/28510.0188` | 2 → 2 | 2 | Igual; adjudicación en el ciclo del 07/10 |
| **Total** | **+18** | **+31** | |

Completitud: de las 17 extracciones lanzadas desde el 22/09, la única con un
error de verdad es la de `6.26/28510.0066` (arriba). Las demás que salen
buscando «no se pudo» son avisos normales por fila («valor que no se pudo
interpretar, marcadas para revisión», «no se pudo determinar la baja»).
Ninguna extracción quedó `fallido`; los 109 trabajos fallidos desde el 22/09
son todos descargas «no encontrado en la Plataforma ni por matriz ni por
expediente» (92 expedientes que se reintentan cada ciclo). `19/28510`, nuevo
del 30/09, está sin líneas a propósito: el documento descargado como
adjudicación no lo menciona.

Con la reextracción de `0066`, la base de la máquina tiene 22 líneas más que
la del portátil: 40.186.

## Usuarios definitivos

Por indicación del cliente se llaman `NOMBRE1` a `NOMBRE6`. Se crearon antes
de borrar los provisionales, para que la plataforma no se quedara sin
usuarios en ningún momento. Las contraseñas temporales van directamente a
`privado/usuarios-2026-10-14.txt` (se comprobó antes con `git check-ignore`
que la carpeta está ignorada); son seis distintas y todas con cambio
obligatorio. `app.usuarios` no tiene orden para borrar, así que `usuario1` a
`usuario6` se borraron con SQL, en una transacción que se deshacía si no eran
exactamente seis. Sus sesiones se borran en cascada y el registro de accesos
se conserva con `usuario_id` a nulo:

```sql
BEGIN;
DO $$ DECLARE n int; BEGIN
  DELETE FROM usuarios WHERE nombre IN ('usuario1','usuario2','usuario3','usuario4','usuario5','usuario6');
  GET DIAGNOSTICS n = ROW_COUNT;
  IF n <> 6 THEN RAISE EXCEPTION 'se iban a borrar % usuarios, no 6', n; END IF;
END $$;
COMMIT;
```

Quedan seis usuarios, los seis `NOMBRE`, y ninguna sesión. Con el navegador,
contra el dominio: `usuario1` ya no entra (401) y `NOMBRE1` entra y la web lo
lleva a «Cambiar contraseña». Desde ahí no deja ir al catálogo y la API
responde 403 `cambio_contrasena_obligatorio`. No se le cambió la contraseña
(sigue sin estrenar) y se cerró la sesión. La lista provisional se borró.

## Cambio de modelo: gpt-4.1

El cliente cambió en Azure el modelo del despliegue `vision`, de
`gpt-4.1-mini` a `gpt-4.1`. El nombre del despliegue y la dirección son los
mismos, así que `deploy/.env` no cambió (`MODEL_ID=vision`, `MODEL_ENDPOINT`
igual) y no hubo que reiniciar nada. La llamada mínima del bloque 2 responde
200 con `"model": "gpt-4.1-2025-04-14"`. El worker sigue viendo
`configurado: True, proveedor openai, modelo vision, lee_escaneados_nuevos:
True`.

La prueba de lectura de escaneado se repitió con el mismo script de solo
lectura y la misma página (página 1, sin capa de texto, de
`6.18_28510.0071/ADJUDICACION_f35b04b217a64bad.pdf`). La base, igual antes que
después: 140 lecturas en caché (la última del 19/09), 40.186 líneas y 34.563
trabajos.

| Modelo | Tiempo | Tokens (entrada / salida) | Caracteres | Coincidencia con la lectura guardada (`claude-haiku-4-5`) |
|---|---:|---:|---:|---:|
| `gpt-4.1-mini` (antes) | 11 s | 1.681 / 785 | 1.922 | 0,896 |
| `gpt-4.1`, intento 1 | 12,5 s | 1.425 / 776 | 1.915 | 0,880 |
| `gpt-4.1`, intento 2 | 15,0 s | 1.425 / 855 | 1.943 | 0,889 |

La coincidencia es `difflib.SequenceMatcher` sobre el texto entero, así que
mide sobre todo el orden y la maquetación de los bloques, no aciertos de
lectura: los tres están en el mismo orden de magnitud. **Primer intento
fallido:** justo después del cambio, la primera llamada con imagen dio
`400 Bad Request` (las de solo texto ya iban). Repetida la misma llamada del
motor minutos después para ver el cuerpo del error, ya no dio error, y las
dos pruebas siguientes fueron bien. No se tocó código.

Pantalla de Mantenimiento, con un usuario temporal (`verificacion-temporal`,
creado para esto y borrado después con SQL, en una transacción que exigía
borrar exactamente uno): «Modelo de IA para escaneados y cabeceras nuevas:
openai · vision», sin aviso del modelo. Los «7 aviso(s)» de la pantalla son
los de la auditoría automática del catálogo, los mismos de antes.

En el registro de accesos consta que `NOMBRE1` entró a las 17:38:37 UTC y
cambió su contraseña a las 17:40:03, desde 91.116.111.191. No fue durante
estas pruebas (la mía con `NOMBRE1` fue a las 17:28:15, entrada y salida sin
cambio): fue el cliente, probando. Después se reinició
(`python -m app.usuarios reiniciar NOMBRE1`): contraseña temporal nueva en
`privado/`, cambio obligatorio y sesión cerrada. Los seis quedan sin
estrenar.

## Dos perfiles y usuarios definitivos (16/10/2026)

Cambio de alcance del cliente: perfil `escritura` (lo de antes, puede todo)
y perfil `consulta` (ve todas las pantallas y exporta, nada más). Código en
los commits `15f7cae` (API, migración 0045 y pruebas), `daf8f45` y `9cad46e`
(web) y `191fe0f` (guía y CONTEXTO.md); detalle en la guía de operación,
apartado Usuarios.

### Despliegue

Antes de tocar nada: cola sin trabajos pendientes ni en curso, copia
manual de la base con el `pg_dump` del worker
(`/srv/adif/copias/antes_perfiles_20261016.dump`, 45,6 MB; no la borra la
rotación automática, que solo mira los que empiezan por `adif`) y recuento de filas de
todas las tablas con la consulta del bloque 3. Después
`git pull && instalar.sh` (dos veces, la segunda por el arreglo de la barra
de arriba). `deploy/Caddyfile` no cambió, así que `entrada` no se reinició.

Tras el primero, las 22 tablas con las mismas filas que antes (40.186
líneas, 614 expedientes, 34.564 trabajos...), esquema `0045`, y los seis
usuarios que había, con perfil `escritura` como manda la migración. El
worker volvió con `modelo de IA: proveedor openai, modelo vision`.

### Usuarios

Creados antes de borrar los anteriores, con `crear <usuario> --perfil ...`,
y las contraseñas llevadas directamente a `privado/usuarios-2026-10-16.txt`
(ignorado por git, comprobado con `git check-ignore`), con el perfil al lado,
sin pasar por pantalla. Once contraseñas distintas de 16 caracteres, todas
con cambio obligatorio.

- Consulta y escritura: `isabel.ibanez`, `raul.talens`.
- Consulta: `antonio.conde`, `nuria.gomez`, `juan.merino`,
  `mercedes.molinero`, `manuel.fraga`, `ignacio.aroca`, `margarita.vaquero`,
  `carla.duque`, `d.redondo`.

Los seis `NOMBRE` se borraron con SQL en una transacción que exigía borrar
exactamente seis, como los provisionales. `NOMBRE1` lo había estrenado el
cliente el 15/10; el registro de accesos se conserva. Ninguna sesión abierta
al terminar. Se borró `privado/usuarios-2026-10-14.txt`.

### Comprobación contra el dominio

Con dos usuarios temporales, `verif-consulta` y `verif-escritura`, creados
con la consola y borrados al final con SQL (transacción que exigía borrar
exactamente dos). Con Chromium de Playwright desde el portátil:

- Los dos pasan por el cambio de contraseña obligatorio y `/api/auth/sesion`
  devuelve su perfil.
- Con la sesión de consulta, la lista de rutas sacada del propio contenedor
  (`app.main.app.routes`, sin `/auth` ni `/health`, con identificadores
  inventados): las **27 que escriben responden 403 `solo_consulta`**; de las
  de lectura, 19 dan 200 y 4 dan 404 (el identificador inventado). Los dos
  Excel no se llamaron así, por lo que tardan.
- En las siete pantallas, consulta no ve ningún botón que escriba y la barra
  dice «solo consulta» bajo el nombre; escritura ve los de siempre
  (Añadir expediente, Descargar, Extraer, Confirmar tal cual, Guardar
  corrección y confirmar, los cuatro de cada línea, Recalcular candidatos,
  Aceptar, Ninguno es correcto, Dejar nota, Lanzar ciclo ahora y Ejecutar
  ahora). En la cola de revisión, consulta ve la tabla de líneas con 7
  columnas (sin la de botones) y escritura con 8.
- Exportación del Excel con el usuario de consulta, pulsando «Exportar
  Excel» en el catálogo: fichero completo (zip íntegro), Materiales 19.374 filas con la cabecera, Conciliación 539, Contraste de presupuestos 515 y Resumen 73. Respecto al 14/10 son 22 filas más en Materiales y un lote más en Contraste, lo que cuadra con las 22 líneas de `6.26/28510.0066` reextraídas aquel día. No se cronometró con precisión (unos 4 minutos). Al terminar, la cola seguía con 34.564 trabajos y la base con 40.186 líneas: ninguna de las pruebas escribió nada.

No se pulsó ningún botón que escriba con el usuario de escritura.

### Lo que se vio de paso

La primera versión ponía «· solo consulta» a la derecha del nombre y la
barra de arriba se desbordaba a 1366 px (Contraseña y Salir cortados). Ahora
va debajo del nombre y no ensancha nada. Quedaba el desbordamiento de antes,
a 1280 px con cualquier perfil y a 1366 px con nombres largos; arreglado el
mismo día (apartado siguiente).

### Barra de arriba en dos filas (commit `246c15a`)

Por debajo de 1700 px la barra pasa a dos filas: arriba la marca (con su
subtítulo) y el bloque de usuario (nombre, Contraseña y Salir), debajo los
siete apartados. No se ha quitado ni escondido ninguna opción. La barra mide
92 px en vez de 64; `--nav-h` cambia con ella, así que las cabeceras fijas
de las tablas se siguen pegando justo debajo (medido, 0 px de hueco). Desde
1700 px sigue en una fila. En móvil, la fila de apartados se desliza de lado
sola, sin arrastrar la página.

Comprobado en local y en la máquina, contra el dominio, con usuarios de 17
caracteres (el largo de `margarita.vaquero` y `mercedes.molinero`, los más
largos; el nombre va en letra de ancho fijo) de los dos perfiles, creados y
borrados para esto: a 1280, 1366 y 1920 px la barra no desborda, marca,
nombre, Contraseña y Salir quedan dentro de la ventana y los siete apartados
caben; a 360, 390 y 412 px, el bloque de usuario cabe y «Salir» queda a 16 px
del borde.

Sin cambios, porque no tienen que ver con la barra: la tabla de Expedientes
con la columna Acciones (perfil de escritura) se pasa 14 px a 1280 px; el
catálogo se desplaza de lado en escritorio por el ancho de su tabla, como
siempre; y en móvil Mantenimiento (815 px) y la cola de revisión (502 px)
se siguen saliendo de ancho igual que el 14/10.
