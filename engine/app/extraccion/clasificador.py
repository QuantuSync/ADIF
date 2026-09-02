"""Etapa 1 de la cascada de extracción (CLAUDE.md sección 5): clasificar la
plantilla de un documento por marcadores de texto, determinista y sin
modelo. Decide toda la ruta posterior — nada aquí se adivina por el nombre
del fichero, solo por su contenido.

Hallazgos de esta sesión sobre el corpus real que CLAUDE.md todavía no
recoge:

- El formulario PCSP no tiene una sola plantilla de título: "Anuncio de
  adjudicación", "Anuncio de formalización de contrato" y "Documento de
  Pliegos" comparten exactamente la misma anatomía de etiquetas fijas
  (Número de Expediente, Presupuesto base de licitación, Importes de
  Adjudicación...). Un fichero cuyo nombre en la Plataforma contiene
  "CONTRATO" puede ser en realidad uno de estos formularios PCSP, no el
  contrato firmado — el marcador de texto "Publicado en la Plataforma de
  Contratación del Sector Público" es lo único fiable.
- Existe una tercera plantilla de propuesta ("L9_CM.32-FE",
  "INFORME-PROPUESTA DE ADJUDICACIÓN DE CONTRATO"), usada por Dirección
  Técnica en vez de la Mesa de Contratación, distinta de LC.27. No tiene
  regla propia todavía: cae en `otro` con confianza 0 hasta decidir si se
  trata como familia nueva o como alias de propuesta_lc27.
- Un fichero descargado como "*_ANEJO_N.pdf" puede ser en realidad el Pliego
  de Prescripciones Técnicas completo, con el anejo de precios unitarios
  como una sección interna suya (título de página 1: "PLIEGO DE
  PRESCRIPCIONES TÉCNICAS..."). Clasificarlo por contenido lo manda a
  `pliego`, no a `anejo` — y es correcto: localizar páginas candidatas
  (CLAUDE.md sección 5, etapa 3) se hace por página dentro de cualquier tipo
  de documento, no depende de que el documento entero se llame "anejo".
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from app.extraccion.texto import PaginaTexto, normalizar
from app.models import TipoDocumento

# Cuántas páginas iniciales se miran para clasificar. Los marcadores de
# título aparecen siempre al principio del documento (portada o primera
# página); la confirmación de "IDENTIFICACIÓN DEL DOCUMENTO" de LC.27 y de
# las resoluciones cae en la página 2. Mirar más allá no cambia el resultado
# y sí el coste.
PAGINAS_A_INSPECCIONAR = 2


@dataclass(frozen=True)
class ResultadoClasificacion:
    tipo: TipoDocumento
    confianza: Decimal
    marcador: str  # el texto normalizado que decidió la regla
    pagina: Optional[int]  # página (1-indexada) donde apareció el marcador


def _texto_normalizado(paginas: list[PaginaTexto]) -> list[tuple[int, str]]:
    return [(p.numero, normalizar(p.texto)) for p in paginas[:PAGINAS_A_INSPECCIONAR]]


def _buscar(paginas_norm: list[tuple[int, str]], *marcadores: str) -> Optional[tuple[int, str]]:
    """Primera página (de las inspeccionadas) que contiene TODOS los
    marcadores dados. Devuelve (número de página, primer marcador) o None."""
    for numero, texto in paginas_norm:
        if all(m in texto for m in marcadores):
            return numero, marcadores[0]
    return None


def clasificar(paginas: list[PaginaTexto]) -> ResultadoClasificacion:
    if not paginas:
        return ResultadoClasificacion(TipoDocumento.otro, Decimal("0"), "", None)

    pn = _texto_normalizado(paginas)

    # 1. Resolución de Adjudicación: título propio + verbo "resuelve" da
    # confianza alta; el título solo (sin "resuelve" cerca) ya es una señal
    # fuerte pero se marca con menos confianza por si es solo una mención.
    hallazgo = _buscar(pn, "resolucion de adjudicacion", "resuelve")
    if hallazgo:
        return ResultadoClasificacion(TipoDocumento.resolucion_adjudicacion, Decimal("0.95"), hallazgo[1], hallazgo[0])
    hallazgo = _buscar(pn, "resolucion de adjudicacion")
    if hallazgo:
        return ResultadoClasificacion(TipoDocumento.resolucion_adjudicacion, Decimal("0.7"), hallazgo[1], hallazgo[0])

    # 2. Propuesta LC.27: código de plantilla + título, los dos.
    hallazgo = _buscar(pn, "lc.27", "propuesta de adjudicacion")
    if hallazgo:
        return ResultadoClasificacion(TipoDocumento.propuesta_lc27, Decimal("0.95"), hallazgo[1], hallazgo[0])

    # 3. Anuncio PCSP: cualquier título "Anuncio de..." de la Plataforma,
    # confirmado por la frase de publicación (ver docstring del módulo).
    for titulo in ("anuncio de adjudicacion", "anuncio de formalizacion de contrato", "anuncio de licitacion"):
        hallazgo = _buscar(pn, titulo, "publicado en la plataforma de contratacion del sector publico")
        if hallazgo:
            return ResultadoClasificacion(TipoDocumento.anuncio_pcsp, Decimal("0.95"), hallazgo[1], hallazgo[0])

    # 4. Contrato firmado ("PARTES CONTRATANTES" + "OBJETO DEL CONTRATO").
    hallazgo = _buscar(pn, "partes contratantes", "objeto del contrato")
    if hallazgo:
        return ResultadoClasificacion(TipoDocumento.contrato, Decimal("0.9"), hallazgo[1], hallazgo[0])

    # 5. Pliego: administrativo, técnico, o el "Documento de Pliegos" índice
    # que también es un formulario PCSP pero sin datos de adjudicación.
    for titulo in (
        "pliego de clausulas administrativas",
        "pliego de prescripciones tecnicas",
        "documento de pliegos",
    ):
        hallazgo = _buscar(pn, titulo)
        if hallazgo:
            return ResultadoClasificacion(TipoDocumento.pliego, Decimal("0.9"), hallazgo[1], hallazgo[0])

    # 6. Anejo suelto (p.ej. "Criterios técnicos"): un documento cuyo título
    # es explícitamente un anejo numerado, no un Pliego que lo contiene.
    hallazgo = _buscar(pn, "criterios tecnicos para el suministro")
    if hallazgo:
        return ResultadoClasificacion(TipoDocumento.anejo, Decimal("0.8"), hallazgo[1], hallazgo[0])

    return ResultadoClasificacion(TipoDocumento.otro, Decimal("0"), "", None)
