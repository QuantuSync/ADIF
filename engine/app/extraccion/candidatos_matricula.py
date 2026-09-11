"""Cola de candidatos de matrícula (Bloque 1, sesión 2026-09-11).

Análisis previo (sesión del maestro de materiales, 2026-09-10, bloque 2,
`docs/sesion-2026-09-10-maestro-materiales-real.md`): de las líneas del
catálogo sin matrícula, un 8,6% coincide EXACTO (normalizado) con una
denominación del maestro y un 19,7% más con alta similitud (`difflib`
>= 0,85) -- pero dos de cada tres de esas últimas tienen más de un
candidato por encima del umbral a la vez, y 2.388 de las 28.782
denominaciones distintas del maestro (8,3%) identifican más de una
matrícula. Conclusión de aquel análisis, sin implementar entonces por
encargo explícito: "si esto se construye, tiene que ser una cola de
candidatos para confirmación humana... nunca una asignación automática, ni
siquiera para el 8,6% de coincidencia exacta".

Este módulo construye esa cola -- calcula candidatos, nunca asigna nada por
su cuenta (`app.routers.candidatos_matricula` es quien escribe `LineaCatalogo.
matricula`, y solo cuando un humano lo pide explícitamente).

Método (mismo que el análisis previo, sin dependencias nuevas): índice
invertido por palabra sobre las denominaciones del maestro, para acotar qué
filas del maestro merece la pena comparar con `difflib` en vez de comparar
cada línea del catálogo contra las ~29.000 denominaciones distintas una a
una -- con 13.000+ líneas sin matrícula y 32.000+ filas de maestro, la
comparación completa sería cuadrática de verdad."""
from __future__ import annotations

import difflib
from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.extraccion.texto import normalizar
from app.models import CandidatoMatricula, LineaCatalogo, MaestroMaterial

# Mismo umbral que verificó el análisis previo contra el corpus real
# (sesión 2026-09-10, bloque 2): por debajo de esto la mayoría de los pares
# ya no son el mismo material, solo texto parecido (ver el caso real de esa
# sesión: dos tornillos de longitud distinta, M22x325 frente a M22x275,
# enlazados a 0,958 de similitud -- el umbral no elimina ese riesgo, pero
# 0,85 es donde el propio análisis lo situó como "alta similitud").
UMBRAL_SIMILITUD = 0.85

# Palabras demasiado frecuentes para acotar nada (aparecerían en la
# denominación de miles de materiales a la vez) -- puramente una
# optimización del índice invertido, nunca cambia qué candidatos pasan el
# umbral de similitud real, solo cuáles se comparan.
_PALABRAS_VACIAS = {
    "de", "del", "la", "el", "los", "las", "y", "en", "con", "para", "a",
    "un", "una", "mm", "kg", "m", "n", "s",
}


def _palabras(texto: str) -> set[str]:
    return {p for p in normalizar(texto).split(" ") if p and p not in _PALABRAS_VACIAS}


@dataclass
class ResumenCandidatosMatricula:
    lineas_sin_matricula: int = 0
    lineas_con_candidato: int = 0
    lineas_sin_candidato: int = 0
    candidatos_generados: int = 0

    def to_dict(self) -> dict:
        return {
            "lineas_sin_matricula": self.lineas_sin_matricula,
            "lineas_con_candidato": self.lineas_con_candidato,
            "lineas_sin_candidato": self.lineas_sin_candidato,
            "candidatos_generados": self.candidatos_generados,
        }


def calcular_candidatos(db: Session) -> ResumenCandidatosMatricula:
    """Recalcula la cola entera: borra todos los `CandidatoMatricula`
    existentes y los reconstruye desde el estado actual del catálogo y del
    maestro -- es una caché, nunca se actualiza a medias (evita candidatos
    obsoletos de una matrícula que el maestro ya no trae, o de una línea que
    entretanto ganó matrícula por otra vía). No toca `LineaCatalogo.matricula`
    ni `matricula_confirmada_manualmente`/`matricula_candidatos_rechazados`
    -- esas son decisiones humanas, esta función solo recalcula las
    opciones."""
    resumen = ResumenCandidatosMatricula()

    lineas = db.execute(
        select(LineaCatalogo.id, LineaCatalogo.descripcion).where(LineaCatalogo.matricula.is_(None))
    ).all()
    resumen.lineas_sin_matricula = len(lineas)
    if not lineas:
        db.execute(delete(CandidatoMatricula))
        db.commit()
        return resumen

    maestros = db.execute(
        select(MaestroMaterial.matricula, MaestroMaterial.descripcion).where(
            MaestroMaterial.descripcion.is_not(None)
        )
    ).all()

    indice_invertido: dict[str, list[int]] = defaultdict(list)
    denominaciones_normalizadas: list[str] = [""] * len(maestros)
    for i, (matricula_maestro, descripcion_maestro) in enumerate(maestros):
        denominacion_normalizada = normalizar(descripcion_maestro)
        denominaciones_normalizadas[i] = denominacion_normalizada
        for palabra in _palabras(descripcion_maestro):
            indice_invertido[palabra].append(i)

    nuevos: list[CandidatoMatricula] = []
    for linea_id, descripcion in lineas:
        descripcion_normalizada = normalizar(descripcion)
        palabras_linea = _palabras(descripcion)
        indices_candidatos: set[int] = set()
        for palabra in palabras_linea:
            indices_candidatos.update(indice_invertido.get(palabra, ()))

        candidatos_linea: list[tuple[float, int, bool]] = []  # (similitud, indice_maestro, exacto)
        for i in indices_candidatos:
            denominacion_normalizada = denominaciones_normalizadas[i]
            exacto = denominacion_normalizada == descripcion_normalizada and bool(descripcion_normalizada)
            similitud = 1.0 if exacto else difflib.SequenceMatcher(
                None, descripcion_normalizada, denominacion_normalizada
            ).ratio()
            if exacto or similitud >= UMBRAL_SIMILITUD:
                candidatos_linea.append((similitud, i, exacto))

        if candidatos_linea:
            resumen.lineas_con_candidato += 1
        else:
            resumen.lineas_sin_candidato += 1

        for similitud, i, exacto in candidatos_linea:
            matricula_maestro, descripcion_maestro = maestros[i]
            nuevos.append(
                CandidatoMatricula(
                    linea_catalogo_id=linea_id,
                    matricula_candidata=matricula_maestro,
                    denominacion_maestro=descripcion_maestro,
                    similitud=round(similitud, 4),
                    exacto=exacto,
                )
            )

    db.execute(delete(CandidatoMatricula))
    db.add_all(nuevos)
    resumen.candidatos_generados = len(nuevos)
    db.commit()
    return resumen
