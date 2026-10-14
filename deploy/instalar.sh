#!/usr/bin/env bash
# Deja el sistema instalado y levantado en una máquina Ubuntu 24.04 recién
# creada (sesión 2026-10-14). Se ejecuta desde una copia del repositorio en la
# propia máquina:
#
#   sudo git clone <repositorio> /opt/adif
#   sudo /opt/adif/deploy/instalar.sh
#
# Se puede repetir sin miedo: lo que ya está hecho, lo deja como está, y al
# final reconstruye y levanta con el código que haya en /opt/adif (también
# sirve para actualizar tras un `git pull`).
#
# Si en RUTA_DATOS/traspaso están adif.dump y documentos.tar y la base todavía
# no tiene expedientes, los restaura (restaurar-datos.sh). Si no, levanta todo
# salvo el worker: con la base vacía, su primer ciclo de mantenimiento se
# pondría a descargar la Plataforma entera desde cero.
set -euo pipefail

[ "$(id -u)" -eq 0 ] || { echo "Ejecuta con sudo." >&2; exit 1; }
DEPLOY="$(cd "$(dirname "$0")" && pwd)"
REPO="$(dirname "$DEPLOY")"
cd "$DEPLOY"

. /etc/os-release
if [ "${VERSION_ID:-}" != "24.04" ]; then
  echo "Aviso: pensado para Ubuntu 24.04 y esto es ${PRETTY_NAME:-desconocido}. Sigo." >&2
fi

echo "== 1/6 Paquetes del sistema y actualizaciones de seguridad automáticas"
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q ca-certificates curl git openssl unattended-upgrades
dpkg-reconfigure -f noninteractive unattended-upgrades

echo "== 2/6 Docker (repositorio oficial)"
if ! command -v docker >/dev/null 2>&1; then
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -q
  apt-get install -y -q docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
# Registros de los contenedores acotados: sin esto crecen sin límite.
if [ ! -f /etc/docker/daemon.json ]; then
  cat > /etc/docker/daemon.json <<'JSON'
{ "log-driver": "json-file", "log-opts": { "max-size": "20m", "max-file": "5" } }
JSON
  systemctl restart docker
fi
systemctl enable --now docker

echo "== 3/6 Configuración (deploy/.env)"
if [ ! -f .env ]; then
  cp env.produccion.ejemplo .env
  echo "   creado deploy/.env a partir del ejemplo"
fi
if grep -q '^POSTGRES_PASSWORD=CAMBIAR$' .env; then
  sed -i "s/^POSTGRES_PASSWORD=CAMBIAR$/POSTGRES_PASSWORD=$(openssl rand -hex 24)/" .env
  echo "   contraseña de la base generada al azar"
fi
chmod 600 .env
set -a; . ./.env; set +a
: "${DOMINIO:?Falta DOMINIO en deploy/.env}"
DATOS="${RUTA_DATOS:-/srv/adif}"

echo "== 4/6 Carpetas de datos en $DATOS"
mkdir -p "$DATOS"/{documentos,copias,entrada,traspaso}
chmod 700 "$DATOS/copias"
# Quien ejecuta el script con sudo puede dejar ahí los ficheros por scp.
if [ -n "${SUDO_USER:-}" ]; then chown "$SUDO_USER" "$DATOS/traspaso"; fi

echo "== 5/6 Construyendo y levantando (la primera vez tarda varios minutos)"
COMPOSE=(docker compose -f docker-compose.prod.yml)
"${COMPOSE[@]}" build
"${COMPOSE[@]}" up -d postgres api web entrada
# La API migra la base al arrancar; si no responde en 5 minutos, algo ha ido
# mal y se enseña por qué en vez de esperar para siempre.
for intento in $(seq 1 100); do
  if "${COMPOSE[@]}" exec -T api python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" >/dev/null 2>&1; then
    break
  fi
  if [ "$intento" = 100 ]; then
    echo "La API no arranca. Últimas líneas de su registro:" >&2
    "${COMPOSE[@]}" logs --tail 40 api >&2
    exit 1
  fi
  sleep 3
done
EXPEDIENTES=$("${COMPOSE[@]}" exec -T postgres psql -U "${POSTGRES_USER:-adif}" -d "${POSTGRES_DB:-adif}" -At -c "SELECT count(*) FROM expedientes")
if [ "$EXPEDIENTES" = "0" ] && [ -f "$DATOS/traspaso/adif.dump" ] && [ -f "$DATOS/traspaso/documentos.tar" ]; then
  echo "   base vacía y datos en $DATOS/traspaso: restaurando"
  "$DEPLOY/restaurar-datos.sh"
elif [ "$EXPEDIENTES" = "0" ]; then
  echo "   base vacía y sin datos que restaurar: el worker se queda parado hasta traerlos"
  echo "   (deja adif.dump y documentos.tar en $DATOS/traspaso y ejecuta deploy/restaurar-datos.sh)"
else
  "${COMPOSE[@]}" up -d
fi

echo "== 6/6 Arranque automático al reiniciar la máquina"
sed "s|@DEPLOY@|$DEPLOY|g" adif.service > /etc/systemd/system/adif.service
systemctl daemon-reload
systemctl enable adif.service >/dev/null

echo
"${COMPOSE[@]}" ps --format "table {{.Service}}\t{{.State}}\t{{.Status}}"
echo
echo "Listo: https://$DOMINIO"
echo "Usuarios: cd $DEPLOY && sudo docker compose -f docker-compose.prod.yml exec api python -m app.usuarios crear <usuario>"
echo "Guía: $REPO/docs/guia-de-operacion.md"
