"""Exportación del catálogo a Excel (CLAUDE.md, encargo de esta sesión, punto
4, y sección 9.8: "El Excel es una vista generada, no la fuente. [...] Se
regenera a demanda"). Un solo catálogo acumulativo para todos los
expedientes, con las once columnas y el orden exactos de `Ejemplo/Output/`
— es el formato que el cliente ya espera recibir.
"""
from __future__ import annotations

import io

from openpyxl import Workbook
from sqlalchemy.orm import Session

from app.catalogo_consulta import consultar_catalogo

COLUMNAS = [
    "Código interno",
    "Código de proyecto",
    "Código matriz",
    "Nombre del proyecto",
    "Matrícula del material",
    "Descripción del material",
    "Código del material",
    "Cantidad",
    "Precio unitario",
    "Lote",
    "Comentarios",
]

# Tamaño de página de la consulta al generar: bastante grande para pocas
# vueltas a la base de datos, pequeño para no cargar el catálogo entero en
# memoria de golpe si crece mucho (CLAUDE.md sección 1: catálogo acumulativo
# para todos los expedientes).
_TAMANO_LOTE = 500


def generar_excel_catalogo(db: Session) -> bytes:
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Materiales"
    hoja.append(COLUMNAS)

    pagina = 1
    while True:
        # CLAUDE.md bloque 2: una línea descartada en la cola de revisión no
        # sale en el Excel que se entrega al cliente, aunque siga en base de
        # datos con su motivo.
        resultado = consultar_catalogo(db, pagina=pagina, tamano_pagina=_TAMANO_LOTE, excluir_descartadas=True)
        for linea, lote, expediente, _documento in resultado.filas:
            # "El sistema nunca inventa una matriz. Si no cruza, se deja
            # vacío" (CLAUDE.md sección 7): código interno y código de
            # proyecto solo se rellenan cuando el cruce con el Excel de
            # códigos confirmó la fila.
            cruzado = bool(expediente.codigos_cruzados)
            hoja.append([
                expediente.codigo_interno if cruzado else None,
                expediente.codigo_expediente if cruzado else None,
                expediente.codigo_matriz,
                expediente.nombre_proyecto,
                linea.matricula,
                linea.descripcion,
                linea.codigo_material,
                float(linea.cantidad) if linea.cantidad is not None else None,
                float(linea.precio_unitario) if linea.precio_unitario is not None else None,
                lote.identificador_lote if lote else None,
                linea.comentarios,
            ])
        if pagina * _TAMANO_LOTE >= resultado.total:
            break
        pagina += 1

    buffer = io.BytesIO()
    libro.save(buffer)
    return buffer.getvalue()
