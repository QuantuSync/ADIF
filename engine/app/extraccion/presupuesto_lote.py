"""El presupuesto de licitación de cada lote, tal como lo publican los
documentos ya descargados (bloque 1, sesión 2026-09-21).

**Para qué existe.** El contraste de presupuestos (`app.contraste_presupuestos`)
suma cantidad × precio de las filas de cada lote y la compara con su
presupuesto publicado. El sistema solo guardaba ese presupuesto por lote
(`Lote.importe_licitacion`) cuando lo declara la adjudicación o el Contrato
del propio lote: medido sobre los 540 lotes con filas en "Materiales", **215
no lo tenían**, y en **179** de ellos el documento sí lo publica. El lote 3 de
`6.20/28510.0054`, el de la discrepancia del propio documento que se verificó
a mano, lo publica tres veces: en el anuncio (`PLIEGO_1.pdf` p.4), en la
lista del `ANEJO_1.pdf` p.4 y en la p.103 de cada Contrato.

**Qué NO hace.** No escribe en `Lote.importe_licitacion` ni en nada del
catálogo: guarda cada aparición en su propia tabla
(`PresupuestoLoteDocumento`), que solo lee el contraste. Ese campo interviene
en la baja, en la prueba aritmética del reparto por lotes y en los precios que
un presupuesto demuestra; rellenarlo desde aquí movería datos del catálogo.

**Tres redacciones, las tres con el tipo de cifra escrito en el propio texto**
(verificadas contra el corpus; no se añade otra sin comprobarla antes):

- ``anuncio`` -- el bloque de un lote del anuncio de la Plataforma: "Lote 3:
  Área Territorial Norte. Presupuesto base de licitación Importe 9.922.000
  EUR. Importe (sin impuestos) 8.200.000 EUR". Trae las dos cifras, con y sin
  IVA. También "Nº Lote: 001 ..." (la variante de `app.extraccion.lotes_pcsp`).
- ``contrato`` -- "importe de licitación del lote N a X € (IVA excluido)", la
  misma expresión que ya lee `app.extraccion.lotes`, pero aquí de todos los
  documentos y de cualquier lote, no solo del Contrato del lote propio.
- ``lista_sin_iva`` -- "Lote 3: Área Territorial Norte, 8.200.000,00 € sin
  IVA" (la lista de lotes del pliego).

Y una cuarta cifra que no es de ningún lote: el **"Presupuesto de Ejecución
Material"** que declara un documento (``ejecucion_material``), sin gastos
generales ni beneficio industrial. El documento no dice de qué lote es; el
contraste solo la liga a un lote cuando multiplicada por 1,15 da, a un céntimo,
la base sin IVA publicada de ese lote (`6.17/28510.0056`: 2.975.673,96 € +
9 % + 6 %, redondeados por separado, = 3.422.025,06 €).

Una mención de lote solo se liga a la cifra que la sigue **sin que se cruce
otra mención de lote en medio**: en un anuncio que enumera los lotes antes de
su presupuesto global, "Lote 6 ... Presupuesto base de licitación" sería el
total de la licitación atribuido al lote 6. Y si aun así un mismo lote recibe
dos cifras distintas, el contraste no escoge ninguna (lo dice en su recuento).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, Optional

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.extraccion.lotes import _LICITACION_DEL_LOTE_RE
from app.extraccion.normalizacion import parsear_importe_es
from app.extraccion.texto import PaginaTexto
from app.models import PresupuestoLoteDocumento

ANUNCIO = "anuncio"
CONTRATO = "contrato"
LISTA_SIN_IVA = "lista_sin_iva"
EJECUCION_MATERIAL = "ejecucion_material"

# Una mención de lote ("Lote 3", "LOTE 3:", "Nº Lote: 003") y, a partir de
# ella, cualquier carácter que NO empiece otra mención de lote.
_MENCION_LOTE = r"(?:N[ºo]\s*)?Lote\s*:?\s*(\d{1,3})\b"
_SIN_OTRO_LOTE = r"(?:(?!Lote\s*:?\s*\d).)"

_ANUNCIO_RE = re.compile(
    _MENCION_LOTE
    + _SIN_OTRO_LOTE + r"{0,400}?Presupuesto\s+base\s+de\s+licitaci[oó]n"
    + _SIN_OTRO_LOTE + r"{0,160}?Importe\s+([\d.]+(?:,\d+)?)\s*EUR"
    + _SIN_OTRO_LOTE + r"{0,200}?Importe\s*\(sin\s+impuestos\)\s*([\d.]+(?:,\d+)?)\s*EUR",
    re.IGNORECASE | re.DOTALL,
)
_EJECUCION_MATERIAL_RE = re.compile(
    r"Presupuesto\s+de\s+Ejecuci[oó]n\s+Material[^\d€]{0,80}?(\d{1,3}(?:\.\d{3})*,\d{2})\s*€?",
    re.IGNORECASE | re.DOTALL,
)
_LISTA_SIN_IVA_RE = re.compile(
    r"Lote\s*(\d{1,3})\s*:[^;€]{0,160}?(\d{1,3}(?:\.\d{3})*,\d{2})\s*€\s*sin\s+IVA",
    re.IGNORECASE | re.DOTALL,
)


@dataclass(frozen=True)
class PresupuestoLoteLeido:
    identificador_lote: Optional[str]
    importe: Decimal
    importe_con_iva: Optional[Decimal]
    redaccion: str
    pagina: int
    fragmento: str


def _identificador(numero: str) -> str:
    """"003" y "3" son el mismo lote: el sistema guarda "3"."""
    return str(int(numero))


def _importe(texto: str) -> Optional[Decimal]:
    try:
        valor = parsear_importe_es(texto)
    except (ValueError, ArithmeticError):
        return None
    return valor if valor > 0 else None


def _fragmento(m: re.Match) -> str:
    return re.sub(r"\s+", " ", m.group(0)).strip()


def leer_presupuestos_de_lote(paginas: Iterable[PaginaTexto]) -> list[PresupuestoLoteLeido]:
    """Todas las apariciones, página a página, sin decidir entre ellas."""
    leidos: list[PresupuestoLoteLeido] = []
    for pagina in paginas:
        texto = pagina.texto or ""
        for m in _ANUNCIO_RE.finditer(texto):
            con_iva, sin_iva = _importe(m.group(2)), _importe(m.group(3))
            # El anuncio da las dos: la de "sin impuestos" nunca puede ser la
            # mayor. Si lo es, la ventana ha cruzado a otra cifra.
            if sin_iva is None or (con_iva is not None and con_iva < sin_iva):
                continue
            leidos.append(PresupuestoLoteLeido(
                _identificador(m.group(1)), sin_iva, con_iva, ANUNCIO, pagina.numero, _fragmento(m)
            ))
        for m in _LICITACION_DEL_LOTE_RE.finditer(texto):
            sin_iva = _importe(m.group(2))
            if sin_iva is not None:
                leidos.append(PresupuestoLoteLeido(
                    _identificador(m.group(1)), sin_iva, None, CONTRATO, pagina.numero, _fragmento(m)
                ))
        for m in _LISTA_SIN_IVA_RE.finditer(texto):
            sin_iva = _importe(m.group(2))
            if sin_iva is not None:
                leidos.append(PresupuestoLoteLeido(
                    _identificador(m.group(1)), sin_iva, None, LISTA_SIN_IVA, pagina.numero, _fragmento(m)
                ))
        for m in _EJECUCION_MATERIAL_RE.finditer(texto):
            importe = _importe(m.group(1))
            if importe is not None:
                leidos.append(PresupuestoLoteLeido(
                    None, importe, None, EJECUCION_MATERIAL, pagina.numero, _fragmento(m)
                ))
    return leidos


def registrar_presupuestos_de_lote(
    db: Session, expediente_id: int, documentos: Iterable[tuple[int, Iterable[PaginaTexto]]]
) -> int:
    """Reescribe las apariciones del expediente: borra las de la pasada
    anterior y guarda las de esta (idempotente, invariante 9). Devuelve
    cuántas guarda."""
    db.execute(delete(PresupuestoLoteDocumento).where(PresupuestoLoteDocumento.expediente_id == expediente_id))
    guardados = 0
    vistos: set[tuple] = set()
    for documento_id, paginas in documentos:
        for leido in leer_presupuestos_de_lote(paginas):
            clave = (documento_id, leido.pagina, leido.redaccion, leido.identificador_lote, leido.importe)
            if clave in vistos:
                continue
            vistos.add(clave)
            db.add(PresupuestoLoteDocumento(
                expediente_id=expediente_id,
                identificador_lote=leido.identificador_lote,
                importe=leido.importe,
                importe_con_iva=leido.importe_con_iva,
                redaccion=leido.redaccion,
                documento_id=documento_id,
                pagina=leido.pagina,
                fragmento=leido.fragmento[:2000],
            ))
            guardados += 1
    return guardados
