"""Relectura de páginas concretas de un documento escaneado con un modelo
distinto del habitual (bloque 1, sesión 2026-09-19 quinta parte, encargo del
cliente sobre `3.16/28510.0044`).

El reconocimiento óptico de `app.extraccion.ocr` lee con `MODEL_ID`
(`claude-haiku-4-5` en este despliegue), y eso basta para casi todo el corpus
de escaneados. Hay una excepción medida: el `ANEJO_1.pdf` de
`3.16/28510.0044` (130 páginas) trae su presupuesto en una **tabla apaisada**
que ese modelo devuelve inservible -- celdas fundidas, columnas cruzadas y
texto corrompido ("Transmísión", "cabezado a panl", "Etiqueta articulo la 13
trams de Mbs"). No es un problema de la cascada: es la lectura.

Este módulo hace exactamente lo que pidió el cliente y nada más:

- **Solo las páginas que se le nombran.** Releer las 130 costaría 20 veces más
  y las otras 124 ya están bien leídas.
- **Solo con el modelo que se le nombra** (payload `modelo`, o
  `OCR_MODELO_RELECTURA`). Sin ninguno de los dos, falla: nunca relee en
  silencio con el modelo de siempre, que daría lo mismo.
- **Nunca empeora lo que ya había.** Una página cuya relectura vuelve con
  error, o vacía, se deja como estaba.
- **Queda escrito de dónde sale cada página.** Cada página releída guarda su
  `modelo` dentro de la propia entrada de `CacheOcrDocumento.paginas`; el
  campo `CacheOcrDocumento.modelo` sigue siendo el modelo base, que es el que
  gobierna la validez de la caché (`reconocer_documento_cacheado`).

No cambia el estado del expediente ni sus líneas: para que la relectura llegue
al catálogo hay que reextraer el expediente después, como con cualquier otro
cambio de la cascada.
"""
from __future__ import annotations

import logging
from typing import BinaryIO, Callable, Optional

from sqlalchemy.orm import Session

from app.extraccion.ocr import VERSION_LOGICA_OCR, _leer_paginas

logger = logging.getLogger(__name__)

TIPO_TRABAJO = "ocr_relectura"


def releer_paginas(
    db: Session,
    documento_hash: str,
    obtener_pdf: Callable[[], bytes | BinaryIO],
    model_provider,
    paginas: list[int],
    modelo: str,
) -> dict:
    """Relee `paginas` con `model_provider` y las mete en la caché de
    reconocimiento óptico del documento. Devuelve el resumen (páginas
    sustituidas, las que se dejaron como estaban y el gasto en tokens) para
    que el trabajo de cola lo registre.

    Exige que el documento ya tenga caché: releer con otro modelo un documento
    que nunca se ha leído no es esto, es una lectura normal."""
    from app.models import CacheOcrDocumento

    cacheado = db.get(CacheOcrDocumento, documento_hash)
    if cacheado is None:
        raise RuntimeError(
            f"el documento {documento_hash[:12]} no tiene ninguna lectura por reconocimiento óptico "
            "en caché: no hay nada que releer"
        )
    numeros = sorted({int(n) for n in paginas})
    fuera = [n for n in numeros if n < 1 or n > cacheado.num_paginas]
    if fuera:
        raise RuntimeError(
            f"páginas fuera del documento ({cacheado.num_paginas} páginas): {fuera}"
        )

    contenido = obtener_pdf()
    datos = contenido if isinstance(contenido, bytes) else contenido.read()
    releidas = _leer_paginas(datos, numeros, model_provider)

    por_numero = {p["numero"]: dict(p) for p in cacheado.paginas}
    sustituidas: list[int] = []
    sin_cambio: list[int] = []
    for pagina in releidas:
        numero = pagina["numero"]
        if pagina.get("error") or not (pagina.get("texto") or "").strip():
            # Nunca se pisa una lectura que existía con una peor o vacía.
            sin_cambio.append(numero)
            continue
        pagina["modelo"] = modelo
        por_numero[numero] = pagina
        sustituidas.append(numero)

    cacheado.paginas = [por_numero[n] for n in sorted(por_numero)]
    cacheado.version_logica_ocr = VERSION_LOGICA_OCR
    db.commit()

    resumen = {
        "documento_hash": documento_hash,
        "modelo": modelo,
        "paginas_pedidas": numeros,
        "paginas_sustituidas": sustituidas,
        "paginas_sin_cambio": sin_cambio,
        "tokens_entrada": sum(p.get("tokens_entrada") or 0 for p in releidas),
        "tokens_salida": sum(p.get("tokens_salida") or 0 for p in releidas),
        "segundos": round(sum(p.get("segundos") or 0.0 for p in releidas), 1),
    }
    logger.info("relectura óptica %s con %s: %s", documento_hash[:12], modelo, resumen)
    return resumen


def modelo_de_relectura(payload: dict, por_defecto: Optional[str]) -> str:
    modelo = (payload.get("modelo") or por_defecto or "").strip()
    if not modelo:
        raise RuntimeError(
            "relectura óptica sin modelo: indica `modelo` en el payload o configura "
            "OCR_MODELO_RELECTURA (nunca se relee con el modelo de siempre, daría el mismo resultado)"
        )
    return modelo
