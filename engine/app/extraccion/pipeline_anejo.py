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
rige cuándo se llama al modelo). Excepción desde la sesión 2026-09-14
(tercera parte): un expediente que es uno de los lotes (`lote_propio`)
también la ejercita con un solo lote conocido -- los documentos que
comparte con sus hermanos traen las tablas de los demás lotes, y no son
suyas."""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

import pdfplumber
from sqlalchemy.orm import Session

from app.catalogo import (
    MOTIVO_MAPEO_INCOHERENTE,
    _acumular_motivo,
    construir_lineas_desde_tabla,
    resolver_glifos_con_precio_de_otro_lote,
)
from app.extraccion.codigo_material import derivar_codigo_material_con_modelo
from app.extraccion.firma_estructural import calcular_firma_estructural
from app.extraccion.invalidado import INVALIDADO
from app.extraccion.localizador import ResultadoLocalizacion, localizar_paginas_candidatas
from app.extraccion.lote_tabla import MOTIVO_TABLA_DEL_CONJUNTO, asociar_lote_tabla
from app.extraccion.mapeo_cabecera import (
    cabecera_sin_senal,
    corregir_confusion_matricula_codigo_precio,
    completar_matricula_por_contenido,
    corregir_confusion_precio_cantidad,
    derivar_mapeo_por_contenido,
    evaluar_coherencia_mapeo,
    heredar_mapeo_por_geometria,
    mapear_cabecera,
)
from app.extraccion.tabla import extraer_tablas_pagina
from app.extraccion.texto import PaginaTexto, normalizar
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
    # caso de ambigüedad. Las tablas del anejo de criterios del conjunto de
    # los lotes no entran (sesión 2026-09-14, tercera parte): no son una
    # ambigüedad.
    tablas_sin_lote: list[str] = field(default_factory=list)
    # Líneas cuyo valor de cantidad/precio/matrícula no se pudo interpretar
    # (CONTEXTO.md, sesión de rodaje 2026-09-03) — `linea["motivo_revision"]`
    # ya lo explica por línea; este contador es solo para que el orquestador
    # sepa si tiene que avisar a nivel de expediente sin releer todas las
    # líneas.
    lineas_con_aviso: int = 0
    # Bloque 5, sesión 2026-09-18 (quinta parte): líneas cuyo precio en glifos
    # no lo confirmó la aritmética de su propia fila (tabla sin columna de
    # totales) sino el mismo código de precio en otra tabla del mismo cuadro.
    # Se cuentan aparte porque la prueba es distinta y más débil.
    glifos_confirmados_por_otro_lote: int = 0


# Sesión 2026-09-14 (`6.23/28510.0051_ANEJO_3_9d725c710163f3db.pdf`, "NOTA DE
# SUBSANACIÓN A LOS ANEJOS DEL PLIEGO..."): una nota de subsanación repite
# cada partida dos veces, en dos tablas -- "Donde aparece:" con el precio
# equivocado (62.171,96 €) y "Debiendo ser:" con el corregido (136.315,00 €).
# Con la guarda de choques de `app.catalogo._combinar_por_clave` (misma
# sesión), el mismo código con dos precios en un documento se dejaba vacío
# -- correcto para cuadros de lotes distintos, pero aquí el documento dice
# explícitamente cuál vale. Las dos redacciones verificadas en el corpus
# real (4 documentos de 1-2 páginas: 38, 456, 527, 552) ponen siempre la
# corrección DESPUÉS del original, así que en un documento así se conserva
# solo la última aparición de cada código. Solo se miran las primeras
# páginas: un pliego largo menciona "subsanación" en su prosa administrativa
# sin ser una nota de corrección.
_MARCAS_SUBSANACION = (("donde aparece", "debiendo ser"), ("donde dice", "debe decir"))


def _es_nota_de_subsanacion(paginas_texto: list[PaginaTexto]) -> bool:
    texto = normalizar(" ".join(p.texto for p in paginas_texto[:3]))
    return any(original in texto and correccion in texto for original, correccion in _MARCAS_SUBSANACION)


def _quedarse_con_la_correccion(lineas: list[dict]) -> list[dict]:
    ultima: dict[tuple, int] = {}
    for indice, linea in enumerate(lineas):
        if linea.get("codigo_precio"):
            ultima[(linea.get("identificador_lote"), linea["clave_linea"])] = indice
    return [
        linea
        for indice, linea in enumerate(lineas)
        if not linea.get("codigo_precio") or ultima[(linea.get("identificador_lote"), linea["clave_linea"])] == indice
    ]


def procesar_anejo(
    ruta_pdf,
    paginas_texto: list[PaginaTexto],
    documento_origen_id: Optional[int],
    expediente_id: int,
    lotes: dict[str, Optional[Decimal]],
    db: Session,
    model_provider: Optional[ModelProvider] = None,
    lote_propio: Optional[str] = None,
    documento_de_otro_lote: bool = False,
) -> ResultadoProcesamientoAnejo:
    """`paginas_texto`: el texto plano de cada página, ya extraído por el
    llamador (etapa 1 de la cascada, `app.extraccion.texto.
    extraer_texto_cacheado`) -- bloque 6, sesión de rendimiento (`docs/
    sesion-2026-09-12-defecto-mapeo-calidad-interfaz-rendimiento.md` bloque
    4): antes de este cambio, esta función volvía a extraer el texto de
    CADA página con `pdfplumber` (`p.extract_text()`) por su cuenta, para
    localizar páginas candidatas (etapa 3) -- exactamente el mismo trabajo
    que `_clasificar_documentos` ya había hecho segundos antes para
    clasificar la plantilla del documento, sin reutilizarlo. Perfilado real:
    esta segunda pasada explicaba la otra mitad del tiempo que la caché de
    texto (migración 0029) por sí sola no llegaba a eliminar. `ruta_pdf`
    sigue haciendo falta para `pdf.pages[...]` (la extracción de TABLAS,
    etapas 3.5-4, necesita el objeto página real de `pdfplumber` por su
    geometría, no solo su texto).

    `lotes`: identificador de lote -> su baja (None si aún no se conoce).
    Con un solo lote (el caso de siempre hasta esta sesión: `{LOTE_UNICO:
    baja}`), todas las líneas se etiquetan con ese único identificador, sin
    pasar por la búsqueda de banda. Con varios, cada tabla localizada se
    asocia a su lote por posición (etapa 3.5); las que resulten ambiguas
    quedan con `identificador_lote=None` en cada línea — el orquestador las
    guarda con `lote_id=None` (huérfanas, CONTEXTO.md encargo de esta sesión
    punto 3: nunca por proximidad ni adivinando).

    `lote_propio` (sesión 2026-09-14, tercera parte, decisión del cliente):
    el lote de este expediente, cuando es uno de los lotes de la licitación
    y lo sabe (su Contrato o la adjudicación lo ligan a su código). "Las
    tablas que no declaran lote dentro de un expediente que sabe cuál es el
    suyo, son suyas": una tabla sin ningún rastro de lote que no sea
    continuación de otra se le atribuye (`lote_del_expediente` en la
    línea), salvo que sea del anejo de criterios del conjunto de los lotes
    (el documento dice que es de todos, `app.extraccion.lote_tabla`), que
    siga a una tabla de otro lote o ambigua sin páginas por medio, o que la
    última mención de lote antes de ella sea la de otro lote (la cabecera de
    su sección está en una página que el localizador no abrió: los
    Contratos de `6.22/28510.0122` traen el pliego entero, con el "Lote 1:"
    en la p.116 y una tabla suya suelta en la p.122). `documento_de_otro_lote`:
    el documento es el Contrato de otro lote -- sus tablas se siguen
    asociando por su cabecera, pero ninguna sin cabecera se atribuye a este
    expediente."""
    lineas: list[dict] = []
    tablas_procesadas = 0
    llamadas_modelo = 0
    firmas_cabecera: set[str] = set()
    tablas_sin_lote: list[str] = []
    lineas_con_aviso = 0

    multi_lote = len(lotes) > 1 or lote_propio is not None
    identificador_unico = next(iter(lotes)) if len(lotes) == 1 else None
    # Herencia de lote entre páginas de continuación (sesión de verificación
    # del Excel, 2026-09-08, aprobado por el cliente tras verificar contra
    # el documento real completo de `6.22/28510.0156`): el último lote
    # resuelto sin ambigüedad -- directamente o ya heredado--, en el orden
    # en que se procesan las tablas del documento. Solo se usa cuando
    # `asociar_lote_tabla` marca la tabla actual como `elegible_para_herencia`
    # (franja sin NINGÚN rastro de "LOTE", nunca sobre una ambigua) — esa es
    # la única condición, la misma tanto si la franja está vacía como si
    # trae boilerplate sin la palabra "LOTE" -- y, desde la sesión del
    # 2026-09-14, que la tabla anterior esté en la misma página o en la
    # contigua (con páginas sin tabla por medio no es una continuación,
    # `asociar_lote_tabla(separada_por_paginas=...)`). Se reinicia a `None` en cada
    # documento (esta función procesa uno solo): heredar de un documento a
    # otro no tendría ninguna base textual.
    ultimo_lote_resuelto: Optional[str] = None
    # Sesión 2026-09-14 (tercera parte, ver `lote_propio` en el docstring):
    # si `ultimo_lote_resuelto` salió de atribuir una tabla sin cabecera al
    # lote del expediente (para marcar igual sus continuaciones); si se está
    # dentro del anejo de criterios del conjunto de los lotes (hasta la
    # próxima tabla con cabecera de lote); y si la tabla anterior tenía una
    # mención de lote que no se pudo resolver (otro lote, o varios) -- su
    # continuación tampoco es del expediente.
    ultimo_lote_del_expediente = False
    en_anejo_del_conjunto = False
    anterior_de_otro_lote = False
    # (página, fondo) de la última tabla procesada de este documento.
    ultima_tabla: Optional[tuple[int, float]] = None
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
    # Sesión 2026-09-14: junto al mapeo viaja si hubo que corregir la
    # confusión matrícula/`codigo_precio` para obtenerlo -- una tabla que lo
    # reutiliza tiene la misma confusión en sus filas ya guardadas, y sin la
    # marca su `codigo_precio` viejo (la matrícula) sobrevivía al reproceso
    # (`6.21/28510.0016_ANEJO_e40fc4e4546ec90b.pdf` p.20, 12 líneas).
    cache_estructural: dict[tuple, tuple[dict[str, Optional[int]], bool]] = {}
    # Sesión 2026-09-14: mapeo final (ya corregido) y geometría de columnas
    # de la última tabla con cabecera propia de ESTE documento. Una tabla sin
    # cabecera cuyas columnas caen en las mismas posiciones es la misma tabla
    # continuando en otra página (`heredar_mapeo_por_geometria`) -- hereda
    # ese mapeo, validado contra sus filas, antes de probar nada más. Como
    # `cache_estructural`, nunca sale de esta llamada.
    ultima_con_cabecera: Optional[tuple[dict[str, Optional[int]], tuple, bool]] = None
    tablas_con_cabecera = 0
    ultima_cabecera_vista: Optional[str] = None

    with pdfplumber.open(ruta_pdf) as pdf:
        localizacion = localizar_paginas_candidatas(paginas_texto)

        for candidata in localizacion.candidatas:
            pagina = pdf.pages[candidata.numero - 1]
            tablas_pagina = sorted(extraer_tablas_pagina(pagina), key=lambda t: t.bbox[1])
            banda_top = 0.0
            for tabla in tablas_pagina:
                heredado_de_pagina_anterior = False
                lote_del_expediente = False
                if multi_lote:
                    # Sesión 2026-09-14 (continuación, ver
                    # `asociar_lote_tabla`): si esta es la primera tabla de su
                    # página, lo que queda debajo de la última tabla de la
                    # página contigua puede traer su cabecera; si la tabla
                    # anterior está más atrás, con páginas sin tabla por
                    # medio, esta no es su continuación. Tercera parte: en
                    # ese caso, y para la primera tabla del documento, el
                    # texto de las páginas de por medio (o de todo lo
                    # anterior).
                    cola_anterior = ""
                    separada = False
                    paginas_previas = ""
                    if banda_top == 0.0 and ultima_tabla is None:
                        paginas_previas = "\n".join(p.texto for p in paginas_texto if p.numero < candidata.numero)
                    elif banda_top == 0.0:
                        pagina_anterior = pdf.pages[ultima_tabla[0] - 1]
                        cola = pagina_anterior.crop(
                            (0, ultima_tabla[1], pagina_anterior.width, pagina_anterior.height)
                        ).extract_text() or ""
                        if ultima_tabla[0] == candidata.numero - 1:
                            cola_anterior = cola
                        elif ultima_tabla[0] < candidata.numero - 1:
                            separada = True
                            paginas_previas = "\n".join(
                                [cola] + [p.texto for p in paginas_texto if ultima_tabla[0] < p.numero < candidata.numero]
                            )
                    resultado_asociacion = asociar_lote_tabla(
                        pagina, banda_top, tabla.bbox, identificadores_validos=set(lotes),
                        texto_titulo_tabla=" ".join(c for c in tabla.cabecera if c),
                        texto_cola_pagina_anterior=cola_anterior,
                        separada_por_paginas=separada,
                        texto_paginas_previas=paginas_previas,
                    )
                    identificador_lote = resultado_asociacion.identificador_lote
                    motivo_ambiguo = resultado_asociacion.motivo_ambiguo
                    # Sin ningún rastro de lote en la franja, el título ni la
                    # cola: franja limpia (heredable) o tabla separada.
                    sin_rastro = resultado_asociacion.elegible_para_herencia or resultado_asociacion.separada
                    if identificador_lote is not None:
                        ultimo_lote_del_expediente = False
                        en_anejo_del_conjunto = anterior_de_otro_lote = False
                    elif resultado_asociacion.del_conjunto_de_lotes:
                        en_anejo_del_conjunto = True
                        anterior_de_otro_lote = False
                    elif (
                        resultado_asociacion.elegible_para_herencia
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
                        lote_del_expediente = ultimo_lote_del_expediente
                    elif sin_rastro and en_anejo_del_conjunto:
                        # Sigue el anejo de criterios, aunque haya páginas
                        # sin tabla por medio (`6.23/28510.0051`, p.82).
                        motivo_ambiguo = MOTIVO_TABLA_DEL_CONJUNTO
                    elif sin_rastro and resultado_asociacion.separada:
                        anterior_de_otro_lote = False
                    if (
                        identificador_lote is None
                        and lote_propio is not None
                        and not documento_de_otro_lote
                        and sin_rastro
                        and not en_anejo_del_conjunto
                        and not anterior_de_otro_lote
                    ):
                        previo = resultado_asociacion.ultimo_lote_previo
                        if previo is None or previo == lote_propio:
                            identificador_lote = lote_propio
                            motivo_ambiguo = None
                            lote_del_expediente = True
                            ultimo_lote_del_expediente = True
                        else:
                            motivo_ambiguo = (
                                f"tabla sin cabecera de lote, pero la última mención de lote antes de ella es "
                                f"la del LOTE {previo}, no la de este expediente (LOTE {lote_propio}): no se le "
                                "atribuye"
                            )
                            # Su continuación en la página siguiente tampoco
                            # (`6.21/28510.0112`, ANEJO_1 p.19-21).
                            anterior_de_otro_lote = True
                    if identificador_lote is None and not sin_rastro and not resultado_asociacion.del_conjunto_de_lotes:
                        anterior_de_otro_lote = True
                        en_anejo_del_conjunto = False
                    # El anejo de criterios no se "pudo" asociar: el documento
                    # dice que es de todos los lotes. Sus líneas llevan el
                    # motivo (la exportación lo cuenta aparte), pero no manda
                    # el expediente a revisión.
                    if motivo_ambiguo is not None and motivo_ambiguo != MOTIVO_TABLA_DEL_CONJUNTO:
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
                ultima_tabla = (candidata.numero, tabla.bbox[3])

                baja_lote = lotes.get(identificador_lote) if identificador_lote is not None else None

                sin_cabecera_propia = cabecera_sin_senal(tabla.cabecera)
                if not sin_cabecera_propia:
                    # Una cabecera distinta de la anterior abre una tabla
                    # nueva; las siguientes sin cabecera, o que repiten la
                    # misma en cada página (el cuadro de `6.23/28510.0051`), son
                    # la misma tabla (ver `tabla_origen` en las líneas, más
                    # abajo).
                    texto_cabecera = normalizar(" ".join(c for c in tabla.cabecera if c))
                    if texto_cabecera != ultima_cabecera_vista:
                        tablas_con_cabecera += 1
                        ultima_cabecera_vista = texto_cabecera
                firma_estructural = calcular_firma_estructural(tabla.filas) if sin_cabecera_propia else None
                entrada_estructural = cache_estructural.get(firma_estructural) if firma_estructural is not None else None
                mapeo_heredado, heredado_corregido = entrada_estructural if entrada_estructural else (None, False)

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
                # Bloque 3, sesión 2026-09-11: antes de mirar la caché de
                # firma estructural (que guarda un mapeo aprendido del
                # MODELO) o de llamar al modelo, se intenta derivar el mapeo
                # del CONTENIDO -- determinista, sin llamar a nada. Solo
                # tiene efecto cuando la clasificación por contenido es
                # inequívoca (ver docstring de `derivar_mapeo_por_contenido`);
                # si no lo es, devuelve `None` y el camino sigue igual que
                # siempre. Se prueba antes que `mapeo_heredado` a propósito:
                # es estrictamente más fiable que un mapeo de modelo cacheado
                # de otra tabla del mismo documento, y evita ensuciar la
                # caché estructural con nada (esta vía no escribe en ella).
                # Sesión 2026-09-14: antes que nada de lo anterior, la tabla
                # con cabecera de la que esta es continuación (misma
                # geometría de columnas) -- trae la semántica completa de la
                # cabecera real (cantidad, unidad, código de material), que
                # la derivación por contenido nunca asigna. Solo se acepta si
                # cuadra con las filas de ESTA tabla.
                mapeo_por_geometria = None
                if sin_cabecera_propia and ultima_con_cabecera is not None:
                    candidato = heredar_mapeo_por_geometria(
                        ultima_con_cabecera[0], ultima_con_cabecera[1], tabla.columnas_x
                    )
                    if candidato is not None and evaluar_coherencia_mapeo(candidato, tabla.filas) is None:
                        mapeo_por_geometria = candidato
                mapeo_por_contenido = (
                    derivar_mapeo_por_contenido(tabla.filas)
                    if sin_cabecera_propia and mapeo_por_geometria is None
                    else None
                )
                matricula_codigo_corregido = False
                precio_cantidad_corregido = False

                if mapeo_por_geometria is not None:
                    mapeo = mapeo_por_geometria
                    motivo_mapeo_incoherente = None
                    matricula_codigo_corregido = ultima_con_cabecera[2]
                elif mapeo_por_contenido is not None:
                    mapeo = mapeo_por_contenido
                    motivo_mapeo_incoherente = evaluar_coherencia_mapeo(mapeo, tabla.filas)
                elif mapeo_heredado is not None and evaluar_coherencia_mapeo(mapeo_heredado, tabla.filas) is None:
                    mapeo = mapeo_heredado
                    motivo_mapeo_incoherente = None
                    matricula_codigo_corregido = heredado_corregido
                else:
                    resultado_mapeo = mapear_cabecera(tabla.cabecera, tabla.filas[:3], db, model_provider)
                    firmas_cabecera.add(resultado_mapeo.firma)
                    if resultado_mapeo.llamada_modelo:
                        llamadas_modelo += 1
                    mapeo = resultado_mapeo.mapeo
                    # Bloque 3, sesión 2026-09-11 (ampliado bloque 2, sesión
                    # 2026-09-12 continuación): la confusión de columna de
                    # matrícula tomada por `codigo_precio` no es exclusiva de
                    # las tablas sin cabecera propia -- caso real,
                    # `6.21/28510.0149_ANEJO_bd79fa987e814be3.pdf` p.6/9
                    # (tabla de "CRITERIOS TÉCNICOS", cabecera real
                    # `[None, "Nº MATRÍCULA", None, "DESCRIPCIÓN", "CRITERIOS
                    # TECNICOS"]`, sin ninguna columna de precio): el
                    # determinista no la resuelve (le falta `precio_unitario`,
                    # CAMPOS_OBLIGATORIOS) y el modelo, sin la red de
                    # seguridad de `evaluar_coherencia_mapeo` (que solo se
                    # aplica a tablas sin cabecera propia), puede mapear
                    # `codigo_precio` a la misma columna que `matricula` sin
                    # que nada lo detecte -- se cachea así para siempre bajo
                    # `origen="modelo"`. Aplicarla aquí, siempre, es un no-op
                    # seguro sobre un mapeo ya correcto (determinista/caché
                    # nunca reutilizan una columna para dos campos, ver
                    # `intentar_mapeo_determinista`) y corrige el caso real
                    # de arriba en el camino con cabecera.
                    indice_codigo_antes = mapeo.get("codigo_precio")
                    mapeo = corregir_confusion_matricula_codigo_precio(mapeo, tabla.filas)
                    matricula_codigo_corregido = (
                        indice_codigo_antes is not None and mapeo.get("codigo_precio") is None
                    )
                    # Sesión 2026-09-14: una columna de matrícula que la
                    # cabecera nombra de otra forma ("CÓDIGO ADIF") -- ver el
                    # docstring. Antes de guardar el mapeo para heredarlo.
                    mapeo = completar_matricula_por_contenido(mapeo, tabla.filas)
                    if sin_cabecera_propia:
                        # Bloque 2, sesión 2026-09-12 (continuación): misma
                        # idea, para la confusión precio_unitario/cantidad --
                        # ver el docstring de `corregir_confusion_precio_
                        # cantidad`. Acotada a `sin_cabecera_propia` porque
                        # solo ahí existe la red de seguridad
                        # (`evaluar_coherencia_mapeo`) que distingue "esta
                        # tabla de verdad no tiene precio" de "el mapeo
                        # falló" -- fuera de ese camino, nulificar
                        # `precio_unitario` sin esa comprobación se
                        # arriesgaría a esconder un fallo de mapeo real.
                        indice_precio_antes = mapeo.get("precio_unitario")
                        mapeo = corregir_confusion_precio_cantidad(mapeo, tabla.filas)
                        precio_cantidad_corregido = (
                            indice_precio_antes is not None and mapeo.get("precio_unitario") is None
                        )
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
                        cache_estructural[firma_estructural] = (mapeo, matricula_codigo_corregido)
                    if not sin_cabecera_propia and tabla.columnas_x:
                        ultima_con_cabecera = (mapeo, tabla.columnas_x, matricula_codigo_corregido)
                tablas_procesadas += 1
                lineas_tabla = construir_lineas_desde_tabla(
                    tabla, mapeo, documento_origen_id, expediente_id, baja_lote,
                    orden_inicial=len(lineas),
                )
                # Bloque 3, sesión 2026-09-11: cuando el mapeo viene de
                # `derivar_mapeo_por_contenido`, la ausencia de `codigo_precio`
                # no es "esta pasada no lo capturó" (el `None` corriente que
                # `guardar_lineas_catalogo` nunca pisa) -- es una
                # determinación confiada por contenido: esta tabla no tiene
                # columna de código de precio. `app.extraccion.invalidado.
                # INVALIDADO` lo distingue para que SÍ borre un valor ya
                # guardado (caso real que lo motiva: `6.20/28510.0042`/`0046`/
                # `0047` p.35 -- 33 líneas con `codigo_precio` igual a su
                # propia matrícula, guardado por un mapeo de modelo equivocado
                # de antes de este arreglo, que un `None` corriente nunca
                # habría corregido). Nunca se hace para `matricula` aunque el
                # mismo razonamiento aplicaría: `_firma_material` compara
                # `matricula` por igualdad para fundir ecos entre tablas
                # (docstring de esa función) y `INVALIDADO is not None`
                # rompería esa comparación contra una línea de otra tabla que
                # trajera `matricula=None` corriente -- alcance deliberadamente
                # acotado a `codigo_precio`, que no participa en esa firma.
                if mapeo_por_contenido is not None and mapeo_por_contenido.get("codigo_precio") is None:
                    for linea in lineas_tabla:
                        if linea.get("codigo_precio") is None:
                            linea["codigo_precio"] = INVALIDADO
                # Bloque 2, sesión 2026-09-12 (continuación): mismo mecanismo,
                # para cuando `corregir_confusion_matricula_codigo_precio`
                # (arriba, aplicada siempre, no solo sin cabecera propia)
                # determina que `codigo_precio` apuntaba de verdad a la
                # columna de `matricula` -- caso real que lo motiva:
                # `6.21/28510.0149_ANEJO_bd79fa987e814be3.pdf`, 5 líneas
                # guardadas con `codigo_precio` igual a su propia matrícula
                # por un mapeo de modelo de antes de este arreglo, que un
                # `None` corriente nunca habría corregido (la fila ya existe,
                # `guardar_lineas_catalogo` no pisa un campo con `None`).
                if matricula_codigo_corregido:
                    for linea in lineas_tabla:
                        if linea.get("codigo_precio") is None:
                            linea["codigo_precio"] = INVALIDADO
                # Bloque 2, sesión 2026-09-12 (continuación): mismo
                # razonamiento que el bloque de arriba para `codigo_precio`,
                # aplicado a `precio_unitario` -- `corregir_confusion_precio_
                # cantidad` determinó por CONTENIDO que la columna que el
                # modelo eligió no es un precio real, así que un `None`
                # corriente aquí también debe borrar un valor ya guardado en
                # un reproceso anterior (antes de este arreglo). Motivo claro
                # y estable (CONTEXTO.md, encargo de esta sesión): distingue
                # "el documento no declara precio para este material" de
                # cualquier otro motivo_revision, sin mandar la línea a
                # revisión -- no hay nada que un humano pueda confirmar contra
                # el documento que este análisis no haya confirmado ya.
                if precio_cantidad_corregido:
                    for linea in lineas_tabla:
                        if linea.get("precio_unitario") is None:
                            linea["precio_unitario"] = INVALIDADO
                            # `precio_adjudicado` ya se calculó (más arriba,
                            # dentro de `construir_lineas_desde_tabla`) con el
                            # `precio_unitario` todavía equivocado -- sin
                            # este borrado quedaría un importe derivado de un
                            # precio que se acaba de descartar por no ser
                            # real. `None` corriente basta aquí (siempre se
                            # recalcula entero en cada pasada, ver el
                            # comentario de `guardar_lineas_catalogo`).
                            linea["precio_adjudicado"] = None
                            linea["motivo_revision"] = _acumular_motivo(
                                linea.get("motivo_revision"),
                                "sin precio de referencia declarado en el documento origen: la columna que "
                                "el mapeo de esta tabla sin cabecera propia identificaba como precio no "
                                "tiene forma de precio real (coincide con la de cantidad), descartada para "
                                "no guardar un valor inventado -- no es un fallo de extracción, el documento "
                                "no declara precio para este material",
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
                    # Mismo convenio para el lote que viene de ser el del
                    # expediente, no de una cabecera (ver `lote_propio`).
                    linea["lote_del_expediente"] = True if lote_del_expediente else None
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
                    # Sesión 2026-09-14 (tercera parte): de qué tabla del
                    # documento sale la línea (la última con cabecera propia
                    # y sus continuaciones), transitorio como la clave de
                    # arriba -- `app.catalogo._combinar_por_clave` no funde
                    # por firma dos códigos propios distintos de la MISMA
                    # tabla (`6.23/28510.0051`: P-0166 y P-0178, mismo texto
                    # y precio en las p.21 y 22 del mismo cuadro).
                    linea["tabla_origen"] = (documento_origen_id, tablas_con_cabecera)
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

    if _es_nota_de_subsanacion(paginas_texto):
        lineas = _quedarse_con_la_correccion(lineas)

    # Bloque 5, sesión 2026-09-18 (quinta parte): las celdas en glifos que la
    # aritmética de su propia fila no pudo confirmar, resueltas -- si se puede
    # -- con el mismo código de precio ya resuelto en otra tabla del MISMO
    # documento. Va aquí, con el documento entero ya leído, porque la tabla que
    # confirma es otra tabla (otro lote) del mismo cuadro. La llamada quita
    # siempre la marca transitoria `precio_glifos_sin_confirmar`, resuelva o
    # no: nunca puede llegar a `guardar_lineas_catalogo`.
    glifos_confirmados_por_otro_lote = resolver_glifos_con_precio_de_otro_lote(lineas)

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
        glifos_confirmados_por_otro_lote=glifos_confirmados_por_otro_lote,
    )
