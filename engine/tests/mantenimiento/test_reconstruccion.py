"""La reconstrucción del catálogo nunca puede vaciar la base de producción
(`app.mantenimiento.reconstruccion`, sesión 2026-09-21, tercera parte)."""
import pytest

from app.mantenimiento.reconstruccion import (
    PAYLOAD_SIN_RED,
    BaseDeProduccionError,
    comprobar_base_aparte,
)


@pytest.mark.parametrize("nombre", ["adif", "adif_copia", "otra", "adif_test"])
def test_se_niega_a_correr_fuera_de_una_base_de_reconstruccion(nombre):
    with pytest.raises(BaseDeProduccionError):
        comprobar_base_aparte(nombre)


def test_acepta_la_base_aparte():
    comprobar_base_aparte("adif_reconstruccion")


def test_el_ciclo_va_forzado_y_con_las_cuatro_vias_de_red_apagadas():
    assert PAYLOAD_SIN_RED == {"forzar": True, "sindicacion_desactivada": True, "busqueda_desactivada": True}
