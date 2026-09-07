"""Descubrimiento inverso: matriz -> pedidos (sesión de descubrimiento
inverso). Hasta esta sesión el sistema solo resolvía la dirección contraria
(`app.extraccion.herencia_matriz`: un pedido declara su matriz, y el sistema
la crea/encola si hace falta) -- nunca había recorrido "dado un acuerdo
marco, qué pedidos cuelgan de él", que es la dirección que de verdad importa
para la segunda familia de baja (CONTEXTO.md sección 16): los precios de
referencia están en la matriz, la baja real en cada pedido, y sin las dos
piezas no hay nada que calcular.

Verificado en vivo contra la Plataforma real (sesión de descubrimiento
inverso): ni la ficha de la matriz ni la sindicación enlazan sus pedidos, pero
el buscador SÍ permite acotar por "Sistema de contratación = Contrato basado
en un Acuerdo Marco" + Órgano + Adjudicatario
(`app.scraping.pcsp.buscar_candidatos_acuerdo_marco`) -- confirmado
encontrando los 9 pedidos conocidos de las 3 matrices de carril entre 92
candidatos reales. Como el mismo adjudicatario puede tener más de un acuerdo
marco a lo largo de los años, cada candidato se confirma abriendo su propia
ficha y leyendo su sección "Acuerdo Marco -> Expediente"
(`app.scraping.pcsp.leer_matriz_declarada`) -- ese resultado se cachea en
`CandidatoAcuerdoMarco` (migración 0017) porque no cambia una vez adjudicado
y abrir una ficha por candidato es caro (92 candidatos para un solo
adjudicatario en la muestra de esta sesión): un candidato ya comprobado, para
esta matriz o para cualquier otra, no se vuelve a abrir nunca.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.extraccion.cruce_codigos import normalizar_codigo_expediente
from app.models import CandidatoAcuerdoMarco, Expediente
from app.queue import encolar_trabajo
from app.scraping.pcsp import descubrir_candidatos_acuerdo_marco

TIPO_TRABAJO = "descubrimiento_pedidos"

# Órgano de contratación con el que se acota siempre la búsqueda (CONTEXTO.md
# sección 24: "ADIF" como texto libre ya cubre los cuatro órganos reales
# verificados -- Presidencia y Consejo de Administración, de ADIF y de ADIF
# Alta Velocidad -- porque el campo del formulario hace coincidencia parcial
# de texto, no una lista cerrada). Constante, no configurable todavía: el
# sistema entero es de alcance ADIF (CONTEXTO.md sección 1), igual que
# `sindicacion_departamentos_adif` acota por departamento en vez de por este
# texto.
ORGANO_BUSQUEDA = "ADIF"

MOTIVO_SIN_ADJUDICATARIO = (
    "no se pudo buscar pedidos de esta matriz: ningún lote tiene adjudicatario extraído todavía "
    "(hace falta para acotar la búsqueda en la Plataforma)"
)


@dataclass
class ResumenDescubrimientoMatriz:
    matriz_codigo: str
    omitido: bool = False
    motivo_omitido: Optional[str] = None
    adjudicatarios_usados: list[str] = field(default_factory=list)
    candidatos_evaluados: int = 0
    candidatos_verificados_ahora: int = 0
    pedidos_nuevos: int = 0
    pedidos_ya_conocidos: int = 0

    def to_dict(self) -> dict:
        return {
            "matriz_codigo": self.matriz_codigo,
            "omitido": self.omitido,
            "motivo_omitido": self.motivo_omitido,
            "adjudicatarios_usados": self.adjudicatarios_usados,
            "candidatos_evaluados": self.candidatos_evaluados,
            "candidatos_verificados_ahora": self.candidatos_verificados_ahora,
            "pedidos_nuevos": self.pedidos_nuevos,
            "pedidos_ya_conocidos": self.pedidos_ya_conocidos,
        }


def _adjudicatarios_de(matriz: Expediente) -> list[str]:
    """Ajuste 1 del encargo: un acuerdo marco puede tener varios lotes con
    distinto adjudicatario (p.ej. varios lotes de material repartidos entre
    proveedores) -- se busca una vez por cada adjudicatario distinto que
    tenga algún lote, nunca solo el del primero."""
    vistos: list[str] = []
    for lote in matriz.lotes:
        nombre = (lote.adjudicatario or "").strip()
        if nombre and nombre not in vistos:
            vistos.append(nombre)
    return vistos


def _cache_existente(db: Session) -> dict[str, Optional[str]]:
    filas = db.execute(select(CandidatoAcuerdoMarco)).scalars().all()
    return {f.codigo_expediente_candidato: f.codigo_matriz_declarado for f in filas}


def _guardar_en_cache(db: Session, codigo: str, matriz_declarada: Optional[str]) -> None:
    existente = db.execute(
        select(CandidatoAcuerdoMarco).where(CandidatoAcuerdoMarco.codigo_expediente_candidato == codigo)
    ).scalar_one_or_none()
    if existente is not None:
        existente.codigo_matriz_declarado = matriz_declarada
        return
    db.add(CandidatoAcuerdoMarco(codigo_expediente_candidato=codigo, codigo_matriz_declarado=matriz_declarada))
    try:
        db.commit()
    except IntegrityError:
        # Carrera con otra verificación del mismo candidato (misma matriz
        # buscada dos veces, o dos matrices con un adjudicatario en común):
        # no es un error real, solo hay que quedarse con la fila ya escrita.
        db.rollback()


def _registrar_pedido(db: Session, matriz: Expediente, codigo_pedido: str) -> bool:
    """True si se dio de alta un `Expediente` nuevo (o se enlazó uno ya
    existente que todavía no tenía matriz resuelta) -- False si ya estaba
    enlazado a esta matriz de antes, para no contarlo dos veces en el
    recuento."""
    existente = db.execute(
        select(Expediente).where(Expediente.codigo_expediente == codigo_pedido)
    ).scalar_one_or_none()
    if existente is not None:
        if existente.matriz_expediente_id == matriz.id:
            return False
        if existente.matriz_expediente_id is None:
            existente.codigo_matriz = matriz.codigo_expediente
            existente.matriz_expediente_id = matriz.id
            db.commit()
            return True
        # Ya enlazado a OTRA matriz por una vía distinta (Excel de códigos,
        # Anuncio PCSP propio): esa vía manda (CONTEXTO.md sección 7, "el
        # sistema nunca inventa una matriz"), este descubrimiento no la pisa.
        return False

    pedido = Expediente(
        codigo_expediente=codigo_pedido,
        codigo_matriz=matriz.codigo_expediente,
        matriz_expediente_id=matriz.id,
    )
    db.add(pedido)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return False
    db.refresh(pedido)
    encolar_trabajo(db, tipo="descargar_expediente", expediente_id=pedido.id)
    return True


def descubrir_pedidos_de_matriz(db: Session, matriz: Expediente) -> ResumenDescubrimientoMatriz:
    resumen = ResumenDescubrimientoMatriz(matriz_codigo=matriz.codigo_expediente)

    adjudicatarios = _adjudicatarios_de(matriz)
    if not adjudicatarios:
        matriz.aviso_descubrimiento_pedidos = MOTIVO_SIN_ADJUDICATARIO
        db.commit()
        resumen.omitido = True
        resumen.motivo_omitido = MOTIVO_SIN_ADJUDICATARIO
        return resumen

    resumen.adjudicatarios_usados = adjudicatarios
    matriz.aviso_descubrimiento_pedidos = None

    cache = _cache_existente(db)
    codigo_matriz_normalizado = normalizar_codigo_expediente(matriz.codigo_expediente)
    candidatos_totales: set[str] = set()

    for adjudicatario in adjudicatarios:
        candidatos, nuevas = asyncio.run(
            descubrir_candidatos_acuerdo_marco(adjudicatario, set(cache), organo=ORGANO_BUSQUEDA)
        )
        candidatos_totales.update(candidatos)
        for codigo, matriz_declarada in nuevas.items():
            _guardar_en_cache(db, codigo, matriz_declarada)
            cache[codigo] = matriz_declarada
            resumen.candidatos_verificados_ahora += 1

    resumen.candidatos_evaluados = len(candidatos_totales)
    db.commit()

    for candidato in candidatos_totales:
        matriz_declarada = cache.get(candidato)
        if matriz_declarada is None:
            continue
        if normalizar_codigo_expediente(matriz_declarada) != codigo_matriz_normalizado:
            continue
        if _registrar_pedido(db, matriz, candidato):
            resumen.pedidos_nuevos += 1
        else:
            resumen.pedidos_ya_conocidos += 1

    return resumen


def matrices_conocidas(db: Session) -> list[Expediente]:
    """Expedientes que ya son matriz de al menos un pedido conocido -- el
    universo sobre el que tiene sentido lanzar este descubrimiento (para uno
    que todavía no es matriz de nadie, no hay nada que buscarle: no se sabe
    que sea un acuerdo marco hasta que algún pedido lo declara una primera
    vez, `app.extraccion.herencia_matriz`)."""
    return (
        db.execute(
            select(Expediente)
            .where(Expediente.id.in_(select(Expediente.matriz_expediente_id).where(
                Expediente.matriz_expediente_id.is_not(None)
            ).distinct()))
            .order_by(Expediente.id)
        )
        .scalars()
        .all()
    )


@dataclass
class ResumenDescubrimientoMatrices:
    matrices_evaluadas: int = 0
    resultados: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"matrices_evaluadas": self.matrices_evaluadas, "resultados": self.resultados}


def descubrir_pedidos_de_matrices_conocidas(
    db: Session, matriz_expediente_id: Optional[int] = None
) -> ResumenDescubrimientoMatrices:
    """Punto de entrada del trabajo de cola: por defecto recorre todas las
    matrices ya conocidas (`matrices_conocidas`); `matriz_expediente_id`
    acota a una sola, para el botón manual de una ficha concreta."""
    if matriz_expediente_id is not None:
        matriz = db.get(Expediente, matriz_expediente_id)
        objetivos = [matriz] if matriz is not None else []
    else:
        objetivos = matrices_conocidas(db)

    resumen = ResumenDescubrimientoMatrices(matrices_evaluadas=len(objetivos))
    for matriz in objetivos:
        resumen.resultados.append(descubrir_pedidos_de_matriz(db, matriz).to_dict())
    return resumen
