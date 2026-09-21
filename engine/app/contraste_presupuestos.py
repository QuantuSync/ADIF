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
FALTAN_CANTIDADES = "No se puede cerrar: faltan cantidades"
# Sesión 2026-09-21 (segunda parte): "No cuadra" a secas no le dice nada a quien
# gestiona presupuestos. Cada lote que no cuadra lleva su causa, comprobada
# contra el documento (`_CAUSAS_COMPROBADAS`), y la explicación en una línea.
NO_CUADRA_LECTURA = "No cuadra: lectura del catálogo pendiente de corregir"
NO_CUADRA_OTRA_CIFRA = "No cuadra: el presupuesto publicado es otra cifra (IVA, gastos generales o beneficio)"
NO_CUADRA_ESTIMADAS = "No cuadra: cantidades estimadas, el presupuesto es un máximo"
NO_CUADRA_FALTAN_LINEAS = "No cuadra: faltan líneas del lote en el catálogo"
NO_CUADRA_PARTIDAS = "No cuadra: el presupuesto incluye partidas que el cuadro no trae"
NO_CUADRA_DOCUMENTO = "No cuadra: discrepancia del propio documento"
NO_CUADRA_SIN_CAUSA = "No cuadra: causa sin determinar"
RESULTADOS_NO_CUADRA = (
    NO_CUADRA_LECTURA,
    NO_CUADRA_OTRA_CIFRA,
    NO_CUADRA_ESTIMADAS,
    NO_CUADRA_FALTAN_LINEAS,
    NO_CUADRA_PARTIDAS,
    NO_CUADRA_DOCUMENTO,
    NO_CUADRA_SIN_CAUSA,
)
RESULTADOS = (CUADRA_AL_CENTIMO, CUADRA_MENOS_001, *RESULTADOS_NO_CUADRA, FALTAN_CANTIDADES)
# Qué significa cada resultado, para quien gestiona presupuestos. Lo usan la
# hoja del Excel, la API (y con ella la pantalla de la web) y
# `docs/diccionario-excel.md`: una sola redacción.
SIGNIFICADO = {
    CUADRA_AL_CENTIMO: "La suma de sus líneas es exactamente el presupuesto publicado.",
    CUADRA_MENOS_001: "No es exacta, pero la diferencia es menor de una diezmilésima del presupuesto.",
    NO_CUADRA_LECTURA: (
        "El catálogo ha leído mal una cantidad, un precio o el lote de alguna fila. Está comprobado contra "
        "el documento y pendiente de arreglar."
    ),
    NO_CUADRA_OTRA_CIFRA: "La cifra publicada no es la base sin IVA equivalente a los precios del cuadro.",
    NO_CUADRA_ESTIMADAS: (
        "El documento da cantidades de referencia o por pedido, no las que se van a comprar: el presupuesto "
        "es un techo de gasto y la suma no tiene por qué coincidir con él."
    ),
    NO_CUADRA_FALTAN_LINEAS: (
        "El documento trae filas de este lote que no están en \"Materiales\" (en revisión, o no leídas)."
    ),
    NO_CUADRA_PARTIDAS: (
        "El presupuesto suma conceptos que no están en el cuadro de precios: reparaciones, obra, "
        "mantenimiento, servicios."
    ),
    NO_CUADRA_DOCUMENTO: "Las filas están bien leídas y el propio documento no suma su presupuesto.",
    NO_CUADRA_SIN_CAUSA: "La causa no se ha comprobado todavía contra el documento.",
    FALTAN_CANTIDADES: "Alguna fila del lote no trae cantidad o precio en el documento, así que la suma está incompleta.",
}

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
class _Causa:
    resultado: str
    texto: str


def _causas(
    expedientes: Iterable[str], lote: str, suma: str, presupuesto: str, resultado: str, texto: str
) -> dict[tuple[str, str, Decimal, Decimal], _Causa]:
    return {(e, lote, Decimal(suma), Decimal(presupuesto)): _Causa(resultado, texto) for e in expedientes}


# Sesión 2026-09-21 (segunda parte): la causa de cada lote que no cuadra,
# comprobada contra su documento (`docs/sesion-2026-09-21-sumas-absurdas-
# causas-del-contraste-y-ficha-duplicada.md`, bloque 2). Misma regla que
# `_COMPROBADO_A_MANO`: la clave lleva la suma y el presupuesto que se
# comprobaron, y **si cualquiera de los dos cambia, la causa no se escribe**
# -- la fila pasa a "causa sin determinar" en vez de explicar otra cosa.
_REFERENCIA_1 = (
    "El cuadro es una lista de precios con una «cantidad estimada» de 1 por referencia, no el pedido: el "
    "presupuesto es el máximo de gasto del contrato"
)
_POR_PEDIDO = (
    "El cuadro da la cantidad mínima por pedido (y la del pedido inicial), no la cantidad total a comprar: "
    "el presupuesto es el máximo de gasto del contrato"
)
_BALASTO = (
    "Las cantidades del cuadro son «estimadas de referencia» y están bien leídas, fila a fila: el "
    "presupuesto del lote es su dotación máxima y el documento no dice que salga de esas cantidades"
)
_UN_SOLO_LOTE_ESCANEADO = (
    "El anejo escaneado trae los cuadros de todos los lotes de la licitación y este expediente los tiene "
    "todos como un único lote: el reparto por lotes de los documentos escaneados está pendiente"
)
_CAUSAS_COMPROBADAS: dict[tuple[str, str, Decimal, Decimal], _Causa] = {
    # --- Lectura del catálogo pendiente de corregir ---
    **_causas(["3.22/28510.0048"], "1", "81300.00", "12900.00", NO_CUADRA_LECTURA,
              "Los lotes 1 y 2 van en la misma tabla y sus filas se han leído todas como del lote 1: la suma "
              "es exactamente 12.900,00 € del lote 1 más 68.400,00 € del lote 2"),
    **_causas(["3.23/28510.0135"], "2", "192435.66", "8545.90", NO_CUADRA_LECTURA,
              "La tabla del anejo mete los lotes 2 a 8 con su rótulo en una fila y se ha leído entera como lote "
              "2; sus filas P-6 a P-8 suman exactamente los 8.545,90 € del lote 2"),
    **_causas(["3.23/28510.0135"], "6", "64285.55", "68146.10", NO_CUADRA_LECTURA,
              "Sus dos filas llevan el precio ofertado del contrato (27.335,30 y 36.950,25 €), no el de "
              "licitación del anejo (28.549,40 y 39.596,70 €), que suman el presupuesto exacto"),
    **_causas(["4.26/28510.0020"], "1", "2852766.32", "2853591.32", NO_CUADRA_LECTURA,
              "P-12 lleva el precio ofertado en un contrato, 5.335,00 €; el presupuesto del lote (ANEJO_1.pdf "
              "p.15) lo da a 5.500,00 € y con él cuadra al céntimo"),
    **_causas(["2.23/28510.0138"], "1", "32815.00", "32740.00", NO_CUADRA_LECTURA,
              "Faltan dos filas del cuadro (4 × 140,00 € y 2 × 40,00 €) y sobran dos de otra tabla (440,00 € y "
              "275,00 €); las filas del cuadro suman su TOTAL, 32.740,00 €"),
    **_causas(["6.19/28510.0135"], "1", "434723.09", "175000.00", NO_CUADRA_LECTURA, _UN_SOLO_LOTE_ESCANEADO),
    **_causas(["6.19/28510.0175"], "1", "434723.09", "1100000.00", NO_CUADRA_LECTURA, _UN_SOLO_LOTE_ESCANEADO),
    **_causas(["6.19/28510.0177"], "1", "434723.09", "350000.00", NO_CUADRA_LECTURA, _UN_SOLO_LOTE_ESCANEADO),
    **_causas(["6.19/28510.0231"], "1", "55946.19", "10000.00", NO_CUADRA_LECTURA, _UN_SOLO_LOTE_ESCANEADO),
    **_causas(["6.20/28510.0025"], "1", "55946.19", "20000.00", NO_CUADRA_LECTURA, _UN_SOLO_LOTE_ESCANEADO),
    # --- Cantidades estimadas: el presupuesto es un máximo ---
    **_causas(["6.23/28510.0034"], "1", "54.35", "400000.00", NO_CUADRA_ESTIMADAS, _REFERENCIA_1),
    **_causas(["6.23/28510.0137"], "1", "17.30", "200000.00", NO_CUADRA_ESTIMADAS, _REFERENCIA_1),
    **_causas(["6.24/28510.0125"], "2", "187.09", "175000.00", NO_CUADRA_ESTIMADAS, _REFERENCIA_1),
    **_causas(["6.24/28510.0096"], "1", "2238.07", "400000.00", NO_CUADRA_ESTIMADAS, _REFERENCIA_1),
    **_causas(["6.24/28510.0129"], "1", "6029.58", "160000.00", NO_CUADRA_ESTIMADAS, _REFERENCIA_1),
    **_causas(["6.22/28510.0163"], "1", "3363.75", "80000.00", NO_CUADRA_ESTIMADAS, _REFERENCIA_1),
    **_causas(["6.24/28510.0173"], "1", "12898.46", "100000.00", NO_CUADRA_ESTIMADAS, _REFERENCIA_1),
    **_causas(["6.26/28510.0016"], "1", "56061.37", "240000.00", NO_CUADRA_ESTIMADAS, _REFERENCIA_1),
    **_causas(["6.22/28510.0160"], "1", "64360.10", "200000.00", NO_CUADRA_ESTIMADAS, _REFERENCIA_1),
    **_causas(["6.25/28510.0246"], "1", "232213.03", "200000.00", NO_CUADRA_ESTIMADAS, _REFERENCIA_1),
    **_causas(["6.23/28510.0097"], "4", "85443.36", "53333.33", NO_CUADRA_ESTIMADAS, _REFERENCIA_1),
    **_causas(["6.24/28510.0184"], "1", "105487.82", "140000.00", NO_CUADRA_ESTIMADAS,
              "El cuadro da un precio de adquisición y otro de reparación con una «cantidad estimada» de 1 por "
              "referencia: el presupuesto es el máximo de gasto del contrato"),
    **_causas(["6.19/28510.0115", "6.19/28510.0161", "6.19/28510.0163"], "1", "11221.30", "260000.00",
              NO_CUADRA_ESTIMADAS, _POR_PEDIDO),
    **_causas(["6.19/28510.0115", "6.19/28510.0162", "6.19/28510.0163"], "2", "2776.75", "2100000.00",
              NO_CUADRA_ESTIMADAS, _POR_PEDIDO),
    **_causas(["6.19/28510.0134", "6.19/28510.0157", "6.19/28510.0158"], "2", "15656.40", "480000.00",
              NO_CUADRA_ESTIMADAS, _POR_PEDIDO),
    **_causas(["6.19/28510.0134", "6.19/28510.0157", "6.19/28510.0159"], "3", "5131.80", "375000.00",
              NO_CUADRA_ESTIMADAS, _POR_PEDIDO),
    **_causas(["6.19/28510.0126"], "1", "16624.00", "190000.00", NO_CUADRA_ESTIMADAS, _POR_PEDIDO),
    **_causas(["6.19/28510.0126"], "2", "6346.35", "150000.00", NO_CUADRA_ESTIMADAS, _POR_PEDIDO),
    **_causas(["6.19/28510.0166"], "1", "16940.50", "190000.00", NO_CUADRA_ESTIMADAS, _POR_PEDIDO),
    **_causas(["6.19/28510.0167"], "2", "6662.85", "150000.00", NO_CUADRA_ESTIMADAS, _POR_PEDIDO),
    **_causas(["6.19/28510.0136"], "1", "18544.06", "70000.00", NO_CUADRA_ESTIMADAS, _POR_PEDIDO),
    **_causas(["6.19/28510.0181"], "1", "1470.53", "300000.00", NO_CUADRA_ESTIMADAS, _POR_PEDIDO),
    **_causas(["6.19/28510.0184"], "2", "23962.64", "60000.00", NO_CUADRA_ESTIMADAS, _POR_PEDIDO),
    **_causas(["6.19/28510.0195"], "1", "63771.00", "70000.00", NO_CUADRA_ESTIMADAS, _POR_PEDIDO),
    **_causas(["6.19/28510.0202"], "1", "3806.70", "26500.00", NO_CUADRA_ESTIMADAS, _POR_PEDIDO),
    **_causas(["6.19/28510.0202"], "2", "1967.67", "16500.00", NO_CUADRA_ESTIMADAS, _POR_PEDIDO),
    **_causas(["6.19/28510.0202"], "3", "566.00", "7000.00", NO_CUADRA_ESTIMADAS, _POR_PEDIDO),
    **_causas(["6.19/28510.0207"], "1", "6860.85", "200000.00", NO_CUADRA_ESTIMADAS, _POR_PEDIDO),
    **_causas(["6.19/28510.0207"], "2", "18072.38", "300000.00", NO_CUADRA_ESTIMADAS, _POR_PEDIDO),
    **_causas(["6.19/28510.0207"], "3", "7037.25", "100000.00", NO_CUADRA_ESTIMADAS, _POR_PEDIDO),
    **_causas(["6.19/28510.0215"], "1", "13983.07", "30000.00", NO_CUADRA_ESTIMADAS, _POR_PEDIDO),
    **_causas(["6.20/28510.0028"], "1", "55707.00", "170000.00", NO_CUADRA_ESTIMADAS, _POR_PEDIDO),
    **_causas(["6.22/28510.0103", "6.22/28510.0139", "6.22/28510.0140", "6.22/28510.0142", "6.22/28510.0143"],
              "5", "224734.25", "232222.38", NO_CUADRA_ESTIMADAS, _BALASTO),
    **_causas(["6.22/28510.0103", "6.22/28510.0139", "6.22/28510.0140", "6.22/28510.0142", "6.22/28510.0144"],
              "6", "642800.40", "659431.85", NO_CUADRA_ESTIMADAS, _BALASTO),
    **_causas(["6.22/28510.0105", "6.22/28510.0147", "6.22/28510.0148", "6.22/28510.0149", "6.22/28510.0150"],
              "4", "644532.00", "659874.60", NO_CUADRA_ESTIMADAS, _BALASTO),
    **_causas(["6.22/28510.0105", "6.22/28510.0147", "6.22/28510.0148", "6.22/28510.0149", "6.22/28510.0151"],
              "5", "405353.25", "415078.13", NO_CUADRA_ESTIMADAS, _BALASTO),
    **_causas(["6.22/28510.0146"], "2", "209831.40", "215973.45", NO_CUADRA_ESTIMADAS, _BALASTO),
    **_causas(["6.22/28510.0165", "6.23/28510.0023"], "2", "520305.00", "508185.00", NO_CUADRA_ESTIMADAS, _BALASTO),
    **_causas(["6.22/28510.0165", "6.23/28510.0024"], "3", "790687.20", "776167.20", NO_CUADRA_ESTIMADAS, _BALASTO),
    **_causas(["6.22/28510.0033", "6.22/28510.0057"], "1", "2379718.50", "2400000.00", NO_CUADRA_ESTIMADAS,
              "Pedido abierto: el documento dice que las cantidades serán las que se concreten en las órdenes de "
              "entrega, así que las del cuadro son estimadas y el presupuesto es un máximo"),
    **_causas(["6.22/28510.0033", "6.22/28510.0058"], "2", "2366875.80", "2400000.00", NO_CUADRA_ESTIMADAS,
              "Pedido abierto: el documento dice que las cantidades serán las que se concreten en las órdenes de "
              "entrega, así que las del cuadro son estimadas y el presupuesto es un máximo"),
    **_causas(["6.22/28510.0122"], "1", "11209999.78", "5900000.00", NO_CUADRA_ESTIMADAS,
              "El cuadro del lote lista los 407 aparatos (también los del otro lote, para urgencias) con cantidad "
              "de referencia 1: no es el pedido del lote"),
    **_causas(["6.22/28510.0122"], "2", "11209999.78", "5900000.00", NO_CUADRA_ESTIMADAS,
              "El cuadro del lote lista los 407 aparatos (también los del otro lote, para urgencias) con cantidad "
              "de referencia 1: no es el pedido del lote"),
    **_causas(["6.20/28510.0041"], "1", "21999998.38", "500000.00", NO_CUADRA_ESTIMADAS,
              "El cuadro da una «cantidad de referencia» (3 casi siempre) para 345 aparatos: es una lista de "
              "precios, no el pedido, y el presupuesto es el máximo de gasto"),
    **_causas(["6.21/28510.0041"], "1", "500014.38", "550000.00", NO_CUADRA_ESTIMADAS,
              "El cuadro da «medición estimada» y el documento no publica su total: el presupuesto es el máximo "
              "de gasto"),
    **_causas(["6.21/28510.0113"], "5", "199814.90", "200000.00", NO_CUADRA_ESTIMADAS,
              "El cuadro separa las cantidades obligatorias en el pedido (0) de las «estimadas de referencia», "
              "que son las del catálogo: el presupuesto es un máximo"),
    **_causas(["6.23/28510.0051", "6.23/28510.0060"], "1", "2160000.00", "2400000.00", NO_CUADRA_ESTIMADAS,
              "Cantidades «estimadas de referencia», 0 en casi todos los aparatos: la suma es exactamente el 90 % "
              "del presupuesto, que es el máximo de gasto"),
    **_causas(["6.23/28510.0051"], "2", "2160000.00", "2400000.00", NO_CUADRA_ESTIMADAS,
              "Cantidades «estimadas de referencia», 0 en casi todos los aparatos: la suma es exactamente el 90 % "
              "del presupuesto, que es el máximo de gasto"),
    **_causas(["6.18/28510.0003"], "1", "16053880.00", "8000000.00", NO_CUADRA_ESTIMADAS,
              "Acuerdo marco con «cantidades de referencia» (600.000 kg de hilo, por ejemplo): la suma del cuadro "
              "no es el gasto y el presupuesto es el máximo del acuerdo"),
    **_causas(["6.25/28510.0030"], "1", "11700000.00", "4277946.96", NO_CUADRA_ESTIMADAS,
              "El cuadro es el del acuerdo marco de carril (suma exactamente su presupuesto, 11.700.000,00 €) y se "
              "compara con el presupuesto de este pedido"),
    **_causas(["6.25/28510.0115"], "1", "11700000.00", "3137323.84", NO_CUADRA_ESTIMADAS,
              "El cuadro es el del acuerdo marco de carril (suma exactamente su presupuesto, 11.700.000,00 €) y se "
              "compara con el presupuesto de este pedido"),
    # --- Faltan líneas del lote en el catálogo ---
    **_causas(["6.20/28510.0094", "6.20/28510.0141"], "2", "81012.74", "90000.00", NO_CUADRA_FALTAN_LINEAS,
              "Falta la partida alzada para imprevistos del lote, 8.987,26 € (CONTRATO_2.pdf p.105): con ella "
              "cuadra al céntimo"),
    **_causas(["6.20/28510.0131"], "2", "27133.70", "30000.00", NO_CUADRA_FALTAN_LINEAS,
              "Falta la partida alzada de repuestos del lote, 2.866,30 € (ANEJO_3.pdf p.6): con ella cuadra al "
              "céntimo"),
    **_causas(["6.20/28510.0131", "6.21/28510.0017"], "1", "85150.00", "90000.00", NO_CUADRA_FALTAN_LINEAS,
              "Falta la partida alzada de repuestos del lote, 4.850,00 € (ANEJO_3.pdf p.4): con ella cuadra al "
              "céntimo"),
    **_causas(["6.21/28510.0058", "6.21/28510.0130", "6.21/28510.0135", "6.21/28510.0137", "6.21/28510.0138"],
              "1", "200000.00", "220000.00", NO_CUADRA_FALTAN_LINEAS,
              "Falta la partida alzada para imprevistos del lote, 20.000,00 € (CONTRATO_1.pdf p.115): con ella "
              "cuadra al céntimo"),
    **_causas(["6.25/28510.0141", "6.25/28510.0186", "6.25/28510.0187"], "2", "882743.20", "1544593.20",
              NO_CUADRA_FALTAN_LINEAS,
              "Falta la fila P-1 del lote (61.000 t × 10,85 € = 661.850,00 €, ANEJO_1.pdf p.23): con ella cuadra "
              "al céntimo"),
    **_causas(["2.23/28510.0108"], "1", "25611.56", "25792.76", NO_CUADRA_FALTAN_LINEAS,
              "El cuadro repite dos filas idénticas (100 × 1,50 € y 10 × 3,12 €) y el catálogo las tiene una "
              "vez: faltan exactamente 181,20 €"),
    **_causas(["2.24/28510.0068"], "1", "51218.77", "51581.17", NO_CUADRA_FALTAN_LINEAS,
              "El cuadro repite dos filas idénticas (100 × 3,00 € y 10 × 6,24 €) y el catálogo las tiene una "
              "vez: faltan exactamente 362,40 €"),
    **_causas(["2.23/28510.0098"], "1", "29480.00", "35760.00", NO_CUADRA_FALTAN_LINEAS,
              "Faltan cuatro filas del cuadro (1.800, 2.160, 1.520 y 800 €): con ellas se llega a su total, "
              "35.760,00 €"),
    **_causas(["2.24/28510.0118"], "1", "47695.00", "49045.00", NO_CUADRA_FALTAN_LINEAS,
              "Falta la fila «Precintos verdes», 3 × 450,00 € = 1.350,00 €: con ella se llega al TOTAL del cuadro, "
              "49.045,00 €"),
    **_causas(["6.24/28510.0185"], "1", "2499470.00", "2500000.00", NO_CUADRA_FALTAN_LINEAS,
              "Falta la fila P-030b del cuadro, 1 × 530,00 € (ANEJO_1.pdf p.22): con ella cuadra al céntimo"),
    **_causas(["2.26/28510.0006"], "1", "2691203.26", "2740603.26", NO_CUADRA_FALTAN_LINEAS,
              "Falta la fila de horas de técnico especializado, 608 h × 81,25 € = 49.400,00 € (ANEJO_1.pdf p.4): "
              "con ella cuadra al céntimo"),
    **_causas(["6.22/28510.0051", "6.22/28510.0159"], "1", "27150.00", "39695.00", NO_CUADRA_FALTAN_LINEAS,
              "Faltan las filas cuyo precio el documento escribe con punto decimal a la inglesa («12.5»): sin su "
              "total en la fila, el catálogo no las acepta"),
    **_causas(["6.20/28510.0042", "6.20/28510.0046", "6.20/28510.0047"], "2", "22050.00", "500000.00",
              NO_CUADRA_FALTAN_LINEAS,
              "El cuadro del lote 2 (ANEJO_3.pdf pp.47-48) solo ha llegado al catálogo en una fila, y además no "
              "publica cantidades"),
    **_causas(["4.19/28510.0212"], "1", "54536.00", "100096.00", NO_CUADRA_FALTAN_LINEAS,
              "Solo está el cuadro del puesto de Córdoba (54.536,00 €, su total exacto); faltan el de Granada y "
              "16.680,00 € de mantenimiento que el presupuesto también suma"),
    # --- El presupuesto incluye partidas que el cuadro no trae ---
    **_causas(["6.24/28510.0067"], "1", "100050.24", "150000.77", NO_CUADRA_PARTIDAS,
              "El presupuesto es 100.050,24 € de suministro, exactamente la suma, más 49.950,53 € de "
              "reparaciones (CONTRATO_1.pdf p.89)"),
    **_causas(["3.19/28510.0141"], "1", "122806.19", "173852.57", NO_CUADRA_PARTIDAS,
              "El presupuesto es 122.806,20 € de suministro, la suma con un céntimo de redondeo, más 51.046,37 € "
              "de obra (ANEJO_1.pdf p.309)"),
    # --- Discrepancia del propio documento ---
    **_causas([f"6.20/28510.00{n}" for n in ("54", "55", "56", "57", "58")], "3", "8230002.13", "8200000.00",
              NO_CUADRA_DOCUMENTO,
              "Comprobado contra el documento: el cuadro del lote 3 del ANEJO_8.pdf se pasa 30.002,13 € de su "
              "propio presupuesto, y su partida alzada sigue siendo el 3 % exacto"),
    **_causas(["3.22/28510.0009"], "2", "21500.00", "71000.00", NO_CUADRA_DOCUMENTO,
              "El cuadro y la adjudicación numeran distinto los lotes: la suma, 21.500,00 €, es exactamente el "
              "presupuesto del lote 3 (pregunta pendiente para ADIF)"),
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
        mayor = "más" if suma > base else "menos"
        diferencia_texto = f"{_euros(abs(suma - base))} {mayor} que el presupuesto"
        causa = _CAUSAS_COMPROBADAS.get((expediente.codigo_expediente, lote.identificador_lote, suma, base))
        if causa is not None:
            # Una sola línea, la comprobada: es lo que lee quien gestiona el
            # presupuesto.
            return _fila(
                expediente, lote, presupuesto, tipo, cifra, suma, lineas, sin_cantidad, causa.resultado,
                f"{causa.texto} (la suma es {diferencia_texto}).",
            )
        if lineas_fuera_de_materiales:
            return _fila(
                expediente, lote, presupuesto, tipo, cifra, suma, lineas, sin_cantidad, NO_CUADRA_FALTAN_LINEAS,
                f"{lineas_fuera_de_materiales} fila(s) de este lote están en revisión y no salen en "
                f"\"Materiales\", así que no se suman (la suma es {diferencia_texto}).",
            )
        resultado = NO_CUADRA_SIN_CAUSA
        explicacion.append(
            f"La suma de sus {len(lineas)} líneas es {diferencia_texto} publicado; la causa no se ha "
            "comprobado todavía contra el documento."
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
    return _fila(
        expediente, lote, presupuesto, tipo, cifra, suma, lineas, sin_cantidad, resultado, " ".join(explicacion)
    )


def _fila(
    expediente: Expediente, lote: Lote, presupuesto: _Presupuesto, tipo: str, cifra: Decimal, suma: Decimal,
    lineas: list[LineaCatalogo], sin_cantidad: int, resultado: str, explicacion: str,
) -> FilaContraste:
    base = _cent(presupuesto.sin_iva)
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
        explicacion=explicacion,
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
