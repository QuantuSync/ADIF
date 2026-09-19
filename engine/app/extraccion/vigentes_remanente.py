"""Los contratos vigentes con remanente que ADIF tiene que enviarnos.

Bloque 2 del encargo de la sesión 2026-09-19 (sexta parte). **El fichero no
ha llegado todavía** y no se inventa: lo que hay aquí es la ingesta, el cruce
y la salida ya montados y probados sobre datos sintéticos, para que meterlo
sea dejarlo en `Ejemplo/Input` y ejecutar un comando (ver
`docs/entradas-pendientes-del-cliente.md`).

**Lo que se sabe del fichero** (sesión 2026-09-19, tercera parte, bloque 2):
lo llaman `EXPEDIENTES_VIGENTES_CON_REMANENTE.xlsx` y son **83 contratos
vigentes con remanente**. Nada más. No sabemos qué columnas trae ni cómo se
llaman, así que la lectura es **tolerante y explícita**, nunca adivinatoria:

1. Si alguna hoja tiene una columna cuyo encabezado, normalizado, contiene
   "expediente" (o "contrato"), esa es la columna de códigos.
2. Si ninguna la tiene, se busca **una sola** columna cuyos valores tengan
   forma de código de expediente de ADIF en la mayoría de sus filas. Con cero
   o con más de una, no se adivina.
3. Si tampoco, la carga termina con `formato_no_reconocido` y **no toca
   nada**: ni da de alta expedientes, ni encola búsquedas, ni escribe en la
   base de datos.

El cruce responde lo que pidió el cliente: **para cada uno, su Situación en
la Conciliación**; y **los que no están en la Conciliación se buscan en la
Plataforma**. Esa búsqueda es la vía normal del sistema (un trabajo
`descargar_expediente` de la cola, que encadena su extracción si encuentra
algo), y para poder encolarla hace falta que el expediente exista: por eso
este módulo **sí da de alta** el que no tenga, a diferencia de
`app.extraccion.estados_adif`. No es una contradicción con aquella regla: allí
el alta falsearía la pregunta "¿cuáles de los suyos nos faltan?"; aquí la
pregunta que el cliente hace es justo la contraria -- "¿qué sabemos de estos
83?" --, y no se puede contestar sin buscarlos. Aun así se puede pedir el
cruce sin tocar la red (`buscar=False`), que es como corre en las pruebas.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import openpyxl
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.conciliacion import FilaConciliacion
from app.extraccion.cruce_codigos import normalizar_codigo_expediente
from app.extraccion.texto import normalizar
from app.models import EstadoExpediente, Expediente
from app.queue import encolar_trabajo

# Encabezados que nombran la columna de códigos. Se comparan normalizados y
# por contenido, no por igualdad: el fichero no existe todavía y su
# encabezado exacto no se puede saber ("Expediente", "Expediente ADIF", "Nº de
# expediente", "Contrato"...).
_ENCABEZADOS_CODIGO = ("expediente", "contrato")

# La forma de un código de expediente de ADIF, en las dos escrituras que el
# corpus real usa: `6.24/28510.0088` y `28510/2023`. Se exige la barra: sin
# ella, cualquier columna de números pasaría por código.
_FORMA_CODIGO_RE = re.compile(r"^\s*\d{1,2}\.\d{2}\s*/\s*\d{4,6}[A-Za-z]?\.?\d{0,4}\s*$|^\s*\d{4,6}[A-Za-z]?\s*/\s*\d{4}\s*$")

# Con menos de esta proporción de valores con forma de código, una columna sin
# encabezado reconocible no se acepta como la de expedientes.
_MINIMO_VALORES_CON_FORMA = 0.6


class VigentesRemanentePathInvalida(RuntimeError):
    """Mismo criterio que el resto de fuentes de entrada permanentes: fallar
    de forma visible al validar la ruta, no dejar la carga rota para el primer
    intento real."""


def validar_ruta_vigentes_remanente(ruta: Optional[str]) -> None:
    if not ruta:
        return
    camino = Path(ruta)
    if not camino.is_file():
        raise VigentesRemanentePathInvalida(
            f"VIGENTES_REMANENTE_PATH={ruta!r} no es un fichero (¿bind-mount con el origen ausente?)"
        )
    try:
        libro = openpyxl.load_workbook(camino, read_only=True)
        libro.close()
    except Exception as exc:
        raise VigentesRemanentePathInvalida(
            f"VIGENTES_REMANENTE_PATH={ruta!r} no se puede abrir como .xlsx: {exc}"
        ) from exc


@dataclass
class FilaVigenteRemanente:
    codigo_expediente: str
    en_el_sistema: bool
    en_la_conciliacion: bool
    situacion: Optional[str]
    motivo: Optional[str]
    estado_sistema: Optional[str]
    lineas_en_catalogo: Optional[int]
    # Solo para los que no están en la Conciliación: qué se ha hecho con
    # ellos ("buscado en la Plataforma", "dado de alta y buscado",
    # "búsqueda no solicitada", "la Plataforma ya confirmó que no lo publica").
    accion: str

    def to_dict(self) -> dict:
        return {
            "codigo_expediente": self.codigo_expediente,
            "en_el_sistema": self.en_el_sistema,
            "en_la_conciliacion": self.en_la_conciliacion,
            "situacion": self.situacion,
            "motivo": self.motivo,
            "estado_sistema": self.estado_sistema,
            "lineas_en_catalogo": self.lineas_en_catalogo,
            "accion": self.accion,
        }


ACCION_EN_LA_CONCILIACION = "está en la Conciliación"
ACCION_BUSCADO = "buscado en la Plataforma"
ACCION_ALTA_Y_BUSCADO = "dado de alta y buscado en la Plataforma"
ACCION_SIN_BUSCAR = "búsqueda no solicitada en esta llamada"


@dataclass
class ResumenVigentesRemanente:
    configurado: bool
    formato_reconocido: bool = False
    # Cómo se localizó la columna de códigos: "encabezado" | "contenido" |
    # "no encontrada". Va en el resumen para que quien lea el resultado sepa
    # si el fichero llegó con la forma esperada o si hubo que deducirla.
    columna_localizada_por: str = "no encontrada"
    hoja: Optional[str] = None
    filas_leidas: int = 0
    codigos_distintos: int = 0
    en_la_conciliacion: int = 0
    fuera_de_la_conciliacion: int = 0
    dados_de_alta: int = 0
    busquedas_encoladas: int = 0
    por_situacion: dict[str, int] = field(default_factory=dict)
    filas: list[FilaVigenteRemanente] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "configurado": self.configurado,
            "formato_reconocido": self.formato_reconocido,
            "columna_localizada_por": self.columna_localizada_por,
            "hoja": self.hoja,
            "filas_leidas": self.filas_leidas,
            "codigos_distintos": self.codigos_distintos,
            "en_la_conciliacion": self.en_la_conciliacion,
            "fuera_de_la_conciliacion": self.fuera_de_la_conciliacion,
            "dados_de_alta": self.dados_de_alta,
            "busquedas_encoladas": self.busquedas_encoladas,
            "por_situacion": self.por_situacion,
            "filas": [f.to_dict() for f in self.filas],
        }


def _encabezado_de_codigos(cabecera: list[object]) -> Optional[int]:
    for indice, celda in enumerate(cabecera):
        if celda is None:
            continue
        texto = normalizar(str(celda))
        if any(palabra in texto for palabra in _ENCABEZADOS_CODIGO):
            return indice
    return None


def _columna_por_contenido(filas: list[tuple]) -> Optional[int]:
    """La única columna cuyos valores tienen forma de código de expediente en
    la mayoría de las filas. Con cero o con más de una, `None`: no se
    adivina."""
    if not filas:
        return None
    anchura = max(len(f) for f in filas)
    candidatas = []
    for indice in range(anchura):
        valores = [f[indice] for f in filas if indice < len(f) and f[indice] is not None]
        if not valores:
            continue
        con_forma = sum(1 for v in valores if _FORMA_CODIGO_RE.match(str(v)))
        if con_forma >= _MINIMO_VALORES_CON_FORMA * len(valores):
            candidatas.append(indice)
    return candidatas[0] if len(candidatas) == 1 else None


def leer_codigos_vigentes(ruta_excel: str) -> tuple[list[str], str, Optional[str], int]:
    """`(códigos, cómo se localizó la columna, hoja, filas leídas)`.

    Lee **todas** las hojas y se queda con la primera que resuelve, por el
    orden de preferencia del docstring del módulo (encabezado antes que
    contenido). Nunca mezcla dos hojas: un fichero con una hoja de datos y
    otra de notas no debe juntar las dos listas."""
    libro = openpyxl.load_workbook(ruta_excel, read_only=True, data_only=True)
    try:
        por_contenido: Optional[tuple[list[str], str, str, int]] = None
        for hoja in libro.worksheets:
            filas = list(hoja.iter_rows(values_only=True))
            if not filas:
                continue
            indice = _encabezado_de_codigos(list(filas[0]))
            if indice is not None:
                codigos = _codigos_de_columna(filas[1:], indice)
                if codigos:
                    return codigos, "encabezado", hoja.title, len(filas) - 1
                continue
            if por_contenido is None:
                indice = _columna_por_contenido(filas)
                if indice is not None:
                    # Solo los valores con forma de código: en esta vía no hay
                    # encabezado que separe los datos del título de la hoja, y
                    # "Vigentes con remanente 2026" no es un expediente.
                    codigos = _codigos_de_columna(filas, indice, solo_con_forma=True)
                    if codigos:
                        por_contenido = (codigos, "contenido", hoja.title, len(filas))
        if por_contenido is not None:
            return por_contenido
        return [], "no encontrada", None, 0
    finally:
        libro.close()


def _codigos_de_columna(filas: list[tuple], indice: int, solo_con_forma: bool = False) -> list[str]:
    vistos: list[str] = []
    for fila in filas:
        if indice >= len(fila):
            continue
        bruto = fila[indice]
        if solo_con_forma and (bruto is None or not _FORMA_CODIGO_RE.match(str(bruto))):
            continue
        codigo = normalizar_codigo_expediente(bruto)
        if codigo and codigo not in vistos:
            vistos.append(codigo)
    return vistos


def cruzar_vigentes_con_remanente(
    db: Session,
    ruta_excel: Optional[str],
    conciliacion: list[FilaConciliacion],
    buscar: bool = True,
) -> ResumenVigentesRemanente:
    """El cruce que pidió el cliente. `conciliacion` es la lista ya construida
    (`app.conciliacion.construir_conciliacion`), que el llamador pasa para no
    recalcularla aquí: es la MISMA lista que escribe el Excel, nunca una
    consulta propia -- el mismo criterio que rige la hoja "Conciliación"."""
    resumen = ResumenVigentesRemanente(configurado=bool(ruta_excel))
    if not ruta_excel:
        return resumen

    codigos, localizada_por, hoja, filas_leidas = leer_codigos_vigentes(ruta_excel)
    resumen.columna_localizada_por = localizada_por
    resumen.hoja = hoja
    resumen.filas_leidas = filas_leidas
    resumen.codigos_distintos = len(codigos)
    resumen.formato_reconocido = bool(codigos)
    if not codigos:
        return resumen

    por_codigo = {f.codigo_expediente: f for f in conciliacion}
    expedientes = {
        e.codigo_expediente: e
        for e in db.execute(
            select(Expediente).where(Expediente.codigo_expediente.in_(codigos))
        ).scalars()
    }

    for codigo in codigos:
        fila_conciliacion = por_codigo.get(codigo)
        expediente = expedientes.get(codigo)
        if fila_conciliacion is not None:
            resumen.en_la_conciliacion += 1
            resumen.por_situacion[fila_conciliacion.situacion] = (
                resumen.por_situacion.get(fila_conciliacion.situacion, 0) + 1
            )
            resumen.filas.append(
                FilaVigenteRemanente(
                    codigo_expediente=codigo,
                    en_el_sistema=True,
                    en_la_conciliacion=True,
                    situacion=fila_conciliacion.situacion,
                    motivo=fila_conciliacion.motivo,
                    estado_sistema=expediente.estado.value if expediente else None,
                    lineas_en_catalogo=fila_conciliacion.lineas_en_catalogo,
                    accion=ACCION_EN_LA_CONCILIACION,
                )
            )
            continue

        resumen.fuera_de_la_conciliacion += 1
        accion = ACCION_SIN_BUSCAR
        if buscar:
            if expediente is None:
                expediente = Expediente(
                    codigo_expediente=codigo, estado=EstadoExpediente.pendiente
                )
                db.add(expediente)
                db.flush()
                expedientes[codigo] = expediente
                resumen.dados_de_alta += 1
                accion = ACCION_ALTA_Y_BUSCADO
            else:
                accion = ACCION_BUSCADO
            encolar_trabajo(db, tipo="descargar_expediente", expediente_id=expediente.id)
            resumen.busquedas_encoladas += 1
        resumen.filas.append(
            FilaVigenteRemanente(
                codigo_expediente=codigo,
                en_el_sistema=expediente is not None,
                en_la_conciliacion=False,
                situacion=None,
                motivo=None,
                estado_sistema=expediente.estado.value if expediente else None,
                lineas_en_catalogo=None,
                accion=accion,
            )
        )
    db.commit()
    return resumen
