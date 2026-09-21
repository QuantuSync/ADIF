"""Sesión 2026-09-21 (tercera parte), bloque 2: el anejo que trae los cuadros
de todos los lotes bajo su rótulo «LOTE N», en un expediente que es uno de
esos lotes según el bloque «Nº Lote» de su anuncio. Solo se queda con el
suyo; los demás se conservan sin lote, con su motivo."""
from types import SimpleNamespace

from app.extraccion.orquestador import LOTE_UNICO, _quedarse_con_el_lote_propio


def _linea(identificador, clave):
    return {"identificador_lote": identificador, "clave_linea": clave, "clave_huerfana_hipotetica": f"{clave}@p1y2",
            "motivo_revision": None, "baja_lote": None, "precio_adjudicado": None}


def test_se_queda_con_su_lote_y_conserva_las_demas_sin_lote():
    resultado = SimpleNamespace(lineas=[_linea("1", "A"), _linea("2", "B"), _linea("3", "C"), _linea(None, "D")])

    _quedarse_con_el_lote_propio(resultado, "2", LOTE_UNICO)

    otra_1, propia, otra_3, criterios = resultado.lineas
    assert propia["identificador_lote"] == LOTE_UNICO and propia["clave_linea"] == "B"
    assert propia["motivo_revision"] is None
    for otra, numero in ((otra_1, "1"), (otra_3, "3")):
        assert otra["identificador_lote"] is None
        assert otra["clave_linea"] == otra["clave_huerfana_hipotetica"]
        assert otra["motivo_revision"].startswith(f"tabla del LOTE {numero} de la licitación: este expediente es su lote 2")
    assert criterios["identificador_lote"] is None and criterios["motivo_revision"] is None
