"""Bloque 2, descubrimiento por sindicación (CONTEXTO.md sección 24): parseo
incremental del XML CODICE que trae cada ZIP mensual
(`licitacionesPerfilesContratanteCompleto3_AAAAMM.zip`, sindicación 643).

Verificado contra el ZIP real de agosto 2024 (122 MB comprimidos, 89
ficheros `.atom` encadenados por `<link rel="next">`, ~1,3 GB de XML sin
comprimir, ~29.500 entradas únicas): "ficheros ATOM encadenados" significa
que el propio ZIP ya trae todas las páginas de la cadena, no que haga falta
seguir el enlace `next` por HTTP — se procesan los `.atom` del ZIP, en
cualquier orden, sin ninguna llamada de red adicional.

Ni el ZIP entero ni un `.atom` individual (10-18 MB cada uno) se cargan
enteros en memoria: `zipfile.ZipFile.open()` da un fichero en streaming por
miembro, y `xml.etree.ElementTree.iterparse` sobre ese stream procesa una
`<entry>` a la vez, liberándola (`clear()`) en cuanto se ha extraído — el
truco estándar de iterparse con memoria acotada.
"""
from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Callable, Iterator, Optional
from xml.etree import ElementTree as ET

ATOM_NS = "http://www.w3.org/2005/Atom"
CBC_NS = "urn:dgpe:names:draft:codice:schema:xsd:CommonBasicComponents-2"
CBC_PLACE_NS = "urn:dgpe:names:draft:codice-place-ext:schema:xsd:CommonBasicComponents-2"
CAC_NS = "urn:dgpe:names:draft:codice:schema:xsd:CommonAggregateComponents-2"
CAC_PLACE_NS = "urn:dgpe:names:draft:codice-place-ext:schema:xsd:CommonAggregateComponents-2"

_TAG_ENTRY = f"{{{ATOM_NS}}}entry"

# Formato del departamento dentro del código de expediente ("6.24/28510.0088"
# -> "28510"): mismo patrón que documenta CONTEXTO.md sección 20 para
# distinguir expediente de matriz, aplicado aquí a la parte "28510".
_DEPARTAMENTO_RE = re.compile(r"^\d+\.\d+/(\d+)\.")


@dataclass(frozen=True)
class LoteSindicado:
    identificador: Optional[str]
    nombre: Optional[str]
    importe_licitacion_sin_impuestos: Optional[Decimal]
    importe_licitacion_con_impuestos: Optional[Decimal]

    def to_dict(self) -> dict:
        return {
            "identificador": self.identificador,
            "nombre": self.nombre,
            "importe_licitacion_sin_impuestos": (
                str(self.importe_licitacion_sin_impuestos)
                if self.importe_licitacion_sin_impuestos is not None
                else None
            ),
            "importe_licitacion_con_impuestos": (
                str(self.importe_licitacion_con_impuestos)
                if self.importe_licitacion_con_impuestos is not None
                else None
            ),
        }


@dataclass(frozen=True)
class EntradaSindicacion:
    codigo_expediente: str
    actualizado_en: datetime
    estado_pcsp: Optional[str]
    organo_contratacion: Optional[str]
    titulo: Optional[str]
    importe_licitacion_sin_impuestos: Optional[Decimal]
    importe_licitacion_con_impuestos: Optional[Decimal]
    importe_adjudicacion_sin_impuestos: Optional[Decimal]
    importe_adjudicacion_con_impuestos: Optional[Decimal]
    adjudicatario: Optional[str]
    lotes: list[LoteSindicado] = field(default_factory=list)

    @property
    def departamento(self) -> Optional[str]:
        m = _DEPARTAMENTO_RE.match(self.codigo_expediente)
        return m.group(1) if m else None


def _decimal(texto: Optional[str]) -> Optional[Decimal]:
    """Los importes del XML CODICE ya vienen en formato máquina (punto
    decimal, sin separador de miles ni símbolo de moneda) — a diferencia del
    formato español de los PDF (CONTEXTO.md sección 8), aquí basta `Decimal`
    directo, nunca `parsear_importe_es`."""
    if texto is None:
        return None
    texto = texto.strip()
    if not texto:
        return None
    try:
        return Decimal(texto)
    except InvalidOperation:
        return None


def _parsear_fecha(texto: Optional[str]) -> Optional[datetime]:
    if not texto:
        return None
    try:
        return datetime.fromisoformat(texto)
    except ValueError:
        return None


def _texto_organo(status: ET.Element) -> Optional[str]:
    located = status.find(f"{{{CAC_PLACE_NS}}}LocatedContractingParty")
    if located is None:
        return None
    party = located.find(f"{{{CAC_NS}}}Party")
    if party is None:
        return None
    return party.findtext(f"{{{CAC_NS}}}PartyName/{{{CBC_NS}}}Name")


def _lotes(status: ET.Element) -> list[LoteSindicado]:
    lotes = []
    for lote_el in status.findall(f"{{{CAC_NS}}}ProcurementProjectLot"):
        identificador = lote_el.findtext(f"{{{CBC_NS}}}ID")
        proyecto = lote_el.find(f"{{{CAC_NS}}}ProcurementProject")
        nombre = proyecto.findtext(f"{{{CBC_NS}}}Name") if proyecto is not None else None
        lic_sin = lic_con = None
        if proyecto is not None:
            lic_sin = _decimal(proyecto.findtext(f"{{{CAC_NS}}}BudgetAmount/{{{CBC_NS}}}TaxExclusiveAmount"))
            lic_con = _decimal(proyecto.findtext(f"{{{CAC_NS}}}BudgetAmount/{{{CBC_NS}}}TotalAmount"))
        lotes.append(LoteSindicado(identificador, nombre, lic_sin, lic_con))
    return lotes


def _adjudicacion(status: ET.Element) -> tuple[Optional[Decimal], Optional[Decimal], Optional[str]]:
    """Suma los importes de todos los `cac:TenderResult` del expediente (0,
    1 o varios — un expediente multi-lote puede traer uno por lote, sin
    verificar contra un ejemplo real de este corpus): agregado a nivel de
    expediente, no por lote — el contraste de este bloque (CONTEXTO.md sección
    24) compara contra `Expediente.importe_adjudicacion`, que tampoco baja a
    nivel de lote."""
    total_sin = total_con = None
    adjudicatarios: list[str] = []
    for resultado in status.findall(f"{{{CAC_NS}}}TenderResult"):
        ganador = resultado.find(f"{{{CAC_NS}}}WinningParty")
        if ganador is not None:
            nombre = ganador.findtext(f"{{{CAC_NS}}}PartyName/{{{CBC_NS}}}Name")
            if nombre and nombre not in adjudicatarios:
                adjudicatarios.append(nombre)
        adjudicado = resultado.find(f"{{{CAC_NS}}}AwardedTenderedProject/{{{CAC_NS}}}LegalMonetaryTotal")
        if adjudicado is not None:
            sin = _decimal(adjudicado.findtext(f"{{{CBC_NS}}}TaxExclusiveAmount"))
            con = _decimal(adjudicado.findtext(f"{{{CBC_NS}}}PayableAmount"))
            if sin is not None:
                total_sin = sin if total_sin is None else total_sin + sin
            if con is not None:
                total_con = con if total_con is None else total_con + con
    adjudicatario = "; ".join(adjudicatarios) if adjudicatarios else None
    return total_sin, total_con, adjudicatario


def _parsear_entrada(entry: ET.Element) -> Optional[EntradaSindicacion]:
    status = entry.find(f"{{{CAC_PLACE_NS}}}ContractFolderStatus")
    if status is None:
        return None
    codigo = status.findtext(f"{{{CBC_NS}}}ContractFolderID")
    if not codigo:
        return None
    actualizado_en = _parsear_fecha(entry.findtext(f"{{{ATOM_NS}}}updated"))
    if actualizado_en is None:
        return None
    estado = status.findtext(f"{{{CBC_PLACE_NS}}}ContractFolderStatusCode")
    proyecto = status.find(f"{{{CAC_NS}}}ProcurementProject")
    titulo = proyecto.findtext(f"{{{CBC_NS}}}Name") if proyecto is not None else entry.findtext(
        f"{{{ATOM_NS}}}title"
    )
    lic_sin = lic_con = None
    if proyecto is not None:
        lic_sin = _decimal(proyecto.findtext(f"{{{CAC_NS}}}BudgetAmount/{{{CBC_NS}}}TaxExclusiveAmount"))
        lic_con = _decimal(proyecto.findtext(f"{{{CAC_NS}}}BudgetAmount/{{{CBC_NS}}}TotalAmount"))
    adj_sin, adj_con, adjudicatario = _adjudicacion(status)
    return EntradaSindicacion(
        codigo_expediente=codigo.strip(),
        actualizado_en=actualizado_en,
        estado_pcsp=estado.strip() if estado else None,
        organo_contratacion=_texto_organo(status),
        titulo=titulo.strip() if titulo else None,
        importe_licitacion_sin_impuestos=lic_sin,
        importe_licitacion_con_impuestos=lic_con,
        importe_adjudicacion_sin_impuestos=adj_sin,
        importe_adjudicacion_con_impuestos=adj_con,
        adjudicatario=adjudicatario,
        lotes=_lotes(status),
    )


def _entradas_de_stream(stream, filtro: Optional[Callable[[EntradaSindicacion], bool]]) -> Iterator[EntradaSindicacion]:
    contexto = ET.iterparse(stream, events=("start", "end"))
    _, raiz = next(contexto)
    for evento, elemento in contexto:
        if evento != "end" or elemento.tag != _TAG_ENTRY:
            continue
        entrada = _parsear_entrada(elemento)
        elemento.clear()
        # Trueco estándar de iterparse con memoria acotada: libera también
        # los hermanos ya procesados que cuelgan de la raíz (CONTEXTO.md
        # bloque 2, punto 1: "procesamiento incremental, no cargarlo entero
        # en memoria" — sin esto, el árbol entero del feed se acumula igual
        # aunque cada <entry> se limpie a sí misma).
        raiz.clear()
        if entrada is not None and (filtro is None or filtro(entrada)):
            yield entrada


def entradas_de_zip(
    ruta_zip: Path, filtro: Optional[Callable[[EntradaSindicacion], bool]] = None
) -> Iterator[EntradaSindicacion]:
    """Recorre todos los miembros `.atom` del ZIP, en streaming: ni el ZIP
    ni ningún miembro se cargan enteros en memoria (ver docstring del
    módulo). `filtro`, si se da, se aplica antes de emitir cada entrada —
    para que el llamador (app.sindicacion.descubrimiento) nunca tenga que
    materializar las entradas que no le interesan."""
    with zipfile.ZipFile(ruta_zip) as zf:
        for nombre in zf.namelist():
            if not nombre.endswith(".atom"):
                continue
            with zf.open(nombre) as stream:
                yield from _entradas_de_stream(stream, filtro)
