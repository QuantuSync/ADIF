"""Sesión de límite de tasa (2026-09-07): `descargar_zip_periodo` debe
distinguir un ZIP real de una página de bloqueo/límite de tasa servida con
código 200 -- un backfill real hizo fallar 11 periodos seguidos con "File is
not a zip file" justo después de 10 correctos, patrón de bloqueo bajo
carga, no de 11 meses genuinamente sin publicar."""
import httpx
import pytest

from app.sindicacion.cliente import DescargaSindicacionInvalidaError, descargar_zip_periodo


def _cliente_falso(respuesta_handler):
    """`httpx.stream` abre su propio cliente internamente -- se sustituye el
    transporte por uno que no toca la red, misma técnica que la documentación
    oficial de httpx para tests."""
    return httpx.Client(transport=httpx.MockTransport(respuesta_handler))


def test_descarga_zip_real_pasa_la_validacion(tmp_path, monkeypatch):
    contenido_zip = b"PK\x03\x04" + b"\x00" * 20

    def handler(request):
        return httpx.Response(200, content=contenido_zip)

    monkeypatch.setattr(httpx, "stream", lambda *a, **k: _cliente_falso(handler).stream(*a, **k))

    destino = tmp_path / "202409.zip"
    resultado = descargar_zip_periodo("202409", destino, timeout_segundos=5.0)

    assert resultado == destino
    assert destino.read_bytes() == contenido_zip


def test_pagina_de_bloqueo_servida_como_200_no_se_confunde_con_zip(tmp_path, monkeypatch):
    cuerpo_bloqueo = b"<html><body>Request Rejected - demasiadas peticiones</body></html>"

    def handler(request):
        return httpx.Response(200, content=cuerpo_bloqueo)

    monkeypatch.setattr(httpx, "stream", lambda *a, **k: _cliente_falso(handler).stream(*a, **k))

    destino = tmp_path / "202410.zip"
    with pytest.raises(DescargaSindicacionInvalidaError) as exc_info:
        descargar_zip_periodo("202410", destino, timeout_segundos=5.0)

    assert "Request Rejected" in str(exc_info.value) or "demasiadas peticiones" in str(exc_info.value)
    # El fichero a medias no se deja tirado como si fuera un ZIP válido.
    assert not destino.exists()


def test_404_real_se_propaga_como_error_http_no_como_invalido(tmp_path, monkeypatch):
    def handler(request):
        return httpx.Response(404, content=b"Not Found")

    monkeypatch.setattr(httpx, "stream", lambda *a, **k: _cliente_falso(handler).stream(*a, **k))

    destino = tmp_path / "202411.zip"
    with pytest.raises(httpx.HTTPStatusError):
        descargar_zip_periodo("202411", destino, timeout_segundos=5.0)
