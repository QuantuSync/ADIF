"""Bloque 1, sesión 2026-09-18 (continuación): el listado de estados que ADIF
envió el 18/09/2026. Ver `app.extraccion.estados_adif` para la procedencia y
para por qué NO reutiliza `estado_sap`."""
import openpyxl
import pytest
from datetime import datetime
from sqlalchemy import select

from app.extraccion.estados_adif import (
    EstadosAdifPathInvalida,
    cargar_estados_adif,
    validar_ruta_estados_adif,
)
from app.models import Expediente


@pytest.fixture
def excel_estados_adif(tmp_path):
    ruta = tmp_path / "estados_expedientes_28510_20260918.xlsx"
    libro = openpyxl.Workbook()
    hoja = libro.active
    hoja.append([
        "Título del expediente", "Expediente ADIF", "Fecha de creación", "Descripción del estado",
    ])
    hoja.append(["SUMINISTRO DE BALASTO", "6.24/28510.0088", datetime(2024, 5, 3), "En ejecución"])
    # Espacios sobrantes: mismo hallazgo de CONTEXTO.md sección 8 que ya cubre
    # `cruce_codigos` -- sin normalizar, el cruce exacto fallaría en silencio.
    hoja.append(["SUMINISTRO DE VISERAS", " 6.14/28510.0126 ", datetime(2014, 2, 1), "Finalizado"])
    hoja.append(["EXPEDIENTE QUE NO TENEMOS", "6.99/28510.9999", datetime(2026, 1, 1), "Desierto"])
    libro.save(ruta)
    return str(ruta)


def test_rellena_el_estado_de_los_expedientes_que_ya_existen(db_session, excel_estados_adif):
    db_session.add(Expediente(codigo_expediente="6.24/28510.0088"))
    db_session.commit()

    resumen = cargar_estados_adif(db_session, excel_estados_adif)

    assert resumen.configurado is True
    assert resumen.filas_leidas == 3
    assert resumen.codigos_distintos == 3
    assert resumen.expedientes_actualizados == 1

    expediente = db_session.execute(
        select(Expediente).where(Expediente.codigo_expediente == "6.24/28510.0088")
    ).scalar_one()
    assert expediente.estado_adif == "En ejecución"
    assert expediente.estado_adif_creado_en.year == 2024
    assert expediente.estado_adif_actualizado_en is not None
    # Columna propia: el estado del OTRO volcado de SAP no se toca.
    assert expediente.estado_contrato_sap is None


def test_no_da_de_alta_ningun_expediente_nuevo(db_session, excel_estados_adif):
    """El criterio del cliente: este listado es fuente de contraste, no de
    descubrimiento. Si diera de alta lo que no tenemos, la pregunta "¿cuáles de
    los suyos nos faltan?" se contestaría sola y en falso."""
    resumen = cargar_estados_adif(db_session, excel_estados_adif)

    assert db_session.execute(select(Expediente)).scalars().all() == []
    assert resumen.sin_expediente_en_el_sistema == 3
    assert "6.99/28510.9999" in resumen.codigos_sin_expediente


def test_recorta_espacios_sobrantes_del_codigo(db_session, excel_estados_adif):
    db_session.add(Expediente(codigo_expediente="6.14/28510.0126"))
    db_session.commit()

    cargar_estados_adif(db_session, excel_estados_adif)

    expediente = db_session.execute(
        select(Expediente).where(Expediente.codigo_expediente == "6.14/28510.0126")
    ).scalar_one()
    assert expediente.estado_adif == "Finalizado"


def test_no_pisa_el_nombre_de_proyecto_ya_extraido_de_un_pdf(db_session, excel_estados_adif):
    existente = Expediente(codigo_expediente="6.24/28510.0088", nombre_proyecto="Objeto real del PDF")
    db_session.add(existente)
    db_session.commit()

    cargar_estados_adif(db_session, excel_estados_adif)

    db_session.refresh(existente)
    assert existente.nombre_proyecto == "Objeto real del PDF"


def test_repetible_sin_duplicar_ni_cambiar_nada(db_session, excel_estados_adif):
    db_session.add(Expediente(codigo_expediente="6.24/28510.0088"))
    db_session.commit()

    cargar_estados_adif(db_session, excel_estados_adif)
    segunda = cargar_estados_adif(db_session, excel_estados_adif)

    assert segunda.expedientes_actualizados == 0
    assert segunda.expedientes_sin_cambios == 1


def test_sin_ruta_configurada_no_es_un_error(db_session):
    resumen = cargar_estados_adif(db_session, None)
    assert resumen.configurado is False
    assert resumen.filas_leidas == 0


def test_ruta_inexistente_falla_al_validar(tmp_path):
    with pytest.raises(EstadosAdifPathInvalida):
        validar_ruta_estados_adif(str(tmp_path / "no_existe.xlsx"))


def test_ruta_vacia_no_valida_nada():
    validar_ruta_estados_adif(None)
