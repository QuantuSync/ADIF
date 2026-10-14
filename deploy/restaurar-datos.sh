#!/usr/bin/env bash
# Restaura en esta máquina la base de datos y los documentos traídos de otra
# (sesión 2026-10-14). Espera en RUTA_DATOS/traspaso (/srv/adif/traspaso):
#
#   adif.dump        volcado de la base (pg_dump -Fc, hecho con el pg_dump del
#                    propio contenedor de PostgreSQL 16; ver la guía)
#   documentos.tar   la carpeta de documentos descargados, empaquetada
#
# Sustituye lo que haya en la base y añade los documentos. Los usuarios, las
# sesiones y el registro de accesos de la máquina de origen se vacían: los de
# producción se crean aquí, con `python -m app.usuarios crear`.
#
# Uso: sudo ./restaurar-datos.sh
set -euo pipefail

cd "$(dirname "$0")"
COMPOSE=(docker compose -f docker-compose.prod.yml)
# shellcheck disable=SC1091
set -a; . ./.env; set +a
DATOS="${RUTA_DATOS:-/srv/adif}"
VOLCADO="$DATOS/traspaso/adif.dump"
DOCUMENTOS="$DATOS/traspaso/documentos.tar"

for f in "$VOLCADO" "$DOCUMENTOS"; do
  [ -f "$f" ] || { echo "Falta $f" >&2; exit 1; }
done

echo "== Parando todo menos la base de datos"
"${COMPOSE[@]}" stop entrada web worker api
"${COMPOSE[@]}" up -d postgres
for intento in $(seq 1 60); do
  "${COMPOSE[@]}" exec -T postgres pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" >/dev/null 2>&1 && break
  [ "$intento" = 60 ] && { echo "PostgreSQL no responde." >&2; exit 1; }
  sleep 2
done

echo "== Restaurando la base ($(du -h "$VOLCADO" | cut -f1))"
# --clean --if-exists: sustituye lo que creó el primer arranque (esquema vacío).
"${COMPOSE[@]}" exec -T postgres pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  --clean --if-exists --no-owner --exit-on-error /traspaso/adif.dump
"${COMPOSE[@]}" exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -c \
  "TRUNCATE sesiones_usuario, registro_accesos, usuarios RESTART IDENTITY CASCADE;"

echo "== Restaurando los documentos ($(du -h "$DOCUMENTOS" | cut -f1))"
mkdir -p "$DATOS/documentos"
tar -xf "$DOCUMENTOS" -C "$DATOS/documentos"

echo "== Arrancando todo"
"${COMPOSE[@]}" up -d

"${COMPOSE[@]}" exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -c \
  "SELECT 'expedientes: ' || count(*) FROM expedientes UNION ALL
   SELECT 'líneas de catálogo: ' || count(*) FROM lineas_catalogo UNION ALL
   SELECT 'documentos: ' || count(*) FROM documentos UNION ALL
   SELECT 'versión del esquema: ' || version_num FROM alembic_version;"
echo "ficheros en $DATOS/documentos: $(find "$DATOS/documentos" -type f | wc -l)"
echo
echo "Hecho. Crea los usuarios con:"
echo "  cd $(pwd) && sudo docker compose -f docker-compose.prod.yml exec api python -m app.usuarios crear <usuario>"
