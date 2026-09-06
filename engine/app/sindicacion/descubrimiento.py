"""Bloque 2 (CONTEXTO.md sección 24): descubrimiento de expedientes nuevos de
ADIF por sindicación, y detección de cambio de estado en los que ya conoce
el sistema. Se suma al Excel de códigos (CONTEXTO.md sección 7), nunca lo
sustituye — ese sigue siendo la fuente del cruce de códigos; esto es solo
una fuente más para *encontrar* expedientes y para *contrastar* sus importes
(`app.sindicacion.contraste`).

Recordatorio de lo ya verificado (CONTEXTO.md secciones 17.1 y 22, y esta
sesión): la sindicación no sirve para descargar documentos —
`resolver_o_encolar_matriz`/`descargar_expediente` (scraping real, con
navegador) siguen siendo el único camino para traer los PDFs. Este módulo
nunca intenta descargar nada él mismo: como mucho, encola el trabajo de
descarga de siempre.
"""
from __future__ import annotations

import logging
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Expediente, SindicacionExpediente
from app.queue import encolar_trabajo
from app.sindicacion.atom_parser import EntradaSindicacion, entradas_de_zip
from app.sindicacion.cliente import descargar_zip_periodo

logger = logging.getLogger("sindicacion.descubrimiento")


@dataclass
class ResumenDescubrimiento:
    periodo: str
    # Expedientes ÚNICOS con órgano de contratación de ADIF (cualquier
    # departamento) vistos en el periodo -- dimensiona el alcance potencial
    # del sistema si algún día se amplía `sindicacion_departamentos_adif`.
    expedientes_adif_total: int = 0
    # De esos, cuántos pasan el filtro de departamento configurado -- los
    # únicos que este descubrimiento da de alta o actualiza de verdad.
    expedientes_filtrados: int = 0
    expedientes_nuevos: int = 0
    expedientes_con_cambio_estado: int = 0
    expedientes_sin_cambios: int = 0

    def to_dict(self) -> dict:
        return {
            "periodo": self.periodo,
            "expedientes_adif_total": self.expedientes_adif_total,
            "expedientes_filtrados": self.expedientes_filtrados,
            "expedientes_nuevos": self.expedientes_nuevos,
            "expedientes_con_cambio_estado": self.expedientes_con_cambio_estado,
            "expedientes_sin_cambios": self.expedientes_sin_cambios,
        }


def _con_tz(momento: Optional[datetime]) -> Optional[datetime]:
    """SQLite (usado en tests, `tests/conftest.py`) no conserva el huso
    horario de una columna `DateTime(timezone=True)` al releerla — vuelve
    "naive". Postgres sí. Para comparar sin reventar en ninguno de los dos,
    un valor sin huso se trata como si ya estuviera en UTC (igual que se
    guarda: `datetime.now(timezone.utc)` en toda esta sesión)."""
    if momento is not None and momento.tzinfo is None:
        return momento.replace(tzinfo=timezone.utc)
    return momento


def periodo_actual() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m")


def _departamentos_configurados() -> set[str]:
    return {d.strip() for d in settings.sindicacion_departamentos_adif.split(",") if d.strip()}


def _es_adif(entrada: EntradaSindicacion) -> bool:
    """Filtro de órgano de contratación (bloque 2, punto 2): por texto, sin
    acotar todavía por departamento -- eso es un segundo filtro, ver
    `_departamentos_configurados`. Cubre "ADIF", "ADIF -Consejo de
    Administración" y "ADIF Alta Velocidad - ..." por igual (los cuatro
    órganos reales encontrados en la sesión de verificación); un
    departamento fuera de la lista configurada nunca llega a crear ni
    actualizar nada, pase lo que pase con el órgano."""
    return bool(entrada.organo_contratacion) and "adif" in entrada.organo_contratacion.lower()


def _lotes_a_json(entrada: EntradaSindicacion) -> Optional[list[dict]]:
    return [l.to_dict() for l in entrada.lotes] if entrada.lotes else None


def descubrir_novedades(
    db: Session, periodo: Optional[str] = None, ruta_zip: Optional[Path] = None
) -> ResumenDescubrimiento:
    """Descarga (salvo que `ruta_zip` ya apunte a un ZIP local -- así lo usan
    los tests, y así se puede reprocesar un mes ya descargado sin volver a
    golpear la red) y procesa el periodo dado (`AAAAMM`, por defecto el mes
    en curso). Crea expedientes nuevos, guarda la instantánea de sindicación
    de cada uno (`SindicacionExpediente`, fuente independiente de los PDFs)
    y, para un expediente que YA existía y cambia de `estado_pcsp` entre dos
    ejecuciones, encola su descarga -- es la única señal de "novedad" que
    tiene bloque 1 hoy (documentos ya presentes, así que
    `app.mantenimiento.frescura.debe_descargar` por sí solo no lo habría
    vuelto a intentar)."""
    periodo = periodo or periodo_actual()
    resumen = ResumenDescubrimiento(periodo=periodo)
    departamentos = _departamentos_configurados()

    debe_descargar_zip = ruta_zip is None
    ruta = ruta_zip or Path(tempfile.gettempdir()) / f"sindicacion_{periodo}.zip"
    if debe_descargar_zip:
        descargar_zip_periodo(periodo, ruta)

    try:
        vistos_adif: set[str] = set()
        mejores: dict[str, EntradaSindicacion] = {}
        for entrada in entradas_de_zip(ruta, filtro=_es_adif):
            vistos_adif.add(entrada.codigo_expediente)
            if entrada.departamento not in departamentos:
                continue
            actual = mejores.get(entrada.codigo_expediente)
            if actual is None or entrada.actualizado_en > actual.actualizado_en:
                mejores[entrada.codigo_expediente] = entrada
    finally:
        if debe_descargar_zip:
            ruta.unlink(missing_ok=True)

    resumen.expedientes_adif_total = len(vistos_adif)
    resumen.expedientes_filtrados = len(mejores)

    for entrada in mejores.values():
        fila = db.execute(
            select(SindicacionExpediente).where(
                SindicacionExpediente.codigo_expediente == entrada.codigo_expediente
            )
        ).scalar_one_or_none()

        expediente = db.execute(
            select(Expediente).where(Expediente.codigo_expediente == entrada.codigo_expediente)
        ).scalar_one_or_none()

        # Dato más viejo que el que ya teníamos (p.ej. se reprocesa un
        # periodo desde el principio): no aporta nada nuevo, nunca pisa lo
        # que ya había ni dispara un cambio de estado que en realidad ya se
        # conocía. Se cuenta como "sin cambios" y no se toca nada más.
        if fila is not None and expediente is not None and _con_tz(fila.actualizado_en) >= entrada.actualizado_en:
            resumen.expedientes_sin_cambios += 1
            continue

        estado_anterior = fila.estado_pcsp if fila is not None else None
        if expediente is None:
            # Expediente nuevo (bloque 2, punto 3): se da de alta con el
            # estado de siempre (`pendiente`) -- es el mismo bucle de
            # decisión del bloque 1, más abajo en el ciclo, quien decide
            # encolar su descarga porque no tiene documentos, no este
            # módulo. Idempotente por `codigo_expediente` igual que
            # `POST /expedientes` (CONTEXTO.md sección 9.9).
            expediente = Expediente(codigo_expediente=entrada.codigo_expediente)
            db.add(expediente)
            db.commit()
            db.refresh(expediente)
            resumen.expedientes_nuevos += 1
        elif estado_anterior is not None and estado_anterior != entrada.estado_pcsp:
            resumen.expedientes_con_cambio_estado += 1
            logger.info(
                "expediente %s cambia de estado_pcsp: %s -> %s, se reencola su descarga",
                entrada.codigo_expediente, estado_anterior, entrada.estado_pcsp,
            )
            # Único caso en el que bloque 2 encola una descarga él mismo: un
            # expediente que ya tiene documentos no dispara
            # `debe_descargar` (bloque 1) por sí solo, así que sin esto el
            # cambio de estado (p.ej. de publicado a adjudicado) nunca
            # llegaría a verse reflejado en los documentos descargados.
            encolar_trabajo(db, tipo="descargar_expediente", expediente_id=expediente.id)
        else:
            resumen.expedientes_sin_cambios += 1

        if fila is None:
            fila = SindicacionExpediente(codigo_expediente=entrada.codigo_expediente)
            db.add(fila)
        fila.expediente_id = expediente.id
        fila.actualizado_en = entrada.actualizado_en
        fila.estado_pcsp = entrada.estado_pcsp
        fila.organo_contratacion = entrada.organo_contratacion
        fila.titulo = entrada.titulo
        fila.importe_licitacion_sin_impuestos = entrada.importe_licitacion_sin_impuestos
        fila.importe_licitacion_con_impuestos = entrada.importe_licitacion_con_impuestos
        fila.importe_adjudicacion_sin_impuestos = entrada.importe_adjudicacion_sin_impuestos
        fila.importe_adjudicacion_con_impuestos = entrada.importe_adjudicacion_con_impuestos
        fila.adjudicatario = entrada.adjudicatario
        fila.lotes = _lotes_a_json(entrada)
        fila.periodo_zip = periodo
        db.commit()

    logger.info("descubrimiento de sindicación terminado: %s", resumen.to_dict())
    return resumen
