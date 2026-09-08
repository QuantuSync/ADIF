"""Etapas 3 y 4 de la sesión (CONTEXTO.md sección 4): la baja es un dato
declarado en texto, nunca una tabla que calcular. Se busca en la Propuesta
LC.27, en la Resolución de Adjudicación y en el contrato — las tres plantillas
declaran la misma frase con redacciones distintas:

  - LC.27 (individual): "con una baja económica del 54,00 % a precios
    unitarios licitados"
  - LC.27 (UTE): "con una baja del 0,50% al conjunto de precios unitarios
    de los artículos que componen el objeto del contrato"
  - Resolución: "con una baja del 4,50% aplicable al conjunto de precios
    unitarios de los artículos que componen el objeto del contrato"
  - Contrato: "La baja económica ofertada del 54,00% será aplicable a
    todos los precios unitarios licitados."
  - Propuesta de Dirección Técnica (L9_CM.32-FE, docs/analisis-corpus.md
    hallazgo 4): "con una baja del 20% a todos los precios unitarios"

Todas comparten la forma "baja [económica] [ofertada] del N %  ... precios
unitarios": un único patrón laxo basta para las cuatro, sin necesitar una
regla por plantilla — verificado contra los dos documentos reales de
Dirección Técnica sin tener que tocar `_BAJA_RE`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from app.extraccion.campos_pcsp import CODIGO_EXPEDIENTE_RE
from app.extraccion.normalizacion import parsear_porcentaje_es
from app.extraccion.texto import PaginaTexto
from app.models import TipoDocumento

# La distancia entre "% " y "precios unitarios" varía (de un espacio a una
# subordinada entera) pero nunca cruza a la frase siguiente en los ejemplos
# vistos; 160 caracteres da margen sin arriesgarse a saltar de párrafo.
_BAJA_RE = re.compile(
    r"baja(?:\s+econ[oó]mica)?(?:\s+ofertada)?\s+del[.,]?\s*([\d.,]+)\s*%[^.]{0,160}?precios unitarios",
    re.IGNORECASE | re.DOTALL,
)

# Redacciones alternativas de la misma baja (sesión de expedientes sin
# publicar, CONTEXTO.md sección 22), verificadas contra un caso real que no
# viene del corpus de PDFs de este proyecto sino de otra fuente: una etiqueta
# de campo, no una frase en prosa, y sin la subordinada "precios unitarios"
# que exige `_BAJA_RE`. Solo se intenta si `_BAJA_RE` no encontró nada en
# ningún documento del expediente (ver `extraer_baja_declarada`), nunca antes
# — es un patrón más laxo y solo debe ganar cuando el estricto no sirve.
#
# El caso que dispara esto: "% de baja:    12,5" — el símbolo de porcentaje
# va pegado a la etiqueta, no al número ("% de baja", no "baja del 12,5%").
# Esa variante concreta ("de baja") exige el "%" delante a propósito: sin
# esa ancla, "de baja" también aparece en cláusulas laborales de boilerplate
# ajenas a la baja del expediente ("el trabajador que se encuentre de
# baja..."), y el símbolo de porcentaje pegado a la etiqueta es la señal que
# distingue el campo de adjudicación de esa prosa. Las otras variantes
# ("% baja adjudicado", "% total de baja", "baja ofertada", "porcentaje de
# baja") son frases lo bastante específicas para no necesitar esa misma
# ancla.
_BAJA_ETIQUETA_RE = re.compile(
    r"(?:"
    r"%\s*de\s+baja"
    r"|%?\s*porcentaje\s+de\s+baja"
    r"|%?\s*total\s+de\s+baja"
    r"|%?\s*baja\s+adjudicad[oa]"
    r"|%?\s*baja\s+ofertada"
    r")\b[:=\s]*([\d]+(?:[.,]\d+)?)\s*%?",
    re.IGNORECASE,
)

# Redacción invertida, verificada en un documento real del corpus
# (6.23/28510.0051_ADJUDICACION_1.pdf, propuesta LC.27 individual): "con un
# 25,31 % de baja a todos los precios unitarios" -- el número precede a "%
# de baja" en vez de seguir a "baja del". No es la misma forma que
# `_BAJA_ETIQUETA_RE` (esa exige el número DESPUÉS de la etiqueta): aquí el
# número va delante, así que hace falta un patrón propio. El riesgo de falso
# positivo es bajo porque exige un número inmediatamente antes de "% de
# baja", a diferencia de la "de baja" sola que sí puede confundirse con
# boilerplate laboral.
_BAJA_INVERTIDA_RE = re.compile(
    r"([\d]+(?:[.,]\d+)?)\s*%\s*de\s+baja\b[^.]{0,160}?precios unitarios",
    re.IGNORECASE | re.DOTALL,
)

# Prioridad al elegir entre varios documentos del mismo hecho para el mismo
# expediente/lote (CONTEXTO.md sección 17: "preferir la Resolución cuando
# existan las dos" porque es el acto posterior y definitivo).
# `propuesta_dt` (docs/analisis-corpus.md hallazgo 4) es al mismo tipo de
# hecho que propuesta_lc27 — una propuesta previa a la Resolución, nunca
# vista junto a una LC.27 en el mismo expediente — misma prioridad.
_PRIORIDAD_BAJA = {
    TipoDocumento.resolucion_adjudicacion: 0,
    TipoDocumento.contrato: 1,
    TipoDocumento.propuesta_lc27: 2,
    TipoDocumento.propuesta_dt: 2,
}


@dataclass(frozen=True)
class BajaDeclarada:
    baja: Decimal  # fracción, p.ej. Decimal("0.5400") para 54,00 %
    pagina: int
    fragmento: str
    tipo_documento: Optional[TipoDocumento] = None


@dataclass(frozen=True)
class BajaEnTexto:
    baja: Decimal
    fragmento: str


# Sesión de medición del alcance "Nº Lote: NNN" (2026-09-08, parte 2 del
# encargo, docs/sesion-2026-09-08-auditoria-automatica.md): un CONTRATO
# (u otro documento de `_TIPOS_CON_BAJA_DECLARADA`) puede estar vinculado a
# varios expedientes hermanos que comparten la misma licitación agrupadora
# (`DocumentoExpediente`, migración 0021) -- el mismo defecto estructural
# que ya se corrigió para el Anuncio PCSP multi-lote, aquí en la baja
# declarada por texto. Verificado contra el corpus real (`6.23/28510.0139`
# y sus dos pedidos, `6.24/28510.0017`/`0018`): dos CONTRATOs distintos,
# cada uno vinculado a los TRES expedientes, con bajas declaradas distintas
# (5,07 % y 0,40 %) -- sin este ancla, `elegir_baja_preferida` no tenía
# forma de saber cuál de las dos es la de cada expediente.
#
# A diferencia del Anuncio PCSP (que agrupa varios lotes en un ÚNICO
# documento bajo "Nº Lote: NNN"), aquí cada lote tiene su propio documento
# COMPLETO, y cada uno declara sin ambigüedad a qué expediente pertenece:
# "Contrato nº: 6.24/28510.0017" -- no hace falta ventanear el texto ni
# emparejar por `nombre_proyecto`, el propio documento ya lo dice.
_CODIGO_PROPIO_RE = re.compile(
    r"Contrato\s*n[ºo]:?\s*(" + CODIGO_EXPEDIENTE_RE.pattern + r")", re.IGNORECASE
)


def extraer_codigo_propio_documento(paginas: list[PaginaTexto]) -> Optional[str]:
    """`None` si el documento no declara "Contrato nº: X" -- la inmensa
    mayoría del corpus, donde este mecanismo no cambia nada (un CONTRATO
    vinculado a un único expediente no necesita desambiguarse). Solo se
    busca en las tres primeras páginas (la cabecera administrativa del
    contrato, verificado contra el corpus real): el patrón de código de
    expediente es demasiado genérico para buscarlo en el cuerpo entero sin
    arriesgarse a coger una referencia a OTRO expediente mencionada de
    pasada más adelante."""
    for pagina in paginas[:3]:
        m = _CODIGO_PROPIO_RE.search(pagina.texto)
        if m:
            return m.group(1)
    return None


def buscar_baja_en_texto(texto: str) -> Optional[BajaEnTexto]:
    """Busca la frase de baja declarada dentro de un fragmento de texto
    cualquiera -- no solo una página completa. Reutilizada tal cual por
    `extraer_baja_declarada` (página a página) y por
    `app.extraccion.lotes` (ventana de texto por lote): las tres variantes
    de redacción son las mismas se busque en un documento entero o en el
    trozo de un lote."""
    for patron in (_BAJA_RE, _BAJA_INVERTIDA_RE, _BAJA_ETIQUETA_RE):
        m = patron.search(texto)
        if m:
            return BajaEnTexto(baja=parsear_porcentaje_es(m.group(1)), fragmento=m.group(0).strip())
    return None


def extraer_baja_declarada(
    paginas: list[PaginaTexto], tipo_documento: Optional[TipoDocumento] = None
) -> Optional[BajaDeclarada]:
    """Primera aparición, en orden de página, de la frase de baja declarada.
    No busca todas las apariciones: en los documentos vistos la baja se
    declara una sola vez por lote/expediente y las siguientes menciones (si
    las hay) repiten el mismo valor. Primero se prueba la frase estricta
    (`_BAJA_RE`) en todas las páginas antes de caer a las variantes más
    laxas (`_BAJA_INVERTIDA_RE`, `_BAJA_ETIQUETA_RE`) si no encontró nada en
    ninguna -- mismo orden de prioridad que antes, ahora compartido con
    `buscar_baja_en_texto`."""
    for pagina in paginas:
        m = _BAJA_RE.search(pagina.texto)
        if m:
            return BajaDeclarada(
                baja=parsear_porcentaje_es(m.group(1)),
                pagina=pagina.numero,
                fragmento=m.group(0).strip(),
                tipo_documento=tipo_documento,
            )
    # Ninguna página trajo la frase estricta "baja ... del N% ... precios
    # unitarios": antes de rendirse, se prueban las variantes más laxas (ver
    # docstrings de `_BAJA_INVERTIDA_RE` y `_BAJA_ETIQUETA_RE`) — solo como
    # segunda pasada, nunca antes.
    for pagina in paginas:
        for patron in (_BAJA_INVERTIDA_RE, _BAJA_ETIQUETA_RE):
            m = patron.search(pagina.texto)
            if m:
                return BajaDeclarada(
                    baja=parsear_porcentaje_es(m.group(1)),
                    pagina=pagina.numero,
                    fragmento=m.group(0).strip(),
                    tipo_documento=tipo_documento,
                )
    return None


def elegir_baja_preferida(candidatas: list[BajaDeclarada]) -> Optional[BajaDeclarada]:
    """Cuando el mismo expediente trae baja declarada en más de un documento
    (p.ej. Propuesta y Resolución, CONTEXTO.md sección 17), se queda con la del
    documento de mayor prioridad. No decide si los valores discrepan entre
    sí — eso es una incoherencia y va a la cola de revisión (sección 12), no
    algo que este selector deba resolver en silencio."""
    if not candidatas:
        return None
    return min(
        candidatas,
        key=lambda c: _PRIORIDAD_BAJA.get(c.tipo_documento, len(_PRIORIDAD_BAJA)),
    )
