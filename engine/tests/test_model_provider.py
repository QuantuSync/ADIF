import json

from app.interfaces.model_provider import AnthropicModelProvider, CachedModelProvider
from tests.extraccion.dobles import ProveedorModeloContador


def test_cached_model_provider_no_repite_llamadas_para_el_mismo_prompt(tmp_path):
    interior = ProveedorModeloContador(_ProveedorFijo({"campo": 1}))
    proveedor = CachedModelProvider(interior, tmp_path)

    r1 = proveedor.completar("cabecera X", esquema={"type": "object"})
    r2 = proveedor.completar("cabecera X", esquema={"type": "object"})

    assert r1 == {"campo": 1}
    assert r2 == {"campo": 1}
    assert interior.llamadas == 1  # la segunda vez se sirvió desde disco


def test_cached_model_provider_prompts_distintos_no_comparten_cache(tmp_path):
    interior = ProveedorModeloContador(_ProveedorFijo({"campo": 1}))
    proveedor = CachedModelProvider(interior, tmp_path)

    proveedor.completar("cabecera X", esquema=None)
    proveedor.completar("cabecera Y", esquema=None)

    assert interior.llamadas == 2


def test_cached_model_provider_persiste_en_disco_entre_instancias(tmp_path):
    interior1 = ProveedorModeloContador(_ProveedorFijo({"campo": 1}))
    CachedModelProvider(interior1, tmp_path).completar("cabecera X", esquema=None)

    # Nueva instancia, mismo directorio: no debería llamar al interior.
    interior2 = ProveedorModeloContador(_ProveedorFijo({"campo": 1}))
    resultado = CachedModelProvider(interior2, tmp_path).completar("cabecera X", esquema=None)

    assert resultado == {"campo": 1}
    assert interior2.llamadas == 0
    assert len(list(tmp_path.glob("*.json"))) == 1


class _ProveedorFijo:
    def __init__(self, respuesta):
        self._respuesta = respuesta

    def completar(self, prompt, esquema=None):
        return dict(self._respuesta)


def test_anthropic_model_provider_construye_la_peticion_y_parsea_json_estructurado(monkeypatch):
    """Sin red: se sustituye `anthropic.Anthropic` por un doble que capta
    los kwargs de la llamada y devuelve una respuesta con la forma real del
    SDK (un bloque de texto con JSON válido)."""
    peticiones = []

    class BloqueTexto:
        type = "text"

        def __init__(self, texto):
            self.text = texto

    class RespuestaFalsa:
        def __init__(self, texto):
            self.content = [BloqueTexto(texto)]

    class MessagesFalso:
        def create(self, **kwargs):
            peticiones.append(kwargs)
            return RespuestaFalsa(json.dumps({"descripcion": 1, "precio_unitario": 2}))

    class ClienteFalso:
        def __init__(self, *args, **kwargs):
            self.messages = MessagesFalso()

    import anthropic

    monkeypatch.setattr(anthropic, "Anthropic", ClienteFalso)

    proveedor = AnthropicModelProvider(api_key="sk-test", modelo="claude-opus-5")
    esquema = {"type": "object", "properties": {"descripcion": {"type": "integer"}}}
    resultado = proveedor.completar("mapea esta cabecera", esquema=esquema)

    assert resultado == {"descripcion": 1, "precio_unitario": 2}
    assert len(peticiones) == 1
    peticion = peticiones[0]
    assert peticion["model"] == "claude-opus-5"
    assert peticion["output_config"] == {"format": {"type": "json_schema", "schema": esquema}}
    assert peticion["messages"] == [{"role": "user", "content": "mapea esta cabecera"}]
