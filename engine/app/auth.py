"""Acceso con usuario y contraseña (sesión 2026-10-14, preparación del
despliegue). Sustituye al usuario ficticio de la costura de autenticación
(CONTEXTO.md sección 9.7): todas las rutas siguen pasando por
`get_current_user`, que ahora exige una sesión válida.

- Contraseñas en argon2id (`argon2-cffi`, parámetros por defecto de la
  librería), nunca en claro.
- Sesión por cookie `HttpOnly` emitida por la API. Una cookie, y no una
  cabecera, porque el Excel y los PDF se descargan por enlace normal del
  navegador, que no lleva cabeceras propias. En la base se guarda el SHA-256
  del token, no el token.
- Caducidad por inactividad del usuario. Las pantallas sondean la API solas
  cada pocos segundos; esas peticiones llevan `CABECERA_SONDEO` y no
  renuevan la sesión, o una pestaña olvidada abierta la mantendría viva para
  siempre.
- Límite de intentos contado sobre `registro_accesos`, por usuario tecleado y
  por dirección de origen.
"""
import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends, HTTPException, Request
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db

CABECERA_SONDEO = "x-sondeo"
# El detalle del 403 que la web reconoce para llevar a la pantalla de cambio.
DETALLE_CAMBIO_OBLIGATORIO = "cambio_contrasena_obligatorio"
# Una sesión no renueva su `ultima_actividad` más de una vez por este margen:
# ahorra una escritura por petición sin cambiar la caducidad de forma visible.
_MARGEN_RENOVACION = timedelta(seconds=30)

_hasher = PasswordHasher()
# Para igualar el tiempo de respuesta cuando el usuario no existe: sin esto,
# una respuesta más rápida delata qué nombres son de verdad.
_HASH_SEÑUELO = _hasher.hash(secrets.token_urlsafe(16))


@dataclass
class Usuario:
    id: int
    nombre: str
    debe_cambiar_contrasena: bool = False


class AccesoBloqueado(Exception):
    pass


class CredencialesIncorrectas(Exception):
    pass


class ContrasenaNoValida(ValueError):
    pass


def ahora() -> datetime:
    return datetime.now(timezone.utc)


def _utc(momento: datetime) -> datetime:
    # SQLite (las pruebas) devuelve fechas sin zona aunque se guarden con ella.
    return momento if momento.tzinfo is not None else momento.replace(tzinfo=timezone.utc)


def cifrar_contrasena(contrasena: str) -> str:
    return _hasher.hash(contrasena)


def verificar_contrasena(hash_guardado: str, contrasena: str) -> bool:
    try:
        return _hasher.verify(hash_guardado, contrasena)
    except (VerificationError, InvalidHashError):
        return False


def validar_contrasena_nueva(contrasena: str, nombre_usuario: str) -> None:
    if len(contrasena) < settings.contrasena_longitud_minima:
        raise ContrasenaNoValida(
            f"La contraseña tiene que tener al menos {settings.contrasena_longitud_minima} caracteres."
        )
    if contrasena.strip().lower() == nombre_usuario.strip().lower():
        raise ContrasenaNoValida("La contraseña no puede ser el nombre de usuario.")


def generar_contrasena_temporal() -> str:
    return secrets.token_urlsafe(12)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def registrar_acceso(
    db: Session, nombre: str, resultado: str, ip: Optional[str], agente: Optional[str] = None,
    usuario_id: Optional[int] = None,
) -> None:
    from app.models import RegistroAcceso

    db.add(RegistroAcceso(
        momento=ahora(), usuario_nombre=nombre[:128], usuario_id=usuario_id, resultado=resultado,
        ip=ip, agente=(agente or "")[:255] or None,
    ))


def comprobar_limite_intentos(db: Session, nombre: str, ip: Optional[str]) -> None:
    """Lanza `AccesoBloqueado` si el usuario tecleado o la dirección de origen
    acumulan demasiados fallos en la ventana. Se comprueba ANTES de mirar la
    contraseña: durante el bloqueo ni siquiera la correcta deja entrar, así
    que probar contraseñas no da información."""
    from app.models import RegistroAcceso

    desde = ahora() - timedelta(minutes=settings.acceso_ventana_minutos)
    fallos = select(func.count()).select_from(RegistroAcceso).where(
        RegistroAcceso.resultado == "fallo", RegistroAcceso.momento >= desde,
    )
    if db.scalar(fallos.where(RegistroAcceso.usuario_nombre == nombre)) >= settings.acceso_max_fallos_usuario:
        raise AccesoBloqueado()
    if ip and db.scalar(fallos.where(RegistroAcceso.ip == ip)) >= settings.acceso_max_fallos_ip:
        raise AccesoBloqueado()


def autenticar(db: Session, nombre: str, contrasena: str, ip: Optional[str], agente: Optional[str]):
    """Devuelve el `models.Usuario` si las credenciales valen y no hay bloqueo.
    Deja escrito el intento en `registro_accesos` en cualquier caso."""
    from app.models import Usuario as UsuarioModelo

    nombre = nombre.strip()
    try:
        comprobar_limite_intentos(db, nombre, ip)
    except AccesoBloqueado:
        registrar_acceso(db, nombre, "bloqueado", ip, agente)
        db.commit()
        raise
    usuario = db.scalar(select(UsuarioModelo).where(UsuarioModelo.nombre == nombre))
    valida = verificar_contrasena(usuario.hash_contrasena if usuario else _HASH_SEÑUELO, contrasena)
    if usuario is None or not usuario.activo or not valida:
        registrar_acceso(db, nombre, "fallo", ip, agente, usuario.id if usuario else None)
        db.commit()
        raise CredencialesIncorrectas()
    if _hasher.check_needs_rehash(usuario.hash_contrasena):
        usuario.hash_contrasena = cifrar_contrasena(contrasena)
    registrar_acceso(db, nombre, "entrada", ip, agente, usuario.id)
    return usuario


def abrir_sesion(db: Session, usuario_id: int, ip: Optional[str]) -> str:
    """Crea la sesión y devuelve el token en claro (solo viaja en la cookie)."""
    from app.models import SesionUsuario

    token = secrets.token_urlsafe(32)
    momento = ahora()
    db.add(SesionUsuario(
        hash_token=_hash_token(token), usuario_id=usuario_id, creada_en=momento, ultima_actividad=momento,
        caduca_en=momento + timedelta(hours=settings.sesion_duracion_maxima_horas), ip=ip,
    ))
    # De paso, se barren las caducadas de todo el mundo: con 6 personas no
    # merece un proceso aparte.
    _borrar_sesiones_caducadas(db, momento)
    db.commit()
    return token


def _borrar_sesiones_caducadas(db: Session, momento: datetime) -> None:
    from app.models import SesionUsuario

    limite_inactividad = momento - timedelta(minutes=settings.sesion_inactividad_minutos)
    db.execute(delete(SesionUsuario).where(
        (SesionUsuario.caduca_en < momento) | (SesionUsuario.ultima_actividad < limite_inactividad)
    ))


def cerrar_sesion(db: Session, token: Optional[str]) -> None:
    from app.models import SesionUsuario

    if token:
        db.execute(delete(SesionUsuario).where(SesionUsuario.hash_token == _hash_token(token)))


def cerrar_sesiones_de_usuario(db: Session, usuario_id: int, salvo_token: Optional[str] = None) -> None:
    from app.models import SesionUsuario

    consulta = delete(SesionUsuario).where(SesionUsuario.usuario_id == usuario_id)
    if salvo_token:
        consulta = consulta.where(SesionUsuario.hash_token != _hash_token(salvo_token))
    db.execute(consulta)


def ip_de(request: Request) -> Optional[str]:
    # Detrás del servidor de entrada, uvicorn ya pone aquí la dirección real
    # (`--proxy-headers`, ver docker-compose.prod.yml).
    return request.client.host if request.client else None


def _sesion_de_la_peticion(request: Request, db: Session):
    from app.models import SesionUsuario, Usuario as UsuarioModelo

    token = request.cookies.get(settings.sesion_cookie_nombre)
    if not token:
        raise HTTPException(status_code=401, detail="Sesión no iniciada.")
    sesion = db.scalar(select(SesionUsuario).where(SesionUsuario.hash_token == _hash_token(token)))
    momento = ahora()
    if sesion is not None and (
        _utc(sesion.caduca_en) <= momento
        or _utc(sesion.ultima_actividad) + timedelta(minutes=settings.sesion_inactividad_minutos) <= momento
    ):
        db.delete(sesion)
        db.commit()
        sesion = None
    if sesion is None:
        raise HTTPException(status_code=401, detail="La sesión ha caducado. Vuelve a entrar.")
    usuario = db.get(UsuarioModelo, sesion.usuario_id)
    if usuario is None or not usuario.activo:
        db.delete(sesion)
        db.commit()
        raise HTTPException(status_code=401, detail="Sesión no válida.")
    if request.headers.get(CABECERA_SONDEO) != "1" and momento - _utc(sesion.ultima_actividad) >= _MARGEN_RENOVACION:
        sesion.ultima_actividad = momento
        db.commit()
    return sesion, usuario


def get_usuario_en_sesion(request: Request, db: Session = Depends(get_db)) -> Usuario:
    """Sesión válida, aunque tenga pendiente el cambio de contraseña. Solo para
    las rutas de `/auth` (consultar la sesión, cambiar la contraseña, salir)."""
    _sesion, usuario = _sesion_de_la_peticion(request, db)
    return Usuario(id=usuario.id, nombre=usuario.nombre, debe_cambiar_contrasena=usuario.debe_cambiar_contrasena)


def get_current_user(usuario: Usuario = Depends(get_usuario_en_sesion)) -> Usuario:
    """Costura de autenticación (CONTEXTO.md sección 9.7): todas las rutas con
    datos dependen de esta función (`app.main` la pone en cada router). Sin
    sesión válida, 401; con la contraseña inicial sin cambiar, 403."""
    if usuario.debe_cambiar_contrasena:
        raise HTTPException(status_code=403, detail=DETALLE_CAMBIO_OBLIGATORIO)
    return usuario
