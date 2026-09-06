"""CONTEXTO.md sección 17 (pendiente): recuperación de trabajos huérfanos.
Un trabajo `en_proceso` bloqueado por un worker que ya no existe (contenedor
caído, `dockerd` reiniciado a mitad de ejecución) no lo recoge nadie más,
porque `tomar_siguiente_trabajo` solo mira `estado = pendiente`."""
from datetime import datetime, timedelta, timezone

from app.models import EstadoTrabajo, TrabajoCola
from app.queue import ejecutar_trabajo, encolar_trabajo, reclamar_trabajos_huerfanos, tomar_siguiente_trabajo


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
