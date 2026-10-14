"""El modelo de IA, configurable (sesión 2026-10-14).

Las dos vías -- la API de siempre y un servicio con el protocolo de chat de
OpenAI, que es como se habla con el servicio de IA del cliente -- se prueban
de punta a punta leyendo un documento escaneado, cada una con un doble en el
sitio de la red: un cliente falso del SDK en la primera y un transporte falso
de `httpx` en la segunda. Ninguna prueba sale a la red.

Además: sin clave el sistema funciona y dice qué no puede hacer, y cambiar de
proveedor no vuelve a leer nada de lo ya leído."""
from __future__ import annotations

import base64
import json
from types import SimpleNamespace

import httpx
import pytest

from app.config import settings
from app.extraccion.ocr import _leer_pagina
from app.interfaces.model_provider import (
    APIModelProvider,
    OpenAICompatibleModelProvider,
    RespuestaTruncada,
    crear_proveedor_modelo,
    describir_proveedor_modelo,
)
from app.models import CacheOcrDocumento, Expediente, LineaCatalogo
from tests.extraccion.dobles import ProveedorVisionFalso
from tests.extraccion.test_ocr import _extraer, _pdf_escaneado
from tests.extraccion.test_orquestador import _crear_expediente_con_documentos


class _ServicioOpenAIFalso:
    """Transporte de `httpx` que hace de servicio remoto: guarda cada petición
    y contesta con lo que diga `ProveedorVisionFalso`, envuelto como lo
    devuelve el protocolo de chat."""

    def __init__(self, finish_reason: str = "stop", estado: int = 200):
        self.peticiones: list[httpx.Request] = []
        self.vision = ProveedorVisionFalso()
        self._finish_reason = finish_reason
        self._estado = estado

    def __call__(self, peticion: httpx.Request) -> httpx.Response:
        self.peticiones.append(peticion)
        if self._estado != 200:
            return httpx.Response(self._estado, json={"error": {"message": "clave no válida"}})
        cuerpo = json.loads(peticion.content)
        contenido = cuerpo["messages"][0]["content"]
        if isinstance(contenido, list):
            respuesta = self.vision.completar_con_imagen("", b"")
        else:
            respuesta = {"descripcion": 1}
        return httpx.Response(200, json={
            "choices": [{"message": {"role": "assistant", "content": json.dumps(respuesta)},
                         "finish_reason": self._finish_reason}],
            "usage": {"prompt_tokens": 1200, "completion_tokens": 300},
        })

    def cuerpos(self) -> list[dict]:
        return [json.loads(p.content) for p in self.peticiones]


def _proveedor_openai(servicio, **kwargs) -> OpenAICompatibleModelProvider:
    return OpenAICompatibleModelProvider(
        api_key="clave-del-cliente", modelo="despliegue-vision", endpoint="https://servicio.ejemplo/openai/v1/",
        transporte=httpx.MockTransport(servicio), **kwargs,
    )


def _sdk_falso(monkeypatch):
    """Cliente falso del SDK de la vía de siempre, que contesta con
    `ProveedorVisionFalso`."""
    import anthropic

    vision = ProveedorVisionFalso()
    peticiones = []

    class Bloque:
        type = "text"

        def __init__(self, texto):
            self.text = texto

    class Respuesta:
        def __init__(self, texto):
            self.content = [Bloque(texto)]
            self.usage = SimpleNamespace(input_tokens=1000, output_tokens=200)
            self.stop_reason = "end_turn"

    class Mensajes:
        def create(self, **kwargs):
            peticiones.append(kwargs)
            return Respuesta(json.dumps(vision.completar_con_imagen("", b"")))

    class Cliente:
        def __init__(self, *args, **kwargs):
            self.messages = Mensajes()

    monkeypatch.setattr(anthropic, "Anthropic", Cliente)
    return peticiones


# --- La vía nueva, pieza a pieza -------------------------------------------


def test_via_openai_arma_la_peticion_del_protocolo_y_lee_el_json():
    servicio = _ServicioOpenAIFalso()
    proveedor = _proveedor_openai(servicio)
    esquema = {"type": "object", "properties": {"descripcion": {"type": "integer"}}}

    assert proveedor.completar("mapea esta cabecera", esquema=esquema) == {"descripcion": 1}

    peticion = servicio.peticiones[0]
    assert str(peticion.url) == "https://servicio.ejemplo/openai/v1/chat/completions"
    assert peticion.headers["api-key"] == "clave-del-cliente"
    assert peticion.headers["authorization"] == "Bearer clave-del-cliente"
    cuerpo = servicio.cuerpos()[0]
    assert cuerpo["model"] == "despliegue-vision"
    assert cuerpo["messages"] == [{"role": "user", "content": "mapea esta cabecera"}]
    assert cuerpo["response_format"]["json_schema"]["schema"] == esquema
    assert proveedor.uso_ultima_llamada == (1200, 300)


def test_via_openai_con_formato_antiguo_por_despliegue_manda_la_version():
    servicio = _ServicioOpenAIFalso()
    proveedor = OpenAICompatibleModelProvider(
        api_key="k", modelo="d", endpoint="https://servicio.ejemplo/openai/deployments/d",
        api_version="2024-10-21", transporte=httpx.MockTransport(servicio),
    )
    proveedor.completar("x")
    assert str(servicio.peticiones[0].url) == (
        "https://servicio.ejemplo/openai/deployments/d/chat/completions?api-version=2024-10-21"
    )


def test_via_openai_manda_la_pagina_como_imagen():
    servicio = _ServicioOpenAIFalso()
    _proveedor_openai(servicio).completar_con_imagen("transcribe", b"\x89PNG-falso", esquema={"type": "object"})
    partes = servicio.cuerpos()[0]["messages"][0]["content"]
    assert partes[0]["type"] == "image_url"
    assert partes[0]["image_url"]["url"] == "data:image/png;base64," + base64.b64encode(b"\x89PNG-falso").decode()
    assert partes[1] == {"type": "text", "text": "transcribe"}


def test_via_openai_respuesta_cortada_no_se_reintenta():
    proveedor = _proveedor_openai(_ServicioOpenAIFalso(finish_reason="length"))
    with pytest.raises(RespuestaTruncada):
        proveedor.completar_con_imagen("p", b"img")
    pagina = _leer_pagina(b"img", 3, proveedor)
    assert pagina["error"] and pagina["reintentar"] is False


def test_via_openai_clave_mala_deja_la_pagina_pendiente_de_reintentar():
    pagina = _leer_pagina(b"img", 1, _proveedor_openai(_ServicioOpenAIFalso(estado=401)))
    assert "401" in pagina["error"]
    assert pagina["reintentar"] is True


# --- Elegir por configuración ----------------------------------------------


def _config(**valores):
    base = dict(
        model_api_key=None, model_id=None, model_proveedor="anthropic", model_endpoint=None,
        model_api_version=None, model_workspace_id=None, ocr_modo="escaneados",
    )
    base.update(valores)
    return SimpleNamespace(**base)


def test_la_configuracion_elige_el_proveedor_sin_tocar_codigo(monkeypatch):
    _sdk_falso(monkeypatch)
    assert isinstance(crear_proveedor_modelo(_config(model_api_key="k", model_id="m")), APIModelProvider)
    nuevo = crear_proveedor_modelo(_config(
        model_api_key="k", model_id="despliegue", model_proveedor="openai", model_endpoint="https://s/openai/v1",
    ))
    assert isinstance(nuevo, OpenAICompatibleModelProvider)
    with pytest.raises(ValueError):
        crear_proveedor_modelo(_config(model_api_key="k", model_id="d", model_proveedor="openai"))  # sin dirección
    with pytest.raises(ValueError):
        crear_proveedor_modelo(_config(model_api_key="k", model_id="m", model_proveedor="otro"))


def test_sin_clave_no_hay_proveedor_y_se_dice_con_claridad():
    assert crear_proveedor_modelo(_config(model_proveedor="openai")) is None
    descripcion = describir_proveedor_modelo(_config())
    assert descripcion["configurado"] is False
    assert descripcion["lee_escaneados_nuevos"] is False
    assert "escaneados nuevos" in descripcion["aviso"]
    assert "exportar funciona" in descripcion["aviso"]


def test_la_descripcion_nunca_lleva_la_clave():
    descripcion = describir_proveedor_modelo(_config(model_api_key="secreto-123", model_id="m"))
    assert "secreto-123" not in json.dumps(descripcion)
    assert descripcion["configurado"] is True


# --- De punta a punta sobre un escaneado -------------------------------------


@pytest.fixture()
def escaneado(db_session, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "ocr_paralelismo", 1)
    return _crear_expediente_con_documentos(db_session, "6.20/28510.0136", [("ANEJO", _pdf_escaneado(tmp_path, 4))])


def _lineas(db_session, expediente: Expediente) -> list[tuple]:
    return sorted(
        (l.codigo_precio, l.descripcion, l.precio_unitario)
        for l in db_session.query(LineaCatalogo).filter_by(expediente_id=expediente.id)
    )


def test_via_de_siempre_lee_un_escaneado(db_session, monkeypatch, escaneado):
    peticiones = _sdk_falso(monkeypatch)
    monkeypatch.setattr(settings, "model_id", "modelo-de-siempre")
    _extraer(db_session, escaneado, APIModelProvider(api_key="k", modelo="modelo-de-siempre"))
    assert len(peticiones) == 4
    assert _lineas(db_session, escaneado)


def test_via_openai_lee_un_escaneado(db_session, monkeypatch, escaneado):
    servicio = _ServicioOpenAIFalso()
    monkeypatch.setattr(settings, "model_id", "despliegue-vision")
    _extraer(db_session, escaneado, _proveedor_openai(servicio))
    assert len(servicio.peticiones) == 4
    assert _lineas(db_session, escaneado)
    assert db_session.query(CacheOcrDocumento).one().modelo == "despliegue-vision"


def test_cambiar_de_proveedor_no_vuelve_a_leer_lo_ya_leido(db_session, monkeypatch, escaneado):
    _sdk_falso(monkeypatch)
    monkeypatch.setattr(settings, "model_id", "modelo-de-siempre")
    _extraer(db_session, escaneado, APIModelProvider(api_key="k", modelo="modelo-de-siempre"))
    antes = _lineas(db_session, escaneado)

    servicio = _ServicioOpenAIFalso()
    monkeypatch.setattr(settings, "model_id", "despliegue-vision")
    _extraer(db_session, escaneado, _proveedor_openai(servicio))

    assert servicio.peticiones == []
    assert _lineas(db_session, escaneado) == antes
    assert db_session.query(CacheOcrDocumento).one().modelo == "modelo-de-siempre"


def test_sin_clave_lo_ya_leido_sigue_saliendo_de_la_cache(db_session, monkeypatch, escaneado):
    _extraer(db_session, escaneado, ProveedorVisionFalso())
    antes = _lineas(db_session, escaneado)
    assert antes

    resultado = _extraer(db_session, escaneado, None)

    assert _lineas(db_session, escaneado) == antes
    assert "no hay modelo de IA configurado" not in (resultado["motivo_revision"] or "")


def test_sin_clave_un_escaneado_nuevo_queda_en_revision_diciendo_por_que(db_session, escaneado):
    resultado = _extraer(db_session, escaneado, None)
    assert "no hay modelo de IA configurado" in resultado["motivo_revision"]
    assert _lineas(db_session, escaneado) == []


def test_la_pantalla_de_mantenimiento_dice_si_hay_modelo(monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import app

    monkeypatch.setattr(settings, "model_api_key", None)
    respuesta = TestClient(app).get("/mantenimiento/modelo-ia")
    assert respuesta.status_code == 200
    assert respuesta.json()["configurado"] is False
    assert "escaneados nuevos" in respuesta.json()["aviso"]

    monkeypatch.setattr(settings, "model_api_key", "secreto-123")
    respuesta = TestClient(app).get("/mantenimiento/modelo-ia")
    assert respuesta.json()["configurado"] is True
    assert "secreto-123" not in respuesta.text
