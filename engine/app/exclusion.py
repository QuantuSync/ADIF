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
- Una línea con el prefijo "INTERNO:" es un código interno completo
  ("INTERNO:24038") -- bloque 3, sesión 2026-09-09: el cliente propuso
  agrupar por código interno como criterio adicional (además de expediente y
  departamento) porque, agrupado así, el catálogo sale coherente por
  tipología de material (`docs/sesion-2026-09-09-...md`, correlación
  verificada contra el corpus real: 160/161 grupos con más de un expediente
  comparten la misma ESPECIALIDAD/DISCIPLINA del Excel de códigos). El
  prefijo es obligatorio porque un código interno y un departamento son las
  dos cadenas de solo dígitos que puede traer este fichero (ambos de 5
  cifras en el corpus real) -- sin distinguirlos, "24038" sería ambiguo
  entre "excluye el departamento 24038" (no existe, pero el fichero no lo
  sabe) y "excluye el código interno 24038". Mecanismo únicamente: qué
  código interno excluir, si alguno, lo decide el cliente, no esta sesión.
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
from app.extraccion.texto import normalizar

# Mismo patrón que `app.sindicacion.atom_parser._DEPARTAMENTO_RE`
# (CONTEXTO.md sección 20): "N.NN/DDDDD.NNNN" -> "DDDDD".
_DEPARTAMENTO_RE = re.compile(r"^\d+\.\d+/(\d+)\.")

_PREFIJO_INTERNO = "INTERNO:"


@dataclass(frozen=True)
class ExclusionExpedientes:
    codigos: frozenset[str] = field(default_factory=frozenset)
    departamentos: frozenset[str] = field(default_factory=frozenset)
    codigos_internos: frozenset[str] = field(default_factory=frozenset)

    def excluye(self, codigo_expediente: str, codigo_interno: Optional[str] = None) -> bool:
        normalizado = normalizar_codigo_expediente(codigo_expediente)
        if normalizado in self.codigos:
            return True
        if codigo_interno is not None and codigo_interno in self.codigos_internos:
            return True
        m = _DEPARTAMENTO_RE.match(normalizado or "")
        return m is not None and m.group(1) in self.departamentos

    def vacia(self) -> bool:
        return not self.codigos and not self.departamentos and not self.codigos_internos


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
    codigos_internos: set[str] = set()
    for linea in contenido.read_text(encoding="utf-8").splitlines():
        valor = linea.strip()
        if not valor or valor.startswith("#"):
            continue
        if valor.upper().startswith(_PREFIJO_INTERNO):
            codigo_interno = valor[len(_PREFIJO_INTERNO):].strip()
            if codigo_interno:
                codigos_internos.add(codigo_interno)
        elif "/" in valor:
            normalizado = normalizar_codigo_expediente(valor)
            if normalizado:
                codigos.add(normalizado)
        else:
            departamentos.add(valor)
    return ExclusionExpedientes(
        codigos=frozenset(codigos),
        departamentos=frozenset(departamentos),
        codigos_internos=frozenset(codigos_internos),
    )


@dataclass(frozen=True)
class ExclusionPalabrasTitulo:
    """Bloque 3, sesión de comparación documento-vs-listado interno: el
    cliente quiere excluir de la vista contratos que no son material
    (arrendamientos, gestión de residuos...) por una palabra o frase del
    título (`Expediente.nombre_proyecto`, CONTEXTO.md sección 7 -- el
    objeto del contrato tal como lo declara el propio documento, siempre
    presente con independencia del cruce con el Excel de códigos), sin
    dejar de descargarlos ni de guardarlos -- mismo criterio que
    `ExclusionExpedientes`: nunca en base de datos, nunca en las pantallas
    de gestión/revisión, solo en `/catalogo` y el Excel.

    `palabras` guarda el texto tal como está en el fichero (solo `strip()`),
    no ya normalizado -- lo necesita también `app.catalogo_consulta` para
    construir la condición SQL (`ilike` por cada palabra, mismo criterio de
    coincidencia por subcadena que el resto de filtros de texto de ese
    módulo). `excluye()` normaliza en el momento de comparar (sin acentos,
    minúsculas, `app.extraccion.texto.normalizar`) para el caso en que el
    fichero y el título del documento no coincidan en acentuación."""

    palabras: frozenset[str] = field(default_factory=frozenset)

    def excluye(self, nombre_proyecto: Optional[str]) -> bool:
        if not nombre_proyecto or not self.palabras:
            return False
        titulo_normalizado = normalizar(nombre_proyecto)
        return any(normalizar(palabra) in titulo_normalizado for palabra in self.palabras)

    def vacia(self) -> bool:
        return not self.palabras


_SIN_PALABRAS_TITULO = ExclusionPalabrasTitulo()


def cargar_exclusion_palabras_titulo(ruta: Optional[str]) -> ExclusionPalabrasTitulo:
    """Mismo formato y mismo criterio de lectura que `cargar_exclusiones`
    (sin caché, para que un cambio del cliente se vea en la siguiente
    exportación o la siguiente carga de `/catalogo` sin reiniciar nada):
    una palabra o frase por línea, líneas vacías y las que empiezan por "#"
    se ignoran. Sin ruta configurada, o con el fichero ausente/vacío, no
    excluye nada -- nunca lanza (mismo criterio que `cargar_exclusiones`)."""
    if not ruta:
        return _SIN_PALABRAS_TITULO
    camino = Path(ruta)
    if not camino.is_file():
        return _SIN_PALABRAS_TITULO
    palabras: set[str] = set()
    for linea in camino.read_text(encoding="utf-8").splitlines():
        valor = linea.strip()
        if not valor or valor.startswith("#"):
            continue
        palabras.add(valor)
    return ExclusionPalabrasTitulo(palabras=frozenset(palabras))
