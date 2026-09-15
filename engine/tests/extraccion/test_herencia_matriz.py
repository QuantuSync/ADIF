"""Herencia de acuerdo marco (docs/analisis-corpus.md hallazgo 3, sesión de
herencia de matriz): un pedido derivado no trae su propio cuadro de precios
ni su propia baja, viven en los documentos de la matriz. Cubre las tres
piezas del encargo por separado (`resolver_o_encolar_matriz`,
`intentar_heredar_de_matriz`, `reencolar_pedidos_esperando_matriz`) y un caso
de aceptación de extremo a extremo con el fixture real que declara una
matriz (`ANUNCIO_PCSP_CON_MATRIZ`, expediente 6.24/28510.0103, matriz
2.18/04703.0019 — CONTEXTO.md sección 17.1)."""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from app.extraccion.herencia_matriz import (
    EstadoResolucionMatriz,
    intentar_heredar_de_matriz,
    reencolar_pedidos_esperando_matriz,
    resolver_o_encolar_matriz,
)
from app.extraccion.orquestador import LOTE_UNICO, ejecutar_extraccion_expediente
from app.interfaces.document_storage import DocumentStorage
from app.models import (
    Documento,
    DocumentoExpediente,
    EstadoExpediente,
    EstadoTrabajo,
    Expediente,
    LineaCatalogo,
    Lote,
    ModeloPrecio,
    TipoDocumento,
    TrabajoCola,
    TrazaOrigen,
)
from tests import fixtures as fx


class _StorageDirecta(DocumentStorage):
    def guardar(self, nombre: str, contenido: bytes) -> str:
        raise NotImplementedError

    def recuperar(self, ruta: str) -> bytes:
        return Path(ruta).read_bytes()

    def listar(self, prefijo: str = "") -> list[str]:
        raise NotImplementedError


def _crear_expediente(db, codigo_expediente, **campos) -> Expediente:
    expediente = Expediente(codigo_expediente=codigo_expediente, **campos)
    db.add(expediente)
    db.commit()
    db.refresh(expediente)
    return expediente


def _crear_lote(db, expediente_id, identificador_lote=LOTE_UNICO, **campos) -> Lote:
    lote = Lote(expediente_id=expediente_id, identificador_lote=identificador_lote, **campos)
    db.add(lote)
    db.commit()
    db.refresh(lote)
    return lote


def _crear_documento(db, expediente_id, *, hash_, nombre_archivo, ruta_almacenamiento, tipo_documento) -> Documento:
    """Colisión de hash entre expedientes hermanos (2026-09-08, migración
    0021): `Documento` ya no tiene `expediente_id`/`nombre_archivo` propios --
    el enlace vive en `DocumentoExpediente`."""
    documento = Documento(tipo_documento=tipo_documento, hash=hash_, ruta_almacenamiento=ruta_almacenamiento)
    db.add(documento)
    db.commit()
    db.add(DocumentoExpediente(documento_id=documento.id, expediente_id=expediente_id, nombre_archivo=nombre_archivo))
    db.commit()
    return documento


# --- resolver_o_encolar_matriz -----------------------------------------


def test_sin_codigo_matriz_no_hace_nada(db_session):
    pedido = _crear_expediente(db_session, "6.24/28510.0001")
    resultado = resolver_o_encolar_matriz(db_session, pedido)
    assert resultado.estado == EstadoResolucionMatriz.sin_matriz


def test_matriz_nueva_se_crea_y_encola_su_descarga(db_session):
    pedido = _crear_expediente(db_session, "6.24/28510.0103", codigo_matriz="2.18/04703.0019")

    resultado = resolver_o_encolar_matriz(db_session, pedido)

    assert resultado.estado == EstadoResolucionMatriz.en_proceso
    matriz = db_session.query(Expediente).filter_by(codigo_expediente="2.18/04703.0019").one()
    assert resultado.matriz.id == matriz.id
    db_session.refresh(pedido)
    assert pedido.matriz_expediente_id == matriz.id

    trabajos = db_session.query(TrabajoCola).filter_by(expediente_id=matriz.id).all()
    assert len(trabajos) == 1
    assert trabajos[0].tipo == "descargar_expediente"
    assert trabajos[0].estado == EstadoTrabajo.pendiente


def test_matriz_existente_con_documentos_sin_procesar_encola_extraccion(db_session):
    matriz = _crear_expediente(db_session, "2.18/04703.0019")
    _crear_documento(
        db_session, matriz.id, hash_="h1", nombre_archivo="a.pdf",
        ruta_almacenamiento="/x/a.pdf", tipo_documento=TipoDocumento.otro,
    )
    pedido = _crear_expediente(db_session, "6.24/28510.0103", codigo_matriz="2.18/04703.0019")

    resultado = resolver_o_encolar_matriz(db_session, pedido)

    assert resultado.estado == EstadoResolucionMatriz.en_proceso
    trabajos = db_session.query(TrabajoCola).filter_by(expediente_id=matriz.id).all()
    assert len(trabajos) == 1
    assert trabajos[0].tipo == "extraer_expediente"


def test_matriz_en_curso_no_duplica_trabajo(db_session):
    matriz = _crear_expediente(db_session, "2.18/04703.0019", estado=EstadoExpediente.descargando)
    # Mientras el estado es "descargando" existe de verdad un trabajo
    # "descargar_expediente" en curso (es lo que puso ese estado) -- sin él,
    # esto no prueba nada distinto del caso "matriz nueva".
    db_session.add(TrabajoCola(
        tipo="descargar_expediente", expediente_id=matriz.id, estado=EstadoTrabajo.en_proceso,
    ))
    db_session.commit()
    pedido = _crear_expediente(db_session, "6.24/28510.0103", codigo_matriz="2.18/04703.0019")

    resultado = resolver_o_encolar_matriz(db_session, pedido)

    assert resultado.estado == EstadoResolucionMatriz.en_proceso
    assert db_session.query(TrabajoCola).count() == 1


def test_matriz_terminada_se_reporta_lista(db_session):
    matriz = _crear_expediente(db_session, "2.18/04703.0019", estado=EstadoExpediente.completado)
    pedido = _crear_expediente(db_session, "6.24/28510.0103", codigo_matriz="2.18/04703.0019")

    resultado = resolver_o_encolar_matriz(db_session, pedido)

    assert resultado.estado == EstadoResolucionMatriz.lista
    assert resultado.matriz.id == matriz.id
    assert db_session.query(TrabajoCola).count() == 0


def test_matriz_sin_publicar_se_reporta_lista_sin_reintentar_descarga(db_session):
    # CONTEXTO.md sección 22: `sin_publicar` es tan terminal como `fallido`
    # para esta resolución. Sin esto, una matriz confirmada como no
    # localizable en la Plataforma (sin documentos, sin trabajo activo)
    # volvería a encolar su descarga en cada pedido que la referencia,
    # reintentando para siempre una búsqueda ya cerrada.
    matriz = _crear_expediente(
        db_session, "2.18/04703.0019", estado=EstadoExpediente.sin_publicar,
        error="no encontrado en la Plataforma ni por matriz ni por expediente: 2.18/04703.0019",
    )
    pedido = _crear_expediente(db_session, "6.24/28510.0103", codigo_matriz="2.18/04703.0019")

    resultado = resolver_o_encolar_matriz(db_session, pedido)

    assert resultado.estado == EstadoResolucionMatriz.lista
    assert resultado.matriz.id == matriz.id
    assert db_session.query(TrabajoCola).count() == 0


def test_ciclo_autoreferencia_se_corta(db_session):
    # Caso real (CONTEXTO.md sección 19): 6.25/28510.0027 llegó a declararse su
    # propia matriz. No se crea ninguna fila nueva ni se encola nada.
    pedido = _crear_expediente(db_session, "6.25/28510.0027", codigo_matriz="6.25/28510.0027")

    resultado = resolver_o_encolar_matriz(db_session, pedido)

    assert resultado.estado == EstadoResolucionMatriz.ciclo
    assert db_session.query(Expediente).count() == 1
    assert db_session.query(TrabajoCola).count() == 0


def test_ciclo_de_cadena_larga_se_corta(db_session):
    # A -> B -> A: ninguno de los dos es una autorreferencia directa, pero
    # seguir la cadena desde A vuelve sobre A.
    _crear_expediente(db_session, "A", codigo_matriz="B")
    b = _crear_expediente(db_session, "B", codigo_matriz="A")
    pedido = db_session.query(Expediente).filter_by(codigo_expediente="A").one()

    resultado = resolver_o_encolar_matriz(db_session, pedido)

    assert resultado.estado == EstadoResolucionMatriz.ciclo
    # No se tocó nada de B ni se creó nada nuevo.
    assert db_session.query(Expediente).count() == 2
    assert db_session.query(TrabajoCola).count() == 0


# --- intentar_heredar_de_matriz -----------------------------------------


def test_hereda_lineas_y_baja_con_trazabilidad_al_documento_de_la_matriz(db_session):
    matriz = _crear_expediente(db_session, "2.18/04703.0019", estado=EstadoExpediente.completado)
    lote_matriz = _crear_lote(db_session, matriz.id, baja_lote=Decimal("0.10"))
    doc_matriz = _crear_documento(
        db_session, matriz.id, hash_="hm", nombre_archivo="anejo_matriz.pdf",
        ruta_almacenamiento="/x/m.pdf", tipo_documento=TipoDocumento.anejo,
    )
    db_session.add(TrazaOrigen(
        entidad_tipo="lote", entidad_id=lote_matriz.id, campo="baja_declarada",
        documento_id=doc_matriz.id, pagina=3, fragmento="baja del 10%", valor_extraido="0.10",
    ))
    db_session.add(LineaCatalogo(
        lote_id=lote_matriz.id, expediente_id=matriz.id, clave_linea="P-001", orden_aparicion=0,
        codigo_precio="P-001", descripcion="BRIDA X", precio_unitario=Decimal("100.00"),
        baja_lote=Decimal("0.10"), precio_adjudicado=Decimal("90.00"),
        documento_origen_id=doc_matriz.id, pagina=5, fragmento="P-001 BRIDA X 100,00",
    ))
    db_session.commit()

    pedido = _crear_expediente(db_session, "6.24/28510.0103", codigo_matriz="2.18/04703.0019")
    lote_pedido = _crear_lote(db_session, pedido.id)

    resultado = intentar_heredar_de_matriz(db_session, pedido, matriz, lote_pedido, total_lineas_propias=0)

    assert resultado.motivo_revision is None
    assert resultado.lineas_creadas == 1
    db_session.refresh(lote_pedido)
    assert lote_pedido.baja_lote == Decimal("0.10")
    assert lote_pedido.baja_heredada_de_matriz is True

    lineas_pedido = db_session.query(LineaCatalogo).filter_by(lote_id=lote_pedido.id).all()
    assert len(lineas_pedido) == 1
    linea = lineas_pedido[0]
    assert linea.heredado_de_matriz is True
    assert linea.precio_unitario == Decimal("100.00")
    assert linea.precio_adjudicado == Decimal("90.00")
    # Trazabilidad: el documento de origen sigue siendo el real de la
    # matriz, no uno inventado del pedido.
    assert linea.documento_origen_id == doc_matriz.id
    assert linea.pagina == 5

    traza_baja_pedido = (
        db_session.query(TrazaOrigen)
        .filter_by(entidad_tipo="lote", entidad_id=lote_pedido.id, campo="baja_declarada")
        .one()
    )
    assert traza_baja_pedido.documento_id == doc_matriz.id
    assert traza_baja_pedido.pagina == 3


def test_baja_propia_del_pedido_manda_sobre_la_de_la_matriz(db_session):
    matriz = _crear_expediente(db_session, "2.18/04703.0019", estado=EstadoExpediente.completado)
    lote_matriz = _crear_lote(db_session, matriz.id, baja_lote=Decimal("0.10"))
    db_session.add(LineaCatalogo(
        lote_id=lote_matriz.id, expediente_id=matriz.id, clave_linea="P-001", orden_aparicion=0,
        codigo_precio="P-001", descripcion="BRIDA X", precio_unitario=Decimal("100.00"),
        baja_lote=Decimal("0.10"), precio_adjudicado=Decimal("90.00"),
    ))
    db_session.commit()

    pedido = _crear_expediente(db_session, "6.24/28510.0103", codigo_matriz="2.18/04703.0019")
    # El pedido ya trae su propia baja (p.ej. de su propio contrato), pero
    # ningún cuadro de precios propio.
    lote_pedido = _crear_lote(db_session, pedido.id, baja_lote=Decimal("0.20"))

    resultado = intentar_heredar_de_matriz(db_session, pedido, matriz, lote_pedido, total_lineas_propias=0)

    assert resultado.motivo_revision is None
    db_session.refresh(lote_pedido)
    # La baja propia no se pisa con la de la matriz.
    assert lote_pedido.baja_lote == Decimal("0.20")
    assert lote_pedido.baja_heredada_de_matriz is None

    linea = db_session.query(LineaCatalogo).filter_by(lote_id=lote_pedido.id).one()
    # El precio adjudicado heredado usa la baja EFECTIVA del pedido (20 %),
    # no la que traía la línea de la matriz (10 %) — "lo propio manda".
    assert linea.baja_lote == Decimal("0.20")
    assert linea.precio_adjudicado == Decimal("80.00")


def test_lineas_propias_parciales_van_a_revision_con_el_conteo_exacto(db_session):
    matriz = _crear_expediente(db_session, "2.18/04703.0019", estado=EstadoExpediente.completado)
    lote_matriz = _crear_lote(db_session, matriz.id, baja_lote=Decimal("0.10"))
    for i in range(5):
        db_session.add(LineaCatalogo(
            lote_id=lote_matriz.id, expediente_id=matriz.id, clave_linea=f"P-{i}", orden_aparicion=i,
            codigo_precio=f"P-{i}", descripcion="X", precio_unitario=Decimal("10.00"),
        ))
    db_session.commit()

    pedido = _crear_expediente(db_session, "6.24/28510.0103", codigo_matriz="2.18/04703.0019")
    lote_pedido = _crear_lote(db_session, pedido.id)

    resultado = intentar_heredar_de_matriz(db_session, pedido, matriz, lote_pedido, total_lineas_propias=2)

    assert resultado.motivo_revision is not None
    assert "2" in resultado.motivo_revision
    assert "5" in resultado.motivo_revision
    # No se tocó nada: ninguna línea de la matriz se copió al pedido.
    assert db_session.query(LineaCatalogo).filter_by(lote_id=lote_pedido.id).count() == 0


def test_matriz_multilote_va_a_revision_ambigua(db_session):
    matriz = _crear_expediente(db_session, "2.18/04703.0019", estado=EstadoExpediente.completado)
    _crear_lote(db_session, matriz.id, identificador_lote="1", baja_lote=Decimal("0.10"))
    _crear_lote(db_session, matriz.id, identificador_lote="2", baja_lote=Decimal("0.20"))

    pedido = _crear_expediente(db_session, "6.24/28510.0103", codigo_matriz="2.18/04703.0019")
    lote_pedido = _crear_lote(db_session, pedido.id)

    resultado = intentar_heredar_de_matriz(db_session, pedido, matriz, lote_pedido, total_lineas_propias=0)

    assert resultado.motivo_revision is not None
    assert "multi-lote" in resultado.motivo_revision


def test_matriz_sin_datos_va_a_revision_citando_su_propio_motivo(db_session):
    matriz = _crear_expediente(
        db_session, "2.18/04703.0019", estado=EstadoExpediente.fallido, error="no se encontró en la Plataforma",
    )
    _crear_lote(db_session, matriz.id)  # sin baja, sin líneas

    pedido = _crear_expediente(db_session, "6.24/28510.0103", codigo_matriz="2.18/04703.0019")
    lote_pedido = _crear_lote(db_session, pedido.id)

    resultado = intentar_heredar_de_matriz(db_session, pedido, matriz, lote_pedido, total_lineas_propias=0)

    assert resultado.motivo_revision is not None
    assert "no se encontró en la Plataforma" in resultado.motivo_revision


def test_matriz_sin_publicar_va_a_revision_distinguible_de_fallido(db_session):
    # Caso real (CONTEXTO.md sección 22): los 8 pedidos cuya identidad se
    # corrigió (sección 21) dependen de una matriz confirmada `sin_publicar`,
    # no `fallido` — el pedido en sí es real y localizable, solo su matriz no
    # existe en la Plataforma. El motivo tiene que decir cuál de los dos es.
    matriz = _crear_expediente(
        db_session, "2.18/04703.0019", estado=EstadoExpediente.sin_publicar,
        error="no encontrado en la Plataforma ni por matriz ni por expediente: 2.18/04703.0019",
    )
    pedido = _crear_expediente(db_session, "6.24/28510.0103", codigo_matriz="2.18/04703.0019")
    lote_pedido = _crear_lote(db_session, pedido.id)

    resultado = intentar_heredar_de_matriz(db_session, pedido, matriz, lote_pedido, total_lineas_propias=0)

    assert resultado.motivo_revision is not None
    assert "sin_publicar" in resultado.motivo_revision


def test_hereda_modelo_precio_indexado_sin_marcarlo_como_fallo(db_session):
    """Ajuste 4 del encargo de descubrimiento inverso: un pedido derivado de
    una matriz de segunda familia (docs/identidad-expediente.md sección 28)
    no tiene, en sus propios documentos, ningún marcador que le permita
    detectar el modelo indexado por pedido -- verificado en vivo contra los
    18 documentos reales de los 9 pedidos conocidos (sesión de descubrimiento
    inverso): son formularios PCSP sin cuadro de precios propio. Sin esta
    propagación, el pedido se quedaba con `modelo_precio=fijo` (su valor por
    defecto) y `baja_lote=None`, indistinguible de un fallo real de
    extracción."""
    matriz = _crear_expediente(db_session, "6.23/28510.0018", estado=EstadoExpediente.completado)
    lote_matriz = _crear_lote(
        db_session, matriz.id,
        modelo_precio=ModeloPrecio.indexado_por_pedido, coeficiente_transformacion=Decimal("1.2760"),
    )
    db_session.add(LineaCatalogo(
        lote_id=lote_matriz.id, expediente_id=matriz.id, clave_linea="P-1", orden_aparicion=0,
        codigo_precio="P-1", descripcion="CARRIL 54E1", precio_unitario=Decimal("99.55"),
    ))
    db_session.commit()

    pedido = _crear_expediente(db_session, "6.24/28510.0040", codigo_matriz="6.23/28510.0018")
    lote_pedido = _crear_lote(db_session, pedido.id)

    resultado = intentar_heredar_de_matriz(db_session, pedido, matriz, lote_pedido, total_lineas_propias=0)

    assert resultado.motivo_revision is None
    db_session.refresh(lote_pedido)
    assert lote_pedido.modelo_precio == ModeloPrecio.indexado_por_pedido
    assert lote_pedido.coeficiente_transformacion == Decimal("1.2760")
    # La baja sigue sin existir (no hay dato que inventar), pero ya no se lee
    # como un hueco sin explicar -- `modelo_precio` es la marca explícita.
    assert lote_pedido.baja_lote is None


def test_revierte_modelo_precio_si_la_matriz_deja_de_declararlo(db_session):
    # Idempotencia (mismo criterio que app.extraccion.orquestador): un
    # reproceso de la matriz que ya no detecta el marcador no debe dejar un
    # `indexado_por_pedido` obsoleto colgando del pedido.
    matriz = _crear_expediente(db_session, "6.23/28510.0018", estado=EstadoExpediente.completado)
    lote_matriz = _crear_lote(db_session, matriz.id, baja_lote=Decimal("0.10"))
    db_session.add(LineaCatalogo(
        lote_id=lote_matriz.id, expediente_id=matriz.id, clave_linea="P-001", orden_aparicion=0,
        codigo_precio="P-001", descripcion="X", precio_unitario=Decimal("10.00"),
        baja_lote=Decimal("0.10"), precio_adjudicado=Decimal("9.00"),
    ))
    db_session.commit()

    pedido = _crear_expediente(db_session, "6.24/28510.0040", codigo_matriz="6.23/28510.0018")
    lote_pedido = _crear_lote(
        db_session, pedido.id,
        modelo_precio=ModeloPrecio.indexado_por_pedido, coeficiente_transformacion=Decimal("1.2760"),
    )

    resultado = intentar_heredar_de_matriz(db_session, pedido, matriz, lote_pedido, total_lineas_propias=0)

    assert resultado.motivo_revision is None
    db_session.refresh(lote_pedido)
    assert lote_pedido.modelo_precio == ModeloPrecio.fijo
    assert lote_pedido.coeficiente_transformacion is None


# --- reencolar_pedidos_esperando_matriz ----------------------------------


def test_reencola_solo_los_pedidos_esperando_esa_matriz(db_session):
    matriz = _crear_expediente(db_session, "2.18/04703.0019", estado=EstadoExpediente.completado)
    esperando_1 = _crear_expediente(
        db_session, "6.24/28510.0103", matriz_expediente_id=matriz.id, estado=EstadoExpediente.esperando_matriz,
    )
    esperando_2 = _crear_expediente(
        db_session, "6.24/28510.0104", matriz_expediente_id=matriz.id, estado=EstadoExpediente.esperando_matriz,
    )
    # Este referencia a la misma matriz pero ya está en revisión por otro
    # motivo -- reencolarlo sería ruido, no lo pidió nadie.
    _crear_expediente(
        db_session, "6.24/28510.0105", matriz_expediente_id=matriz.id, estado=EstadoExpediente.pendiente_revision,
    )

    total = reencolar_pedidos_esperando_matriz(db_session, matriz)

    assert total == 2
    trabajos = db_session.query(TrabajoCola).all()
    assert {t.expediente_id for t in trabajos} == {esperando_1.id, esperando_2.id}
    assert all(t.tipo == "extraer_expediente" for t in trabajos)


# --- extremo a extremo, con el fixture real que declara matriz ----------


def test_pedido_real_sin_matriz_creada_pasa_a_esperando_matriz(db_session):
    """Fixture real (CONTEXTO.md sección 17.1): el Anuncio PCSP de
    6.24/28510.0103 declara "Licitación basada en el acuerdo marco ->
    Expediente 2.18/04703.0019" y no trae cuadro de precios propio (es el
    patrón de los 14 pedidos derivados de docs/analisis-corpus.md hallazgo 3:
    solo 2 documentos PCSP, sin anejo)."""
    pedido = Expediente(codigo_expediente="6.24/28510.0103")
    db_session.add(pedido)
    db_session.commit()
    _crear_documento(
        db_session, pedido.id, hash_="h-pedido", nombre_archivo="ADJUDICACION_1.pdf",
        ruta_almacenamiento=str(fx.ANUNCIO_PCSP_CON_MATRIZ), tipo_documento=TipoDocumento.otro,
    )
    trabajo = SimpleNamespace(expediente_id=pedido.id)

    resultado = ejecutar_extraccion_expediente(db_session, _StorageDirecta(), trabajo, model_provider=None)

    db_session.refresh(pedido)
    assert pedido.codigo_matriz == "2.18/04703.0019"
    assert pedido.estado == EstadoExpediente.esperando_matriz
    assert resultado["estado"] == "esperando_matriz"

    matriz = db_session.query(Expediente).filter_by(codigo_expediente="2.18/04703.0019").one()
    assert pedido.matriz_expediente_id == matriz.id
    trabajo_matriz = db_session.query(TrabajoCola).filter_by(expediente_id=matriz.id).one()
    assert trabajo_matriz.tipo == "descargar_expediente"


def test_pedido_real_hereda_al_reprocesar_una_vez_la_matriz_esta_completa(db_session):
    """Continuación del caso anterior: una vez la matriz existe y ya se
    procesó (aquí, simulada a mano -- no vuelve a ejercitarse el scraping
    real), reprocesar el pedido lo completa por herencia, con el 54,00 % de
    baja y la línea de la matriz."""
    pedido = Expediente(codigo_expediente="6.24/28510.0103")
    db_session.add(pedido)
    db_session.commit()
    _crear_documento(
        db_session, pedido.id, hash_="h-pedido", nombre_archivo="ADJUDICACION_1.pdf",
        ruta_almacenamiento=str(fx.ANUNCIO_PCSP_CON_MATRIZ), tipo_documento=TipoDocumento.otro,
    )
    trabajo = SimpleNamespace(expediente_id=pedido.id)
    ejecutar_extraccion_expediente(db_session, _StorageDirecta(), trabajo, model_provider=None)
    db_session.refresh(pedido)
    matriz = db_session.query(Expediente).filter_by(codigo_expediente="2.18/04703.0019").one()

    # Simula que el trabajo de descarga+extracción de la matriz ya terminó
    # con éxito (fuera del alcance de este test: eso lo cubren los tests de
    # scraping y de la cascada de extracción por separado).
    matriz.estado = EstadoExpediente.completado
    lote_matriz = Lote(expediente_id=matriz.id, identificador_lote=LOTE_UNICO, baja_lote=Decimal("0.5400"))
    db_session.add(lote_matriz)
    db_session.commit()
    db_session.add(LineaCatalogo(
        lote_id=lote_matriz.id, expediente_id=matriz.id, clave_linea="P-001", orden_aparicion=0,
        codigo_precio="P-001", descripcion="POLO MANGA CORTA", precio_unitario=Decimal("24.00"),
        baja_lote=Decimal("0.5400"), precio_adjudicado=Decimal("11.04"),
    ))
    db_session.commit()

    resultado = reencolar_pedidos_esperando_matriz(db_session, matriz)
    assert resultado == 1
    db_session.commit()

    # El reencolado real lo ejecuta el worker; aquí se llama directamente al
    # mismo punto de entrada que usaría, sobre el mismo trabajo.
    resultado_pedido = ejecutar_extraccion_expediente(
        db_session, _StorageDirecta(), SimpleNamespace(expediente_id=pedido.id), model_provider=None,
    )

    db_session.refresh(pedido)
    assert pedido.estado == EstadoExpediente.completado
    assert pedido.baja_global == Decimal("0.5400")
    assert resultado_pedido["motivo_revision"] is None

    lineas = db_session.query(LineaCatalogo).filter_by(expediente_id=pedido.id).all()
    assert len(lineas) == 1
    assert lineas[0].heredado_de_matriz is True
    assert lineas[0].precio_adjudicado == Decimal("11.04")


def test_pedido_real_no_conserva_una_linea_que_ya_no_hereda(db_session):
    """Sesión 2026-09-15 (`4.25/28510.0207`): una línea que el pedido heredó
    en una pasada y que la matriz ya no trae no se quedaba para siempre --
    la poda por documento deja fuera las heredadas a propósito."""
    pedido = Expediente(codigo_expediente="6.24/28510.0103")
    db_session.add(pedido)
    db_session.commit()
    _crear_documento(
        db_session, pedido.id, hash_="h-pedido", nombre_archivo="ADJUDICACION_1.pdf",
        ruta_almacenamiento=str(fx.ANUNCIO_PCSP_CON_MATRIZ), tipo_documento=TipoDocumento.otro,
    )
    ejecutar_extraccion_expediente(db_session, _StorageDirecta(), SimpleNamespace(expediente_id=pedido.id))
    matriz = db_session.query(Expediente).filter_by(codigo_expediente="2.18/04703.0019").one()
    matriz.estado = EstadoExpediente.completado
    lote_matriz = Lote(expediente_id=matriz.id, identificador_lote=LOTE_UNICO, baja_lote=Decimal("0.5400"))
    db_session.add(lote_matriz)
    db_session.commit()
    for clave, descripcion in (("P-001", "POLO MANGA CORTA"), ("P-002", "POLO MANGA LARGA")):
        db_session.add(LineaCatalogo(
            lote_id=lote_matriz.id, expediente_id=matriz.id, clave_linea=clave, orden_aparicion=0,
            codigo_precio=clave, descripcion=descripcion, precio_unitario=Decimal("24.00"),
        ))
    db_session.commit()
    ejecutar_extraccion_expediente(db_session, _StorageDirecta(), SimpleNamespace(expediente_id=pedido.id))
    heredadas = {l.clave_linea: l.id for l in db_session.query(LineaCatalogo).filter_by(expediente_id=pedido.id)}
    assert set(heredadas) == {"P-001", "P-002"}

    db_session.query(LineaCatalogo).filter_by(expediente_id=matriz.id, clave_linea="P-002").delete()
    db_session.commit()
    resultado = ejecutar_extraccion_expediente(db_session, _StorageDirecta(), SimpleNamespace(expediente_id=pedido.id))

    quedan = {l.clave_linea: l.id for l in db_session.query(LineaCatalogo).filter_by(expediente_id=pedido.id)}
    assert quedan == {"P-001": heredadas["P-001"]}
    assert resultado["lineas_podadas"] == 1


def test_con_la_matriz_en_proceso_las_lineas_heredadas_se_conservan(db_session):
    """Mientras la matriz se descarga o se extrae, la herencia no se puede
    decidir: las líneas heredadas de una pasada anterior se quedan hasta que
    el pedido se reprocese con la matriz lista."""
    matriz = _crear_expediente(db_session, "2.18/04703.0019", estado=EstadoExpediente.descargando)
    db_session.add(TrabajoCola(
        tipo="descargar_expediente", expediente_id=matriz.id, estado=EstadoTrabajo.en_proceso,
    ))
    db_session.commit()
    pedido = _crear_expediente(db_session, "6.24/28510.0103")
    _crear_documento(
        db_session, pedido.id, hash_="h-pedido", nombre_archivo="ADJUDICACION_1.pdf",
        ruta_almacenamiento=str(fx.ANUNCIO_PCSP_CON_MATRIZ), tipo_documento=TipoDocumento.otro,
    )
    lote = _crear_lote(db_session, pedido.id)
    heredada = LineaCatalogo(
        lote_id=lote.id, expediente_id=pedido.id, clave_linea="P-001", orden_aparicion=0, codigo_precio="P-001",
        descripcion="POLO MANGA CORTA", precio_unitario=Decimal("24.00"), heredado_de_matriz=True,
    )
    db_session.add(heredada)
    db_session.commit()

    resultado = ejecutar_extraccion_expediente(db_session, _StorageDirecta(), SimpleNamespace(expediente_id=pedido.id))

    assert resultado["estado"] == "esperando_matriz"
    assert db_session.get(LineaCatalogo, heredada.id) is not None
    assert resultado["lineas_podadas"] == 0
