"""Entrada, salida y cambio de contraseña (sesión 2026-10-14, `app.auth`).

Las únicas rutas sin `get_current_user` delante, junto a `/health`: entrar
no puede exigir haber entrado, y cambiar la contraseña obligatoria tiene que
poder hacerse antes de llegar a ningún dato."""
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import (
    AccesoBloqueado,
    ContrasenaNoValida,
    CredencialesIncorrectas,
    Usuario,
    abrir_sesion,
    ahora,
    cerrar_sesion,
    cerrar_sesiones_de_usuario,
    cifrar_contrasena,
    get_usuario_en_sesion,
    ip_de,
    registrar_acceso,
    validar_contrasena_nueva,
    verificar_contrasena,
    autenticar,
)
from app.config import settings
from app.db import get_db

router = APIRouter(prefix="/auth")


class Credenciales(BaseModel):
    usuario: str
    contrasena: str


class CambioContrasena(BaseModel):
    actual: str
    nueva: str


def _sesion_respuesta(usuario: Usuario) -> dict:
    return {"usuario": usuario.nombre, "debe_cambiar_contrasena": usuario.debe_cambiar_contrasena}


def _poner_cookie(respuesta: Response, token: str) -> None:
    respuesta.set_cookie(
        settings.sesion_cookie_nombre, token,
        httponly=True, secure=settings.sesion_cookie_segura, samesite="lax", path="/",
        # Sin `max_age`: cookie de sesión del navegador. La caducidad real la
        # decide la API (inactividad y duración máxima), no el navegador.
    )


def _borrar_cookie(respuesta: Response) -> None:
    respuesta.delete_cookie(
        settings.sesion_cookie_nombre, path="/", httponly=True,
        secure=settings.sesion_cookie_segura, samesite="lax",
    )


@router.post("/entrar")
def entrar(datos: Credenciales, request: Request, response: Response, db: Session = Depends(get_db)):
    ip = ip_de(request)
    try:
        usuario = autenticar(db, datos.usuario, datos.contrasena, ip, request.headers.get("user-agent"))
    except AccesoBloqueado:
        raise HTTPException(
            status_code=429,
            detail=f"Demasiados intentos fallidos. Vuelve a probar dentro de {settings.acceso_ventana_minutos} minutos.",
        )
    except CredencialesIncorrectas:
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos.")
    token = abrir_sesion(db, usuario.id, ip)
    _poner_cookie(response, token)
    return {"usuario": usuario.nombre, "debe_cambiar_contrasena": usuario.debe_cambiar_contrasena}


@router.get("/sesion")
def sesion(usuario: Usuario = Depends(get_usuario_en_sesion)):
    return _sesion_respuesta(usuario)


@router.post("/salir")
def salir(request: Request, response: Response, db: Session = Depends(get_db)):
    """No exige sesión válida: salir con una ya caducada solo borra la cookie."""
    token = request.cookies.get(settings.sesion_cookie_nombre)
    usuario = None
    if token:
        try:
            usuario = get_usuario_en_sesion(request, db)
        except HTTPException:
            usuario = None
        cerrar_sesion(db, token)
        if usuario is not None:
            registrar_acceso(db, usuario.nombre, "salida", ip_de(request), request.headers.get("user-agent"), usuario.id)
        db.commit()
    _borrar_cookie(response)
    return {"ok": True}


@router.post("/cambiar-contrasena")
def cambiar_contrasena(
    datos: CambioContrasena,
    request: Request,
    usuario: Usuario = Depends(get_usuario_en_sesion),
    db: Session = Depends(get_db),
):
    from app.models import Usuario as UsuarioModelo

    fila = db.get(UsuarioModelo, usuario.id)
    if not verificar_contrasena(fila.hash_contrasena, datos.actual):
        registrar_acceso(db, fila.nombre, "fallo", ip_de(request), request.headers.get("user-agent"), fila.id)
        db.commit()
        raise HTTPException(status_code=400, detail="La contraseña actual no es correcta.")
    if datos.nueva == datos.actual:
        raise HTTPException(status_code=400, detail="La contraseña nueva tiene que ser distinta de la actual.")
    try:
        validar_contrasena_nueva(datos.nueva, fila.nombre)
    except ContrasenaNoValida as error:
        raise HTTPException(status_code=400, detail=str(error))
    fila.hash_contrasena = cifrar_contrasena(datos.nueva)
    fila.debe_cambiar_contrasena = False
    fila.contrasena_cambiada_en = ahora()
    # Las demás sesiones del usuario se cierran: si cambia la contraseña porque
    # alguien la conocía, ese alguien no debe seguir dentro.
    cerrar_sesiones_de_usuario(db, fila.id, salvo_token=request.cookies.get(settings.sesion_cookie_nombre))
    registrar_acceso(db, fila.nombre, "cambio_contrasena", ip_de(request), request.headers.get("user-agent"), fila.id)
    db.commit()
    return {"usuario": fila.nombre, "debe_cambiar_contrasena": False}
