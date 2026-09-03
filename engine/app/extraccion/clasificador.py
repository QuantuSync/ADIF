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
- Tercera plantilla de propuesta ("L9_CM.32-FE", "INFORME-PROPUESTA DE
  ADJUDICACIÓN DE CONTRATO"), usada por Dirección Técnica en vez de la Mesa
  de Contratación, distinta de LC.27: declara el mismo tipo de hecho (baja y
  adjudicatario) con su propia anatomía (tabla "RAZÓN SOCIAL / BAJA
  OFERTADA / ORDEN CLASIFICATORIO"), así que tiene su propio tipo
  (`propuesta_dt`) en vez de forzarse como alias de `propuesta_lc27`
  (docs/analisis-corpus.md hallazgo 4).
- Un fichero descargado como "*_ANEJO_N.pdf" puede ser en realidad el Pliego
  de Prescripciones Técnicas completo, con el anejo de precios unitarios
  como una sección interna suya (título de página 1: "PLIEGO DE
  PRESCRIPCIONES TÉCNICAS..."). Clasificarlo por contenido lo manda a
  `pliego`, no a `anejo` — y es correcto: localizar páginas candidatas
  (CLAUDE.md sección 5, etapa 3) se hace por página dentro de cualquier tipo
  de documento, no depende de que el documento entero se llame "anejo".
- Falso positivo de `pliego` (docs/analisis-corpus.md hallazgo 4, corpus
  completo, sesión de arreglos pequeños 2026-09-03): el título real de un
  Pliego siempre abre la página (verificado en las 23 apariciones reales del
  corpus, todas en la posición 0 del texto normalizado), pero la misma frase
  también aparece de pasada, a mitad de página, en documentos que citan "el
  Pliego de Cláusulas Administrativas Particulares" sin ser ese documento
  (verificado en 3 casos reales: una Resolución, un Contrato y la 3ª
  plantilla de Dirección Técnica, con el marcador en la posición 265, 607 y
  1662 respectivamente). La regla de pliego exige que el marcador aparezca
  cerca del principio de la página — una mención de pasada no cuenta.
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


# Límite de posición para `_buscar_titulo` (docs/analisis-corpus.md hallazgo
# 4, corpus completo): las 23 apariciones reales de "pliego de clausulas
# administrativas" como título abren la página en la posición 0; las tres
# apariciones de la misma frase citada de pasada dentro de un párrafo
# aparecen en la posición 265, 607 y 1662. 50 separa los dos casos con
# margen sin arriesgarse a acercarse al segundo grupo.
_LIMITE_POSICION_TITULO = 50


def _buscar_titulo(paginas_norm: list[tuple[int, str]], marcador: str) -> Optional[tuple[int, str]]:
    """Como `_buscar`, pero solo cuenta si el marcador aparece cerca del
    principio de la página normalizada — la posición real de un título de
    portada, nunca de una mención de pasada en medio de un párrafo. No es el
    comportamiento por defecto de `_buscar`: otros marcadores de este mismo
    clasificador (p.ej. "pliego de prescripciones tecnicas") sí aparecen
    lejos del principio en documentos reales y correctamente clasificados
    (portadas con índice antes del título, layout a dos columnas), así que
    esta restricción se aplica solo donde el corpus real confirma que hace
    falta — ver docstring del módulo."""
    for numero, texto in paginas_norm:
        indice = texto.find(marcador)
        if indice != -1 and indice <= _LIMITE_POSICION_TITULO:
            return numero, marcador
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

    # 5. Propuesta de Dirección Técnica (L9_CM.32-FE), tercera plantilla de
    # adjudicación: código de plantilla único e inequívoco, igual que "lc.27"
    # para la regla 2. Tiene que ir antes de la regla 6 (pliego): su propio
    # texto cita de pasada "el Pliego de Cláusulas Administrativas
    # Particulares" (docs/analisis-corpus.md hallazgo 4), y sin esta regla
    # antes caía en ese falso positivo en vez de en su propia familia.
    hallazgo = _buscar(pn, "l9_cm.32-fe")
    if hallazgo:
        return ResultadoClasificacion(TipoDocumento.propuesta_dt, Decimal("0.95"), hallazgo[1], hallazgo[0])

    # 6. Pliego: administrativo, técnico, o el "Documento de Pliegos" índice
    # que también es un formulario PCSP pero sin datos de adjudicación.
    # "pliego de clausulas administrativas" exige posición de título
    # (`_buscar_titulo`, ver su docstring y el docstring del módulo,
    # hallazgo 4): la misma frase aparece de pasada, a mitad de página, en
    # documentos que solo citan el pliego sin ser ellos mismos un pliego.
    # Los otros dos marcadores de esta familia no muestran ese problema en
    # el corpus real (a veces aparecen lejos del principio en un Pliego
    # real, p.ej. tras un índice) y mantienen la búsqueda normal.
    hallazgo = _buscar_titulo(pn, "pliego de clausulas administrativas")
    if hallazgo:
        return ResultadoClasificacion(TipoDocumento.pliego, Decimal("0.9"), hallazgo[1], hallazgo[0])
    for titulo in ("pliego de prescripciones tecnicas", "documento de pliegos"):
        hallazgo = _buscar(pn, titulo)
        if hallazgo:
            return ResultadoClasificacion(TipoDocumento.pliego, Decimal("0.9"), hallazgo[1], hallazgo[0])

    # 7. Anejo suelto (p.ej. "Criterios técnicos"): un documento cuyo título
    # es explícitamente un anejo numerado, no un Pliego que lo contiene.
    hallazgo = _buscar(pn, "criterios tecnicos para el suministro")
    if hallazgo:
        return ResultadoClasificacion(TipoDocumento.anejo, Decimal("0.8"), hallazgo[1], hallazgo[0])

    return ResultadoClasificacion(TipoDocumento.otro, Decimal("0"), "", None)
