"""Por qué está vacía cada celda de una línea de catálogo -- el mismo criterio
de tres motivos que ya aplica la web (`web/app/ui.tsx`, `DatoVacio`): el dato
no aplica a este tipo de línea, no consta en el documento de origen, o está
pendiente de otro dato.

Sesión 2026-09-14 (continuación), encargo del cliente: una cantidad o un
precio unitario que la guarda de choques deja vacío porque el documento
trae un valor distinto para cada lote (`app.catalogo.MOTIVO_VALOR_DE_OTRO_LOTE`)
no puede leerse igual que uno que el documento no trae. Lo decide el motor,
en un solo sitio, para que el Excel (`app.exportacion`, columna "Motivo de
las celdas vacías") y la web (`celdas_vacias` en la API) digan lo mismo."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.catalogo import campos_vacios_por_valor_de_otro_lote
from app.models import LineaCatalogo, ModeloPrecio

# Mismos códigos que `MotivoVacio` de la web.
NO_APLICA = "na"
NO_CONSTA = "no-consta"
PENDIENTE = "pendiente"
ETIQUETA_MOTIVO = {NO_APLICA: "no aplica", NO_CONSTA: "no consta", PENDIENTE: "pendiente"}

_DETALLE_PARTIDA_ALZADA = "partida alzada"
_DETALLE_OTRO_LOTE = {
    "cantidad": "el documento da una cantidad distinta para cada lote y falta saber cuál es la de este",
    "precio_unitario": "el documento da un precio distinto para cada lote y falta saber cuál es el de este",
}

# Sesión 2026-09-18, bloque 2: las columnas que describen el EXPEDIENTE (no la
# línea) también pueden quedar vacías, y hasta hoy ninguna traía motivo -- el
# cliente veía la celda en blanco sin nada que la explicara en ninguna parte
# del entregable. Texto en castellano llano, para alguien de almacenes que no
# sabe nada de este sistema: nada de "cruce", "índice" ni "codigos_cruzados".
_DETALLE_SIN_CRUCE = "este expediente no aparece en el listado de códigos de ADIF"
_DETALLE_CRUZA_SIN_INTERNO = "el listado de códigos de ADIF no trae número interno para este expediente"
# Sesión 2026-09-18, bloque 2 (decisión del cliente). Tercera causa, hasta hoy
# invisible: el expediente encuentra fila en el listado de ADIF, pero es la
# fila de OTRO expediente de la misma familia (la encuentra por la columna de
# acuerdo marco, no por su propio número). El número interno de esa fila es el
# de ese otro expediente, y escribirlo aquí es peor que dejar la celda vacía:
# en almacenes lo usan para buscar, y les llevaría al expediente equivocado.
_DETALLE_SIN_FILA_PROPIA = "este expediente no figura por sí mismo en el listado de códigos de ADIF"
_DETALLE_SIN_MATRIZ = "no se conoce ningún acuerdo marco del que dependa este expediente"
_DETALLE_SIN_TITULO = "no se ha encontrado el título en los documentos de este expediente"
_DETALLE_SIN_ESTADO_SAP = "este expediente no aparece en el listado de contratos en ejecución de SAP"
# Bloque 7, sesión 2026-09-18 (continuación), caso `6.26/28510.0014`. En la
# segunda familia de precio (CONTEXTO.md sección 16: los acuerdos marco de
# carril, `P(t) = Precio ofertado × Kt × Coeficiente de baja`) no hay una baja
# única de lote **por diseño del propio contrato**, no porque no se haya
# sabido leer. Decir "no consta" ahí es decir que falta un dato que no
# existe, y deja al cliente buscando en la Plataforma algo que nunca se
# publicó. Verificado en la sesión 2026-09-07 contra los documentos reales de
# los 9 pedidos de las 3 matrices conocidas: el coeficiente no está publicado
# en ninguno -- ADIF y el adjudicatario lo pactan fuera de la Plataforma.
_DETALLE_PRECIO_INDEXADO = (
    "este contrato no tiene una baja única: su precio se revisa pedido a pedido con un coeficiente que "
    "ADIF pacta con el proveedor fuera de la Plataforma"
)


@dataclass(frozen=True)
class CeldaVacia:
    campo: str
    motivo: str  # NO_APLICA | NO_CONSTA | PENDIENTE
    detalle: Optional[str] = None


def es_partida_alzada(descripcion: Optional[str]) -> bool:
    """Réplica exacta de `esPartidaAlzada` de la web: una reserva
    presupuestaria, no un artículo de almacén (CONTEXTO.md sección 2)."""
    return bool(descripcion) and descripcion.lstrip().lower().startswith("partida alzada")


def celdas_vacias(
    linea: LineaCatalogo,
    identificador_lote: Optional[str],
    expediente=None,
    modelo_precio: Optional[ModeloPrecio] = None,
) -> list[CeldaVacia]:
    """Una entrada por cada campo vacío de la fila, en el orden de las columnas
    del Excel.

    `expediente` es opcional a propósito: las columnas que describen el
    expediente (código interno, código matriz, título, estado del contrato en
    SAP) solo existen en el Excel, así que solo `app.exportacion` lo pasa. La
    web (`app.catalogo_consulta`) muestra una tabla de LÍNEAS y sigue llamando
    con dos argumentos, sin cambiar de comportamiento -- los motivos de las
    columnas de línea se siguen decidiendo aquí, en un solo sitio, que es lo
    que pide el docstring del módulo."""
    partida = es_partida_alzada(linea.descripcion)
    de_otro_lote = campos_vacios_por_valor_de_otro_lote(linea.motivo_revision)
    vacias: list[CeldaVacia] = []

    # Columnas 1, 3 y 4 del Excel, antes de las de la línea.
    if expediente is not None:
        if not expediente.codigo_interno:
            # Tres causas distintas que el cliente no puede distinguir mirando
            # la celda: el expediente no está en el listado de ADIF, está pero
            # esa fila no trae número interno, o la única fila que se le
            # encuentra es la de otro expediente de su familia.
            if not expediente.codigos_cruzados:
                detalle = _DETALLE_SIN_CRUCE
            elif getattr(expediente, "cruce_fila_propia", None) is False:
                detalle = _DETALLE_SIN_FILA_PROPIA
            else:
                detalle = _DETALLE_CRUZA_SIN_INTERNO
            vacias.append(CeldaVacia("codigo_interno", NO_CONSTA, detalle))
        if not expediente.codigo_matriz:
            vacias.append(CeldaVacia("codigo_matriz", NO_CONSTA, _DETALLE_SIN_MATRIZ))
        if not expediente.nombre_proyecto:
            # Un solo motivo para las dos columnas que salen de este campo
            # ("Título expediente" y "Objeto del contrato (documento)"):
            # repetirlo dos veces en la misma celda no aporta nada.
            vacias.append(CeldaVacia("titulo_expediente", NO_CONSTA, _DETALLE_SIN_TITULO))

    def sin_dato_propio(campo: str) -> None:
        if partida:
            vacias.append(CeldaVacia(campo, NO_APLICA, _DETALLE_PARTIDA_ALZADA))
        else:
            vacias.append(CeldaVacia(campo, NO_CONSTA))

    def valor_de_lote(campo: str) -> None:
        if campo in de_otro_lote:
            vacias.append(CeldaVacia(campo, PENDIENTE, _DETALLE_OTRO_LOTE[campo]))
        else:
            vacias.append(CeldaVacia(campo, NO_CONSTA))

    if not linea.matricula:
        sin_dato_propio("matricula")
    if not linea.codigo_material:
        sin_dato_propio("codigo_material")
    if linea.cantidad is None:
        valor_de_lote("cantidad")
    if linea.precio_unitario is None:
        valor_de_lote("precio_unitario")
    if identificador_lote is None:
        vacias.append(CeldaVacia("lote", NO_CONSTA))
    indexado = modelo_precio == ModeloPrecio.indexado_por_pedido
    if linea.precio_adjudicado is None:
        # Siempre derivado (precio unitario × (1 − baja del lote), CONTEXTO.md
        # sección 4): vacío solo porque le falta uno de los dos.
        if indexado:
            vacias.append(CeldaVacia("precio_adjudicado", NO_APLICA, _DETALLE_PRECIO_INDEXADO))
        elif linea.precio_unitario is None:
            vacias.append(CeldaVacia("precio_adjudicado", PENDIENTE, "falta el precio unitario"))
        elif linea.baja_lote is None:
            vacias.append(CeldaVacia("precio_adjudicado", PENDIENTE, "falta la baja del lote"))
        else:
            vacias.append(CeldaVacia("precio_adjudicado", NO_CONSTA))
    if linea.baja_lote is None:
        if indexado:
            vacias.append(CeldaVacia("baja_lote", NO_APLICA, _DETALLE_PRECIO_INDEXADO))
        else:
            vacias.append(CeldaVacia("baja_lote", NO_CONSTA))
    if not linea.unidad_medida:
        sin_dato_propio("unidad_medida")
    # Columna 14, después de las de la línea.
    if expediente is not None and not expediente.estado_contrato_sap:
        vacias.append(CeldaVacia("estado_contrato_sap", NO_CONSTA, _DETALLE_SIN_ESTADO_SAP))
    return vacias
