"""La partida alzada del lote que la tabla no llega a leer (sesión 2026-09-21,
tercera parte, bloque 3 del encargo: las líneas que faltan).

El caso real, medido contra el documento: el cuadro de un lote termina con su
partida alzada ("PARTIDA ALZADA A JUSTIFICAR PARA IMPREVISTOS … 8.987,26 €"),
pero esa fila no llega a ser línea porque la tabla la deja fuera -- una tabla
de una sola fila en lo alto de la página siguiente, que la cascada descarta
por espuria (`6.20/28510.0094` lote 2, ANEJO_3.pdf p.5), o una subcabecera
"DESCRIPCIÓN | PRECIO UNITARIO" justo encima que corta la lectura
(`6.20/28510.0131` lote 1, ANEJO_3.pdf p.4). El lote se queda sin ella y no
cuadra con su presupuesto por exactamente su importe.

**Condición del cliente: una línea recuperada solo entra si con ella el lote
cuadra con su presupuesto publicado.** Por eso aquí no se busca "la partida
alzada del lote", se busca **la única fila de partida alzada de las páginas
del propio lote cuyo importe es, al céntimo, lo que le falta al lote para su
presupuesto**. Con ella el lote cuadra por construcción; sin una candidata
única, no entra nada. Nunca se inventa la cifra: sale del texto del
documento, con su página y su línea literal como fragmento, y la línea va
marcada (`MOTIVO_PARTIDA_ALZADA_RECUPERADA`).

Qué páginas son las del lote: las de sus líneas en este documento y la
siguiente a la última (la tabla de una fila en lo alto de la página que
sigue). Qué suma el lote: cantidad × precio de sus líneas de este documento, y
una partida alzada sin cantidad una vez por su importe -- la misma cuenta que
el contraste de presupuestos.
"""
from __future__ import annotations

import re
from decimal import Decimal
from typing import Optional

from app.catalogo import construir_linea_catalogo
from app.celdas_vacias import es_partida_alzada
from app.extraccion.normalizacion import parsear_importe_es
from app.extraccion.texto import PaginaTexto

MOTIVO_PARTIDA_ALZADA_RECUPERADA = (
    "partida alzada del lote leída del texto del documento (la tabla no llegó a leerla): su importe es "
    "exactamente lo que le faltaba al lote para su presupuesto de licitación publicado"
)
MARCA_FRAGMENTO = "[partida alzada recuperada del texto del cuadro]"

# La fila en el texto de la página: el renglón que abre con "Partida alzada" y
# el primer importe en ese renglón o en los `_RENGLONES_DE_LA_FILA` siguientes.
# La celda de la descripción puede partirse en varios renglones y la cifra
# caer en cualquiera de ellos ("PARTIDA ALZADA A JUSTIFICAR PARA IMPREVISTOS" /
# "8.987,26 €", `6.20/28510.0094` p.5; "… de la misma naturaleza" /
# "2.866,30 €" / "que las cubiertas …", `6.20/28510.0131` p.6).
_INICIO_PARTIDA_ALZADA_RE = re.compile(r"^\s*partida\s+alzada\b", re.IGNORECASE)
_IMPORTE_EN_RENGLON_RE = re.compile(r"(?<![\d.,])(\d{1,3}(?:\.\d{3})*,\d{2})\s*€")
_RENGLONES_DE_LA_FILA = 3
_MAPEO = {
    "codigo_precio": None, "matricula": None, "descripcion": 0, "codigo_material": None,
    "cantidad": None, "precio_unitario": 1, "unidad_medida": None,
}


def _importe(linea: dict) -> Decimal:
    cantidad, precio = linea.get("cantidad"), linea.get("precio_unitario")
    if not isinstance(precio, Decimal):
        return Decimal("0")
    if isinstance(cantidad, Decimal):
        return cantidad * precio
    return precio if es_partida_alzada(linea.get("descripcion")) else Decimal("0")


def suma_del_lote_como_el_catalogo(del_lote: list[dict]) -> Decimal:
    """La suma del lote tal como quedará en el catálogo: el mismo material que
    el documento imprime dos veces (el cuadro repetido en el anejo y en el
    contrato, o en dos páginas) se funde por su firma (matrícula, descripción,
    precio) y cuenta una vez; lo que no tiene firma cuenta cada vez."""
    from app.catalogo import _firma_material

    vistas: set = set()
    suma = Decimal("0")
    for linea in del_lote:
        firma = _firma_material(linea)
        if firma is not None:
            if firma in vistas:
                continue
            vistas.add(firma)
        suma += _importe(linea)
    return suma


def _candidatas(paginas_texto: list[PaginaTexto], numeros: set[int], falta: Decimal) -> set[tuple[int, str, str]]:
    encontradas: set[tuple[int, str, str]] = set()
    for pagina in paginas_texto:
        if pagina.numero not in numeros:
            continue
        renglones = (pagina.texto or "").splitlines()
        for i, renglon in enumerate(renglones):
            if not _INICIO_PARTIDA_ALZADA_RE.match(renglon):
                continue
            for j in range(i, min(i + _RENGLONES_DE_LA_FILA + 1, len(renglones))):
                if j > i and _INICIO_PARTIDA_ALZADA_RE.match(renglones[j]):
                    break
                cifras = _IMPORTE_EN_RENGLON_RE.findall(renglones[j])
                if not cifras:
                    continue
                if len(cifras) == 1:
                    try:
                        importe = parsear_importe_es(cifras[0])
                    except ValueError:
                        break
                    if importe == falta:
                        texto = " ".join(renglones[i:j] + [_IMPORTE_EN_RENGLON_RE.sub("", renglones[j])])
                        encontradas.add((pagina.numero, re.sub(r"\s+", " ", texto).strip(), cifras[0]))
                break
    return encontradas


MOTIVO_FILA_RECUPERADA = (
    "fila del cuadro que la lectura de la tabla dejaba fuera, recuperada: con ella el lote suma exactamente su "
    "presupuesto de licitación publicado"
)
_TOLERANCIA = Decimal("0.01")


_MAX_RECUPERADAS_POR_LOTE = 8


def _unico_subconjunto_que_cuadra(
    lineas: list[dict], identificador: Optional[str], recuperadas: list[dict], presupuesto: Optional[Decimal]
) -> Optional[list[dict]]:
    """Las recuperadas del lote con las que el lote cuadra: todas, si con todas
    cuadra; si no, el ÚNICO subconjunto no vacío que lo hace (una fila de la
    otra copia del cuadro que ya estaba leída no suma nada nuevo, y la
    recuperación de verdad es la otra). Con dos subconjuntos que cuadran no se
    elige ninguno: `None`."""
    if presupuesto is None or identificador is None:
        return None
    ids = {id(l) for l in recuperadas}
    base = [l for l in lineas if l.get("identificador_lote") == identificador and id(l) not in ids]

    def cuadra(elegidas: list[dict]) -> bool:
        return abs(suma_del_lote_como_el_catalogo(base + elegidas) - Decimal(presupuesto)) <= _TOLERANCIA

    if cuadra(recuperadas):
        return recuperadas
    if len(recuperadas) > _MAX_RECUPERADAS_POR_LOTE:
        return None
    from itertools import combinations

    validos = [
        list(c) for n in range(1, len(recuperadas)) for c in combinations(recuperadas, n) if cuadra(list(c))
    ]
    return validos[0] if len(validos) == 1 else None


def descartar_recuperadas_que_no_cuadran(
    lineas: list[dict], presupuestos_por_lote: dict[str, Optional[Decimal]]
) -> tuple[list[dict], list[str]]:
    """Condición del cliente para el bloque 3 del encargo: una línea recuperada
    (`recuperada_que_falta`, marca transitoria) solo entra si con ella su lote
    cuadra con su presupuesto publicado. Sin presupuesto no hay con qué
    comprobarlo y no entra. Devuelve (líneas que se quedan, motivos)."""
    marcadas = [l for l in lineas if l.pop("recuperada_que_falta", False)]
    if not marcadas:
        return lineas, []
    fuera: set[int] = set()
    motivos: list[str] = []
    for identificador in sorted({l.get("identificador_lote") for l in marcadas}, key=str):
        grupo = [l for l in marcadas if l.get("identificador_lote") == identificador]
        presupuesto = presupuestos_por_lote.get(identificador) if identificador is not None else None
        subconjunto = _unico_subconjunto_que_cuadra(lineas, identificador, grupo, presupuesto)
        if subconjunto is not None:
            elegidas = {id(l) for l in subconjunto}
            fuera.update(id(l) for l in grupo if id(l) not in elegidas)
            grupo = subconjunto
            for linea in grupo:
                linea["motivo_revision"] = (
                    f"{linea['motivo_revision']}; {MOTIVO_FILA_RECUPERADA}"
                    if linea.get("motivo_revision") else MOTIVO_FILA_RECUPERADA
                )
            motivos.append(
                f"LOTE {identificador}: {len(grupo)} fila(s) recuperada(s) del cuadro -- con ellas "
                f"el lote suma exactamente su presupuesto ({Decimal(presupuesto):.2f} €)"
            )
            continue
        fuera.update(id(l) for l in grupo)
        motivos.append(
            f"LOTE {identificador}: {len(grupo)} fila(s) del cuadro no se recuperan porque con "
            f"ellas el lote no cuadra con su presupuesto publicado"
        )
    return [l for l in lineas if id(l) not in fuera], motivos


def recuperar_partidas_alzadas_que_cierran_el_lote(
    lineas: list[dict],
    paginas_texto: list[PaginaTexto],
    presupuestos_por_lote: dict[str, Optional[Decimal]],
    documento_origen_id: Optional[int],
    expediente_id: int,
    bajas_por_lote: dict[str, Optional[Decimal]],
) -> list[str]:
    """Añade a `lineas` las partidas alzadas recuperadas y devuelve un motivo
    por cada una (para el resumen del documento)."""
    motivos: list[str] = []
    for identificador, presupuesto in sorted(presupuestos_por_lote.items(), key=lambda kv: str(kv[0])):
        if presupuesto is None:
            continue
        del_lote = [l for l in lineas if l.get("identificador_lote") == identificador]
        if not del_lote:
            continue
        falta = Decimal(presupuesto) - suma_del_lote_como_el_catalogo(del_lote)
        if falta <= 0:
            continue
        # Una partida alzada con ese mismo importe ya leída en el lote no se
        # repite: la que falta sería otra, y no hay con qué distinguirla.
        if any(es_partida_alzada(l.get("descripcion")) and l.get("precio_unitario") == falta for l in del_lote):
            continue
        paginas = {l["pagina"] for l in del_lote if l.get("pagina") is not None}
        if not paginas:
            continue
        candidatas = _candidatas(paginas_texto, paginas | {max(paginas) + 1}, falta)
        # La misma fila puede verse en el texto de dos páginas solo si son dos
        # filas: con más de una candidata no se elige ninguna.
        if len({(texto, importe) for _, texto, importe in candidatas}) != 1 or len(candidatas) != 1:
            continue
        numero, texto, importe = next(iter(candidatas))
        linea = construir_linea_catalogo(
            [texto, importe], _MAPEO, numero, documento_origen_id, expediente_id,
            bajas_por_lote.get(identificador), max(l.get("orden_aparicion", 0) for l in lineas) + 1,
        )
        if linea is None or linea.get("precio_unitario") != falta:
            continue
        linea["identificador_lote"] = identificador
        linea["clave_huerfana_hipotetica"] = f"{linea['clave_linea']}@p{numero}pa"
        linea["motivo_revision"] = (
            f"{linea['motivo_revision']}; {MOTIVO_PARTIDA_ALZADA_RECUPERADA}"
            if linea.get("motivo_revision") else MOTIVO_PARTIDA_ALZADA_RECUPERADA
        )
        linea["fragmento"] = f"{MARCA_FRAGMENTO} {linea.get('fragmento') or ''}".strip()
        lineas.append(linea)
        motivos.append(
            f"LOTE {identificador}: partida alzada de {importe} € recuperada del texto de la p.{numero} -- con ella "
            f"el lote suma exactamente su presupuesto ({Decimal(presupuesto):.2f} €)"
        )
    return motivos
