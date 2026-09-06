"""Exportación del catálogo a Excel (CLAUDE.md, encargo de esta sesión, punto
4, y sección 9.8: "El Excel es una vista generada, no la fuente. [...] Se
regenera a demanda"). Un solo catálogo acumulativo para todos los
expedientes, con las once columnas y el orden exactos de `Ejemplo/Output/`
— es el formato que el cliente ya espera recibir — más las dos columnas de
precio adjudicado y baja de lote al final (encargo de esta sesión, punto 3).

El marcador entre paréntesis ("(no consta)", "(no aplica)") es una
convención de la interfaz web (`app/ui.tsx`, `DatoVacio`) para que una
persona lea la pantalla sin ambigüedad. **No viaja al Excel** (encargo de
esta sesión, punto 1): en una columna numérica (Cantidad, Precio unitario,
Precio adjudicado, Baja del lote) un marcador de texto convierte la columna
entera en texto mixto y rompe sumar/filtrar/ordenar en Excel. En las
columnas de texto (Matrícula, Código del material, Lote) se aplica el mismo
criterio único por consistencia y porque es el que trae el Excel que ya
maneja el cliente: celda vacía, sin ninguna variante. El motivo por el que
falta (partida alzada, cruce sin confirmar, tabla ambigua) ya vive en
`motivo_revision`/la cola de revisión, trazable desde ahí — no se
inventa aquí un texto nuevo para la casilla.

Líneas huérfanas (`lote_id IS NULL`, tabla que no se pudo asociar a un
lote sin ambigüedad, `app.extraccion.lote_tabla`) sin ningún equivalente
ya resuelto en un lote conocido del mismo expediente: por defecto **no
salen en este Excel** (encargo de esta sesión) — mostrarían el mismo
material 2-6 veces sin que el cliente pueda distinguir una repetición real
de una casualidad de la extracción, y siguen genuinamente pendientes de
que una persona les asigne lote (docs/decisiones.md sección 31). Quedan en
la cola de revisión interna, nunca se pierden. `incluir_pendientes_sin_lote`
lo vuelve a activar sin tocar código, para cuando el cliente prefiera
verlas todas. Se excluyan o no, la hoja "Resumen" siempre dice cuántas
hay y por qué motivo agrupado — nunca desaparecen en silencio."""
from __future__ import annotations

import io
from collections import Counter

from openpyxl import Workbook
from sqlalchemy.orm import Session

from app.catalogo_consulta import consultar_catalogo
from app.models import LineaCatalogo


def _celda_matricula(linea: LineaCatalogo) -> str | None:
    return linea.matricula or None


def _celda_texto(valor: str | None) -> str | None:
    return valor or None


def _celda_numero(valor) -> object:
    return float(valor) if valor is not None else None


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
    "Precio adjudicado",
    "Baja del lote",
]

# Columnas numéricas (1-indexadas, en el orden de COLUMNAS de arriba) a las
# que aplicar un formato de celda explícito -- sin esto openpyxl las deja en
# "General" y Excel puede mostrarlas alineadas a la izquierda como si fueran
# texto pese a llevar ya un valor numérico real (punto 1 de esta sesión:
# "Asegúrate además de que los importes se exportan como número").
_FORMATO_CANTIDAD = "#,##0.###"
_FORMATO_IMPORTE = "#,##0.00"
_FORMATO_PORCENTAJE = "0.00%"
_COLUMNA_CANTIDAD = COLUMNAS.index("Cantidad") + 1
_COLUMNAS_IMPORTE = (COLUMNAS.index("Precio unitario") + 1, COLUMNAS.index("Precio adjudicado") + 1)
_COLUMNA_PORCENTAJE = COLUMNAS.index("Baja del lote") + 1

# Tamaño de página de la consulta al generar: bastante grande para pocas
# vueltas a la base de datos, pequeño para no cargar el catálogo entero en
# memoria de golpe si crece mucho (CLAUDE.md sección 1: catálogo acumulativo
# para todos los expedientes).
_TAMANO_LOTE = 500

# Categorías de `app.extraccion.lote_tabla.ResultadoAsociacionLote.motivo_ambiguo`
# (docstring de ese módulo): agrupa el texto libre -- que lleva números de
# página/lote concretos, distinto en cada fila -- en un puñado de motivos
# legibles para el resumen. `_OTRO_MOTIVO` cubre cualquier redacción nueva
# que aparezca en el futuro sin que el resumen deje de sumar bien.
_OTRO_MOTIVO = "otro motivo de ambigüedad"
_SIN_MOTIVO = "(sin motivo registrado)"
_CATEGORIAS_MOTIVO = (
    ("banda vacía", "banda vacía: posible continuación de tabla partida entre páginas"),
    ("varias cabeceras de lote", "varias cabeceras de lote en la misma franja"),
    ("ninguna cabecera LOTE", "ninguna cabecera de lote reconocible en la franja"),
    ("no está entre los lotes declarados", "la tabla declara un lote no registrado en el expediente"),
)


def _categoria_motivo(motivo: str | None) -> str:
    if not motivo:
        return _SIN_MOTIVO
    for marcador, categoria in _CATEGORIAS_MOTIVO:
        if marcador in motivo:
            return categoria
    return _OTRO_MOTIVO


def _escribir_resumen(
    libro: Workbook, incluidas: int, excluidas_por_categoria: Counter[str], incluir_pendientes_sin_lote: bool
) -> None:
    hoja = libro.create_sheet("Resumen")
    hoja.append(["Concepto", "Valor"])
    hoja.append(["Líneas en este catálogo", incluidas])
    total_excluidas = sum(excluidas_por_categoria.values())
    hoja.append(["Líneas pendientes de revisión (no incluidas arriba)", total_excluidas])
    hoja.append([])
    if incluir_pendientes_sin_lote:
        hoja.append(["Exportado con las líneas pendientes de revisión incluidas en \"Materiales\".", None])
    elif total_excluidas:
        hoja.append([
            "Motivo (tabla sin lote asignado con seguridad; el material sigue en la cola de revisión interna)",
            "Líneas",
        ])
        for categoria, cantidad in sorted(excluidas_por_categoria.items(), key=lambda kv: -kv[1]):
            hoja.append([categoria, cantidad])
    hoja.column_dimensions["A"].width = 75
    hoja.column_dimensions["B"].width = 12


def generar_excel_catalogo(db: Session, incluir_pendientes_sin_lote: bool = False) -> bytes:
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Materiales"
    hoja.append(COLUMNAS)

    incluidas = 0
    excluidas_por_categoria: Counter[str] = Counter()

    pagina = 1
    while True:
        # CLAUDE.md bloque 2: una línea descartada en la cola de revisión no
        # sale en el Excel que se entrega al cliente, aunque siga en base de
        # datos con su motivo.
        resultado = consultar_catalogo(db, pagina=pagina, tamano_pagina=_TAMANO_LOTE, excluir_descartadas=True)
        for linea, lote, expediente, _documento in resultado.filas:
            if lote is None and not incluir_pendientes_sin_lote:
                excluidas_por_categoria[_categoria_motivo(linea.motivo_revision)] += 1
                continue
            incluidas += 1
            # "El sistema nunca inventa una matriz. Si no cruza, se deja
            # vacío" (CLAUDE.md sección 7): código interno y código de
            # proyecto solo se rellenan cuando el cruce con el Excel de
            # códigos confirmó la fila.
            cruzado = bool(expediente.codigos_cruzados)
            fila = hoja.max_row + 1
            hoja.append([
                expediente.codigo_interno if cruzado else None,
                expediente.codigo_expediente if cruzado else None,
                expediente.codigo_matriz,
                expediente.nombre_proyecto,
                _celda_matricula(linea),
                linea.descripcion,
                _celda_texto(linea.codigo_material),
                _celda_numero(linea.cantidad),
                _celda_numero(linea.precio_unitario),
                _celda_texto(lote.identificador_lote if lote else None),
                linea.comentarios,
                _celda_numero(linea.precio_adjudicado),
                _celda_numero(linea.baja_lote),
            ])
            hoja.cell(row=fila, column=_COLUMNA_CANTIDAD).number_format = _FORMATO_CANTIDAD
            for columna in _COLUMNAS_IMPORTE:
                hoja.cell(row=fila, column=columna).number_format = _FORMATO_IMPORTE
            hoja.cell(row=fila, column=_COLUMNA_PORCENTAJE).number_format = _FORMATO_PORCENTAJE
        if pagina * _TAMANO_LOTE >= resultado.total:
            break
        pagina += 1

    _escribir_resumen(libro, incluidas, excluidas_por_categoria, incluir_pendientes_sin_lote)

    buffer = io.BytesIO()
    libro.save(buffer)
    return buffer.getvalue()
