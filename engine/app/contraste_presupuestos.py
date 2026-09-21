"""Hoja "Contraste de presupuestos" del Excel, y su vista en la web: la suma de
cantidad × precio de las filas de cada lote contra el presupuesto de licitación
que la Plataforma publica para ese lote.

Bloque 1, sesión 2026-09-21. **El cliente preguntó dónde podía ver la
comprobación** que hicimos en la sesión 2026-09-18 (sexta parte) sobre 70
tablas de lote, y que solo vivía en nuestros registros. Aquí pasa a ser parte
del sistema, y para **todo lote con filas en "Materiales" que tenga un
presupuesto publicado con el que compararlo**, no solo aquellos 70.

**Las filas que se suman son exactamente las de "Materiales".** El Excel le
pasa las que acaba de escribir; la web, las de la misma consulta con los mismos
filtros (`lineas_de_materiales_por_lote`). Si pudieran ser otras, la hoja
compararía un catálogo que nadie ve.

**Contra qué cifra se compara, y cómo se sabe qué cifra es.** Un presupuesto
publicado puede ser la base de licitación sin IVA, la misma con IVA o el
presupuesto de ejecución material (sin gastos generales ni beneficio
industrial). Los precios de un cuadro son siempre sin IVA, así que la cifra
equivalente es la base sin IVA, con una excepción demostrada por la
aritmética: si la suma **multiplicada por 1,15 da la base sin IVA a un
céntimo**, el cuadro está a precios de ejecución material y la base le suma un
15 % de gastos generales y beneficio industrial. El céntimo es el del redondeo:
el documento redondea los dos por separado (`6.17/28510.0056`, lote 1:
2.975.673,96 € + 267.810,66 € del 9 % + 178.540,44 € del 6 % =
3.422.025,06 €, el importe sin impuestos que publica la Plataforma; ×1,15 de
una vez daría 3.422.025,05). Entonces se compara con la ejecución material
que **declara el propio documento** si alguno la declara con esa relación
(`app.extraccion.presupuesto_lote`, redacción ``ejecucion_material``), y si no,
con la base ÷ 1,15. El tipo de cifra publicada sale siempre **de la etiqueta
con la que se publica**, nunca de que la cuenta salga:

- el anuncio de la Plataforma escribe las dos cifras ("Importe 9.922.000 EUR.
  Importe (sin impuestos) 8.200.000 EUR");
- el Contrato, "(IVA excluido)"; la lista de lotes del pliego, "sin IVA";
- la propuesta LC.27, "Presupuesto de licitación: X € Y € Z €" bajo las
  columnas Base imponible / IVA / Total con IVA: la primera es la base
  (comprobado en las 95 del corpus: en 93 la base más el IVA da el total al
  céntimo; en las otras 2 es la misma tabla con un "€" o un dígito partido);
- la sindicación de la Plataforma, sus dos campos "sin impuestos" y "con
  impuestos".

Si la etiqueta no es ninguna de esas, la fila **lo dice** ("No se puede saber
con certeza...") en vez de suponerlo, y se compara igual.

**De dónde sale el presupuesto de cada lote**, por este orden: el que el
sistema ya guarda para el lote (`Lote.importe_licitacion`) con su traza; el
que publican sus documentos para ese lote
(`app.extraccion.presupuesto_lote`); el de la sindicación para ese lote; y,
**solo si el expediente es de un único lote**, el del expediente entero. Un
lote cuyo "1" lo puso el sistema (el expediente no declara lotes) no es el
"Lote 1" de la licitación: para él solo vale la cifra del expediente.

**Qué lotes no entran, y por qué** (se cuentan en la hoja y en la web):
los que no tienen ningún presupuesto publicado para el lote; los de un
expediente de varios lotes que solo publica el total; aquellos cuyos
documentos dan cifras distintas para el mismo lote; y los pedidos cuyas líneas
son el cuadro heredado de su acuerdo marco, porque ese cuadro es el del
acuerdo marco y no tiene nada que ver con el presupuesto del pedido.

**Nada de esto cambia el catálogo.** Es una comprobación de solo lectura.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field, replace
from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.catalogo_consulta import filtros_del_entregable
from app.celdas_vacias import es_partida_alzada
from app.models import (
    DocumentoExpediente,
    Expediente,
    LineaCatalogo,
    Lote,
    PresupuestoLoteDocumento,
    SindicacionExpediente,
    TrazaOrigen,
)

NOMBRE_HOJA = "Contraste de presupuestos"

CUADRA_AL_CENTIMO = "Cuadra al céntimo"
CUADRA_MENOS_001 = "Cuadra con diferencia menor del 0,01 %"
NO_CUADRA = "No cuadra"
FALTAN_CANTIDADES = "No se puede cerrar: faltan cantidades"
RESULTADOS = (CUADRA_AL_CENTIMO, CUADRA_MENOS_001, NO_CUADRA, FALTAN_CANTIDADES)

BASE_SIN_IVA = "Presupuesto base de licitación sin IVA"
BASE_CON_IVA = "Presupuesto base de licitación con IVA"
EJECUCION_MATERIAL = (
    "Presupuesto base de licitación sin IVA; se compara con su ejecución material (sin el 15 % de "
    "gastos generales y beneficio industrial)"
)
COMPARADO_CON_IVA = "Presupuesto base de licitación con IVA (los precios del cuadro lo incluyen)"
INCIERTO = "No se puede saber con certeza"

# Por qué un lote con filas en "Materiales" no tiene fila en el contraste.
SIN_PRESUPUESTO = "Ningún documento ni la sindicación publican presupuesto para este lote"
SOLO_TOTAL_DEL_EXPEDIENTE = (
    "El expediente tiene varios lotes y solo se publica el presupuesto del conjunto, no el de este lote"
)
CIFRAS_DISTINTAS = "Sus documentos publican cifras distintas para este lote y no se elige ninguna"
CUADRO_HEREDADO = (
    "Sus líneas son el cuadro del acuerdo marco del que cuelga: se comparan en la fila del acuerdo "
    "marco, no contra el presupuesto del pedido"
)
MOTIVOS_FUERA = (SIN_PRESUPUESTO, SOLO_TOTAL_DEL_EXPEDIENTE, CIFRAS_DISTINTAS, CUADRO_HEREDADO)

COLUMNAS = (
    "Código de expediente",
    "Lote",
    "Presupuesto publicado",
    "Qué cifra es",
    "Cifra con la que se compara",
    "Documento",
    "Página",
    "Suma de sus líneas (cantidad × precio)",
    "Diferencia (€)",
    "Diferencia (%)",
    "Líneas",
    "Líneas sin cantidad",
    "Resultado",
    "Explicación",
)

# `app.extraccion.orquestador.LOTE_UNICO`: el lote que el sistema crea cuando
# el expediente no declara ninguno. Se copia en vez de importarse para no
# arrastrar el orquestador entero a la exportación.
_LOTE_UNICO = "1"
_CENTIMO = Decimal("0.01")
_GASTOS_Y_BENEFICIO = Decimal("1.15")
_UMBRAL_CASI = Decimal("0.0001")  # 0,01 %

# Verificados a mano contra el documento en la sesión 2026-09-18 (sexta parte,
# `docs/sesion-2026-09-18-verificacion-del-reparto-por-lotes.md`, bloque 1) y
# en la 2026-09-19. Clave: expediente, lote y las dos cifras que se
# comprobaron. **Si la suma o el presupuesto de hoy no son esas cifras, el
# texto no se escribe**: explicaría otra cosa.
_TRAVIESAS_LOTE_3 = (
    "Comprobado a mano contra el documento (sesión 2026-09-18): la discrepancia es del propio "
    "documento de ADIF, no de la lectura. Las cantidades raras del cuadro (2408, 2392, 1999, 2001, "
    "2250, 2501...) están así en el ANEJO_8.pdf fila a fila: son el ajuste con el que ADIF hace caer "
    "cada cuadro sobre su presupuesto, y en el lote 3 no cierra: sus filas de material suman "
    "30.002,23 € más que el 97 % del presupuesto que les corresponde, mientras su partida alzada de "
    "imprevistos sigue siendo el 3 % "
    "exacto del presupuesto del lote (245.999,90 / 8.200.000). El cuadro del lote 3 se pasa de su "
    "propio presupuesto en el documento original. El presupuesto lo publican igual el anuncio, el "
    "ANEJO_1.pdf p.4, el ANEJO_2.pdf p.4 y los dos Contratos (p.103)."
)
_TRAVIESAS_LOTE_4 = (
    "Comprobado a mano contra el documento (sesión 2026-09-18): los 1,60 € están en el propio "
    "ANEJO_8.pdf. El ajuste de cantidades con el que ADIF hace caer el cuadro sobre su presupuesto "
    "se quedó a 1,60 €; la partida alzada es el 3 % exacto del presupuesto del lote "
    "(215.999,16 / 7.200.000)."
)
_COMPROBADO_A_MANO: dict[tuple[str, str, Decimal, Decimal], str] = {
    **{
        (f"6.20/28510.00{n}", "3", Decimal("8230002.13"), Decimal("8200000.00")): _TRAVIESAS_LOTE_3
        for n in ("54", "55", "56", "57", "58")
    },
    **{
        (f"6.20/28510.00{n}", "4", Decimal("7200001.60"), Decimal("7200000.00")): _TRAVIESAS_LOTE_4
        for n in ("54", "55", "56", "57", "58")
    },
    ("6.22/28510.0094", "1", Decimal("5899901.11"), Decimal("5900000.00")): (
        "Comprobado a mano contra el documento (sesión 2026-09-18): los −98,89 € son los 98,88 € de "
        "diferencia en el precio de P-002, que el anejo de criterios técnicos (ANEJO_3.pdf, sin columna "
        "de cantidad) publica distinto del cuadro de precios del lote."
    ),
    ("6.17/28510.0056", "1", Decimal("2975673.96"), Decimal("2975673.96")): (
        "Comprobado a mano contra el documento (sesión 2026-09-18): 2.975.673,96 € es el Presupuesto de "
        "Ejecución Material que declara el propio documento, y ×1,15 (9 % de gastos generales y 6 % de "
        "beneficio industrial) da exactamente el importe sin impuestos del lote 1. Cuadra desde que el "
        "precio de P-7, que el reconocimiento óptico leyó 56.555,91 € donde el PDF pone 56.455,91 €, se "
        "corrigió desde la columna de importes del propio documento (sesión 2026-09-19)."
    ),
}


@dataclass(frozen=True)
class FilaContraste:
    codigo_expediente: str
    lote: str
    presupuesto_publicado: Decimal
    tipo_cifra: str
    cifra_comparada: Decimal
    documento: Optional[str]
    pagina: Optional[int]
    suma_lineas: Decimal
    diferencia: Decimal
    diferencia_relativa: Optional[Decimal]
    lineas: int
    lineas_sin_cantidad: int
    resultado: str
    explicacion: str


@dataclass(frozen=True)
class LoteFuera:
    codigo_expediente: str
    lote: str
    lineas: int
    motivo: str


@dataclass
class Contraste:
    filas: list[FilaContraste] = field(default_factory=list)
    fuera: list[LoteFuera] = field(default_factory=list)

    def por_resultado(self) -> dict[str, int]:
        conteo = Counter(f.resultado for f in self.filas)
        return {r: conteo.get(r, 0) for r in RESULTADOS}

    def por_motivo_fuera(self) -> dict[str, int]:
        conteo = Counter(f.motivo for f in self.fuera)
        return {m: conteo.get(m, 0) for m in MOTIVOS_FUERA}


@dataclass(frozen=True)
class _Presupuesto:
    sin_iva: Decimal
    con_iva: Optional[Decimal]
    tipo: str  # BASE_SIN_IVA, o INCIERTO + ": motivo"
    documento: Optional[str]
    pagina: Optional[int]
    # Las ejecuciones materiales que declaran los documentos del expediente:
    # (importe, documento, página). Solo se usan si la aritmética las liga.
    ejecucion_material: tuple = ()


def _cent(valor: Decimal) -> Decimal:
    return Decimal(valor).quantize(_CENTIMO, rounding=ROUND_HALF_UP)


def _euros(valor: Decimal) -> str:
    texto = f"{_cent(valor):,.2f}"
    return texto.replace(",", "_").replace(".", ",").replace("_", ".") + " €"


def _porcentaje(valor: Decimal, decimales: int = 2) -> str:
    return f"{valor * 100:.{decimales}f} %".replace(".", ",")


def _periodo_legible(periodo: str) -> str:
    if len(periodo) == 6 and periodo.isdigit():
        return f"{periodo[4:]}/{periodo[:4]}"
    return periodo


def _con_iva_del_anuncio(fragmento: str) -> Optional[Decimal]:
    import re

    from app.extraccion.normalizacion import parsear_importe_es

    m = re.search(r"Importe\s+([\d.]+(?:,\d+)?)\s*EUR", fragmento, re.IGNORECASE)
    if not m:
        return None
    try:
        return parsear_importe_es(m.group(1))
    except (ValueError, ArithmeticError):
        return None


def _tipo_por_fragmento(fragmento: Optional[str]) -> tuple[str, Optional[Decimal]]:
    """El tipo de cifra que dice la etiqueta con la que se publicó, y la
    cifra con IVA si el mismo fragmento la trae. Nunca por la cuenta."""
    texto = (fragmento or "").lower()
    if "(sin impuestos)" in texto:
        return BASE_SIN_IVA, _con_iva_del_anuncio(fragmento or "")
    if "iva excluido" in texto or "sin iva" in texto or "imponible" in texto:
        return BASE_SIN_IVA, None
    if texto.startswith("presupuesto de licitación:") or texto.startswith("presupuesto de licitacion:"):
        # Propuesta LC.27: la primera cifra de "Base imponible / IVA / Total
        # con IVA" (ver docstring del módulo).
        return BASE_SIN_IVA, None
    return f"{INCIERTO}: la etiqueta con la que se publicó no dice si lleva IVA", None


def lineas_de_materiales_por_lote(db: Session) -> dict[int, list[LineaCatalogo]]:
    """Las líneas que `app.exportacion.generar_excel_catalogo` escribe en
    "Materiales", agrupadas por lote. Mismos filtros
    (`filtros_del_entregable`) y mismo criterio de inclusión
    (`linea_sale_en_materiales`): así la vista de la web suma lo mismo que la
    hoja del Excel."""
    from app.exportacion import linea_sale_en_materiales

    por_lote: dict[int, list[LineaCatalogo]] = defaultdict(list)
    for linea in db.execute(filtros_del_entregable(select(LineaCatalogo))).scalars():
        # `linea_sale_en_materiales` solo mira si hay lote, no cuál.
        if linea.lote_id is not None and linea_sale_en_materiales(linea, linea.lote_id):
            por_lote[linea.lote_id].append(linea)
    return por_lote


class _Fuentes:
    """Todo lo que hace falta leer de la base de datos, en cinco consultas
    para el corpus entero, no por lote."""

    def __init__(self, db: Session, expediente_ids: set[int]):
        self.lotes_por_expediente: dict[int, list[Lote]] = defaultdict(list)
        for lote in db.execute(select(Lote).where(Lote.expediente_id.in_(expediente_ids))).scalars():
            self.lotes_por_expediente[lote.expediente_id].append(lote)
        self.trazas: dict[tuple[str, int], TrazaOrigen] = {}
        for traza in db.execute(
            select(TrazaOrigen).where(TrazaOrigen.campo == "importe_licitacion").order_by(TrazaOrigen.id)
        ).scalars():
            self.trazas[(traza.entidad_tipo, traza.entidad_id)] = traza  # la última
        self.documentales: dict[tuple[int, str], list[PresupuestoLoteDocumento]] = defaultdict(list)
        self.ejecucion_material: dict[int, list[PresupuestoLoteDocumento]] = defaultdict(list)
        for p in db.execute(
            select(PresupuestoLoteDocumento)
            .where(PresupuestoLoteDocumento.expediente_id.in_(expediente_ids))
            .order_by(PresupuestoLoteDocumento.id)
        ).scalars():
            if p.identificador_lote is None:
                self.ejecucion_material[p.expediente_id].append(p)
            else:
                self.documentales[(p.expediente_id, p.identificador_lote)].append(p)
        self.sindicacion: dict[int, SindicacionExpediente] = {
            s.expediente_id: s
            for s in db.execute(
                select(SindicacionExpediente).where(SindicacionExpediente.expediente_id.in_(expediente_ids))
            ).scalars()
        }
        self.nombres: dict[tuple[int, int], str] = {}
        self.nombre_cualquiera: dict[int, str] = {}
        for de in db.execute(select(DocumentoExpediente)).scalars():
            self.nombres[(de.documento_id, de.expediente_id)] = de.nombre_archivo
            self.nombre_cualquiera.setdefault(de.documento_id, de.nombre_archivo)

    def nombre(self, documento_id: int, expediente_id: int) -> str:
        return self.nombres.get((documento_id, expediente_id)) or self.nombre_cualquiera.get(
            documento_id, f"documento {documento_id}"
        )


def _es_lote_del_sistema(lote: Lote, lotes_del_expediente: list[Lote]) -> bool:
    """El "1" que pone el sistema cuando el expediente no declara lotes: no es
    el "Lote 1" de la licitación, y leerle el presupuesto del "Lote 1" de un
    documento compartido le daría el de otro expediente (medido: 6 casos)."""
    return (
        lote.identificador_lote == _LOTE_UNICO
        and len(lotes_del_expediente) == 1
        and not lote.codigo_expediente_lote
    )


def _presupuesto_del_lote(
    fuentes: _Fuentes, expediente: Expediente, lote: Lote
) -> tuple[Optional[_Presupuesto], Optional[str]]:
    """El presupuesto publicado de ESTE lote, o el motivo de no tenerlo, con
    las ejecuciones materiales que declaran los documentos del expediente."""
    presupuesto, motivo = _presupuesto_publicado(fuentes, expediente, lote)
    if presupuesto is None:
        return None, motivo
    declaradas = tuple(
        (Decimal(p.importe), fuentes.nombre(p.documento_id, expediente.id), p.pagina)
        for p in fuentes.ejecucion_material.get(expediente.id, [])
    )
    return replace(presupuesto, ejecucion_material=declaradas), None


def _presupuesto_publicado(
    fuentes: _Fuentes, expediente: Expediente, lote: Lote
) -> tuple[Optional[_Presupuesto], Optional[str]]:
    lotes = fuentes.lotes_por_expediente.get(expediente.id, [lote])
    del_sistema = _es_lote_del_sistema(lote, lotes)

    # 1. El que el sistema ya guarda para el lote, con su traza.
    guardado = Decimal(lote.importe_licitacion) if lote.importe_licitacion is not None else None
    if guardado is not None:
        traza = fuentes.trazas.get(("lote", lote.id))
        if traza is None and len(lotes) == 1 and expediente.importe_licitacion == lote.importe_licitacion:
            traza = fuentes.trazas.get(("expediente", expediente.id))
        if traza is not None:
            tipo, con_iva = _tipo_por_fragmento(traza.fragmento)
            return _Presupuesto(
                guardado, con_iva, tipo, fuentes.nombre(traza.documento_id, expediente.id), traza.pagina,
            ), None

    if not del_sistema:
        # 2. La que publican sus documentos para ese lote. Si el sistema ya
        # guarda una cifra sin traza, solo vale la aparición que dice esa
        # misma cifra: entonces es la que demuestra qué cifra es.
        documentales = [
            p for p in fuentes.documentales.get((expediente.id, lote.identificador_lote), [])
            if guardado is None or _cent(p.importe) == _cent(guardado)
        ]
        if documentales:
            if len({_cent(p.importe) for p in documentales}) > 1:
                return None, CIFRAS_DISTINTAS
            orden = {"anuncio": 0, "contrato": 1, "lista_sin_iva": 2}
            elegido = min(documentales, key=lambda p: (orden.get(p.redaccion, 9), p.id))
            con_iva = next((p.importe_con_iva for p in documentales if p.importe_con_iva is not None), None)
            return _Presupuesto(
                Decimal(elegido.importe), con_iva, BASE_SIN_IVA,
                fuentes.nombre(elegido.documento_id, expediente.id), elegido.pagina,
            ), None
        # 3. La de la sindicación para ese lote (con la misma condición).
        sindicacion = fuentes.sindicacion.get(expediente.id)
        for entrada in (sindicacion.lotes or []) if sindicacion else []:
            identificador = str(entrada.get("identificador") or "")
            if identificador.isdigit() and str(int(identificador)) == lote.identificador_lote:
                sin_iva = entrada.get("importe_licitacion_sin_impuestos")
                if sin_iva and (guardado is None or _cent(Decimal(str(sin_iva))) == _cent(guardado)):
                    con_iva = entrada.get("importe_licitacion_con_impuestos")
                    return _Presupuesto(
                        Decimal(str(sin_iva)), Decimal(str(con_iva)) if con_iva else None, BASE_SIN_IVA,
                        f"Sindicación de la Plataforma (boletín {_periodo_legible(sindicacion.periodo_zip)})",
                        None,
                    ), None

    if guardado is not None:
        # Una cifra que el sistema guarda y que no se puede ligar a ninguna
        # etiqueta publicada: se compara, pero la fila dice que no se sabe
        # qué cifra es.
        return _Presupuesto(
            guardado, None,
            f"{INCIERTO}: el sistema guarda esta cifra sin la traza del documento que la publica",
            None, None,
        ), None

    if len(lotes) == 1:
        # 4. Expediente de un único lote: su presupuesto es el del expediente.
        if expediente.importe_licitacion is not None:
            traza = fuentes.trazas.get(("expediente", expediente.id))
            if traza is not None:
                tipo, con_iva = _tipo_por_fragmento(traza.fragmento)
                return _Presupuesto(
                    Decimal(expediente.importe_licitacion), con_iva, tipo,
                    fuentes.nombre(traza.documento_id, expediente.id), traza.pagina,
                ), None
        sindicacion = fuentes.sindicacion.get(expediente.id)
        if sindicacion is not None and sindicacion.importe_licitacion_sin_impuestos:
            con_iva = sindicacion.importe_licitacion_con_impuestos
            return _Presupuesto(
                Decimal(sindicacion.importe_licitacion_sin_impuestos),
                Decimal(con_iva) if con_iva else None, BASE_SIN_IVA,
                f"Sindicación de la Plataforma (boletín {_periodo_legible(sindicacion.periodo_zip)})", None,
            ), None
        return None, SIN_PRESUPUESTO

    if expediente.importe_licitacion is not None:
        return None, SOLO_TOTAL_DEL_EXPEDIENTE
    return None, SIN_PRESUPUESTO


def _es_ejecucion_material_de(importe: Decimal, base: Decimal) -> bool:
    """`importe` × 1,15 = `base`, a un céntimo como mucho: el que sale de
    redondear por separado los gastos generales y el beneficio industrial."""
    return importe > 0 and abs(importe * _GASTOS_Y_BENEFICIO - base) <= _CENTIMO


def _porcentaje_exacto(suma: Decimal, presupuesto: Decimal) -> Optional[int]:
    """Si la suma es, al céntimo, un porcentaje entero del presupuesto (el
    90 %, el 97 %...), cuál. Es un hecho aritmético, no una explicación: se
    escribe para que quien revise el lote tenga por dónde empezar."""
    if presupuesto <= 0:
        return None
    candidato = int((suma * 100 / presupuesto).to_integral_value(rounding=ROUND_HALF_UP))
    if 0 < candidato < 1000 and candidato != 100 and _cent(presupuesto * candidato / 100) == suma:
        return candidato
    return None


def _comparar(
    expediente: Expediente, lote: Lote, lineas: list[LineaCatalogo], presupuesto: _Presupuesto,
    lineas_fuera_de_materiales: int = 0,
) -> FilaContraste:
    suma = Decimal("0")
    sin_cantidad = sin_precio = partidas_una_vez = 0
    for linea in lineas:
        if linea.precio_unitario is None:
            sin_precio += 1
            if linea.cantidad is None:
                sin_cantidad += 1
            continue
        if linea.cantidad is None:
            if es_partida_alzada(linea.descripcion):
                # Una partida alzada es cantidad 1 por definición (CONTEXTO.md
                # sección 2): su importe cuenta una vez. Así se contó también
                # en la verificación del 2026-09-18.
                suma += Decimal(linea.precio_unitario)
                partidas_una_vez += 1
            else:
                sin_cantidad += 1
            continue
        suma += Decimal(linea.cantidad) * Decimal(linea.precio_unitario)
    suma = _cent(suma)
    base = _cent(presupuesto.sin_iva)
    con_iva = _cent(presupuesto.con_iva) if presupuesto.con_iva is not None else None
    incierto = presupuesto.tipo.startswith(INCIERTO)

    tipo, cifra = presupuesto.tipo, base
    explicacion: list[str] = []
    if sin_cantidad or sin_precio:
        resultado = FALTAN_CANTIDADES
        faltan = []
        if sin_cantidad:
            faltan.append(f"{sin_cantidad} sin cantidad")
        if sin_precio:
            faltan.append(f"{sin_precio} sin precio unitario")
        explicacion.append(
            f"De sus {len(lineas)} líneas, {' y '.join(faltan)} en el documento: la suma de las demás es "
            f"{_euros(suma)} y sin esos datos no se puede cerrar contra el presupuesto."
        )
    elif suma == base:
        resultado = CUADRA_AL_CENTIMO
        explicacion.append(f"La suma de sus {len(lineas)} líneas es exactamente el presupuesto publicado.")
    elif con_iva is not None and suma == con_iva and not incierto:
        resultado, tipo, cifra = CUADRA_AL_CENTIMO, COMPARADO_CON_IVA, con_iva
        explicacion.append("La suma coincide al céntimo con la cifra con IVA, no con la base sin IVA.")
    elif not incierto and _es_ejecucion_material_de(suma, base):
        declarada = next(
            (d for d in presupuesto.ejecucion_material if _es_ejecucion_material_de(_cent(d[0]), base)), None
        )
        tipo = EJECUCION_MATERIAL
        explicacion.append(
            f"La suma no es la base sin IVA publicada ({_euros(base)}), pero multiplicada por 1,15 la da "
            f"a un céntimo (el del redondeo de los gastos generales y el beneficio industrial, que se "
            f"suman por separado): el cuadro está a precios de ejecución material."
        )
        if declarada is not None:
            cifra = _cent(declarada[0])
            pagina = f" p.{declarada[2]}" if declarada[2] else ""
            explicacion.append(
                f"Se compara con el Presupuesto de Ejecución Material que declara {declarada[1]}{pagina}, "
                f"{_euros(cifra)}."
            )
        else:
            cifra = _cent(base / _GASTOS_Y_BENEFICIO)
            explicacion.append(
                f"Ningún documento declara esa ejecución material: se compara con la equivalente, "
                f"{_euros(base)} ÷ 1,15 = {_euros(cifra)}."
            )
        resultado = CUADRA_AL_CENTIMO if suma == cifra else CUADRA_MENOS_001
    elif base and abs(suma - base) / base < _UMBRAL_CASI:
        resultado = CUADRA_MENOS_001
        explicacion.append(
            f"Diferencia de {_euros(suma - base)}, por debajo del 0,01 % del presupuesto."
        )
    else:
        resultado = NO_CUADRA
        mayor = "más" if suma > base else "menos"
        explicacion.append(
            f"La suma de sus {len(lineas)} líneas es {_euros(abs(suma - base))} {mayor} que el "
            f"presupuesto publicado."
        )
        porcentaje = _porcentaje_exacto(suma, base)
        if porcentaje is not None:
            explicacion.append(f"La suma es exactamente el {porcentaje} % del presupuesto, al céntimo.")
        elif base and suma / base >= 10:
            explicacion.append(
                f"La suma es {int(suma / base):,} veces el presupuesto: revisar las cantidades y los "
                "precios de este lote contra el documento.".replace(",", ".")
            )
    if lineas_fuera_de_materiales:
        # `6.25/28510.0097` lotes 2 y 3: sus conjuntos de contrapesos no traen
        # cantidad y su tabla no sale en "Materiales" (mapeo incoherente). Sin
        # decirlo, "No cuadra" parecería un fallo de atribución.
        explicacion.append(
            f"Además, {lineas_fuera_de_materiales} fila(s) de este lote están en la base de datos pero no "
            "salen en \"Materiales\" (el Resumen explica por qué se dejan fuera), y no se suman."
        )
    if partidas_una_vez:
        explicacion.append(
            f"Incluye {partidas_una_vez} partida(s) alzada(s) sin cantidad, contada(s) una vez por su "
            "importe: una partida alzada es cantidad 1 por definición."
        )
    comprobado = _COMPROBADO_A_MANO.get((expediente.codigo_expediente, lote.identificador_lote, suma, cifra))
    if comprobado:
        explicacion.append(comprobado)

    diferencia = suma - cifra
    return FilaContraste(
        codigo_expediente=expediente.codigo_expediente,
        lote=lote.identificador_lote,
        presupuesto_publicado=base,
        tipo_cifra=tipo,
        cifra_comparada=cifra,
        documento=presupuesto.documento,
        pagina=presupuesto.pagina,
        suma_lineas=suma,
        diferencia=diferencia,
        diferencia_relativa=(diferencia / cifra) if cifra else None,
        lineas=len(lineas),
        lineas_sin_cantidad=sin_cantidad,
        resultado=resultado,
        explicacion=" ".join(explicacion),
    )


def _clave_lote(identificador: str) -> tuple:
    return (0, int(identificador), "") if identificador.isdigit() else (1, 0, identificador)


def construir_contraste(
    db: Session, lineas_por_lote: dict[int, Iterable[LineaCatalogo]]
) -> Contraste:
    """Una fila por lote con filas en "Materiales" y presupuesto publicado; el
    resto, en `Contraste.fuera` con su motivo."""
    lineas_por_lote = {lote_id: list(lineas) for lote_id, lineas in lineas_por_lote.items() if lineas}
    lotes = {
        lote.id: lote
        for lote in db.execute(select(Lote).where(Lote.id.in_(lineas_por_lote))).scalars()
    }
    expedientes = {
        e.id: e
        for e in db.execute(
            select(Expediente).where(Expediente.id.in_({l.expediente_id for l in lotes.values()}))
        ).scalars()
    }
    fuentes = _Fuentes(db, set(expedientes))
    # Todas las filas de cada lote que pasan los filtros del entregable, salgan
    # o no en "Materiales": la diferencia son las que se dejan fuera.
    en_el_entregable = Counter(
        lote_id
        for (lote_id,) in db.execute(
            filtros_del_entregable(select(LineaCatalogo.lote_id)).where(
                LineaCatalogo.lote_id.in_(lineas_por_lote)
            )
        )
    )

    contraste = Contraste()
    for lote_id, lineas in lineas_por_lote.items():
        lote = lotes[lote_id]
        expediente = expedientes[lote.expediente_id]
        if any(linea.heredado_de_matriz for linea in lineas):
            contraste.fuera.append(LoteFuera(expediente.codigo_expediente, lote.identificador_lote,
                                             len(lineas), CUADRO_HEREDADO))
            continue
        presupuesto, motivo = _presupuesto_del_lote(fuentes, expediente, lote)
        if presupuesto is None:
            contraste.fuera.append(LoteFuera(expediente.codigo_expediente, lote.identificador_lote,
                                             len(lineas), motivo or SIN_PRESUPUESTO))
            continue
        contraste.filas.append(_comparar(
            expediente, lote, lineas, presupuesto,
            lineas_fuera_de_materiales=max(0, en_el_entregable[lote_id] - len(lineas)),
        ))

    contraste.filas.sort(key=lambda f: (f.codigo_expediente, _clave_lote(f.lote)))
    contraste.fuera.sort(key=lambda f: (f.codigo_expediente, _clave_lote(f.lote)))
    return contraste
