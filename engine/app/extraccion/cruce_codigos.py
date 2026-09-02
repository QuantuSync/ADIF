"""Cruce con el Excel de códigos (CLAUDE.md sección 7, "Cruce con el Excel
de códigos" y sección 16, "confirmar con el cliente..."): las tres primeras
columnas del catálogo — código interno, código de proyecto y código matriz —
salen de `Expedientes.xlsx` por clave exacta, nunca por similitud de nombre.

No usa modelo, no es una etapa de la cascada de extracción (CLAUDE.md sección
5): es una búsqueda determinista sobre un fichero de referencia, igual de
mecánica que un `JOIN`. El Excel se carga entero una vez por proceso (es un
fichero de unos pocos cientos de filas, sección 3) y se cachea en memoria por
ruta + fecha de modificación, para no releerlo en cada expediente.

"El sistema nunca inventa una matriz. Si no cruza, se deja vacío y se marca"
(sección 7): `CruceCodigos.cruzado` es la marca; ningún campo se rellena con
una suposición cuando es `False`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import openpyxl
from sqlalchemy.orm import Session

from app.config import settings

_ESPACIOS = re.compile(r"\s+")


@dataclass(frozen=True)
class CruceCodigos:
    codigo_interno: Optional[str]
    codigo_proyecto: Optional[str]
    codigo_matriz: Optional[str]
    cruzado: bool


def _normalizar_codigo(valor: Optional[str]) -> Optional[str]:
    """Recorta espacios sobrantes y unifica separadores (CLAUDE.md sección 8:
    "En el Excel hay valores como '6.25/28510.0146 '. Un cruce exacto fallaría
    en silencio.")."""
    if valor is None:
        return None
    limpio = _ESPACIOS.sub("", str(valor).strip())
    return limpio or None


class _IndiceCodigosProyecto:
    """Índice en memoria de `Expedientes.xlsx` (columnas `Nº Interno`,
    `Nº Expediente`, `MATRIZ`), por las dos claves por las que puede cruzar
    un código extraído (CLAUDE.md sección 3: "29 como Nº Expediente, 3 como
    MATRIZ")."""

    def __init__(self, filas: list[dict]):
        self._por_nexpediente: dict[str, dict] = {}
        self._por_matriz: dict[str, dict] = {}
        for fila in filas:
            clave_nexp = _normalizar_codigo(fila.get("Nº Expediente"))
            clave_matriz = _normalizar_codigo(fila.get("MATRIZ"))
            if clave_nexp and clave_nexp not in self._por_nexpediente:
                self._por_nexpediente[clave_nexp] = fila
            if clave_matriz and clave_matriz not in self._por_matriz:
                self._por_matriz[clave_matriz] = fila

    def buscar(self, codigo_expediente: str, codigo_matriz: Optional[str]) -> Optional[tuple[dict, bool]]:
        """Devuelve la fila encontrada junto con si el cruce fue por `Nº
        Expediente` (`True`) o por `MATRIZ` (`False`). La distinción importa:
        cuando `codigo_expediente` cruza por la columna MATRIZ (CLAUDE.md
        sección 3: "3 como MATRIZ"), significa que el propio expediente ES el
        acuerdo marco de esa fila — su columna MATRIZ vale, trivialmente, el
        propio `codigo_expediente` que se buscó. Devolver ese valor como "la
        matriz de este expediente" sería inventarla por auto-referencia
        (sección 7: "el sistema nunca inventa una matriz")."""
        for clave in (codigo_expediente, codigo_matriz):
            clave_normalizada = _normalizar_codigo(clave)
            if clave_normalizada is None:
                continue
            fila = self._por_nexpediente.get(clave_normalizada)
            if fila is not None:
                return fila, True
            fila = self._por_matriz.get(clave_normalizada)
            if fila is not None:
                return fila, False
        return None


_cache: dict[str, tuple[float, _IndiceCodigosProyecto]] = {}


def _cargar_indice(ruta_excel: str) -> _IndiceCodigosProyecto:
    ruta = Path(ruta_excel)
    mtime = ruta.stat().st_mtime
    entrada = _cache.get(ruta_excel)
    if entrada is not None and entrada[0] == mtime:
        return entrada[1]

    libro = openpyxl.load_workbook(ruta, read_only=True, data_only=True)
    hoja = libro.worksheets[0]
    filas_iter = hoja.iter_rows(values_only=True)
    cabecera = [str(c).strip() if c is not None else "" for c in next(filas_iter)]
    filas = [dict(zip(cabecera, fila)) for fila in filas_iter]
    libro.close()

    indice = _IndiceCodigosProyecto(filas)
    _cache[ruta_excel] = (mtime, indice)
    return indice


def cruzar_codigo_proyecto(
    ruta_excel: str, codigo_expediente: str, codigo_matriz: Optional[str] = None
) -> CruceCodigos:
    indice = _cargar_indice(ruta_excel)
    encontrado = indice.buscar(codigo_expediente, codigo_matriz)
    if encontrado is None:
        return CruceCodigos(codigo_interno=None, codigo_proyecto=None, codigo_matriz=None, cruzado=False)
    fila, coincide_por_nexpediente = encontrado

    nº_interno = fila.get("Nº Interno")
    return CruceCodigos(
        codigo_interno=str(nº_interno).strip() if nº_interno is not None else None,
        codigo_proyecto=_normalizar_codigo(fila.get("Nº Expediente")),
        # Solo cuando el cruce fue por Nº Expediente el campo MATRIZ de la
        # fila es información nueva (la matriz real de este expediente). Por
        # MATRIZ, ese campo es el propio codigo_expediente buscado (ver
        # docstring de `buscar`): no hay matriz que devolver.
        codigo_matriz=_normalizar_codigo(fila.get("MATRIZ")) if coincide_por_nexpediente else None,
        cruzado=True,
    )


def asegurar_cruce_codigos(db: Session, expediente) -> None:
    """Intenta el cruce una sola vez por expediente (`codigos_cruzados` pasa
    de `None` a `True`/`False`, nunca se repite) y deja la sesión con el
    cambio aplicado pero sin `commit` — lo hace la persona que llama, igual
    que el resto de mutaciones sobre `expediente` en esta cascada
    (CLAUDE.md sección 7: cruce por clave exacta, "el sistema nunca inventa
    una matriz"). Se usa tanto al terminar la extracción de un expediente
    como, de forma perezosa, sobre expedientes ya procesados antes de que
    existiera esta columna (routers de catálogo y de expedientes)."""
    if expediente.codigos_cruzados is not None:
        return
    if not settings.codigos_proyecto_path:
        return
    try:
        resultado = cruzar_codigo_proyecto(
            settings.codigos_proyecto_path, expediente.codigo_expediente, expediente.codigo_matriz
        )
    except FileNotFoundError:
        return
    expediente.codigos_cruzados = resultado.cruzado
    if resultado.cruzado:
        expediente.codigo_interno = resultado.codigo_interno
        if not expediente.codigo_matriz and resultado.codigo_matriz:
            expediente.codigo_matriz = resultado.codigo_matriz
