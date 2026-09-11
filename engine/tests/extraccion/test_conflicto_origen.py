"""Bloque 6, sesión de comparación documento-vs-listado interno: política
confirmada por el cliente -- cuando el mismo expediente trae, para el mismo
tipo de documento, uno descargado de la Plataforma y uno aportado a mano,
gana la Plataforma, y el aportado a mano no se pierde en silencio (aviso
informativo). Prueba las dos piezas puras de `app.extraccion.orquestador`
sin base de datos ni PDFs reales -- objetos `Documento`/`_Documento`
sueltos, nunca persistidos."""
from __future__ import annotations

from app.extraccion.orquestador import _Documento, _detectar_conflicto_origen, _priorizar_por_origen
from app.models import Documento, OrigenDocumento, TipoDocumento


def _doc(tipo: TipoDocumento, origen: OrigenDocumento, id_: int) -> _Documento:
    documento = Documento(id=id_, tipo_documento=tipo, hash=f"hash-{id_}", ruta_almacenamiento="x", origen=origen)
    return _Documento(documento=documento, tipo=tipo, paginas=[])


def test_priorizar_por_origen_deja_plataforma_antes_que_manual():
    manual = _doc(TipoDocumento.contrato, OrigenDocumento.manual, 1)
    plataforma = _doc(TipoDocumento.contrato, OrigenDocumento.plataforma, 2)

    resultado = _priorizar_por_origen([manual, plataforma])

    assert [item.documento.id for item in resultado] == [2, 1]


def test_priorizar_por_origen_es_estable_dentro_del_mismo_origen():
    a = _doc(TipoDocumento.anuncio_pcsp, OrigenDocumento.plataforma, 1)
    b = _doc(TipoDocumento.contrato, OrigenDocumento.plataforma, 2)
    c = _doc(TipoDocumento.anejo, OrigenDocumento.manual, 3)
    d = _doc(TipoDocumento.pliego, OrigenDocumento.manual, 4)

    resultado = _priorizar_por_origen([a, c, b, d])

    assert [item.documento.id for item in resultado] == [1, 2, 3, 4]


def test_detectar_conflicto_origen_sin_documentos_manuales_no_avisa():
    items = [_doc(TipoDocumento.contrato, OrigenDocumento.plataforma, 1)]
    assert _detectar_conflicto_origen(items) is None


def test_detectar_conflicto_origen_solo_manual_no_avisa():
    # Es exactamente el caso real de los 211 expedientes de esta sesión: sin
    # ninguna contraparte publicada, el aportado a mano manda sin discusión
    # -- no hay "conflicto" que señalar, solo una fuente.
    items = [_doc(TipoDocumento.anejo, OrigenDocumento.manual, 1)]
    assert _detectar_conflicto_origen(items) is None


def test_detectar_conflicto_origen_mismo_tipo_dos_origenes_avisa():
    items = [
        _doc(TipoDocumento.contrato, OrigenDocumento.plataforma, 1),
        _doc(TipoDocumento.contrato, OrigenDocumento.manual, 2),
    ]
    aviso = _detectar_conflicto_origen(items)
    assert aviso is not None
    assert "contrato" in aviso


def test_detectar_conflicto_origen_tipos_distintos_no_avisa():
    # Un Anuncio PCSP de la Plataforma y un Contrato aportado a mano no son
    # "el mismo hecho por partida doble" -- son dos documentos distintos y
    # complementarios, nada que contrastar entre sí.
    items = [
        _doc(TipoDocumento.anuncio_pcsp, OrigenDocumento.plataforma, 1),
        _doc(TipoDocumento.contrato, OrigenDocumento.manual, 2),
    ]
    assert _detectar_conflicto_origen(items) is None


def test_detectar_conflicto_origen_anejo_pliego_otro_fuera_del_alcance():
    # `anejo` sí se vigila (dos cuadros de precios de origen distinto es un
    # desacuerdo real); `pliego`/`otro` no declaran ningún hecho propio del
    # expediente, así que quedan fuera aunque coincidan en tipo y difieran
    # en origen.
    items = [
        _doc(TipoDocumento.pliego, OrigenDocumento.plataforma, 1),
        _doc(TipoDocumento.pliego, OrigenDocumento.manual, 2),
        _doc(TipoDocumento.otro, OrigenDocumento.plataforma, 3),
        _doc(TipoDocumento.otro, OrigenDocumento.manual, 4),
    ]
    assert _detectar_conflicto_origen(items) is None
