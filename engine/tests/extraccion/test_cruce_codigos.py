import openpyxl
import pytest

from app.extraccion.cruce_codigos import cruzar_codigo_proyecto


@pytest.fixture
def excel_codigos(tmp_path):
    ruta = tmp_path / "Codigos_de_proyecto.xlsx"
    libro = openpyxl.Workbook()
    hoja = libro.active
    hoja.append(["Nº Interno", "Nº Expediente", "MATRIZ", "ESPECIALIDAD/DISCIPLINA", "DESCRIPCIÓN"])
    hoja.append([24001, "6.24/28510.0128", None, "Señalización", "Equipos de medida"])
    # Fila con espacios sobrantes (CLAUDE.md sección 8): un cruce exacto sin
    # normalizar fallaría en silencio.
    hoja.append([24038, "6.25/28510.0085 ", "6.25/28510.0028", "Vía", "Balasto"])
    libro.save(ruta)
    return str(ruta)


def test_cruza_por_numero_de_expediente_exacto(excel_codigos):
    resultado = cruzar_codigo_proyecto(excel_codigos, "6.24/28510.0128")

    assert resultado.cruzado is True
    assert resultado.codigo_interno == "24001"
    assert resultado.codigo_proyecto == "6.24/28510.0128"
    assert resultado.codigo_matriz is None


def test_recorta_espacios_sobrantes_antes_de_comparar(excel_codigos):
    resultado = cruzar_codigo_proyecto(excel_codigos, "6.25/28510.0085")

    assert resultado.cruzado is True
    assert resultado.codigo_interno == "24038"
    assert resultado.codigo_matriz == "6.25/28510.0028"


def test_cruza_por_matriz_cuando_no_hay_por_numero_de_expediente(excel_codigos):
    resultado = cruzar_codigo_proyecto(excel_codigos, "codigo-inexistente", codigo_matriz="6.25/28510.0028")

    assert resultado.cruzado is True
    assert resultado.codigo_interno == "24038"


def test_no_cruza_no_inventa_nada(excel_codigos):
    resultado = cruzar_codigo_proyecto(excel_codigos, "6.99/00000.0000")

    assert resultado.cruzado is False
    assert resultado.codigo_interno is None
    assert resultado.codigo_proyecto is None
    assert resultado.codigo_matriz is None
