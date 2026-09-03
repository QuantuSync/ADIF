"""Sesión de expedientes sin publicar (CLAUDE.md sección 22):
`ExpedienteNoPublicadoError` es un resultado negativo determinista (no
localizable en la Plataforma por ninguna variante de búsqueda), distinto de
cualquier otro fallo de scraping (timeout, WAF, formulario no localizado).
`ejecutar_scraping_expediente` debe marcar el expediente `sin_publicar` (no
`fallido`) y no gastar más intentos reintentando una búsqueda que ya se sabe
que no cambia de resultado."""
from types import SimpleNamespace

import pytest

from app.models import EstadoExpediente, Expediente, TrabajoCola
from app.scraping.job import ejecutar_scraping_expediente
from app.scraping.pcsp import ExpedienteNoPublicadoError


def _crear_trabajo(db_session, codigo_expediente: str) -> TrabajoCola:
    expediente = Expediente(codigo_expediente=codigo_expediente)
    db_session.add(expediente)
    db_session.commit()
    trabajo = TrabajoCola(tipo="descargar_expediente", expediente_id=expediente.id, intentos=1, max_intentos=3)
    db_session.add(trabajo)
    db_session.commit()
    db_session.refresh(trabajo)
    return trabajo


async def _scrape_no_encontrado(*args, **kwargs):
    raise ExpedienteNoPublicadoError(
        "no encontrado en la Plataforma ni por matriz ni por expediente: 2.18/04703.0019"
    )


async def _scrape_error_generico(*args, **kwargs):
    raise RuntimeError("Timeout esperando resultados")


def test_no_encontrado_marca_sin_publicar_y_agota_intentos(db_session, monkeypatch):
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
