"""Gestión de usuarios por consola (sesión 2026-10-14). No hay administración
desde la web: quien administra la máquina crea, desactiva y reinicia aquí.

    docker compose exec api python -m app.usuarios crear <usuario>
    docker compose exec api python -m app.usuarios reiniciar <usuario>
    docker compose exec api python -m app.usuarios desactivar <usuario>
    docker compose exec api python -m app.usuarios activar <usuario>
    docker compose exec api python -m app.usuarios listar
    docker compose exec api python -m app.usuarios accesos [--usuario X] [--limite 50]

`crear` y `reiniciar` imprimen una contraseña temporal generada al azar, que
se entrega a la persona por un canal aparte; la primera vez que entre, la web
le obliga a cambiarla. Ninguna contraseña se pasa por la línea de órdenes (se
quedaría en el historial de la consola)."""
import argparse
import sys

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import ahora, cerrar_sesiones_de_usuario, cifrar_contrasena, generar_contrasena_temporal


class ErrorUsuarios(Exception):
    pass


def _buscar(db: Session, nombre: str):
    from app.models import Usuario

    usuario = db.scalar(select(Usuario).where(Usuario.nombre == nombre))
    if usuario is None:
        raise ErrorUsuarios(f"No existe el usuario «{nombre}».")
    return usuario


def crear(db: Session, nombre: str) -> str:
    from app.models import Usuario

    nombre = nombre.strip()
    if not nombre or len(nombre) > 64 or any(c.isspace() for c in nombre):
        raise ErrorUsuarios("El nombre de usuario no puede estar vacío, tener espacios ni pasar de 64 caracteres.")
    if db.scalar(select(Usuario).where(Usuario.nombre == nombre)) is not None:
        raise ErrorUsuarios(f"Ya existe el usuario «{nombre}». Para darle otra contraseña, usa «reiniciar».")
    temporal = generar_contrasena_temporal()
    db.add(Usuario(nombre=nombre, hash_contrasena=cifrar_contrasena(temporal), activo=True, debe_cambiar_contrasena=True))
    db.commit()
    return temporal


def reiniciar(db: Session, nombre: str) -> str:
    usuario = _buscar(db, nombre)
    temporal = generar_contrasena_temporal()
    usuario.hash_contrasena = cifrar_contrasena(temporal)
    usuario.debe_cambiar_contrasena = True
    usuario.activo = True
    usuario.contrasena_cambiada_en = ahora()
    cerrar_sesiones_de_usuario(db, usuario.id)
    db.commit()
    return temporal


def cambiar_activo(db: Session, nombre: str, activo: bool) -> None:
    usuario = _buscar(db, nombre)
    usuario.activo = activo
    if not activo:
        cerrar_sesiones_de_usuario(db, usuario.id)
    db.commit()


def listar(db: Session) -> list[dict]:
    from app.models import RegistroAcceso, Usuario

    filas = []
    for usuario in db.scalars(select(Usuario).order_by(Usuario.nombre)):
        ultima = db.scalar(
            select(RegistroAcceso.momento)
            .where(RegistroAcceso.usuario_id == usuario.id, RegistroAcceso.resultado == "entrada")
            .order_by(RegistroAcceso.momento.desc()).limit(1)
        )
        filas.append({
            "usuario": usuario.nombre,
            "activo": usuario.activo,
            "debe_cambiar_contrasena": usuario.debe_cambiar_contrasena,
            "ultima_entrada": ultima,
        })
    return filas


def accesos(db: Session, nombre: str | None = None, limite: int = 50) -> list:
    from app.models import RegistroAcceso

    consulta = select(RegistroAcceso).order_by(RegistroAcceso.momento.desc()).limit(limite)
    if nombre:
        consulta = consulta.where(RegistroAcceso.usuario_nombre == nombre)
    return list(db.scalars(consulta))


def _fecha(momento) -> str:
    return momento.strftime("%Y-%m-%d %H:%M:%S UTC") if momento else "-"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.usuarios", description="Usuarios de la plataforma.")
    ordenes = parser.add_subparsers(dest="orden", required=True)
    for orden, ayuda in (
        ("crear", "alta con contraseña temporal"),
        ("reiniciar", "contraseña temporal nueva; obliga a cambiarla y cierra sus sesiones"),
        ("desactivar", "impide la entrada y cierra sus sesiones"),
        ("activar", "vuelve a permitir la entrada"),
    ):
        sub = ordenes.add_parser(orden, help=ayuda)
        sub.add_argument("usuario")
    ordenes.add_parser("listar", help="usuarios y su última entrada")
    sub = ordenes.add_parser("accesos", help="registro de entradas, salidas e intentos fallidos")
    sub.add_argument("--usuario")
    sub.add_argument("--limite", type=int, default=50)
    args = parser.parse_args(argv)

    from app.db import SessionLocal

    db = SessionLocal()
    try:
        if args.orden in ("crear", "reiniciar"):
            temporal = (crear if args.orden == "crear" else reiniciar)(db, args.usuario)
            print(f"Usuario «{args.usuario.strip()}». Contraseña temporal: {temporal}")
            print("Entrégala por un canal aparte. Se pedirá cambiarla en la primera entrada.")
        elif args.orden in ("desactivar", "activar"):
            cambiar_activo(db, args.usuario, args.orden == "activar")
            print(f"Usuario «{args.usuario}» {'activado' if args.orden == 'activar' else 'desactivado'}.")
        elif args.orden == "listar":
            filas = listar(db)
            if not filas:
                print("No hay usuarios. Crea el primero con: python -m app.usuarios crear <usuario>")
            for fila in filas:
                estado = "activo" if fila["activo"] else "DESACTIVADO"
                cambio = "  (contraseña temporal pendiente de cambiar)" if fila["debe_cambiar_contrasena"] else ""
                print(f"{fila['usuario']:<24} {estado:<12} última entrada: {_fecha(fila['ultima_entrada'])}{cambio}")
        else:
            for acceso in accesos(db, args.usuario, args.limite):
                print(f"{_fecha(acceso.momento)}  {acceso.resultado:<18} {acceso.usuario_nombre:<24} {acceso.ip or '-'}")
    except ErrorUsuarios as error:
        print(error, file=sys.stderr)
        return 1
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
