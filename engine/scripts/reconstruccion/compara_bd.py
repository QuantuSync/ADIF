"""Compara producción (adif) con la base reconstruida (adif_reconstruccion)
línea a línea por (expediente, lote, clave_linea), y lotes y expedientes por
su clave. uso: python compara_bd.py /salida/cmp_bd.json"""
import json
import sys
from collections import Counter

from sqlalchemy import create_engine, text

URL = "postgresql+psycopg://adif:adif@postgres:5432/{}"

CAMPOS_LINEA = [
    "codigo_precio", "matricula", "descripcion", "codigo_material", "cantidad", "precio_unitario",
    "unidad_medida", "unidad_medida_original", "baja_lote", "precio_adjudicado", "codigo_interno",
    "doc_hash", "pagina", "motivo_revision", "estado_revision", "comentarios", "heredado_de_matriz",
    "lote_heredado_de_pagina_anterior", "lote_del_expediente", "texto_reconocido",
    "precio_corregido_desde_importe", "descripcion_desde_referencia",
    "unidad_medida_completada_desde_maestro", "unidad_medida_discrepancia_maestro",
    "matricula_confirmada_manualmente", "matricula_candidatos_rechazados", "orden_aparicion",
]
SQL_LINEAS = """
select e.codigo_expediente as exp, lo.identificador_lote as lote, l.clave_linea as clave, l.id,
  l.codigo_precio, l.matricula, l.descripcion, l.codigo_material, l.cantidad, l.precio_unitario,
  l.unidad_medida, l.unidad_medida_original, l.baja_lote, l.precio_adjudicado, l.codigo_interno,
  d.hash as doc_hash, l.pagina, l.motivo_revision, l.estado_revision::text, l.comentarios,
  l.heredado_de_matriz, l.lote_heredado_de_pagina_anterior, l.lote_del_expediente, l.texto_reconocido,
  l.precio_corregido_desde_importe, l.descripcion_desde_referencia,
  l.unidad_medida_completada_desde_maestro, l.unidad_medida_discrepancia_maestro,
  l.matricula_confirmada_manualmente, l.matricula_candidatos_rechazados, l.orden_aparicion,
  l.updated_at
from lineas_catalogo l join expedientes e on e.id = l.expediente_id
left join lotes lo on lo.id = l.lote_id left join documentos d on d.id = l.documento_origen_id
"""
CAMPOS_LOTE = ["baja_lote", "importe_licitacion", "importe_adjudicacion", "adjudicatario",
               "codigo_expediente_lote", "baja_heredada_de_matriz", "modelo_precio", "coeficiente_transformacion"]
SQL_LOTES = """select e.codigo_expediente as exp, lo.identificador_lote as lote, lo.baja_lote, lo.importe_licitacion,
 lo.importe_adjudicacion, lo.adjudicatario, lo.codigo_expediente_lote, lo.baja_heredada_de_matriz,
 lo.modelo_precio::text, lo.coeficiente_transformacion from lotes lo join expedientes e on e.id = lo.expediente_id"""
CAMPOS_EXP = ["nombre_proyecto", "codigo_matriz", "codigo_interno", "codigos_cruzados", "cruce_fila_propia",
              "importe_licitacion", "importe_adjudicacion", "baja_global", "baja_variable_por_lote",
              "lotes_totales_declarados", "estado", "error", "matriz", "aviso_sindicacion"]
SQL_EXP = """select e.codigo_expediente as exp, e.nombre_proyecto, e.codigo_matriz, e.codigo_interno,
 e.codigos_cruzados, e.cruce_fila_propia, e.importe_licitacion, e.importe_adjudicacion, e.baja_global,
 e.baja_variable_por_lote, e.lotes_totales_declarados, e.estado::text, e.error, m.codigo_expediente as matriz,
 e.aviso_sindicacion from expedientes e left join expedientes m on m.id = e.matriz_expediente_id"""


def leer(base, sql, clave):
    eng = create_engine(URL.format(base))
    with eng.connect() as c:
        filas = [dict(r._mapping) for r in c.execute(text(sql))]
    d = {}
    for f in filas:
        k = tuple(f[x] for x in clave)
        assert k not in d, (base, k)
        d[k] = f
    return d


def comparar(p, r, campos):
    difs = []
    for k in sorted(set(p) & set(r), key=str):
        for c in campos:
            if p[k][c] != r[k][c]:
                difs.append({"clave": list(k), "campo": c, "produccion": p[k][c], "reconstruida": r[k][c],
                             "id_prod": p[k].get("id")})
    return difs, sorted(set(p) - set(r), key=str), sorted(set(r) - set(p), key=str)


def main():
    out = {}
    for nombre, sql, clave, campos in (
        ("lineas", SQL_LINEAS, ("exp", "lote", "clave"), CAMPOS_LINEA),
        ("lotes", SQL_LOTES, ("exp", "lote"), CAMPOS_LOTE),
        ("expedientes", SQL_EXP, ("exp",), CAMPOS_EXP),
    ):
        p, r = leer("adif", sql, clave), leer("adif_reconstruccion", sql, clave)
        difs, solo_p, solo_r = comparar(p, r, campos)
        out[nombre] = {
            "produccion": len(p), "reconstruida": len(r), "diferencias": difs,
            "solo_produccion": [p[k] for k in solo_p], "solo_reconstruida": [r[k] for k in solo_r],
        }
        print(nombre, len(p), len(r), "difs", len(difs), "solo_prod", len(solo_p), "solo_recon", len(solo_r))
        print("  ", Counter(d["campo"] for d in difs).most_common())
    with open(sys.argv[1], "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, default=str, indent=1)


if __name__ == "__main__":
    main()
