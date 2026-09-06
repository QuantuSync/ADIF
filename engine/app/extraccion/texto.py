"""Lectura de texto de PDF, página a página.

CONTEXTO.md sección 3: 186 de los 187 documentos del corpus tienen capa de
texto — no hace falta OCR ni modelo multimodal para leerlos. El documento
número 187 (`6.20/28510.0136_ANEJO_2.pdf`, 100 páginas) es la excepción
confirmada (sesión de expedientes sin publicar): cada página es una imagen a
página completa sin ningún carácter de texto, ni con `pdfplumber` ni con
`pypdf`. `es_documento_escaneado` detecta ese caso para que el motivo de
revisión lo diga explícitamente ("documento escaneado, sin capa de texto"),
en vez de confundirse con "no se extrajo ninguna línea de catálogo" — son
diagnósticos distintos: el primero dice "no se puede leer este documento con
las herramientas actuales", el segundo dice "se leyó pero no traía cuadro de
precios".

Usamos pdfplumber también para el texto plano (y no solo para tablas, sección
6) porque es la dependencia de lectura que ya trae el proyecto para los
cuadros de precios; mantener una sola vía de lectura evita que el texto y las
tablas de una misma página se extraigan con dos herramientas que puedan
discrepar en el número de página o en la codificación.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import pdfplumber


@dataclass(frozen=True)
class PaginaTexto:
    """Una página con su texto. `numero` es 1-indexado: es el número de
    página que se ancla en `documentos.pagina` / `trazas_origen.pagina`
    (CONTEXTO.md sección 9.10), no un índice de lista."""

    numero: int
    texto: str


def extraer_texto(ruta_pdf: str | Path) -> list[PaginaTexto]:
    """Extrae el texto de cada página de un PDF con capa de texto."""
    paginas: list[PaginaTexto] = []
    with pdfplumber.open(ruta_pdf) as pdf:
        for indice, pagina in enumerate(pdf.pages, start=1):
            paginas.append(PaginaTexto(numero=indice, texto=pagina.extract_text() or ""))
    return paginas


# Umbral, no cero exacto: deja margen a un artefacto suelto de extracción
# (un carácter de pie de página mal decodificado) sin dejar de detectar el
# caso real verificado -- 0 caracteres en las 100 páginas de
# `6.20/28510.0136_ANEJO_2.pdf`, confirmado con `pdfplumber` y `pypdf` a la
# vez, cada página una imagen a página completa. Ningún documento no
# escaneado del corpus real se acerca a este umbral: el más pobre en texto
# de los 186 restantes tiene páginas enteras de tabla o de prosa.
UMBRAL_CARACTERES_DOCUMENTO_ESCANEADO = 10


def es_documento_escaneado(paginas: list[PaginaTexto]) -> bool:
    """Un documento con páginas pero prácticamente sin texto extraíble es,
    con toda probabilidad, un PDF escaneado (imagen, sin capa de texto) —
    distinto de un documento vacío por no tener páginas en absoluto, que no
    es este caso."""
    if not paginas:
        return False
    total_caracteres = sum(len(p.texto.strip()) for p in paginas)
    return total_caracteres < UMBRAL_CARACTERES_DOCUMENTO_ESCANEADO


def normalizar(texto: str) -> str:
    """Minúsculas, sin acentos, espacios colapsados. Para *comparar* texto
    (buscar marcadores), nunca para guardarlo: el valor guardado siempre es
    el fragmento original (CONTEXTO.md sección 8, "el modelo devuelve el
    literal, tu código normaliza" aplica igual al código determinista)."""
    s = texto.lower()
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s).strip()
