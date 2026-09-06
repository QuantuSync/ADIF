"""Copias de seguridad automáticas (CONTEXTO.md, bloque de copias de
seguridad, sesión 2026-09-06): antes no había ninguna copia periódica, solo
volcados puntuales hechos a mano antes de cada limpieza -- con un entorno
que se reinicia solo varias veces al día
(`docs/diagnostico-caidas-dockerd.md`), perder el volumen de la base de
datos se llevaría por delante los expedientes procesados y el catálogo
entero sin ningún respaldo.

Mismo patrón que `app.mantenimiento.ciclo`: un tipo de trabajo más de la
cola (CONTEXTO.md sección 10, "no un script suelto"), lanzado desde el
propio bucle del worker (`app.mantenimiento.programacion`) -- ningún quinto
proceso, ningún cron del sistema operativo.

Formato `pg_dump --format=custom` (`.dump`): comprimido de por sí, y
restaurable con `pg_restore` sin depender de que el volcado en texto plano
cuadre carácter a carácter -- el formato que PostgreSQL recomienda para
copias que se van a restaurar, no solo a inspeccionar. `postgresql-client`
(paquete instalado en `engine/Dockerfile`) trae `pg_dump`/`pg_restore` en
una versión más nueva que el servidor (`postgres:16-alpine`) -- la
dirección de compatibilidad que sí está soportada: un cliente más nuevo
sabe volcar un servidor más antiguo, no al revés.

Guardadas en `settings.backup_dir`, un volumen de Docker propio
(`docker-compose.yml`, `copias_seguridad_bd`) distinto del de PostgreSQL
(`postgres_data`) -- para que perder el volumen de datos no se lleve las
copias por delante. Procedimiento de restauración documentado y probado en
`README.md`.
"""
from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlsplit

from app.config import settings

logger = logging.getLogger("mantenimiento.copia_seguridad")

TIPO_TRABAJO = "copia_seguridad"

_PREFIJO_ARCHIVO = "adif"
_SUFIJO_ARCHIVO = ".dump"


@dataclass
class ParametrosConexion:
    host: str
    port: str
    user: str
    password: str
    dbname: str


def parametros_desde_url(url: str) -> ParametrosConexion:
    """`settings.database_url` viene en formato SQLAlchemy
    (`postgresql+psycopg://usuario:clave@host:puerto/base`), que `pg_dump`
    no entiende como argumento directo -- se parte a mano y se pasa como
    variables de entorno estándar de libpq (`PGHOST`, `PGPORT`...), que sí
    entienden tanto `pg_dump` como `pg_restore`."""
    partes = urlsplit(url)
    return ParametrosConexion(
        host=partes.hostname or "postgres",
        port=str(partes.port or 5432),
        user=partes.username or "adif",
        password=partes.password or "",
        dbname=(partes.path or "").lstrip("/") or "adif",
    )


def entorno_pg(parametros: ParametrosConexion) -> dict:
    entorno = os.environ.copy()
    entorno["PGHOST"] = parametros.host
    entorno["PGPORT"] = parametros.port
    entorno["PGUSER"] = parametros.user
    entorno["PGPASSWORD"] = parametros.password
    return entorno


def nombre_archivo(momento: Optional[datetime] = None) -> str:
    momento = momento or datetime.now(timezone.utc)
    return f"{_PREFIJO_ARCHIVO}_{momento.strftime('%Y%m%d_%H%M%S')}{_SUFIJO_ARCHIVO}"


def listar_copias(directorio: Optional[str] = None) -> list[Path]:
    """Más recientes primero -- el propio nombre de archivo ya es ordenable
    cronológicamente (timestamp `AAAAMMDD_HHMMSS`), sin necesidad de mirar
    la fecha de modificación del fichero."""
    ruta = Path(directorio if directorio is not None else settings.backup_dir)
    if not ruta.is_dir():
        return []
    return sorted(
        (
            p
            for p in ruta.iterdir()
            if p.is_file() and p.name.startswith(_PREFIJO_ARCHIVO) and p.suffix == _SUFIJO_ARCHIVO
        ),
        reverse=True,
    )


def purgar_copias_antiguas(retencion: Optional[int] = None, directorio: Optional[str] = None) -> list[str]:
    """Conserva las `retencion` copias más recientes (por defecto
    `settings.backup_retencion`) y borra el resto -- sin esto, una copia
    diaria sin límite acaba llenando el disco. Devuelve los nombres
    borrados, para que quede en el resultado del trabajo (trazabilidad)."""
    retencion = retencion if retencion is not None else settings.backup_retencion
    copias = listar_copias(directorio)
    sobrantes = copias[retencion:] if retencion > 0 else copias
    borrados = []
    for copia in sobrantes:
        copia.unlink(missing_ok=True)
        borrados.append(copia.name)
    return borrados


def ejecutar_copia_seguridad(db, trabajo) -> dict:
    """Manejador de la cola (`app.queue.ejecutar_trabajo`): vuelca la base
    de datos completa con `pg_dump --format=custom` a `settings.backup_dir`
    y purga las copias que sobren según la retención configurada.

    `db` no se usa para nada (el volcado va directo contra el servidor por
    `pg_dump`, no a través de la sesión de SQLAlchemy) -- se recibe igual
    que el resto de manejadores porque `app.queue.ejecutar_trabajo` los
    llama a todos con la misma firma `(db, trabajo)`."""
    directorio = Path(settings.backup_dir)
    directorio.mkdir(parents=True, exist_ok=True)
    archivo = directorio / nombre_archivo()
    parametros = parametros_desde_url(settings.database_url)

    resultado = subprocess.run(
        [
            "pg_dump",
            "--format=custom",
            "--no-owner",
            "--dbname", parametros.dbname,
            "--file", str(archivo),
        ],
        env=entorno_pg(parametros),
        capture_output=True,
        text=True,
        timeout=settings.backup_timeout_segundos,
    )
    if resultado.returncode != 0:
        # Sin dejar un `.dump` a medias que `listar_copias` confundiría con
        # una copia real -- `pg_dump` puede haber escrito parte del fichero
        # antes de fallar (disco lleno, conexión cortada a mitad).
        archivo.unlink(missing_ok=True)
        raise RuntimeError(f"pg_dump falló (código {resultado.returncode}): {resultado.stderr.strip()}")

    tamano_bytes = archivo.stat().st_size
    eliminadas = purgar_copias_antiguas()
    logger.info(
        "copia de seguridad creada: %s (%s bytes), %s copia(s) antigua(s) purgada(s)",
        archivo.name,
        tamano_bytes,
        len(eliminadas),
    )
    return {
        "archivo": archivo.name,
        "tamano_bytes": tamano_bytes,
        "copias_conservadas": len(listar_copias()),
        "copias_eliminadas": eliminadas,
    }
