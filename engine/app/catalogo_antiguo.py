"""Cruce con el catálogo antiguo de materiales de ADIF.

Bloque 2 del encargo de la sesión 2026-09-19 (sexta parte). **El fichero no ha
llegado y su formato es desconocido** -- así lo dijo el cliente, con esas
palabras. Lo que hay montado aquí es la ingesta tolerante, el cruce y su
informe, probados sobre datos sintéticos, para que meterlo sea dejarlo en
`Ejemplo/Input` y ejecutar un comando (`docs/entradas-pendientes-del-cliente.md`).

**Formato desconocido quiere decir lectura por contenido, no adivinación.**
Se busca, en todas las hojas y en las primeras filas de cada una (el
encabezado puede no estar en la primera), una fila que nombre al menos una de
estas tres cosas: matrícula, descripción o precio. De ahí salen los índices de
columna. Si ninguna hoja los da, el informe sale con `formato_reconocido =
False` y **cero filas**: no se inventa un emparejamiento a partir de columnas
que no se sabe qué son.

**El emparejamiento es el que pidió el cliente**: por matrícula exacta
primero; **cuando no la haya**, por descripción normalizada (minúsculas, sin
acentos, sin puntuación, espacios colapsados). Nunca al revés y nunca las dos
a la vez: una matrícula que no casa no se intenta "salvar" por descripción --
sería la puerta trasera que CONTEXTO.md sección 7 cierra ("el cruce es por
clave exacta, no por similitud de nombre"); la descripción solo entra donde no
hay clave que comparar.

**El informe va aparte, nunca dentro del entregable** (condición explícita del
cliente): es un `.xlsx` propio, que se pide por su endpoint y no se guarda en
la base de datos.
"""
from __future__ import annotations

import io
import re
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Optional

import openpyxl
from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.catalogo_consulta import filtros_del_entregable
from app.exportacion import linea_sale_en_materiales
from app.extraccion.normalizacion import parsear_importe_es
from app.models import LineaCatalogo, Lote

# Palabras que nombran cada columna, comparadas sobre el encabezado
# normalizado y por contenido. Son las que el corpus real y los ficheros que
# ADIF ya nos ha enviado usan para lo mismo.
_PALABRAS_MATRICULA = ("matricula", "material", "referencia", "codigo adif", "cod. adif")
_PALABRAS_DESCRIPCION = ("descripcion", "denominacion", "designacion", "concepto", "texto breve")
_PALABRAS_PRECIO = ("precio", "importe", "valor")
# Deliberadamente fuera de la de precio: un importe total de pedido no es el
# precio unitario del material.
_PALABRAS_PRECIO_EXCLUIDAS = ("total", "pedido", "acumulad")

# Cuántas filas del principio de una hoja se miran buscando el encabezado. Un
# fichero de formato desconocido puede traer un título o un logotipo encima.
_FILAS_CABECERA = 10

_SIN_PUNTUACION_RE = re.compile(r"[^0-9a-z ]+")


class CatalogoAntiguoPathInvalida(RuntimeError):
    pass


def validar_ruta_catalogo_antiguo(ruta: Optional[str]) -> None:
    if not ruta:
        return
    camino = Path(ruta)
    if not camino.is_file():
        raise CatalogoAntiguoPathInvalida(
            f"CATALOGO_ANTIGUO_PATH={ruta!r} no es un fichero (¿bind-mount con el origen ausente?)"
        )
    try:
        libro = openpyxl.load_workbook(camino, read_only=True)
        libro.close()
    except Exception as exc:
        raise CatalogoAntiguoPathInvalida(
            f"CATALOGO_ANTIGUO_PATH={ruta!r} no se puede abrir como .xlsx: {exc}"
        ) from exc


def clave_descripcion(texto: Optional[str]) -> Optional[str]:
    """La descripción normalizada con la que se empareja cuando no hay
    matrícula: minúsculas, sin acentos, sin puntuación, espacios colapsados.
    `None` si no queda nada -- una cadena vacía emparejaría con cualquier
    otra vacía, que es justo lo que no se quiere."""
    if not texto:
        return None
    s = texto.lower()
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    s = _SIN_PUNTUACION_RE.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s or None


@dataclass(frozen=True)
class MaterialCatalogoAntiguo:
    matricula: Optional[str]
    descripcion: Optional[str]
    precio: Optional[Decimal]
    hoja: str
    fila: int


@dataclass
class ResumenCatalogoAntiguo:
    configurado: bool
    formato_reconocido: bool = False
    hojas_leidas: list[str] = field(default_factory=list)
    columnas: dict[str, Optional[int]] = field(default_factory=dict)
    materiales_suyos: int = 0
    materiales_nuestros: int = 0
    emparejados_por_matricula: int = 0
    emparejados_por_descripcion: int = 0
    solo_en_el_suyo: int = 0
    solo_en_el_nuestro: int = 0
    con_precio_distinto: int = 0

    def to_dict(self) -> dict:
        return {
            "configurado": self.configurado,
            "formato_reconocido": self.formato_reconocido,
            "hojas_leidas": self.hojas_leidas,
            "columnas": self.columnas,
            "materiales_suyos": self.materiales_suyos,
            "materiales_nuestros": self.materiales_nuestros,
            "emparejados_por_matricula": self.emparejados_por_matricula,
            "emparejados_por_descripcion": self.emparejados_por_descripcion,
            "solo_en_el_suyo": self.solo_en_el_suyo,
            "solo_en_el_nuestro": self.solo_en_el_nuestro,
            "con_precio_distinto": self.con_precio_distinto,
        }


def _indice(cabecera: list[str], palabras: tuple[str, ...], excluidas: tuple[str, ...] = ()) -> Optional[int]:
    candidatos = [
        indice
        for indice, texto in enumerate(cabecera)
        if any(p in texto for p in palabras) and not any(p in texto for p in excluidas)
    ]
    return candidatos[0] if candidatos else None


def _normalizar_cabecera(fila: tuple) -> list[str]:
    salida = []
    for celda in fila:
        if celda is None:
            salida.append("")
            continue
        s = str(celda).lower()
        s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
        salida.append(re.sub(r"\s+", " ", s).strip())
    return salida


def _precio(valor: object) -> Optional[Decimal]:
    if valor is None:
        return None
    if isinstance(valor, (int, float, Decimal)):
        try:
            return Decimal(str(valor))
        except (ValueError, ArithmeticError):
            return None
    try:
        return parsear_importe_es(str(valor))
    except (ValueError, ArithmeticError):
        return None


def leer_catalogo_antiguo(ruta_excel: str) -> tuple[list[MaterialCatalogoAntiguo], dict, list[str]]:
    """`(materiales, índices de columna, hojas leídas)`. Recorre todas las
    hojas y se queda con las que resuelven al menos una columna útil; una hoja
    de notas sin encabezado reconocible se salta sin ruido."""
    libro = openpyxl.load_workbook(ruta_excel, read_only=True, data_only=True)
    materiales: list[MaterialCatalogoAntiguo] = []
    columnas: dict[str, Optional[int]] = {}
    hojas: list[str] = []
    try:
        for hoja in libro.worksheets:
            filas = list(hoja.iter_rows(values_only=True))
            # La fila de encabezado es la que resuelve MÁS columnas de las
            # tres, no la primera que resuelve alguna: un título de portada
            # ("CATÁLOGO DE MATERIALES ADIF") contiene "material" y se llevaría
            # el puesto. A igualdad, la primera.
            encabezado = None
            mejor = 0
            for indice in range(min(_FILAS_CABECERA, len(filas))):
                cabecera = _normalizar_cabecera(filas[indice])
                i_matricula = _indice(cabecera, _PALABRAS_MATRICULA)
                i_descripcion = _indice(cabecera, _PALABRAS_DESCRIPCION)
                i_precio = _indice(cabecera, _PALABRAS_PRECIO, _PALABRAS_PRECIO_EXCLUIDAS)
                resueltas = sum(1 for i in (i_matricula, i_descripcion, i_precio) if i is not None)
                if (i_matricula is not None or i_descripcion is not None) and resueltas > mejor:
                    encabezado = (indice, i_matricula, i_descripcion, i_precio)
                    mejor = resueltas
            if encabezado is None:
                continue
            indice, i_matricula, i_descripcion, i_precio = encabezado
            hojas.append(hoja.title)
            if not columnas:
                columnas = {"matricula": i_matricula, "descripcion": i_descripcion, "precio": i_precio}
            for numero, fila in enumerate(filas[indice + 1:], start=indice + 2):
                def celda(i):
                    return fila[i] if i is not None and i < len(fila) else None

                matricula = celda(i_matricula)
                descripcion = celda(i_descripcion)
                if matricula is None and descripcion is None:
                    continue
                materiales.append(
                    MaterialCatalogoAntiguo(
                        matricula=str(matricula).strip() or None if matricula is not None else None,
                        descripcion=str(descripcion).strip() or None if descripcion is not None else None,
                        precio=_precio(celda(i_precio)),
                        hoja=hoja.title,
                        fila=numero,
                    )
                )
    finally:
        libro.close()
    return materiales, columnas, hojas


@dataclass(frozen=True)
class MaterialNuestro:
    matricula: Optional[str]
    descripcion: Optional[str]
    precio: Optional[Decimal]
    codigo_expediente: str
    lote: Optional[str]


def materiales_del_catalogo(db: Session) -> list[MaterialNuestro]:
    """Los materiales del entregable: mismos filtros y mismo criterio de
    inclusión que la hoja "Materiales" (`app.exportacion.linea_sale_en_materiales`),
    nunca una consulta propia -- si esto contara otra cosa, el informe diría
    que falta un material que el cliente sí tiene en su Excel."""
    salida: list[MaterialNuestro] = []
    consulta = filtros_del_entregable(select(LineaCatalogo)).outerjoin(
        Lote, LineaCatalogo.lote_id == Lote.id
    )
    for linea in db.execute(consulta).scalars():
        lote = db.get(Lote, linea.lote_id) if linea.lote_id else None
        if not linea_sale_en_materiales(linea, lote):
            continue
        salida.append(
            MaterialNuestro(
                matricula=linea.matricula,
                descripcion=linea.descripcion,
                precio=linea.precio_unitario,
                codigo_expediente=linea.expediente.codigo_expediente,
                lote=lote.identificador_lote if lote else None,
            )
        )
    return salida


@dataclass(frozen=True)
class DiferenciaPrecio:
    matricula: Optional[str]
    descripcion_suya: Optional[str]
    descripcion_nuestra: Optional[str]
    precio_suyo: Decimal
    precio_nuestro: Decimal
    diferencia: Decimal
    emparejado_por: str
    codigo_expediente: str
    lote: Optional[str]


@dataclass
class InformeCatalogoAntiguo:
    resumen: ResumenCatalogoAntiguo
    solo_en_el_suyo: list[MaterialCatalogoAntiguo] = field(default_factory=list)
    solo_en_el_nuestro: list[MaterialNuestro] = field(default_factory=list)
    diferencias_de_precio: list[DiferenciaPrecio] = field(default_factory=list)


EMPAREJADO_POR_MATRICULA = "matrícula"
EMPAREJADO_POR_DESCRIPCION = "descripción normalizada"


def comparar_con_catalogo_antiguo(db: Session, ruta_excel: Optional[str]) -> InformeCatalogoAntiguo:
    resumen = ResumenCatalogoAntiguo(configurado=bool(ruta_excel))
    informe = InformeCatalogoAntiguo(resumen=resumen)
    if not ruta_excel:
        return informe

    suyos, columnas, hojas = leer_catalogo_antiguo(ruta_excel)
    resumen.columnas = columnas
    resumen.hojas_leidas = hojas
    resumen.formato_reconocido = bool(suyos)
    resumen.materiales_suyos = len(suyos)
    if not suyos:
        return informe

    nuestros = materiales_del_catalogo(db)
    resumen.materiales_nuestros = len(nuestros)

    nuestros_por_matricula: dict[str, list[MaterialNuestro]] = {}
    nuestros_por_descripcion: dict[str, list[MaterialNuestro]] = {}
    for material in nuestros:
        if material.matricula:
            nuestros_por_matricula.setdefault(material.matricula.strip(), []).append(material)
        clave = clave_descripcion(material.descripcion)
        if clave:
            nuestros_por_descripcion.setdefault(clave, []).append(material)

    emparejados_nuestros: set[int] = set()
    for suyo in suyos:
        candidatos: list[MaterialNuestro] = []
        emparejado_por = ""
        if suyo.matricula:
            candidatos = nuestros_por_matricula.get(suyo.matricula.strip(), [])
            emparejado_por = EMPAREJADO_POR_MATRICULA
        if not candidatos and not suyo.matricula:
            clave = clave_descripcion(suyo.descripcion)
            candidatos = nuestros_por_descripcion.get(clave, []) if clave else []
            emparejado_por = EMPAREJADO_POR_DESCRIPCION
        if not candidatos:
            informe.solo_en_el_suyo.append(suyo)
            resumen.solo_en_el_suyo += 1
            continue
        if emparejado_por == EMPAREJADO_POR_MATRICULA:
            resumen.emparejados_por_matricula += 1
        else:
            resumen.emparejados_por_descripcion += 1
        for nuestro in candidatos:
            emparejados_nuestros.add(id(nuestro))
            if suyo.precio is None or nuestro.precio is None:
                continue
            diferencia = Decimal(suyo.precio) - Decimal(nuestro.precio)
            if diferencia == 0:
                continue
            informe.diferencias_de_precio.append(
                DiferenciaPrecio(
                    matricula=suyo.matricula,
                    descripcion_suya=suyo.descripcion,
                    descripcion_nuestra=nuestro.descripcion,
                    precio_suyo=Decimal(suyo.precio),
                    precio_nuestro=Decimal(nuestro.precio),
                    diferencia=diferencia,
                    emparejado_por=emparejado_por,
                    codigo_expediente=nuestro.codigo_expediente,
                    lote=nuestro.lote,
                )
            )
    informe.diferencias_de_precio.sort(key=lambda d: (-abs(d.diferencia), d.codigo_expediente))
    resumen.con_precio_distinto = len(informe.diferencias_de_precio)

    informe.solo_en_el_nuestro = [m for m in nuestros if id(m) not in emparejados_nuestros]
    resumen.solo_en_el_nuestro = len(informe.solo_en_el_nuestro)
    return informe


def generar_informe_catalogo_antiguo(informe: InformeCatalogoAntiguo) -> bytes:
    """El informe, **aparte del entregable**: su propio fichero, con una hoja
    por pregunta y una de resumen."""
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Solo en el catálogo de ADIF"
    hoja.append(["Matrícula", "Descripción", "Precio", "Hoja de origen", "Fila de origen"])
    for m in informe.solo_en_el_suyo:
        hoja.append([m.matricula, m.descripcion, m.precio, m.hoja, m.fila])

    hoja = libro.create_sheet("Solo en el nuestro")
    hoja.append(["Matrícula", "Descripción", "Precio unitario", "Código de expediente", "Lote"])
    for m in informe.solo_en_el_nuestro:
        hoja.append([m.matricula, m.descripcion, m.precio, m.codigo_expediente, m.lote])

    hoja = libro.create_sheet("Diferencias de precio")
    hoja.append([
        "Matrícula", "Descripción en su catálogo", "Descripción en el nuestro", "Precio en su catálogo",
        "Precio en el nuestro", "Diferencia (suyo − nuestro)", "Emparejado por", "Código de expediente", "Lote",
    ])
    for d in informe.diferencias_de_precio:
        hoja.append([
            d.matricula, d.descripcion_suya, d.descripcion_nuestra, d.precio_suyo, d.precio_nuestro,
            d.diferencia, d.emparejado_por, d.codigo_expediente, d.lote,
        ])

    hoja = libro.create_sheet("Resumen")
    hoja.append(["Concepto", "Valor"])
    for clave, valor in informe.resumen.to_dict().items():
        hoja.append([clave, valor if not isinstance(valor, (list, dict)) else str(valor)])
    hoja.append([])
    hoja.append([
        "El emparejamiento es por matrícula exacta; solo los materiales de su catálogo que no traen "
        "matrícula se intentan por descripción normalizada. Una matrícula que no casa NO se reintenta por "
        "descripción: sería un cruce por parecido de nombre, que es justo lo que este sistema no hace.",
        None,
    ])

    buffer = io.BytesIO()
    libro.save(buffer)
    return buffer.getvalue()
