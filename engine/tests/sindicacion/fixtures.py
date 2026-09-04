"""Fabrica ZIPs de sindicación sintéticos (namespaces y forma reales,
verificados contra el ZIP real de agosto 2024 en la sesión de mantenimiento
automático — CLAUDE.md sección 24) para no depender de la red en los tests."""
from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Optional

_FEED_HEADER = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:cbc-place-ext="urn:dgpe:names:draft:codice-place-ext:schema:xsd:CommonBasicComponents-2"
      xmlns:cbc="urn:dgpe:names:draft:codice:schema:xsd:CommonBasicComponents-2"
      xmlns:cac="urn:dgpe:names:draft:codice:schema:xsd:CommonAggregateComponents-2"
      xmlns:cac-place-ext="urn:dgpe:names:draft:codice-place-ext:schema:xsd:CommonAggregateComponents-2">
    <id>https://contrataciondelestado.es/sindicacion/sindicacion_643/prueba.atom</id>
    <title>feed de prueba</title>
    <updated>2024-08-31T00:00:00.000+02:00</updated>
"""
_FEED_FOOTER = "</feed>\n"


def entrada_xml(
    codigo: str,
    organo: str,
    estado: str,
    updated: str,
    lic_sin: str,
    lic_con: str,
    adj_sin: Optional[str] = None,
    adj_con: Optional[str] = None,
    adjudicatario: Optional[str] = None,
    lotes: Optional[list[tuple[str, str, str, str]]] = None,
) -> str:
    """`lotes`: lista de (identificador, nombre, importe_sin, importe_con)."""
    lotes_xml = ""
    for identificador, nombre, sin, con in (lotes or []):
        lotes_xml += f"""
            <cac:ProcurementProjectLot>
                <cbc:ID schemeName="ID_LOTE">{identificador}</cbc:ID>
                <cac:ProcurementProject>
                    <cbc:Name>{nombre}</cbc:Name>
                    <cac:BudgetAmount>
                        <cbc:TotalAmount currencyID="EUR">{con}</cbc:TotalAmount>
                        <cbc:TaxExclusiveAmount currencyID="EUR">{sin}</cbc:TaxExclusiveAmount>
                    </cac:BudgetAmount>
                </cac:ProcurementProject>
            </cac:ProcurementProjectLot>"""

    tender_result_xml = ""
    if adj_sin is not None:
        tender_result_xml = f"""
            <cac:TenderResult>
                <cac:WinningParty>
                    <cac:PartyName><cbc:Name>{adjudicatario or "Adjudicatario de prueba"}</cbc:Name></cac:PartyName>
                </cac:WinningParty>
                <cac:AwardedTenderedProject>
                    <cac:LegalMonetaryTotal>
                        <cbc:TaxExclusiveAmount currencyID="EUR">{adj_sin}</cbc:TaxExclusiveAmount>
                        <cbc:PayableAmount currencyID="EUR">{adj_con}</cbc:PayableAmount>
                    </cac:LegalMonetaryTotal>
                </cac:AwardedTenderedProject>
            </cac:TenderResult>"""

    return f"""
    <entry>
        <id>https://contrataciondelestado.es/sindicacion/licitacionesPerfilContratante/{hash(codigo + updated) % 10_000_000}</id>
        <title>Expediente de prueba {codigo}</title>
        <updated>{updated}</updated>
        <cac-place-ext:ContractFolderStatus>
            <cbc:ContractFolderID>{codigo}</cbc:ContractFolderID>
            <cbc-place-ext:ContractFolderStatusCode>{estado}</cbc-place-ext:ContractFolderStatusCode>
            <cac-place-ext:LocatedContractingParty>
                <cac:Party>
                    <cac:PartyName><cbc:Name>{organo}</cbc:Name></cac:PartyName>
                </cac:Party>
            </cac-place-ext:LocatedContractingParty>
            <cac:ProcurementProject>
                <cbc:Name>Objeto de prueba {codigo}</cbc:Name>
                <cac:BudgetAmount>
                    <cbc:TotalAmount currencyID="EUR">{lic_con}</cbc:TotalAmount>
                    <cbc:TaxExclusiveAmount currencyID="EUR">{lic_sin}</cbc:TaxExclusiveAmount>
                </cac:BudgetAmount>
            </cac:ProcurementProject>{lotes_xml}{tender_result_xml}
        </cac-place-ext:ContractFolderStatus>
    </entry>
"""


def construir_zip(destino: Path, entradas: list[str], nombre_atom: str = "prueba.atom") -> Path:
    contenido = _FEED_HEADER + "".join(entradas) + _FEED_FOOTER
    with zipfile.ZipFile(destino, "w") as zf:
        zf.writestr(nombre_atom, contenido.encode("utf-8"))
    return destino
