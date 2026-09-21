"""Listado de expedientes en ejecución de ADIF, con su fecha de firma del acta
de inicio (bloque 2, sesión 2026-09-21).

**Procedencia, escrita aquí para que no haya que preguntarla.** Es el
**listado interno de ADIF** de sus expedientes en ejecución. Lo compartió Isa,
de ADIF, en el grupo de trabajo el **18/09/2026** y lo reenvió
ordenado el **21/09/2026**; esa versión es
`Ejemplo/Input/expedientes_en_ejecucion_adif_20260921.csv`. **No sale de la
Plataforma** ni de ningún sistema al que tengamos acceso: es su dato. Detalle
y cifras en `docs/expedientes-en-ejecucion-adif.md`.

**Qué trae.** Dos columnas, "Nº Expediente" y "Firma acta de inicio"
(DD/MM/AAAA, a veces en blanco). La versión del 21/09/2026: 121 expedientes,
112 del departamento 28510 y 9 de otros, que quedan fuera del alcance y no se
cargan.

**Qué hace.** Rellena tres campos propios del expediente
(`en_ejecucion_adif`, `acta_inicio_adif`, `en_ejecucion_adif_listado`), que la
hoja "Conciliación" muestra en su propia columna, "En ejecución según ADIF".
Cada carga **sustituye entera a la anterior**: un expediente que deja de
figurar en la versión nueva deja de mostrarse como en ejecución.

**Qué NO hace**, por las mismas razones que el listado de estados
(`app.extraccion.estados_adif`):

1. **No decide si un expediente consta publicado.** Eso se apoya solo en la
   Plataforma (`app.conciliacion.consta_publicado`). Criterio del cliente.
2. **No da de alta expedientes.** Los códigos que no existen en el sistema se
   cuentan y se devuelven; crearlos haría que la pregunta "¿cuáles de los suyos
   no tenemos?" se contestara sola.
3. **No escribe en `estado_adif` ni en `estado_contrato_sap`**: otra fuente,
   otro campo, para que cada valor conserve su procedencia.

**Versiones nuevas.** Cada una llega con su fecha en el nombre
(`expedientes_en_ejecucion_adif_AAAAMMDD.csv`). Se deja en `Ejemplo/Input`
(montada entera en `/data/entrada`, `EN_EJECUCION_ADIF_DIR`) y se ejecuta
`POST /mantenimiento/en-ejecucion-adif/cargar`: se carga la de fecha más
reciente. La lectura es tolerante con lo que puede cambiar al reenviar un
fichero: separador `;`, `,` o tabulador, UTF-8 o Windows-1252, y el nombre de
las columnas reconocido por contenido ("expediente"; "acta" o "firma").
"""
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.criterio_expediente import departamentos_configurados, fragmento_en_codigo
from app.extraccion.cruce_codigos import normalizar_codigo_expediente
from app.extraccion.texto import normalizar
from app.models import Expediente

PATRON_FICHERO = re.compile(r"^expedientes_en_ejecucion_adif_(\d{8})\.(csv|txt)$", re.IGNORECASE)

# Cuántos códigos sin expediente se devuelven en el resumen de la carga.
_MAX_CODIGOS_DEVUELTOS = 50


@dataclass(frozen=True)
class FilaEnEjecucion:
    codigo_expediente: str
    acta_inicio: Optional[date]


@dataclass
class ResumenCargaEnEjecucion:
    configurado: bool
    fichero: Optional[str] = None
    filas_leidas: int = 0
    filas_sin_codigo: int = 0
    otros_departamentos: int = 0
    del_departamento: int = 0
    sin_fecha_de_acta: int = 0
    cargados: int = 0
    sin_expediente_en_el_sistema: int = 0
    codigos_sin_expediente: list[str] = field(default_factory=list)
    codigos_otros_departamentos: list[str] = field(default_factory=list)
    fechas_no_legibles: list[str] = field(default_factory=list)
    retirados: int = 0


def elegir_fichero(carpeta: Optional[str]) -> Optional[Path]:
    """La versión de fecha más reciente de la carpeta, por la fecha de su
    nombre (no por la del sistema de ficheros, que cambia al copiar)."""
    if not carpeta:
        return None
    ruta = Path(carpeta)
    if not ruta.is_dir():
        return None
    candidatos = [
        (m.group(1), p) for p in ruta.iterdir() if p.is_file() and (m := PATRON_FICHERO.match(p.name))
    ]
    return max(candidatos)[1] if candidatos else None


def _decodificar(contenido: bytes) -> str:
    for codificacion in ("utf-8-sig", "cp1252"):
        try:
            return contenido.decode(codificacion)
        except UnicodeDecodeError:
            continue
    return contenido.decode("utf-8", errors="replace")


def _fecha(valor: str) -> Optional[date]:
    texto = (valor or "").strip()
    if not texto:
        return None
    for formato in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%y"):
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            continue
    raise ValueError(texto)


def leer_listado(contenido: bytes) -> tuple[list[FilaEnEjecucion], list[str], int]:
    """Las filas del listado, las fechas que no se han podido leer (se
    devuelven, nunca se inventan) y cuántas filas no traen código."""
    texto = _decodificar(contenido)
    try:
        dialecto = csv.Sniffer().sniff(texto.splitlines()[0] if texto else "", delimiters=";,\t")
        separador = dialecto.delimiter
    except csv.Error:
        separador = ";"
    lector = csv.reader(io.StringIO(texto), delimiter=separador)
    cabecera = [normalizar(c or "") for c in next(lector, [])]
    i_codigo = next((i for i, c in enumerate(cabecera) if "expediente" in c), 0)
    i_fecha = next((i for i, c in enumerate(cabecera) if "acta" in c or "firma" in c), 1)
    filas: list[FilaEnEjecucion] = []
    no_legibles: list[str] = []
    sin_codigo = 0
    for fila in lector:
        if not any((c or "").strip() for c in fila):
            continue
        codigo = normalizar_codigo_expediente(fila[i_codigo] if i_codigo < len(fila) else None)
        if not codigo:
            sin_codigo += 1
            continue
        crudo = fila[i_fecha] if i_fecha < len(fila) else ""
        try:
            acta = _fecha(crudo)
        except ValueError:
            no_legibles.append(f"{codigo}: {crudo.strip()}")
            acta = None
        filas.append(FilaEnEjecucion(codigo, acta))
    return filas, no_legibles, sin_codigo


def cargar_en_ejecucion_adif(db: Session, carpeta: Optional[str]) -> ResumenCargaEnEjecucion:
    fichero = elegir_fichero(carpeta)
    resumen = ResumenCargaEnEjecucion(configurado=bool(carpeta), fichero=fichero.name if fichero else None)
    if fichero is None:
        return resumen

    filas, resumen.fechas_no_legibles, resumen.filas_sin_codigo = leer_listado(fichero.read_bytes())
    resumen.filas_leidas = len(filas) + resumen.filas_sin_codigo
    departamentos = departamentos_configurados()

    # Cada carga sustituye entera a la anterior.
    anteriores = set(db.execute(select(Expediente.id).where(Expediente.en_ejecucion_adif.is_(True))).scalars())
    db.execute(
        update(Expediente)
        .where(Expediente.en_ejecucion_adif.is_(True))
        .values(en_ejecucion_adif=None, acta_inicio_adif=None, en_ejecucion_adif_listado=None)
    )
    cargados: set[int] = set()

    por_codigo = {e.codigo_expediente: e for e in db.execute(select(Expediente)).scalars()}
    for fila in filas:
        if departamentos and not any(fragmento_en_codigo(fila.codigo_expediente, d) for d in departamentos):
            resumen.otros_departamentos += 1
            resumen.codigos_otros_departamentos.append(fila.codigo_expediente)
            continue
        resumen.del_departamento += 1
        if fila.acta_inicio is None:
            resumen.sin_fecha_de_acta += 1
        expediente = por_codigo.get(fila.codigo_expediente)
        if expediente is None:
            resumen.sin_expediente_en_el_sistema += 1
            if len(resumen.codigos_sin_expediente) < _MAX_CODIGOS_DEVUELTOS:
                resumen.codigos_sin_expediente.append(fila.codigo_expediente)
            continue
        expediente.en_ejecucion_adif = True
        expediente.acta_inicio_adif = fila.acta_inicio
        expediente.en_ejecucion_adif_listado = fichero.name
        cargados.add(expediente.id)
    resumen.cargados = len(cargados)
    # Los que figuraban en la versión anterior y ya no figuran en esta.
    resumen.retirados = len(anteriores - cargados)
    db.commit()
    return resumen
