from abc import ABC, abstractmethod
from pathlib import Path


class DocumentStorage(ABC):
    """Interfaz de almacenamiento de documentos. CONTEXTO.md sección 9.3:
    hoy disco local, mañana almacenamiento de objetos."""

    @abstractmethod
    def guardar(self, nombre: str, contenido: bytes) -> str:
        raise NotImplementedError

    @abstractmethod
    def recuperar(self, ruta: str) -> bytes:
        raise NotImplementedError

    @abstractmethod
    def listar(self, prefijo: str = "") -> list[str]:
        raise NotImplementedError


class LocalDiskStorage(DocumentStorage):
    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def guardar(self, nombre: str, contenido: bytes) -> str:
        destino = self.base_path / nombre
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(contenido)
        return str(destino.relative_to(self.base_path))

    def recuperar(self, ruta: str) -> bytes:
        return (self.base_path / ruta).read_bytes()

    def listar(self, prefijo: str = "") -> list[str]:
        return [
            str(p.relative_to(self.base_path))
            for p in self.base_path.rglob(f"{prefijo}*")
            if p.is_file()
        ]
