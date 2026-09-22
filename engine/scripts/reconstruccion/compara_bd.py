"""Compara producción (adif) con la base reconstruida (adif_reconstruccion)
línea a línea por (expediente, lote, clave_linea), y lotes y expedientes por
su clave. uso: python compara_bd.py /salida/cmp_bd.json [base_a base_b]
(por defecto adif y adif_reconstruccion)."""
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


CONTENIDO = ("codigo_precio", "matricula", "descripcion", "precio_unitario", "doc_hash", "pagina")


def emparejar_por_contenido(p, r, solo_p, solo_r):
    por_contenido = {}
    for k in solo_r:
        por_contenido.setdefault((k[0], k[1]) + tuple(r[k][c] for c in CONTENIDO), []).append(k)
    quedan_p, pares = [], []
    for k in solo_p:
        c = (k[0], k[1]) + tuple(p[k][x] for x in CONTENIDO)
        if por_contenido.get(c):
            pares.append((k, por_contenido[c].pop(0)))
        else:
            quedan_p.append(k)
    usadas = {kr for _, kr in pares}
    difs = []
    for kp, kr in pares:
        for c in CAMPOS_LINEA:
            if c != "orden_aparicion" and p[kp][c] != r[kr][c]:
                difs.append({"clave": list(kp), "clave_reconstruida": list(kr), "campo": c,
                             "produccion": p[kp][c], "reconstruida": r[kr][c], "id_prod": p[kp].get("id")})
    return quedan_p, [k for k in solo_r if k not in usadas], [[list(a), list(b)] for a, b in pares], difs


def main():
    out = {}
    base_a, base_b = (sys.argv[2], sys.argv[3]) if len(sys.argv) > 3 else ("adif", "adif_reconstruccion")
    for nombre, sql, clave, campos in (
        ("lineas", SQL_LINEAS, ("exp", "lote", "clave"), CAMPOS_LINEA),
        ("lotes", SQL_LOTES, ("exp", "lote"), CAMPOS_LOTE),
        ("expedientes", SQL_EXP, ("exp",), CAMPOS_EXP),
    ):
        p, r = leer(base_a, sql, clave), leer(base_b, sql, clave)
        difs, solo_p, solo_r = comparar(p, r, campos)
        claves_distintas = []
        if nombre == "lineas":
            # Una fila sin código ni matrícula lleva por clave un hash de su
            # descripción y su orden de aparición: si el orden cambia, cambia
            # la clave sin cambiar la fila. Se emparejan por contenido.
            solo_p, solo_r, claves_distintas, difs_contenido = emparejar_por_contenido(p, r, solo_p, solo_r)
            difs += difs_contenido
        out[nombre] = {
            "produccion": len(p), "reconstruida": len(r), "diferencias": difs,
            "solo_produccion": [p[k] for k in solo_p], "solo_reconstruida": [r[k] for k in solo_r],
            "claves_distintas": claves_distintas,
        }
        print(nombre, len(p), len(r), "difs", len(difs), "solo_prod", len(solo_p), "solo_recon", len(solo_r),
              "misma fila con otra clave", len(claves_distintas))
        print("  ", Counter(d["campo"] for d in difs).most_common())
    with open(sys.argv[1], "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, default=str, indent=1)


if __name__ == "__main__":
    main()
