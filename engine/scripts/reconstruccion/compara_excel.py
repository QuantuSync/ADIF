"""Compara dos Excel del catálogo celda a celda (hoja Materiales y las demás).
uso: python compara_excel.py A.xlsx B.xlsx salida.json
Empareja filas dentro de (expediente, lote): primero idénticas, luego por
código de precio, luego por (matrícula, descripción), luego por descripción,
y lo que quede, por orden."""
import json
import sys
from collections import Counter, defaultdict

import openpyxl


def leer(ruta):
    wb = openpyxl.load_workbook(ruta, read_only=True)
    hojas = {}
    for ws in wb.worksheets:
        hojas[ws.title] = [tuple(r) for r in ws.iter_rows(values_only=True)]
    return hojas


def norm(v):
    if isinstance(v, str) and v.strip() == "":
        return None
    if isinstance(v, float) and v == int(v):
        return int(v)
    return v


def comparar_materiales(fa, fb):
    cab = fa[0]
    assert cab == fb[0], (cab, fb[0])
    ix = {c: i for i, c in enumerate(cab)}
    iexp, ilote, icp, imat, idesc = (ix["Código de expediente"], ix["Lote"], ix["Código de precio"],
                                     ix["Matrícula del material"], ix["Descripción del material"])
    ga, gb = defaultdict(list), defaultdict(list)
    for r in fa[1:]:
        r = tuple(norm(v) for v in r)
        ga[(r[iexp], r[ilote])].append(r)
    for r in fb[1:]:
        r = tuple(norm(v) for v in r)
        gb[(r[iexp], r[ilote])].append(r)
    pares, solo_a, solo_b = [], [], []
    for g in sorted(set(ga) | set(gb), key=lambda k: (str(k[0]), str(k[1]))):
        a, b = list(ga.get(g, [])), list(gb.get(g, []))
        # idénticas
        cb = Counter(b)
        resto_a = []
        for r in a:
            if cb[r] > 0:
                cb[r] -= 1
            else:
                resto_a.append(r)
        resto_b = []
        for r in b:
            if cb[r] > 0:
                resto_b.append(r)
                cb[r] -= 1
        # cb ahora lleva las no emparejadas de b: reconstruir
        usados = Counter(a)
        resto_b = []
        for r in b:
            if usados[r] > 0:
                usados[r] -= 1
            else:
                resto_b.append(r)
        for clave in (lambda r: r[icp], lambda r: (r[imat], r[idesc]), lambda r: r[idesc]):
            nuevo_a = []
            for r in resto_a:
                k = clave(r)
                cand = [x for x in resto_b if k is not None and k != (None, None) and clave(x) == k]
                if len(cand) >= 1 and sum(1 for y in resto_a if clave(y) == k) == len(cand) == 1:
                    pares.append((g, r, cand[0]))
                    resto_b.remove(cand[0])
                else:
                    nuevo_a.append(r)
            resto_a = nuevo_a
        n = min(len(resto_a), len(resto_b))
        for r, s in zip(resto_a[:n], resto_b[:n]):
            pares.append((g, r, s))
        solo_a += [(g, r) for r in resto_a[n:]]
        solo_b += [(g, r) for r in resto_b[n:]]
    difs = []
    for g, r, s in pares:
        for i, c in enumerate(cab):
            if r[i] != s[i]:
                difs.append({"expediente": g[0], "lote": g[1], "codigo_precio": r[icp] or s[icp],
                             "descripcion": (r[idesc] or s[idesc] or "")[:120], "columna": c,
                             "a": r[i], "b": s[i]})
    return {
        "filas_a": len(fa) - 1, "filas_b": len(fb) - 1, "pares": len(pares),
        "solo_a": [{"expediente": g[0], "lote": g[1], "fila": dict(zip(cab, r))} for g, r in solo_a],
        "solo_b": [{"expediente": g[0], "lote": g[1], "fila": dict(zip(cab, r))} for g, r in solo_b],
        "diferencias": difs,
    }


def comparar_hoja_plana(fa, fb):
    difs = []
    for i in range(max(len(fa), len(fb))):
        ra = fa[i] if i < len(fa) else ()
        rb = fb[i] if i < len(fb) else ()
        for j in range(max(len(ra), len(rb))):
            va = norm(ra[j]) if j < len(ra) else None
            vb = norm(rb[j]) if j < len(rb) else None
            if va != vb:
                difs.append({"fila": i + 1, "col": j + 1, "a": va, "b": vb,
                             "clave": [norm(x) for x in (ra[:2] or rb[:2])]})
    return {"filas_a": len(fa), "filas_b": len(fb), "diferencias": difs}


def main():
    a, b = leer(sys.argv[1]), leer(sys.argv[2])
    out = {"hojas_a": list(a), "hojas_b": list(b)}
    out["Materiales"] = comparar_materiales(a["Materiales"], b["Materiales"])
    for h in a:
        if h != "Materiales" and h in b:
            out[h] = comparar_hoja_plana(a[h], b[h])
    with open(sys.argv[3], "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, default=str, indent=1)
    m = out["Materiales"]
    print("Materiales:", m["filas_a"], "vs", m["filas_b"], "pares", m["pares"], "solo_a", len(m["solo_a"]),
          "solo_b", len(m["solo_b"]), "celdas distintas", len(m["diferencias"]))
    print(" por columna:", Counter(d["columna"] for d in m["diferencias"]).most_common())
    for h in a:
        if h != "Materiales" and h in b:
            print(h, out[h]["filas_a"], out[h]["filas_b"], "celdas distintas", len(out[h]["diferencias"]))


if __name__ == "__main__":
    main()
