"""Reconocimiento óptico de documentos escaneados (sesión 2026-09-17,
`docs/sesion-2026-09-17-escaneados-codigo-material.md`, decisión del cliente).

140 documentos del corpus (casi todos de 2016-2019) no traen capa de texto;
60 son pliegos técnicos con su cuadro de precios. La vía es la que ya preveía
CONTEXTO.md sección 15: rasterizar cada página y leerla con el modelo con
visión (`ModelProvider.completar_con_imagen`), no un OCR tradicional.

Tres condiciones del cliente:

1. **Desactivable** (`OCR_MODO`: "escaneados" por defecto, "desactivado"), y
   solo para documentos que `app.extraccion.texto.es_documento_escaneado`
   marca como tales: un documento con texto nunca pasa por aquí.
2. **Marcado**: las líneas que salen de aquí llevan `texto_reconocido`, un
   motivo de revisión propio (`MOTIVO_TEXTO_RECONOCIDO`) y el prefijo
   `MARCA_FRAGMENTO` en su fragmento y en las trazas del documento.
3. **Sin repetir**: el resultado se cachea por hash de documento
   (`CacheOcrDocumento`), como el texto normal.

Para no leer páginas que no sirven, se leen primero las
`PAGINAS_PARA_CLASIFICAR` primeras: si con eso el documento es un pliego
administrativo (que la cascada tampoco abre, `es_pliego_sin_precios`), se para
ahí. Un documento de más de `settings.ocr_max_paginas` páginas tampoco se lee
entero. En los dos casos la caché lo guarda como `completo=False`.

Lo reconocido se convierte en un PDF con capa de texto y rejilla
(`app.extraccion.ocr_pdf`) que recorre la cascada sin cambios.
"""
from __future__ import annotations

import io
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import BinaryIO, Callable, Optional

import pypdfium2 as pdfium
from sqlalchemy.orm import Session

from app.config import settings
from app.extraccion.texto import PaginaTexto
from app.interfaces.model_provider import ModelProvider, RespuestaTruncada

logger = logging.getLogger(__name__)

VERSION_LOGICA_OCR = "2026-09-17"
PAGINAS_PARA_CLASIFICAR = 2
# Lado largo de la imagen enviada: el tamaño que el modelo usa sin reescalar.
LADO_LARGO_PX = 1568

MARCA_FRAGMENTO = "[reconocimiento óptico]"
MOTIVO_TEXTO_RECONOCIDO = (
    "línea leída por reconocimiento óptico de un documento escaneado (sin capa de texto): "
    "puede traer errores de lectura, confirmar contra el documento antes de dar por buena"
)

_ESQUEMA_PAGINA = {
    "type": "object",
    "properties": {
        "bloques": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "tipo": {"type": "string", "enum": ["texto", "tabla"]},
                    "texto": {"type": "string"},
                    "filas": {"type": "array", "items": {"type": "array", "items": {"type": "string"}}},
                },
                "required": ["tipo", "texto", "filas"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["bloques"],
    "additionalProperties": False,
}

_PROMPT_PAGINA = (
    "Esta imagen es una página escaneada de un documento de contratación pública de ADIF "
    "(pliegos, anejos, adjudicaciones). Transcríbela LITERALMENTE, de arriba abajo, en bloques:\n"
    "- tipo \"texto\": un párrafo, título, encabezado o pie, con su texto exacto en \"texto\" "
    "(saltos de línea donde los haya) y \"filas\" vacío.\n"
    "- tipo \"tabla\": una tabla, con \"texto\" vacío y \"filas\" = todas sus filas en orden, "
    "incluidas las de cabecera; una cadena por columna, \"\" si la celda está vacía, y el mismo "
    "número de columnas en cada fila. Si el texto de una celda ocupa varias líneas, júntalas con "
    "\"\\n\".\n"
    "Copia números, códigos y matrículas carácter a carácter, con su puntuación (\"1.234,56 €\"). "
    "No corrijas, no completes, no resumas ni traduzcas. Si algo no se puede leer, escribe "
    "[ilegible] en su lugar. Omite sellos, firmas, rúbricas y los textos verticales de los márgenes."
)


def ocr_activo() -> bool:
    return (settings.ocr_modo or "").strip().lower() == "escaneados"


@dataclass(frozen=True)
class DocumentoReconocido:
    paginas: list[dict]  # salida cacheada, ver `CacheOcrDocumento.paginas`
    completo: bool
    num_paginas: int

    @property
    def paginas_texto(self) -> list[PaginaTexto]:
        return [PaginaTexto(numero=p["numero"], texto=p["texto"]) for p in self.paginas]

    @property
    def segundos(self) -> float:
        return sum(p.get("segundos") or 0.0 for p in self.paginas)


def _texto_de_bloques(bloques: list[dict]) -> str:
    partes = []
    for bloque in bloques:
        if bloque.get("tipo") == "tabla":
            partes.extend(" ".join(c.replace("\n", " ") for c in fila if c) for fila in bloque.get("filas") or [])
        elif bloque.get("texto"):
            partes.append(bloque["texto"])
    return "\n".join(partes)


def _rasterizar(pdf: pdfium.PdfDocument, indice: int) -> bytes:
    pagina = pdf[indice]
    ancho, alto = pagina.get_size()
    escala = LADO_LARGO_PX / max(ancho, alto)
    imagen = pagina.render(scale=escala).to_pil().convert("L")
    salida = io.BytesIO()
    imagen.save(salida, format="PNG", optimize=True)
    return salida.getvalue()


class LecturaIncompleta(RuntimeError):
    """Alguna página no se pudo leer por un fallo transitorio (sin saldo en la
    API, red): lo ya leído queda en la caché, y el trabajo falla para que se
    vea y se reintente -- el siguiente intento solo relee esas páginas."""


def _leer_pagina(imagen: bytes, numero: int, model_provider: ModelProvider) -> dict:
    inicio = time.monotonic()
    try:
        respuesta = model_provider.completar_con_imagen(_PROMPT_PAGINA, imagen, esquema=_ESQUEMA_PAGINA)
    except NotImplementedError:
        raise
    except Exception as exc:  # noqa: BLE001 -- una página que falla no tira el documento
        # Sesión 2026-09-17, lanzamiento sobre el corpus: una página de
        # `6.18/28510.0071` que no cabía en max_tokens, y el saldo de la API
        # agotado al final, tiraban el documento entero y lo ya leído se perdía.
        return {
            "numero": numero, "texto": "", "bloques": [], "segundos": round(time.monotonic() - inicio, 2),
            "tokens_entrada": None, "tokens_salida": None,
            "error": str(exc)[:300], "reintentar": not isinstance(exc, RespuestaTruncada),
        }
    uso = model_provider.uso_ultima_llamada or (None, None)
    bloques = [b for b in (respuesta or {}).get("bloques") or [] if isinstance(b, dict)]
    return {
        "numero": numero,
        "texto": _texto_de_bloques(bloques),
        "bloques": bloques,
        "segundos": round(time.monotonic() - inicio, 2),
        "tokens_entrada": uso[0],
        "tokens_salida": uso[1],
    }


def _leer_paginas(datos_pdf: bytes, numeros: list[int], model_provider: ModelProvider) -> list[dict]:
    pdf = pdfium.PdfDocument(datos_pdf)
    try:
        imagenes = [(n, _rasterizar(pdf, n - 1)) for n in numeros]
    finally:
        pdf.close()
    with ThreadPoolExecutor(max_workers=max(1, settings.ocr_paralelismo)) as ejecutor:
        return list(ejecutor.map(lambda par: _leer_pagina(par[1], par[0], model_provider), imagenes))


def _num_paginas(datos_pdf: bytes) -> int:
    pdf = pdfium.PdfDocument(datos_pdf)
    try:
        return len(pdf)
    finally:
        pdf.close()


def _pendientes(paginas: list[dict]) -> list[int]:
    return [p["numero"] for p in paginas if p.get("error") and p.get("reintentar")]


def reconocer_documento_cacheado(
    db: Session,
    documento_hash: str,
    obtener_pdf: Callable[[], bytes | BinaryIO],
    model_provider: ModelProvider,
    es_pliego_sin_precios: Callable[[list[PaginaTexto]], bool],
) -> DocumentoReconocido:
    """El texto reconocido del documento, de la caché si está (misma versión y
    mismo modelo) o leyéndolo. `es_pliego_sin_precios` decide con las primeras
    páginas si merece la pena seguir (el llamador le pasa el clasificador).

    Una página que falla no tira el documento: se guarda con su error. Si el
    fallo es transitorio, se guarda lo leído y se lanza `LecturaIncompleta`; la
    siguiente pasada solo relee esas páginas. Una página que no cabe en la
    respuesta del modelo queda anotada y no se reintenta (daría lo mismo)."""
    from app.models import CacheOcrDocumento

    modelo = settings.model_id or type(model_provider).__name__
    cacheado = db.get(CacheOcrDocumento, documento_hash)
    vigente = (
        cacheado is not None and cacheado.version_logica_ocr == VERSION_LOGICA_OCR and cacheado.modelo == modelo
    )
    if vigente and not _pendientes(cacheado.paginas):
        return DocumentoReconocido(list(cacheado.paginas), cacheado.completo, cacheado.num_paginas)

    contenido = obtener_pdf()
    datos = contenido if isinstance(contenido, bytes) else contenido.read()
    total = _num_paginas(datos)
    if vigente:
        por_numero = {p["numero"]: p for p in cacheado.paginas}
        for releida in _leer_paginas(datos, _pendientes(cacheado.paginas), model_provider):
            por_numero[releida["numero"]] = releida
        paginas = [por_numero[n] for n in sorted(por_numero)]
        planificado_entero = cacheado.completo or len(paginas) == total
    else:
        primeras = list(range(1, min(PAGINAS_PARA_CLASIFICAR, total) + 1))
        paginas = _leer_paginas(datos, primeras, model_provider)
        planificado_entero = True
        if _pendientes(paginas):
            planificado_entero = False  # sin las primeras páginas no se puede decidir si seguir
        elif es_pliego_sin_precios([PaginaTexto(numero=p["numero"], texto=p["texto"]) for p in paginas]):
            planificado_entero = total <= len(primeras)
        elif total > settings.ocr_max_paginas:
            planificado_entero = False
        elif total > len(primeras):
            paginas += _leer_paginas(datos, list(range(len(primeras) + 1, total + 1)), model_provider)
    completo = planificado_entero and len(paginas) == total and not any(p.get("error") for p in paginas)
    logger.info(
        "OCR %s: %d de %d páginas leídas en %.1f s (completo=%s, con error=%d)",
        documento_hash[:12], len(paginas), total, sum(p["segundos"] for p in paginas), completo,
        sum(1 for p in paginas if p.get("error")),
    )

    if cacheado is None:
        cacheado = CacheOcrDocumento(documento_hash=documento_hash)
        db.add(cacheado)
    cacheado.version_logica_ocr = VERSION_LOGICA_OCR
    cacheado.modelo = modelo
    cacheado.num_paginas = total
    cacheado.completo = completo
    cacheado.paginas = paginas
    db.commit()
    pendientes = _pendientes(paginas)
    if pendientes:
        raise LecturaIncompleta(
            f"reconocimiento óptico incompleto ({len(pendientes)} página(s) sin leer por un fallo transitorio, "
            f"se reintentarán): {next(p['error'] for p in paginas if p.get('error') and p.get('reintentar'))}"
        )
    return DocumentoReconocido(paginas, completo, total)


def marcar_linea_reconocida(linea: dict) -> None:
    """Condición 2 del cliente: la línea sale de texto reconocido, y se nota
    en la marca, en el motivo y en el fragmento que la ancla."""
    linea["texto_reconocido"] = True
    motivo = linea.get("motivo_revision")
    if not motivo or MOTIVO_TEXTO_RECONOCIDO not in motivo:
        linea["motivo_revision"] = f"{MOTIVO_TEXTO_RECONOCIDO}; {motivo}" if motivo else MOTIVO_TEXTO_RECONOCIDO
    fragmento = linea.get("fragmento")
    if fragmento and not fragmento.startswith(MARCA_FRAGMENTO):
        linea["fragmento"] = f"{MARCA_FRAGMENTO} {fragmento}"
