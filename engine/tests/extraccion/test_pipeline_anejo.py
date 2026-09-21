"""Caso de aceptación de esta sesión: etapas 3 a 6 de la cascada (CONTEXTO.md
sección 5) encadenadas sobre los dos anejos de fixture con cabecera
distinta, produciendo líneas de catálogo reales — no inventadas a mano en el
test. Ejecutar con `pytest -s` para ver el informe de páginas descartadas,
líneas extraídas y llamadas al modelo.
"""
from decimal import Decimal

from app.catalogo import guardar_lineas_catalogo
from app.extraccion.lote_tabla import MOTIVO_TABLA_DEL_CONJUNTO
from app.extraccion.pipeline_anejo import procesar_anejo
from app.extraccion.texto import extraer_texto
from app.models import Documento, DocumentoExpediente, Expediente, Lote, TipoDocumento
from tests import fixtures as fx
from tests.extraccion.dobles import ProveedorModeloCabeceraPorContenido, ProveedorModeloFalso


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


def test_lote_en_el_titulo_de_la_tabla_o_al_final_de_la_pagina_anterior(db_session):
    """Sesión 2026-09-14 (continuación, auditoría de las huérfanas):
    `4.26/28510.0020`. La cabecera "LOTE N" de cada presupuesto no está en
    la franja sobre la tabla: la del LOTE 1 va dentro de la caja de la tabla
    (sus filas de título) y la del LOTE 2 al final de la página anterior.
    Antes, las cuatro páginas quedaban sin lote. Y el cuadro de la partida
    alzada (p.39 del original, común a los dos lotes) no hereda el LOTE 2
    de la p.17: hay páginas sin tabla por medio, no es su continuación."""
    expediente = Expediente(codigo_expediente="4.26/28510.0020")
    db_session.add(expediente)
    db_session.commit()
    documento = Documento(
        tipo_documento=TipoDocumento.anejo, hash="hash-0020-lote-titulo-cola",
        ruta_almacenamiento=str(fx.ANEJO_LOTE_EN_TITULO_Y_COLA_0020),
    )
    db_session.add(documento)
    db_session.commit()

    resultado = procesar_anejo(
        fx.ANEJO_LOTE_EN_TITULO_Y_COLA_0020,
        extraer_texto(fx.ANEJO_LOTE_EN_TITULO_Y_COLA_0020),
        documento_origen_id=documento.id,
        expediente_id=expediente.id,
        lotes={"1": None, "2": None},
        db=db_session,
        model_provider=ProveedorModeloCabeceraPorContenido(),
    )

    por_pagina: dict[int, set] = {}
    for linea in resultado.lineas:
        por_pagina.setdefault(linea["pagina"], set()).add(
            (linea["identificador_lote"], linea["lote_heredado_de_pagina_anterior"])
        )
    # Las continuaciones sin cabecera (p.2 y p.4 del fixture) no dan líneas
    # aquí: su mapeo sale en producción de la caché de cabeceras, que este
    # test no tiene. La herencia en sí ya la cubre el test de `0156`.
    assert por_pagina[1] == {("1", None)}   # título de la tabla
    assert por_pagina[3] == {("2", None)}   # cola de la página anterior
    assert por_pagina[6] == {(None, None)}  # partida alzada, común
    assert any("página 6: tabla separada de la anterior por páginas sin tabla" in m for m in resultado.tablas_sin_lote)


def _documento_de_prueba(db_session, codigo_expediente: str, ruta) -> tuple[Expediente, Documento]:
    expediente = db_session.query(Expediente).filter_by(codigo_expediente=codigo_expediente).one_or_none()
    if expediente is None:
        expediente = Expediente(codigo_expediente=codigo_expediente)
        db_session.add(expediente)
        db_session.commit()
    documento = db_session.query(Documento).filter_by(hash=f"hash-{ruta.name}").one_or_none()
    if documento is None:
        documento = Documento(
            tipo_documento=TipoDocumento.anejo, hash=f"hash-{ruta.name}", ruta_almacenamiento=str(ruta)
        )
        db_session.add(documento)
        db_session.commit()
    return expediente, documento


def _lotes_por_pagina(resultado) -> dict[int, set]:
    por_pagina: dict[int, set] = {}
    for linea in resultado.lineas:
        por_pagina.setdefault(linea["pagina"], set()).add((linea["identificador_lote"], linea["lote_del_expediente"]))
    return por_pagina


def test_anejo_de_criterios_del_conjunto_no_es_de_ningun_lote(db_session):
    """Sesión 2026-09-14, tercera parte: `6.23/28510.0051_ANEJO_1`, p.14, 38,
    55 y 56 del original. El cuadro de precios trae cada lote con su
    cabecera ("Lote 1: ANCHO MIXTO", "Lote 2: ANCHO METRICO"); el anejo de
    criterios se declara del conjunto ("materiales a suministrar en el
    expediente “... 2 LOTES”") y no es de ningún lote -- tampoco en `0060`,
    que es el LOTE 1 y se queda con las tablas sin cabecera: esta la tiene,
    y dice que es de todos."""
    for lote_propio in (None, "1"):
        expediente, documento = _documento_de_prueba(
            db_session, f"6.23/28510.{'0051' if lote_propio is None else '0060'}", fx.ANEJO_LOTES_Y_CRITERIOS_0051
        )
        resultado = procesar_anejo(
            fx.ANEJO_LOTES_Y_CRITERIOS_0051, extraer_texto(fx.ANEJO_LOTES_Y_CRITERIOS_0051),
            documento_origen_id=documento.id, expediente_id=expediente.id,
            lotes={"1": None, "2": None}, db=db_session, model_provider=ProveedorModeloCabeceraPorContenido(),
            lote_propio=lote_propio,
        )
        por_pagina = _lotes_por_pagina(resultado)
        assert por_pagina[1] == {("1", None)}
        assert ("2", None) in por_pagina[2]
        assert por_pagina[3] == {(None, None)}
        assert por_pagina[4] == {(None, None)}
        criterios = [l for l in resultado.lineas if l["pagina"] in (3, 4)]
        assert all(l["motivo_revision"] == MOTIVO_TABLA_DEL_CONJUNTO for l in criterios)
        # No es una ambigüedad: no manda el expediente a revisión.
        assert not any(MOTIVO_TABLA_DEL_CONJUNTO in m for m in resultado.tablas_sin_lote)
        # El cuadro repite su cabecera en cada página: sigue siendo la misma
        # tabla (la fusión por firma no junta dos códigos suyos); el anejo de
        # criterios es otra.
        origen = {l["pagina"]: l["tabla_origen"] for l in resultado.lineas if l["identificador_lote"] == "1"}
        origen_criterios = {l["tabla_origen"] for l in criterios}
        assert origen[1] == origen[2]
        assert origen[1] not in origen_criterios


def test_expediente_de_lote_se_queda_las_tablas_sin_cabecera_de_su_seccion(db_session):
    """Decisión del cliente (misma sesión): en un expediente que sabe cuál
    es su lote, las tablas que no declaran lote son suyas. Contrato del LOTE
    1 de `6.22/28510.0122` (p.116, 122, 127 y 133 del original): la tabla
    de la p.122 no trae cabecera, y la última mención de lote antes de ella
    es "LLote 1:" (p.116); la de la p.133 va detrás de "LLote 2:" (p.127).
    La del LOTE 1 es de `0155`, la del LOTE 2 de `0156` -- nunca al revés."""
    ruta = fx.CONTRATO_LOTE1_PLIEGO_0155

    def procesar(codigo, lote_propio, documento_de_otro_lote=False):
        expediente, documento = _documento_de_prueba(db_session, codigo, ruta)
        return procesar_anejo(
            ruta, extraer_texto(ruta), documento_origen_id=documento.id, expediente_id=expediente.id,
            lotes={"1": None, "2": None}, db=db_session, model_provider=ProveedorModeloCabeceraPorContenido(),
            lote_propio=lote_propio, documento_de_otro_lote=documento_de_otro_lote,
        )

    lote1 = _lotes_por_pagina(procesar("6.22/28510.0155", "1"))
    assert lote1[2] == {("1", True)}
    assert lote1[4] == {(None, None)}

    lote2 = procesar("6.22/28510.0156", "2")
    assert _lotes_por_pagina(lote2)[2] == {(None, None)}
    assert _lotes_por_pagina(lote2)[4] == {("2", True)}
    assert any("la última mención de lote antes de ella es la del LOTE 1" in m for m in lote2.tablas_sin_lote)

    # Archivado con `0156` es el Contrato de otro lote: nada sin cabecera se
    # le atribuye.
    otro = _lotes_por_pagina(procesar("6.22/28510.0156", "2", documento_de_otro_lote=True))
    assert otro[2] == {(None, None)} and otro[4] == {(None, None)}

    # El principal (sin lote propio) los deja sin lote, como hasta ahora.
    principal = _lotes_por_pagina(procesar("6.22/28510.0122", None))
    assert principal[2] == {(None, None)} and principal[4] == {(None, None)}


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


def test_documento_0109_continuaciones_heredan_mapeo_y_repuesto_sin_modelo(db_session):
    # Sesión 2026-09-14: las páginas 2-3 del fixture (p.4-5 del original)
    # continúan la tabla de la p.1 sin repetir cabecera. Deben abrirse
    # (localizador), heredar el mapeo de la cabecera por geometría de
    # columnas -- sin llamar al modelo: el doble revienta si se le llama -- y
    # tomar el Código del material de la columna REPUESTO (decisión del
    # cliente), no de la descripción.
    expediente, lote, documento = _crear_lote(db_session, "6.21/28510.0109", fx.ANEJO_REPUESTO_CONTINUACION_0109)
    modelo = ProveedorModeloFalso({})

    resultado = procesar_anejo(
        fx.ANEJO_REPUESTO_CONTINUACION_0109,
        extraer_texto(fx.ANEJO_REPUESTO_CONTINUACION_0109),
        documento_origen_id=documento.id,
        expediente_id=expediente.id,
        lotes={"1": None},
        db=db_session,
        model_provider=modelo,
    )

    assert [c.numero for c in resultado.localizacion.candidatas] == [1, 2, 3]
    assert modelo.llamadas == 0
    codigos = [l["codigo_precio"] for l in resultado.lineas]
    assert codigos == [f"P-{n}" for n in range(11, 23)]
    assert all(l["descripcion"] and l["precio_unitario"] for l in resultado.lineas)
    assert {l["codigo_material"] for l in resultado.lineas} == {"SEMICAMBIO", "AGUJA", "CONTRAAGUJA"}
    p13 = next(l for l in resultado.lineas if l["codigo_precio"] == "P-13")
    assert p13["pagina"] == 2
    assert p13["precio_unitario"] == Decimal("91537.95")
    assert p13["unidad_medida"] == "ud"  # sin el "€/" de la base del precio (sesión 2026-09-15)


def test_documento_0016_cabecera_ilegible_no_se_cachea_y_la_matricula_va_a_su_campo(db_session):
    # Sesión 2026-09-14. El doble devuelve exactamente el mapeo equivocado
    # que dio el modelo real sobre esta tabla (quedó cacheado en su día):
    # `codigo_precio` en la matrícula, `matricula` en "REF. ADIF", unidad en
    # el plano. La cabecera ilegible no debe llegar al prompt ni cachearse;
    # la corrección matrícula/código debe aplicarse a las DOS páginas (la
    # segunda reutiliza el mapeo de la primera por firma estructural) y
    # marcar `codigo_precio` para borrar el valor viejo guardado.
    from app.extraccion.invalidado import INVALIDADO
    from app.models import MapeoCabeceraCache

    expediente, lote, documento = _crear_lote(db_session, "6.21/28510.0016", fx.ANEJO_CABECERA_ILEGIBLE_0016)
    modelo = ProveedorModeloFalso({
        "codigo_precio": 0, "matricula": 1, "descripcion": 2,
        "unidad_medida": 3, "cantidad": 4, "precio_unitario": 5,
    })
    resultado = procesar_anejo(
        fx.ANEJO_CABECERA_ILEGIBLE_0016,
        extraer_texto(fx.ANEJO_CABECERA_ILEGIBLE_0016),
        documento_origen_id=documento.id,
        expediente_id=expediente.id,
        lotes={"1": None},
        db=db_session,
        model_provider=modelo,
    )

    assert all("(cid:" not in prompt for prompt in modelo.prompts)
    assert db_session.query(MapeoCabeceraCache).count() == 0

    con_matricula = [l for l in resultado.lineas if l["matricula"]]
    assert len(con_matricula) == 25
    assert {l["pagina"] for l in con_matricula} == {1, 2}
    assert all(l["codigo_precio"] is INVALIDADO for l in con_matricula)
    assert all(l["unidad_medida"] is None for l in con_matricula)
    primera = next(l for l in con_matricula if l["matricula"] == "642370100")
    assert primera["cantidad"] == Decimal("30")
    assert primera["precio_unitario"] == Decimal("9.92")
    partida = next(l for l in resultado.lineas if (l["descripcion"] or "").startswith("Partida alzada"))
    assert partida["precio_unitario"] == Decimal("1467.20")


def test_nota_de_subsanacion_se_queda_con_la_correccion():
    # `6.23/28510.0051_ANEJO_3_9d725c710163f3db.pdf`: "Donde aparece:"
    # 62.171,96 € / "Debiendo ser:" 136.315,00 € para la misma partida.
    from app.extraccion.pipeline_anejo import _es_nota_de_subsanacion, _quedarse_con_la_correccion
    from app.extraccion.texto import PaginaTexto

    texto = (
        "NOTA DE SUBSANACIÓN A LOS ANEJOS DEL PLIEGO\nSe subsana el precio reflejado en los Anejos del PPT\n"
        "Donde aparece:\nP-0063 Semicambio dcha UD. 0 62.171,96 €\nDebiendo ser:\nP-0063 Semicambio dcha UD. 0 136.315,00"
    )
    assert _es_nota_de_subsanacion([PaginaTexto(numero=1, texto=texto)])
    assert not _es_nota_de_subsanacion([PaginaTexto(numero=1, texto="Plazo de subsanación de la documentación: 3 días")])

    lineas = [
        {"identificador_lote": "1", "clave_linea": "P-0063", "codigo_precio": "P-0063", "precio_unitario": Decimal("62171.96")},
        {"identificador_lote": "1", "clave_linea": "abc", "codigo_precio": None, "precio_unitario": Decimal("5")},
        {"identificador_lote": "1", "clave_linea": "P-0063", "codigo_precio": "P-0063", "precio_unitario": Decimal("136315.00")},
    ]
    resultado = _quedarse_con_la_correccion(lineas)
    assert [l["precio_unitario"] for l in resultado] == [Decimal("5"), Decimal("136315.00")]


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


def test_las_paginas_de_la_oferta_van_del_titulo_a_su_total():
    # Sesión 2026-09-21 (segunda parte): "ANEJO Nº 1 Bis. JUSTIFICACIÓN DE LA
    # PROPOSICIÓN ECONÓMICA PRESENTADA..." de `4.26/28510.0020` CONTRATO_1.pdf
    # pp.5-6: sus precios son los ofertados, no los de licitación.
    from app.extraccion.pipeline_anejo import paginas_de_la_oferta
    from app.extraccion.texto import PaginaTexto

    paginas = [
        PaginaTexto(numero=4, texto="PROPOSICIÓN ECONÓMICA Importe ofertado"),
        PaginaTexto(numero=5, texto="ANEJO Nº 1 Bis JUSTIFICACIÓN DE LA PROPOSICIÓN ECONÓMICA PRESENTADA"),
        PaginaTexto(numero=6, texto="P-17 Ud. 1 4.820,00 4.820,00 TOTAL OFERTADO (SIN IVA) 2.765.385,23"),
        PaginaTexto(numero=7, texto="LOTE 1 PRESUPUESTO P-1 48 10.805,22"),
    ]
    assert paginas_de_la_oferta(paginas) == {5, 6}


def test_el_titulo_del_pliego_sin_total_detras_no_marca_nada():
    # El pliego administrativo repite el título en sus instrucciones, sin
    # ningún cuadro detrás: no puede tapar un cuadro de precios de verdad.
    from app.extraccion.pipeline_anejo import paginas_de_la_oferta
    from app.extraccion.texto import PaginaTexto

    paginas = [PaginaTexto(numero=n, texto="") for n in range(1, 12)]
    paginas[1] = PaginaTexto(numero=2, texto="la justificación de la proposición económica presentada")
    assert paginas_de_la_oferta(paginas) == set()
