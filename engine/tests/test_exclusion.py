"""Lista de exclusión de expedientes (bloque 5, cambios del cliente tras
revisar el catálogo): pruebas del módulo puro, sin base de datos. La
integración con `/catalogo` y el Excel vive en test_api_catalogo.py."""
from app.exclusion import ExclusionExpedientes, cargar_exclusiones


def test_sin_ruta_no_excluye_nada():
    exclusiones = cargar_exclusiones(None)
    assert exclusiones.vacia()
    assert not exclusiones.excluye("6.24/28510.0008")


def test_fichero_ausente_no_excluye_nada(tmp_path):
    exclusiones = cargar_exclusiones(str(tmp_path / "no_existe.txt"))
    assert exclusiones.vacia()


def test_codigo_exacto(tmp_path):
    fichero = tmp_path / "exclusion.txt"
    fichero.write_text("6.24/28510.0008\n")
    exclusiones = cargar_exclusiones(str(fichero))
    assert exclusiones.excluye("6.24/28510.0008")
    assert not exclusiones.excluye("6.24/28510.0009")


def test_codigo_con_espacios_sobrantes_se_normaliza(tmp_path):
    # CONTEXTO.md sección 8: "En el Excel hay valores como '6.25/28510.0146
    # '. Un cruce exacto fallaría en silencio." -- mismo criterio aquí,
    # tanto al leer el fichero como al comparar contra el código real.
    fichero = tmp_path / "exclusion.txt"
    fichero.write_text(" 6.24/28510.0008 \n")
    exclusiones = cargar_exclusiones(str(fichero))
    assert exclusiones.excluye("6.24/28510.0008")


def test_departamento_completo(tmp_path):
    fichero = tmp_path / "exclusion.txt"
    fichero.write_text("28520\n")
    exclusiones = cargar_exclusiones(str(fichero))
    assert exclusiones.excluye("6.24/28520.0001")
    assert not exclusiones.excluye("6.24/28510.0001")


def test_comentarios_y_lineas_vacias_se_ignoran(tmp_path):
    fichero = tmp_path / "exclusion.txt"
    fichero.write_text("# excluidos de otro equipo\n\n6.24/28510.0008\n\n# 28599\n")
    exclusiones = cargar_exclusiones(str(fichero))
    assert exclusiones.codigos == frozenset({"6.24/28510.0008"})
    assert exclusiones.departamentos == frozenset()


def test_expediente_sin_formato_de_codigo_no_casa_ningun_departamento():
    exclusiones = ExclusionExpedientes(departamentos=frozenset({"28510"}))
    assert not exclusiones.excluye("no-es-un-codigo")
