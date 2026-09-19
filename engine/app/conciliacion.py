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
from app.extraccion.lote_declarado import extraer_expediente_principal_declarado
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
    TipoDocumento,
    TrabajoCola,
    TrazaOrigen,
)

# Los valores de "Situación", literales. Los seis originales son los que pidió
# el cliente; los dos añadidos en la quinta parte de la sesión 2026-09-18
# (bloques 3 y 4) parten en dos sendas situaciones que estaban mezclando dos
# hechos distintos, y llevan su porqué justo encima. "Otro" obliga a
# explicarse en la columna "Motivo" -- no es un cajón de sastre silencioso.
APORTA_LINEAS = "Aporta líneas"
SIN_CUADRO = "Publicado sin cuadro de precios"
PRECIOS_EN_ACUERDO_MARCO = "Los precios están en un acuerdo marco que no está publicado"
# Bloque 4, sesión 2026-09-18 (quinta parte). La anterior metía en el mismo
# saco dos cosas que el cliente distingue y va a preguntar: que el acuerdo
# marco no esté publicado (no hay de dónde leer un precio) y que sí lo esté
# pero publique el modelo de proposición económica EN BLANCO, con la columna
# de precio unitario vacía porque la rellena el licitador (`4.23/04110.0256`,
# acuerdo marco de EPIs 2024-2025, verificado documento a documento en la
# cuarta parte de esta misma sesión). En el segundo caso el documento existe y
# se ha leído entero: lo que no existe es el precio.
ACUERDO_MARCO_SIN_PRECIOS = "El acuerdo marco está publicado pero no publica precios unitarios"
ESCANEADO_ILEGIBLE = "Documentos escaneados que no se han podido leer"
# Bloque 3, sesión 2026-09-18 (quinta parte). Un expediente de lote puede no
# devolver nada al buscarlo por su propio número y tener, aun así, su
# adjudicación publicada dentro de la ficha del expediente principal de su
# licitación (`6.26/28510.0003`, lote 2 de `6.25/28510.0221`). Llamarlo "no
# publicado" a secas era falso: lo que no está publicado es su *ficha*, no sus
# documentos.
PUBLICADO_EN_FICHA_DE_OTRO = "Publicado dentro de la ficha de otro expediente"
PENDIENTE_DE_PROCESAR = "Pendiente de procesar"
# Bloque 5, sesión 2026-09-19 (tercera parte), encargo del cliente: partir
# "Otro" en las causas reales que el propio sistema ya escribía en su motivo,
# creando una situación nueva solo cuando hay al menos 3 expedientes del mismo
# tipo (condición del cliente). Desglosados los 26 de "Otro" uno a uno contra
# su motivo técnico y contra sus documentos, salen tres grupos que la cumplen
# y dos que no (2 y 1 expedientes, que se quedan en "Otro" con su motivo, que
# es exactamente para lo que "Otro" existe).
#
# Los tres son licitaciones por lotes o pedidos de acuerdo marco cuyos
# documentos SÍ se han leído enteros: lo que falta no es lectura, es que el
# documento que traería el precio de SU lote no está publicado bajo su número.
# Decirlo así, y no "un motivo que no encaja en los anteriores", es lo que
# permite al cliente preguntar a ADIF por el documento concreto que falta.
MATRIZ_TAMPOCO_PUBLICA = "El acuerdo marco del que depende tampoco publica precios"
BAJA_SOLO_EN_DOCUMENTO_DE_HERMANO = "Sus documentos son de expedientes hermanos y ninguno es el suyo"
COBERTURA_PARCIAL_DE_LOTES = "Licitación por lotes de la que solo se conocen algunos lotes"
OTRO = "Otro"

SITUACIONES = (
    APORTA_LINEAS,
    SIN_CUADRO,
    PRECIOS_EN_ACUERDO_MARCO,
    ACUERDO_MARCO_SIN_PRECIOS,
    ESCANEADO_ILEGIBLE,
    PUBLICADO_EN_FICHA_DE_OTRO,
    MATRIZ_TAMPOCO_PUBLICA,
    BAJA_SOLO_EN_DOCUMENTO_DE_HERMANO,
    COBERTURA_PARCIAL_DE_LOTES,
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
    # Bloque 3, sesión 2026-09-18 (quinta parte): de los que la Plataforma no
    # devuelve al buscarlos por su número, cuántos sí tienen sus documentos
    # publicados dentro de la ficha de otro expediente (y por eso SÍ salen en
    # la hoja). Se cuentan aparte para que la frase del registro no vuelva a
    # llamarlos "no publicados" sin más.
    expedientes_en_ficha_de_otro: int = 0


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
    # Bloque 3, sesión 2026-09-18 (quinta parte): los que ya salen en la hoja
    # porque sus documentos se publican en la ficha de otro expediente no se
    # cuentan aquí como "no publicados" -- estarían contados dos veces, y en
    # la segunda con la etiqueta equivocada.
    en_la_hoja = {fila.codigo_expediente for fila in filas}
    no_publicados = [
        codigo
        for (codigo,) in db.execute(
            select(Expediente.codigo_expediente).where(
                Expediente.estado == EstadoExpediente.sin_publicar
            )
        ).all()
        if any(fragmento_en_codigo(codigo, d) for d in departamentos)
    ]
    en_ficha_de_otro = sum(1 for codigo in no_publicados if codigo in en_la_hoja)
    return RegistroPublicado(
        departamentos=departamentos,
        periodos_sindicacion=periodos,
        sindicacion_actualizado_hasta=actualizado,
        busqueda_ejecutada_en=busqueda_en,
        busqueda_fragmentos=fragmentos,
        busqueda_codigos_encontrados=encontrados,
        expedientes_publicados=len(filas),
        expedientes_no_publicados=len(no_publicados) - en_ficha_de_otro,
        expedientes_en_ficha_de_otro=en_ficha_de_otro,
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
# Bloque 5, sesión 2026-09-19 (tercera parte): los tres motivos técnicos que
# el propio sistema ya escribía y que hasta hoy caían todos en "Otro". Se
# comparan por subcadena porque cada uno lleva detrás sus cifras concretas
# (cuántos lotes, cuántas bajas, qué códigos), que son justo lo que el
# expediente aporta de particular y lo que sigue saliendo en la columna
# "Motivo" para los que se queden en "Otro".
_MOTIVO_MATRIZ_SIN_CUADRO = "tampoco tiene cuadro de precios ni baja"
_MOTIVO_BAJA_DE_HERMANO = "en documento(s) compartido(s) con expediente(s) hermano(s)"
_MOTIVO_COBERTURA_PARCIAL = "cobertura parcial:"


@dataclass(frozen=True)
class LoteDeOtroExpediente:
    """Bloque 3, sesión 2026-09-18 (quinta parte): este expediente es el lote
    `identificador` de la licitación `principal`, y quien lo declara así es un
    documento publicado de `principal` (su Resolución de Adjudicación o su
    Contrato), no una suposición nuestra.

    Es el mismo dato que `Lote.codigo_expediente_lote` ya guardaba desde la
    generalización de `docs/identidad-expediente.md` sección 27 -- aquí solo se
    le da la vuelta al índice (del principal a su lote, en vez de al revés)
    para poder contestar "¿de quién cuelga este número?"."""

    principal: str
    identificador: str


def _lotes_en_ficha_de_otro(db: Session, por_codigo: dict[str, Expediente]) -> dict[str, LoteDeOtroExpediente]:
    """Código de expediente -> de quién cuelga, para los expedientes cuyo
    número aparece como el de un lote de OTRA licitación.

    Certeza estructural, no coincidencia de texto: la relación sale de un
    documento de adjudicación o de un contrato que liga, por número, un lote a
    su expediente (`app.extraccion.lotes`), nunca de encontrar el número
    suelto en el texto de cualquier documento. Se descarta el caso degenerado
    de un expediente que se declara lote de sí mismo."""
    enlaces: dict[str, LoteDeOtroExpediente] = {}

    def anotar(codigo_lote: Optional[str], identificador: Optional[str], codigo_principal: str) -> None:
        codigo_lote = (codigo_lote or "").strip()
        if not codigo_lote or not identificador or codigo_lote == codigo_principal:
            return
        if codigo_lote not in por_codigo:
            return
        enlaces.setdefault(codigo_lote, LoteDeOtroExpediente(codigo_principal, identificador))

    for lote, codigo_principal in db.execute(
        select(Lote, Expediente.codigo_expediente).join(
            Expediente, Expediente.id == Lote.expediente_id
        )
    ).all():
        anotar(lote.codigo_expediente_lote, lote.identificador_lote, codigo_principal)

    # Segunda fuente, bloque 3 de la sexta parte de esta sesión (migración
    # 0038): la identidad que el propio Contrato firmado declara en su
    # cabecera ("Contrato nº: 6.19/28510.0213 ... LOTE 1"). Es la MISMA
    # evidencia -- un documento publicado del principal que liga por número un
    # lote a su expediente --, solo que hasta ahora se perdía cuando el
    # expediente no traía además una Resolución/Propuesta que declarase lotes:
    # `app.extraccion.orquestador._extraer_lotes` no abre candidatos con un
    # Contrato, así que no llegaba a crearse ningún `Lote` donde guardarla.
    # Sin esto, `4.23/28510.0081`, `6.19/28510.0213` y `6.19/28510.0216`
    # salían del entregable como "no publicados", que es falso: su Contrato
    # firmado está publicado en la ficha del principal y dice qué lote son.
    # Va DESPUÉS del bucle de arriba y con `setdefault`: donde ya hay un lote
    # registrado manda el lote, que es el camino verificado desde antes.
    for codigo_lote, identificador, codigo_principal in db.execute(
        select(
            Documento.identidad_lote_codigo,
            Documento.identidad_lote_identificador,
            Expediente.codigo_expediente,
        )
        .join(DocumentoExpediente, DocumentoExpediente.documento_id == Documento.id)
        .join(Expediente, Expediente.id == DocumentoExpediente.expediente_id)
        .where(Documento.identidad_lote_codigo.is_not(None))
    ).all():
        anotar(codigo_lote, identificador, codigo_principal)
    return enlaces


def _situacion(
    expediente: Expediente,
    lineas: int,
    documentos: int,
    documentos_ocr: int,
    matriz_publicada: Optional[bool],
    principal_publicado: Optional[str] = None,
    en_ficha_de_otro: Optional[LoteDeOtroExpediente] = None,
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

    if en_ficha_de_otro is not None and documentos == 0:
        # Bloque 3, sesión 2026-09-18 (quinta parte). Va por delante de la
        # rama de "no se ha descargado nada suyo" porque la explica: no hay
        # nada que descargar bajo ESTE número, y no por estar pendiente.
        return PUBLICADO_EN_FICHA_DE_OTRO, (
            f"Este expediente es el lote {en_ficha_de_otro.identificador} de la licitación "
            f"{en_ficha_de_otro.principal}, y así lo declara por su número un documento publicado de "
            f"{en_ficha_de_otro.principal}. Sus documentos (adjudicación, contrato, cuadro de precios) se "
            f"publican dentro de la ficha de {en_ficha_de_otro.principal}, no bajo su propio número: "
            "buscarlo en la Plataforma por este número no devuelve nada, y eso no significa que no esté "
            f"publicado. Lo que aporte al catálogo se cuenta en la fila de {en_ficha_de_otro.principal}."
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

    if matriz_publicada is False and principal_publicado:
        # Bloque 4, sesión 2026-09-18 (quinta parte). El acuerdo marco que
        # figura en el campo fijo del anuncio (`codigo_matriz`) no está
        # publicado, pero el propio anuncio declara además el **expediente
        # principal** de la licitación por lotes de la que cuelga, y ESE sí lo
        # está. No es el mismo caso: hay documentos publicados y leídos, lo
        # que no hay en ellos es un precio unitario.
        return ACUERDO_MARCO_SIN_PRECIOS, (
            f"Es un pedido que se hace contra el acuerdo marco {expediente.codigo_matriz}. El anuncio de "
            f"este pedido declara además el expediente principal de ese acuerdo marco, "
            f"{principal_publicado}, que sí está publicado y cuyos documentos se han descargado y leído "
            "enteros. Lo que publica no es un cuadro de precios: es el modelo de proposición económica en "
            "blanco, con las unidades puestas y la columna de precio unitario vacía, que es la que rellena "
            "cada licitador al presentar su oferta. No hay ningún precio unitario publicado que leer. Para "
            "completarlo haría falta que ADIF facilitara los precios adjudicados de ese acuerdo marco."
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

    # Bloque 5, sesión 2026-09-19 (tercera parte). El orden importa y es el
    # orden de las causas, igual que el resto de esta función:
    #
    # 1. La matriz va primero porque su texto CONTIENE el de la siguiente: el
    #    motivo de un pedido cuya matriz no tiene cuadro arrastra literalmente
    #    el motivo de la matriz ("la matriz X tampoco tiene cuadro de precios
    #    ni baja: 2 baja(s) declarada(s) en documento(s) compartido(s)...").
    #    Al revés, el pedido se clasificaría por la causa de su matriz.
    # 2. "Documentos de hermanos" antes que "cobertura parcial" porque es más
    #    específica: dice de quién son los documentos, no solo que faltan
    #    lotes.
    if _MOTIVO_MATRIZ_SIN_CUADRO in motivo_tecnico:
        return MATRIZ_TAMPOCO_PUBLICA, (
            f"Es un pedido que se hace contra el acuerdo marco {expediente.codigo_matriz or 'del que depende'}, "
            "y ese acuerdo marco sí está publicado y sus documentos se han descargado y leído enteros. "
            "El problema es que tampoco ellos traen un cuadro de precios unitarios ni una baja: el "
            "precio de este pedido no está publicado ni aquí ni allí. Para completarlo haría falta que "
            "ADIF facilitara el cuadro de precios del acuerdo marco."
        )

    if _MOTIVO_BAJA_DE_HERMANO in motivo_tecnico:
        return BAJA_SOLO_EN_DOCUMENTO_DE_HERMANO, (
            "Es uno de los lotes de una licitación, y los documentos que la Plataforma publica bajo su "
            "número son en realidad los de sus lotes hermanos: cada uno declara su propio número de "
            "contrato y ninguno es el de este expediente. Se han leído enteros, y por eso no se les "
            "toma ni la baja ni el cuadro de precios -- serían los de otro lote. Para completarlo haría "
            "falta el contrato o el anejo de precios de ESTE lote."
        )

    if _MOTIVO_COBERTURA_PARCIAL in motivo_tecnico:
        return COBERTURA_PARCIAL_DE_LOTES, (
            "Es una licitación repartida en varios lotes, y de los documentos publicados solo se puede "
            "leer la baja o el importe de algunos de ellos -- no del que corresponde a este expediente. "
            "Se han descargado y leído todos sus documentos: lo que no está publicado bajo este número "
            "es el cuadro de precios de su lote. Para completarlo haría falta el anejo de precios o el "
            "contrato de ese lote concreto."
        )

    return OTRO, (
        "Se han leído sus documentos y no ha aportado ninguna línea, por un motivo que no encaja en "
        "los anteriores. Lo que anotó el sistema al leerlo: "
        + (motivo_tecnico or "no se guardó ninguna explicación.")
    )


# ---------------------------------------------------------------------------
# Bloque 6, sesión 2026-09-18 (quinta parte): el documento manda sobre el
# boletín cuando va por delante
# ---------------------------------------------------------------------------
# El caso que lo motiva es `6.25/28510.0221` (tercera parte de esta sesión):
# su Resolución de Adjudicación está descargada de la Plataforma y leída, pero
# la columna decía "Pendiente de adjudicación" porque el último boletín de
# sindicación que lo lista es el de 07/2026 y ahí todavía lo estaba. Un boletín
# refleja un evento de ese mes, no "sigue vigente" (CONTEXTO.md sección 16), así
# que quedarse con él es quedarse con el dato más viejo de los dos.
#
# **Por qué esto no viola CONTEXTO.md sección 12** ("un contraste externo no
# tiene autoridad para cambiar el estado de un expediente"). Esa regla protege
# al documento del contraste, no al revés: aquí manda el documento firmado, que
# es justo lo que esa sección dice que manda. Y no se cambia ningún estado del
# sistema -- `Expediente.estado` no se toca --, solo lo que esta columna
# informa.
#
# **Nunca baja de estado.** Solo se sustituye cuando el documento prueba una
# etapa POSTERIOR a la que dice el boletín; si el boletín va por delante o
# empatan, manda el boletín. Y "Anulada" no está en la escalera: una anulación
# no la deshace un documento anterior a ella.
_ESCALERA_ESTADO = {"PRE": 0, "PUB": 1, "EV": 2, "ADJ": 3, "RES": 4}

# Qué prueba cada tipo de documento publicado en la Plataforma, y nada más.
# El techo es "Resuelta": sin acceso a SAP, los estados posteriores del
# contrato los tiene que indicar ADIF a mano (decisión de Isabel Ibáñez,
# 18/09/2026, `docs/decisiones-cliente.md`).
_ESTADO_QUE_PRUEBA_EL_DOCUMENTO = {
    TipoDocumento.resolucion_adjudicacion: "ADJ",
    TipoDocumento.propuesta_lc27: "ADJ",
    TipoDocumento.propuesta_dt: "ADJ",
    TipoDocumento.contrato: "RES",
}

_ORIGEN_DEL_DOCUMENTO = {
    "ADJ": "su Resolución o Propuesta de Adjudicación",
    "RES": "su Contrato o su Anuncio de formalización",
}


def _estado_publicado(
    codigo_sindicacion: Optional[str], codigo_por_documento: Optional[str], periodo: Optional[str]
) -> str:
    """El texto de la columna "Estado que consta publicado en la Plataforma"."""
    # Un código que no está en la escalera ("ANUL", o uno que la Plataforma
    # añada mañana y todavía no conozcamos) **no se compara**: manda el
    # boletín. Sin esta condición, `.get(..., -1)` haría que cualquier
    # documento pasara por delante de una anulación, que es justo lo contrario
    # de lo que hay que hacer.
    if codigo_por_documento is not None and (
        codigo_sindicacion is None
        or (
            codigo_sindicacion in _ESCALERA_ESTADO
            and _ESCALERA_ESTADO[codigo_por_documento] > _ESCALERA_ESTADO[codigo_sindicacion]
        )
    ):
        texto = _ESTADO_PLATAFORMA[codigo_por_documento]
        origen = _ORIGEN_DEL_DOCUMENTO[codigo_por_documento]
        if codigo_sindicacion is None:
            return (
                f"{texto} (lo prueba {origen}, que el sistema ha descargado de la Plataforma; la "
                "sindicación mensual no ha listado todavía este expediente)"
            )
        anterior = _ESTADO_PLATAFORMA.get(codigo_sindicacion, codigo_sindicacion)
        cuando = f" de {_periodo_legible(periodo)}" if periodo else ""
        return (
            f"{texto} (lo prueba {origen}, que el sistema ha descargado de la Plataforma; el último "
            f"boletín de sindicación"
            f"{cuando} todavía decía “{anterior}”, y un boletín refleja el mes en que se publicó, "
            "no lo que sigue vigente)"
        )
    if codigo_sindicacion is not None:
        return _ESTADO_PLATAFORMA.get(codigo_sindicacion, codigo_sindicacion)
    return _SIN_ESTADO_PUBLICADO


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
    # Bloque 6: qué etapa prueba el documento más avanzado que la Plataforma
    # publica de cada expediente (ver `_estado_publicado`). Solo cuentan los
    # descargados de la Plataforma: un documento aportado a mano no prueba
    # nada sobre lo que la Plataforma publica.
    estado_por_documento: dict[int, str] = {}
    for expediente_id, hash_documento, origen, tipo in db.execute(
        select(
            DocumentoExpediente.expediente_id,
            Documento.hash,
            Documento.origen,
            Documento.tipo_documento,
        ).join(Documento, Documento.id == DocumentoExpediente.documento_id)
    ).all():
        documentos.setdefault(expediente_id, []).append(hash_documento)
        if origen == OrigenDocumento.plataforma:
            con_documento_de_plataforma.add(expediente_id)
            prueba = _ESTADO_QUE_PRUEBA_EL_DOCUMENTO.get(tipo)
            if prueba is not None:
                anterior = estado_por_documento.get(expediente_id)
                if anterior is None or _ESCALERA_ESTADO[prueba] > _ESCALERA_ESTADO[anterior]:
                    estado_por_documento[expediente_id] = prueba

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

    # Bloque 3: los que no devuelven nada al buscarlos por su número pero
    # tienen sus documentos publicados dentro de la ficha de otro expediente.
    # Entran en la hoja: sí están publicados, solo que no bajo su número.
    en_ficha_de_otro = {
        codigo: enlace
        for codigo, enlace in _lotes_en_ficha_de_otro(db, por_codigo).items()
        if not consta_publicado(por_codigo[codigo])
        and (principal := por_codigo.get(enlace.principal)) is not None
        and consta_publicado(principal)
    }

    seleccionados = [
        e
        for e in expedientes.values()
        if (
            any(fragmento_en_codigo(e.codigo_expediente, d) for d in departamentos)
            and (consta_publicado(e) or e.codigo_expediente in en_ficha_de_otro)
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
        # Bloque 4: el expediente principal del acuerdo marco que el propio
        # anuncio del pedido declara en su título, cuando ESE sí está
        # publicado. Nunca se escribe en `codigo_matriz` (CONTEXTO.md sección
        # 7: el sistema no inventa matrices); aquí solo se usa para saber cuál
        # de las dos situaciones de acuerdo marco es la de verdad.
        principal_publicado: Optional[str] = None
        if matriz_publicada is False:
            declarado = extraer_expediente_principal_declarado(expediente.nombre_proyecto)
            if declarado and declarado != expediente.codigo_matriz:
                principal = por_codigo.get(declarado)
                if principal is not None and consta_publicado(principal):
                    principal_publicado = declarado
        situacion, motivo = _situacion(
            expediente,
            lineas=lineas,
            documentos=len(hashes),
            documentos_ocr=sum(1 for h in hashes if h in hashes_ocr),
            matriz_publicada=matriz_publicada,
            principal_publicado=principal_publicado,
            en_ficha_de_otro=en_ficha_de_otro.get(expediente.codigo_expediente),
        )
        traza, nombre_documento = traza_baja.get(expediente.id, (None, None))
        # Bloque 6: el documento publicado manda sobre el boletín de
        # sindicación cuando prueba una etapa posterior. Ver `_estado_publicado`.
        estado = _estado_publicado(
            entrada.estado_pcsp if entrada is not None else None,
            estado_por_documento.get(expediente.id),
            entrada.periodo_zip if entrada is not None else None,
        )
        filas.append(
            FilaConciliacion(
                codigo_expediente=expediente.codigo_expediente,
                titulo=expediente.nombre_proyecto or (entrada.titulo if entrada else None),
                organo_contratacion=entrada.organo_contratacion if entrada else None,
                estado_plataforma=estado,
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
