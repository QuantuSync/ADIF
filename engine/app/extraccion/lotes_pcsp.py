"""Tercera variante de documento multi-lote (sesión de medición del alcance,
2026-09-08, `docs/sesion-2026-09-08-auditoria-automatica.md`): un "Anuncio de
adjudicación" del formulario PCSP puede agrupar varios lotes de UNA misma
licitación en un solo PDF, cada uno marcado con "Nº Lote: NNN" (no "LOTE N",
la forma narrativa que ya cubre `app.extraccion.lotes`) seguido de su propio
bloque -- "Objeto del Contrato", "Presupuesto base de licitación",
"Adjudicatario", "Importes de Adjudicación" -- repetido una vez por lote.

Hallazgo real que motiva este módulo: `app.extraccion.campos_pcsp.
extraer_campos_anuncio_pcsp` busca la primera coincidencia de cada etiqueta
en el documento ENTERO (`_buscar_en_paginas`), que para un documento así es
la cabecera GLOBAL de toda la licitación para "Presupuesto base de
licitación" (aparece una vez antes del primer "Nº Lote:", con el total de
todos los lotes) y el bloque del PRIMER lote del documento para
"Adjudicatario"/"Importes de Adjudicación" -- sin distinguir a cuál de los
varios expedientes hermanos que pueden compartir este mismo documento (uno
por lote, `DocumentoExpediente` migración 0021) pertenece cada dato.
Verificado contra el corpus real: 22 expedientes con `importe_licitacion` =
el total global en vez del de su propio lote; en la familia más grave (14
pedidos de "balasto en régimen de pedido abierto"), TAMBIÉN
`importe_adjudicacion` y `adjudicatario` resultan idénticos en los 14,
todos copiados del primer lote del documento ("Madrid Norte 2").

Cómo se resuelve sin adivinar: cada bloque de lote trae su propio "Objeto
del Contrato", que para el corpus real coincide casi literalmente con
`Expediente.nombre_proyecto` -- una fuente independiente y ya correcta por
expediente (viene del Excel de ejecución SAP, `app.extraccion.estado_sap`,
o de una extracción anterior, nunca de este mismo camino: el guard `if not
expediente.nombre_proyecto` en `app.extraccion.orquestador._extraer_campos_
expediente` nunca lo pisa una vez puesto). Se empareja cada expediente con
SU bloque comparando ese nombre contra el objeto de cada ventana; si no hay
una coincidencia única y clara, no se usa ninguno de los importes de este
documento para ese expediente -- se manda a revisión en vez de atribuir el
bloque equivocado (CONTEXTO.md: "el sistema nunca inventa un dato")."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, replace
from typing import Optional

from app.extraccion.campos_pcsp import (
    CampoAnclado,
    CamposAnuncioPcsp,
    _ADJUDICATARIO_RE,
    _IMPORTE_ADJUDICACION_RE,
    _IMPORTE_LICITACION_RE,
    extraer_campos_anuncio_pcsp,
)
from app.extraccion.invalidado import INVALIDADO
from app.extraccion.texto import PaginaTexto

# Marcador de esta variante: "Nº Lote: NNN" con dos puntos -- deliberadamente
# distinto de `app.extraccion.lotes._LOTE_OCURRENCIA_RE` ("LOTE N" sin dos
# puntos, la forma narrativa), para que un documento nunca dispare las dos
# vías de extracción multi-lote a la vez.
_NLOTE_RE = re.compile(r"N[ºo]\s*Lote:\s*(\d{1,3})", re.IGNORECASE)

# El objeto de cada bloque termina en la primera de tres etiquetas posibles,
# verificadas contra el corpus real: la mayoría de los bloques van directos a
# "Presupuesto base de licitación", pero algunos (`6.23/28510.0139`, dos
# lotes de balasto) repiten el objeto bajo "Descripción" y añaden un "Valor
# estimado del contrato" antes de esa misma etiqueta -- sin las tres
# alternativas, la captura se comía el bloque entero hasta la PRIMERA vez que
# "Presupuesto" aparece, arrastrando la repetición.
_OBJETO_VENTANA_RE = re.compile(
    r"Objeto del Contrato:\s*(.+?)\s*\n(?:Descripci[oó]n|Presupuesto|Valor estimado)", re.DOTALL | re.IGNORECASE
)


@dataclass(frozen=True)
class VentanaLotePcsp:
    numero_lote: str
    objeto: Optional[str]
    importe_licitacion: Optional[CampoAnclado]
    importe_adjudicacion: Optional[CampoAnclado]
    adjudicatario: Optional[CampoAnclado]


def _texto_y_paginas(paginas: list[PaginaTexto]) -> tuple[str, list[tuple[int, int]]]:
    """Mismo criterio que `app.extraccion.lotes._texto_y_paginas`: concatena
    todas las páginas (un bloque de lote puede partirse por un salto de
    página) y devuelve los límites para anclar cada hallazgo a su página."""
    texto = ""
    limites: list[tuple[int, int]] = []
    for pagina in paginas:
        limites.append((len(texto), pagina.numero))
        texto += pagina.texto + "\n"
    return texto, limites


def _pagina_en_offset(limites: list[tuple[int, int]], offset: int) -> int:
    numero = limites[0][1] if limites else 0
    for inicio, pagina_numero in limites:
        if inicio <= offset:
            numero = pagina_numero
        else:
            break
    return numero


def _normalizar_texto(valor: Optional[str]) -> str:
    """Espacios colapsados, minúsculas y sin acentos -- el Excel de ejecución
    SAP (fuente habitual de `Expediente.nombre_proyecto`, `app.extraccion.
    estado_sap`) y el propio PDF no siempre concuerdan letra a letra en los
    acentos aunque describan el mismo objeto."""
    sin_acentos = unicodedata.normalize("NFKD", valor or "").encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", sin_acentos).strip().lower()


def extraer_ventanas_multi_lote_pcsp(paginas: list[PaginaTexto]) -> list[VentanaLotePcsp]:
    """Lista vacía si el documento no trae al menos DOS "Nº Lote: NNN"
    distintos -- un único lote marcado así (o ninguno) sigue su camino de
    siempre (`app.extraccion.campos_pcsp`), sin pasar por aquí. Cuando el
    mismo número de lote aparece más de una vez (footer de firma/sello que
    repite la línea "Nº Lote: NNN" tras el bloque real, verificado en el
    corpus), se queda con la PRIMERA aparición -- las siguientes son ruido
    de paginación, no un segundo lote."""
    texto, limites = _texto_y_paginas(paginas)
    ocurrencias = list(_NLOTE_RE.finditer(texto))
    numeros_distintos = {m.group(1) for m in ocurrencias}
    if len(numeros_distintos) < 2:
        return []

    ventanas: dict[str, VentanaLotePcsp] = {}
    for i, m in enumerate(ocurrencias):
        numero_lote = m.group(1)
        if numero_lote in ventanas:
            continue
        fin = ocurrencias[i + 1].start() if i + 1 < len(ocurrencias) else len(texto)
        ventana_texto = texto[m.start():fin]
        pagina = _pagina_en_offset(limites, m.start())

        m_obj = _OBJETO_VENTANA_RE.search(ventana_texto)
        objeto = re.sub(r"\s+", " ", m_obj.group(1)).strip() if m_obj else None

        m_lic = _IMPORTE_LICITACION_RE.search(ventana_texto)
        importe_licitacion = (
            CampoAnclado(valor=m_lic.group(1).strip(), pagina=pagina, fragmento=m_lic.group(0).strip())
            if m_lic else None
        )
        m_adj = _IMPORTE_ADJUDICACION_RE.search(ventana_texto)
        importe_adjudicacion = (
            CampoAnclado(valor=m_adj.group(1).strip(), pagina=pagina, fragmento=m_adj.group(0).strip())
            if m_adj else None
        )
        m_adjc = _ADJUDICATARIO_RE.search(ventana_texto)
        adjudicatario = (
            CampoAnclado(valor=m_adjc.group(1).strip(), pagina=pagina, fragmento=m_adjc.group(0).strip())
            if m_adjc else None
        )

        ventanas[numero_lote] = VentanaLotePcsp(
            numero_lote=numero_lote,
            objeto=objeto,
            importe_licitacion=importe_licitacion,
            importe_adjudicacion=importe_adjudicacion,
            adjudicatario=adjudicatario,
        )
    return list(ventanas.values())


def emparejar_ventana_por_nombre_proyecto(
    ventanas: list[VentanaLotePcsp], nombre_proyecto: Optional[str]
) -> Optional[VentanaLotePcsp]:
    """Empareja por el objeto de cada bloque contra `Expediente.nombre_proyecto`
    (ver docstring del módulo: por qué es una fuente fiable e independiente).
    `None` sin adivinar cuando no hay nombre con el que comparar, cuando
    ninguna ventana casa, o cuando casan varias (ambiguo) -- nunca se elige
    "la primera" ni "la más parecida" a ciegas."""
    objetivo = _normalizar_texto(nombre_proyecto)
    if not objetivo:
        return None

    exactas = [v for v in ventanas if v.objeto and _normalizar_texto(v.objeto) == objetivo]
    if len(exactas) == 1:
        return exactas[0]
    if len(exactas) > 1:
        return None

    # Respaldo por contención (mayúsculas/acentos/espacios ya normalizados):
    # el Excel SAP y el propio PDF pueden truncar o puntuar el mismo texto
    # de forma distinta. Exige longitud mínima para no emparejar por una
    # coincidencia trivial de unas pocas palabras.
    candidatas = [
        v for v in ventanas
        if v.objeto and len(_normalizar_texto(v.objeto)) > 30
        and (_normalizar_texto(v.objeto) in objetivo or objetivo in _normalizar_texto(v.objeto))
    ]
    if len(candidatas) == 1:
        return candidatas[0]
    return None


def extraer_campos_pcsp_para_expediente(
    paginas: list[PaginaTexto], nombre_proyecto: Optional[str]
) -> tuple[CamposAnuncioPcsp, Optional[str]]:
    """Punto de entrada para `app.extraccion.orquestador`: igual que
    `extraer_campos_anuncio_pcsp` (número de expediente, matriz, objeto,
    tipo de contrato, nº de lotes -- campos genuinamente del documento
    entero, sin cambios) salvo que, cuando el documento agrupa varios lotes
    bajo "Nº Lote: NNN", `importe_licitacion`/`importe_adjudicacion`/
    `adjudicatario` salen del bloque propio de este expediente (emparejado
    por `nombre_proyecto`) en vez de la cabecera global / el primer bloque.

    Devuelve `(campos, motivo_revision)`. `motivo_revision` no es `None`
    solo cuando el documento SÍ es multi-lote pero no se pudo identificar
    con confianza el bloque de este expediente -- en ese caso `campos` trae
    esos tres campos como `INVALIDADO` (`app.extraccion.invalidado`), nunca
    `None`: el documento SÍ trae un valor para esas etiquetas, solo que no
    se sabe atribuir, así que a diferencia de "no encontrado" (`None`, que
    nunca pisa un dato ya guardado) esto sí debe poder borrar un valor
    previo que viniera de esta misma fuente ambigua en una pasada anterior
    -- ver docstring de `INVALIDADO`."""
    campos = extraer_campos_anuncio_pcsp(paginas)
    ventanas = extraer_ventanas_multi_lote_pcsp(paginas)
    if not ventanas:
        return campos, None

    ventana = emparejar_ventana_por_nombre_proyecto(ventanas, nombre_proyecto)
    if ventana is None:
        numeros = "/".join(sorted(v.numero_lote for v in ventanas))
        motivo = (
            f"el Anuncio de adjudicación agrupa varios lotes en un solo documento (Nº Lote: {numeros}) y no "
            "se pudo identificar con confianza a cuál pertenece este expediente (nombre_proyecto vacío o sin "
            "coincidencia clara con ningún bloque) -- importe de licitación, importe de adjudicación y "
            "adjudicatario de este documento no se usan, para no atribuir el bloque equivocado"
        )
        # `objeto_contrato` también se invalida (no solo los tres importes):
        # sin él, un expediente todavía sin `nombre_proyecto` propio (recién
        # descubierto, sin Excel SAP que lo rellene primero) podría sembrarlo
        # con el objeto del PRIMER lote del documento -- envenenando para
        # siempre el propio ancla con la que este emparejamiento decide
        # (`if not expediente.nombre_proyecto` en el llamador nunca lo
        # vuelve a pisar una vez puesto).
        return replace(
            campos,
            importe_licitacion=INVALIDADO, importe_adjudicacion=INVALIDADO, adjudicatario=INVALIDADO,
            objeto_contrato=INVALIDADO,
        ), motivo

    return (
        replace(
            campos,
            importe_licitacion=ventana.importe_licitacion,
            importe_adjudicacion=ventana.importe_adjudicacion,
            adjudicatario=ventana.adjudicatario,
        ),
        None,
    )
