"""Sesión de expedientes sin publicar (CONTEXTO.md sección 22):
`ExpedienteNoPublicadoError` es un resultado negativo determinista (no
localizable en la Plataforma por ninguna variante de búsqueda), distinto de
cualquier otro fallo de scraping (timeout, WAF, formulario no localizado).
`ejecutar_scraping_expediente` debe marcar el expediente `sin_publicar` (no
`fallido`) y no gastar más intentos reintentando una búsqueda que ya se sabe
que no cambia de resultado."""
from types import SimpleNamespace

import pytest

from app.models import Documento, EstadoExpediente, Expediente, TipoDocumento, TrabajoCola
from app.scraping.job import ejecutar_scraping_expediente
from app.scraping.pcsp import ExpedienteNoPublicadoError


def _crear_trabajo(db_session, codigo_expediente: str, estado: EstadoExpediente = EstadoExpediente.pendiente) -> TrabajoCola:
    expediente = Expediente(codigo_expediente=codigo_expediente, estado=estado)
    db_session.add(expediente)
    db_session.commit()
    trabajo = TrabajoCola(tipo="descargar_expediente", expediente_id=expediente.id, intentos=1, max_intentos=3)
    db_session.add(trabajo)
    db_session.commit()
    db_session.refresh(trabajo)
    return trabajo


def _sin_espera(monkeypatch):
    # `esperar_turno` (sesión de límite de tasa) usa un turno global en
    # memoria de proceso -- sin esto, el segundo test de este módulo que
    # llama a `ejecutar_scraping_expediente` heredaría el turno del primero
    # y dormiría de verdad varios segundos.
    monkeypatch.setattr("app.scraping.job.esperar_turno", lambda: None)


async def _scrape_no_encontrado(*args, **kwargs):
    raise ExpedienteNoPublicadoError(
        "no encontrado en la Plataforma ni por matriz ni por expediente: 2.18/04703.0019"
    )


async def _scrape_error_generico(*args, **kwargs):
    raise RuntimeError("Timeout esperando resultados")


def test_no_encontrado_marca_sin_publicar_y_agota_intentos(db_session, monkeypatch):
    _sin_espera(monkeypatch)
    monkeypatch.setattr("app.scraping.job.scrape_expediente", _scrape_no_encontrado)
    trabajo = _crear_trabajo(db_session, "2.18/04703.0019")

    with pytest.raises(ExpedienteNoPublicadoError):
        ejecutar_scraping_expediente(db_session, storage=SimpleNamespace(), trabajo=trabajo)

    expediente = db_session.get(Expediente, trabajo.expediente_id)
    assert expediente.estado == EstadoExpediente.sin_publicar
    assert "no encontrado en la Plataforma" in expediente.error
    # No tiene sentido reintentar una búsqueda que ya se sabe que no cambia
    # de resultado: se agotan los intentos aquí mismo.
    assert trabajo.intentos == trabajo.max_intentos


def test_error_generico_marca_fallido_sin_agotar_intentos(db_session, monkeypatch):
    _sin_espera(monkeypatch)
    monkeypatch.setattr("app.scraping.job.scrape_expediente", _scrape_error_generico)
    trabajo = _crear_trabajo(db_session, "6.24/28510.9999")
    intentos_originales = trabajo.intentos

    with pytest.raises(RuntimeError):
        ejecutar_scraping_expediente(db_session, storage=SimpleNamespace(), trabajo=trabajo)

    expediente = db_session.get(Expediente, trabajo.expediente_id)
    assert expediente.estado == EstadoExpediente.fallido
    # Un fallo genérico sí puede ser transitorio: no se tocan los intentos,
    # el reintento normal de la cola decide si vuelve a probar.
    assert trabajo.intentos == intentos_originales


# --- Sesión de límite de tasa (2026-09-07): un expediente que YA tiene
# documentos descargados no puede degradarse nunca por un fallo posterior de
# búsqueda -- caso real, `6.25/28510.0016` (matriz de carril verificada y
# completada) quedó marcada `sin_publicar` tras un reintento automático que
# coincidió con una tanda de cientos de descargas sin pausa.


def _con_un_documento(db_session, expediente: Expediente) -> None:
    db_session.add(
        Documento(
            expediente_id=expediente.id,
            tipo_documento=TipoDocumento.anuncio_pcsp,
            hash=f"hash-{expediente.id}",
            nombre_archivo="ADJUDICACION_1.pdf",
            ruta_almacenamiento=f"{expediente.codigo_expediente}/ADJUDICACION_1.pdf",
        )
    )
    db_session.commit()


def test_no_encontrado_con_documentos_no_baja_a_sin_publicar(db_session, monkeypatch):
    _sin_espera(monkeypatch)
    monkeypatch.setattr("app.scraping.job.scrape_expediente", _scrape_no_encontrado)
    trabajo = _crear_trabajo(db_session, "6.25/28510.0016", estado=EstadoExpediente.completado)
    expediente = db_session.get(Expediente, trabajo.expediente_id)
    _con_un_documento(db_session, expediente)

    with pytest.raises(ExpedienteNoPublicadoError):
        ejecutar_scraping_expediente(db_session, storage=SimpleNamespace(), trabajo=trabajo)

    db_session.refresh(expediente)
    # Nunca `sin_publicar`: se restaura el estado que ya tenía.
    assert expediente.estado == EstadoExpediente.completado
    assert "tratado como fallo transitorio" in expediente.error
    # Tampoco se agotan los intentos a la fuerza -- es un fallo reintentable
    # normal, no un negativo determinista.
    assert trabajo.intentos == 1


def test_error_generico_con_documentos_no_marca_fallido(db_session, monkeypatch):
    _sin_espera(monkeypatch)
    monkeypatch.setattr("app.scraping.job.scrape_expediente", _scrape_error_generico)
    trabajo = _crear_trabajo(db_session, "6.23/28510.0018", estado=EstadoExpediente.pendiente_revision)
    expediente = db_session.get(Expediente, trabajo.expediente_id)
    _con_un_documento(db_session, expediente)

    with pytest.raises(RuntimeError):
        ejecutar_scraping_expediente(db_session, storage=SimpleNamespace(), trabajo=trabajo)

    db_session.refresh(expediente)
    assert expediente.estado == EstadoExpediente.pendiente_revision


def test_no_encontrado_sin_documentos_sigue_marcando_sin_publicar(db_session, monkeypatch):
    # Guarda de regresión: la nueva comprobación no debe tocar el
    # comportamiento de siempre para un expediente que de verdad no tiene
    # nada descargado todavía.
    _sin_espera(monkeypatch)
    monkeypatch.setattr("app.scraping.job.scrape_expediente", _scrape_no_encontrado)
    trabajo = _crear_trabajo(db_session, "2.18/04703.0099")

    with pytest.raises(ExpedienteNoPublicadoError):
        ejecutar_scraping_expediente(db_session, storage=SimpleNamespace(), trabajo=trabajo)

    expediente = db_session.get(Expediente, trabajo.expediente_id)
    assert expediente.estado == EstadoExpediente.sin_publicar
