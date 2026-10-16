"""Acceso con usuario y contraseña (sesión 2026-10-14, `app.auth`).

La prueba central es la primera: recorre TODAS las rutas de la API y exige
401 sin sesión, para que una ruta nueva no pueda quedar abierta por olvido.
El resto prueba el ciclo completo: alta por consola, primera entrada con
cambio obligatorio, caducidad por inactividad, límite de intentos y registro.

Sesión 2026-10-16: dos perfiles. La otra prueba central recorre también
TODAS las rutas y exige que un usuario de consulta no pueda escribir en
ninguna, con la lista sacada de la propia aplicación: una ruta nueva que
escriba queda cubierta sin tocar esta prueba."""
from datetime import timedelta

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models, usuarios
from app.auth import DETALLE_SOLO_CONSULTA, METODOS_DE_LECTURA, ahora
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
    assert cliente.get("/auth/sesion").json() == {"usuario": "ana", "debe_cambiar_contrasena": True, "perfil": "escritura"}

    corta = cliente.post("/auth/cambiar-contrasena", json={"actual": temporal, "nueva": "corta"})
    assert corta.status_code == 400
    mal = cliente.post("/auth/cambiar-contrasena", json={"actual": "no-es-esta", "nueva": "una contraseña larga"})
    assert mal.status_code == 400
    bien = cliente.post("/auth/cambiar-contrasena", json={"actual": temporal, "nueva": "una contraseña larga"})
    assert bien.status_code == 200

    assert cliente.get("/catalogo").status_code == 200
    assert _entrar(TestClient(app), "ana", temporal).status_code == 401
    assert _entrar(TestClient(app), "ana", "una contraseña larga").json()["debe_cambiar_contrasena"] is False


def _usuario_listo(db_session, nombre="ana", contrasena="una contraseña larga", perfil="escritura"):
    temporal = usuarios.crear(db_session, nombre, perfil)
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


# --- Perfiles (sesión 2026-10-16) -------------------------------------------

def _rutas_con_datos():
    """Todas las rutas detrás de la sesión: las de `app.routes` menos las de
    `/auth` y `/health`, que no llevan `get_usuario_con_permiso`."""
    for metodo, plantilla, concreta in _rutas():
        if plantilla.startswith("/auth/") or plantilla == "/health":
            continue
        yield metodo, plantilla, concreta


def _rutas_que_escriben():
    return [r for r in _rutas_con_datos() if r[0] not in METODOS_DE_LECTURA]


def _entrar_como(db_session, nombre, perfil):
    _usuario_listo(db_session, nombre=nombre, perfil=perfil)
    cliente = TestClient(app, raise_server_exceptions=False)
    assert _entrar(cliente, nombre, "una contraseña larga").status_code == 200
    return cliente


def _filas(db_session):
    """Recuento de filas de cada tabla con datos (las de acceso no: la sesión
    renueva su actividad y eso no es escribir datos)."""
    from sqlalchemy import func

    return {tabla.name: db_session.scalar(select(func.count()).select_from(tabla)) for tabla in _TABLAS}


# Un cuerpo que valdría para casi cualquier ruta, para que el 403 no sea un
# 422 disfrazado: la negativa tiene que venir del perfil, no del formulario.
_CUERPO = {"codigo_expediente": "6.26/28510.9999", "motivo": "m", "nota": "n", "valor": "1"}


def test_un_usuario_de_consulta_no_puede_escribir_en_ninguna_ruta(cliente, db_session):
    escriben = _rutas_que_escriben()
    # Las que nombró el cliente, para que la lista no salga corta por error.
    plantillas = {(m, p) for m, p, _c in escriben}
    for esperada in (
        ("PATCH", "/catalogo/lineas/{linea_id}"),
        ("POST", "/catalogo/lineas/{linea_id}/confirmar"),
        ("POST", "/catalogo/lineas/{linea_id}/descartar"),
        ("POST", "/catalogo/lineas/{linea_id}/pendiente"),
        ("POST", "/revision/candidatos-matricula/{linea_id}/aceptar"),
        ("POST", "/expedientes"),
        ("POST", "/expedientes/{expediente_id}/descargar"),
        ("POST", "/expedientes/{expediente_id}/extraer"),
        ("POST", "/mantenimiento/ejecutar"),
    ):
        assert esperada in plantillas
    assert len(escriben) > 25

    consulta = _entrar_como(db_session, "eva", "consulta")
    antes = _filas(db_session)
    abiertas = []
    for metodo, plantilla, concreta in escriben:
        respuesta = consulta.request(metodo, concreta, json=_CUERPO)
        if (respuesta.status_code, respuesta.json().get("detail")) != (403, DETALLE_SOLO_CONSULTA):
            abiertas.append((metodo, plantilla, respuesta.status_code))
    assert abiertas == []
    assert _filas(db_session) == antes


def test_un_usuario_de_consulta_ve_todas_las_pantallas_y_exporta(cliente, db_session):
    consulta = _entrar_como(db_session, "eva", "consulta")
    lecturas = [r for r in _rutas_con_datos() if r[0] in METODOS_DE_LECTURA]
    assert ("GET", "/catalogo/exportar.xlsx") in {(m, p) for m, p, _c in lecturas}
    cerradas = []
    for metodo, plantilla, concreta in lecturas:
        respuesta = consulta.request(metodo, concreta)
        if respuesta.status_code in (401, 403):
            cerradas.append((metodo, plantilla, respuesta.status_code))
    assert cerradas == []
    assert consulta.get("/catalogo").status_code == 200
    exportado = consulta.get("/catalogo/exportar.xlsx")
    assert exportado.status_code == 200 and exportado.content[:2] == b"PK"


def test_el_perfil_no_frena_a_un_usuario_de_escritura(cliente, db_session):
    escritura = _entrar_como(db_session, "ana", "escritura")
    frenadas = []
    for metodo, plantilla, concreta in _rutas_que_escriben():
        respuesta = escritura.request(metodo, concreta, json=_CUERPO)
        if respuesta.status_code in (401, 403):
            frenadas.append((metodo, plantilla, respuesta.status_code))
    assert frenadas == []
    assert escritura.post("/expedientes", json={"codigo_expediente": "6.26/28510.9998"}).status_code == 200


def test_consulta_puede_cambiar_su_contrasena_y_salir(cliente, db_session):
    temporal = usuarios.crear(db_session, "eva", "consulta")
    entrada = _entrar(cliente, "eva", temporal)
    assert entrada.json() == {"usuario": "eva", "debe_cambiar_contrasena": True, "perfil": "consulta"}
    assert cliente.post("/auth/cambiar-contrasena", json={"actual": temporal, "nueva": "una contraseña larga"}).status_code == 200
    assert cliente.get("/auth/sesion").json()["perfil"] == "consulta"
    assert cliente.post("/auth/salir").status_code == 200
    assert cliente.get("/catalogo").status_code == 401


def test_cambiar_el_perfil_vale_desde_la_peticion_siguiente(cliente, db_session):
    cliente = _entrar_como(db_session, "eva", "consulta")  # sustituye al de la fixture, sin sesión
    assert cliente.post("/expedientes", json={"codigo_expediente": "6.26/28510.9999"}).status_code == 403
    usuarios.cambiar_perfil(db_session, "eva", "escritura")
    assert cliente.post("/expedientes", json={"codigo_expediente": "6.26/28510.9999"}).status_code == 200
    usuarios.cambiar_perfil(db_session, "eva", "consulta")
    assert cliente.post("/expedientes", json={"codigo_expediente": "6.26/28510.9998"}).status_code == 403
    assert cliente.get("/auth/sesion").json()["perfil"] == "consulta"


def test_la_consola_exige_el_perfil_al_crear_y_solo_admite_los_dos(db_session, monkeypatch, capsys):
    with pytest.raises(usuarios.ErrorUsuarios):
        usuarios.crear(db_session, "eva", "administrador")
    usuarios.crear(db_session, "eva", "consulta")
    with pytest.raises(usuarios.ErrorUsuarios):
        usuarios.cambiar_perfil(db_session, "eva", "todo")
    assert [(f["usuario"], f["perfil"]) for f in usuarios.listar(db_session)] == [("eva", "consulta")]

    import app.db

    monkeypatch.setattr(app.db, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(db_session, "close", lambda: None)
    with pytest.raises(SystemExit):
        usuarios.main(["crear", "luis"])  # sin --perfil no crea nada
    assert usuarios.main(["crear", "luis", "--perfil", "escritura"]) == 0
    assert usuarios.main(["perfil", "luis", "consulta"]) == 0
    assert {f["usuario"]: f["perfil"] for f in usuarios.listar(db_session)} == {"eva": "consulta", "luis": "consulta"}
    capsys.readouterr()


def test_los_usuarios_que_ya_existian_quedan_con_escritura(db_session):
    from sqlalchemy import text

    # Como una fila de antes de la migración 0045: sin perfil.
    db_session.execute(text(
        "INSERT INTO usuarios (nombre, hash_contrasena, activo, debe_cambiar_contrasena, created_at) "
        "VALUES ('vieja', 'x', 1, 0, CURRENT_TIMESTAMP)"
    ))
    db_session.commit()
    assert db_session.scalar(select(models.Usuario.perfil).where(models.Usuario.nombre == "vieja")) == "escritura"
