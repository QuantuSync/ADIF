from unittest.mock import MagicMock

from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError

from app.esperar_bd import esperar_base_datos


def test_esperar_base_datos_conecta_a_la_primera_sin_dormir(monkeypatch):
    # Motor real (SQLite en memoria): conectable desde el primer intento, no
    # debe dormir ni una sola vez.
    dormido = []
    monkeypatch.setattr("app.esperar_bd.time.sleep", lambda s: dormido.append(s))

    motor = create_engine("sqlite:///:memory:")
    assert esperar_base_datos(intentos=5, espera_segundos=1, motor=motor) is True
    assert dormido == []


def _motor_falla_n_veces(n: int) -> MagicMock:
    """Motor falso cuyo `.connect()` lanza `OperationalError` en las primeras
    `n` llamadas y conecta de verdad (SQLite en memoria) a partir de ahí --
    reproduce "postgres tarda unos segundos en aceptar conexiones tras un
    reinicio real" sin depender de un Postgres de verdad."""
    motor_real = create_engine("sqlite:///:memory:")
    llamadas = {"n": 0}

    def connect_falible(*args, **kwargs):
        llamadas["n"] += 1
        if llamadas["n"] <= n:
            raise OperationalError("SELECT 1", {}, Exception("conexión rechazada"))
        return motor_real.connect(*args, **kwargs)

    motor = MagicMock()
    motor.connect.side_effect = connect_falible
    return motor


def test_esperar_base_datos_reintenta_hasta_conectar(monkeypatch):
    dormido = []
    monkeypatch.setattr("app.esperar_bd.time.sleep", lambda s: dormido.append(s))

    motor = _motor_falla_n_veces(3)
    assert esperar_base_datos(intentos=10, espera_segundos=2, motor=motor) is True
    assert len(dormido) == 3  # duerme entre cada intento fallido, no tras el último (el que sí conecta)


def test_esperar_base_datos_agota_intentos_y_devuelve_false_sin_lanzar(monkeypatch):
    dormido = []
    monkeypatch.setattr("app.esperar_bd.time.sleep", lambda s: dormido.append(s))

    motor = _motor_falla_n_veces(100)  # nunca conecta dentro del límite de intentos
    assert esperar_base_datos(intentos=4, espera_segundos=1, motor=motor) is False
    assert len(dormido) == 3  # 4 intentos, duerme entre cada uno salvo tras el último
