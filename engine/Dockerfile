FROM python:3.12-slim

WORKDIR /app
ENV PYTHONPATH=/app

# `pg_dump`/`pg_restore` para las copias de seguridad automáticas
# (`app.mantenimiento.copia_seguridad`, sesión 2026-09-06): la versión de
# Debian es más nueva que el servidor (`postgres:16-alpine`) -- dirección
# de compatibilidad soportada por PostgreSQL (un cliente más nuevo sabe
# volcar/restaurar un servidor más antiguo, no al revés).
RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && playwright install --with-deps chromium

COPY . .

EXPOSE 8000
