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
from app.models import LineaCatalogo

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


@dataclass(frozen=True)
class CeldaVacia:
    campo: str
    motivo: str  # NO_APLICA | NO_CONSTA | PENDIENTE
    detalle: Optional[str] = None


def es_partida_alzada(descripcion: Optional[str]) -> bool:
    """Réplica exacta de `esPartidaAlzada` de la web: una reserva
    presupuestaria, no un artículo de almacén (CONTEXTO.md sección 2)."""
    return bool(descripcion) and descripcion.lstrip().lower().startswith("partida alzada")


def celdas_vacias(linea: LineaCatalogo, identificador_lote: Optional[str]) -> list[CeldaVacia]:
    """Una entrada por cada campo de datos de la línea que está vacío, en el
    orden de las columnas del Excel."""
    partida = es_partida_alzada(linea.descripcion)
    de_otro_lote = campos_vacios_por_valor_de_otro_lote(linea.motivo_revision)
    vacias: list[CeldaVacia] = []

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
    if linea.precio_adjudicado is None:
        # Siempre derivado (precio unitario × (1 − baja del lote), CONTEXTO.md
        # sección 4): vacío solo porque le falta uno de los dos.
        if linea.precio_unitario is None:
            vacias.append(CeldaVacia("precio_adjudicado", PENDIENTE, "falta el precio unitario"))
        elif linea.baja_lote is None:
            vacias.append(CeldaVacia("precio_adjudicado", PENDIENTE, "falta la baja del lote"))
        else:
            vacias.append(CeldaVacia("precio_adjudicado", NO_CONSTA))
    if linea.baja_lote is None:
        vacias.append(CeldaVacia("baja_lote", NO_CONSTA))
    if not linea.unidad_medida:
        sin_dato_propio("unidad_medida")
    return vacias
