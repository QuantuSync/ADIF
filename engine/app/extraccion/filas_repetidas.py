"""Las filas que el propio cuadro repite (sesión 2026-09-21, tercera parte,
bloque 3 del encargo: las líneas que faltan).

El caso real: el cuadro de `2.23/28510.0108` trae dos veces la misma fila
("100 × 1,50 €" y "10 × 3,12 €"), y el catálogo la tenía una sola vez: la
fusión por firma (`app.catalogo._firma_material`, descripción + precio) existe
para juntar el ECO de un material en dos tablas distintas del mismo documento,
y juntaba también las dos filas iguales de una misma tabla. El lote se quedaba
corto exactamente por su importe (181,20 €; 362,40 € en `2.24/28510.0068`).

**Condición del cliente: una línea recuperada solo entra si con ella el lote
cuadra con su presupuesto publicado.** Así que las repeticiones solo se
conservan cuando, contándolas, el lote suma exactamente su presupuesto y sin
ellas no. Una repetición cuenta solo dentro de la MISMA tabla y la MISMA
página -- dos filas seguidas de un mismo cuadro --, nunca entre tablas (eso es
el eco, y se sigue fundiendo). La fila conservada lleva
`MOTIVO_FILA_REPETIDA_EN_EL_CUADRO`, y con él no tiene firma de material: no se
funde con la otra ni en esta pasada ni en las siguientes.
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Optional

from app.catalogo import _MOTIVO_FILA_REPETIDA_EN_EL_CUADRO as MOTIVO_FILA_REPETIDA_EN_EL_CUADRO
from app.extraccion.partida_alzada_del_lote import _importe

_TOLERANCIA = Decimal("0.01")


def _firma(linea: dict) -> Optional[tuple]:
    if linea.get("codigo_precio") or not linea.get("descripcion") or linea.get("precio_unitario") is None:
        return None
    return (linea.get("matricula"), linea["descripcion"], linea["precio_unitario"], linea.get("cantidad"))


def conservar_filas_repetidas_que_cierran_el_lote(
    lineas: list[dict], presupuestos_por_lote: dict[str, Optional[Decimal]]
) -> list[str]:
    motivos: list[str] = []
    for identificador, presupuesto in presupuestos_por_lote.items():
        if presupuesto is None:
            continue
        del_lote = [l for l in lineas if l.get("identificador_lote") == identificador]
        # Lo que el catálogo guardará sin este arreglo: una vez por firma.
        vistas: set[tuple] = set()
        sin_repetir = Decimal("0")
        for linea in del_lote:
            firma = _firma(linea)
            if firma is not None and (firma[:3]) in vistas:
                continue
            if firma is not None:
                vistas.add(firma[:3])
            sin_repetir += _importe(linea)
        if abs(sin_repetir - Decimal(presupuesto)) <= _TOLERANCIA:
            continue
        # Las repeticiones de una misma fila dentro de una tabla y página.
        por_tabla: dict[tuple, list[dict]] = defaultdict(list)
        for linea in del_lote:
            firma = _firma(linea)
            if firma is not None:
                por_tabla[(firma[:3], linea.get("tabla_origen"), linea.get("pagina"))].append(linea)
        extra_por_firma: dict[tuple, list[dict]] = {}
        for (firma, _tabla, _pagina), grupo in por_tabla.items():
            if len(grupo) > 1 and len(grupo) - 1 > len(extra_por_firma.get(firma, [])):
                extra_por_firma[firma] = grupo[1:]
        if not extra_por_firma:
            continue
        con_repetidas = sin_repetir + sum(
            (_importe(l) for extra in extra_por_firma.values() for l in extra), Decimal("0")
        )
        if abs(con_repetidas - Decimal(presupuesto)) > _TOLERANCIA:
            continue
        for extra in extra_por_firma.values():
            for linea in extra:
                linea["motivo_revision"] = (
                    f"{linea['motivo_revision']}; {MOTIVO_FILA_REPETIDA_EN_EL_CUADRO}"
                    if linea.get("motivo_revision") else MOTIVO_FILA_REPETIDA_EN_EL_CUADRO
                )
        motivos.append(
            f"LOTE {identificador}: {sum(len(e) for e in extra_por_firma.values())} fila(s) que el cuadro repite "
            f"se conservan -- con ellas el lote suma exactamente su presupuesto ({Decimal(presupuesto):.2f} €)"
        )
    return motivos
