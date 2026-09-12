"""Caso de aceptación de esta sesión: etapas 3 a 6 de la cascada (CONTEXTO.md
sección 5) encadenadas sobre los dos anejos de fixture con cabecera
distinta, produciendo líneas de catálogo reales — no inventadas a mano en el
test. Ejecutar con `pytest -s` para ver el informe de páginas descartadas,
líneas extraídas y llamadas al modelo.
"""
from decimal import Decimal

from app.catalogo import guardar_lineas_catalogo
from app.extraccion.pipeline_anejo import procesar_anejo
from app.extraccion.texto import extraer_texto
from app.models import Documento, DocumentoExpediente, Expediente, Lote, TipoDocumento
from tests import fixtures as fx
from tests.extraccion.dobles import ProveedorModeloFalso


def _sin_identificador_lote(lineas: list[dict]) -> list[dict]:
    """`identificador_lote` es una clave de enrutamiento interna de
    `procesar_anejo` (etapa 3.5, `app.extraccion.lote_tabla`): el
    orquestador la usa para agrupar líneas por lote y la retira antes de
    llamar a `guardar_lineas_catalogo` (que solo conoce columnas reales de
    `LineaCatalogo`). Estos tests llaman a `guardar_lineas_catalogo`
    directamente, así que hacen la misma retirada aquí."""
    return [{k: v for k, v in l.items() if k != "identificador_lote"} for l in lineas]


def _crear_lote(db_session, codigo_expediente, ruta_pdf):
    expediente = Expediente(codigo_expediente=codigo_expediente)
    db_session.add(expediente)
    db_session.commit()
    lote = Lote(expediente_id=expediente.id, identificador_lote="1")
    db_session.add(lote)
    db_session.commit()
    documento = Documento(
        tipo_documento=TipoDocumento.anejo,
        hash=f"hash-{codigo_expediente}",
        ruta_almacenamiento=str(ruta_pdf),
    )
    db_session.add(documento)
    db_session.commit()
    db_session.add(DocumentoExpediente(
        documento_id=documento.id, expediente_id=expediente.id, nombre_archivo=ruta_pdf.name,
    ))
    db_session.commit()
    return expediente, lote, documento


def test_cascada_completa_sobre_los_dos_anejos_de_fixture(db_session, capsys):
    documentos = [
        ("6.24/28510.0008", fx.ANEJO_PRECIOS_GUANTES, Decimal("0.5400")),
        ("6.24/28510.0088", fx.ANEJO_PRECIOS_TRAVIESAS, Decimal("0.0050")),
    ]

    # Con las cabeceras reales de estos dos fixtures, el mapeo determinista
    # (CONTEXTO.md sección 6: "antes de llamar al modelo, intenta un mapeo
    # determinista") ya las resuelve —no hace falta un ModelProvider real
    # aquí—, pero se ejercita igual con un doble que reventaría el test si
    # se le llamase, para dejar constancia de que en efecto no se llama.
    modelo = ProveedorModeloFalso({})

    informe = []
    llamadas_modelo_totales = 0
    firmas_vistas: set[str] = set()

    for codigo_expediente, ruta, baja in documentos:
        expediente, lote, documento = _crear_lote(db_session, codigo_expediente, ruta)

        resultado = procesar_anejo(
            ruta, extraer_texto(ruta), documento_origen_id=documento.id, expediente_id=expediente.id,
            lotes={"1": baja}, db=db_session, model_provider=modelo,
        )
        guardado = guardar_lineas_catalogo(db_session, lote.id, _sin_identificador_lote(resultado.lineas))

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
    expediente, lote, documento = _crear_lote(db_session, "6.24/28510.0008", fx.ANEJO_PRECIOS_GUANTES)

    resultado = procesar_anejo(
        fx.ANEJO_PRECIOS_GUANTES,
        extraer_texto(fx.ANEJO_PRECIOS_GUANTES),
        documento_origen_id=documento.id,
        expediente_id=expediente.id,
        lotes={"1": Decimal("0.5400")},
        db=db_session,
        model_provider=None,
    )

    assert len(resultado.lineas) == 13
    assert resultado.llamadas_modelo == 0
    assert resultado.tablas_sin_lote == []

    primera = resultado.lineas[0]
    assert primera["codigo_precio"] == "P-001"
    assert primera["matricula"] == "697500900"
    assert primera["cantidad"] == Decimal("30")
    assert primera["precio_unitario"] == Decimal("24.00")
    # 24,00 * (1 - 0,54) = 11,04 — no 0,00 (CONTEXTO.md sección 4).
    assert primera["precio_adjudicado"] == Decimal("11.0400")
    assert primera["identificador_lote"] == "1"


def test_documento_0088_traviesas_colapsa_a_14_lineas_unicas_en_catalogo(db_session):
    # El mismo cuadro de precios aparece dos veces en el PDF (Anejo 1 y el
    # cuadro de "criterios técnicos" del Anejo 2): 33 filas crudas deben
    # colapsar a 14 códigos de precio únicos en el catálogo.
    expediente, lote, documento = _crear_lote(db_session, "6.24/28510.0088", fx.ANEJO_PRECIOS_TRAVIESAS)

    resultado = procesar_anejo(
        fx.ANEJO_PRECIOS_TRAVIESAS,
        extraer_texto(fx.ANEJO_PRECIOS_TRAVIESAS),
        documento_origen_id=documento.id,
        expediente_id=expediente.id,
        lotes={"1": Decimal("0.0050")},
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
    guardado = guardar_lineas_catalogo(db_session, lote.id, _sin_identificador_lote(resultado.lineas))
    assert guardado.creadas == 14
    assert guardado.actualizadas == 0


def test_documento_0156_hereda_lote_entre_paginas_de_continuacion(db_session):
    # Sesión de verificación del Excel (2026-09-08), aprobado por el
    # cliente tras verificar contra el documento real completo: fixture de
    # 5 páginas reales de `6.22/28510.0156` (p.15, 16, 25, 26, 27 del
    # original) -- p.15 y p.26 traen la cláusula de "urgencia mutua" (Parte
    # A: se resuelven por posición gramatical), p.16/25/27 no traen ningún
    # rastro de "LOTE" (Parte B: heredan el lote de la tabla anterior).
    expediente = Expediente(codigo_expediente="6.22/28510.0156")
    db_session.add(expediente)
    db_session.commit()
    lote1 = Lote(expediente_id=expediente.id, identificador_lote="1")
    lote2 = Lote(expediente_id=expediente.id, identificador_lote="2")
    db_session.add_all([lote1, lote2])
    db_session.commit()
    documento = Documento(
        tipo_documento=TipoDocumento.anejo,
        hash="hash-0156-herencia-lote",
        ruta_almacenamiento=str(fx.ANEJO_HERENCIA_LOTE_0156),
    )
    db_session.add(documento)
    db_session.commit()
    db_session.add(DocumentoExpediente(
        documento_id=documento.id, expediente_id=expediente.id,
        nombre_archivo=fx.ANEJO_HERENCIA_LOTE_0156.name,
    ))
    db_session.commit()

    resultado = procesar_anejo(
        fx.ANEJO_HERENCIA_LOTE_0156,
        extraer_texto(fx.ANEJO_HERENCIA_LOTE_0156),
        documento_origen_id=documento.id,
        expediente_id=expediente.id,
        lotes={"1": Decimal("0.10"), "2": Decimal("0.20")},
        db=db_session,
        model_provider=None,
    )

    # Las 5 páginas del fixture (5 tablas, una por página) resuelven todas
    # -- ninguna se queda ambigua.
    assert resultado.tablas_sin_lote == []

    por_pagina: dict[int, list[dict]] = {}
    for linea in resultado.lineas:
        por_pagina.setdefault(linea["pagina"], []).append(linea)
    assert set(por_pagina) == {1, 2, 3, 4, 5}

    # Página 1 (p.15 real): cabecera propia, resuelta por la Parte A -- no
    # heredada.
    for linea in por_pagina[1]:
        assert linea["identificador_lote"] == "1"
        assert linea["lote_heredado_de_pagina_anterior"] is None

    # Páginas 2 y 3 (p.16 y p.25 reales): continuación de Lote 1, heredada.
    for pagina in (2, 3):
        for linea in por_pagina[pagina]:
            assert linea["identificador_lote"] == "1"
            assert linea["lote_heredado_de_pagina_anterior"] is True

    # Página 4 (p.26 real): nueva cabecera propia, Parte A resuelve a Lote
    # 2 -- la herencia de Lote 1 se corta aquí, no heredada.
    for linea in por_pagina[4]:
        assert linea["identificador_lote"] == "2"
        assert linea["lote_heredado_de_pagina_anterior"] is None

    # Página 5 (p.27 real): continuación de Lote 2, heredada -- nunca de
    # Lote 1, aunque sea el "último lote" que apareció antes de la página 4.
    for linea in por_pagina[5]:
        assert linea["identificador_lote"] == "2"
        assert linea["lote_heredado_de_pagina_anterior"] is True

    # La baja de cada lote se aplica según el lote resuelto (heredado o no),
    # nunca un valor mezclado entre los dos.
    assert all(l["baja_lote"] == Decimal("0.10") for l in por_pagina[1] + por_pagina[2] + por_pagina[3])
    assert all(l["baja_lote"] == Decimal("0.20") for l in por_pagina[4] + por_pagina[5])

    grupos: dict[str, list[dict]] = {"1": [], "2": []}
    for linea in resultado.lineas:
        grupos[linea.pop("identificador_lote")].append(
            {k: v for k, v in linea.items()}
        )
    guardado1 = guardar_lineas_catalogo(db_session, lote1.id, grupos["1"])
    guardado2 = guardar_lineas_catalogo(db_session, lote2.id, grupos["2"])
    db_session.commit()

    from app.models import LineaCatalogo

    heredadas_lote1 = (
        db_session.query(LineaCatalogo)
        .filter_by(lote_id=lote1.id, lote_heredado_de_pagina_anterior=True)
        .count()
    )
    heredadas_lote2 = (
        db_session.query(LineaCatalogo)
        .filter_by(lote_id=lote2.id, lote_heredado_de_pagina_anterior=True)
        .count()
    )
    assert heredadas_lote1 == len(por_pagina[2]) + len(por_pagina[3])
    assert heredadas_lote2 == len(por_pagina[5])
    assert guardado1.creadas + guardado2.creadas == len(resultado.lineas)


def test_reprocesar_el_mismo_documento_no_duplica_lineas_ni_repite_llamadas(db_session):
    expediente, lote, documento = _crear_lote(db_session, "6.24/28510.0088", fx.ANEJO_PRECIOS_TRAVIESAS)

    paginas = extraer_texto(fx.ANEJO_PRECIOS_TRAVIESAS)
    r1 = procesar_anejo(
        fx.ANEJO_PRECIOS_TRAVIESAS, paginas, documento.id, expediente.id, {"1": Decimal("0.0050")}, db_session, None
    )
    guardar_lineas_catalogo(db_session, lote.id, _sin_identificador_lote(r1.lineas))

    r2 = procesar_anejo(
        fx.ANEJO_PRECIOS_TRAVIESAS, paginas, documento.id, expediente.id, {"1": Decimal("0.0050")}, db_session, None
    )
    guardado2 = guardar_lineas_catalogo(db_session, lote.id, _sin_identificador_lote(r2.lineas))

    # r2.lineas también trae las 33 filas crudas, fundidas a 14 por clave
    # antes de escribir — las 14 ya existen en la base de datos desde r1.
    assert guardado2.creadas == 0
    assert guardado2.actualizadas == 14
    from app.models import LineaCatalogo

    assert db_session.query(LineaCatalogo).filter_by(lote_id=lote.id).count() == 14
