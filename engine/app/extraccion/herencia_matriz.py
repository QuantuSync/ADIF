"""Herencia de acuerdo marco (docs/analisis-corpus.md hallazgo 3): un pedido
derivado de un acuerdo marco no trae su propio cuadro de precios ni su propia
baja — viven en los documentos de la MATRIZ, el expediente del acuerdo marco
del que cuelga el pedido (CONTEXTO.md sección 2). Este módulo resuelve esa
matriz como expediente propio (creándola y encolando su descarga o su
extracción si hace falta) y copia lo que el pedido no tiene, sin perder
trazabilidad ni inventar nada que la matriz tampoco tenga.

Reutiliza toda la infraestructura ya existente en vez de crear una paralela:
`app.queue.encolar_trabajo` para descargar/extraer la matriz (mismos tipos de
trabajo que cualquier expediente, nunca ejecutados en línea), y
`app.catalogo.guardar_lineas_catalogo` para escribir las líneas heredadas
(mismo mecanismo idempotente por clave, así que reprocesar no duplica nada).
`documento_origen_id`/`pagina`/`fragmento` de `LineaCatalogo` ya apuntan al
documento real de origen sea cual sea su expediente, así que copiarlos tal
cual desde la línea de la matriz ya es la trazabilidad completa que pide el
encargo; `heredado_de_matriz` (en `LineaCatalogo`, y `baja_heredada_de_matriz`
en `Lote` para la baja) es solo una marca de lectura rápida para la web.

Límite conocido, documentado en CONTEXTO.md: reprocesar una matriz ya resuelta
no refresca sola a los pedidos que ya heredaron de ella — hay que reencolar
esos pedidos a mano. `reencolar_pedidos_esperando_matriz` solo dispara
cuando la matriz TERMINA un trabajo de extracción, no en cualquier reproceso
posterior.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.catalogo import guardar_lineas_catalogo
from app.extraccion.cruce_codigos import normalizar_codigo_expediente
from app.extraccion.lote_declarado import (
    extraer_expediente_principal_declarado,
    extraer_lote_declarado,
)
from app.extraccion.traza import registrar_traza
from app.models import (
    DocumentoExpediente,
    EstadoExpediente,
    EstadoTrabajo,
    Expediente,
    LineaCatalogo,
    Lote,
    ModeloPrecio,
    TrabajoCola,
    TrazaOrigen,
)
from app.queue import encolar_trabajo

# Tope defensivo para recorrer la cadena de matrices al comprobar ciclos
# (encargo de la sesión de herencia, requisito 1: "protege contra el ciclo").
# En la práctica una cadena real no debería pasar de 1-2 saltos; este límite
# es solo para cortar si los datos de origen están mal, no una cifra con
# significado de dominio.
_PROFUNDIDAD_MAXIMA_CADENA = 10

_ESTADOS_TERMINADOS = frozenset({
    EstadoExpediente.completado, EstadoExpediente.pendiente_revision, EstadoExpediente.fallido,
    # `sin_publicar` (CONTEXTO.md sección 22) es tan terminal como `fallido`
    # para efectos de esta resolución -- sin incluirlo aquí, una matriz sin
    # publicar (sin documentos, sin trabajo activo) se releería como "hace
    # falta encolar su descarga" en cada pedido que la referencia, reintentando
    # para siempre una búsqueda ya confirmada sin resultado.
    EstadoExpediente.sin_publicar,
})


class EstadoResolucionMatriz(str, enum.Enum):
    sin_matriz = "sin_matriz"
    ciclo = "ciclo"
    en_proceso = "en_proceso"
    lista = "lista"


@dataclass(frozen=True)
class ResolucionMatriz:
    estado: EstadoResolucionMatriz
    matriz: Optional[Expediente] = None
    motivo: Optional[str] = None


@dataclass(frozen=True)
class ResultadoHerencia:
    motivo_revision: Optional[str]
    lineas_creadas: int = 0
    lineas_actualizadas: int = 0
    # Las líneas que esta herencia escribió: el orquestador borra las
    # heredadas de pasadas anteriores que ya no están aquí.
    ids_tocadas: frozenset[int] = frozenset()


def _forma_ciclo(db: Session, pedido: Expediente, codigo_matriz_normalizado: str) -> bool:
    """Corta antes de crear/seguir una matriz si eso forma un ciclo: el
    propio pedido referenciándose a sí mismo como su propia matriz (ya ha
    pasado con datos reales del corpus, 6.25/28510.0027 — de ahí el commit
    "evita inventar la matriz cuando el expediente es su propia MATRIZ" en
    `cruce_codigos.buscar`, que cubre la vía del Excel pero no una matriz mal
    declarada en el propio Anuncio PCSP) o una cadena de matrices que vuelve
    sobre un expediente ya visitado (A -> B -> A, o más larga)."""
    codigo_pedido = normalizar_codigo_expediente(pedido.codigo_expediente)
    if codigo_matriz_normalizado == codigo_pedido:
        return True

    visitados = {codigo_pedido}
    codigo_actual: Optional[str] = codigo_matriz_normalizado
    profundidad = 0
    while codigo_actual is not None:
        if codigo_actual in visitados:
            return True
        if profundidad >= _PROFUNDIDAD_MAXIMA_CADENA:
            # No se cerró el ciclo en el límite de saltos: se corta igual,
            # por seguridad, no porque se haya demostrado un ciclo real.
            return True
        visitados.add(codigo_actual)
        candidato = db.execute(
            select(Expediente).where(Expediente.codigo_expediente == codigo_actual)
        ).scalar_one_or_none()
        if candidato is None or not candidato.codigo_matriz:
            return False
        codigo_actual = normalizar_codigo_expediente(candidato.codigo_matriz)
        profundidad += 1
    return False


def _hay_trabajo_activo(db: Session, tipo: str, expediente_id: int) -> bool:
    return db.execute(
        select(TrabajoCola.id).where(
            TrabajoCola.tipo == tipo,
            TrabajoCola.expediente_id == expediente_id,
            TrabajoCola.estado.in_((EstadoTrabajo.pendiente, EstadoTrabajo.en_proceso)),
        ).limit(1)
    ).scalar_one_or_none() is not None


def resolver_o_encolar_matriz(db: Session, pedido: Expediente) -> ResolucionMatriz:
    """Punto 1 y 2 del encargo: identificar la matriz (ya extraída en
    `pedido.codigo_matriz` por la etapa 2 de la cascada o por el cruce con el
    Excel de códigos — ver `app.extraccion.cruce_codigos`), crearla como
    expediente propio si no existe, y encolar lo que le falte: su descarga
    si no tiene documentos, su extracción si los tiene pero no se ha
    procesado. Nunca se ejecuta nada en línea, siempre por la cola, igual
    que cualquier otro expediente (CONTEXTO.md sección 10)."""
    if not pedido.codigo_matriz:
        return ResolucionMatriz(EstadoResolucionMatriz.sin_matriz)

    codigo_normalizado = normalizar_codigo_expediente(pedido.codigo_matriz)
    if codigo_normalizado is None:
        return ResolucionMatriz(EstadoResolucionMatriz.sin_matriz)

    if _forma_ciclo(db, pedido, codigo_normalizado):
        return ResolucionMatriz(
            EstadoResolucionMatriz.ciclo,
            motivo=(
                f"la matriz declarada ('{pedido.codigo_matriz}') forma un ciclo con este expediente o con "
                "su propia cadena de matrices; no se puede heredar sin entrar en bucle"
            ),
        )

    matriz = db.execute(
        select(Expediente).where(Expediente.codigo_expediente == codigo_normalizado)
    ).scalar_one_or_none()
    if matriz is None:
        matriz = Expediente(codigo_expediente=codigo_normalizado)
        db.add(matriz)
        try:
            db.commit()
        except IntegrityError:
            # Carrera con otro pedido que apunta a la misma matriz y la creó
            # primero (codigo_expediente es UNIQUE): no es un error real de
            # este pedido, solo hay que releerla.
            db.rollback()
            matriz = db.execute(
                select(Expediente).where(Expediente.codigo_expediente == codigo_normalizado)
            ).scalar_one_or_none()
        else:
            db.refresh(matriz)

    if pedido.matriz_expediente_id != matriz.id:
        pedido.matriz_expediente_id = matriz.id
        db.commit()

    if matriz.estado in _ESTADOS_TERMINADOS:
        return ResolucionMatriz(EstadoResolucionMatriz.lista, matriz=matriz)

    documento_existente = db.execute(
        select(DocumentoExpediente.id).where(DocumentoExpediente.expediente_id == matriz.id).limit(1)
    ).scalar_one_or_none()

    if documento_existente is None:
        if not _hay_trabajo_activo(db, "descargar_expediente", matriz.id):
            encolar_trabajo(db, tipo="descargar_expediente", expediente_id=matriz.id)
    elif matriz.estado in (EstadoExpediente.pendiente, EstadoExpediente.descargado):
        if not _hay_trabajo_activo(db, "extraer_expediente", matriz.id):
            encolar_trabajo(db, tipo="extraer_expediente", expediente_id=matriz.id)
    # descargando / extrayendo: ya en curso -por este pedido o por otro que
    # comparte la misma matriz-, no hace falta encolar nada más.

    return ResolucionMatriz(EstadoResolucionMatriz.en_proceso, matriz=matriz)


def intentar_heredar_de_matriz(
    db: Session,
    pedido: Expediente,
    matriz: Expediente,
    lote_pedido: Lote,
    total_lineas_propias: int,
) -> ResultadoHerencia:
    """Puntos 3 y 4 del encargo: heredar del acuerdo marco lo que el pedido
    no tiene, pero solo cuando el pedido no aportó nada propio para su
    lote -- "lo propio del pedido manda" se decide a nivel de tabla
    completa, no fila a fila (visto bueno de la sesión de diseño): si el
    pedido ya trae alguna línea propia, no se mezcla con la de la matriz, se
    manda a revisión con el detalle exacto de cuántas líneas tiene cada uno
    (requisito 3 de los ajustes: "sin ese dato, quien revise no puede
    decidir")."""
    lotes_matriz = matriz.lotes
    if not lotes_matriz:
        # Bloque 6, sesión 2026-09-18 (continuación): cuando el acuerdo marco
        # del pedido no está publicado, su propio anuncio a veces declara el
        # **expediente principal** de la licitación por lotes de la que cuelga
        # ("expediente principal 4.23/04110.0256 lote 4: guantes..."). Ese
        # número no se escribe nunca en `codigo_matriz` -- el campo fijo del
        # anuncio manda, y el sistema no inventa matrices (CONTEXTO.md sección
        # 7) --, pero decirlo en el motivo ahorra abrir el PDF para saber
        # dónde mirar.
        principal = extraer_expediente_principal_declarado(pedido.nombre_proyecto)
        pista = ""
        if principal and principal != matriz.codigo_expediente:
            lote_declarado = extraer_lote_declarado(pedido.nombre_proyecto)
            detalle_lote = f", lote {lote_declarado}" if lote_declarado else ""
            pista = (
                f"; el anuncio de este pedido declara además el expediente principal "
                f"{principal}{detalle_lote}"
            )
        return ResultadoHerencia(
            motivo_revision=(
                f"la matriz {matriz.codigo_expediente} no tiene ningún lote registrado "
                f"(estado: {matriz.estado.value}){pista}"
            )
        )
    if len(lotes_matriz) > 1:
        # Bloque 6, sesión 2026-09-18 (continuación): una matriz multi-lote ya
        # no es un callejón sin salida cuando el pedido **declara** su lote en
        # el "Objeto del Contrato" que publica la Plataforma
        # (`app.extraccion.lote_declarado`). Es una declaración estructural del
        # órgano de contratación, no un parecido de texto entre descripciones:
        # emparejar por parecido sigue prohibido, y si el número declarado no
        # casa con ningún lote de la matriz esto se va a revisión igual que
        # antes, diciendo qué se leyó.
        declarado = extraer_lote_declarado(pedido.nombre_proyecto)
        candidatos = [l for l in lotes_matriz if l.identificador_lote == declarado] if declarado else []
        if len(candidatos) != 1:
            identificadores = ", ".join(sorted(l.identificador_lote or "?" for l in lotes_matriz))
            if declarado is None:
                detalle = "y este pedido no declara a cuál pertenece"
            else:
                detalle = (
                    f"y este pedido declara el lote {declarado}, que no está entre los suyos "
                    f"({identificadores})"
                )
            return ResultadoHerencia(
                motivo_revision=(
                    f"la matriz {matriz.codigo_expediente} es multi-lote ({len(lotes_matriz)} lotes) "
                    f"{detalle}; no se puede heredar sin adivinar"
                )
            )
        lote_matriz = candidatos[0]
    else:
        lote_matriz = lotes_matriz[0]

    # Ajuste 4 del encargo (descubrimiento inverso, hallazgo de paso): un
    # pedido heredado de una matriz de segunda familia (CONTEXTO.md sección
    # 16, docs/identidad-expediente.md sección 28) se quedaba con `baja_lote`
    # NULL sin ninguna marca de que fuera a propósito -- `modelo_precio` del
    # pedido seguía en `fijo` (su valor por defecto) porque sus propios
    # documentos nunca traen el marcador literal que lo detecta (solo vive en
    # los de la matriz, verificado en la sesión de descubrimiento inverso:
    # los 18 documentos reales de los 9 pedidos conocidos son formularios
    # PCSP sin cuadro de precios ni marcador). Sin esto, un `baja_lote` vacío
    # se leía igual que un fallo real de extracción. Idempotente en el mismo
    # sentido que `app.extraccion.orquestador`: un reproceso en el que la
    # matriz ya no declare el modelo indexado no deja un valor heredado
    # obsoleto en el pedido.
    if lote_matriz.modelo_precio == ModeloPrecio.indexado_por_pedido:
        lote_pedido.modelo_precio = ModeloPrecio.indexado_por_pedido
        lote_pedido.coeficiente_transformacion = lote_matriz.coeficiente_transformacion
    elif lote_pedido.modelo_precio == ModeloPrecio.indexado_por_pedido:
        lote_pedido.modelo_precio = ModeloPrecio.fijo
        lote_pedido.coeficiente_transformacion = None
    db.commit()

    lineas_matriz = db.execute(
        select(LineaCatalogo)
        .where(LineaCatalogo.lote_id == lote_matriz.id)
        .order_by(LineaCatalogo.orden_aparicion)
    ).scalars().all()

    if not lineas_matriz and lote_matriz.baja_lote is None:
        detalle = f": {matriz.error}" if matriz.error else ""
        return ResultadoHerencia(
            motivo_revision=f"la matriz {matriz.codigo_expediente} tampoco tiene cuadro de precios ni baja{detalle}"
        )

    if total_lineas_propias > 0:
        return ResultadoHerencia(
            motivo_revision=(
                f"el pedido trae {total_lineas_propias} línea(s) propia(s) de catálogo, y la matriz "
                f"{matriz.codigo_expediente} trae {len(lineas_matriz)}; no se combina una tabla propia "
                "parcial con la de la matriz, hay que revisar cuál es la correcta"
            )
        )

    baja_heredada = lote_pedido.baja_lote is None
    baja_efectiva = lote_pedido.baja_lote if lote_pedido.baja_lote is not None else lote_matriz.baja_lote

    if baja_heredada and baja_efectiva is not None:
        lote_pedido.baja_lote = baja_efectiva
        lote_pedido.baja_heredada_de_matriz = True
        # La traza de la baja heredada apunta al mismo documento/página de la
        # matriz que ya la trazó (CONTEXTO.md sección 9.10): "cada línea
        # heredada debe dejar constancia... con su documento y página de
        # origen" aplica igual a la baja del lote, no solo a las líneas.
        traza_matriz = db.execute(
            select(TrazaOrigen)
            .where(
                TrazaOrigen.entidad_tipo == "lote",
                TrazaOrigen.entidad_id == lote_matriz.id,
                TrazaOrigen.campo == "baja_declarada",
            )
            .order_by(TrazaOrigen.id.desc())
        ).scalars().first()
        # `trazas_origen.documento_id` es NOT NULL (CONTEXTO.md sección 9.10:
        # toda traza cuelga de un documento real) -- si la baja de la matriz
        # nunca se trazó a un documento (p.ej. se corrigió a mano en la cola
        # de revisión, sección 18), no hay nada real que copiar aquí. La
        # baja se hereda igual; solo la traza explícita se omite.
        if traza_matriz is not None:
            registrar_traza(
                db,
                entidad_tipo="lote",
                entidad_id=lote_pedido.id,
                campo="baja_declarada",
                documento_id=traza_matriz.documento_id,
                pagina=traza_matriz.pagina,
                fragmento=traza_matriz.fragmento,
                valor_extraido=str(baja_efectiva),
            )

    if lote_pedido.importe_licitacion is None:
        lote_pedido.importe_licitacion = lote_matriz.importe_licitacion
    if lote_pedido.importe_adjudicacion is None:
        lote_pedido.importe_adjudicacion = lote_matriz.importe_adjudicacion

    if not lineas_matriz:
        return ResultadoHerencia(motivo_revision=None)

    lineas_heredadas = [
        {
            "clave_linea": linea.clave_linea,
            "expediente_id": pedido.id,
            "orden_aparicion": linea.orden_aparicion,
            "codigo_precio": linea.codigo_precio,
            "matricula": linea.matricula,
            "descripcion": linea.descripcion,
            "codigo_material": linea.codigo_material,
            "unidad_medida": linea.unidad_medida,
            "unidad_medida_original": linea.unidad_medida_original,
            "cantidad": linea.cantidad,
            "precio_unitario": linea.precio_unitario,
            "baja_lote": baja_efectiva,
            # La baja EFECTIVA del pedido (la propia si la tenía, si no la
            # heredada) es la que manda sobre el precio adjudicado heredado,
            # no la que tuviera la matriz en su propia línea (requisito 4:
            # "lo propio del pedido manda").
            "precio_adjudicado": (
                linea.precio_unitario * (Decimal("1") - baja_efectiva)
                if linea.precio_unitario is not None and baja_efectiva is not None
                else None
            ),
            "documento_origen_id": linea.documento_origen_id,
            "pagina": linea.pagina,
            "fragmento": linea.fragmento,
            "heredado_de_matriz": True,
        }
        for linea in lineas_matriz
    ]
    guardado = guardar_lineas_catalogo(db, lote_pedido.id, lineas_heredadas)
    return ResultadoHerencia(
        motivo_revision=None, lineas_creadas=guardado.creadas, lineas_actualizadas=guardado.actualizadas,
        ids_tocadas=guardado.ids_tocadas,
    )


def reencolar_pedidos_esperando_matriz(db: Session, matriz: Expediente) -> int:
    """Al terminar el procesamiento de un expediente que resulta ser matriz
    de otros (con cualquier desenlace -completado, pendiente_revision o
    fallido-, el pedido decide después si eso le basta), se reencola la
    extracción de los pedidos que se habían quedado `esperando_matriz` de
    él. Mismo patrón de encadenado que
    `app.scraping.job.ejecutar_scraping_expediente` usa para pasar de
    descarga a extracción.

    Límite conocido, documentado en CONTEXTO.md: esto solo dispara cuando la
    MATRIZ termina un trabajo de extracción. Reprocesar una matriz ya
    resuelta a mano no reencola sola a los pedidos que ya heredaron de
    ella."""
    pedidos = db.execute(
        select(Expediente).where(
            Expediente.matriz_expediente_id == matriz.id,
            Expediente.estado == EstadoExpediente.esperando_matriz,
        )
    ).scalars().all()
    for pedido in pedidos:
        encolar_trabajo(db, tipo="extraer_expediente", expediente_id=pedido.id)
    return len(pedidos)
