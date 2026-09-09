"""Maestro de materiales de SAP (bloque 4, sesión 2026-09-09): ADIF va a
facilitar un documento de referencia existente en SAP -- no derivado de
pliegos ni contratos -- con matrícula y unidad de medida de cada material.
Resolvería los dos huecos mayores del catálogo (CONTEXTO.md sección 2:
matrícula presente solo en ~66% de las líneas del corpus completo, hoy 40,7%
en la base real; unidad de medida al 73,2%).

Todavía no lo tenemos. Este módulo deja preparada su carga como fuente de
entrada permanente, mismo mecanismo que `app.extraccion.estado_sap`/
`app.extraccion.sap_desglose`: una ruta configurada (`MAESTRO_MATERIALES_PATH`),
montada por bind-mount, repetible sin duplicar (upsert por `matricula`, la
clave natural de un material en SAP).

Formato mínimo esperado a pedir al cliente -- tres columnas, incluidas ya en
el desglose de SAP que el cliente facilitó en la sesión anterior
(`app.extraccion.sap_desglose`, bloque 6), mismo vocabulario para no pedir
dos nombres distintos de la misma cosa:
    - "Material"            matrícula, 9 dígitos.
    - "Texto breve"          descripción del material.
    - "Unidad medida base"   unidad de medida.

Cómo se cruzaría, en dos pasos separados y ninguno automático por completo:

1. Completar UNIDAD DE MEDIDA (`completar_unidades_desde_maestro`): join
   determinista por `matricula` exacta -- la línea de catálogo YA tiene
   matrícula (40,7% del corpus real) y el maestro trae su unidad. Sin
   ambigüedad, se puede automatizar sin más red de seguridad que "nunca pisar
   un valor ya extraído" (ver más abajo). Techo real: solo alcanza a las
   líneas que YA tienen matrícula pero no unidad -- no las que carecen de
   las dos cosas.

2. Completar MATRÍCULA -- deliberadamente NO implementado en esta sesión.
   El maestro de materiales no trae ninguna clave que ya tengamos en las
   líneas SIN matrícula (ni código de expediente, ni código de precio): la
   única vía posible es cruzar por texto (`descripcion` de la línea contra
   `Texto breve` del maestro), que CONTEXTO.md sección 7 ya reserva como "red
   de seguridad... con umbral y cola de revisión", nunca como cruce directo.
   Construir ese emparejamiento difuso (normalización de texto, umbral de
   similitud, cola de revisión para confirmar cada match) es una sesión
   propia -- mismo criterio que el cliente ya aplicó explícitamente a la
   completitud de matrícula del desglose de SAP (bloque 6 de la sesión
   anterior: "no lo implementes todavía"). Intentarlo aquí sin ese diseño
   completo arriesgaría inventar matrículas, justo lo que CONTEXTO.md
   prohíbe ("el sistema nunca inventa un dato").

Nunca pisa un valor ya extraído de un documento real (CONTEXTO.md invariante
10, trazabilidad, y el encargo explícito de esta sesión): solo escribe
`unidad_medida` cuando la línea la tiene a `None`. La línea completada se
marca con `unidad_medida_completada_desde_maestro = True` (migración 0025)
para que quede claro en la trazabilidad que ese valor concreto no vino del
documento apuntado por `documento_origen_id`/`pagina`/`fragmento`, sino de
este maestro."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import openpyxl
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import LineaCatalogo, MaestroMaterial

COLUMNA_MATRICULA = "Material"
COLUMNA_DESCRIPCION = "Texto breve"
COLUMNA_UNIDAD_MEDIDA = "Unidad medida base"

_COLUMNAS_REQUERIDAS = (COLUMNA_MATRICULA,)


class MaestroMaterialesPathInvalida(RuntimeError):
    """Mismo criterio que `EstadoSapPathInvalida`/`SapDesglosePathInvalida`:
    fallar de forma visible al validar la ruta en vez de dejar la carga rota
    para el primer intento real."""


def validar_ruta_maestro_materiales(ruta: Optional[str]) -> None:
    if not ruta:
        return
    camino = Path(ruta)
    if not camino.is_file():
        raise MaestroMaterialesPathInvalida(
            f"MAESTRO_MATERIALES_PATH={ruta!r} no es un fichero (¿bind-mount con el origen ausente?)"
        )
    try:
        libro = openpyxl.load_workbook(camino, read_only=True)
        libro.close()
    except Exception as exc:
        raise MaestroMaterialesPathInvalida(
            f"MAESTRO_MATERIALES_PATH={ruta!r} no se puede abrir como .xlsx: {exc}"
        ) from exc


def _texto(valor: object) -> Optional[str]:
    if valor is None:
        return None
    texto = str(valor).strip()
    return texto or None


@dataclass
class ResumenCargaMaestroMateriales:
    configurado: bool
    filas_leidas: int = 0
    filas_sin_matricula: int = 0
    materiales_nuevos: int = 0
    materiales_actualizados: int = 0
    materiales_sin_cambios: int = 0

    def to_dict(self) -> dict:
        return {
            "configurado": self.configurado,
            "filas_leidas": self.filas_leidas,
            "filas_sin_matricula": self.filas_sin_matricula,
            "materiales_nuevos": self.materiales_nuevos,
            "materiales_actualizados": self.materiales_actualizados,
            "materiales_sin_cambios": self.materiales_sin_cambios,
        }


def cargar_maestro_materiales(db: Session, ruta_excel: Optional[str]) -> ResumenCargaMaestroMateriales:
    """Lee todas las hojas (mismo motivo que el resto de fuentes de entrada:
    no asumir que el dato vive siempre en la primera). Upsert por
    `matricula` -- un material de SAP tiene una fila de referencia, no una
    por compra."""
    resumen = ResumenCargaMaestroMateriales(configurado=bool(ruta_excel))
    if not ruta_excel:
        return resumen

    libro = openpyxl.load_workbook(ruta_excel, read_only=True, data_only=True)
    try:
        for hoja in libro.worksheets:
            filas_iter = hoja.iter_rows(values_only=True)
            primera = next(filas_iter, None)
            if primera is None:
                continue
            cabecera = [str(c).strip() if c is not None else "" for c in primera]
            if not all(col in cabecera for col in _COLUMNAS_REQUERIDAS):
                continue  # hoja sin la columna mínima: no es la hoja del maestro

            indice = {col: cabecera.index(col) for col in cabecera if col}

            def _valor(fila, columna):
                idx = indice.get(columna)
                return fila[idx] if idx is not None and idx < len(fila) else None

            for fila in filas_iter:
                resumen.filas_leidas += 1
                matricula = _texto(_valor(fila, COLUMNA_MATRICULA))
                if not matricula:
                    resumen.filas_sin_matricula += 1
                    continue

                datos = dict(
                    descripcion=_texto(_valor(fila, COLUMNA_DESCRIPCION)),
                    unidad_medida=_texto(_valor(fila, COLUMNA_UNIDAD_MEDIDA)),
                )

                existente = db.execute(
                    select(MaestroMaterial).where(MaestroMaterial.matricula == matricula)
                ).scalar_one_or_none()
                if existente is None:
                    db.add(MaestroMaterial(matricula=matricula, **datos))
                    resumen.materiales_nuevos += 1
                else:
                    cambio = any(getattr(existente, campo) != valor for campo, valor in datos.items())
                    for campo, valor in datos.items():
                        setattr(existente, campo, valor)
                    if cambio:
                        resumen.materiales_actualizados += 1
                    else:
                        resumen.materiales_sin_cambios += 1
            db.commit()
    finally:
        libro.close()
    return resumen


@dataclass
class ResumenCompletarUnidades:
    lineas_evaluadas: int = 0
    lineas_completadas: int = 0
    sin_matricula_en_maestro: int = 0

    def to_dict(self) -> dict:
        return {
            "lineas_evaluadas": self.lineas_evaluadas,
            "lineas_completadas": self.lineas_completadas,
            "sin_matricula_en_maestro": self.sin_matricula_en_maestro,
        }


def completar_unidades_desde_maestro(db: Session) -> ResumenCompletarUnidades:
    """Rellena `LineaCatalogo.unidad_medida` por `matricula` exacta, SOLO
    donde la línea ya tiene matrícula y no tiene unidad -- nunca pisa un
    valor ya extraído (docstring del módulo). Marca
    `unidad_medida_completada_desde_maestro = True` en cada línea que toca,
    para que la trazabilidad distinga este origen del documento real."""
    resumen = ResumenCompletarUnidades()
    lineas = db.execute(
        select(LineaCatalogo).where(
            LineaCatalogo.matricula.is_not(None),
            LineaCatalogo.unidad_medida.is_(None),
        )
    ).scalars().all()

    if not lineas:
        return resumen

    matriculas = {linea.matricula for linea in lineas}
    maestros = db.execute(
        select(MaestroMaterial).where(MaestroMaterial.matricula.in_(matriculas))
    ).scalars().all()
    unidad_por_matricula = {m.matricula: m.unidad_medida for m in maestros if m.unidad_medida}

    for linea in lineas:
        resumen.lineas_evaluadas += 1
        unidad = unidad_por_matricula.get(linea.matricula)
        if unidad is None:
            resumen.sin_matricula_en_maestro += 1
            continue
        linea.unidad_medida = unidad
        linea.unidad_medida_completada_desde_maestro = True
        resumen.lineas_completadas += 1

    db.commit()
    return resumen
