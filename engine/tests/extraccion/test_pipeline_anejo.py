"""Caso de aceptación de esta sesión: etapas 3 a 6 de la cascada (CLAUDE.md
sección 5) encadenadas sobre los dos anejos de fixture con cabecera
distinta, produciendo líneas de catálogo reales — no inventadas a mano en el
test. Ejecutar con `pytest -s` para ver el informe de páginas descartadas,
líneas extraídas y llamadas al modelo.
"""
from decimal import Decimal

from app.catalogo import guardar_lineas_catalogo
from app.extraccion.pipeline_anejo import procesar_anejo
from app.models import Documento, Expediente, Lote, TipoDocumento
from tests import fixtures as fx
from tests.extraccion.dobles import ProveedorModeloFalso


def _crear_lote(db_session, codigo_expediente, ruta_pdf):
    expediente = Expediente(codigo_expediente=codigo_expediente)
    db_session.add(expediente)
    db_session.commit()
    lote = Lote(expediente_id=expediente.id, identificador_lote="1")
    db_session.add(lote)
    db_session.commit()
    documento = Documento(
        expediente_id=expediente.id,
        tipo_documento=TipoDocumento.anejo,
        hash=f"hash-{codigo_expediente}",
        nombre_archivo=ruta_pdf.name,
        ruta_almacenamiento=str(ruta_pdf),
    )
    db_session.add(documento)
    db_session.commit()
    return lote, documento


def test_cascada_completa_sobre_los_dos_anejos_de_fixture(db_session, capsys):
    documentos = [
        ("6.24/28510.0008", fx.ANEJO_PRECIOS_GUANTES, Decimal("0.5400")),
        ("6.24/28510.0088", fx.ANEJO_PRECIOS_TRAVIESAS, Decimal("0.0050")),
    ]

    # Con las cabeceras reales de estos dos fixtures, el mapeo determinista
    # (CLAUDE.md sección 6: "antes de llamar al modelo, intenta un mapeo
    # determinista") ya las resuelve —no hace falta un ModelProvider real
    # aquí—, pero se ejercita igual con un doble que reventaría el test si
    # se le llamase, para dejar constancia de que en efecto no se llama.
    modelo = ProveedorModeloFalso({})

    informe = []
    llamadas_modelo_totales = 0
    firmas_vistas: set[str] = set()

    for codigo_expediente, ruta, baja in documentos:
        lote, documento = _crear_lote(db_session, codigo_expediente, ruta)

        resultado = procesar_anejo(
            ruta, documento_origen_id=documento.id, baja_lote=baja, db=db_session, model_provider=modelo
        )
        guardado = guardar_lineas_catalogo(db_session, lote.id, resultado.lineas)

        llamadas_modelo_totales += resultado.llamadas_modelo
        firmas_vistas |= resultado.firmas_cabecera

        informe.append(
            f"{ruta.name}: {resultado.localizacion.total_paginas} páginas, "
            f"{len(resultado.localizacion.candidatas)} candidatas "
            f"({resultado.localizacion.porcentaje_descartado:.1%} descartado), "
            f"{resultado.tablas_procesadas} tablas, "
            f"{len(resultado.lineas)} líneas extraídas -> "
            f"{guardado.creadas} nuevas / {guardado.actualizadas} actualizadas en catálogo, "
            f"{resultado.llamadas_modelo} llamadas al modelo"
        )

    print("\n=== Cascada de extracción (etapas 3-6) sobre los fixtures ===")
    for linea in informe:
        print(" -", linea)
    print(f"Llamadas al modelo (total): {llamadas_modelo_totales}")
    print(f"Firmas de cabecera distintas (total): {len(firmas_vistas)}")

    # El requisito de la sesión: si las llamadas al modelo superan el número
    # de firmas de cabecera distintas, la caché no está funcionando.
    assert llamadas_modelo_totales <= len(firmas_vistas)
    assert modelo.llamadas == 0

    salida = capsys.readouterr().out
    assert "Cascada de extracción" in salida


def test_documento_0008_guantes_produce_13_lineas_con_baja_aplicada(db_session):
    lote, documento = _crear_lote(db_session, "6.24/28510.0008", fx.ANEJO_PRECIOS_GUANTES)

    resultado = procesar_anejo(
        fx.ANEJO_PRECIOS_GUANTES,
        documento_origen_id=documento.id,
        baja_lote=Decimal("0.5400"),
        db=db_session,
        model_provider=None,
    )

    assert len(resultado.lineas) == 13
    assert resultado.llamadas_modelo == 0

    primera = resultado.lineas[0]
    assert primera["codigo_precio"] == "P-001"
    assert primera["matricula"] == "697500900"
    assert primera["cantidad"] == Decimal("30")
    assert primera["precio_unitario"] == Decimal("24.00")
    # 24,00 * (1 - 0,54) = 11,04 — no 0,00 (CLAUDE.md sección 4).
    assert primera["precio_adjudicado"] == Decimal("11.0400")


def test_documento_0088_traviesas_colapsa_a_14_lineas_unicas_en_catalogo(db_session):
    # El mismo cuadro de precios aparece dos veces en el PDF (Anejo 1 y el
    # cuadro de "criterios técnicos" del Anejo 2): 33 filas crudas deben
    # colapsar a 14 códigos de precio únicos en el catálogo.
    lote, documento = _crear_lote(db_session, "6.24/28510.0088", fx.ANEJO_PRECIOS_TRAVIESAS)

    resultado = procesar_anejo(
        fx.ANEJO_PRECIOS_TRAVIESAS,
        documento_origen_id=documento.id,
        baja_lote=Decimal("0.0050"),
        db=db_session,
        model_provider=None,
    )
    assert len(resultado.lineas) == 33

    # Las 33 filas se funden por clave_linea en Python antes de tocar la base
    # de datos (app.catalogo._combinar_por_clave) — sin depender de que la
    # sesión autoflushee entre iteraciones, que `SessionLocal` (app/db.py)
    # desactiva a propósito. Las 19 repeticiones dentro de este mismo
    # documento no son una "actualización": son la misma línea vista dos
    # veces antes de que exista fila alguna en la base de datos.
    guardado = guardar_lineas_catalogo(db_session, lote.id, resultado.lineas)
    assert guardado.creadas == 14
    assert guardado.actualizadas == 0


def test_reprocesar_el_mismo_documento_no_duplica_lineas_ni_repite_llamadas(db_session):
    lote, documento = _crear_lote(db_session, "6.24/28510.0088", fx.ANEJO_PRECIOS_TRAVIESAS)

    r1 = procesar_anejo(fx.ANEJO_PRECIOS_TRAVIESAS, documento.id, Decimal("0.0050"), db_session, None)
    guardar_lineas_catalogo(db_session, lote.id, r1.lineas)

    r2 = procesar_anejo(fx.ANEJO_PRECIOS_TRAVIESAS, documento.id, Decimal("0.0050"), db_session, None)
    guardado2 = guardar_lineas_catalogo(db_session, lote.id, r2.lineas)

    # r2.lineas también trae las 33 filas crudas, fundidas a 14 por clave
    # antes de escribir — las 14 ya existen en la base de datos desde r1.
    assert guardado2.creadas == 0
    assert guardado2.actualizadas == 14
    from app.models import LineaCatalogo

    assert db_session.query(LineaCatalogo).filter_by(lote_id=lote.id).count() == 14
