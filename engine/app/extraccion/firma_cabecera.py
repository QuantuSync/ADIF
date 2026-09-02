"""Firma estable de una cabecera de tabla (CLAUDE.md sección 6): la clave con
la que se indexa la caché persistente de mapeos, para que la misma cabecera
—vista en cualquier página, documento o expediente— nunca dispare una
segunda llamada al modelo."""
from __future__ import annotations

import hashlib

from app.extraccion.texto import normalizar


def calcular_firma_cabecera(cabecera: list[str | None]) -> str:
    normalizada = "|".join(normalizar(celda) if celda else "" for celda in cabecera)
    return hashlib.sha256(normalizada.encode("utf-8")).hexdigest()
