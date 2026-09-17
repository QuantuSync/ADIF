import json
import hashlib
import logging
import threading
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class RespuestaTruncada(RuntimeError):
    """La respuesta no cabe en `max_tokens`: repetir la misma petición da lo
    mismo, así que quien llama no debe reintentarla."""


class ModelProvider(ABC):
    """Interfaz de acceso al modelo. CONTEXTO.md secciones 6 y 9.2:
    misma firma para la API comercial de hoy y un modelo autoalojado mañana."""

    @abstractmethod
    def completar(self, prompt: str, esquema: Optional[dict] = None) -> Any:
        raise NotImplementedError

    def completar_con_imagen(self, prompt: str, imagen_png: bytes, esquema: Optional[dict] = None) -> Any:
        """Reconocimiento óptico de documentos escaneados (sesión 2026-09-17,
        `app.extraccion.ocr`): misma salida estructurada que `completar`, con
        una imagen de página delante del texto. Una implementación sin visión
        (un modelo autoalojado solo de texto) no la sobrescribe, y la etapa de
        reconocimiento se desactiva sola."""
        raise NotImplementedError(f"{type(self).__name__} no admite imágenes")

    @property
    def uso_ultima_llamada(self) -> Optional[tuple[int, int]]:
        """(tokens de entrada, tokens de salida) de la última llamada real, si
        la implementación lo sabe. Para medir el coste del reconocimiento."""
        return None


class NullModelProvider(ModelProvider):
    """Implementación local: no llama a ninguna API. Sustituir por una
    implementación real cuando la cascada de extracción lo necesite."""

    def completar(self, prompt: str, esquema: Optional[dict] = None) -> Any:
        raise NotImplementedError(
            "NullModelProvider no llama a ningún modelo. Configura una implementación real."
        )


class APIModelProvider(ModelProvider):
    """Implementación real de `ModelProvider` sobre la API comercial del
    proveedor de modelo configurado (CONTEXTO.md sección 6: la única etapa
    de la cascada que puede llamar al modelo es el mapeo de cabecera, y una
    vez por firma). Salida estructurada obligatoria vía
    `output_config.format` de tipo `json_schema`: la respuesta siempre es
    JSON válido contra `esquema`, nunca texto libre que haya que parsear a
    ojo. La clave de API se resuelve por variable de entorno
    (`MODEL_API_KEY`, vía el SDK del proveedor) — nunca hardcodeada.

    `workspace_id` es un detalle de autenticación de esta implementación
    concreta, no de la interfaz `ModelProvider`: una clave de API "ligada a
    identidad" (creada en la consola bajo un usuario, no una clave clásica de
    workspace) exige una cabecera propia del proveedor en cada petición —
    si falta, la API devuelve 400. Una clave clásica de workspace no la
    necesita. No pertenece a `ModelProvider.completar` ni a ninguna
    implementación futura sobre un modelo autoalojado: esa cabecera es
    exclusiva de la API de este proveedor concreto, parte de su contrato de
    red y no se puede renombrar sin romper la llamada real."""

    _CABECERA_WORKSPACE = "anthropic-workspace-id"

    def __init__(
        self,
        api_key: Optional[str] = None,
        modelo: Optional[str] = None,
        max_tokens: int = 2048,
        workspace_id: Optional[str] = None,
    ):
        import anthropic  # import perezoso: no forzar la dependencia en NullModelProvider ni en tests que no llaman al modelo

        if not modelo:
            raise ValueError("APIModelProvider requiere un identificador de modelo (variable de entorno MODEL_ID).")
        kwargs: dict = {}
        if api_key:
            kwargs["api_key"] = api_key
        if workspace_id:
            kwargs["default_headers"] = {self._CABECERA_WORKSPACE: workspace_id}
        self._client = anthropic.Anthropic(**kwargs)
        self._modelo = modelo
        self._max_tokens = max_tokens
        # Por hilo: el reconocimiento óptico lee varias páginas a la vez.
        self._local = threading.local()

    @property
    def uso_ultima_llamada(self) -> Optional[tuple[int, int]]:
        return getattr(self._local, "uso", None)

    def completar_con_imagen(self, prompt: str, imagen_png: bytes, esquema: Optional[dict] = None) -> Any:
        import base64

        kwargs: dict = {}
        if esquema is not None:
            kwargs["output_config"] = {"format": {"type": "json_schema", "schema": esquema}}
        # Una página densa transcrita ocupa ~1.750 tokens (piloto de la sesión
        # 2026-09-17); margen amplio para cuadros de 40-50 filas.
        respuesta = self._client.messages.create(
            model=self._modelo,
            max_tokens=max(self._max_tokens, 16000),
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {
                        "type": "base64", "media_type": "image/png",
                        "data": base64.b64encode(imagen_png).decode("ascii"),
                    }},
                    {"type": "text", "text": prompt},
                ],
            }],
            **kwargs,
        )
        self._local.uso = (respuesta.usage.input_tokens, respuesta.usage.output_tokens)
        logger.info(
            "APIModelProvider.completar_con_imagen: %s tokens de entrada, %s de salida (modelo %s, stop %s)",
            respuesta.usage.input_tokens, respuesta.usage.output_tokens, self._modelo, respuesta.stop_reason,
        )
        if respuesta.stop_reason == "max_tokens":
            raise RespuestaTruncada("la transcripción de la página no cabe en max_tokens")
        texto = next(bloque.text for bloque in respuesta.content if bloque.type == "text")
        return json.loads(texto)

    def completar(self, prompt: str, esquema: Optional[dict] = None) -> Any:
        kwargs: dict = {}
        if esquema is not None:
            kwargs["output_config"] = {"format": {"type": "json_schema", "schema": esquema}}
        logger.info(
            "APIModelProvider.completar: llamada real a %s, prompt (%d caracteres):\n%s",
            self._modelo, len(prompt), prompt,
        )
        respuesta = self._client.messages.create(
            model=self._modelo,
            max_tokens=self._max_tokens,
            messages=[{"role": "user", "content": prompt}],
            **kwargs,
        )
        # CONTEXTO.md sección 6: la única llamada al modelo que hace la
        # cascada es cara de dimensionar sin este dato — se registra en
        # cada llamada real (nunca en un acierto de CachedModelProvider).
        logger.info(
            "APIModelProvider.completar: %s tokens de entrada, %s de salida (modelo %s)",
            respuesta.usage.input_tokens, respuesta.usage.output_tokens, self._modelo,
        )
        texto = next(bloque.text for bloque in respuesta.content if bloque.type == "text")
        return json.loads(texto)


class CachedModelProvider(ModelProvider):
    """Decorador de desarrollo: cachea en disco la respuesta de cada llamada
    a `completar` por hash de (prompt, esquema), para no gastar créditos
    reprocesando los mismos fixtures mientras se itera. No sustituye a la
    caché persistente de firma de cabecera (CONTEXTO.md sección 6, tabla
    `cache_mapeo_cabecera`) — esa vive en base de datos y es la que hace que
    el sistema llame menos al modelo cuantos más expedientes procesa; esta
    solo evita llamadas de red repetidas durante el desarrollo local."""

    def __init__(self, interior: ModelProvider, directorio_cache: str | Path):
        self._interior = interior
        self._directorio = Path(directorio_cache)
        self._directorio.mkdir(parents=True, exist_ok=True)

    def _ruta_cache(self, prompt: str, esquema: Optional[dict]) -> Path:
        base = prompt + "\n---\n" + json.dumps(esquema, sort_keys=True, ensure_ascii=False) if esquema else prompt
        clave = hashlib.sha256(base.encode("utf-8")).hexdigest()
        return self._directorio / f"{clave}.json"

    @property
    def uso_ultima_llamada(self) -> Optional[tuple[int, int]]:
        return self._interior.uso_ultima_llamada

    def completar_con_imagen(self, prompt: str, imagen_png: bytes, esquema: Optional[dict] = None) -> Any:
        # Sin caché de disco: el texto reconocido ya se cachea por hash de
        # documento en base de datos (`cache_ocr_documento`).
        return self._interior.completar_con_imagen(prompt, imagen_png, esquema)

    def completar(self, prompt: str, esquema: Optional[dict] = None) -> Any:
        ruta = self._ruta_cache(prompt, esquema)
        if ruta.exists():
            return json.loads(ruta.read_text(encoding="utf-8"))
        resultado = self._interior.completar(prompt, esquema)
        ruta.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
        return resultado
