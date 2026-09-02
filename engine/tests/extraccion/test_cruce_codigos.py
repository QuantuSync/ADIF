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


def test_expediente_que_es_matriz_de_otra_fila_no_se_pone_su_propia_matriz(excel_codigos):
    # 6.25/28510.0028 nunca aparece como "Nº Expediente": solo es la MATRIZ
    # de la fila de 6.25/28510.0085 (acuerdo marco del que cuelga ese
    # pedido). Cruzar directamente por ese código (sección 3: "3 como
    # MATRIZ") debe traer su Nº Interno, pero NO debe devolver
    # codigo_matriz="6.25/28510.0028" (el propio código buscado, tal cual
    # sale de la columna MATRIZ de la fila encontrada) como si el expediente
    # tuviera una matriz distinta de sí mismo — eso sería inventarla por
    # auto-referencia (bug real: expediente 6.25/28510.0027, sesión de
    # pulido de la web, CLAUDE.md).
    resultado = cruzar_codigo_proyecto(excel_codigos, "6.25/28510.0028")

    assert resultado.cruzado is True
    assert resultado.codigo_interno == "24038"
    assert resultado.codigo_matriz is None


def test_no_cruza_no_inventa_nada(excel_codigos):
    resultado = cruzar_codigo_proyecto(excel_codigos, "6.99/00000.0000")

    assert resultado.cruzado is False
    assert resultado.codigo_interno is None
    assert resultado.codigo_proyecto is None
    assert resultado.codigo_matriz is None
