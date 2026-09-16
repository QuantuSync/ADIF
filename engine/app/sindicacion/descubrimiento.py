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

Hallazgo real (aviso del cliente, sesión 2026-09-07, caso `6.26/28510.0014`):
`descubrir_novedades` siempre acepta un `periodo` explícito, pero **nada lo
llamaba nunca con otra cosa que el mes en curso** — `app.mantenimiento.ciclo`
(la única llamadora automática) usa `periodo_actual()` por defecto en cada
ciclo semanal, sin ningún mecanismo que revisite un mes ya pasado. Medido
contra la base de datos real de esta sesión: solo dos periodos se habían
ingerido jamás, `202408` (prueba puntual de la sesión original) y `202609`
(el mes en curso de esta sesión) — **ningún mes intermedio, unos 25 meses,
se ha comprobado nunca**. Un expediente cuyo único cambio de estado cayó en
uno de esos meses saltados es invisible para el sistema aunque esté
publicado en la Plataforma con normalidad (verificado: `6.26/28510.0014`
existe y el scraper real lo encuentra al momento en cuanto se busca a
mano). `descubrir_backfill` y `periodos_recientes` de más abajo cierran
este hueco — un mecanismo explícito para recorrer varios periodos pasados,
no solo el mes en curso.
"""
from __future__ import annotations

import logging
import re
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.criterio_expediente import cumple_criterio, departamentos_configurados
from app.models import Expediente, SindicacionExpediente
from app.queue import encolar_trabajo
from app.sindicacion.atom_parser import EntradaSindicacion, entradas_de_zip
from app.sindicacion.cliente import descargar_zip_periodo

logger = logging.getLogger("sindicacion.descubrimiento")

# Trabajo de cola dedicado (sesión 2026-09-07): un backfill de varios meses
# no necesita el ciclo completo (descargar/extraer lo que falte,
# `app.mantenimiento.ciclo`) -- sindicacion_periodo en ese ciclo ya permitía
# reprocesar UN mes pasado a mano, pero nadie lo había llamado en bucle para
# los ~25 meses nunca comprobados. Este tipo de trabajo es solo el barrido
# de descubrimiento, mes a mes, sin el coste de descargar/extraer de paso.
TIPO_TRABAJO = "sindicacion_backfill"


@dataclass
class ResumenDescubrimiento:
    periodo: str
    # Expedientes ÚNICOS con órgano de contratación de ADIF (cualquier
    # departamento) vistos en el periodo -- dimensiona el alcance potencial
    # del sistema si algún día se amplía `sindicacion_departamentos_adif`.
    # Solo informativo: el órgano ya no decide nada (sesión 2026-09-15).
    expedientes_adif_total: int = 0
    # Cuántos cumplen el criterio (código con un departamento configurado)
    # -- los únicos que este descubrimiento da de alta o actualiza de verdad.
    expedientes_filtrados: int = 0
    expedientes_nuevos: int = 0
    expedientes_con_cambio_estado: int = 0
    expedientes_sin_cambios: int = 0
    # Los que cumplen el criterio pero el filtro anterior (órgano con "adif" y
    # código con la forma `N.AA/DDDDD.`) habría descartado, con el motivo.
    codigos_criterio_ampliado: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "periodo": self.periodo,
            "expedientes_adif_total": self.expedientes_adif_total,
            "expedientes_filtrados": self.expedientes_filtrados,
            "expedientes_nuevos": self.expedientes_nuevos,
            "expedientes_con_cambio_estado": self.expedientes_con_cambio_estado,
            "expedientes_sin_cambios": self.expedientes_sin_cambios,
            "codigos_criterio_ampliado": self.codigos_criterio_ampliado,
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
    return departamentos_configurados()


def _es_adif(entrada: EntradaSindicacion) -> bool:
    """Órgano de contratación con "adif" en el texto. Solo para el recuento
    informativo `expedientes_adif_total` y para señalar lo que el filtro
    anterior habría perdido: desde la sesión 2026-09-15 el órgano no decide
    si un expediente entra (ver `_cumple_criterio`)."""
    return bool(entrada.organo_contratacion) and "adif" in entrada.organo_contratacion.lower()


def _cumple_criterio(codigo: Optional[str], departamentos: set[str]) -> bool:
    """Criterio del cliente (sesión 2026-09-15): entra todo expediente cuyo
    código contenga los dígitos de un departamento configurado (28510), en
    cualquier estado, sin mirar el órgano ni la forma del resto del código.
    Antes se exigía además un órgano con "adif" y la forma exacta
    `N.AA/28510.`: un expediente 28510 con el órgano escrito de otra manera, o
    con el código escrito con otro separador, se perdía sin aviso.

    La regla vive en `app.criterio_expediente` desde la sesión 2026-09-16,
    compartida con el descubrimiento por búsqueda directa -- que sin ella
    daba de alta como expedientes del departamento códigos donde "28510"
    solo aparecía pegado a otros dígitos."""
    return cumple_criterio(codigo, departamentos)


def _motivo_criterio_ampliado(entrada: EntradaSindicacion, departamentos: set[str]) -> Optional[str]:
    """Por qué el filtro anterior habría descartado una entrada que cumple el
    criterio actual, o `None` si también la admitía."""
    motivos = []
    if not _es_adif(entrada):
        motivos.append(f"órgano sin 'adif': {entrada.organo_contratacion!r}")
    if entrada.departamento not in departamentos:
        motivos.append("código sin la forma N.AA/DDDDD.")
    return "; ".join(motivos) or None


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
        filtro = lambda e: _es_adif(e) or _cumple_criterio(e.codigo_expediente, departamentos)  # noqa: E731
        for entrada in entradas_de_zip(ruta, filtro=filtro):
            if _es_adif(entrada):
                vistos_adif.add(entrada.codigo_expediente)
            if not _cumple_criterio(entrada.codigo_expediente, departamentos):
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
        motivo = _motivo_criterio_ampliado(entrada, departamentos)
        if motivo is not None:
            resumen.codigos_criterio_ampliado[entrada.codigo_expediente] = motivo
            logger.info("expediente %s entra por el criterio ampliado: %s", entrada.codigo_expediente, motivo)

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


def periodos_recientes(n: int, hasta: Optional[str] = None) -> list[str]:
    """Los últimos `n` periodos `AAAAMM` terminando en `hasta` (por defecto
    el mes en curso), del más reciente al más antiguo -- mismo orden en el
    que `descubrir_backfill` los procesa, para que una tanda interrumpida a
    medias deje sin procesar los meses más antiguos, nunca los recientes
    (los que con más probabilidad traen expedientes todavía activos)."""
    if n < 1:
        raise ValueError(f"n debe ser >= 1, recibido {n!r}")
    base = hasta or periodo_actual()
    anio, mes = int(base[:4]), int(base[4:6])
    periodos = []
    for _ in range(n):
        periodos.append(f"{anio:04d}{mes:02d}")
        mes -= 1
        if mes == 0:
            mes = 12
            anio -= 1
    return periodos


@dataclass
class ResumenBackfill:
    """Agregado de varios `ResumenDescubrimiento`, uno por periodo -- lo que
    devuelve `descubrir_backfill`. `periodos_con_error` aísla el fallo de un
    mes concreto (ZIP no publicado todavía, corte de red) del resto de la
    tanda, igual que `app.mantenimiento.ciclo` ya aísla el fallo de un
    documento del resto del expediente: un mes que falla no debe impedir que
    los demás se procesen."""

    periodos_procesados: list[str] = field(default_factory=list)
    periodos_con_error: dict[str, str] = field(default_factory=dict)
    expedientes_nuevos: int = 0
    expedientes_con_cambio_estado: int = 0
    codigos_criterio_ampliado: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "periodos_procesados": self.periodos_procesados,
            "periodos_con_error": self.periodos_con_error,
            "expedientes_nuevos": self.expedientes_nuevos,
            "expedientes_con_cambio_estado": self.expedientes_con_cambio_estado,
            "codigos_criterio_ampliado": self.codigos_criterio_ampliado,
        }


# Sesión de límite de tasa (2026-09-07): un backfill real de 21 meses hizo
# fallar 11 periodos SEGUIDOS con "File is not a zip file" justo después de
# 10 correctos -- patrón de bloqueo/límite de tasa bajo carga, no de 11
# meses genuinamente sin publicar (que la Plataforma real respondería con
# 404, no con un cuerpo de bloqueo servido como 200 -- ver
# `app.sindicacion.cliente.DescargaSindicacionInvalidaError`). Antes, un
# solo intento fallido por periodo se daba por perdido inmediatamente y se
# pasaba al siguiente sin ninguna pausa, machacando la fuente real sin
# tregua durante los 11 periodos.
_ESPERA_ENTRE_PERIODOS_SEGUNDOS = 15.0
_REINTENTOS_POR_PERIODO = 3
_ESPERA_BASE_REINTENTO_SEGUNDOS = 60.0


def _descubrir_periodo_con_reintentos(db: Session, periodo: str) -> ResumenDescubrimiento:
    """Reintenta un periodo hasta `_REINTENTOS_POR_PERIODO` veces con espera
    creciente (60 s, 120 s...) antes de darlo por fallido de verdad --
    distingue un bloqueo transitorio real (se recupera solo tras esperar)
    de un mes genuinamente sin publicar (sigue fallando igual tras esperar,
    y ahí sí se anota en `periodos_con_error` sin gastar más tiempo)."""
    ultimo_error: Exception = RuntimeError(f"periodo {periodo}: sin ningún intento realizado")
    for intento in range(1, _REINTENTOS_POR_PERIODO + 1):
        try:
            return descubrir_novedades(db, periodo=periodo)
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            ultimo_error = exc
            if intento < _REINTENTOS_POR_PERIODO:
                espera = _ESPERA_BASE_REINTENTO_SEGUNDOS * (2 ** (intento - 1))
                logger.warning(
                    "backfill de sindicación: periodo %s falló (intento %s/%s), reintentando en %ss: %s",
                    periodo, intento, _REINTENTOS_POR_PERIODO, espera, exc,
                )
                time.sleep(espera)
    raise ultimo_error


def descubrir_backfill(db: Session, periodos: list[str]) -> ResumenBackfill:
    """Recorre varios periodos pasados llamando a `descubrir_novedades` una
    vez por cada uno (mismo mecanismo de siempre) -- cierra el hueco real de
    esta sesión: nada, hasta ahora, llamaba a `descubrir_novedades` con un
    periodo que no fuera el mes en curso. Cada periodo se reintenta con
    espera creciente (`_descubrir_periodo_con_reintentos`) y hay una pausa
    mínima entre periodos distintos (`_ESPERA_ENTRE_PERIODOS_SEGUNDOS`),
    para no encadenar descargas reales sin ninguna pausa (sesión de límite
    de tasa, 2026-09-07, ver docstring de arriba). Un periodo que sigue
    fallando tras agotar sus reintentos se anota en
    `ResumenBackfill.periodos_con_error` y la tanda sigue con el siguiente,
    nunca aborta el resto."""
    resumen = ResumenBackfill()
    for indice, periodo in enumerate(periodos):
        if indice > 0:
            time.sleep(_ESPERA_ENTRE_PERIODOS_SEGUNDOS)
        try:
            parcial = _descubrir_periodo_con_reintentos(db, periodo)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "backfill de sindicación: periodo %s falló tras %s intentos, se continúa con el resto: %s",
                periodo, _REINTENTOS_POR_PERIODO, exc,
            )
            resumen.periodos_con_error[periodo] = str(exc)
            continue
        resumen.periodos_procesados.append(periodo)
        resumen.expedientes_nuevos += parcial.expedientes_nuevos
        resumen.expedientes_con_cambio_estado += parcial.expedientes_con_cambio_estado
        resumen.codigos_criterio_ampliado.update(parcial.codigos_criterio_ampliado)
    logger.info("backfill de sindicación terminado: %s", resumen.to_dict())
    return resumen
