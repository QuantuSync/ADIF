"""Lectura de texto de PDF, página a página.

CLAUDE.md sección 3: ningún documento del corpus está escaneado, todos tienen
capa de texto — no hace falta OCR ni modelo multimodal para esta etapa.
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
    (CLAUDE.md sección 9.10), no un índice de lista."""

    numero: int
    texto: str


def extraer_texto(ruta_pdf: str | Path) -> list[PaginaTexto]:
    """Extrae el texto de cada página de un PDF con capa de texto."""
    paginas: list[PaginaTexto] = []
    with pdfplumber.open(ruta_pdf) as pdf:
        for indice, pagina in enumerate(pdf.pages, start=1):
            paginas.append(PaginaTexto(numero=indice, texto=pagina.extract_text() or ""))
    return paginas


def normalizar(texto: str) -> str:
    """Minúsculas, sin acentos, espacios colapsados. Para *comparar* texto
    (buscar marcadores), nunca para guardarlo: el valor guardado siempre es
    el fragmento original (CLAUDE.md sección 8, "el modelo devuelve el
    literal, tu código normaliza" aplica igual al código determinista)."""
    s = texto.lower()
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s).strip()
