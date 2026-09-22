"""Extrae desde cero solo unos expedientes en una base aparte y compara sus
líneas con producción, celda a celda (sesión 2026-09-22).

Para probar un arreglo de la extracción sin esperar a una reconstrucción
completa: la base aparte (`adif_reconstruccion_seco`, o cualquiera con
`reconstruccion` en el nombre) es una copia de producción; `--vaciar` le quita
todo lo extraído (el mismo `vaciar_lo_extraido` de la reconstrucción) y cada
pasada lanza `extraer_expediente` para los expedientes nombrados, con el mismo
despachador del worker y la unidad del maestro de fin de ciclo. Corre en un
contenedor de la imagen del worker conectado solo a la red aislada.

uso: python extrae_subconjunto.py [--vaciar] [--pasadas 2] [--contra BASE] --salida x.json EXP [EXP ...]
Sin `--vaciar`, sobre una copia del estado de producción: sirve para ver qué
hace el código nuevo con los valores y las claves que producción ya tiene.
"""
import argparse
import json
from collections import Counter

from sqlalchemy import create_engine, select, text

from app.db import SessionLocal
from app.mantenimiento.reconstruccion import _base_actual, comprobar_base_aparte, vaciar_lo_extraido
from app.models import Expediente
from app.queue import ejecutar_trabajo, encolar_trabajo, tomar_siguiente_trabajo

from compara_bd import CAMPOS_LINEA, SQL_LINEAS, URL, comparar

CAMPOS_IGNORADOS = {"orden_aparicion"}


def leer(base, expedientes):
    eng = create_engine(URL.format(base))
    with eng.connect() as c:
        filas = [dict(r._mapping) for r in c.execute(text(SQL_LINEAS))]
    return {(f["exp"], f["lote"], f["clave"]): f for f in filas if f["exp"] in expedientes}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vaciar", action="store_true")
    ap.add_argument("--pasadas", type=int, default=2)
    ap.add_argument("--salida", required=True)
    ap.add_argument("--contra", default="adif", help="base con la que se compara (producción por defecto)")
    ap.add_argument("expedientes", nargs="+")
    args = ap.parse_args()

    from app.extraccion.maestro_materiales import completar_unidades_desde_maestro
    from app.worker import MANEJADORES

    db = SessionLocal()
    base = _base_actual(db)
    comprobar_base_aparte(base)
    if args.vaciar:
        print(json.dumps(vaciar_lo_extraido(db)), flush=True)
    ids = db.execute(select(Expediente.id).where(Expediente.codigo_expediente.in_(args.expedientes))).scalars().all()
    for pasada in range(args.pasadas):
        for eid in ids:
            encolar_trabajo(db, tipo="extraer_expediente", expediente_id=eid)
        while (t := tomar_siguiente_trabajo(db)) is not None:
            ejecutar_trabajo(db, t, MANEJADORES)
            db.refresh(t)
            print(pasada + 1, t.expediente_id, t.estado.value, (t.error or "")[:200], flush=True)
        completar_unidades_desde_maestro(db)
    db.close()

    p, r = leer(args.contra, set(args.expedientes)), leer(base, set(args.expedientes))
    difs, solo_p, solo_r = comparar(p, r, [c for c in CAMPOS_LINEA if c not in CAMPOS_IGNORADOS])
    print("lineas", len(p), len(r), "difs", len(difs), "solo_prod", len(solo_p), "solo_recon", len(solo_r))
    print(Counter((d["clave"][0], d["campo"]) for d in difs).most_common())
    with open(args.salida, "w", encoding="utf-8") as f:
        json.dump({"diferencias": difs, "solo_produccion": [p[k] for k in solo_p],
                   "solo_reconstruida": [r[k] for k in solo_r]}, f, ensure_ascii=False, default=str, indent=1)


if __name__ == "__main__":
    main()
