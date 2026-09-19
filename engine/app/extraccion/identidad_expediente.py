"""Identidad del expediente (CONTEXTO.md sección 20, "pendiente de resolver";
docs/analisis-corpus.md, sección "Herencia de acuerdo marco"): el código de
un expediente es el que declara su propio Anuncio PCSP en *Número de
Expediente*, nunca la carpeta ni el término con el que se buscó en la
Plataforma. El scraper viejo guardaba `codigo_expediente` con el término de
búsqueda -- para un pedido derivado de acuerdo marco eso era a menudo el
código de su MATRIZ, no el suyo propio (campo *Licitación basada en el
acuerdo marco -> Expediente*, otro dato).

Verificado con los 8 casos reales del corpus (sesión 2026-09-03): cada uno
de los 8 expedientes etiquetados con formato de MATRIZ (`2.18/04703.00NN`,
`2.24/04110.00NN`) trae, dentro de sus propios documentos Anuncio PCSP, un
"Número de Expediente" real y distinto (`6.24/28510.0103`, `.0100`, `.0101`,
`.0102`, `.0111`, `6.25/28510.0215`, `.0175`, `.0248`) -- confirma que el
patrón es "la fila representa al pedido pero está etiquetada con el código
de su matriz", no una anomalía de un único caso.

Corrige la identidad en el sitio, no crea una fila nueva: `codigo_expediente`
es la clave de idempotencia (CONTEXTO.md sección 9.9) pero no es una clave
externa de ninguna otra tabla (`documentos.expediente_id`,
`lotes.expediente_id`, `lineas_catalogo.expediente_id` y
`trabajos_cola.expediente_id` son todos por `id`, no por código), así que
renombrarla en el sitio no pierde ni duplica nada de lo ya extraído.

Solo se aplica en la etapa de extracción (`app.extraccion.orquestador`), no
en el scraping: el scraping descarga bytes sin leer el contenido, y la
identidad real solo se conoce leyendo el texto del Anuncio PCSP -- que es
exactamente lo que ya hace la etapa 2 de la cascada (CONTEXTO.md sección 5).
"En la ingesta y en el scraping" del encargo se cumple end-to-end: un
expediente se registra por primera vez (POST /expedientes o
`herencia_matriz.resolver_o_encolar_matriz`) con el código que se tenga a
mano -- casi siempre el término de búsqueda -- y esta función es lo que lo
corrige la primera vez que sus propios documentos se leen de verdad, antes
de que ningún otro dato (importes, baja, matriz declarada, cruce con el
Excel) se ancle a la identidad equivocada.
"""
from __future__ import annotations

from typing import Iterable, Optional

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.extraccion.campos_pcsp import extraer_campos_anuncio_pcsp
from app.extraccion.cruce_codigos import asignar_matriz, normalizar_codigo_expediente
from app.extraccion.traza import registrar_traza
from app.models import (
    DocumentoExpediente,
    Expediente,
    LineaCatalogo,
    Lote,
    SindicacionExpediente,
    TipoDocumento,
    TrabajoCola,
    TrazaOrigen,
)


def corregir_identidad_expediente(db: Session, expediente: Expediente, documentos: Iterable) -> Optional[str]:
    """Si los Anuncio PCSP propios del expediente declaran un "Número de
    Expediente" distinto del `codigo_expediente` guardado, corrige la fila:
    el código del documento pasa a ser `codigo_expediente`, y el código con
    el que estaba registrado (que en la práctica siempre resulta ser el de
    su MATRIZ, nunca un dato arbitrario) pasa a `codigo_matriz` si el
    expediente no traía ya uno declarado.

    `documentos` es la lista `_Documento` de `app.extraccion.orquestador`
    (duck-typed aquí como `.tipo`, `.paginas`, `.documento.id`, para no
    crear un import circular con el módulo que la define).

    Nunca corrige a ciegas: si los distintos Anuncio PCSP del mismo
    expediente declaran códigos distintos entre sí, o si el código real ya
    pertenece a otra fila (un caso de fusión, no de renombrado -- fuera de
    alcance de esta función, CONTEXTO.md sección 9.9), se deja la identidad
    como está y se devuelve un motivo para la cola de revisión en vez de
    adivinar."""
    codigos_declarados: dict[str, tuple] = {}
    for item in documentos:
        if item.tipo != TipoDocumento.anuncio_pcsp:
            continue
        campos = extraer_campos_anuncio_pcsp(item.paginas)
        if campos.numero_expediente is None:
            continue
        codigo = normalizar_codigo_expediente(campos.numero_expediente.valor)
        if codigo is None:
            continue
        codigos_declarados.setdefault(codigo, (item.documento.id, campos.numero_expediente))

    if not codigos_declarados:
        return None

    if len(codigos_declarados) > 1:
        return (
            "los documentos Anuncio PCSP de este expediente declaran 'Número de Expediente' distintos entre sí "
            f"({', '.join(sorted(codigos_declarados))}); no se corrige la identidad sin revisión"
        )

    codigo_real, (documento_id, campo) = next(iter(codigos_declarados.items()))
    codigo_actual = normalizar_codigo_expediente(expediente.codigo_expediente)
    if codigo_real == codigo_actual:
        return None

    colision = db.execute(
        select(Expediente.id).where(Expediente.codigo_expediente == codigo_real, Expediente.id != expediente.id)
    ).scalar_one_or_none()
    if colision is not None:
        return (
            f"el Anuncio PCSP declara 'Número de Expediente' {codigo_real}, pero ya existe otro expediente "
            f"(id {colision}) con ese código; no se fusiona automáticamente, hace falta revisión manual"
        )

    codigo_anterior = expediente.codigo_expediente
    expediente.codigo_expediente = codigo_real
    # `codigo_anterior` nunca puede coincidir con el `codigo_expediente` ya
    # renombrado (se comprobó `codigo_real != codigo_actual` más arriba), así
    # que `asignar_matriz` nunca lanza `AutoreferenciaMatrizError` aquí --
    # solo puede devolver `False` porque ya había una matriz declarada
    # distinta, el caso que gestiona el `if` de abajo.
    if not asignar_matriz(expediente, codigo_anterior):
        if normalizar_codigo_expediente(expediente.codigo_matriz) != normalizar_codigo_expediente(codigo_anterior):
            # No debería pasar en la práctica (el propio Anuncio suele
            # autorreferenciarse como su propia matriz cuando la fila está
            # mal etiquetada), pero si el expediente ya traía una matriz
            # declarada distinta del código con el que estaba registrado, no
            # se pisa en silencio -- se marca igual que hace
            # `asegurar_cruce_codigos` para el mismo tipo de discrepancia
            # (CONTEXTO.md sección 20, requisito 1).
            expediente.matriz_conflicto = True

    registrar_traza(
        db,
        entidad_tipo="expediente",
        entidad_id=expediente.id,
        campo="codigo_expediente",
        documento_id=documento_id,
        pagina=campo.pagina,
        fragmento=campo.fragmento,
        valor_extraido=codigo_real,
    )
    return None


# Bloque 4, sesión 2026-09-19 (decisión del cliente). El caso que el
# docstring de `corregir_identidad_expediente` dejaba explícitamente fuera
# ("un caso de fusión, no de renombrado"), ahora resuelto para la única
# forma de la que se puede afirmar con certeza estructural que dos filas son
# el mismo expediente.
#
# El caso real: `19/28510` y `6.19/28510.0129` los creó la misma ejecución
# del barrido del buscador, con 0,1 s de diferencia, el 16/09/2026. Tienen el
# mismo título, el mismo importe, la misma adjudicación, la misma baja y **los
# mismos dos documentos** (los mismos `documentos.id`, es decir el mismo hash
# de fichero). `19/28510` es literalmente `6.19/28510.0129` recortado: el
# buscador de la Plataforma devuelve una subcadena y `app.criterio_expediente`
# la acepta a propósito ("sin mirar la forma del resto del código", decisión
# del cliente de la sesión 2026-09-15), así que el recorte entra como
# expediente propio. No es un fallo del extractor; es una consecuencia medida
# de ese criterio, y aquí se deshace sin tocarlo.


def detectar_expediente_recortado(db: Session, expediente: Expediente) -> Optional[Expediente]:
    """El expediente del que este es un recorte, o `None`. Las TRES
    condiciones a la vez, y ninguna de ellas es una heurística de parecido:

    1. su código es una **subcadena** del del otro, y más corto -- "19/28510"
       dentro de "6.19/28510.0129"; nunca al revés, nunca un parecido;
    2. los dos cuelgan **exactamente del mismo conjunto de documentos**, y no
       está vacío: el mismo fichero (mismo hash) bajo los dos códigos es la
       prueba de que la Plataforma los publicó en una sola ficha;
    3. declaran el **mismo título**.

    Con un solo candidato se devuelve; con varios, no se fusiona nada (no
    hay a quién unificar sin adivinar). Medido sobre los 613 expedientes del
    corpus: un único par lo cumple."""
    codigo = (expediente.codigo_expediente or "").strip()
    if not codigo:
        return None
    documentos_propios = _documentos_de(db, expediente.id)
    if not documentos_propios:
        return None
    candidatos = [
        otro
        for otro in db.execute(
            select(Expediente).where(Expediente.id != expediente.id)
        ).scalars()
        if len(otro.codigo_expediente or "") > len(codigo)
        and codigo in (otro.codigo_expediente or "")
        and (otro.nombre_proyecto or "") == (expediente.nombre_proyecto or "")
        and _documentos_de(db, otro.id) == documentos_propios
    ]
    return candidatos[0] if len(candidatos) == 1 else None


def _documentos_de(db: Session, expediente_id: int) -> frozenset[int]:
    return frozenset(
        db.execute(
            select(DocumentoExpediente.documento_id).where(
                DocumentoExpediente.expediente_id == expediente_id
            )
        ).scalars()
    )


def fusionar_en(db: Session, duplicado: Expediente, canonico: Expediente) -> str:
    """Pasa al expediente canónico todo lo que cuelga del duplicado y borra
    el duplicado. Devuelve el texto para el registro del ciclo.

    Nada se pierde y nada se duplica: los documentos ya son los mismos (es
    una de las tres condiciones de `detectar_expediente_recortado`, así que
    los enlaces del duplicado son redundantes y se borran, no se mueven); las
    líneas, los lotes, los trabajos de cola, las entradas de sindicación y
    las trazas se reapuntan al canónico salvo que este ya tenga una fila con
    la misma clave, en cuyo caso la del duplicado se borra. Tras esto no
    queda ni una fila apuntando al código viejo, que es justo lo que había
    que garantizar."""
    identificadores_canonicos = {
        l.identificador_lote
        for l in db.execute(select(Lote).where(Lote.expediente_id == canonico.id)).scalars()
    }
    lineas_movidas = lotes_movidos = 0
    for lote in db.execute(select(Lote).where(Lote.expediente_id == duplicado.id)).scalars().all():
        if lote.identificador_lote in identificadores_canonicos:
            # El canónico ya tiene ese lote: las líneas del duplicado son las
            # mismas filas leídas de los mismos documentos, con la misma
            # clave. Se borran con su lote en vez de chocar contra
            # `uq_lote_expediente_identificador`.
            db.execute(delete(LineaCatalogo).where(LineaCatalogo.lote_id == lote.id))
            db.execute(
                delete(TrazaOrigen).where(TrazaOrigen.entidad_tipo == "lote", TrazaOrigen.entidad_id == lote.id)
            )
            db.delete(lote)
        else:
            lote.expediente_id = canonico.id
            lotes_movidos += 1

    for linea in db.execute(
        select(LineaCatalogo).where(LineaCatalogo.expediente_id == duplicado.id)
    ).scalars().all():
        linea.expediente_id = canonico.id
        lineas_movidas += 1

    db.execute(
        delete(DocumentoExpediente).where(DocumentoExpediente.expediente_id == duplicado.id)
    )
    for modelo in (TrabajoCola, SindicacionExpediente):
        db.execute(
            update(modelo).where(modelo.expediente_id == duplicado.id).values(expediente_id=canonico.id)
        )
    db.execute(
        update(Expediente)
        .where(Expediente.matriz_expediente_id == duplicado.id)
        .values(matriz_expediente_id=canonico.id)
    )
    db.execute(
        delete(TrazaOrigen).where(
            TrazaOrigen.entidad_tipo == "expediente", TrazaOrigen.entidad_id == duplicado.id
        )
    )
    codigo_viejo = duplicado.codigo_expediente
    db.delete(duplicado)
    db.commit()
    return (
        f"expediente {codigo_viejo} unificado con {canonico.codigo_expediente}: es el mismo número "
        f"recortado por el buscador de la Plataforma (mismo título, mismos documentos), "
        f"{lotes_movidos} lote(s) y {lineas_movidas} línea(s) pasan al código completo"
    )
