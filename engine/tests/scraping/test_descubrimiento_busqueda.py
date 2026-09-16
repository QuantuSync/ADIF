"""Descubrimiento por búsqueda directa en la Plataforma (sesión 2026-09-16).

Ningún test toca la red: se sustituye `buscar_codigos_de_fragmentos`, la
única función del módulo que abre navegador, por un doble que devuelve los
códigos que devolvería la Plataforma.
"""
import pytest

from app.models import EstadoExpediente, Expediente
from app.scraping import descubrimiento_busqueda
from app.scraping.descubrimiento_busqueda import descubrir_por_busqueda, fragmentos_configurados


def _doble_busqueda(monkeypatch, por_fragmento: dict):
    async def falso(fragmentos):
        return {f: list(por_fragmento.get(f, [])) for f in fragmentos}

    monkeypatch.setattr(descubrimiento_busqueda, "buscar_codigos_de_fragmentos", falso)


def test_da_de_alta_los_que_no_estaban(db_session, monkeypatch):
    _doble_busqueda(monkeypatch, {"28510": ["6.26/28510.0016", "6.26/28510.0074"]})

    resumen = descubrir_por_busqueda(db_session, fragmentos=["28510"])

    assert resumen.expedientes_nuevos == 2
    assert resumen.codigos_encontrados == 2
    assert sorted(resumen.codigos_nuevos) == ["6.26/28510.0016", "6.26/28510.0074"]
    codigos = {e.codigo_expediente for e in db_session.query(Expediente).all()}
    assert codigos == {"6.26/28510.0016", "6.26/28510.0074"}


def test_no_duplica_los_que_ya_existen(db_session, monkeypatch):
    db_session.add(Expediente(codigo_expediente="6.26/28510.0016"))
    db_session.commit()
    _doble_busqueda(monkeypatch, {"28510": ["6.26/28510.0016"]})

    resumen = descubrir_por_busqueda(db_session, fragmentos=["28510"])

    assert resumen.expedientes_nuevos == 0
    assert resumen.ya_conocidos == 1
    assert db_session.query(Expediente).count() == 1


def test_reabre_un_sin_publicar_que_la_busqueda_si_encuentra(db_session, monkeypatch):
    """La búsqueda es evidencia positiva de que está publicado: el negativo
    que lo dejó en `sin_publicar` era falso. Vuelve a `pendiente` y se
    limpian las marcas, para que el bucle de frescura del ciclo (que excluye
    los `sin_publicar`) lo recoja y encole su descarga."""
    exp = Expediente(
        codigo_expediente="6.26/28510.0004",
        estado=EstadoExpediente.sin_publicar,
        sin_publicar_version_busqueda="2026-09-07",
    )
    db_session.add(exp)
    db_session.commit()
    _doble_busqueda(monkeypatch, {"28510": ["6.26/28510.0004"]})

    resumen = descubrir_por_busqueda(db_session, fragmentos=["28510"])

    assert resumen.sin_publicar_reabiertos == 1
    assert resumen.codigos_reabiertos == ["6.26/28510.0004"]
    db_session.refresh(exp)
    assert exp.estado == EstadoExpediente.pendiente
    assert exp.sin_publicar_en is None
    assert exp.sin_publicar_version_busqueda is None


def test_un_codigo_repetido_entre_fragmentos_se_cuenta_una_vez(db_session, monkeypatch):
    """Dos fragmentos solapados ("28510" y "6.26/28510") devuelven el mismo
    expediente: no se da de alta dos veces ni se cuenta dos veces."""
    _doble_busqueda(
        monkeypatch,
        {"28510": ["6.26/28510.0016"], "6.26/28510": ["6.26/28510.0016"]},
    )

    resumen = descubrir_por_busqueda(db_session, fragmentos=["28510", "6.26/28510"])

    assert resumen.expedientes_nuevos == 1
    assert resumen.codigos_encontrados == 1
    assert resumen.encontrados_por_fragmento == {"28510": 1, "6.26/28510": 1}
    assert db_session.query(Expediente).count() == 1


def test_lista_vacia_explicita_no_abre_navegador(db_session, monkeypatch):
    """`[]` es "ninguno", distinto de `None` ("los configurados") -- ver el
    docstring de `descubrir_por_busqueda`."""
    def explota(fragmentos):  # pragma: no cover - no debe llegar a llamarse
        raise AssertionError("no debería abrir navegador sin fragmentos")

    monkeypatch.setattr(descubrimiento_busqueda, "buscar_codigos_de_fragmentos", explota)

    resumen = descubrir_por_busqueda(db_session, fragmentos=[])

    assert resumen.codigos_encontrados == 0
    assert resumen.fragmentos == []


def test_sin_fragmentos_usa_los_configurados(db_session, monkeypatch):
    from app import config
    monkeypatch.setattr(config.settings, "busqueda_fragmentos", "")
    monkeypatch.setattr(config.settings, "sindicacion_departamentos_adif", "28510")
    _doble_busqueda(monkeypatch, {"28510": ["6.26/28510.0016"]})

    resumen = descubrir_por_busqueda(db_session)

    assert resumen.fragmentos == ["28510"]
    assert resumen.expedientes_nuevos == 1


@pytest.mark.parametrize(
    "busqueda, departamentos, esperado",
    [
        ("", "28510", ["28510"]),
        ("", "28510,28520", ["28510", "28520"]),
        ("6.26/28510, 4.26/28510", "28510", ["6.26/28510", "4.26/28510"]),
    ],
)
def test_fragmentos_configurados_cae_a_los_departamentos(monkeypatch, busqueda, departamentos, esperado):
    """Sin `BUSQUEDA_FRAGMENTOS`, el criterio es el mismo que el de la
    sindicación -- una sola fuente de "qué es nuestro", no dos listas que
    puedan divergir."""
    from app import config
    monkeypatch.setattr(config.settings, "busqueda_fragmentos", busqueda)
    monkeypatch.setattr(config.settings, "sindicacion_departamentos_adif", departamentos)

    assert fragmentos_configurados() == esperado


def test_descarta_los_codigos_donde_el_fragmento_va_pegado_a_otros_digitos(db_session, monkeypatch):
    """El buscador de la Plataforma hace coincidencia por subcadena pura:
    "28510" devuelve también `PcPG/2026/828510` y `EMER_HV_2020_62285100`,
    que no son del departamento (verificado en vivo, sesión 2026-09-16). El
    criterio se aplica aquí, con la misma regla que la sindicación."""
    _doble_busqueda(
        monkeypatch,
        {"28510": ["6.26/28510.0016", "PcPG/2026/828510", "EMER_HV_2020_62285100"]},
    )

    resumen = descubrir_por_busqueda(db_session, fragmentos=["28510"])

    assert resumen.expedientes_nuevos == 1
    assert resumen.codigos_encontrados == 1
    assert sorted(resumen.codigos_descartados) == ["EMER_HV_2020_62285100", "PcPG/2026/828510"]
    codigos = {e.codigo_expediente for e in db_session.query(Expediente).all()}
    assert codigos == {"6.26/28510.0016"}
