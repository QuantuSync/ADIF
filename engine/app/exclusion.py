"""Lista de exclusión de expedientes (bloque 5, cambios del cliente tras
revisar el catálogo): el cliente quitaba a mano, en cada exportación,
expedientes que no son de su equipo -- y volvían a aparecer en la
siguiente, porque el Excel es una vista generada y nunca guarda ediciones
manuales (CONTEXTO.md sección 9.8). El encargo explícito era que fuera
"fácil de mantener sin tocar código": mismo mecanismo que
`app.extraccion.cruce_codigos`/`app.extraccion.estado_sap` (una ruta de
fichero configurable por variable de entorno, `EXCLUSION_EXPEDIENTES_PATH`),
pero un simple fichero de texto en vez de un Excel -- no hace falta ninguna
columna ni hoja para una lista de códigos.

Formato del fichero, una entrada por línea:
- Una línea con "/" es un código de expediente exacto ("6.24/28510.0088").
- Una línea de solo dígitos es un departamento completo ("28520") -- mismo
  segmento que ya usa `app.sindicacion.atom_parser.EntradaSindicacion.
  departamento" ("6.24/28510.0088" -> "28510").
- Líneas vacías y las que empiezan por "#" se ignoran (comentarios).

Se excluye del Excel entregado y del catálogo de la web (`app.catalogo_
consulta.consultar_catalogo`, usado por los dos, CONTEXTO.md: "una sola
implementación, nunca una copia") -- nunca de la base de datos ni de las
pantallas de gestión/revisión, donde el cliente sigue necesitando verlos y
poder reincluirlos quitando la línea del fichero."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from app.extraccion.cruce_codigos import normalizar_codigo_expediente

# Mismo patrón que `app.sindicacion.atom_parser._DEPARTAMENTO_RE`
# (CONTEXTO.md sección 20): "N.NN/DDDDD.NNNN" -> "DDDDD".
_DEPARTAMENTO_RE = re.compile(r"^\d+\.\d+/(\d+)\.")


@dataclass(frozen=True)
class ExclusionExpedientes:
    codigos: frozenset[str] = field(default_factory=frozenset)
    departamentos: frozenset[str] = field(default_factory=frozenset)

    def excluye(self, codigo_expediente: str) -> bool:
        normalizado = normalizar_codigo_expediente(codigo_expediente)
        if normalizado in self.codigos:
            return True
        m = _DEPARTAMENTO_RE.match(normalizado or "")
        return m is not None and m.group(1) in self.departamentos

    def vacia(self) -> bool:
        return not self.codigos and not self.departamentos


_SIN_EXCLUSIONES = ExclusionExpedientes()


def cargar_exclusiones(ruta: Optional[str]) -> ExclusionExpedientes:
    """Lectura directa del fichero en cada llamada, sin caché: es un
    fichero de texto pequeño (decenas de líneas, no miles), y el precio de
    releerlo siempre es la garantía de que un cambio del cliente se ve en
    la siguiente exportación o la siguiente carga de `/catalogo`, sin
    reiniciar nada -- el mismo motivo por el que `app.extraccion.
    cruce_codigos` no cachea el Excel de códigos entre trabajos. Sin ruta
    configurada, o con el fichero ausente/vacío, no excluye nada -- nunca
    lanza (mismo criterio que `codigos_proyecto_path`: una fuente de
    entrada opcional que degrada a "no hace nada" en vez de romper el
    resto del sistema)."""
    if not ruta:
        return _SIN_EXCLUSIONES
    contenido = Path(ruta)
    if not contenido.is_file():
        return _SIN_EXCLUSIONES
    codigos: set[str] = set()
    departamentos: set[str] = set()
    for linea in contenido.read_text(encoding="utf-8").splitlines():
        valor = linea.strip()
        if not valor or valor.startswith("#"):
            continue
        if "/" in valor:
            normalizado = normalizar_codigo_expediente(valor)
            if normalizado:
                codigos.add(normalizado)
        else:
            departamentos.add(valor)
    return ExclusionExpedientes(codigos=frozenset(codigos), departamentos=frozenset(departamentos))
