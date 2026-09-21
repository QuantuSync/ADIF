"""Bloque 4, sesión 2026-09-19 (decisión del cliente): `19/28510` y
`6.19/28510.0129` son el mismo expediente -- el barrido del buscador de la
Plataforma creó los dos con 0,1 s de diferencia, con el mismo título, el
mismo importe y los MISMOS dos documentos. `19/28510` es el número completo
recortado. Se unifican con el código completo como bueno.
"""
from decimal import Decimal

from app.extraccion.identidad_expediente import detectar_expediente_recortado, fusionar_en
from app.models import (
    Documento,
    DocumentoExpediente,
    Expediente,
    LineaCatalogo,
    Lote,
    TipoDocumento,
)

_TITULO = "SUMINISTRO DE TORNILLOS Y TIRAFONDOS DE VÍA PARA NECESIDADES DE LA RED"


def _documento(db_session, sufijo):
    documento = Documento(
        tipo_documento=TipoDocumento.otro,
        hash=f"hash-{sufijo}",
        ruta_almacenamiento=f"ruta/{sufijo}.pdf",
    )
    db_session.add(documento)
    db_session.commit()
    return documento


def _expediente(db_session, codigo, documentos, titulo=_TITULO, **campos):
    expediente = Expediente(codigo_expediente=codigo, nombre_proyecto=titulo, **campos)
    db_session.add(expediente)
    db_session.commit()
    for documento in documentos:
        db_session.add(DocumentoExpediente(
            documento_id=documento.id, expediente_id=expediente.id, nombre_archivo=f"{codigo}.pdf",
        ))
    db_session.commit()
    return expediente


def test_detecta_el_recorte_solo_con_las_tres_condiciones(db_session):
    documentos = [_documento(db_session, "a"), _documento(db_session, "b")]
    completo = _expediente(db_session, "6.19/28510.0129", documentos)
    recortado = _expediente(db_session, "19/28510", documentos)

    assert detectar_expediente_recortado(db_session, recortado) is not None
    assert detectar_expediente_recortado(db_session, recortado).id == completo.id
    # Nunca al revés: el largo no es un recorte del corto.
    assert detectar_expediente_recortado(db_session, completo) is None


def test_con_documentos_distintos_no_se_fusiona(db_session):
    a, b, c = _documento(db_session, "a"), _documento(db_session, "b"), _documento(db_session, "c")
    _expediente(db_session, "6.19/28510.0129", [a, b])
    recortado = _expediente(db_session, "19/28510", [a, c])
    assert detectar_expediente_recortado(db_session, recortado) is None


def test_con_titulo_distinto_no_se_fusiona(db_session):
    documentos = [_documento(db_session, "a")]
    _expediente(db_session, "6.19/28510.0129", documentos)
    recortado = _expediente(db_session, "19/28510", documentos, titulo="OTRA COSA")
    assert detectar_expediente_recortado(db_session, recortado) is None


def test_sin_documentos_no_se_fusiona(db_session):
    """Sin la prueba del fichero compartido, dos códigos parecidos son solo
    dos códigos parecidos."""
    _expediente(db_session, "6.19/28510.0129", [])
    recortado = _expediente(db_session, "19/28510", [])
    assert detectar_expediente_recortado(db_session, recortado) is None


def test_la_fusion_no_deja_nada_apuntando_al_codigo_viejo(db_session):
    documentos = [_documento(db_session, "a"), _documento(db_session, "b")]
    completo = _expediente(db_session, "6.19/28510.0129", documentos)
    recortado = _expediente(db_session, "19/28510", documentos)
    lote_completo = Lote(expediente_id=completo.id, identificador_lote="1", baja_lote=Decimal("0.1025"))
    lote_recortado = Lote(expediente_id=recortado.id, identificador_lote="1", baja_lote=Decimal("0.1025"))
    lote_solo_del_recortado = Lote(expediente_id=recortado.id, identificador_lote="2")
    db_session.add_all([lote_completo, lote_recortado, lote_solo_del_recortado])
    db_session.commit()
    db_session.add(LineaCatalogo(
        lote_id=lote_solo_del_recortado.id, expediente_id=recortado.id,
        clave_linea="P-1", orden_aparicion=1, descripcion="tirafondo",
    ))
    db_session.commit()

    resumen = fusionar_en(db_session, recortado, completo)

    assert "19/28510" in resumen and "6.19/28510.0129" in resumen
    assert db_session.query(Expediente).filter_by(codigo_expediente="19/28510").one_or_none() is None
    # El lote que el canónico ya tenía no se duplica; el que solo tenía el
    # recortado pasa entero, con su línea.
    assert sorted(l.identificador_lote for l in completo.lotes) == ["1", "2"]
    assert db_session.query(LineaCatalogo).filter_by(expediente_id=completo.id).count() == 1
    assert db_session.query(LineaCatalogo).count() == 1
    # Ni una huérfana apuntando al código viejo.
    assert db_session.query(Lote).filter_by(expediente_id=recortado.id).count() == 0
    assert db_session.query(DocumentoExpediente).filter_by(expediente_id=recortado.id).count() == 0
    # Y ningún documento se pierde: los dos siguen colgando del canónico.
    assert db_session.query(DocumentoExpediente).filter_by(expediente_id=completo.id).count() == 2
    assert db_session.query(Documento).count() == 2


def test_la_ficha_con_otro_separador_se_unifica_sin_perder_nada(db_session):
    """Sesión 2026-09-21 (segunda parte), bloque 3: `6.25/28510.5001_01` (alta
    del 2026-09-03 desde un nombre de carpeta) y `6.25/28510.5001/01` (la forma
    de ADIF) son la misma ficha. Gana la de la barra y no se pierde nada de la
    otra: su lote, sus trabajos de cola, su fecha de alta, más antigua."""
    from datetime import datetime, timezone

    from app.extraccion.identidad_expediente import unificar_ficha_duplicada
    from app.models import TrabajoCola

    documento = _documento(db_session, "g")
    guion = _expediente(
        db_session, "6.25/28510.5001_01", [documento], titulo=None,
        created_at=datetime(2026, 9, 3, tzinfo=timezone.utc),
    )
    barra = _expediente(
        db_session, "6.25/28510.5001/01", [], titulo="Suministro de repuestos de engrasadores",
        codigo_interno="24037", created_at=datetime(2026, 9, 7, tzinfo=timezone.utc),
    )
    db_session.add(Lote(expediente_id=guion.id, identificador_lote="1"))
    db_session.add(TrabajoCola(tipo="descargar_expediente", expediente_id=guion.id))
    db_session.commit()
    # Con la relación ya cargada, como en la unificación real: sin mover los
    # lotes por UPDATE, borrar el duplicado les ponía `expediente_id` a NULL.
    assert len(guion.lotes) == 1

    texto = unificar_ficha_duplicada(db_session, guion, barra)

    assert db_session.query(Expediente).filter_by(codigo_expediente="6.25/28510.5001_01").count() == 0
    unida = db_session.query(Expediente).filter_by(codigo_expediente="6.25/28510.5001/01").one()
    assert unida.nombre_proyecto == "Suministro de repuestos de engrasadores"
    assert unida.codigo_interno == "24037"
    assert unida.created_at.date().isoformat() == "2026-09-03"
    assert [l.identificador_lote for l in db_session.query(Lote).filter_by(expediente_id=unida.id)] == ["1"]
    assert db_session.query(TrabajoCola).filter_by(expediente_id=unida.id).count() == 1
    assert [d.documento_id for d in db_session.query(DocumentoExpediente).filter_by(expediente_id=unida.id)] == [
        documento.id
    ]
    assert "created_at" in texto
