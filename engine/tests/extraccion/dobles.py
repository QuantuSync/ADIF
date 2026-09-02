"""Test doubles para `ModelProvider`, usados solo en tests: nunca hay
llamada de red real. Con las cabeceras reales de los dos anejos de fixture,
el mapeo determinista ya resuelve todo (ver test_mapeo_cabecera.py y
test_pipeline_anejo.py) — estos dobles sirven para ejercitar el camino "cae
al modelo" de `mapear_cabecera` con una cabecera sintética que el mapeo
determinista no puede resolver."""
from __future__ import annotations

import ast
import re
from typing import Any, Optional

from app.interfaces.model_provider import ModelProvider


class ProveedorModeloFalso(ModelProvider):
    def __init__(self, respuesta: dict):
        self._respuesta = respuesta
        self.llamadas = 0
        self.prompts: list[str] = []

    def completar(self, prompt: str, esquema: Optional[dict] = None) -> Any:
        self.llamadas += 1
        self.prompts.append(prompt)
        return dict(self._respuesta)


class ProveedorModeloCabeceraPorContenido(ModelProvider):
    """Doble para cabeceras reales que la extracción corrompe (un carácter
    acentuado roto, CLAUDE.md sección 17.2) o desplaza (columnas fantasma,
    sección 3): a diferencia de `ProveedorModeloFalso`, que devuelve siempre
    la misma respuesta fija, este doble lee la lista de columnas del propio
    prompt (`app.extraccion.mapeo_cabecera._construir_prompt` ya las numera)
    y las empareja por palabra clave — lo mismo que haría el modelo real con
    una cabecera legible pese a la corrupción de un carácter.

    Hallazgo real sobre el expediente 6.25/28510.0027 (fixture
    `ANEJO_PRECIOS_BALASTO_MULTI_LOTE`): en algunas de sus tablas la columna
    fantasma de la cabecera combinada NO cae en el mismo índice que la
    columna vacía de las filas de datos — `pdfplumber` alinea la cabecera y
    los datos de forma distinta dentro de la misma tabla. Un emparejamiento
    por texto de cabecera a secas apuntaría entonces a una columna vacía. El
    modelo real resuelve esto mirando también las filas de ejemplo que ya
    trae el prompt (CLAUDE.md sección 6: "dos o tres filas de ejemplo para
    desambiguar"); este doble hace lo mismo para los campos numéricos
    (`cantidad`, `precio_unitario`): si la columna que eligió por palabra
    clave sale vacía en las tres filas de ejemplo, prueba la columna vecina
    con contenido numérico antes de rendirse."""

    _CLAVES: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("codigo_precio", ("CODIFICAC", "CODIGO")),
        ("descripcion", ("DESCRIPCI",)),
        ("unidad_medida", ("UNIDADES", "UNIDAD")),
        ("cantidad", ("CANTIDAD",)),
        ("precio_unitario", ("PRECIO",)),
    )
    _CAMPOS_NUMERICOS = ("cantidad", "precio_unitario")

    def __init__(self):
        self.llamadas = 0
        self.prompts: list[str] = []

    def completar(self, prompt: str, esquema: Optional[dict] = None) -> Any:
        self.llamadas += 1
        self.prompts.append(prompt)

        columnas = {int(i): texto for i, texto in re.findall(r"^  (\d+): (.+)$", prompt, re.MULTILINE)}
        filas_ejemplo = [
            ast.literal_eval(linea)
            for linea in re.findall(r"^  (\[.*\])$", prompt, re.MULTILINE)
        ]

        mapeo: dict[str, Optional[int]] = {"matricula": None}
        for campo, _ in self._CLAVES:
            mapeo[campo] = None
        for indice, texto in columnas.items():
            texto_mayus = texto.upper()
            for campo, claves in self._CLAVES:
                if mapeo[campo] is None and any(clave in texto_mayus for clave in claves):
                    mapeo[campo] = indice
                    break

        def _con_contenido(indice: int) -> bool:
            return any(
                indice < len(fila) and fila[indice] not in (None, "")
                for fila in filas_ejemplo
            )

        usados = {i for i in mapeo.values() if i is not None}
        for campo in self._CAMPOS_NUMERICOS:
            indice = mapeo[campo]
            if indice is not None and filas_ejemplo and not _con_contenido(indice):
                for vecino in (indice - 1, indice + 1):
                    if vecino in columnas and vecino not in usados and _con_contenido(vecino):
                        mapeo[campo] = vecino
                        usados.add(vecino)
                        break

        return mapeo


class ProveedorModeloContador(ModelProvider):
    """Envuelve otro `ModelProvider` y cuenta cuántas veces se le llama de
    verdad — para probar `CachedModelProvider` sin tocar la red."""

    def __init__(self, interior: ModelProvider):
        self._interior = interior
        self.llamadas = 0

    def completar(self, prompt: str, esquema: Optional[dict] = None) -> Any:
        self.llamadas += 1
        return self._interior.completar(prompt, esquema)
