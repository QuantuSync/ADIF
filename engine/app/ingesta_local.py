"""Bloque 6, sesión de comparación documento-vs-listado interno: segunda vía
de ingesta de documentos, además del scraping con navegador
(`app.scraping.job`, CONTEXTO.md sección 10: "el scraping es un tipo de
trabajo de la cola", no un script suelto -- esta ingesta es otro tipo más,
mismo sitio). El cliente va a aportar, con una macro propia, PDF de
expedientes vigentes en su SAP que no están publicados en la Plataforma --
este módulo los registra exactamente igual que si los hubiera descargado el
scraper: mismo hash (`Documento.hash`, deduplicación por contenido, nunca
por nombre de fichero ni de carpeta), misma tabla `DocumentoExpediente`, y la
misma cascada de extracción los clasifica por contenido después
(`app.extraccion.clasificador`) -- este módulo no decide la plantilla final,
solo registra.

Convención de carpeta (documentada también para el cliente en
`docs/ingesta-manual-convencion-carpetas.md`, porque su macro está en
construcción y estamos a tiempo de pedirle que la siga): **una subcarpeta
por expediente**, nombrada con el código de expediente saneado igual que ya
usa `app.scraping.job` al guardar en disco (`codigo_expediente.replace("/",
"_")`, p. ej. `6.24_28510.0088/`). Es la única señal que funciona igual para
todo tipo de documento -- un Anuncio PCSP declara su "Número de Expediente"
en el texto, pero un Anejo con el cuadro de precios (el documento que más
importa de estos 211) casi nunca declara ningún código legible; depender
solo de leer el PDF fallaría justo ahí. El nombre del fichero dentro de la
carpeta es libre (lo decide la macro del cliente) -- se conserva en
`DocumentoExpediente.nombre_archivo` para trazabilidad, nunca decide nada.

Comprobación cruzada, no ciega: cuando el propio documento SÍ declara su
código (`app.extraccion.campos_pcsp.extraer_campos_anuncio_pcsp` para la
familia PCSP, `app.extraccion.baja.extraer_codigo_propio_documento` para un
Contrato con "Contrato nº: X") se compara contra el de la carpeta. Si
coincide, más confianza; si no, no se adivina cuál es el correcto -- ese
documento no se enlaza y `Expediente.aviso_ingesta_manual` lo señala para
revisión manual (CONTEXTO.md sección 12: "lo que no cuadre no se corrige
solo").

Repetible sin duplicar nada: releer la misma carpeta sin cambios no crea
ningún `Documento` ni `DocumentoExpediente` nuevo (idempotencia por hash,
igual que el scraper) y no vuelve a encolar `extraer_expediente` si no hay
nada nuevo que extraer."""
from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.extraccion.baja import extraer_codigo_propio_documento
from app.extraccion.campos_pcsp import extraer_campos_anuncio_pcsp
from app.extraccion.clasificador import clasificar
from app.extraccion.cruce_codigos import normalizar_codigo_expediente
from app.extraccion.texto import PaginaTexto, extraer_texto
from app.interfaces.document_storage import DocumentStorage
from app.models import Documento, DocumentoExpediente, Expediente, OrigenDocumento, TipoDocumento
from app.queue import encolar_trabajo
from app.scraping.pcsp import safe

logger = logging.getLogger("ingesta_local")

# Trabajo de cola dedicado (mismo patrón que `sindicacion_backfill`,
# `auditoria_catalogo`...): un tipo de trabajo más, lanzable desde la web,
# nunca un script suelto (CONTEXTO.md sección 10).
TIPO_TRABAJO = "ingesta_local"

# Formato de carpeta: mismo código de expediente saneado que ya usa
# `app.scraping.job` al guardar (`codigo_expediente.replace("/", "_")`) --
# reconstruido con este regex porque el formato del código
# ("N.NN/DDDDD.NNNN") tiene siempre una única barra que reemplazar de vuelta.
_CARPETA_EXPEDIENTE_RE = re.compile(r"^(\d+\.\d+)_(\d+\.\d+)$")


def codigo_expediente_desde_carpeta(nombre_carpeta: str) -> Optional[str]:
    """`None` si el nombre de la carpeta no tiene la forma esperada -- nunca
    se adivina un código a partir de un nombre libre; esa carpeta se cuenta
    como "sin código reconocible" y se salta entera, para que la ingesta
    complete el resto de expedientes en vez de fallar de golpe."""
    m = _CARPETA_EXPEDIENTE_RE.match(nombre_carpeta.strip())
    if m is None:
        return None
    return f"{m.group(1)}/{m.group(2)}"


def _codigo_declarado_por_documento(paginas: list[PaginaTexto]) -> Optional[str]:
    """Código propio que el documento declara en su texto, si lo declara --
    ver docstring del módulo. `None` es la inmensa mayoría (anejos, cuadros
    de precios, pliegos): no es un fallo, es que el documento no lleva esa
    etiqueta, y entonces manda el código de la carpeta sin más."""
    campos = extraer_campos_anuncio_pcsp(paginas)
    if campos.numero_expediente is not None:
        return campos.numero_expediente.valor
    return extraer_codigo_propio_documento(paginas)


@dataclass
class ResumenIngestaLocal:
    configurado: bool
    carpetas_leidas: int = 0
    carpetas_sin_codigo_reconocible: int = 0
    expedientes_nuevos: int = 0
    expedientes_existentes: int = 0
    documentos_nuevos: int = 0
    documentos_ya_conocidos: int = 0
    enlaces_nuevos: int = 0
    documentos_codigo_declarado_distinto: int = 0
    expedientes_reencolados: int = 0

    def to_dict(self) -> dict:
        return {
            "configurado": self.configurado,
            "carpetas_leidas": self.carpetas_leidas,
            "carpetas_sin_codigo_reconocible": self.carpetas_sin_codigo_reconocible,
            "expedientes_nuevos": self.expedientes_nuevos,
            "expedientes_existentes": self.expedientes_existentes,
            "documentos_nuevos": self.documentos_nuevos,
            "documentos_ya_conocidos": self.documentos_ya_conocidos,
            "enlaces_nuevos": self.enlaces_nuevos,
            "documentos_codigo_declarado_distinto": self.documentos_codigo_declarado_distinto,
            "expedientes_reencolados": self.expedientes_reencolados,
        }


def _obtener_o_crear_expediente(db: Session, codigo: str) -> tuple[Expediente, bool]:
    expediente = db.execute(
        select(Expediente).where(Expediente.codigo_expediente == codigo)
    ).scalar_one_or_none()
    if expediente is not None:
        return expediente, False
    expediente = Expediente(codigo_expediente=codigo)
    db.add(expediente)
    db.commit()
    db.refresh(expediente)
    return expediente, True


def _ingerir_documento(
    db: Session, storage: DocumentStorage, fichero: Path, expediente: Expediente, codigo_carpeta: str
) -> tuple[bool, bool, Optional[str]]:
    """Un fichero de la carpeta -> (hay_enlace_nuevo, es_documento_nuevo,
    aviso_si_no_se_enlaza). El aviso, cuando existe, es la única señal de
    que este fichero concreto se dejó fuera -- nunca se enlaza a ciegas
    cuando el propio documento discrepa de su carpeta."""
    contenido = fichero.read_bytes()
    hash_doc = hashlib.sha256(contenido).hexdigest()

    existente = db.execute(select(Documento).where(Documento.hash == hash_doc)).scalar_one_or_none()
    if existente is None:
        # Solo se lee el PDF de verdad (coste real de `pdfplumber`) para
        # contenido genuinamente nuevo -- releer una carpeta sin cambios no
        # vuelve a pagar esto por cada fichero ya conocido.
        paginas = extraer_texto(fichero)
        codigo_declarado = _codigo_declarado_por_documento(paginas)
        if (
            codigo_declarado is not None
            and normalizar_codigo_expediente(codigo_declarado) != normalizar_codigo_expediente(codigo_carpeta)
        ):
            aviso = (
                f"el fichero {fichero.name!r} de la carpeta {codigo_carpeta} declara su propio código "
                f"como {codigo_declarado!r} -- no coincide, no se enlaza sin revisión"
            )
            logger.warning("ingesta_local: %s", aviso)
            return False, False, aviso

        clasificacion = clasificar(paginas) if paginas else None
        tipo = clasificacion.tipo if clasificacion is not None else TipoDocumento.otro
        carpeta_almacenamiento = safe(codigo_carpeta.replace("/", "_"))
        ruta = storage.guardar(f"{carpeta_almacenamiento}/MANUAL_{hash_doc}.pdf", contenido)
        existente = Documento(
            tipo_documento=tipo, hash=hash_doc, ruta_almacenamiento=ruta, origen=OrigenDocumento.manual,
        )
        db.add(existente)
        db.flush()
        documento_nuevo = True
    else:
        documento_nuevo = False

    enlace_existente = db.execute(
        select(DocumentoExpediente.id).where(
            DocumentoExpediente.documento_id == existente.id,
            DocumentoExpediente.expediente_id == expediente.id,
        )
    ).first()
    if enlace_existente is not None:
        return False, documento_nuevo, None
    db.add(DocumentoExpediente(
        documento_id=existente.id, expediente_id=expediente.id, nombre_archivo=fichero.name,
    ))
    return True, documento_nuevo, None


def ingerir_carpeta_local(db: Session, storage: DocumentStorage, ruta_raiz: Optional[str]) -> ResumenIngestaLocal:
    resumen = ResumenIngestaLocal(configurado=bool(ruta_raiz))
    if not ruta_raiz:
        return resumen
    raiz = Path(ruta_raiz)
    if not raiz.is_dir():
        return resumen

    for subcarpeta in sorted((p for p in raiz.iterdir() if p.is_dir()), key=lambda p: p.name):
        resumen.carpetas_leidas += 1
        codigo = codigo_expediente_desde_carpeta(subcarpeta.name)
        if codigo is None:
            resumen.carpetas_sin_codigo_reconocible += 1
            logger.warning(
                "ingesta_local: carpeta %r no tiene forma de código de expediente, se salta", subcarpeta.name
            )
            continue

        expediente, es_nuevo = _obtener_o_crear_expediente(db, codigo)
        if es_nuevo:
            resumen.expedientes_nuevos += 1
        else:
            resumen.expedientes_existentes += 1

        huella_cambiada = False
        avisos: list[str] = []
        for fichero in sorted((p for p in subcarpeta.iterdir() if p.is_file()), key=lambda p: p.name):
            if fichero.suffix.lower() != ".pdf":
                continue
            enlace_nuevo, documento_nuevo, aviso = _ingerir_documento(db, storage, fichero, expediente, codigo)
            if aviso is not None:
                avisos.append(aviso)
                resumen.documentos_codigo_declarado_distinto += 1
                continue
            if documento_nuevo:
                resumen.documentos_nuevos += 1
            else:
                resumen.documentos_ya_conocidos += 1
            if enlace_nuevo:
                resumen.enlaces_nuevos += 1
                huella_cambiada = True

        # Recalculado entero en cada ingesta de esta carpeta, nunca
        # acumulado sobre un aviso de una pasada anterior (mismo criterio
        # que `aviso_sindicacion`): si esta pasada no encuentra ningún
        # documento discrepante, el aviso se limpia -- no se queda pegado.
        expediente.aviso_ingesta_manual = "; ".join(avisos) if avisos else None
        db.commit()

        if huella_cambiada:
            encolar_trabajo(db, tipo="extraer_expediente", expediente_id=expediente.id)
            resumen.expedientes_reencolados += 1
            db.commit()

    return resumen
