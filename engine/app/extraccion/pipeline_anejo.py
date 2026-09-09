"""Encadena las etapas 3 a 6 de la cascada (CONTEXTO.md sección 5) sobre un
documento completo: localizar páginas candidatas, extraer sus tablas, mapear
cada cabecera (con caché) y normalizar las filas a líneas de catálogo listas
para `app.catalogo.guardar_lineas_catalogo`. No persiste nada por sí mismo —
el llamador decide el `lote_id` y hace la escritura, esta función solo sabe
de un documento.

Etapa 3.5 (asociación tabla -> lote, `app.extraccion.lote_tabla`) solo se
ejercita cuando `lotes` trae más de una entrada: con un único lote no hay
ambigüedad que resolver, y buscar cabeceras "LOTE N" en cada página sería
trabajo — y riesgo de falso positivo— sin ningún propósito (CONTEXTO.md
sección 6, el mismo principio de "no hacer trabajo que el caso no pide" que
rige cuándo se llama al modelo)."""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

import pdfplumber
from sqlalchemy.orm import Session

from app.catalogo import MOTIVO_MAPEO_INCOHERENTE, _acumular_motivo, construir_lineas_desde_tabla
from app.extraccion.codigo_material import derivar_codigo_material_con_modelo
from app.extraccion.firma_estructural import calcular_firma_estructural
from app.extraccion.localizador import ResultadoLocalizacion, localizar_paginas_candidatas
from app.extraccion.lote_tabla import asociar_lote_tabla
from app.extraccion.mapeo_cabecera import cabecera_sin_senal, evaluar_coherencia_mapeo, mapear_cabecera
from app.extraccion.tabla import extraer_tablas_pagina
from app.extraccion.texto import PaginaTexto
from app.interfaces.model_provider import ModelProvider


@dataclass(frozen=True)
class ResultadoProcesamientoAnejo:
    lineas: list[dict]
    localizacion: ResultadoLocalizacion
    tablas_procesadas: int
    llamadas_modelo: int
    firmas_cabecera: set[str] = field(default_factory=set)
    # Motivo por tabla que no se pudo asociar a un lote sin ambigüedad (ver
    # `app.extraccion.lote_tabla`), en el mismo orden en que aparecieron.
    # Vacía siempre que `lotes` traiga un único lote. El orquestador la usa
    # para componer el motivo de revisión del expediente; el script de
    # medición del corpus la usa para contar cuántas líneas caen en cada
    # caso de ambigüedad.
    tablas_sin_lote: list[str] = field(default_factory=list)
    # Líneas cuyo valor de cantidad/precio/matrícula no se pudo interpretar
    # (CONTEXTO.md, sesión de rodaje 2026-09-03) — `linea["motivo_revision"]`
    # ya lo explica por línea; este contador es solo para que el orquestador
    # sepa si tiene que avisar a nivel de expediente sin releer todas las
    # líneas.
    lineas_con_aviso: int = 0


def procesar_anejo(
    ruta_pdf,
    documento_origen_id: Optional[int],
    expediente_id: int,
    lotes: dict[str, Optional[Decimal]],
    db: Session,
    model_provider: Optional[ModelProvider] = None,
) -> ResultadoProcesamientoAnejo:
    """`lotes`: identificador de lote -> su baja (None si aún no se conoce).
    Con un solo lote (el caso de siempre hasta esta sesión: `{LOTE_UNICO:
    baja}`), todas las líneas se etiquetan con ese único identificador, sin
    pasar por la búsqueda de banda. Con varios, cada tabla localizada se
    asocia a su lote por posición (etapa 3.5); las que resulten ambiguas
    quedan con `identificador_lote=None` en cada línea — el orquestador las
    guarda con `lote_id=None` (huérfanas, CONTEXTO.md encargo de esta sesión
    punto 3: nunca por proximidad ni adivinando)."""
    lineas: list[dict] = []
    tablas_procesadas = 0
    llamadas_modelo = 0
    firmas_cabecera: set[str] = set()
    tablas_sin_lote: list[str] = []
    lineas_con_aviso = 0

    multi_lote = len(lotes) > 1
    identificador_unico = next(iter(lotes)) if len(lotes) == 1 else None
    # Herencia de lote entre páginas de continuación (sesión de verificación
    # del Excel, 2026-09-08, aprobado por el cliente tras verificar contra
    # el documento real completo de `6.22/28510.0156`): el último lote
    # resuelto sin ambigüedad -- directamente o ya heredado--, en el orden
    # en que se procesan las tablas del documento. Solo se usa cuando
    # `asociar_lote_tabla` marca la tabla actual como `elegible_para_herencia`
    # (franja sin NINGÚN rastro de "LOTE", nunca sobre una ambigua) — esa es
    # la única condición, la misma tanto si la franja está vacía como si
    # trae boilerplate sin la palabra "LOTE". Se reinicia a `None` en cada
    # documento (esta función procesa uno solo): heredar de un documento a
    # otro no tendría ninguna base textual.
    ultimo_lote_resuelto: Optional[str] = None
    # Bloque 3 (caché de tablas sin cabecera, sesión de auditoría
    # 2026-09-09): mapeo ya validado de una tabla sin cabecera anterior de
    # ESTE MISMO documento, indexado por `calcular_firma_estructural` (nunca
    # por número de columnas a secas, ver su docstring). Vive solo mientras
    # dura esta llamada -- nunca se persiste ni se comparte entre documentos,
    # a diferencia de `cache_mapeo_cabecera` (CONTEXTO.md sección 6: el
    # mapeo de una firma de CABECERA real sí vale entre documentos porque el
    # texto de la cabecera es una señal fuerte; el contenido de una tabla sin
    # cabecera no lo es lo bastante como para arriesgarse fuera del
    # documento que la vio).
    cache_estructural: dict[tuple, dict[str, Optional[int]]] = {}

    with pdfplumber.open(ruta_pdf) as pdf:
        paginas_texto = [
            PaginaTexto(numero=i, texto=p.extract_text() or "") for i, p in enumerate(pdf.pages, start=1)
        ]
        localizacion = localizar_paginas_candidatas(paginas_texto)

        for candidata in localizacion.candidatas:
            pagina = pdf.pages[candidata.numero - 1]
            tablas_pagina = sorted(extraer_tablas_pagina(pagina), key=lambda t: t.bbox[1])
            banda_top = 0.0
            for tabla in tablas_pagina:
                heredado_de_pagina_anterior = False
                if multi_lote:
                    resultado_asociacion = asociar_lote_tabla(
                        pagina, banda_top, tabla.bbox, identificadores_validos=set(lotes)
                    )
                    identificador_lote = resultado_asociacion.identificador_lote
                    motivo_ambiguo = resultado_asociacion.motivo_ambiguo
                    if (
                        identificador_lote is None
                        and resultado_asociacion.elegible_para_herencia
                        and ultimo_lote_resuelto is not None
                    ):
                        # Ausencia total de rastro de "LOTE" en la franja Y
                        # ya hay un lote resuelto antes en el documento del
                        # que heredar -- nunca se adivina sobre un rastro
                        # dudoso (`elegible_para_herencia` ya lo garantiza) ni
                        # se inventa un lote de la nada (sin ancla previa, se
                        # queda huérfana como siempre).
                        identificador_lote = ultimo_lote_resuelto
                        motivo_ambiguo = None
                        heredado_de_pagina_anterior = True
                    if motivo_ambiguo is not None:
                        tablas_sin_lote.append(
                            f"página {tabla.pagina}: {motivo_ambiguo}"
                        )
                    if identificador_lote is not None:
                        # Se actualiza también cuando `identificador_lote`
                        # viene de heredar (no solo de una cabecera fresca):
                        # así la herencia encadena a través de varias páginas
                        # de continuación seguidas, no solo una.
                        ultimo_lote_resuelto = identificador_lote
                    elif not resultado_asociacion.elegible_para_herencia:
                        # Hallazgo real verificando esta misma sesión contra
                        # `6.25/28510.0027` (balasto, 6 lotes en el
                        # documento, solo 1 y 3 declarados): una mención de
                        # "LOTE" que no se pudo resolver -- rechazada por no
                        # estar declarada, o ambigua de verdad -- SIGUE
                        # siendo la prueba de que aquí empieza una sección
                        # nueva, aunque no se sepa a qué lote. Sin este
                        # reinicio, una página de continuación sin ningún
                        # rastro justo después de esa mención rechazada
                        # heredaría a ciegas el último lote VÁLIDO visto
                        # mucho antes -- p.ej. atribuir a Lote 1 la
                        # continuación de la tabla de Lote 2, solo porque
                        # Lote 2 no está entre los declarados. Se corta la
                        # cadena aquí: la próxima página sin rastro alguno
                        # se queda huérfana, no hereda de antes del corte.
                        ultimo_lote_resuelto = None
                else:
                    identificador_lote = identificador_unico
                    motivo_ambiguo = None
                banda_top = tabla.bbox[3]

                baja_lote = lotes.get(identificador_lote) if identificador_lote is not None else None

                sin_cabecera_propia = cabecera_sin_senal(tabla.cabecera)
                firma_estructural = calcular_firma_estructural(tabla.filas) if sin_cabecera_propia else None
                mapeo_heredado = cache_estructural.get(firma_estructural) if firma_estructural is not None else None

                # Bloque 3 (caché de tablas sin cabecera): un mapeo heredado
                # de otra tabla sin cabecera de ESTE documento con la misma
                # firma estructural nunca se acepta a ciegas -- se valida
                # contra las filas de ESTA tabla (misma comprobación del
                # Bloque 2) antes de usarlo. `calcular_firma_estructural` ya
                # distingue formas realmente distintas con el mismo número de
                # columnas (docstring del módulo, caso real
                # `6.22/28510.0126`), pero esta segunda comprobación es la
                # red de seguridad si dos formas distintas coincidieran en
                # firma por algún caso no visto todavía.
                if mapeo_heredado is not None and evaluar_coherencia_mapeo(mapeo_heredado, tabla.filas) is None:
                    mapeo = mapeo_heredado
                    motivo_mapeo_incoherente = None
                else:
                    resultado_mapeo = mapear_cabecera(tabla.cabecera, tabla.filas[:3], db, model_provider)
                    firmas_cabecera.add(resultado_mapeo.firma)
                    if resultado_mapeo.llamada_modelo:
                        llamadas_modelo += 1
                    mapeo = resultado_mapeo.mapeo
                    # Bloque 2 (auditoría 6.20/28510.0042/0046/0047): una tabla
                    # sin cabecera propia siempre resuelve su mapeo con el
                    # modelo, a ciegas de 2-3 filas de ejemplo
                    # (`cabecera_sin_senal` implica `resultado_mapeo.origen ==
                    # "modelo"`, nunca caché ni determinista). Se valida contra
                    # TODAS sus filas antes de aceptarlo -- un mapeo
                    # incoherente no cambia el lote de la línea (ver el
                    # docstring de `MOTIVO_MAPEO_INCOHERENTE`, motivo de
                    # idempotencia), solo se marca para que `app.exportacion`
                    # la excluya del Excel entregable en vez de contaminarlo
                    # con datos mal columnados.
                    motivo_mapeo_incoherente = (
                        evaluar_coherencia_mapeo(mapeo, tabla.filas) if sin_cabecera_propia else None
                    )
                    if sin_cabecera_propia and firma_estructural is not None and motivo_mapeo_incoherente is None:
                        cache_estructural[firma_estructural] = mapeo
                tablas_procesadas += 1
                lineas_tabla = construir_lineas_desde_tabla(
                    tabla, mapeo, documento_origen_id, expediente_id, baja_lote,
                    orden_inicial=len(lineas),
                )
                for linea in lineas_tabla:
                    if motivo_mapeo_incoherente is not None:
                        linea["motivo_revision"] = _acumular_motivo(
                            linea.get("motivo_revision"),
                            f"{MOTIVO_MAPEO_INCOHERENTE}, tabla descartada del catálogo entregable: "
                            f"{motivo_mapeo_incoherente}",
                        )
                    linea["identificador_lote"] = identificador_lote
                    # Trazabilidad de la herencia (encargo explícito del
                    # cliente, sesión 2026-09-08): una línea cuyo lote viene
                    # de heredarse de la tabla anterior, no de leerse en una
                    # cabecera propia, tiene que poder distinguirse siempre
                    # -- si algún día una herencia resulta ser incorrecta,
                    # hace falta poder encontrar TODAS las líneas afectadas
                    # por ese mecanismo, no solo esta. `True` o `None`, nunca
                    # `False` explícito (mismo convenio que
                    # `heredado_de_matriz`).
                    linea["lote_heredado_de_pagina_anterior"] = True if heredado_de_pagina_anterior else None
                    # `construir_linea_catalogo` (CONTEXTO.md, sesión de rodaje
                    # 2026-09-03) ya puede haber puesto su propio
                    # `motivo_revision` (un valor de cantidad/precio/matrícula
                    # ilegible): se cuenta aparte de la ambigüedad de lote
                    # (que ya se resume en `tablas_sin_lote`) para que el
                    # orquestador sepa si hay algo nuevo que avisar. La
                    # ambigüedad de lote nunca pisa este motivo, se combina.
                    if linea.get("motivo_revision"):
                        lineas_con_aviso += 1
                    if motivo_ambiguo is not None:
                        linea["motivo_revision"] = motivo_ambiguo
                    # Clave que esta línea usaría SI fuese huérfana (mismo
                    # sufijo de página + franja vertical que more abajo) --
                    # se calcula siempre, resuelva o no a un lote real, y
                    # viaja aparte en `clave_huerfana_hipotetica` (nunca en
                    # `clave_linea`, que sigue siendo la clave real de esta
                    # línea). `guardar_lineas_catalogo` la usa para encontrar
                    # y limpiar, con una comparación EXACTA de clave, la fila
                    # huérfana de una pasada anterior que esta línea acaba de
                    # superar (herencia de lote, sesión 2026-09-08) -- nunca
                    # por contenido (descripción/precio): un precio de
                    # referencia puede repetirse igual entre tablas de lotes
                    # DISTINTOS de la misma página (hallazgo real,
                    # `6.25/28510.0027`, "P-1 Balasto..." a 10,85 € en varios
                    # lotes) y comparar por contenido confundiría esa
                    # coincidencia con la misma fila reextraída -- justo el
                    # riesgo de mezclar lotes que esta sesión verificó antes
                    # de aprobar la propuesta. La franja vertical de la
                    # tabla de origen es la única señal que distingue dos
                    # tablas de la misma página sin ambigüedad.
                    linea["clave_huerfana_hipotetica"] = f"{linea['clave_linea']}@p{tabla.pagina}y{int(tabla.bbox[1])}"
                    if identificador_lote is None:
                        # Hallazgo real (expediente 6.25/28510.0027): varias
                        # tablas ambiguas del mismo documento pueden compartir
                        # codigo_precio — el mismo cuadro de precios se repite
                        # por lote (CONTEXTO.md sección 3), así que LOTE 2, 4, 5
                        # y 6 traen todos un "P-1".."P-6" propio. Sin lote que
                        # las separe, `clave_linea` a secas fundiría en una
                        # sola fila los datos de lotes distintos entre sí —
                        # justo lo que hace huérfana a la línea es no saber a
                        # qué lote pertenece, no que sea la misma línea vista
                        # dos veces. Se desambigua por la posición de la
                        # tabla de origen (página + franja vertical), no por
                        # lote.
                        linea["clave_linea"] = linea["clave_huerfana_hipotetica"]
                lineas.extend(lineas_tabla)

    # `Código del material`, vía de modelo (CONTEXTO.md sección 6, bloque 5 de
    # la sesión de vocabulario): `construir_lineas_desde_tabla` (dentro de
    # `construir_linea_catalogo`) ya intentó el vocabulario determinista sin
    # `db`/`model_provider` -- aquí, con las líneas ya construidas y `db`/
    # `model_provider` a mano, se completa lo que la regla no casó, una
    # llamada por término candidato nuevo, cacheada (nunca por línea).
    for linea in lineas:
        if linea.get("codigo_material") is None and linea.get("descripcion"):
            linea["codigo_material"] = derivar_codigo_material_con_modelo(
                linea["descripcion"], db, model_provider
            )

    return ResultadoProcesamientoAnejo(
        lineas=lineas,
        localizacion=localizacion,
        tablas_procesadas=tablas_procesadas,
        llamadas_modelo=llamadas_modelo,
        firmas_cabecera=firmas_cabecera,
        tablas_sin_lote=tablas_sin_lote,
        lineas_con_aviso=lineas_con_aviso,
    )
