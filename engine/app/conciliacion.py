"""Hoja "Conciliación" del Excel (sesión 2026-09-18, bloque 5, encargo del
cliente).

**La pregunta que contesta.** "¿Cómo sabemos que la app ha leído todo lo que
hay publicado?" Hasta hoy no había forma de comprobarlo: el entregable
enseñaba las líneas extraídas, y un expediente que no aportaba ninguna
simplemente no aparecía -- indistinguible de uno que el sistema nunca hubiera
visto. La respuesta es una lista: **una fila por cada expediente del
departamento que consta publicado en la Plataforma, aporte líneas o no**, con
qué se descargó de él, qué se leyó, cuánto aportó y, si no aportó nada, por
qué. Da igual el año, el estado y el tipo de procedimiento (mismo criterio
del cliente que ya rige el descubrimiento, `app.criterio_expediente`).

**De dónde sale la lista de lo publicado.** De las dos vías de
descubrimiento, que juntas son el registro completo de lo que la Plataforma
publica de este departamento: la sindicación mensual
(`app.sindicacion.descubrimiento`, el ZIP CODICE) y la búsqueda directa en el
buscador de la Plataforma (`app.scraping.descubrimiento_busqueda`). Un
expediente cuenta como publicado cuando alguna de las dos lo encontró, o
cuando se le descargó al menos un documento de la Plataforma -- que es la
evidencia más fuerte de las tres. Queda fuera lo que la Plataforma confirmó
que no tiene (`EstadoExpediente.sin_publicar`): ahí no hay nada que conciliar,
y meterlo en la lista daría a entender que el sistema se ha dejado algo.

**Qué NO es esta hoja.** No es una segunda fuente de verdad ni un recuento
paralelo: la columna de líneas la rellena `app.exportacion` con las filas que
de verdad escribió en la hoja "Materiales", no con una consulta propia que
pudiera dar otro número. Por eso `construir_conciliacion` recibe ese recuento
en vez de calcularlo -- si las dos cifras pudieran discrepar, la hoja dejaría
de servir para lo único que existe.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.criterio_expediente import departamentos_configurados, fragmento_en_codigo
from app.models import (
    CacheOcrDocumento,
    Documento,
    DocumentoExpediente,
    EstadoExpediente,
    EstadoTrabajo,
    Expediente,
    Lote,
    ModeloPrecio,
    OrigenDocumento,
    SindicacionExpediente,
    TrabajoCola,
    TrazaOrigen,
)

# Los seis valores de "Situación" que pidió el cliente, literales. El séptimo
# ("Otro") obliga a explicarse en la columna "Motivo" -- no es un cajón de
# sastre silencioso.
APORTA_LINEAS = "Aporta líneas"
SIN_CUADRO = "Publicado sin cuadro de precios"
PRECIOS_EN_ACUERDO_MARCO = "Los precios están en un acuerdo marco que no está publicado"
ESCANEADO_ILEGIBLE = "Documentos escaneados que no se han podido leer"
PENDIENTE_DE_PROCESAR = "Pendiente de procesar"
OTRO = "Otro"

SITUACIONES = (
    APORTA_LINEAS,
    SIN_CUADRO,
    PRECIOS_EN_ACUERDO_MARCO,
    ESCANEADO_ILEGIBLE,
    PENDIENTE_DE_PROCESAR,
    OTRO,
)

COLUMNAS_CONCILIACION = [
    "Código de expediente",
    "Título",
    "Órgano de contratación",
    "Estado que consta publicado en la Plataforma",
    # Bloque 3, sesión 2026-09-18 (continuación): columna aparte, nunca
    # mezclada con la anterior. La de la izquierda es lo que publica la
    # PLATAFORMA; esta es lo que dice el listado que ADIF nos envió el
    # 18/09/2026, sacado por ellos de SAP. Son dos hechos distintos (el
    # estado del anuncio frente al estado del contrato) y de dos fuentes
    # distintas: juntarlos en una sola columna haría imposible saber cuál
    # de las dos se está leyendo.
    "Estado según ADIF",
    "Documentos descargados",
    "Documentos leídos con reconocimiento óptico",
    "Líneas que aporta al catálogo",
    "Baja y de dónde sale",
    "Situación",
    "Motivo",
]

# `cbc-place-ext:ContractFolderStatusCode` del XML CODICE de la sindicación
# (`app.sindicacion.atom_parser`). Un código que no esté aquí se escribe tal
# cual, nunca se traduce a ciegas ni se deja en blanco.
_ESTADO_PLATAFORMA = {
    "PRE": "Anuncio previo",
    "PUB": "En plazo de presentación",
    "EV": "Pendiente de adjudicación",
    "ADJ": "Adjudicada",
    "RES": "Resuelta",
    "ANUL": "Anulada",
}

_SIN_ESTADO_ADIF = (
    "no consta (este expediente no figura en el listado de estados que ADIF envió el 18/09/2026)"
)

_SIN_ESTADO_PUBLICADO = (
    "no consta (este expediente se conoce por la búsqueda directa en la Plataforma, que devuelve el "
    "número pero no el estado; la sindicación mensual, que sí lo trae, no lo ha listado todavía)"
)


@dataclass(frozen=True)
class FilaConciliacion:
    codigo_expediente: str
    titulo: Optional[str]
    organo_contratacion: Optional[str]
    estado_plataforma: Optional[str]
    estado_adif: Optional[str]
    documentos_descargados: int
    documentos_reconocimiento_optico: int
    lineas_en_catalogo: int
    baja: str
    situacion: str
    motivo: str


@dataclass(frozen=True)
class RegistroPublicado:
    """De qué fecha es el registro de lo publicado y qué cubre -- lo que el
    cliente pidió dejar escrito en el propio Excel "para que nadie tenga que
    suponerlo"."""

    departamentos: list[str] = field(default_factory=list)
    periodos_sindicacion: list[str] = field(default_factory=list)
    sindicacion_actualizado_hasta: Optional[datetime] = None
    busqueda_ejecutada_en: Optional[datetime] = None
    busqueda_fragmentos: list[str] = field(default_factory=list)
    busqueda_codigos_encontrados: Optional[int] = None
    expedientes_publicados: int = 0
    expedientes_no_publicados: int = 0


def _periodo_legible(periodo: str) -> str:
    """"202609" -> "09/2026". El periodo es el nombre del ZIP mensual."""
    if len(periodo) == 6 and periodo.isdigit():
        return f"{periodo[4:]}/{periodo[:4]}"
    return periodo


def describir_registro_publicado(db: Session, filas: list[FilaConciliacion]) -> RegistroPublicado:
    periodos = sorted(
        {p for (p,) in db.execute(select(SindicacionExpediente.periodo_zip).distinct()).all() if p}
    )
    actualizado = db.execute(select(func.max(SindicacionExpediente.actualizado_en))).scalar()
    busqueda_en = None
    fragmentos: list[str] = []
    encontrados: Optional[int] = None
    # La búsqueda directa corre dentro del ciclo de mantenimiento y deja su
    # resumen en el resultado del trabajo (`descubrimiento_busqueda`): el
    # último ciclo que de verdad la ejecutó es la fecha del registro.
    for trabajo in db.execute(
        select(TrabajoCola)
        .where(TrabajoCola.tipo == "mantenimiento_ciclo", TrabajoCola.estado == EstadoTrabajo.completado)
        .order_by(TrabajoCola.created_at.desc())
        .limit(50)
    ).scalars():
        resumen = (trabajo.resultado or {}).get("descubrimiento_busqueda")
        if not resumen or resumen.get("error"):
            continue
        busqueda_en = trabajo.created_at
        fragmentos = list(resumen.get("fragmentos") or [])
        encontrados = resumen.get("codigos_encontrados")
        break

    # Acotado al mismo departamento que la hoja: el sistema conoce también
    # matrices de otros departamentos dadas por no publicadas, y contarlas
    # aquí daría una cifra que no cuadra con la lista que se está explicando.
    departamentos = sorted(departamentos_configurados())
    no_publicados = sum(
        1
        for (codigo,) in db.execute(
            select(Expediente.codigo_expediente).where(
                Expediente.estado == EstadoExpediente.sin_publicar
            )
        ).all()
        if any(fragmento_en_codigo(codigo, d) for d in departamentos)
    )
    return RegistroPublicado(
        departamentos=departamentos,
        periodos_sindicacion=periodos,
        sindicacion_actualizado_hasta=actualizado,
        busqueda_ejecutada_en=busqueda_en,
        busqueda_fragmentos=fragmentos,
        busqueda_codigos_encontrados=encontrados,
        expedientes_publicados=len(filas),
        expedientes_no_publicados=no_publicados,
    )


def _texto_baja(expediente: Expediente, lotes: list[Lote], traza: Optional[TrazaOrigen],
                nombre_documento: Optional[str]) -> str:
    """"Si tiene baja y de dónde sale", en una frase que se lea sin conocer el
    sistema."""
    if any(l.modelo_precio == ModeloPrecio.indexado_por_pedido for l in lotes):
        return (
            "No: es un acuerdo marco cuyos precios se revisan pedido a pedido con un coeficiente que "
            "ADIF pacta fuera de la Plataforma, así que no hay una baja única publicada"
        )
    bajas = {l.baja_lote for l in lotes if l.baja_lote is not None}
    if not bajas and expediente.baja_global is None:
        return "No: ningún documento de este expediente declara una baja"
    origen = f" (declarada en {nombre_documento})" if nombre_documento else ""
    if traza is not None and traza.fragmento:
        origen = f" (declarada en {nombre_documento or 'un documento del expediente'}: “{traza.fragmento.strip()}”)"
    if len(bajas) > 1:
        detalle = ", ".join(_porcentaje(b) for b in sorted(bajas))
        return f"Sí, distinta por lote: {detalle}{origen}"
    unica = next(iter(bajas)) if bajas else expediente.baja_global
    return f"Sí, {_porcentaje(unica)}{origen}"


def _porcentaje(valor: Optional[Decimal]) -> str:
    if valor is None:
        return "sin valor"
    return f"{valor * 100:.2f} %".replace(".", ",")


# El motivo exacto que deja `app.extraccion.orquestador` cuando el expediente
# SÍ traía documentos con posible cuadro de precios y no salió ninguna línea de
# ellos. Se compara por igualdad, no por subcadena: los motivos que empiezan
# igual pero siguen ("...: el expediente no trae ningún Anejo ni Pliego
# técnico...") dicen otra cosa y tienen su propia rama.
_MOTIVO_SIN_LINEAS_GENERICO = "no se extrajo ninguna línea de catálogo de los documentos descargados"


def _situacion(
    expediente: Expediente,
    lineas: int,
    documentos: int,
    documentos_ocr: int,
    matriz_publicada: Optional[bool],
) -> tuple[str, str]:
    """Devuelve `(situación, motivo)`. El orden de las ramas es el orden de
    las causas: la primera que se cumple es la que de verdad explica el caso.

    Los textos son para quien no sabe nada del sistema (mismo criterio y mismo
    test de jerga prohibida que `app.celdas_vacias`): nada de "huérfana",
    "cascada", "cola" ni nombres de campo."""
    motivo_tecnico = (expediente.error or "").strip()

    if lineas > 0:
        return APORTA_LINEAS, (
            f"Se han leído sus documentos y ha aportado {lineas} línea(s) de material al catálogo, "
            "con su precio unitario."
        )

    if documentos == 0:
        # Corrección de la sesión 2026-09-18 (continuación, bloque 4): "no
        # tiene ningún documento" tenía dos causas muy distintas metidas en la
        # misma frase. Si el expediente nunca se ha buscado, es trabajo
        # pendiente de verdad; si ya se buscó y la Plataforma lo encontró pero
        # su ficha no publica ningún documento descargable, no hay nada
        # pendiente que hacer y llamarlo "pendiente" promete un trabajo que no
        # existe (`6.14/28510.0148` y `0177`: cinco búsquedas, cero documentos).
        if expediente.descargado_en is None:
            return PENDIENTE_DE_PROCESAR, (
                "Consta publicado en la Plataforma, pero todavía no se ha descargado ningún documento "
                "suyo. Está en la lista de trabajo pendiente."
            )
        return SIN_CUADRO, (
            "Se ha buscado en la Plataforma y su ficha aparece, pero no publica ningún documento que "
            "se pueda descargar: ni anuncio, ni contrato, ni anejo de precios. No es que falte leerlo, "
            "es que no hay nada publicado que leer."
        )
    if expediente.extraido_en is None or expediente.estado in _ESTADOS_EN_CURSO:
        return PENDIENTE_DE_PROCESAR, (
            "Sus documentos están descargados, pero todavía no se han terminado de leer. Está en la "
            "lista de trabajo pendiente."
        )

    if matriz_publicada is False:
        return PRECIOS_EN_ACUERDO_MARCO, (
            f"Es un pedido que se hace contra el acuerdo marco {expediente.codigo_matriz}. Los precios "
            "no están en los documentos de este pedido, sino en los de ese acuerdo marco, y ese acuerdo "
            "marco no está publicado en la Plataforma: no hay de dónde leerlos. Para completarlo haría "
            "falta que ADIF facilitara el cuadro de precios del acuerdo marco."
        )

    # Corrección de la sesión 2026-09-18 (continuación, bloque 4): antes
    # bastaba con que UN documento cualquiera del expediente hubiera pasado por
    # reconocimiento óptico, o con que la palabra "escaneado" apareciera en
    # cualquier punto del motivo, para clasificarlo aquí -- y esta rama iba por
    # delante de todas las demás. Eso metía en el mismo cajón 16 expedientes
    # cuya causa real estaba escrita en su propio motivo y era otra (cobertura
    # parcial de lotes, baja en un documento compartido con un hermano,
    # documento equivocado del scraper, expediente sin ningún anejo). Ahora se
    # exige lo que de verdad significa la etiqueta: que hubiera documentos que
    # leer, que alguno de ELLOS hiciera falta leerlo por imagen, y que el
    # sistema no tenga ninguna otra explicación que dar.
    if documentos_ocr > 0 and motivo_tecnico == _MOTIVO_SIN_LINEAS_GENERICO:
        return ESCANEADO_ILEGIBLE, (
            f"Sus documentos son copias escaneadas (imágenes, sin texto). Se han pasado por "
            f"reconocimiento óptico {documentos_ocr} documento(s), pero no se ha podido recomponer de "
            "ellos ningún cuadro de precios fiable. Para completarlo haría falta el documento original "
            "en formato electrónico, o revisarlo a mano."
        )

    if motivo_tecnico.startswith("no se extrajo ninguna línea de catálogo"):
        return SIN_CUADRO, (
            "Se han descargado y leído sus documentos, y ninguno trae un cuadro de precios unitarios: "
            "la Plataforma publica de este expediente la adjudicación y el contrato, pero no el anejo "
            "de precios. No es un fallo de lectura, es lo que hay publicado."
        )

    return OTRO, (
        "Se han leído sus documentos y no ha aportado ninguna línea, por un motivo que no encaja en "
        "los anteriores. Lo que anotó el sistema al leerlo: "
        + (motivo_tecnico or "no se guardó ninguna explicación.")
    )


_ESTADOS_EN_CURSO = (
    EstadoExpediente.pendiente,
    EstadoExpediente.descargando,
    EstadoExpediente.descargado,
    EstadoExpediente.extrayendo,
    EstadoExpediente.esperando_matriz,
)


def construir_conciliacion(
    db: Session, lineas_por_expediente: dict[int, int]
) -> list[FilaConciliacion]:
    """Una fila por expediente publicado del departamento, más -- siempre --
    cualquier expediente que haya aportado filas a "Materiales" aunque no
    cumpla el criterio de departamento (requisito duro del cliente: "todo
    expediente que aparezca en la hoja Materiales tiene que aparecer en
    Conciliación").

    `lineas_por_expediente` son las filas realmente escritas en "Materiales",
    por `Expediente.id` -- ver el docstring del módulo."""
    departamentos = sorted(departamentos_configurados())
    expedientes = {e.id: e for e in db.execute(select(Expediente)).scalars()}

    documentos: dict[int, list[str]] = {}
    # Aparte: solo los descargados de la Plataforma. Un documento aportado a
    # mano (`app.ingesta_local`) no prueba que el expediente esté publicado
    # -- justamente existe para los que no lo están.
    con_documento_de_plataforma: set[int] = set()
    for expediente_id, hash_documento, origen in db.execute(
        select(DocumentoExpediente.expediente_id, Documento.hash, Documento.origen)
        .join(Documento, Documento.id == DocumentoExpediente.documento_id)
    ).all():
        documentos.setdefault(expediente_id, []).append(hash_documento)
        if origen == OrigenDocumento.plataforma:
            con_documento_de_plataforma.add(expediente_id)

    hashes_ocr = {h for (h,) in db.execute(select(CacheOcrDocumento.documento_hash)).all()}
    sindicacion = {
        s.codigo_expediente: s for s in db.execute(select(SindicacionExpediente)).scalars()
    }
    lotes_por_expediente: dict[int, list[Lote]] = {}
    for lote in db.execute(select(Lote)).scalars():
        lotes_por_expediente.setdefault(lote.expediente_id, []).append(lote)

    # Traza de la baja declarada, la más reciente de cada expediente, con el
    # nombre del fichero del que salió -- "de dónde sale" en la columna.
    traza_baja: dict[int, tuple[TrazaOrigen, Optional[str]]] = {}
    for traza, nombre in db.execute(
        select(TrazaOrigen, DocumentoExpediente.nombre_archivo)
        .outerjoin(
            DocumentoExpediente,
            (DocumentoExpediente.documento_id == TrazaOrigen.documento_id)
            & (DocumentoExpediente.expediente_id == TrazaOrigen.entidad_id),
        )
        .where(TrazaOrigen.entidad_tipo == "expediente", TrazaOrigen.campo == "baja_declarada")
        .order_by(TrazaOrigen.id)
    ).all():
        traza_baja[traza.entidad_id] = (traza, nombre)

    por_codigo = {e.codigo_expediente: e for e in expedientes.values()}

    def consta_publicado(expediente: Expediente) -> bool:
        if expediente.estado == EstadoExpediente.sin_publicar:
            return False
        if expediente.codigo_expediente in sindicacion:
            return True
        if expediente.id in con_documento_de_plataforma:
            return True
        return expediente.descargado_en is not None

    seleccionados = [
        e
        for e in expedientes.values()
        if (
            any(fragmento_en_codigo(e.codigo_expediente, d) for d in departamentos)
            and consta_publicado(e)
        )
        # Requisito duro: nada de lo que está en "Materiales" puede faltar
        # aquí, cumpla o no el criterio de departamento (p. ej. la matriz de
        # otro departamento cuyo cuadro de precios sí se leyó).
        or lineas_por_expediente.get(e.id, 0) > 0
    ]

    filas: list[FilaConciliacion] = []
    for expediente in sorted(seleccionados, key=lambda e: e.codigo_expediente):
        entrada = sindicacion.get(expediente.codigo_expediente)
        hashes = documentos.get(expediente.id, [])
        lineas = lineas_por_expediente.get(expediente.id, 0)
        matriz_publicada: Optional[bool] = None
        if expediente.codigo_matriz:
            matriz = por_codigo.get(expediente.codigo_matriz)
            matriz_publicada = matriz is not None and consta_publicado(matriz)
        situacion, motivo = _situacion(
            expediente,
            lineas=lineas,
            documentos=len(hashes),
            documentos_ocr=sum(1 for h in hashes if h in hashes_ocr),
            matriz_publicada=matriz_publicada,
        )
        traza, nombre_documento = traza_baja.get(expediente.id, (None, None))
        estado = None
        if entrada is not None and entrada.estado_pcsp:
            estado = _ESTADO_PLATAFORMA.get(entrada.estado_pcsp, entrada.estado_pcsp)
        filas.append(
            FilaConciliacion(
                codigo_expediente=expediente.codigo_expediente,
                titulo=expediente.nombre_proyecto or (entrada.titulo if entrada else None),
                organo_contratacion=entrada.organo_contratacion if entrada else None,
                estado_plataforma=estado or _SIN_ESTADO_PUBLICADO,
                # Dato de ADIF, no de la Plataforma (columna aparte, ver
                # `COLUMNAS_CONCILIACION`). Se escribe tal cual viene en su
                # listado: no se traduce ni se normaliza, es su vocabulario.
                estado_adif=expediente.estado_adif or _SIN_ESTADO_ADIF,
                documentos_descargados=len(hashes),
                documentos_reconocimiento_optico=sum(1 for h in hashes if h in hashes_ocr),
                lineas_en_catalogo=lineas,
                baja=_texto_baja(expediente, lotes_por_expediente.get(expediente.id, []), traza,
                                 nombre_documento),
                situacion=situacion,
                motivo=motivo,
            )
        )
    return filas


class DescuadreConciliacion(RuntimeError):
    """La suma de la columna de líneas de "Conciliación" no da el número de
    filas de "Materiales" (requisito duro del cliente: "si no cuadra, párate
    y dime la diferencia"). Nunca se exporta un Excel descuadrado: sería
    justo la clase de dato que esta hoja existe para descartar."""


def comprobar_cuadre(filas: list[FilaConciliacion], filas_materiales: int) -> None:
    suma = sum(f.lineas_en_catalogo for f in filas)
    if suma != filas_materiales:
        raise DescuadreConciliacion(
            f"la hoja \"Conciliación\" suma {suma} línea(s) y la hoja \"Materiales\" tiene "
            f"{filas_materiales} fila(s): diferencia de {suma - filas_materiales}"
        )
    sin_situacion = [f.codigo_expediente for f in filas if f.situacion not in SITUACIONES]
    if sin_situacion:
        raise DescuadreConciliacion(
            f"{len(sin_situacion)} expediente(s) sin Situación válida en \"Conciliación\": "
            + ", ".join(sin_situacion[:10])
        )
