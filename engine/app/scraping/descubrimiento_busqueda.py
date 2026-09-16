"""Descubrimiento por búsqueda directa en la Plataforma (sesión 2026-09-16).

**Por qué hace falta, además de la sindicación.** El descubrimiento por
sindicación (`app.sindicacion.descubrimiento`) lee el ZIP mensual de
licitaciones: una entrada aparece cuando hay un evento de contratación en
ese mes, así que cubre bien lo ya adjudicado o resuelto, pero un expediente
que sigue en licitación o pendiente de resolver puede no haber generado
todavía ninguna entrada -- y entonces, para ese mecanismo, no existe. Ya
estaba medido que la sindicación no lo cubre todo (CONTEXTO.md sección 16:
solo el 2,5 % de los 367 expedientes del SAP), pero la causa que se había
documentado era la antigüedad; esta es la otra mitad, y afecta justo a lo
más reciente de cada año.

**El criterio es del cliente, no de este módulo**: todo expediente cuyo
código contenga los dígitos del departamento, en cualquier estado
(CONTEXTO.md sección 16, sesión 2026-09-15 tercera parte -- el mismo
criterio que ya rige la sindicación, que dejó de mirar el órgano de
contratación y la forma exacta del código). Aquí se aplica pidiéndoselo
literalmente al buscador de la Plataforma, cuyo campo "Nº de expediente"
hace coincidencia por subcadena (ver `app.scraping.pcsp.
buscar_codigos_por_fragmento`).

**Configurable, nunca atado a un año.** `BUSQUEDA_FRAGMENTOS` es la lista de
fragmentos que se buscan; vacía (por defecto) significa "los departamentos
de `SINDICACION_DEPARTAMENTOS_ADIF`", que es exactamente el criterio del
cliente y no hay que tocar nada para que valga en 2027. Un fragmento más
fino (`6.26/28510`) sirve para acotar una pasada concreta sin cambiar la
configuración, pasándolo en el payload del trabajo.

**Ritmo.** Cada búsqueda y cada paso de página van detrás de
`app.scraping.limitador.esperar_turno_async`, el mismo turno compartido que
espacia las descargas -- el episodio de 2026-09-07 (cientos de peticiones
seguidas sin pausa, bloqueos confundidos con "expediente no publicado") no
se repite por abrir una vía nueva de peticiones.

**Dónde corre.** Dentro del ciclo de mantenimiento
(`app.mantenimiento.ciclo`), junto al descubrimiento por sindicación y antes
del bucle de frescura, para que lo que aparezca aquí se descargue y se
extraiga en la misma pasada. No es un trabajo que haya que lanzar a mano.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.criterio_expediente import fragmento_en_codigo
from app.models import EstadoExpediente, Expediente
from app.scraping.pcsp import buscar_codigos_de_fragmentos

logger = logging.getLogger("scraping.descubrimiento_busqueda")


@dataclass
class ResumenDescubrimientoBusqueda:
    fragmentos: list[str] = field(default_factory=list)
    # {fragmento: nº de códigos que devolvió la Plataforma}
    encontrados_por_fragmento: dict[str, int] = field(default_factory=dict)
    codigos_encontrados: int = 0
    # Códigos que devolvió el buscador pero donde el fragmento solo aparecía
    # pegado a otros dígitos (`app.criterio_expediente`): no son del
    # departamento, se descartan sin darlos de alta.
    codigos_descartados: list[str] = field(default_factory=list)
    expedientes_nuevos: int = 0
    # Estaban dados por `sin_publicar` y la búsqueda acaba de demostrar que sí
    # están publicados: se reabren y se vuelve a encolar su descarga.
    sin_publicar_reabiertos: int = 0
    ya_conocidos: int = 0
    codigos_nuevos: list[str] = field(default_factory=list)
    codigos_reabiertos: list[str] = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "fragmentos": self.fragmentos,
            "encontrados_por_fragmento": self.encontrados_por_fragmento,
            "codigos_encontrados": self.codigos_encontrados,
            "codigos_descartados": sorted(self.codigos_descartados),
            "expedientes_nuevos": self.expedientes_nuevos,
            "sin_publicar_reabiertos": self.sin_publicar_reabiertos,
            "ya_conocidos": self.ya_conocidos,
            "codigos_nuevos": sorted(self.codigos_nuevos),
            "codigos_reabiertos": sorted(self.codigos_reabiertos),
            "error": self.error,
        }


def fragmentos_configurados() -> list[str]:
    """`BUSQUEDA_FRAGMENTOS` si está puesta; si no, los departamentos de
    `SINDICACION_DEPARTAMENTOS_ADIF` -- una sola fuente para "qué es nuestro"
    en las dos vías de descubrimiento, en vez de dos listas que puedan
    divergir en silencio."""
    crudo = (settings.busqueda_fragmentos or "").strip()
    if not crudo:
        crudo = settings.sindicacion_departamentos_adif or ""
    return [f.strip() for f in crudo.split(",") if f.strip()]


def _registrar(db: Session, codigo: str, resumen: ResumenDescubrimientoBusqueda) -> None:
    existente = db.execute(
        select(Expediente).where(Expediente.codigo_expediente == codigo)
    ).scalar_one_or_none()

    if existente is None:
        # Alta con el estado de siempre (`pendiente`), igual que el
        # descubrimiento por sindicación: es el bucle de frescura del ciclo
        # quien encola su descarga porque no tiene documentos, no este
        # módulo. Idempotente por `codigo_expediente` (CONTEXTO.md 9.9).
        expediente = Expediente(codigo_expediente=codigo)
        db.add(expediente)
        try:
            db.commit()
        except IntegrityError:
            # Carrera con otra vía de alta (sindicación, herencia de matriz,
            # ingesta local): no es un error, el expediente ya está.
            db.rollback()
            resumen.ya_conocidos += 1
            return
        resumen.expedientes_nuevos += 1
        resumen.codigos_nuevos.append(codigo)
        return

    if existente.estado == EstadoExpediente.sin_publicar:
        # La búsqueda acaba de encontrarlo en la Plataforma: el negativo que
        # lo dejó en `sin_publicar` era falso, venga de donde venga (el
        # bloqueo de 2026-09-07, o una variante de código que la búsqueda
        # exacta no probó). Se reabre y se vuelve a encolar su descarga sin
        # esperar al plazo de `SIN_PUBLICAR_REINTENTO_DIAS`: aquí hay
        # evidencia positiva, no un reintento a ciegas.
        #
        # Volver a `pendiente` es todo lo que hace falta, y a propósito no se
        # encola aquí la descarga: el bucle de frescura del ciclo excluye los
        # `sin_publicar` pero sí recorre los `pendiente`, y un expediente sin
        # documentos dispara `debe_descargar` por sí solo. Encolarla también
        # aquí sería la misma descarga por duplicado -- una petición real de
        # más a la Plataforma, justo lo que el resto del módulo evita.
        logger.info("%s estaba sin_publicar y la búsqueda lo encuentra: se reabre", codigo)
        existente.estado = EstadoExpediente.pendiente
        existente.sin_publicar_en = None
        existente.sin_publicar_version_busqueda = None
        db.commit()
        resumen.sin_publicar_reabiertos += 1
        resumen.codigos_reabiertos.append(codigo)
        return

    resumen.ya_conocidos += 1


def descubrir_por_busqueda(
    db: Session, fragmentos: Optional[list[str]] = None
) -> ResumenDescubrimientoBusqueda:
    """Busca cada fragmento en la Plataforma y da de alta lo que falte.

    `fragmentos` acota una pasada concreta (payload del trabajo). `None`
    -- el caso normal, y lo que devuelve `payload.get(...)` cuando la clave
    no viene -- significa "los de `fragmentos_configurados()`"; una lista
    vacía significa literalmente ninguno, y entonces no se abre navegador.
    Son dos cosas distintas a propósito: "no me has dicho cuáles" no puede
    valer lo mismo que "ninguno", o una configuración vacía acabaría
    buscando por su cuenta algo que nadie pidió. Una sola sesión de
    navegador para todos los fragmentos.
    """
    if fragmentos is None:
        fragmentos = fragmentos_configurados()
    fragmentos = [f.strip() for f in fragmentos if f and f.strip()]
    resumen = ResumenDescubrimientoBusqueda(fragmentos=fragmentos)
    if not fragmentos:
        return resumen

    por_fragmento = asyncio.run(buscar_codigos_de_fragmentos(fragmentos))

    vistos: set[str] = set()
    descartados: set[str] = set()
    for fragmento in fragmentos:
        codigos = por_fragmento.get(fragmento, [])
        resumen.encontrados_por_fragmento[fragmento] = len(codigos)
        for codigo in codigos:
            codigo = codigo.strip()
            if not codigo or codigo in vistos or codigo in descartados:
                continue
            # El campo "Nº de expediente" del buscador hace coincidencia por
            # SUBCADENA pura, sin ninguna noción de qué es un número de
            # departamento: buscar "28510" devuelve también `PcPG/2026/828510`
            # y `EMER_HV_2020_62285100`, donde esos dígitos son parte de otro
            # número (verificado en vivo, sesión 2026-09-16). El criterio del
            # cliente se aplica aquí, con la misma regla que la sindicación
            # (`app.criterio_expediente`), nunca delegado al buscador.
            if not fragmento_en_codigo(codigo, fragmento):
                descartados.add(codigo)
                resumen.codigos_descartados.append(codigo)
                logger.info(
                    "%s descartado: %r solo aparece pegado a otros dígitos", codigo, fragmento
                )
                continue
            vistos.add(codigo)
            _registrar(db, codigo, resumen)

    resumen.codigos_encontrados = len(vistos)
    logger.info("descubrimiento por búsqueda terminado: %s", resumen.to_dict())
    return resumen
