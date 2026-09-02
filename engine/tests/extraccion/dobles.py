"""Test doubles para `ModelProvider`, usados solo en tests: nunca hay
llamada de red real. Con las cabeceras reales de los dos anejos de fixture,
el mapeo determinista ya resuelve todo (ver test_mapeo_cabecera.py y
test_pipeline_anejo.py) — estos dobles sirven para ejercitar el camino "cae
al modelo" de `mapear_cabecera` con una cabecera sintética que el mapeo
determinista no puede resolver."""
from __future__ import annotations

from typing import Any, Optional

from app.interfaces.model_provider import ModelProvider


class ProveedorModeloFalso(ModelProvider):
    def __init__(self, respuesta: dict):
        self._respuesta = respuesta
        self.llamadas = 0
        self.prompts: list[str] = []

    def completar(self, prompt: str, esquema: Optional[dict] = None) -> Any:
        self.llamadas += 1
        self.prompts.append(prompt)
        return dict(self._respuesta)


class ProveedorModeloContador(ModelProvider):
    """Envuelve otro `ModelProvider` y cuenta cuántas veces se le llama de
    verdad — para probar `CachedModelProvider` sin tocar la red."""

    def __init__(self, interior: ModelProvider):
        self._interior = interior
        self.llamadas = 0

    def completar(self, prompt: str, esquema: Optional[dict] = None) -> Any:
        self.llamadas += 1
        return self._interior.completar(prompt, esquema)
