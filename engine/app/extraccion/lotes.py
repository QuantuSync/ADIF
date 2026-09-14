"""Etapa 2, camino multi-lote (CONTEXTO.md sección 19 y sección 27 — sesión de
identidad de lote): un expediente puede subdividirse en varios lotes, cada
uno con su propia baja, su propio presupuesto, su propio adjudicatario y
—hallazgo de la sesión de identidad de lote— su propio código de
expediente en la Plataforma, distinto del "expediente principal" bajo el
que están archivados los documentos comunes.

Reescrito por completo en la sesión de identidad de lote. La versión
anterior solo reconocía una redacción exacta ("En el LOTE N. ...", la única
que trae el documento real de `6.25/28510.0027`) y fallaba en silencio para
los otros 14 expedientes multi-lote reales del corpus, cada uno con una
redacción distinta: bullet con dos puntos ("- LOTE N: ..., a la empresa"),
numerado ("1º.- Se eleva propuesta de adjudicación en LOTE N..."), con el
título completo repetido antes de cada lote ("SUMINISTRO...N LOTES. Nº
<principal>. LOTE N: ..."), orden baja/importe invertido, etc. Catalogadas
las 15 variantes reales antes de tocar este módulo (sesión de identidad de
lote) — nunca generalizado contra una sola.

Estrategia: en vez de un regex por variante, dos pasadas independientes:

1. **Ventaneo por "LOTE N"**: cada aparición literal de "LOTE" + número en
   el documento (con o sin "En el"/"-"/numeración delante — el ancla mínima
   que comparten las 15 variantes) abre una ventana de texto hasta la
   siguiente aparición de "LOTE N" (cualquier número) o el final del
   documento. Todas las páginas se concatenan antes de buscar: un bloque de
   adjudicación puede partirse por un salto de página (verificado en
   `6.24/28510.0117`, la baja de LOTE 2 queda en la página siguiente a su
   importe).
2. **Sub-extractores genéricos dentro de cada ventana**: baja
   (`app.extraccion.baja.buscar_baja_en_texto`, ya tolera las tres
   redacciones y el orden invertido), importe adjudicado ("Base
   imponible...€", el mismo patrón que ya usa `campos_lc27` para el camino
   de un único lote) y adjudicatario. El orden baja/importe dentro del
   texto deja de importar porque cada sub-extractor busca su propio patrón,
   no una secuencia fija.

Una ventana puede no traer nada más que el número de lote y su código
propio (las apariciones de la cabecera/firma, que solo listan los lotes por
nombre) — se fusiona con las ventanas del cuerpo que sí traen datos,
"primer valor no nulo encontrado gana" por campo, igual que el resto de la
cascada resuelve varias fuentes del mismo hecho.

Un documento de un solo lote (`6.23/28510.0051`, `0066`, `0088`, `0109`,
`0129`: el cuerpo nunca repite "LOTE N", solo la cabecera lo nombra una
vez) no necesita ninguna rama especial: su única ventana ya cubre desde esa
mención hasta el final del documento, así que el sub-extractor de baja e
importe encuentra los mismos datos que ya extraía el camino de un único
lote — simplemente ahora quedan etiquetados con el número de lote real de
la cabecera en vez del sentinela `LOTE_UNICO`.

**Huecos en la numeración, verificados con un caso real
(`6.25/28510.0028`, licitación de "7 LOTES" cuyo LOTE 5 no aparece en
ningún sitio del documento, ni en la cabecera ni en el cuerpo — desierto o
anulado, sin verificar cuál): `lotes_totales_declarados` nunca se usa para
generar identificadores de lote que falten.** Solo cuenta cuántos lotes se
conocen por nombre contra cuántos declara el título, nunca inventa el
hueco.

**Trampa verificada del vocabulario, sesión de identidad de lote:
`6.24/28510.0094` etiqueta su expediente principal como "Nº EXPEDIENTE
MATRIZ" — la palabra "matriz" aquí no tiene relación con el acuerdo marco
de CONTEXTO.md sección 2/20 (`codigo_matriz`/`matriz_expediente_id`), es solo
como esta Propuesta LC.27 concreta llama a "expediente que agrupa los
lotes". Por eso `codigo_principal_declarado` de este módulo NUNCA se
escribe en `expediente.codigo_matriz`: hacerlo reintroduciría el bug de
autorreferencia de la sección 20/21 (una fila etiquetada con el código de
su propia licitación agrupadora, tratada como si fuera una matriz de
acuerdo marco). Es la misma ambigüedad de vocabulario que ya documenta la
sección 27 para la palabra "lote" (categoría de producto en un acuerdo
marco vs. subdivisión de una licitación en contratos concurrentes) —
"matriz" aquí es un tercer uso más de una palabra ya sobrecargada en este
corpus.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from app.extraccion.baja import CODIGO_PROPIO_RE, buscar_baja_en_texto, extraer_baja_declarada
from app.extraccion.campos_pcsp import CODIGO_EXPEDIENTE_RE, CampoAnclado
from app.extraccion.cruce_codigos import normalizar_codigo_expediente
from app.extraccion.normalizacion import parsear_importe_es
from app.extraccion.texto import PaginaTexto
from app.models import TipoDocumento


def _importe_o_none(texto: str) -> Optional[Decimal]:
    """Bloque 3, sesión 2026-09-10: un importe que el regex sí encontró pero
    que no se puede parsear (p.ej. `parsear_numero_es` rechazando una
    agrupación de miles inválida) no debe tumbar el expediente entero
    (CONTEXTO.md sección 12) -- se trata como "no encontrado", igual que si
    el regex no hubiera casado nada. Mismo hallazgo que
    `app.extraccion.campos_pcsp.importe_como_decimal`, expediente
    `6.20/28510.0062` del reproceso completo del bloque 5."""
    try:
        return parsear_importe_es(texto)
    except ValueError:
        return None

# Ancla mínima común a las 15 variantes reales: "LOTE" + número, con o sin
# "En el"/"-"/"▪"/"•"/numeración ("1º.-") delante. Deliberadamente NO exige
# ninguno de esos prefijos -- son justo lo que varía entre documentos.
_LOTE_OCURRENCIA_RE = re.compile(r"LOTE\s*(\d{1,2})\b", re.IGNORECASE)

# Sesión 2026-09-14 (revisión del cliente, continuación): la descripción de un
# lote puede nombrar a OTRO lote -- "LOTE 2: SUR Y, EN CASO DE URGENCIA QUE NO
# PUEDA SER TENDIDA POR EL ADJUDICATARIO DEL LOTE1, NORTE | EXPEDIENTE Nº
# 6.22/28510.0058" (`6.22/28510.0033`; la misma redacción en
# `6.22/28510.0122`). Esa referencia no es el arranque de un bloque: si abre
# ventana, el código propio y la baja de LOTE 2 acaban atribuidos a LOTE 1
# (verificado contra los dos Contratos de cada familia, que dicen lo
# contrario). La referencia no abre ventana, pero el lote queda nombrado.
# Solo esta redacción exacta, la única verificada: un "del lote N" más
# genérico podría ser el arranque real de un bloque en otra plantilla.
_REFERENCIA_A_OTRO_LOTE_RE = re.compile(r"adjudicatario\s+del\s*$", re.IGNORECASE)

# Identidad declarada por un Contrato firmado: "Contrato nº: X" en la cabecera
# y, justo debajo del título de la licitación, "LOTE N: <descripción>"
# (distancia real entre los dos: de 78 a 223 caracteres en todos los
# Contratos del corpus que traen las dos cosas).
_DISTANCIA_MAXIMA_CONTRATO_LOTE = 300

# Código propio del lote: con etiqueta ("EXPEDIENTE Nº", "Nº DE EXPEDIENTE:")
# o, verificado en `6.25/28510.0019` (LOTE 1: "...MATERIAL AUXILIAR.
# 6.25/28510.0039:"), sin ninguna etiqueta -- el código pelado justo después
# de la descripción y un punto. Se busca solo en los primeros ~250
# caracteres de la ventana (la descripción del lote nunca es más larga que
# eso en el corpus real) para no acabar cogiendo un código de otra frase
# más adelante en la misma ventana.
_CODIGO_LOTE_ETIQUETA_RE = re.compile(
    r"(?:EXPEDIENTE\s*N[ºo]\.?:?|N[ºo]\s*DE\s*EXPEDIENTE:?)\s*(" + CODIGO_EXPEDIENTE_RE.pattern + r")",
    re.IGNORECASE,
)
_CODIGO_LOTE_PELADO_RE = re.compile(
    r"^LOTE\s*\d{1,2}\b[^.]{0,160}?\.\s*(" + CODIGO_EXPEDIENTE_RE.pattern + r")(?=[:\s]|$)",
    re.IGNORECASE | re.DOTALL,
)

# Importe adjudicado del lote: mismo patrón que `campos_lc27
# ._IMPORTE_ADJUDICACION_RE`, aplicado a la ventana de un lote en vez de al
# documento entero -- "Base imponible" también aparece como cabecera de
# columna ("(A) Base Imponible IVA (21%) Total con IVA") pero nunca con un
# € inmediatamente después del hueco de separadores, así que no hace falta
# distinguirlas aquí tampoco.
_IMPORTE_ADJUDICACION_LOTE_RE = re.compile(r"[Bb]ase [Ii]mponible[^\d\n]{0,100}([\d.,]+)\s*€")

# Presupuesto de licitación por lote, cuando el documento lo declara en una
# tabla con una fila por lote empezando la línea por "LOTE N" (verificado
# solo en `6.25/28510.0027`, CONTEXTO.md sección 19) -- no generalizado más
# allá de esta forma exacta porque ningún otro de los 15 expedientes trae
# esta tabla (docs/analisis-corpus.md, sesión de identidad de lote): sin
# ella, `importe_licitacion` del lote queda `None`, nunca inventado.
_TABLA_LICITACION_LOTE_RE = re.compile(r"^LOTE\s*(\d{1,2})\s+([\d.,]+)\s*€", re.MULTILINE)

# Adjudicatario: dato secundario (CONTEXTO.md sección 7, "no lo exige").
# Ampliado en la sesión de identidad de lote para cubrir "a la empresa" /
# "a las empresas", "con NIF" / "con CIF" (`6.23/28510.0051` usa CIF, el
# resto NIF) y con o sin dos puntos -- si no casa con ninguna variante, se
# deja en `None` sin bloquear baja ni importe.
_ADJUDICATARIO_RE = re.compile(
    r"a\s+la[s]?\s+empresa[s]?:?\s*(.+?),?\s*con\s+(?:NIF|CIF)", re.IGNORECASE | re.DOTALL
)

# "N LOTES" o "(N LOTES)" del título -- el total que declara la licitación,
# nunca una secuencia que se vaya a generar (ver docstring del módulo). El
# número y "LOTES" pueden partirse en líneas de PDF distintas
# (`6.24/28510.0117`: "(3\nLOTES)"), así que `\s*` sí cruza saltos de línea
# -- pero el lookahead negativo `(?!\s*\d)` es imprescindible: bug real
# encontrado verificando contra `6.24/28510.0088`, cuyo código de
# expediente termina en "...0088" justo antes de "LOTE 1:" (el nombre real
# del primer lote, en su propia línea) -- sin el lookahead, el regex leía
# "88" + salto de línea + "LOTE" y devolvía 88 lotes. El lookahead exige
# que tras "LOTE(S)" NO venga inmediatamente un número (que delataría una
# mención de "LOTE N" concreto, no el total de la licitación).
_LOTES_TOTALES_RE = re.compile(r"\(?\s*(\d{1,2})\s*LOTES?\b(?!\s*\d)\)?", re.IGNORECASE)

# Expediente principal: cuatro etiquetas reales distintas para el mismo
# concepto, dos de ellas con el orden de las palabras invertido entre sí
# (`6.23/28510.0109`: "EXPEDIENTE ORIGEN Nº"; `6.24/28510.0203`: "Nº
# EXPEDIENTE ORIGEN:"). "N[ºo] EXPEDIENTE MATRIZ" (`6.24/28510.0094`) es la
# trampa de vocabulario del docstring del módulo -- se captura aquí solo
# para contraste/trazabilidad, nunca para `expediente.codigo_matriz`.
_EXPEDIENTE_PRINCIPAL_RE = re.compile(
    r"EXPEDIENTE\s+PRINCIPAL\s+N[ºo]\.?:?\s*(" + CODIGO_EXPEDIENTE_RE.pattern + r")"
    r"|EXPEDIENTE\s+ORIGEN\s+N[ºo]\.?:?\s*(" + CODIGO_EXPEDIENTE_RE.pattern + r")"
    r"|N[ºo]\s+EXPEDIENTE\s+ORIGEN:?\s*(" + CODIGO_EXPEDIENTE_RE.pattern + r")"
    r"|N[ºo]\s+EXPEDIENTE\s+MATRIZ:?\s*(" + CODIGO_EXPEDIENTE_RE.pattern + r")",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class LoteDeclarado:
    identificador: str
    baja: Optional[Decimal]
    importe_licitacion: Optional[Decimal]
    importe_adjudicacion: Optional[Decimal]
    adjudicatario: Optional[str]
    codigo_expediente_lote: Optional[str]
    pagina: int
    fragmento: str
    # Documento del que sale el lote cuando no es el documento de lotes
    # elegido por el orquestador (un lote que solo conoce su Contrato).
    documento_id: Optional[int] = None


@dataclass(frozen=True)
class IdentidadContrato:
    """Lo que un Contrato firmado dice de sí mismo: qué lote es y con qué
    código de expediente ("Contrato nº"). CONTEXTO.md sección 27, relación
    "Contrato ⟷ lote": el "Contrato nº" coincide siempre con el
    "EXPEDIENTE Nº" que el lote declara en su adjudicación."""
    identificador: str
    codigo_expediente_lote: str
    baja: Optional[Decimal]
    pagina: int
    fragmento: str


@dataclass(frozen=True)
class ResultadoLotes:
    lotes: list[LoteDeclarado]
    # Del "N LOTES" del título -- puede ser mayor que `len(lotes)` (algunos
    # lotes declarados por número no traen ni baja ni importe en ningún
    # documento disponible, o la numeración tiene huecos, sección 27).
    lotes_totales_declarados: Optional[int]
    # Solo para contraste/trazabilidad -- nunca se escribe en
    # `expediente.codigo_matriz` (ver docstring del módulo).
    codigo_principal_declarado: Optional[CampoAnclado]


def _texto_y_paginas(paginas: list[PaginaTexto]) -> tuple[str, list[tuple[int, int]]]:
    """Concatena todas las páginas en un único texto (un bloque de
    adjudicación puede partirse por un salto de página) y devuelve, junto
    al texto, los límites `(offset_inicio, numero_pagina)` de cada página
    para poder anclar cada hallazgo a la página donde empieza."""
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


def _codigo_propio_lote(ventana: str) -> Optional[str]:
    m = _CODIGO_LOTE_ETIQUETA_RE.search(ventana[:300])
    if m:
        return m.group(1)
    m = _CODIGO_LOTE_PELADO_RE.match(ventana[:250])
    if m:
        return m.group(1)
    return None


def _lotes_totales_declarados(texto: str) -> Optional[int]:
    m = _LOTES_TOTALES_RE.search(texto)
    if not m:
        return None
    return int(m.group(1))


def _codigo_principal_declarado(texto: str) -> Optional[CampoAnclado]:
    m = _EXPEDIENTE_PRINCIPAL_RE.search(texto)
    if not m:
        return None
    valor = next(g for g in m.groups() if g is not None)
    return CampoAnclado(valor=valor, pagina=0, fragmento=m.group(0).strip())


def _entrada_vacia(offset: int) -> dict:
    return {
        "baja": None, "fragmento_baja": None,
        "importe_adjudicacion": None,
        "adjudicatario": None,
        "codigo_expediente_lote": None,
        "offset": offset,
    }


def _es_referencia_a_otro_lote(texto: str, inicio: int) -> bool:
    return _REFERENCIA_A_OTRO_LOTE_RE.search(texto[max(0, inicio - 40):inicio]) is not None


def extraer_identidad_contrato(paginas: list[PaginaTexto]) -> Optional[IdentidadContrato]:
    """`None` si el documento no declara "Contrato nº: X" seguido de cerca
    por un "LOTE N" (un contrato de un expediente sin lotes, la mayoría).
    Solo la cabecera (tres primeras páginas, mismo criterio que
    `extraer_codigo_propio_documento`): en el cuerpo, un Contrato puede
    nombrar otro lote de pasada -- incluso con errata, verificado en
    `6.21/28510.0016` ("Ascendiendo el importe de licitación del lote 1 a
    15.000,00 €" en el Contrato del LOTE 2)."""
    for pagina in paginas[:3]:
        m = CODIGO_PROPIO_RE.search(pagina.texto)
        if not m:
            continue
        m_lote = _LOTE_OCURRENCIA_RE.search(pagina.texto, m.end(), m.end() + _DISTANCIA_MAXIMA_CONTRATO_LOTE)
        if m_lote is None:
            return None
        baja = extraer_baja_declarada(paginas, tipo_documento=TipoDocumento.contrato)
        return IdentidadContrato(
            identificador=m_lote.group(1),
            codigo_expediente_lote=m.group(1),
            baja=baja.baja if baja is not None else None,
            pagina=pagina.numero,
            fragmento=(baja.fragmento if baja is not None else pagina.texto[m.start():m_lote.end()]).strip(),
        )
    return None


def extraer_lotes_declarados(
    paginas: list[PaginaTexto], lote_por_codigo: Optional[dict[str, str]] = None
) -> ResultadoLotes:
    """Lista vacía si el documento no menciona ningún "LOTE N" por su
    nombre -- el llamador (orquestador) cae entonces al camino de un único
    lote implícito (CONTEXTO.md, sección 19, "un único lote implícito").

    `lote_por_codigo` (código de expediente normalizado -> identificador de
    lote, de los Contratos firmados del expediente): cuando una ventana
    declara un código propio que un Contrato ata a OTRO número de lote, el
    número de la ventana es una errata y la ventana se atribuye al lote del
    Contrato. Caso real: la Resolución del LOTE 2 de tornillería
    (`6.21/28510.0016`) lo llama "LOTE 2" en la cabecera y en la firma, pero
    "LOTE 1: ANCLAJES DE SEGURIDAD. EXPEDIENTE Nº: 6.21/28510.0016" en el
    RESUELVE -- sin esto, la baja y el importe del LOTE 2 se guardaban en el
    LOTE 1, y los dos lotes quedaban ligados a `0016`."""
    lote_por_codigo = lote_por_codigo or {}
    texto, limites = _texto_y_paginas(paginas)
    ocurrencias = []
    referencias = []
    for m in _LOTE_OCURRENCIA_RE.finditer(texto):
        (referencias if _es_referencia_a_otro_lote(texto, m.start()) else ocurrencias).append(m)
    if not ocurrencias:
        return ResultadoLotes(lotes=[], lotes_totales_declarados=None, codigo_principal_declarado=None)

    importes_licitacion = {
        m.group(1): _importe_o_none(m.group(2)) for m in _TABLA_LICITACION_LOTE_RE.finditer(texto)
    }

    # Acumulador por identificador: primer valor no nulo encontrado gana,
    # en el orden en que aparecen las ventanas (una ventana de cabecera que
    # solo trae el código propio no debe borrar la baja/importe que ya
    # encontró una ventana anterior del cuerpo, ni al revés).
    datos: dict[str, dict] = {}
    orden: list[str] = []

    for i, m in enumerate(ocurrencias):
        identificador = m.group(1)
        fin = ocurrencias[i + 1].start() if i + 1 < len(ocurrencias) else len(texto)
        ventana = texto[m.start():fin]
        codigo_ventana = _codigo_propio_lote(ventana)
        if codigo_ventana is not None:
            identificador_contrato = lote_por_codigo.get(normalizar_codigo_expediente(codigo_ventana))
            if identificador_contrato is not None and identificador_contrato != identificador:
                # El número de la errata sigue nombrando un lote que existe
                # (el documento lo menciona): se conserva, sin los datos de
                # esta ventana, para que su propio Contrato lo complete.
                if identificador not in datos:
                    datos[identificador] = _entrada_vacia(m.start())
                    orden.append(identificador)
                identificador = identificador_contrato

        if identificador not in datos:
            datos[identificador] = _entrada_vacia(m.start())
            orden.append(identificador)
        entrada = datos[identificador]

        if entrada["codigo_expediente_lote"] is None:
            entrada["codigo_expediente_lote"] = codigo_ventana

        if entrada["baja"] is None:
            baja_encontrada = buscar_baja_en_texto(ventana)
            if baja_encontrada is not None:
                entrada["baja"] = baja_encontrada.baja
                entrada["fragmento_baja"] = baja_encontrada.fragmento

        if entrada["importe_adjudicacion"] is None:
            m_imp = _IMPORTE_ADJUDICACION_LOTE_RE.search(ventana)
            if m_imp:
                entrada["importe_adjudicacion"] = _importe_o_none(m_imp.group(1))

        if entrada["adjudicatario"] is None:
            m_adj = _ADJUDICATARIO_RE.search(ventana)
            if m_adj:
                entrada["adjudicatario"] = re.sub(r"\s+", " ", m_adj.group(1)).strip()

    # Una referencia cruzada no abre ventana, pero sí dice que ese lote
    # existe: queda nombrado, sin datos (`6.22/28510.0122`: la Propuesta del
    # LOTE 2 es el único documento de lotes, y solo nombra el LOTE 1 así; su
    # código y su baja los completa su Contrato, en el orquestador).
    for m in referencias:
        if m.group(1) not in datos:
            datos[m.group(1)] = _entrada_vacia(m.start())
            orden.append(m.group(1))

    lotes = [
        LoteDeclarado(
            identificador=identificador,
            baja=datos[identificador]["baja"],
            importe_licitacion=importes_licitacion.get(identificador),
            importe_adjudicacion=datos[identificador]["importe_adjudicacion"],
            adjudicatario=datos[identificador]["adjudicatario"],
            codigo_expediente_lote=datos[identificador]["codigo_expediente_lote"],
            pagina=_pagina_en_offset(limites, datos[identificador]["offset"]),
            fragmento=(datos[identificador]["fragmento_baja"] or "").strip() or f"LOTE {identificador}",
        )
        for identificador in orden
    ]
    return ResultadoLotes(
        lotes=lotes,
        lotes_totales_declarados=_lotes_totales_declarados(texto),
        codigo_principal_declarado=_codigo_principal_declarado(texto),
    )
