"""Lista de exclusión de expedientes (bloque 5, cambios del cliente tras
revisar el catálogo): pruebas del módulo puro, sin base de datos. La
integración con `/catalogo` y el Excel vive en test_api_catalogo.py."""
from app.exclusion import (
    ExclusionExpedientes,
    ExclusionPalabrasTitulo,
    cargar_exclusion_palabras_titulo,
    cargar_exclusiones,
)


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


# Bloque 3, sesión 2026-09-09: mecanismo de exclusión por código interno,
# además de expediente y departamento -- prefijo "INTERNO:" porque un código
# interno y un departamento son ambos cadenas de solo dígitos (ambigüedad
# real, ver docstring del módulo).
def test_codigo_interno(tmp_path):
    fichero = tmp_path / "exclusion.txt"
    fichero.write_text("INTERNO:24038\n")
    exclusiones = cargar_exclusiones(str(fichero))
    assert exclusiones.codigos_internos == frozenset({"24038"})
    assert exclusiones.excluye("6.24/28510.9999", codigo_interno="24038")
    assert not exclusiones.excluye("6.24/28510.9999", codigo_interno="24039")


def test_codigo_interno_no_excluye_sin_dato_de_codigo_interno():
    exclusiones = ExclusionExpedientes(codigos_internos=frozenset({"24038"}))
    assert not exclusiones.excluye("6.24/28510.9999")
    assert not exclusiones.excluye("6.24/28510.9999", codigo_interno=None)


def test_codigo_interno_no_se_confunde_con_departamento(tmp_path):
    fichero = tmp_path / "exclusion.txt"
    fichero.write_text("28510\n")
    exclusiones = cargar_exclusiones(str(fichero))
    assert exclusiones.departamentos == frozenset({"28510"})
    assert exclusiones.codigos_internos == frozenset()


# Bloque 3, sesión de comparación documento-vs-listado interno: filtro por
# palabras del título del contrato, mismo mecanismo que la exclusión de
# expedientes de arriba, pero por texto libre en vez de por código.
def test_palabras_titulo_sin_ruta_no_excluye_nada():
    exclusion = cargar_exclusion_palabras_titulo(None)
    assert exclusion.vacia()
    assert not exclusion.excluye("ARRENDAMIENTO DE MAQUINARIA")


def test_palabras_titulo_fichero_ausente_no_excluye_nada(tmp_path):
    exclusion = cargar_exclusion_palabras_titulo(str(tmp_path / "no_existe.txt"))
    assert exclusion.vacia()


def test_palabras_titulo_coincidencia_por_subcadena_sin_distinguir_mayusculas(tmp_path):
    fichero = tmp_path / "palabras.txt"
    fichero.write_text("arrendamiento\n")
    exclusion = cargar_exclusion_palabras_titulo(str(fichero))
    assert exclusion.palabras == frozenset({"arrendamiento"})
    assert exclusion.excluye("ARRENDAMIENTO DE MAQUINARIA PESADA")
    assert exclusion.excluye("Arrendamiento de vehículos")
    assert not exclusion.excluye("SUMINISTRO DE BALASTO")


def test_palabras_titulo_ignora_acentos_al_comparar(tmp_path):
    # El fichero y el título del documento pueden no coincidir en
    # acentuación -- `excluye()` normaliza los dos lados al comparar
    # (a diferencia de la exclusión aplicada en SQL, `app.catalogo_consulta`,
    # que compara tal cual).
    fichero = tmp_path / "palabras.txt"
    fichero.write_text("gestion de residuos\n")
    exclusion = cargar_exclusion_palabras_titulo(str(fichero))
    assert exclusion.excluye("Contrato de GESTIÓN DE RESIDUOS peligrosos")


def test_palabras_titulo_sin_titulo_no_excluye():
    exclusion = ExclusionPalabrasTitulo(palabras=frozenset({"arrendamiento"}))
    assert not exclusion.excluye(None)
    assert not exclusion.excluye("")


def test_palabras_titulo_comentarios_y_lineas_vacias_se_ignoran(tmp_path):
    fichero = tmp_path / "palabras.txt"
    fichero.write_text(
        "# no es material\narrendamiento\n\n# otra nota\ngestión de residuos\n", encoding="utf-8"
    )
    exclusion = cargar_exclusion_palabras_titulo(str(fichero))
    assert exclusion.palabras == frozenset({"arrendamiento", "gestión de residuos"})
