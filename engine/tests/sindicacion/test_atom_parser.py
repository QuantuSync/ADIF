"""Bloque 2 (CLAUDE.md sección 24): parseo del XML CODICE de sindicación,
contra un ZIP sintético con la misma forma que el real (verificado en la
sesión de mantenimiento automático contra el ZIP real de agosto 2024)."""
from decimal import Decimal

from app.sindicacion.atom_parser import entradas_de_zip
from tests.sindicacion.fixtures import construir_zip, entrada_xml


def test_parsea_campos_basicos(tmp_path):
    zip_path = construir_zip(
        tmp_path / "prueba.zip",
        [
            entrada_xml(
                "6.24/28510.0088", "ADIF - Presidencia", "PUB", "2024-08-05T15:07:29.158+02:00",
                "2000000", "2420000",
                lotes=[
                    ("001", "Lote 1", "1000000", "1210000"),
                    ("002", "Lote 2", "1000000", "1210000"),
                ],
            ),
        ],
    )
    entradas = list(entradas_de_zip(zip_path))
    assert len(entradas) == 1
    e = entradas[0]
    assert e.codigo_expediente == "6.24/28510.0088"
    assert e.departamento == "28510"
    assert e.estado_pcsp == "PUB"
    assert e.organo_contratacion == "ADIF - Presidencia"
    assert e.importe_licitacion_sin_impuestos == Decimal("2000000")
    assert e.importe_licitacion_con_impuestos == Decimal("2420000")
    assert e.importe_adjudicacion_sin_impuestos is None
    assert len(e.lotes) == 2
    assert e.lotes[0].identificador == "001"
    assert e.lotes[0].importe_licitacion_sin_impuestos == Decimal("1000000")


def test_parsea_adjudicacion_y_suma_varios_tender_result(tmp_path):
    """Verificado contra el expediente real 6.24/28510.0103 (CLAUDE.md
    sección 17.1): licitación y adjudicación pueden ser el mismo número."""
    zip_path = construir_zip(
        tmp_path / "prueba.zip",
        [
            entrada_xml(
                "6.24/28510.0103", "ADIF - Presidencia", "ADJ", "2024-08-14T10:44:21.250+02:00",
                "145100", "175571", adj_sin="145100", adj_con="175571", adjudicatario="SIEL CONFECCIONES SL",
            ),
        ],
    )
    e = list(entradas_de_zip(zip_path))[0]
    assert e.importe_adjudicacion_sin_impuestos == Decimal("145100")
    assert e.importe_adjudicacion_con_impuestos == Decimal("175571")
    assert e.adjudicatario == "SIEL CONFECCIONES SL"


def test_departamento_none_si_codigo_no_encaja():
    from app.sindicacion.atom_parser import EntradaSindicacion
    from datetime import datetime, timezone

    e = EntradaSindicacion(
        codigo_expediente="310/2024", actualizado_en=datetime.now(timezone.utc), estado_pcsp="PUB",
        organo_contratacion="Alcaldía de Cistierna", titulo=None,
        importe_licitacion_sin_impuestos=None, importe_licitacion_con_impuestos=None,
        importe_adjudicacion_sin_impuestos=None, importe_adjudicacion_con_impuestos=None,
        adjudicatario=None,
    )
    assert e.departamento is None


def test_filtro_se_aplica_antes_de_emitir(tmp_path):
    zip_path = construir_zip(
        tmp_path / "prueba.zip",
        [
            entrada_xml("6.24/28510.0088", "ADIF - Presidencia", "PUB", "2024-08-01T00:00:00+02:00", "1", "1"),
            entrada_xml("310/2024", "Alcaldía de Cistierna", "PUB", "2024-08-01T00:00:00+02:00", "1", "1"),
        ],
    )
    filtrado = list(
        entradas_de_zip(zip_path, filtro=lambda e: e.organo_contratacion and "adif" in e.organo_contratacion.lower())
    )
    assert len(filtrado) == 1
    assert filtrado[0].codigo_expediente == "6.24/28510.0088"


def test_varios_ficheros_atom_en_el_mismo_zip(tmp_path):
    import zipfile

    from tests.sindicacion.fixtures import _FEED_FOOTER, _FEED_HEADER

    with zipfile.ZipFile(tmp_path / "prueba.zip", "w") as zf:
        zf.writestr(
            "a.atom",
            (_FEED_HEADER + entrada_xml("6.24/28510.0001", "ADIF", "PUB", "2024-08-01T00:00:00+02:00", "1", "1") + _FEED_FOOTER),
        )
        zf.writestr(
            "b.atom",
            (_FEED_HEADER + entrada_xml("6.24/28510.0002", "ADIF", "PUB", "2024-08-02T00:00:00+02:00", "1", "1") + _FEED_FOOTER),
        )
    codigos = {e.codigo_expediente for e in entradas_de_zip(tmp_path / "prueba.zip")}
    assert codigos == {"6.24/28510.0001", "6.24/28510.0002"}
