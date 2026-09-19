"""Etapa 3.5: a qué lote pertenece cada tabla de precios localizada, cuando
el expediente declara varios (CONTEXTO.md, encargo de esta sesión, punto 3 —
"es la parte difícil"). Aprobado explícitamente por el usuario: se decide
por la **posición de la tabla en la página** (la caja delimitadora que ya da
`pdfplumber`), nunca por proximidad textual ni por adivinación.

Una página puede traer más de una tabla de lote (verificado contra el
expediente real 6.25/28510.0027: los lotes pequeños caben enteros y dos
tablas de "LOTE N" distintas comparten página), así que "la página menciona
LOTE N" no es señal suficiente — hace falta saber a cuál de sus tablas
pertenece cada mención.

La regla: cada tabla tiene una franja vertical propia y exclusiva, desde el
fondo de la tabla anterior en la misma página (o el principio de la página,
si es la primera) hasta su propio techo. Si en esa franja —y solo ahí—
aparece una única cabecera "LOTE N", esa tabla es de ese lote: es la
cabecera de sección que la introduce, con certeza estructural, no una
suposición. Si aparecen cero o varias, la tabla es ambigua y no se le asigna
lote por defecto ni por cercanía: sus líneas quedan huérfanas (CONTEXTO.md,
`app.models.LineaCatalogo.lote_id` admite NULL para esto) y van a la cola de
revisión.

**Ambigüedad de "urgencia mutua entre lotes": resuelta (sesión de
verificación del Excel, 2026-09-08, aprobado por el cliente).** Verificado
contra `6.22/28510.0156`/`0122` (repuestos de vía, 2 lotes): la cláusula
administrativa que abre cada lote es "Lote N: <alcance> y, en caso de
urgencia que no pueda ser atendida por el adjudicatario del lote M,
<alcance del otro>" — SIEMPRE menciona los dos números de lote en la misma
frase, así que la franja de cualquiera de los dos lotes trae dos
identificadores y caía en "varias cabeceras" sin serlo de verdad. El número
que abre la sección real es el que precede a los dos puntos ("Lote N:");
el que sigue a "del lote"/"por el lote" es solo la referencia de repuesto
de urgencia, nunca una cabecera de tabla. `_resolver_ambiguedad_urgencia_mutua`
distingue los dos por su posición gramatical en el texto — nunca por el
contenido de las filas de datos (precio, descripción): eso es justo lo que
CONTEXTO.md sección 12 y el caso del balasto (`6.25/28510.0027`) ya
descartaron como riesgo de mezclar lotes distintos por coincidencia.

**Herencia de lote entre páginas de continuación: implementada (misma
sesión).** Cuando la franja no trae NINGÚN rastro de la palabra "LOTE" —ni
siquiera ambiguo— es estructuralmente inequívoco que la tabla sigue siendo
la misma que la anterior: siempre y cuando NO se haya descartado esa
inferencia frente a una franja que sí trae algún indicio, aunque sea
dudoso. `ResultadoAsociacionLote.elegible_para_herencia` señala
exactamente y solo este caso (`app.extraccion.pipeline_anejo` es quien
hereda de verdad, porque es el único que conoce la secuencia de tablas del
documento). Verificado contra el documento real completo de
`6.22/28510.0156` antes de implementar (sesión de verificación del Excel,
2026-09-08): el "Lote 2" de ese documento es una copia íntegra del cuadro
de precios de "Lote 1" (mismos códigos, mismas descripciones, mismos
precios, desplazados 11 páginas) — la transición semicambios→cruzamientos
que parecía un cambio de lote a mitad de tabla es el orden interno del
propio catálogo, idéntico dentro de los dos bloques, y el único punto real
de cambio de lote (p.26) trae su propia cabecera fuerte ("Lote 2:"), nunca
una franja sin ningún rastro. No hay caso real en el corpus, verificado
antes de implementar, donde un lote cambie sin dejar ningún rastro
textual — pero si apareciera, sigue siendo el mismo riesgo que ya asumía
esta sesión de diseño original (docstring previo: "una regla así puede
fallar de formas silenciosas"), nunca el riesgo del balasto (aquí no se
compara nunca el contenido de una fila con otra).

Sesión 2026-09-14 (continuación): "continuación" quiere decir página
contigua. Una tabla separada de la anterior por páginas sin tabla ya no
hereda (`separada_por_paginas`): heredaba el último lote a páginas de
distancia en tablas comunes a todos los lotes (criterios técnicos, precios
de la partida alzada). Y la cabecera "LOTE N" de una tabla también se busca
en sus filas de título y al pie de la página anterior, cuando la franja no
trae nada (ver `asociar_lote_tabla`).

Sesión 2026-09-14 (tercera parte): el anejo de criterios técnicos de una
licitación por lotes se declara a sí mismo del conjunto ("detallar los
materiales a suministrar en el expediente “... 9 LOTES”") y avisa de que "no
coincide" con el cuadro de precios: sus tablas son de todos los lotes a la
vez, nunca de uno (`ResultadoAsociacionLote.del_conjunto_de_lotes`). Y en un
expediente que es uno de los lotes, el texto entre la tabla anterior y esta
decide si una tabla sin cabecera puede ser suya
(`ResultadoAsociacionLote.ultimo_lote_previo`)."""
from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Optional

# Lo que puede ir entre "LOTE" y su número: "N", "Nº", "Nº." y, desde la
# sesión 2026-09-14 (tercera parte), "nº" -- "• Lote nº1: Arrendamiento de
# vagones de bogies" (`4.25/28510.0207`/`0208`, 35 menciones en 6
# documentos): sin él, esas tablas parecían sin cabecera y un expediente de
# lote se quedaba las de los dos lotes.
_ORDINAL = r"(?:N\s*[º°o]|[Nº°])?\.?"

_LOTE_CABECERA_RE = re.compile(r"\bLOTE\s*" + _ORDINAL + r"\s*(\d{1,2})\b", re.IGNORECASE)

# Frase con la que abre el anejo de criterios técnicos de una licitación por
# lotes (plantilla de ADIF, 55 documentos del corpus): "El presente documento
# tiene como objeto detallar los materiales a suministrar en el expediente
# “SUMINISTRO DE ... 9 LOTES”, así como los requisitos técnicos...". En una
# licitación de un solo lote la misma frase no trae "N LOTES" (53
# documentos) y no se toca. Variantes reales de lo que se detalla: "los
# materiales de la especialidad de instalaciones" (`6.25/28510.0019`), "los
# elementos" (`6.25/28510.0214`), "los productos ferroviarios" (con la
# comilla sin mapa Unicode, "(cid:862)").
_CONJUNTO_DE_LOTES_RE = re.compile(
    r"detallar\s+(?:los|las)\s+(?:[^\s“\"]+\s+){1,6}?a\s+suministrar\s+en\s+el\s+expediente\s*[^”\"]{0,260}?"
    r"\b\d{1,2}\s*LOTES\b",
    re.IGNORECASE | re.DOTALL,
)
# Menciones de lote en el texto entre la tabla anterior y esta, cuando hay
# páginas por medio: la negrita simulada de algunos PDF duplica la primera
# letra ("LLote 2: CRUZAMIENTOS", Contratos de `6.22/28510.0122`).
_LOTE_EN_TEXTO_PREVIO_RE = re.compile(r"\bL?LOTE\s*" + _ORDINAL + r"\s*(\d{1,2})\b", re.IGNORECASE)
_ENUMERACION_DE_LOTES_RE = re.compile(
    r"tanto\s+en\s+el\s+lote\s*\d{1,2}\s+como\s+en\s+el\s+lote\s*\d{1,2}", re.IGNORECASE
)

# Motivo de las líneas de esas tablas: la exportación lo cuenta aparte en la
# hoja Resumen.
MOTIVO_TABLA_DEL_CONJUNTO = (
    "tabla del anejo de criterios técnicos, que el documento declara del conjunto de los lotes "
    "(\"materiales a suministrar en el expediente ... N LOTES\"): no es de ningún lote en concreto"
)

# Las dos mitades de la cláusula de "urgencia mutua" (ver docstring del
# módulo): "Lote N:" abre la sección real que sigue; "del lote M"/"por el
# lote M" es la referencia de repuesto de urgencia al OTRO lote, nunca una
# cabecera. Verificado contra las dos variantes reales del corpus ("...que
# no pueda ser atendida por el adjudicatario del lote 2..." y su espejo
# "...del lote 1...").
# Sesión 2026-09-14 (tercera parte): también con punto, "Lote 1. NORTE y,
# en caso de urgencia que no pueda ser atendida por el adjudicatario del
# lote 2, SUR." (`6.22/28510.0125`/`0126`, ANEJO_1 y los dos Contratos) --
# con los dos puntos solamente, las tablas de esos tres documentos quedaban
# ambiguas en cuanto el expediente pasó a saber cuál es su lote.
_LOTE_CABECERA_FUERTE_RE = re.compile(r"\bLOTE\s*" + _ORDINAL + r"\s*(\d{1,2})\s*(?::|\.(?!\d))", re.IGNORECASE)
_LOTE_REFERENCIA_URGENCIA_RE = re.compile(
    r"\b(?:del|por el)\s+lote\s*" + _ORDINAL + r"\s*(\d{1,2})\b", re.IGNORECASE
)


def _resolver_ambiguedad_urgencia_mutua(texto_banda: str, identificadores: list[str]) -> Optional[str]:
    """Solo se llama con exactamente dos identificadores en la franja (ver
    `asociar_lote_tabla`). Devuelve el que abre la sección real ("Lote N:")
    cuando el OTRO aparece únicamente como referencia de urgencia ("del
    lote M") y nunca también como cabecera fuerte por su cuenta — con
    cualquier otra combinación (los dos con cabecera fuerte de verdad, como
    dos tablas reales compartiendo página; ninguno con cabecera fuerte;
    más de dos identificadores) no se adivina, se devuelve `None` y la
    tabla se queda ambigua como hasta ahora."""
    if len(identificadores) != 2:
        return None
    fuertes = set(_LOTE_CABECERA_FUERTE_RE.findall(texto_banda))
    referencias_urgencia = set(_LOTE_REFERENCIA_URGENCIA_RE.findall(texto_banda))
    candidatos_cabecera = [i for i in identificadores if i in fuertes and i not in referencias_urgencia]
    candidatos_solo_referencia = [i for i in identificadores if i in referencias_urgencia and i not in fuertes]
    if len(candidatos_cabecera) == 1 and len(candidatos_solo_referencia) == 1:
        return candidatos_cabecera[0]
    return None


@dataclass(frozen=True)
class ResultadoAsociacionLote:
    identificador_lote: Optional[str]
    # None solo cuando `identificador_lote` no es None. Cuando es ambiguo,
    # distingue el caso "banda vacía" (ver docstring del módulo) de "banda
    # con texto pero sin cabecera reconocible" y de "varias cabeceras en la
    # banda" — necesario para poder contar cada caso por separado.
    motivo_ambiguo: Optional[str]
    # True solo en los dos casos de CERO identificadores en la franja
    # (banda vacía, o banda con texto pero sin ninguna mención de "LOTE") —
    # la única condición bajo la que `app.extraccion.pipeline_anejo` puede
    # heredar el lote de la tabla anterior (ver docstring del módulo).
    # Cualquier mención de "LOTE", por dudosa o no declarada que sea, deja
    # esto en False: la herencia es para la ausencia total de rastro, nunca
    # para un rastro dudoso (encargo explícito del cliente, sesión
    # 2026-09-08).
    elegible_para_herencia: bool = False
    # Sesión 2026-09-14 (tercera parte): la tabla abre el anejo de criterios
    # técnicos de la licitación entera (`_CONJUNTO_DE_LOTES_RE` en el texto
    # que la precede, sin ninguna cabecera "LOTE N" después): no es de
    # ningún lote. Nunca con `identificador_lote`.
    del_conjunto_de_lotes: bool = False
    # Solo para una tabla sin ningún rastro de lote en su franja: el último
    # lote mencionado en el texto de las páginas que la separan de la tabla
    # anterior (o del principio del documento), sin contar las referencias
    # de urgencia ("del lote 2"). En un expediente que es uno de los lotes,
    # si es otro lote, la tabla no se le atribuye (ver
    # `app.extraccion.pipeline_anejo`).
    ultimo_lote_previo: Optional[str] = None
    # `separada_por_paginas` con la franja, el título y la cola limpios (el
    # único caso en que se devuelve el motivo de "tabla separada").
    separada: bool = False
    # Bloque 6, sesión 2026-09-19: el LOTE que la franja SÍ nombra sin
    # ambigüedad cuando resulta no estar entre los declarados del expediente
    # (la red de seguridad de `_asociar_por_texto`). No sirve para atribuir
    # nada -- la tabla sigue huérfana --, pero sí para que sus páginas de
    # continuación, que no traen ningún rastro propio, puedan decir de qué
    # cuadro son en vez de quedarse con un "no se encontró ninguna cabecera"
    # que es verdad y no explica nada. Ver `app.extraccion.pipeline_anejo`.
    identificador_no_declarado: Optional[str] = None


def _ultimo_lote_mencionado(texto: str) -> Optional[str]:
    referencias = {m.start(1) for m in _LOTE_REFERENCIA_URGENCIA_RE.finditer(texto)}
    ultimo = None
    for m in _LOTE_EN_TEXTO_PREVIO_RE.finditer(texto):
        if m.start(1) not in referencias:
            ultimo = m.group(1)
    return ultimo


def _abre_anejo_del_conjunto(texto: str) -> bool:
    """La frase del anejo de criterios aparece en `texto` y ninguna mención
    de lote la sigue (una cabecera "LOTE N" posterior abre una sección de
    lote y manda). La enumeración del propio anejo ("el listado inicial de
    materiales a suministrar ... tanto en el lote 1 como en el lote 2",
    `6.22/28510.0126`) no es una cabecera."""
    texto = _ENUMERACION_DE_LOTES_RE.sub(" ", texto)
    marcas = list(_CONJUNTO_DE_LOTES_RE.finditer(texto))
    if not marcas:
        return False
    return _LOTE_EN_TEXTO_PREVIO_RE.search(texto, marcas[-1].end()) is None


def asociar_lote_tabla(
    pagina_pdfplumber,
    banda_top: float,
    tabla_bbox: tuple[float, float, float, float],
    identificadores_validos: Optional[set[str]] = None,
    texto_titulo_tabla: str = "",
    texto_cola_pagina_anterior: str = "",
    separada_por_paginas: bool = False,
    texto_paginas_previas: str = "",
) -> ResultadoAsociacionLote:
    """`banda_top`: fondo (en coordenadas de página) de la tabla anterior en
    esta misma página, o 0 si `tabla_bbox` es la primera tabla de la
    página — la llama el orquestador de la búsqueda de banda (ver
    `app.extraccion.pipeline_anejo`), que es quien recorre las tablas de una
    página en orden y sabe cuál es "la anterior".

    Sesión 2026-09-14 (continuación, auditoría de las huérfanas recuperadas):
    si la franja no trae ningún rastro de "LOTE", la cabecera de sección
    puede estar en otros dos sitios que también son solo de esta tabla,
    verificados en `4.26/28510.0020` (en su CONTRATO y en su ANEJO, el
    presupuesto de cada lote quedaba sin lote):

    - `texto_titulo_tabla`: dentro de la propia caja de la tabla, en sus
      filas de título -- `pdfplumber` las devuelve como cabecera ("...
      LOTE 1: SUBDIRECCIÓN DE OPERACIONES ESTE Ref. CAPITULO I: MEDIOS
      HUMANOS").
    - `texto_cola_pagina_anterior`: al final de la página anterior, debajo
      de su última tabla, cuando esta es la primera tabla de su página ("El
      Presupuesto Base de Licitación del Lote 1 asciende a ... LOTE 2:
      SUBDIRECCIÓN DE OPERACIONES NORESTE", y la tabla del LOTE 2 empieza
      en la página siguiente).

    Se consultan en ese orden, con las mismas reglas que la franja, y solo
    si la franja está limpia: una franja con rastro manda como siempre.
    Cualquier rastro en ellos cuenta igual que en la franja -- deja la tabla
    fuera de la herencia aunque no se pueda resolver.

    `separada_por_paginas`: la tabla anterior del documento no está en esta
    página ni en la contigua -- hay páginas sin tabla por medio. Entonces
    esta no es la continuación de aquella, aunque su franja esté limpia: no
    es elegible para heredar (y corta la cadena de herencia). El criterio
    aprobado de la herencia son las páginas de continuación, y verificando
    esta sesión salieron dos tablas comunes a todos los lotes que heredaban
    el último lote a páginas de distancia: el cuadro de precios de la
    partida alzada del ANEJO de `4.26/28510.0020` (p.39, 22 páginas después
    del presupuesto del LOTE 2) y la tabla de criterios técnicos del ANEJO
    de `6.25/28510.0214` (p.30, cinco páginas después de la del LOTE 8).

    Sesión 2026-09-14 (tercera parte), con la franja, el título y la cola
    limpios:

    - Si el texto que precede a la tabla abre el anejo de criterios técnicos
      de una licitación por lotes (`_CONJUNTO_DE_LOTES_RE`, sin ninguna
      mención de lote después), la tabla es del conjunto
      (`del_conjunto_de_lotes`): no se hereda nada ni se atribuye a ningún
      lote. Verificado en los siete anejos de criterios del corpus con
      líneas sin lote: la lista reúne los materiales de todos los lotes con
      su propia numeración (`6.23/28510.0051`: "ENF-54 Curva" es P-0994 en el
      cuadro de precios y P-0996 en criterios) y la cantidad, cuando la trae,
      es la "mínima a incluir en cada pedido", no la del lote.
    - `texto_paginas_previas`: el texto de las páginas que separan esta
      tabla de la anterior (con el final de la página de aquella), o todo el
      documento hasta aquí si es la primera. Solo se lee para esas dos
      cosas: la frase del anejo de criterios y `ultimo_lote_previo` --
      nunca para asignar un lote a la tabla, porque ese texto puede ser un
      pliego entero."""
    _x0, techo_tabla, _x1, _bottom = tabla_bbox
    banda = pagina_pdfplumber.crop((0, banda_top, pagina_pdfplumber.width, techo_tabla))
    texto_banda = banda.extract_text() or ""

    if _abre_anejo_del_conjunto(texto_banda):
        # Antes que las menciones de lote de la franja: la frase del anejo
        # es la declaración más fuerte que hay sobre esta tabla.
        return ResultadoAsociacionLote(
            identificador_lote=None,
            motivo_ambiguo=MOTIVO_TABLA_DEL_CONJUNTO,
            elegible_para_herencia=False,
            del_conjunto_de_lotes=True,
        )
    resultado = _asociar_por_texto(texto_banda, identificadores_validos)
    if resultado.elegible_para_herencia:
        for texto in (texto_titulo_tabla, texto_cola_pagina_anterior):
            if _LOTE_CABECERA_RE.search(texto):
                return _asociar_por_texto(texto, identificadores_validos)
        texto_previo = "\n".join(
            t for t in (texto_paginas_previas, texto_cola_pagina_anterior, texto_banda, texto_titulo_tabla) if t
        )
        if _abre_anejo_del_conjunto(texto_previo):
            return ResultadoAsociacionLote(
                identificador_lote=None,
                motivo_ambiguo=MOTIVO_TABLA_DEL_CONJUNTO,
                elegible_para_herencia=False,
                del_conjunto_de_lotes=True,
            )
        ultimo_lote_previo = _ultimo_lote_mencionado(texto_paginas_previas) if texto_paginas_previas else None
        if separada_por_paginas:
            return ResultadoAsociacionLote(
                identificador_lote=None,
                motivo_ambiguo=(
                    "tabla separada de la anterior por páginas sin tabla: no es continuación de ninguna, "
                    "no se hereda el lote"
                ),
                elegible_para_herencia=False,
                ultimo_lote_previo=ultimo_lote_previo,
                separada=True,
            )
        return replace(resultado, ultimo_lote_previo=ultimo_lote_previo)
    return resultado


def _asociar_por_texto(texto_banda: str, identificadores_validos: Optional[set[str]]) -> ResultadoAsociacionLote:
    identificadores = sorted(set(_LOTE_CABECERA_RE.findall(texto_banda)))

    if len(identificadores) == 1:
        identificador = identificadores[0]
        if identificadores_validos is not None and identificador not in identificadores_validos:
            # Red de seguridad: la tabla apunta a un lote que ningún
            # documento de etiqueta fija declaró. No se adivina cuál de los
            # lotes conocidos "debía" ser — huérfana también, y NO elegible
            # para herencia: hay un rastro real de "LOTE", solo que inválido.
            return ResultadoAsociacionLote(
                identificador_lote=None,
                motivo_ambiguo=(
                    f"la tabla se asocia al LOTE {identificador}, que no está entre los lotes "
                    "declarados del expediente"
                ),
                elegible_para_herencia=False,
                identificador_no_declarado=identificador,
            )
        return ResultadoAsociacionLote(identificador_lote=identificador, motivo_ambiguo=None)

    if not identificadores:
        if not texto_banda.strip():
            return ResultadoAsociacionLote(
                identificador_lote=None,
                motivo_ambiguo="banda vacía: posible continuación de tabla partida entre páginas, sin inferir",
                elegible_para_herencia=True,
            )
        return ResultadoAsociacionLote(
            identificador_lote=None,
            motivo_ambiguo="ninguna cabecera LOTE N encontrada en la franja que precede a esta tabla",
            elegible_para_herencia=True,
        )

    resuelto = _resolver_ambiguedad_urgencia_mutua(texto_banda, identificadores)
    if resuelto is not None:
        if identificadores_validos is not None and resuelto not in identificadores_validos:
            return ResultadoAsociacionLote(
                identificador_lote=None,
                motivo_ambiguo=(
                    f"la tabla se asocia al LOTE {resuelto}, que no está entre los lotes "
                    "declarados del expediente"
                ),
                elegible_para_herencia=False,
                identificador_no_declarado=resuelto,
            )
        return ResultadoAsociacionLote(identificador_lote=resuelto, motivo_ambiguo=None)

    return ResultadoAsociacionLote(
        identificador_lote=None,
        motivo_ambiguo=f"varias cabeceras de lote en la franja que precede a esta tabla: {identificadores}",
        elegible_para_herencia=False,
    )
