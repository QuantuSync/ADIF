"""Acceso con usuario y contraseña (sesión 2026-10-14, `app.auth`).

La prueba central es la primera: recorre TODAS las rutas de la API y exige
401 sin sesión, para que una ruta nueva no pueda quedar abierta por olvido.
El resto prueba el ciclo completo: alta por consola, primera entrada con
cambio obligatorio, caducidad por inactividad, límite de intentos y registro."""
from datetime import timedelta

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models, usuarios
from app.auth import ahora
from app.config import settings
from app.db import Base, get_db
from app.main import app
from tests.conftest import _TABLAS

pytestmark = pytest.mark.acceso_real

# Lo único que se sirve sin sesión: la comprobación de salud (sin datos) y
# entrar/salir. `/auth/sesion` y `/auth/cambiar-contrasena` exigen sesión
# aunque admitan la contraseña temporal sin cambiar.
_ABIERTAS = {("GET", "/health"), ("POST", "/auth/entrar"), ("POST", "/auth/salir")}


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(
        engine,
        tables=_TABLAS + [models.Usuario.__table__, models.SesionUsuario.__table__, models.RegistroAcceso.__table__],
    )
    sesion = sessionmaker(bind=engine)()
    try:
        yield sesion
    finally:
        sesion.close()


@pytest.fixture()
def cliente(db_session):
    def _get_db_prueba():
        yield db_session

    app.dependency_overrides[get_db] = _get_db_prueba
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _rutas():
    for ruta in app.routes:
        if not isinstance(ruta, APIRoute):
            continue
        ruta_concreta = ruta.path
        for parametro in ruta.param_convertors:
            ruta_concreta = ruta_concreta.replace("{" + parametro + "}", "1")
        for metodo in sorted(ruta.methods):
            yield metodo, ruta.path, ruta_concreta


def test_ninguna_ruta_con_datos_responde_sin_sesion(cliente):
    rutas = list(_rutas())
    assert len(rutas) > 50  # todas las de la API, no un puñado
    assert any("exportar" in plantilla or "excel" in plantilla for _m, plantilla, _c in rutas)
    abiertas = []
    for metodo, plantilla, concreta in rutas:
        if (metodo, plantilla) in _ABIERTAS:
            continue
        respuesta = cliente.request(metodo, concreta)
        if respuesta.status_code != 401:
            abiertas.append((metodo, plantilla, respuesta.status_code))
    assert abiertas == []


def test_una_cookie_inventada_no_abre_nada(cliente):
    cliente.cookies.set(settings.sesion_cookie_nombre, "inventada")
    assert cliente.get("/catalogo").status_code == 401
    assert cliente.get("/expedientes").status_code == 401


def test_la_documentacion_de_la_api_esta_apagada(cliente):
    assert cliente.get("/openapi.json").status_code == 404
    assert cliente.get("/docs").status_code == 404


def test_la_contrasena_se_guarda_cifrada_con_argon2id(db_session):
    temporal = usuarios.crear(db_session, "ana")
    usuario = db_session.scalar(select(models.Usuario).where(models.Usuario.nombre == "ana"))
    assert usuario.hash_contrasena.startswith("$argon2id$")
    assert temporal not in usuario.hash_contrasena


def _entrar(cliente, nombre, contrasena):
    return cliente.post("/auth/entrar", json={"usuario": nombre, "contrasena": contrasena})


def test_primera_entrada_obliga_a_cambiar_la_contrasena_antes_de_ver_datos(cliente, db_session):
    temporal = usuarios.crear(db_session, "ana")

    respuesta = _entrar(cliente, "ana", temporal)
    assert respuesta.status_code == 200
    assert respuesta.json()["debe_cambiar_contrasena"] is True
    cookie = respuesta.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie

    bloqueada = cliente.get("/catalogo")
    assert bloqueada.status_code == 403
    assert bloqueada.json()["detail"] == "cambio_contrasena_obligatorio"
    assert cliente.get("/auth/sesion").json() == {"usuario": "ana", "debe_cambiar_contrasena": True}

    corta = cliente.post("/auth/cambiar-contrasena", json={"actual": temporal, "nueva": "corta"})
    assert corta.status_code == 400
    mal = cliente.post("/auth/cambiar-contrasena", json={"actual": "no-es-esta", "nueva": "una contraseña larga"})
    assert mal.status_code == 400
    bien = cliente.post("/auth/cambiar-contrasena", json={"actual": temporal, "nueva": "una contraseña larga"})
    assert bien.status_code == 200

    assert cliente.get("/catalogo").status_code == 200
    assert _entrar(TestClient(app), "ana", temporal).status_code == 401
    assert _entrar(TestClient(app), "ana", "una contraseña larga").json()["debe_cambiar_contrasena"] is False


def _usuario_listo(db_session, nombre="ana", contrasena="una contraseña larga"):
    temporal = usuarios.crear(db_session, nombre)
    usuario = db_session.scalar(select(models.Usuario).where(models.Usuario.nombre == nombre))
    from app.auth import cifrar_contrasena

    usuario.hash_contrasena = cifrar_contrasena(contrasena)
    usuario.debe_cambiar_contrasena = False
    db_session.commit()
    return temporal


def test_la_sesion_caduca_por_inactividad_y_el_sondeo_no_la_renueva(cliente, db_session):
    _usuario_listo(db_session)
    assert _entrar(cliente, "ana", "una contraseña larga").status_code == 200
    sesion = db_session.scalar(select(models.SesionUsuario))

    hace_diez = ahora() - timedelta(minutes=10)
    sesion.ultima_actividad = hace_diez
    db_session.commit()
    assert cliente.get("/catalogo", headers={"X-Sondeo": "1"}).status_code == 200
    db_session.refresh(sesion)
    assert sesion.ultima_actividad.replace(tzinfo=None) == hace_diez.replace(tzinfo=None)

    assert cliente.get("/catalogo").status_code == 200
    db_session.refresh(sesion)
    assert sesion.ultima_actividad.replace(tzinfo=None) > hace_diez.replace(tzinfo=None)

    sesion.ultima_actividad = ahora() - timedelta(minutes=settings.sesion_inactividad_minutos + 1)
    db_session.commit()
    assert cliente.get("/catalogo").status_code == 401
    assert db_session.scalar(select(models.SesionUsuario)) is None


def test_la_sesion_caduca_a_la_duracion_maxima_aunque_haya_actividad(cliente, db_session):
    _usuario_listo(db_session)
    _entrar(cliente, "ana", "una contraseña larga")
    sesion = db_session.scalar(select(models.SesionUsuario))
    sesion.caduca_en = ahora() - timedelta(seconds=1)
    db_session.commit()
    assert cliente.get("/catalogo").status_code == 401


def test_limite_de_intentos_bloquea_incluso_con_la_contrasena_correcta(cliente, db_session):
    _usuario_listo(db_session)
    for _ in range(settings.acceso_max_fallos_usuario):
        assert _entrar(cliente, "ana", "mala").status_code == 401
    bloqueado = _entrar(cliente, "ana", "una contraseña larga")
    assert bloqueado.status_code == 429
    resultados = [r.resultado for r in db_session.scalars(select(models.RegistroAcceso).order_by(models.RegistroAcceso.id))]
    assert resultados == ["fallo"] * settings.acceso_max_fallos_usuario + ["bloqueado"]

    # Pasada la ventana, los fallos dejan de contar.
    for registro in db_session.scalars(select(models.RegistroAcceso)):
        registro.momento = ahora() - timedelta(minutes=settings.acceso_ventana_minutos + 1)
    db_session.commit()
    assert _entrar(cliente, "ana", "una contraseña larga").status_code == 200


def test_limite_de_intentos_por_direccion_aunque_cambie_el_usuario(cliente, db_session, monkeypatch):
    monkeypatch.setattr(settings, "acceso_max_fallos_ip", 3)
    _usuario_listo(db_session)
    for nombre in ("x1", "x2", "x3"):
        assert _entrar(cliente, nombre, "mala").status_code == 401
    assert _entrar(cliente, "ana", "una contraseña larga").status_code == 429


def test_usuario_inexistente_y_contrasena_mala_responden_igual(cliente, db_session):
    _usuario_listo(db_session)
    a = _entrar(cliente, "nadie", "mala")
    b = _entrar(cliente, "ana", "mala")
    assert (a.status_code, a.json()) == (b.status_code, b.json())


def test_registro_de_accesos_con_quien_y_cuando(cliente, db_session):
    _usuario_listo(db_session)
    _entrar(cliente, "ana", "mala")
    _entrar(cliente, "ana", "una contraseña larga")
    cliente.post("/auth/salir")
    registros = list(db_session.scalars(select(models.RegistroAcceso).order_by(models.RegistroAcceso.id)))
    assert [(r.usuario_nombre, r.resultado) for r in registros] == [("ana", "fallo"), ("ana", "entrada"), ("ana", "salida")]
    assert all(r.momento is not None and r.ip for r in registros)
    assert cliente.get("/catalogo").status_code == 401


def test_desactivar_cierra_las_sesiones_y_impide_entrar(cliente, db_session):
    _usuario_listo(db_session)
    _entrar(cliente, "ana", "una contraseña larga")
    assert cliente.get("/catalogo").status_code == 200
    usuarios.cambiar_activo(db_session, "ana", False)
    assert cliente.get("/catalogo").status_code == 401
    assert _entrar(cliente, "ana", "una contraseña larga").status_code == 401
    usuarios.cambiar_activo(db_session, "ana", True)
    assert _entrar(cliente, "ana", "una contraseña larga").status_code == 200


def test_reiniciar_da_temporal_nueva_y_vuelve_a_obligar_al_cambio(cliente, db_session):
    _usuario_listo(db_session)
    _entrar(cliente, "ana", "una contraseña larga")
    temporal = usuarios.reiniciar(db_session, "ana")
    assert cliente.get("/catalogo").status_code == 401  # sus sesiones se cierran
    assert _entrar(cliente, "ana", "una contraseña larga").status_code == 401
    assert _entrar(cliente, "ana", temporal).json()["debe_cambiar_contrasena"] is True


def test_la_consola_no_crea_duplicados_ni_nombres_con_espacios(db_session):
    usuarios.crear(db_session, "ana")
    with pytest.raises(usuarios.ErrorUsuarios):
        usuarios.crear(db_session, "ana")
    with pytest.raises(usuarios.ErrorUsuarios):
        usuarios.crear(db_session, "ana maría")
    with pytest.raises(usuarios.ErrorUsuarios):
        usuarios.reiniciar(db_session, "nadie")
