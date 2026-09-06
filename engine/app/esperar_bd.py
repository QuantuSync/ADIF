"""Arranque resistente (sesión 2026-09-06, tolerancia a reinicios de
`dockerd`): `depends_on: condition: service_healthy` de `docker-compose.yml`
solo lo respeta `docker compose up` — cuando `dockerd` se reinicia por su
cuenta (WSL2, Modo de espera moderno) y restaura los contenedores con
`restart: unless-stopped`, cada uno arranca por separado, sin pasar por el
orquestador de Compose ni por su orden de dependencias. `postgres` puede
tardar unos segundos más en aceptar conexiones (o su nombre puede no
resolver todavía si la red del stack se está recreando) — sin esta espera,
`api`/`worker` fallaban al primer intento (`alembic upgrade head` o la
primera consulta) y dependían de que `restart: unless-stopped` los
reintentara desde cero, con el contenedor entero cayendo y levantándose de
nuevo en vez de reintentar dentro del mismo proceso.

Invocado como `python -m app.esperar_bd` antes de `alembic upgrade head`
(api) y antes de `python -m app.worker` (worker) en `docker-compose.yml`.
"""
from __future__ import annotations

import logging
import sys
import time

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError

from app.db import engine as _engine_por_defecto

logging.basicConfig(level=logging.INFO, format="%(asctime)s esperar_bd %(message)s")
logger = logging.getLogger("esperar_bd")

# 40 intentos x 3s = 2 minutos: generoso frente a los pocos segundos que
# tarda `postgres` en aceptar conexiones tras un reinicio real (medido en
# esta sesión), sin quedarse colgado para siempre si la base de datos está
# genuinamente rota — a partir de ahí, `restart: unless-stopped` sigue
# siendo el último recurso.
INTENTOS_POR_DEFECTO = 40
ESPERA_SEGUNDOS_POR_DEFECTO = 3.0


def esperar_base_datos(
    intentos: int = INTENTOS_POR_DEFECTO,
    espera_segundos: float = ESPERA_SEGUNDOS_POR_DEFECTO,
    motor: Engine | None = None,
) -> bool:
    """Reintenta una conexión mínima (`SELECT 1`) hasta que la base de datos
    responde. `pool_pre_ping=True` en `app.db.engine` no sirve aquí: solo
    revalida conexiones ya abiertas del pool, no ayuda en el primer intento
    cuando el DNS del contenedor `postgres` ni siquiera resuelve todavía.

    `motor` es inyectable para los tests (un motor SQLite en memoria, o uno
    apuntando a un puerto cerrado, no requieren Postgres real); por defecto
    usa el motor real de `app.db`.

    Devuelve `True` en cuanto conecta. Devuelve `False` (nunca lanza) tras
    agotar los intentos -- decidir qué hacer con eso es cosa del llamador."""
    motor = motor if motor is not None else _engine_por_defecto
    for intento in range(1, intentos + 1):
        try:
            with motor.connect() as conexion:
                conexion.execute(text("SELECT 1"))
            if intento > 1:
                logger.info("base de datos alcanzable (intento %d de %d)", intento, intentos)
            return True
        except OperationalError as exc:
            logger.warning(
                "base de datos no alcanzable todavía (intento %d de %d): %s",
                intento, intentos, exc.orig if exc.orig else exc,
            )
            if intento < intentos:
                time.sleep(espera_segundos)
    logger.error("base de datos sigue sin responder tras %d intentos, abandonando", intentos)
    return False


if __name__ == "__main__":
    if not esperar_base_datos():
        sys.exit(1)
