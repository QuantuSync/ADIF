"""Reconstrucción del catálogo desde cero en una base de datos aparte
(sesión 2026-09-21, tercera parte).

Por qué existe: **un `None` no pisa un valor ya guardado** (CONTEXTO.md
sección 9), así que una celda que escribió un código anterior, ya corregido,
sobrevive a cualquier reproceso si el código de hoy no produce nada para ella.
Ningún reproceso lo detecta. La única forma de verlo es extraer el corpus
entero sobre una base sin nada extraído y comparar el Excel resultante con el
de producción celda a celda.

La base aparte es una copia de la de producción (`pg_dump` + `pg_restore`) a
la que `vaciar_lo_extraido` quita todo lo que produce la extracción —líneas,
lotes, trazas, presupuestos por lote, importes y bajas del expediente y lo que
la extracción anota en cada documento— y le deja todo lo demás: los
documentos, las **cachés de texto, de reconocimiento óptico, de mapeo de
cabecera y de código de material**, los listados de entrada (códigos, SAP,
estados, maestro, en ejecución) y la sindicación. `reconstruir` lanza después
el mismo ciclo de siempre, forzado y con la red apagada. Procedimiento
completo en CONTEXTO.md sección 13.

Lo que NO se vacía, a propósito: el título (`nombre_proyecto`), la matriz y el
cruce con el listado de códigos, porque los escriben también los listados de
entrada, y rehacerlos exigiría repetir cada carga en el orden en que se hizo.

**Nunca corre contra producción**: `comprobar_base_aparte` exige que la base
a la que está conectada se llame distinto de la de producción y contenga
`reconstruccion` en el nombre.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.mantenimiento.ciclo import TIPO_TRABAJO as TIPO_MANTENIMIENTO_CICLO
from app.queue import encolar_trabajo, tomar_siguiente_trabajo

BASE_PRODUCCION = "adif"
MARCA_BASE_APARTE = "reconstruccion"

# El payload del reproceso "con la red apagada" de todas las sesiones de
# cierre: las cuatro vías de red del ciclo, apagadas.
PAYLOAD_SIN_RED = {"forzar": True, "sindicacion_desactivada": True, "busqueda_desactivada": True}

# Todo lo que escribe la extracción, en el orden que imponen las claves
# ajenas. Lo demás de la base se queda como está.
_VACIADO = (
    ("candidatos_matricula", "delete from candidatos_matricula"),
    ("lineas_catalogo", "delete from lineas_catalogo"),
    ("trazas_origen", "delete from trazas_origen"),
    ("presupuestos_lote_documento", "delete from presupuestos_lote_documento"),
    ("lotes", "delete from lotes"),
    (
        "expedientes",
        "update expedientes set importe_licitacion = null, importe_adjudicacion = null, "
        "baja_global = null, baja_variable_por_lote = null, lotes_totales_declarados = null, "
        "extraido_en = null, version_logica_extraccion = null, huella_documentos = null",
    ),
    (
        "documentos",
        "update documentos set paginas = null, identidad_lote_codigo = null, "
        "identidad_lote_identificador = null, procesado_en = null",
    ),
    # Lo que la copia trae pendiente en la cola de producción no se ejecuta
    # aquí: el ciclo de abajo es lo único que tiene que correr.
    ("trabajos_cola", "delete from trabajos_cola where estado in ('pendiente', 'en_proceso')"),
)


class BaseDeProduccionError(RuntimeError):
    pass


def comprobar_base_aparte(nombre_base: str) -> None:
    if nombre_base == BASE_PRODUCCION or MARCA_BASE_APARTE not in nombre_base:
        raise BaseDeProduccionError(
            f"la reconstrucción solo corre en una base aparte (con «{MARCA_BASE_APARTE}» en el "
            f"nombre); esta es «{nombre_base}»"
        )


def _base_actual(db: Session) -> str:
    return db.execute(text("select current_database()")).scalar_one()


def vaciar_lo_extraido(db: Session) -> dict:
    comprobar_base_aparte(_base_actual(db))
    recuento = {}
    for tabla, sentencia in _VACIADO:
        recuento[tabla] = db.execute(text(sentencia)).rowcount
    db.commit()
    return recuento


def reconstruir(db: Session, manejadores: dict) -> dict:
    """Encola y ejecuta aquí mismo un único ciclo forzado y sin red, con el
    mismo despachador del worker. Devuelve su resumen (`descargas_lanzadas`
    tiene que ser 0)."""
    from app.queue import ejecutar_trabajo

    comprobar_base_aparte(_base_actual(db))
    trabajo = encolar_trabajo(db, tipo=TIPO_MANTENIMIENTO_CICLO, payload=dict(PAYLOAD_SIN_RED))
    siguiente = tomar_siguiente_trabajo(db)
    if siguiente is None or siguiente.id != trabajo.id:
        raise RuntimeError("la cola de la base aparte tiene otro trabajo por delante del ciclo")
    ejecutar_trabajo(db, siguiente, manejadores)
    db.refresh(siguiente)
    # La unidad del maestro de materiales la aplica el propio ciclo desde la
    # sesión 2026-09-22 (va en `resultado["unidades_desde_maestro"]`).
    return {"trabajo": siguiente.id, "estado": siguiente.estado.value, "resultado": siguiente.resultado,
            "error": siguiente.error}


def exportar(db: Session, ruta: Path) -> None:
    from app.exportacion import generar_excel_catalogo

    ruta.write_bytes(generar_excel_catalogo(db))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--vaciar", action="store_true", help="quita todo lo extraído de la base aparte")
    parser.add_argument("--reconstruir", action="store_true", help="un ciclo forzado y sin red")
    parser.add_argument("--completar-unidades", action="store_true",
                        help="solo el paso de las unidades del maestro (ya incluido en el ciclo)")
    parser.add_argument("--exportar", type=Path, help="escribe el Excel del catálogo en esta ruta")
    args = parser.parse_args(argv)

    from app.db import SessionLocal

    db = SessionLocal()
    try:
        comprobar_base_aparte(_base_actual(db))
        if args.vaciar:
            print(json.dumps({"vaciado": vaciar_lo_extraido(db)}, ensure_ascii=False), flush=True)
        if args.reconstruir:
            from app.worker import MANEJADORES

            print(json.dumps(reconstruir(db, MANEJADORES), ensure_ascii=False, default=str), flush=True)
        if args.completar_unidades:
            from app.extraccion.maestro_materiales import completar_unidades_desde_maestro

            print(json.dumps({"unidades_desde_maestro": vars(completar_unidades_desde_maestro(db))},
                             ensure_ascii=False, default=str), flush=True)
        if args.exportar:
            exportar(db, args.exportar)
            print(json.dumps({"exportado": str(args.exportar)}), flush=True)
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
