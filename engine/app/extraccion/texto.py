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
from typing import BinaryIO, Callable

import pdfplumber
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class PaginaTexto:
    """Una página con su texto. `numero` es 1-indexado: es el número de
    página que se ancla en `documentos.pagina` / `trazas_origen.pagina`
    (CONTEXTO.md sección 9.10), no un índice de lista."""

    numero: int
    texto: str


def extraer_texto(ruta_pdf: str | Path | BinaryIO) -> list[PaginaTexto]:
    """Extrae el texto de cada página de un PDF con capa de texto. Sin
    caché: perfil real de la sesión de rendimiento (bloque 4, `docs/sesion-
    2026-09-12-defecto-mapeo-calidad-interfaz-rendimiento.md`) midió que esto
    es ~99% del tiempo de un reproceso -- para un documento ya visto antes,
    usa `extraer_texto_cacheado`, que envuelve esta misma función."""
    paginas: list[PaginaTexto] = []
    with pdfplumber.open(ruta_pdf) as pdf:
        for indice, pagina in enumerate(pdf.pages, start=1):
            paginas.append(PaginaTexto(numero=indice, texto=pagina.extract_text() or ""))
    return paginas


# Bloque 6, sesión de rendimiento: sube este valor cuando un cambio en
# `extraer_texto` (o en cómo se llama a `pdfplumber`) deba invalidar todo el
# texto ya cacheado -- una fila con una versión distinta a esta se trata
# como caché ausente y se recalcula, sin necesidad de borrar nada a mano
# (mismo mecanismo que `app.mantenimiento.frescura.VERSION_LOGICA_EXTRACCION`,
# pero para esta caché concreta: cambiar cómo se clasifica un documento o
# cómo se arma una línea de catálogo no debería invalidar texto ya extraído
# correctamente, y viceversa).
VERSION_LOGICA_TEXTO = "2026-09-13.1"


def extraer_texto_cacheado(
    db: Session, documento_hash: str, obtener_pdf: Callable[[], str | Path | BinaryIO]
) -> list[PaginaTexto]:
    """Envuelve `extraer_texto` con una caché persistente por hash de
    documento (`CacheTextoDocumento`, migración 0029): un documento ya
    descargado y sin cambios no vuelve a pagar el coste de `pdfplumber`
    en cada reproceso -- solo el primero. Clave por CONTENIDO
    (`Documento.hash`), no por id ni por ruta: el mismo documento físico
    puede vivir bajo más de un `Documento` si algún día se rompe la
    deduplicación por hash, y esta caché no debe depender de que eso nunca
    pase para seguir siendo correcta.

    `obtener_pdf` es una función, no el PDF ya en mano: en un acierto de
    caché no hace falta ni siquiera leer el fichero del almacenamiento
    (`DocumentStorage.recuperar`), así que el llamador no paga esa lectura
    tampoco -- solo se invoca en un fallo de caché.

    Importa `app.models` aquí dentro (no al nivel del módulo) para no
    introducir una dependencia de `app.extraccion.texto` -> `app.models`
    en el camino de import de todo el paquete `app.extraccion`, que hoy no
    la necesita para nada más."""
    from app.models import CacheTextoDocumento

    cacheado = db.get(CacheTextoDocumento, documento_hash)
    if cacheado is not None and cacheado.version_logica_texto == VERSION_LOGICA_TEXTO:
        return [PaginaTexto(numero=p["numero"], texto=p["texto"]) for p in cacheado.paginas]

    paginas = extraer_texto(obtener_pdf())
    payload = [{"numero": p.numero, "texto": p.texto} for p in paginas]
    if cacheado is not None:
        cacheado.version_logica_texto = VERSION_LOGICA_TEXTO
        cacheado.num_paginas = len(paginas)
        cacheado.paginas = payload
    else:
        db.add(
            CacheTextoDocumento(
                documento_hash=documento_hash,
                version_logica_texto=VERSION_LOGICA_TEXTO,
                num_paginas=len(paginas),
                paginas=payload,
            )
        )
    db.commit()
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
