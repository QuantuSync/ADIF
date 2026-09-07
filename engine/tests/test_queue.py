"""CONTEXTO.md sección 17 (pendiente): recuperación de trabajos huérfanos.
Un trabajo `en_proceso` bloqueado por un worker que ya no existe (contenedor
caído, `dockerd` reiniciado a mitad de ejecución) no lo recoge nadie más,
porque `tomar_siguiente_trabajo` solo mira `estado = pendiente`."""
from datetime import datetime, timedelta, timezone

from app.models import EstadoTrabajo, TrabajoCola
from app.queue import (
    calcular_espera_reintento,
    ejecutar_trabajo,
    encolar_trabajo,
    reclamar_trabajos_huerfanos,
    tomar_siguiente_trabajo,
)


def _crear_en_proceso(db_session, *, hace_segundos, intentos=1, max_intentos=3):
    trabajo = TrabajoCola(
        tipo="descargar_expediente",
        estado=EstadoTrabajo.en_proceso,
        intentos=intentos,
        max_intentos=max_intentos,
        bloqueado_por="worker-fantasma",
        bloqueado_en=datetime.now(timezone.utc) - timedelta(seconds=hace_segundos),
    )
    db_session.add(trabajo)
    db_session.commit()
    db_session.refresh(trabajo)
    return trabajo


def test_trabajo_vencido_con_intentos_libres_vuelve_a_pendiente(db_session):
    trabajo = _crear_en_proceso(db_session, hace_segundos=600, intentos=1, max_intentos=3)

    reclamados = reclamar_trabajos_huerfanos(db_session, umbral_segundos=300)

    assert reclamados == 1
    db_session.refresh(trabajo)
    assert trabajo.estado == EstadoTrabajo.pendiente
    assert trabajo.bloqueado_por is None
    assert trabajo.bloqueado_en is None
    assert "huérfano" in trabajo.error
    # No se reinicia intentos: un reclamo no es una oportunidad extra.
    assert trabajo.intentos == 1


def test_trabajo_vencido_sin_intentos_libres_va_a_fallido(db_session):
    trabajo = _crear_en_proceso(db_session, hace_segundos=600, intentos=3, max_intentos=3)

    reclamados = reclamar_trabajos_huerfanos(db_session, umbral_segundos=300)

    assert reclamados == 1
    db_session.refresh(trabajo)
    assert trabajo.estado == EstadoTrabajo.fallido
    assert "huérfano" in trabajo.error


def test_trabajo_reciente_no_se_reclama(db_session):
    trabajo = _crear_en_proceso(db_session, hace_segundos=10, intentos=1, max_intentos=3)

    reclamados = reclamar_trabajos_huerfanos(db_session, umbral_segundos=300)

    assert reclamados == 0
    db_session.refresh(trabajo)
    assert trabajo.estado == EstadoTrabajo.en_proceso


def test_trabajo_reclamado_puede_volver_a_tomarse(db_session):
    _crear_en_proceso(db_session, hace_segundos=600, intentos=1, max_intentos=3)

    reclamar_trabajos_huerfanos(db_session, umbral_segundos=300)
    tomado = tomar_siguiente_trabajo(db_session)

    assert tomado is not None
    assert tomado.estado == EstadoTrabajo.en_proceso
    assert tomado.intentos == 2


def test_tomar_siguiente_trabajo_excluye_tipos(db_session):
    """Bloque 1 del ciclo de mantenimiento (app.mantenimiento.ciclo): su
    drenaje síncrono nunca debe recoger otro trabajo de su propio tipo."""
    encolar_trabajo(db_session, tipo="mantenimiento_ciclo")
    ping = encolar_trabajo(db_session, tipo="ping")

    tomado = tomar_siguiente_trabajo(db_session, excluir_tipos={"mantenimiento_ciclo"})

    assert tomado is not None
    assert tomado.id == ping.id


def test_ejecutar_trabajo_generico_completa_con_manejador(db_session):
    trabajo = encolar_trabajo(db_session, tipo="ping")
    manejadores = {"ping": lambda db, t: {"ok": True}}

    ejecutar_trabajo(db_session, trabajo, manejadores)

    assert trabajo.estado == EstadoTrabajo.completado
    assert trabajo.resultado == {"ok": True}


def test_ejecutar_trabajo_generico_tipo_desconocido_falla(db_session):
    trabajo = encolar_trabajo(db_session, tipo="tipo-inventado")

    ejecutar_trabajo(db_session, trabajo, manejadores={})

    assert trabajo.estado == EstadoTrabajo.fallido
    assert "tipo de trabajo desconocido" in trabajo.error


def test_ejecutar_trabajo_generico_reintenta_si_quedan_intentos(db_session):
    trabajo = encolar_trabajo(db_session, tipo="ping")
    trabajo.intentos = 1
    trabajo.max_intentos = 3
    db_session.commit()

    def falla(db, t):
        raise RuntimeError("boom")

    ejecutar_trabajo(db_session, trabajo, manejadores={"ping": falla})

    assert trabajo.estado == EstadoTrabajo.pendiente
    assert trabajo.error == "boom"


# --- Sesión de límite de tasa (2026-09-07): backoff creciente en
# reintentos -- 454 descargas fallidas seguidas, sin ninguna espera entre
# reintentos, coincidieron con un patrón de bloqueo de la Plataforma real.


def test_calcular_espera_reintento_crece_y_tiene_tope():
    assert calcular_espera_reintento(1) == 30.0
    assert calcular_espera_reintento(2) == 120.0
    assert calcular_espera_reintento(3) == 480.0
    # Tope: un `intentos` mayor no sigue creciendo sin límite.
    assert calcular_espera_reintento(10) == 600.0


def test_ejecutar_trabajo_reintento_fija_disponible_en_con_backoff(db_session):
    trabajo = encolar_trabajo(db_session, tipo="ping")
    trabajo.intentos = 2
    trabajo.max_intentos = 3
    db_session.commit()

    def falla(db, t):
        raise RuntimeError("boom")

    antes = datetime.now(timezone.utc)
    ejecutar_trabajo(db_session, trabajo, manejadores={"ping": falla})

    assert trabajo.estado == EstadoTrabajo.pendiente
    assert trabajo.disponible_en is not None
    # SQLite (tests) no conserva el huso horario al releer una columna
    # DateTime(timezone=True) -- se trata como UTC, igual que el resto del
    # código (ver `_con_tz` en app.sindicacion.descubrimiento).
    disponible_en = trabajo.disponible_en
    if disponible_en.tzinfo is None:
        disponible_en = disponible_en.replace(tzinfo=timezone.utc)
    # intentos=2 -> espera de calcular_espera_reintento(2) = 120s
    espera_real = (disponible_en - antes).total_seconds()
    assert 115 <= espera_real <= 125


def test_tomar_siguiente_trabajo_no_recoge_uno_con_disponible_en_futuro(db_session):
    trabajo = encolar_trabajo(db_session, tipo="ping")
    trabajo.disponible_en = datetime.now(timezone.utc) + timedelta(seconds=60)
    db_session.commit()

    assert tomar_siguiente_trabajo(db_session) is None


def test_tomar_siguiente_trabajo_recoge_uno_con_disponible_en_pasado(db_session):
    trabajo = encolar_trabajo(db_session, tipo="ping")
    trabajo.disponible_en = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.commit()

    tomado = tomar_siguiente_trabajo(db_session)

    assert tomado is not None
    assert tomado.id == trabajo.id


def test_tomar_siguiente_trabajo_salta_al_disponible_aunque_sea_mas_reciente(db_session):
    # El trabajo más antiguo por `created_at` sigue en backoff -- el
    # siguiente `pendiente` ya disponible pasa por delante, para que un
    # reintento en espera no bloquee el resto de la cola.
    en_backoff = encolar_trabajo(db_session, tipo="ping")
    en_backoff.disponible_en = datetime.now(timezone.utc) + timedelta(seconds=300)
    disponible = encolar_trabajo(db_session, tipo="ping")
    db_session.commit()

    tomado = tomar_siguiente_trabajo(db_session)

    assert tomado is not None
    assert tomado.id == disponible.id
