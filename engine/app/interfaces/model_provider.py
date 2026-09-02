import json
import hashlib
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ModelProvider(ABC):
    """Interfaz de acceso al modelo. CLAUDE.md secciones 6 y 9.2:
    misma firma para la API de Anthropic hoy y un modelo autoalojado mañana."""

    @abstractmethod
    def completar(self, prompt: str, esquema: Optional[dict] = None) -> Any:
        raise NotImplementedError


class NullModelProvider(ModelProvider):
    """Implementación local: no llama a ninguna API. Sustituir por una
    implementación real cuando la cascada de extracción lo necesite."""

    def completar(self, prompt: str, esquema: Optional[dict] = None) -> Any:
        raise NotImplementedError(
            "NullModelProvider no llama a ningún modelo. Configura una implementación real."
        )


class AnthropicModelProvider(ModelProvider):
    """Implementación real de `ModelProvider` sobre la API de Anthropic
    (CLAUDE.md sección 6: la única etapa de la cascada que puede llamar al
    modelo es el mapeo de cabecera, y una vez por firma). Salida estructurada
    obligatoria vía `output_config.format` de tipo `json_schema`: la
    respuesta siempre es JSON válido contra `esquema`, nunca texto libre que
    haya que parsear a ojo. La clave de API se resuelve por variable de
    entorno (`ANTHROPIC_API_KEY`, vía el SDK) — nunca hardcodeada.

    `workspace_id` es un detalle de autenticación de esta implementación
    concreta, no de la interfaz `ModelProvider`: una clave de API "ligada a
    identidad" (creada en la consola bajo un usuario, no una clave clásica de
    workspace) exige la cabecera `anthropic-workspace-id` en cada petición a
    `/v1/messages` — si falta, la API devuelve 400. Una clave clásica de
    workspace no la necesita. No pertenece a `ModelProvider.completar` ni a
    ninguna implementación futura sobre un modelo autoalojado: esa cabecera
    no existe fuera de la API de Anthropic."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        modelo: str = "claude-haiku-4-5",
        max_tokens: int = 2048,
        workspace_id: Optional[str] = None,
    ):
        import anthropic  # import perezoso: no forzar la dependencia en NullModelProvider ni en tests que no llaman al modelo

        kwargs: dict = {}
        if api_key:
            kwargs["api_key"] = api_key
        if workspace_id:
            kwargs["default_headers"] = {"anthropic-workspace-id": workspace_id}
        self._client = anthropic.Anthropic(**kwargs)
        self._modelo = modelo
        self._max_tokens = max_tokens

    def completar(self, prompt: str, esquema: Optional[dict] = None) -> Any:
        kwargs: dict = {}
        if esquema is not None:
            kwargs["output_config"] = {"format": {"type": "json_schema", "schema": esquema}}
        logger.info(
            "AnthropicModelProvider.completar: llamada real a %s, prompt (%d caracteres):\n%s",
            self._modelo, len(prompt), prompt,
        )
        respuesta = self._client.messages.create(
            model=self._modelo,
            max_tokens=self._max_tokens,
            messages=[{"role": "user", "content": prompt}],
            **kwargs,
        )
        # CLAUDE.md sección 6: la única llamada al modelo que hace la
        # cascada es cara de dimensionar sin este dato — se registra en
        # cada llamada real (nunca en un acierto de CachedModelProvider).
        logger.info(
            "AnthropicModelProvider.completar: %s tokens de entrada, %s de salida (modelo %s)",
            respuesta.usage.input_tokens, respuesta.usage.output_tokens, self._modelo,
        )
        texto = next(bloque.text for bloque in respuesta.content if bloque.type == "text")
        return json.loads(texto)


class CachedModelProvider(ModelProvider):
    """Decorador de desarrollo: cachea en disco la respuesta de cada llamada
    a `completar` por hash de (prompt, esquema), para no gastar créditos
    reprocesando los mismos fixtures mientras se itera. No sustituye a la
    caché persistente de firma de cabecera (CLAUDE.md sección 6, tabla
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

    def completar(self, prompt: str, esquema: Optional[dict] = None) -> Any:
        ruta = self._ruta_cache(prompt, esquema)
        if ruta.exists():
            return json.loads(ruta.read_text(encoding="utf-8"))
        resultado = self._interior.completar(prompt, esquema)
        ruta.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
        return resultado
