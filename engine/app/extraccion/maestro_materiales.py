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

Formato real, recibido y verificado bloque 1, sesión 2026-09-10
(`LISTADO_MATERIALES_UNIDAD__MEDIDA.xlsx`, 32.116 filas, sin huecos) --
distinto del que se suponía al preparar la carga (sesión 2026-09-09: se
esperaba "Texto breve"/"Unidad medida base", nombres tomados por analogía
del desglose de SAP del bloque 6 anterior; el maestro real usa otros dos):
    - "Material"        matrícula. 31.665 de nueve dígitos, 440 de cuatro y
                         11 de diez (categorías genéricas de SAP) -- ver
                         migración 0026 para por qué `MaestroMaterial.matricula`
                         ensancha a `String(10)`.
    - "Denominación"     descripción del material.
    - "UM base"          unidad de medida. 18 unidades distintas, "UN" en
                         el 96% de las filas.

Cómo se cruza, en dos pasos separados y ninguno automático por completo:

1. Completar UNIDAD DE MEDIDA (`completar_unidades_desde_maestro`): join
   determinista por `matricula` exacta -- la línea de catálogo YA tiene
   matrícula (40,7% del corpus real) y el maestro trae su unidad. Sin
   ambigüedad, se puede automatizar sin más red de seguridad que "nunca pisar
   un valor ya extraído" (ver más abajo). Techo real: solo alcanza a las
   líneas que YA tienen matrícula pero no unidad -- no las que carecen de
   las dos cosas. De paso (mismo encargo, bloque 1): cuando la línea YA
   tiene su propia unidad Y el maestro trae una distinta para la misma
   matrícula, la discrepancia se anota (`unidad_medida_discrepancia_maestro`)
   para revisión humana, nunca se corrige sola -- "es información útil",
   no un error a resolver en silencio.

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

from app.extraccion.unidad_medida import es_marca_de_partida_alzada, es_unidad_conocida, normalizar_unidad
from app.models import LineaCatalogo, MaestroMaterial

COLUMNA_MATRICULA = "Material"
COLUMNA_DESCRIPCION = "Denominación"
COLUMNA_UNIDAD_MEDIDA = "UM base"

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
    # Bloque 1, sesión 2026-09-10: líneas que YA traían su propia unidad
    # (del documento real) y el maestro da una distinta para la misma
    # matrícula -- anotadas, nunca corregidas solas.
    discrepancias_detectadas: int = 0

    def to_dict(self) -> dict:
        return {
            "lineas_evaluadas": self.lineas_evaluadas,
            "lineas_completadas": self.lineas_completadas,
            "sin_matricula_en_maestro": self.sin_matricula_en_maestro,
            "discrepancias_detectadas": self.discrepancias_detectadas,
        }


# Medido contra el maestro real cargado en este bloque: sin esto, "UD"/
# "UD."/"ud" del documento contra "UN" del maestro por sí solas producían
# 3.281 de 3.636 discrepancias -- la misma unidad real (SAP y los pliegos
# usan abreviaturas distintas para "unidad"), no una discrepancia de
# sustancia. Sinónimos verificados, no adivinados: solo variantes gráficas
# de "unidad", nunca una unidad físicamente distinta (Kg/M/UN sí se dejan
# como discrepancia real).
_SINONIMOS_UNIDAD = {
    "UD": "UN",
    "UDS": "UN",
    "UNIDAD": "UN",
    "UNIDADES": "UN",
}


def _normalizada(unidad: Optional[str]) -> Optional[str]:
    """Compara sin dejarse engañar por mayúsculas/espacios/puntos sobrantes
    (CONTEXTO.md sección 8) ni por sinónimos gráficos conocidos de la misma
    unidad real -- una diferencia de caja o de abreviatura no es una
    discrepancia real."""
    if unidad is None:
        return None
    # Sesión 2026-09-16 (noche): la forma única ("Ton" -> "t") antes de
    # comparar; las líneas ya la guardan así desde entonces.
    texto = normalizar_unidad(unidad).upper().rstrip(".")
    if not texto:
        return None
    return _SINONIMOS_UNIDAD.get(texto, texto)


def aplicar_unidades_del_maestro(db: Session, lineas) -> ResumenCompletarUnidades:
    """La unidad del maestro sobre estas líneas, mirando la fila ya escrita.

    Sesión 2026-09-22: deja de ser solo un paso manual y corre dentro del
    proceso automático -- al guardar las líneas de cada documento
    (`app.catalogo.guardar_lineas_catalogo`) y al final de cada ciclo de
    mantenimiento --, así que el reproceso la aplica siempre. Tres reglas:

    1. **La unidad del documento manda siempre.** Una línea con unidad propia
       nunca se pisa; si el maestro da otra, se anota la discrepancia.
    2. Sin unidad propia, la del maestro por matrícula exacta, marcada con
       `unidad_medida_completada_desde_maestro` para que la fila lo diga.
    3. **Una unidad que vino del maestro se recalcula**, no se hereda: si la
       matrícula ya no está en el maestro (o ya no es la misma), la unidad se
       retira. Si la marca sigue puesta es porque ningún documento ha traído
       unidad -- el guardado la quita en cuanto una pasada la trae.

    La partida alzada (`PA` en la celda de unidad) no recibe unidad del
    maestro: su celda es "no aplica". **Sin maestro cargado no toca nada.**"""
    resumen = ResumenCompletarUnidades()
    lineas = [
        linea for linea in lineas
        if linea.matricula is not None or linea.unidad_medida_completada_desde_maestro
    ]
    if not lineas or db.query(MaestroMaterial).limit(1).first() is None:
        return resumen

    matriculas = {linea.matricula for linea in lineas if linea.matricula is not None}
    maestros = db.execute(
        select(MaestroMaterial).where(MaestroMaterial.matricula.in_(matriculas))
    ).scalars().all() if matriculas else []
    # Sesión 2026-09-15 (cuarta parte): la unidad del maestro pasa el mismo
    # vocabulario que la del documento -- "001" (una fila del maestro) no es
    # una unidad.
    unidad_por_matricula = {
        m.matricula: m.unidad_medida
        for m in maestros
        if m.unidad_medida and es_unidad_conocida(m.unidad_medida)
    }

    for linea in lineas:
        unidad_maestro = unidad_por_matricula.get(linea.matricula) if linea.matricula else None

        if linea.unidad_medida_completada_desde_maestro:
            if unidad_maestro is None:
                linea.unidad_medida = None
                linea.unidad_medida_original = None
                linea.unidad_medida_completada_desde_maestro = None
                continue
            if linea.unidad_medida_original != unidad_maestro:
                linea.unidad_medida = normalizar_unidad(unidad_maestro)
                linea.unidad_medida_original = unidad_maestro
            if linea.unidad_medida_discrepancia_maestro is not None:
                linea.unidad_medida_discrepancia_maestro = None
            continue

        if linea.unidad_medida is None:
            if linea.unidad_medida_original and es_marca_de_partida_alzada(linea.unidad_medida_original):
                continue
            resumen.lineas_evaluadas += 1
            if unidad_maestro is None:
                resumen.sin_matricula_en_maestro += 1
                continue
            linea.unidad_medida = normalizar_unidad(unidad_maestro)
            linea.unidad_medida_original = unidad_maestro
            linea.unidad_medida_completada_desde_maestro = True
            resumen.lineas_completadas += 1
            continue

        if unidad_maestro is None:
            continue
        if _normalizada(unidad_maestro) == _normalizada(linea.unidad_medida):
            if linea.unidad_medida_discrepancia_maestro is not None:
                linea.unidad_medida_discrepancia_maestro = None
            continue
        if linea.unidad_medida_discrepancia_maestro != unidad_maestro:
            linea.unidad_medida_discrepancia_maestro = unidad_maestro
        resumen.discrepancias_detectadas += 1

    return resumen


def completar_unidades_desde_maestro(db: Session) -> ResumenCompletarUnidades:
    """`aplicar_unidades_del_maestro` sobre todo el catálogo: el paso manual
    de siempre (`POST /mantenimiento/maestro-materiales/completar-unidades`),
    y el que corre al final de cada ciclo de mantenimiento, para las líneas
    que esa pasada no ha vuelto a guardar (un maestro recién recargado)."""
    lineas = db.execute(
        select(LineaCatalogo).where(
            (LineaCatalogo.matricula.is_not(None))
            | (LineaCatalogo.unidad_medida_completada_desde_maestro.is_(True))
        )
    ).scalars().all()
    resumen = aplicar_unidades_del_maestro(db, lineas)
    db.commit()
    return resumen
