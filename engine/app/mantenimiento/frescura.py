"""Bloque 1, ejecución incremental (CONTEXTO.md sección 23).

Decide si un expediente necesita una nueva descarga o una nueva extracción
sin abrir ningún documento y sin tocar la cascada de extracción
(`app.extraccion.*`) ni el scraping (`app.scraping.*`) — ninguno de los dos
se modifica en esta sesión. Quien SÍ escribe las columnas de frescura
(`Expediente.descargado_en/extraido_en/version_logica_extraccion/
huella_documentos`) es `app.worker` (los manejadores de trabajo), usando los
helpers `estampar_*` de este módulo, justo después de llamar —sin tocarlas—
a `app.scraping.job.ejecutar_scraping_expediente` y a
`app.extraccion.orquestador.ejecutar_extraccion_expediente`.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Iterable, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Documento, EstadoExpediente, Expediente, LineaCatalogo

# Sube este valor cuando un cambio en `app.extraccion.*` deba forzar el
# reproceso de todos los expedientes aunque sus documentos no hayan cambiado
# — p.ej. un alias determinista nuevo, un umbral distinto, una regla de
# clasificación nueva (docs/analisis-corpus.md documenta varios cambios de
# este tipo a lo largo del proyecto). Comparado contra
# `Expediente.version_logica_extraccion`; cualquier cadena sirve, no hace
# falta que sea un número — una fecha de sesión es una convención razonable.
# Bloque 5, sesión de comparación documento-vs-listado interno: sube por dos
# cambios reales en la cascada desde la última vez (2026-09-08.1) -- ninguno
# de los dos toca ningún documento (misma huella), así que sin este bump
# `debe_extraer` nunca los recogería solo: (1) `guardar_lineas_catalogo`
# (bloque 2) ya no deja `motivo_revision` pegado entre pasadas -- líneas con
# un motivo obsoleto de una sesión anterior necesitan una pasada nueva para
# limpiarse; (2) `_priorizar_por_origen`/`_detectar_conflicto_origen`
# (bloque 6) son nuevos en el orquestador, aunque hoy no cambien nada (0
# documentos aportados a mano todavía).
# Sesión 2026-09-14: páginas de continuación que el localizador no abría,
# cabeceras ilegibles (fuente sin mapa Unicode), códigos con sufijo de
# variante, herencia de mapeo por geometría de columnas y código de material
# de la columna REPUESTO -- todo sin tocar ningún documento.
VERSION_LOGICA_EXTRACCION = "2026-09-14.1"


def huella_documentos(documentos: Iterable[Documento]) -> str:
    """Hash estable del conjunto de documentos de un expediente, por
    contenido (`Documento.hash`, sección 17 de CONTEXTO.md: la ruta de
    almacenamiento ya va por hash), no por índice ni por fecha: cambia si se
    añade, se quita o se sustituye un documento, sin releer ningún PDF."""
    hashes = sorted(d.hash for d in documentos)
    return hashlib.sha256(",".join(hashes).encode("utf-8")).hexdigest()


def debe_descargar(expediente: Expediente, documentos: list[Documento]) -> bool:
    """CONTEXTO.md, bloque 1, punto 2: "si los tiene [documentos] y no hay
    indicios de novedad, no se descarga". Sin ninguna fuente de novedad
    propia todavía (llega en el bloque 2 con la sindicación), la única señal
    disponible hoy es si el expediente ya tiene algún documento: si no tiene
    ninguno, nunca se descargó con éxito (o el intento anterior falló sin
    dejar nada), y merece un intento nuevo. Un expediente con documentos
    nunca se redescarga solo, aunque esté `fallido` o `pendiente_revision`
    por otra causa — evitar cada descarga evitable es el punto (CONTEXTO.md,
    bloque 1: "la Plataforma es lenta y frágil").

    Deliberadamente sin `forzar`: el punto 4 del bloque 1 lo pide "para
    desarrollo", y en desarrollo lo que hace falta casi siempre es forzar la
    RE-EXTRACCIÓN tras un cambio en `app.extraccion.*`, no volver a golpear
    la Plataforma real para un expediente que ya tiene sus documentos
    íntegros en disco — forzar eso también contradiría el principio de este
    mismo punto ("cada descarga evitada cuenta"). `debe_extraer` sí acepta
    `forzar`; forzar una redescarga de un expediente con documentos queda
    fuera de esta sesión (se puede seguir haciendo a mano, con el endpoint
    ya existente `POST /expedientes/{id}/descargar`)."""
    return not documentos


def debe_extraer(
    expediente: Expediente,
    documentos: list[Documento],
    forzar: bool,
    ciclo_creado_en: Optional[datetime] = None,
) -> bool:
    """CONTEXTO.md, bloque 1, punto 3: "si los documentos no han cambiado
    (mismo hash) y la lógica tampoco, no se reextrae". Deliberadamente NO
    mira si el expediente tiene documentos: un pedido derivado de acuerdo
    marco sin ningún documento propio (docs/analisis-corpus.md hallazgo 3)
    también necesita que se intente su extracción, aunque no vaya a producir
    ninguna línea — es el único camino que le queda para cruzar con el Excel
    de códigos y, a través de `codigo_matriz`, heredar de su matriz.

    `extraido_en is None` cubre tanto "nunca se ha extraído" como
    "se quedó `esperando_matriz`" — `app.worker` solo estampa `extraido_en`
    en un intento que de verdad corrió la cascada (ver su docstring), nunca
    en ese estado, así que un pedido derivado se reintenta en cada ciclo
    hasta que su matriz esté lista, sin necesitar una regla aparte aquí.

    `ciclo_creado_en` (resumibilidad del ciclo de mantenimiento, sesión
    2026-09-11, CONTEXTO.md "pendiente de resolver"): `TrabajoCola.created_at`
    del propio `mantenimiento_ciclo` que está evaluando este expediente, fijo
    entre reintentos de un mismo trabajo huérfano-y-recuperado. Si
    `expediente.extraido_en` ya es posterior, un intento ANTERIOR de este
    mismo ciclo ya extrajo este expediente con éxito -- se salta incluso con
    `forzar=True`, para que un reinicio del worker a mitad de un ciclo largo
    reanude por donde iba en vez de reprocesar los cientos de expedientes que
    el intento interrumpido ya había resuelto. `forzar` pasa a significar
    "ignora lo obsoleto de antes de pedir este ciclo", no "repite ciegamente
    en cada reintento de este mismo ciclo". Esta comprobación va antes que
    `forzar` a propósito: sin `ciclo_creado_en` (llamador que no participa de
    un ciclo, p.ej. un test o un reproceso manual futuro) se comporta como
    antes."""
    if (
        ciclo_creado_en is not None
        and expediente.extraido_en is not None
        and expediente.extraido_en > ciclo_creado_en
    ):
        return False
    if forzar:
        return True
    if expediente.extraido_en is None:
        return True
    if expediente.version_logica_extraccion != VERSION_LOGICA_EXTRACCION:
        return True
    if expediente.huella_documentos != huella_documentos(documentos):
        return True
    return False


def debe_estampar_extraccion(expediente: Expediente) -> bool:
    """Solo se estampa frescura de extracción cuando de verdad corrió un
    intento completo de la cascada: no en `esperando_matriz` (ahí no hay
    nada que registrar todavía, ver docstring de `debe_extraer`) ni en
    `sin_publicar` (`ejecutar_extraccion_expediente` corta en seco sin tocar
    nada, CONTEXTO.md sección 22)."""
    return expediente.estado not in (EstadoExpediente.esperando_matriz, EstadoExpediente.sin_publicar)


def estampar_descarga_exitosa(db: Session, expediente: Expediente) -> None:
    expediente.descargado_en = datetime.now(timezone.utc)
    db.commit()


def estampar_extraccion(db: Session, expediente: Expediente, documentos: list[Documento]) -> None:
    """Llamar solo cuando `debe_estampar_extraccion(expediente)` ya es
    `True` — ver docstring de esa función."""
    expediente.extraido_en = datetime.now(timezone.utc)
    expediente.version_logica_extraccion = VERSION_LOGICA_EXTRACCION
    expediente.huella_documentos = huella_documentos(documentos)
    db.commit()


# Comprobación permanente de integridad del catálogo (auditoría 2026-09-05,
# docs/correccion-defectos-auditoria.md): CONTEXTO.md sección 9.9 exige que
# reprocesar un expediente actualice sus filas, nunca las duplique. El bug
# real que motiva esto (clave de huérfana "canonicalizada" de vuelta al
# `codigo_precio` desnudo en cada actualización, arreglado en
# `app.catalogo.guardar_lineas_catalogo`) duplicaba sin límite en cada ciclo
# de mantenimiento sin que nada lo señalara -- se descubrió por auditoría
# manual, no porque el sistema lo detectara solo. Estas dos funciones,
# usadas juntas por `app.worker.procesar_extraer_expediente`, cierran ese
# hueco: si los documentos del expediente no cambiaron (misma huella) desde
# la última extracción con éxito, el número de líneas de catálogo tampoco
# debería crecer.


def documentos_sin_cambios(expediente: Expediente, documentos: Iterable[Documento]) -> bool:
    """`False` si nunca hubo una extracción con éxito de la que partir
    (`huella_documentos` todavía `None`) -- ahí no hay nada contra qué
    comparar, y cualquier línea que se cree es la primera vez, no una
    duplicación."""
    if expediente.huella_documentos is None:
        return False
    return expediente.huella_documentos == huella_documentos(documentos)


def contar_lineas_catalogo(db: Session, expediente_id: int) -> int:
    return db.query(func.count(LineaCatalogo.id)).filter(LineaCatalogo.expediente_id == expediente_id).scalar() or 0


def detectar_crecimiento_sin_cambios(conteo_antes: int, conteo_despues: int) -> Optional[str]:
    """`None` cuando no hay nada que avisar. Un motivo explícito, listo para
    `Expediente.error`, cuando el recuento creció -- nunca se corrige solo
    (CONTEXTO.md sección 12: "lo que no cuadra va a la cola de revisión"), la
    idea es que un humano lo vea y decida, no que el sistema intente
    deducir cuáles de las líneas nuevas son el duplicado real."""
    if conteo_despues > conteo_antes:
        return (
            f"integridad del catálogo: {conteo_antes} -> {conteo_despues} líneas en este expediente sin que "
            "cambiaran sus documentos (misma huella) -- posible duplicación en la extracción, revisar antes "
            "de confiar en el recuento"
        )
    return None
