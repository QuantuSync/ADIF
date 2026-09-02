from dataclasses import dataclass


@dataclass
class Usuario:
    id: int
    nombre: str


def get_current_user() -> Usuario:
    """Costura de autenticación: todas las rutas dependen de esta función.
    Hoy devuelve un usuario ficticio; añadir autenticación real se hace aquí."""
    return Usuario(id=0, nombre="usuario-demo")
