"""PDF con capa de texto a partir de lo reconocido en un documento escaneado
(sesión 2026-09-17, `app.extraccion.ocr`).

La cascada de tablas (etapas 3-5, `app.extraccion.pipeline_anejo`) trabaja
sobre la geometría de `pdfplumber`: tablas con sus líneas, el "LOTE N" que va
encima de cada una, la cola de la página anterior. En vez de enseñarle un
segundo formato, se le da un PDF de verdad: una página por página escaneada
(mismo número, para que la traza apunte a la página real), con los bloques de
texto en orden y cada tabla dibujada como rejilla con sus celdas. Así el
documento reconocido recorre la cascada sin ninguna rama propia.

Se genera cada vez desde la caché (es barato y determinista); no se guarda.
"""
from __future__ import annotations

import ctypes
import io

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c

_ANCHO_A4 = 595.0
_ALTO_A4 = 842.0
_MARGEN = 30.0
_TAM_TEXTO = 7.0
_INTERLINEA = 1.25
_RELLENO_CELDA = 3.0
_MAX_CARACTERES_COLUMNA = 60
_MAX_CARACTERES_TEXTO = 120

# Helvetica estándar va en WinAnsi: lo que no cabe se sustituye por su forma
# más próxima en vez de perderse.
_SUSTITUCIONES = {
    "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "−": "-",
    "‘": "'", "’": "'", "´": "'", "“": '"', "”": '"',
    " ": " ", "\t": " ",
}


def _limpiar(texto: str) -> str:
    texto = "".join(_SUSTITUCIONES.get(c, c) for c in texto)
    return "".join(c if (c == "€" or ord(c) < 256) else "?" for c in texto)


def _partir(texto: str, max_caracteres: int) -> list[str]:
    lineas: list[str] = []
    for parrafo in _limpiar(texto).split("\n"):
        actual = ""
        for palabra in parrafo.split(" "):
            candidata = f"{actual} {palabra}" if actual else palabra
            if len(candidata) <= max_caracteres or not actual:
                actual = candidata
            else:
                lineas.append(actual)
                actual = palabra
        lineas.append(actual)
    return lineas


def _alto_linea() -> float:
    return _TAM_TEXTO * _INTERLINEA


class _Escritor:
    def __init__(self) -> None:
        self.documento = pdfium.PdfDocument.new()
        self._buffers: list = []  # vivos hasta guardar: pdfium no copia el texto al instante

    def _nuevo_texto(self, contenido: str):
        objeto = pdfium_c.FPDFPageObj_NewTextObj(self.documento.raw, b"Helvetica", ctypes.c_float(_TAM_TEXTO))
        codificado = (contenido + "\x00").encode("utf-16-le")
        buffer = ctypes.create_string_buffer(codificado, len(codificado))
        self._buffers.append(buffer)
        pdfium_c.FPDFText_SetText(objeto, ctypes.cast(buffer, ctypes.POINTER(pdfium_c.FPDF_WCHAR)))
        return objeto

    def ancho(self, contenido: str) -> float:
        """Ancho real en puntos, medido por pdfium con el mismo tipo de letra."""
        if not contenido:
            return 0.0
        objeto = self._nuevo_texto(contenido)
        izq, abajo, der, arriba = (ctypes.c_float() for _ in range(4))
        pdfium_c.FPDFPageObj_GetBounds(objeto, izq, abajo, der, arriba)
        pdfium_c.FPDFPageObj_Destroy(objeto)
        return der.value - izq.value

    def texto(self, pagina, alto: float, x: float, y: float, contenido: str) -> None:
        if not contenido.strip():
            return
        objeto = self._nuevo_texto(contenido)
        pdfium_c.FPDFPageObj_Transform(objeto, 1, 0, 0, 1, x, alto - y - _TAM_TEXTO)
        pdfium_c.FPDFPage_InsertObject(pagina.raw, objeto)

    def linea(self, pagina, alto: float, x0: float, y0: float, x1: float, y1: float) -> None:
        camino = pdfium_c.FPDFPageObj_CreateNewPath(ctypes.c_float(x0), ctypes.c_float(alto - y0))
        pdfium_c.FPDFPath_LineTo(camino, ctypes.c_float(x1), ctypes.c_float(alto - y1))
        pdfium_c.FPDFPageObj_SetStrokeWidth(camino, ctypes.c_float(0.5))
        pdfium_c.FPDFPath_SetDrawMode(camino, pdfium_c.FPDF_FILLMODE_NONE, True)
        pdfium_c.FPDFPage_InsertObject(pagina.raw, camino)


def _normalizar_filas(filas: list[list]) -> list[list[str]]:
    columnas = max(len(f) for f in filas)
    return [[str(c) if c is not None else "" for c in f] + [""] * (columnas - len(f)) for f in filas]


def generar_pdf_reconocido(paginas: list[dict]) -> bytes:
    """`paginas`: la salida cacheada de `app.extraccion.ocr` -- cada una con
    `numero` y `bloques` (`{"tipo": "texto"|"tabla", "texto", "filas"}`), en
    orden. Las páginas que falten (documento leído solo en parte) salen en
    blanco, para conservar la numeración."""
    escritor = _Escritor()
    por_numero = {p["numero"]: p for p in paginas}
    total = max(por_numero, default=0)
    for numero in range(1, total + 1):
        bloques = (por_numero.get(numero) or {}).get("bloques") or []
        preparados = []
        ancho = _ANCHO_A4
        alto = 2 * _MARGEN
        for bloque in bloques:
            if bloque.get("tipo") == "tabla" and bloque.get("filas"):
                filas = _normalizar_filas(bloque["filas"])
                partidas = [[_partir(c, _MAX_CARACTERES_COLUMNA) for c in fila] for fila in filas]
                anchos = [
                    max(escritor.ancho(l) for fila in partidas for l in fila[i]) + 2 * _RELLENO_CELDA + 2
                    for i in range(len(filas[0]))
                ]
                altos = [max(len(c) for c in fila) * _alto_linea() + 2 * _RELLENO_CELDA for fila in partidas]
                ancho = max(ancho, sum(anchos) + 2 * _MARGEN)
                alto += sum(altos) + _alto_linea()
                preparados.append(("tabla", anchos, partidas, altos))
            else:
                lineas = _partir(bloque.get("texto") or "", _MAX_CARACTERES_TEXTO)
                alto += len(lineas) * _alto_linea() + _alto_linea() / 2
                preparados.append(("texto", lineas))
        alto = max(alto, _ALTO_A4)
        pagina = escritor.documento.new_page(ancho, alto)
        y = _MARGEN
        for preparado in preparados:
            if preparado[0] == "tabla":
                _, anchos, partidas, altos = preparado
                bordes = [_MARGEN]
                for a in anchos:
                    bordes.append(bordes[-1] + a)
                y_inicio = y
                for fila, alto_fila in zip(partidas, altos):
                    escritor.linea(pagina, alto, bordes[0], y, bordes[-1], y)
                    for i, celda in enumerate(fila):
                        for k, contenido in enumerate(celda):
                            escritor.texto(
                                pagina, alto, bordes[i] + _RELLENO_CELDA, y + _RELLENO_CELDA + k * _alto_linea(), contenido
                            )
                    y += alto_fila
                escritor.linea(pagina, alto, bordes[0], y, bordes[-1], y)
                for x in bordes:
                    escritor.linea(pagina, alto, x, y_inicio, x, y)
                y += _alto_linea()
            else:
                for contenido in preparado[1]:
                    escritor.texto(pagina, alto, _MARGEN, y, contenido)
                    y += _alto_linea()
                y += _alto_linea() / 2
        pdfium_c.FPDFPage_GenerateContent(pagina.raw)
    salida = io.BytesIO()
    escritor.documento.save(salida)
    return salida.getvalue()
