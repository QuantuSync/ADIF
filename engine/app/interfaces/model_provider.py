from abc import ABC, abstractmethod
from typing import Any, Optional


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
