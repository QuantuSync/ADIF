"""Scraper de la Plataforma de Contratación del Sector Público (PCSP).

Rescatado de Ejemplo/heredado/scraping_ADIF/src/pcsp_scraper/scraper.py. Se
conserva la navegación (búsqueda por MATRIZ con caída a Nº Expediente, espera
de la tabla de resultados, apertura de la ficha, listado y descarga de
documentos, deduplicación por hash, selección del documento idóneo de cada
tipo). Se descarta el envoltorio: Excel/JSON de estado, CSV de log, Microsoft
Edge y el modo con ventana — este módulo corre siempre headless con el
Chromium que trae Playwright, dentro del contenedor del worker.

Hallazgo de esta sesión (verificado en vivo, headless, contra la Plataforma
real): las descargas por `context.request.get()` que usaba el scraper
original son rechazadas por el WAF de la Plataforma con "Request Rejected",
aunque se copien todas las cabeceras de un navegador real. La navegación real
del motor de render (`page.goto` + evento `download`) sí pasa. Por eso
`descargar_documento()` abre una pestaña y navega de verdad, en vez de hacer
la petición HTTP a mano. No se ha podido comprobar si esto es específico de
headless o del motor Chromium frente a Microsoft Edge (el contenedor no tiene
Edge y no lo necesita), pero el efecto práctico es el mismo: sin esta
navegación real, ningún PDF se descarga.
"""
from __future__ import annotations

import asyncio
import hashlib
import html as ihtml
import io
import re
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from playwright.async_api import BrowserContext, Page, async_playwright
from PyPDF2 import PdfReader

from app.config import settings


class ExpedienteNoPublicadoError(RuntimeError):
    """Ninguna variante de búsqueda (matriz, expediente, separadores `/`, `_`,
    `-`, sin separador) encontró una fila en la tabla de resultados de la
    Plataforma **con una confirmación explícita** de "sin resultados" (ver
    `wait_results`). Distinto de un `RuntimeError` genérico (timeout, WAF,
    formulario no localizado) o de `BloqueoTransitorioError`: esto es un
    resultado negativo determinista, no un fallo transitorio -- `app.scraping.job`
    lo trata aparte para marcar el expediente `sin_publicar` en vez de
    `fallido` y no gastar reintentos en repetir una búsqueda que no va a
    cambiar de resultado (sesión de expedientes sin publicar, CONTEXTO.md
    sección 22: comprobado a mano que estos códigos no están en la
    Plataforma, no es un problema del scraper).

    **Corregido, sesión de límite de tasa (2026-09-07)**: `try_open` antes
    convertía CUALQUIER excepción de cualquier variante de búsqueda (un
    timeout esperando resultados, un WAF, el formulario sin localizar) en
    "sigue con la siguiente variante", y si todas fallaban así, en esta
    excepción -- confundiendo "la Plataforma no respondió/bloqueó la
    petición" con "el expediente no existe". Verificado con datos reales:
    una matriz de carril conocida y publicada (`6.25/28510.0016`) quedó
    marcada `sin_publicar` tras una tanda de cientos de descargas seguidas
    sin ninguna pausa. Ahora solo se lanza cuando `wait_results` confirma de
    verdad el mensaje de "sin resultados" en cada variante intentada --
    cualquier otra excepción se propaga tal cual, nunca se traduce a "no
    publicado"."""


class BloqueoTransitorioError(RuntimeError):
    """La Plataforma devolvió una página reconocible de bloqueo/límite de
    tasa (WAF, "demasiadas peticiones", 429/503) en vez de la tabla de
    resultados o de la confirmación normal de "sin resultados" -- sesión de
    límite de tasa (2026-09-07). Nunca se traduce a `ExpedienteNoPublicadoError`;
    es un fallo transitorio como cualquier otro (reintentable, con backoff,
    `app.queue.calcular_espera_reintento`), pero con una causa identificada
    en el mensaje en vez de un timeout genérico -- útil para saber, sin
    adivinar, si lo que está pasando es un bloqueo real."""

BASE = "https://contrataciondelestado.es"
SEARCH = BASE + "/wps/portal/plataforma/buscadores/busqueda"

# IDs del formulario JSF. Verificados en vivo el 2026-09-02 contra la
# Plataforma real, headless. Son cadenas largas generadas por JSF/WebSphere
# Portal y pueden cambiar sin aviso en un despliegue futuro de la Plataforma;
# si `ensure_form` empieza a fallar, es el primer sitio donde mirar.
CARD = "viewns_Z7_AVEQAI930OBRD02JPMTPG21004_:form1:textFormularioBusqueda"
INPUT = "viewns_Z7_AVEQAI930OBRD02JPMTPG21004_:form1:text71ExpMAQ"
BUTTON = "viewns_Z7_AVEQAI930OBRD02JPMTPG21004_:form1:button1"

# Verificados igual: cada fila de documento en la ficha trae hasta 3 enlaces
# (HTML/XML/PDF) para los "Documentos publicados" y uno solo (icono lupa) para
# el resto de filas (informes, actas, propuestas, resoluciones, contrato...).
# Cuando no hay icono de PDF, DOC_ANCHOR cae al único enlace disponible, que
# en la práctica siempre resuelve a un PDF real vía descarga de navegador.
DOC_ANCHOR = 'a[href*="GetDocumentByIdServlet"], a[href*="docAccCmpnt"]'
PDF_ANCHOR = ('a[href*="GetDocumentByIdServlet"]:has(img[src*="pdf-icon"]), '
              'a[href*="docAccCmpnt"]:has(img[src*="pdf-icon"])')

NAV_MS = settings.scraping_navigation_timeout_ms
UI_MS = settings.scraping_ui_timeout_ms
CONTRACT_MAX_KEEP = settings.scraping_contract_max_keep
REQUIRE_QR = settings.scraping_require_contract_qr_csv_hint

DETAIL_MARKERS = (
    "organo de contratacion", "objeto del contrato", "presupuesto base de licitacion",
    "proceso de licitacion", "documentos publicados", "publicaciones oficiales del boletin",
    "detalle de la licitacion",
)

_DT_RE = re.compile(r"(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}(?::\d{2})?)")
_SERVLET_RE = re.compile(r"(?:GetDocumentByIdServlet|docAccCmpnt)\?[^\s)\"'\]]+", re.I)


# --------------------------------------------------------------------------- #
# Utilidades puras
# --------------------------------------------------------------------------- #
def norm(s) -> str:
    s = str(s or "").lower()
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s).strip()


def safe(s) -> str:
    return re.sub(r"[^\w.-]+", "_", str(s), flags=re.UNICODE).strip("_")[:180]


def absolute(u) -> str:
    u = str(u or "")
    if u.startswith("http"):
        return u
    return BASE + (u if u.startswith("/") else "/" + u)


def sha16(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


def search_variants(code: str) -> list[str]:
    """Código tal cual + intercambios de separador (/ _ - guiones) + sin separadores."""
    code = str(code or "").strip()
    if not code:
        return []
    base = re.sub(r"\s+", "", code)
    out: list[str] = []

    def add(v: str) -> None:
        if v and v not in out:
            out.append(v)

    add(base)
    slash = re.sub(r"[_\-–—]", "/", base)
    add(slash)
    add(slash.replace("/", "_"))
    add(base.replace("/", "_"))
    add(base.replace("_", "/"))
    add(re.sub(r"[/_\-–—]", "", base))
    add(code)
    return out


def parse_dt(text) -> Optional[datetime]:
    m = _DT_RE.search(" ".join(str(text or "").split()))
    if not m:
        return None
    for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M"):
        try:
            return datetime.strptime(m.group(1), fmt)
        except ValueError:
            pass
    return None


def category(label: str) -> str:
    """Clasifica la etiqueta de una fila de documento en la ficha PCSP.

    Nota: esto NO es la clasificación de plantilla (Anuncio PCSP / Propuesta
    LC.27) de la sección 6 de CONTEXTO.md — esa se decide leyendo el contenido
    del documento, en la cascada de extracción, no aquí. Aquí solo se decide
    qué descargar y cómo nombrarlo.
    """
    t = norm(label)
    if not t:
        return ""
    if "anulacion" in t and "pliego" in t:
        return ""
    if "contrato" in t or "contractual" in t or "formalizacion" in t:
        return "CONTRATO"
    if "pliego" in t or "prescripciones" in t or re.search(r"\bppt\b", t):
        return "PLIEGO"
    if "anejo" in t or "anexo" in t:
        return "ANEJO"
    if re.search(r"\badjudi\w*", t) and any(
        k in t for k in ("resoluc", "propuest", "acuerdo", "acta", "mesa", "informe", "adjudicacion")
    ):
        return "ADJUDICACION"
    return ""


# --------------------------------------------------------------------------- #
# Navegación PCSP
# --------------------------------------------------------------------------- #
async def accept_cookies(page: Page) -> None:
    for txt in ("Aceptar todas", "Aceptar todo", "Aceptar y continuar", "Aceptar"):
        for factory in (lambda: page.get_by_role("button", name=txt, exact=False),
                        lambda: page.get_by_text(txt, exact=False)):
            try:
                loc = factory().first
                if await loc.count() and await loc.is_visible():
                    await loc.click(timeout=2000)
                    await page.wait_for_timeout(400)
                    return
            except Exception:
                pass


async def find_in_frames(page: Page, selector: str):
    for fr in page.frames:
        try:
            loc = fr.locator(selector).first
            if await loc.count():
                return loc
        except Exception:
            pass
    return None


async def ensure_form(page: Page):
    """Localiza el input de búsqueda. En headless, igual que con ventana, el
    input no siempre está visible tras cargar: hay que abrir antes la tarjeta
    'Licitaciones' (verificado en vivo — este es el camino que se toma siempre,
    no solo de vez en cuando)."""
    await page.goto(SEARCH, wait_until="domcontentloaded")
    await page.wait_for_timeout(900)
    await accept_cookies(page)

    loc = await find_in_frames(page, f'input[id="{INPUT}"]')
    if loc:
        return loc

    try:
        card = page.locator(f'span[id="{CARD}"]').first
        if await card.count():
            await card.click(timeout=UI_MS)
            await page.wait_for_timeout(1000)
    except Exception:
        pass

    for _ in range(3):
        loc = await find_in_frames(page, f'input[id="{INPUT}"]')
        if loc:
            return loc
        await page.wait_for_timeout(700)
    raise RuntimeError("No se localiza el formulario de Licitaciones")


async def click_search(page: Page) -> None:
    btn = await find_in_frames(page, f'input[id="{BUTTON}"]')
    if not btn:
        raise RuntimeError("No se localiza el botón Buscar")
    await btn.click()


# Frases reconocibles de bloqueo/límite de tasa, verificadas contra el
# hallazgo real de esta sesión (docstring del módulo: el WAF de la
# Plataforma responde "Request Rejected" a peticiones que no vienen de
# navegación real) y las respuestas habituales de un límite de tasa HTTP
# genérico. Sin pretender ser exhaustiva -- lo que no case aquí sigue
# cayendo al timeout genérico de `wait_results`, nunca a
# `ExpedienteNoPublicadoError`.
_FRASES_BLOQUEO = (
    "request rejected", "acceso denegado", "access denied",
    "demasiadas peticiones", "too many requests", "429",
    "no disponible temporalmente", "servicio no disponible", "service unavailable", "503",
)


async def wait_results(page: Page):
    """Devuelve el frame con la tabla de resultados, o `None` cuando la
    Plataforma confirma explícitamente "sin resultados" en el texto de la
    página -- la única señal que cuenta como negativo determinista
    (`ExpedienteNoPublicadoError`, ver su docstring). Cualquier otro
    desenlace se lanza como excepción, nunca como `None`: un bloqueo
    reconocible (`BloqueoTransitorioError`) o, si no hay ninguna frase
    reconocible, un timeout genérico con el último cuerpo visto para
    diagnóstico."""
    start = time.monotonic()
    deadline = start + NAV_MS / 1000
    ultimo_cuerpo = ""
    while time.monotonic() < deadline:
        for fr in page.frames:
            try:
                if await fr.locator("table#myTablaBusquedaCustom tbody tr").count():
                    return fr
            except Exception:
                pass
        if time.monotonic() - start > 3:
            for fr in page.frames:
                try:
                    body = norm(await fr.locator("body").inner_text())
                except Exception:
                    continue
                if not body:
                    continue
                ultimo_cuerpo = body
                if any(x in body for x in ("no se han encontrado resultados", "sin resultados",
                                           "no existen resultados", "no se encontraron resultados")):
                    return None
                if any(x in body for x in _FRASES_BLOQUEO):
                    raise BloqueoTransitorioError(
                        f"la Plataforma devolvió una página de bloqueo/límite de tasa reconocible: "
                        f"{body[:200]!r}"
                    )
        await page.wait_for_timeout(400)
    raise RuntimeError(f"timeout esperando resultados (último cuerpo visto: {ultimo_cuerpo[:200]!r})")


async def _on_results(page: Page) -> bool:
    for fr in page.frames:
        try:
            if await fr.locator("table#myTablaBusquedaCustom tbody tr").count():
                return True
        except Exception:
            pass
    return False


async def _detail_ready(page: Page) -> bool:
    if await _on_results(page):
        return False
    for fr in page.frames:
        try:
            if await fr.locator(DOC_ANCHOR).count():
                return True
        except Exception:
            pass
    for fr in page.frames:
        try:
            body = norm(await fr.locator("body").inner_text())
        except Exception:
            continue
        if any(k in body for k in DETAIL_MARKERS):
            return True
    return False


async def _wait_detail(page: Page) -> bool:
    deadline = time.monotonic() + UI_MS / 1000
    while time.monotonic() < deadline:
        try:
            await page.wait_for_load_state("domcontentloaded")
        except Exception:
            pass
        if await _detail_ready(page):
            return True
        await page.wait_for_timeout(400)
    return await _detail_ready(page)


async def open_detail(page: Page, fr, code: str) -> bool:
    """Pincha en el enlace del expediente listado y confirma que abre la ficha.

    Los enlaces de la tabla de PCSP suelen tener href="#" y navegan por su
    onclick (submit JSF), así que NO se descartan por el href: se prueban por
    orden de prioridad y se verifica que la ficha ha cargado de verdad.
    """
    variants = list(dict.fromkeys(norm(v) for v in search_variants(code) if v))
    want = norm(code)

    for v in variants:
        try:
            link = fr.locator("table#myTablaBusquedaCustom a", has_text=v).first
            if await link.count():
                try:
                    await link.scroll_into_view_if_needed(timeout=2000)
                except Exception:
                    pass
                await link.click()
                if await _wait_detail(page):
                    return True
        except Exception:
            pass

    try:
        rows = fr.locator("table#myTablaBusquedaCustom tbody tr")
        row_total = await rows.count()
    except Exception:
        row_total = 0
    target = None
    for i in range(row_total):
        row = rows.nth(i)
        try:
            if any(v in norm(await row.inner_text()) for v in variants) or want in norm(await row.inner_text()):
                target = row
                break
        except Exception:
            pass
    if target is None:
        return await _detail_ready(page)

    anchors = target.locator("a")
    try:
        total = await anchors.count()
    except Exception:
        total = 0
    scored: list[tuple[int, int]] = []
    for i in range(total):
        a = anchors.nth(i)
        try:
            txt = norm(await a.inner_text() or "")
            href = (await a.get_attribute("href") or "").lower()
            aid = norm(await a.get_attribute("id") or "")
            cls = norm(await a.get_attribute("class") or "")
        except Exception:
            continue
        if "colapsa" in aid or "colapsa" in cls or "colapsa" in href or txt in ("", "+", "-"):
            continue
        score = 0
        if any(v and v in txt for v in variants):
            score += 100
        if "detalle" in txt:
            score += 40
        if any(k in href for k in ("deeplink", "licitacion", "detalle", "muestradetalle", "verdetalle")):
            score += 30
        if any(k in aid for k in ("detalle", "expediente", "objeto", "link")):
            score += 20
        scored.append((score, i))
    scored.sort(reverse=True)
    order = [i for _, i in scored] or list(range(total))

    for idx in order:
        try:
            await anchors.nth(idx).click()
        except Exception:
            continue
        if await _wait_detail(page):
            return True

    return await _detail_ready(page)


async def _intentar_variante(page: Page, code: str, q: str) -> bool:
    """Un único intento de búsqueda (una variante concreta del código):
    `True` si abre la ficha, `False` si la Plataforma confirma "sin
    resultados" para ESTA variante. Puede lanzar cualquier excepción
    (`BloqueoTransitorioError`, timeout, formulario no localizado) -- el
    llamador decide si tolerarla (`try_open`, uso de mejor esfuerzo del
    descubrimiento inverso) o propagarla (`scrape_expediente`, donde
    confundirla con un negativo real marcaría un expediente publicado como
    `sin_publicar`)."""
    field = await ensure_form(page)
    await field.click()
    await field.fill("")
    await field.fill(q)
    await click_search(page)
    fr = await wait_results(page)
    if fr is None:
        return False
    return await open_detail(page, fr, code)


async def try_open(page: Page, code: str) -> bool:
    """Busca un código (con sus variantes) y abre su ficha. `True` si lo
    consigue. Tolerante al fallo de una variante concreta -- pensado para
    `leer_matriz_declarada`/`descubrir_candidatos_acuerdo_marco`, que ya
    recorren muchos candidatos en su propio bucle y no deben abortar el
    lote entero porque una búsqueda puntual falle; un candidato que falla
    así simplemente se trata como no resuelto, nunca como "confirmado sin
    resultados". **No usar en el camino de `scrape_expediente`** (descarga
    real de un expediente): ahí una excepción real nunca debe disolverse en
    "sigue probando" -- ver `ExpedienteNoPublicadoError` y el hallazgo de la
    sesión de límite de tasa en su docstring."""
    for q in search_variants(code):
        try:
            if await _intentar_variante(page, code, q):
                return True
        except Exception:
            continue
    return False


# --------------------------------------------------------------------------- #
# Descubrimiento inverso: candidatos a pedido de un Acuerdo Marco
# --------------------------------------------------------------------------- #
# Sesión de descubrimiento inverso: verificado en vivo contra la Plataforma
# real que la ficha de un Acuerdo Marco NO enlaza sus pedidos, y que la
# sindicación tampoco trae ese campo estructurado (docs/hallazgos-
# sindicacion.md sección 17.1) -- pero el buscador SÍ permite acotar por
# "Sistema de contratación = Contrato basado en un Acuerdo Marco" (id de
# formulario `tipoSistemaContratacion`, valor "3"), combinado con Órgano de
# contratación y Adjudicatario. No existe un campo "Expediente del Acuerdo
# Marco" (las 23 etiquetas del formulario avanzado no traen ninguno) -- por
# eso cada candidato que devuelve la búsqueda hay que abrirlo y leer su
# propia sección "Acuerdo Marco -> Expediente" para confirmar de cuál cuelga
# de verdad (el mismo adjudicatario puede tener más de un Acuerdo Marco a lo
# largo de los años, verificado con 92 resultados reales para un único
# adjudicatario en la muestra de esta sesión).
ORGANO_INPUT = "viewns_Z7_AVEQAI930OBRD02JPMTPG21004_:form1:texoorganoMAQ"
SISTEMA_CONTRATACION_SELECT = "viewns_Z7_AVEQAI930OBRD02JPMTPG21004_:form1:tipoSistemaContratacion"
ADJUDICATARIO_INPUT = "viewns_Z7_AVEQAI930OBRD02JPMTPG21004_:form1:texAdjudicatarioMAQ"
# Valor real del <option> "Contrato basado en un Acuerdo Marco" del select
# "Sistema de contratación" -- verificado en vivo, no inventado (los otros
# valores del mismo select son "Establecimiento del Acuerdo Marco" = "1",
# "Sistema Dinámico de Adquisición" en sus dos variantes = "2"/"4").
SISTEMA_CONTRATO_BASADO_EN_ACUERDO_MARCO = "3"
# El botón de paginación es un <input type="submit"> cuyo `id` cambia entre
# cargas de página (hash generado por JSF) -- localizarlo por su `value`
# visible es lo único estable, verificado en vivo.
BOTON_SIGUIENTE_PAGINA = 'input[value="Siguiente >>"]'

_ACUERDO_MARCO_EXPEDIENTE_RE = re.compile(
    r"Acuerdo Marco\s*\n\s*Expediente\s*\n\s*([^\n]+)", re.IGNORECASE
)


async def buscar_candidatos_acuerdo_marco(page: Page, adjudicatario: str, organo: str = "ADIF") -> list[str]:
    """Rellena el formulario avanzado (Órgano, Sistema de contratación =
    Contrato basado en un Acuerdo Marco, Adjudicatario) y recorre todas las
    páginas de resultado, devolviendo cada código de expediente encontrado
    (con repetidos posibles si se llama varias veces -- el llamador dedupe).
    No abre ninguna ficha todavía, solo la lista de candidatos."""
    field = await ensure_form(page)
    await field.click()
    await field.fill("")

    organo_campo = await find_in_frames(page, f'input[id="{ORGANO_INPUT}"]')
    if organo_campo:
        await organo_campo.fill(organo)
    sistema_campo = await find_in_frames(page, f'select[id="{SISTEMA_CONTRATACION_SELECT}"]')
    if sistema_campo:
        await sistema_campo.select_option(SISTEMA_CONTRATO_BASADO_EN_ACUERDO_MARCO)
    adjudicatario_campo = await find_in_frames(page, f'input[id="{ADJUDICATARIO_INPUT}"]')
    if adjudicatario_campo:
        await adjudicatario_campo.fill(adjudicatario)

    await click_search(page)
    fr = await wait_results(page)
    if fr is None:
        return []

    codigos: list[str] = []
    for _ in range(50):  # tope defensivo, muy por encima de cualquier resultado real visto
        rows = fr.locator("table#myTablaBusquedaCustom tbody tr")
        for i in range(await rows.count()):
            try:
                texto = await rows.nth(i).inner_text()
            except Exception:
                continue
            primera_linea = texto.split("\n", 1)[0].strip()
            if primera_linea:
                codigos.append(primera_linea)
        siguiente = fr.locator(BOTON_SIGUIENTE_PAGINA)
        if not await siguiente.count() or not await siguiente.first.is_enabled():
            break
        try:
            await siguiente.first.click()
            await page.wait_for_timeout(1200)
            await page.wait_for_load_state("domcontentloaded")
        except Exception:
            break
    return codigos


async def leer_matriz_declarada(page: Page, codigo_candidato: str) -> Optional[str]:
    """Abre la ficha de `codigo_candidato` (búsqueda normal, misma vía que
    `try_open`) y lee su sección 'Acuerdo Marco -> Expediente', si la trae.
    `None` si no se pudo abrir la ficha o no declara ninguna matriz."""
    if not await try_open(page, codigo_candidato):
        return None
    for f in page.frames:
        try:
            body = await f.locator("body").inner_text()
        except Exception:
            continue
        if not any(m in norm(body) for m in DETAIL_MARKERS):
            continue
        m = _ACUERDO_MARCO_EXPEDIENTE_RE.search(body)
        if m:
            return m.group(1).strip()
    return None


async def descubrir_candidatos_acuerdo_marco(
    adjudicatario: str, ya_verificados: set[str], organo: str = "ADIF"
) -> tuple[list[str], dict[str, Optional[str]]]:
    """Punto de entrada de esta sección: una única sesión de navegador para
    buscar y, de los candidatos que `ya_verificados` no cubra todavía, abrir
    su ficha y leer la matriz que declaran. Devuelve
    (todos_los_candidatos_de_esta_busqueda, {candidato_nuevo: matriz_o_None})
    -- el llamador (app.extraccion.descubrimiento_matriz) decide qué hacer
    con cada uno contra la base de datos real."""
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(locale="es-ES", accept_downloads=True)
        page = await context.new_page()
        page.set_default_timeout(UI_MS)
        page.set_default_navigation_timeout(NAV_MS)
        try:
            candidatos = await buscar_candidatos_acuerdo_marco(page, adjudicatario, organo)
            nuevas_verificaciones: dict[str, Optional[str]] = {}
            for codigo in dict.fromkeys(candidatos):  # dedup preservando orden
                if codigo in ya_verificados:
                    continue
                nuevas_verificaciones[codigo] = await leer_matriz_declarada(page, codigo)
            return candidatos, nuevas_verificaciones
        finally:
            await context.close()
            await browser.close()


# --------------------------------------------------------------------------- #
# Detalle: localizar y volcar las filas de documentos
# --------------------------------------------------------------------------- #
async def doc_frame(page: Page):
    """Frame del detalle con más enlaces a documentos."""
    best, best_n = None, 0
    for fr in page.frames:
        try:
            n = await fr.locator(DOC_ANCHOR).count()
        except Exception:
            n = 0
        if n > best_n:
            best, best_n = fr, n
    return best


async def expand_collapsibles(fr) -> None:
    """Despliega los grupos colapsables para que aparezcan todas las filas."""
    try:
        toggles = fr.locator('img[id^="imgMasColapsable"]')
        for _ in range(4):
            clicked = 0
            for i in range(await toggles.count()):
                t = toggles.nth(i)
                try:
                    if await t.is_visible():
                        await t.click(timeout=1500)
                        clicked += 1
                        await fr.page.wait_for_timeout(120)
                except Exception:
                    pass
            if not clicked:
                break
            await fr.page.wait_for_timeout(400)
    except Exception:
        pass


async def load_doc_rows(page: Page) -> list[dict]:
    """Lista de {label, dt, hrefs} ya materializada (sin locators vivos).

    `hrefs` trae primero el enlace con icono de PDF si existe (la mayoría de
    filas solo tienen un enlace, sin ese icono, y ese único enlace resuelve a
    PDF igualmente vía descarga de navegador — ver `descargar_documento`)."""
    fr = await doc_frame(page)
    if not fr:
        for txt in ("Documentacion", "Documentos publicados", "Documentos"):
            try:
                tab = page.get_by_role("link", name=txt, exact=False).first
                if await tab.count() and await tab.is_visible():
                    await tab.click(timeout=UI_MS)
                    await page.wait_for_timeout(1000)
                    break
            except Exception:
                pass
        deadline = time.monotonic() + UI_MS / 1000
        while time.monotonic() < deadline and not fr:
            fr = await doc_frame(page)
            if not fr:
                await page.wait_for_timeout(500)
    if not fr:
        return []

    await expand_collapsibles(fr)

    result: list[dict] = []
    rows = fr.locator("tr")
    for i in range(await rows.count()):
        row = rows.nth(i)
        try:
            if not await row.locator(DOC_ANCHOR).count():
                continue
            chosen = row.locator(PDF_ANCHOR)
            if not await chosen.count():
                chosen = row.locator(DOC_ANCHOR)
            hrefs: list[str] = []
            for j in range(await chosen.count()):
                h = await chosen.nth(j).get_attribute("href")
                if h:
                    h = absolute(h)
                    if h not in hrefs:
                        hrefs.append(h)
            if not hrefs:
                continue

            label = ""
            for sel in ("xpath=./td[2]", "xpath=./td[contains(@class,'tipoDocumento')]"):
                try:
                    label = re.sub(r"\s+", " ", await row.locator(sel).inner_text()).strip()
                    if label:
                        break
                except Exception:
                    pass
            if not label:
                try:
                    label = re.sub(r"\s+", " ", await row.inner_text()).strip()
                except Exception:
                    label = ""

            dt = None
            try:
                dt = parse_dt(await row.locator("xpath=./td[1]").inner_text())
            except Exception:
                pass

            result.append({"label": label, "dt": dt, "hrefs": hrefs})
        except Exception:
            continue

    return result


# --------------------------------------------------------------------------- #
# Descarga
# --------------------------------------------------------------------------- #
async def descargar_documento(context: BrowserContext, href: str) -> bytes:
    """Descarga un PDF navegando de verdad.

    El scraper original pedía los PDFs con `context.request.get()` (un cliente
    HTTP aparte, sin motor de render). Contra la Plataforma real esa vía la
    rechaza el WAF con "Request Rejected", headers de navegador incluidos.
    Solo pasan las peticiones que hace el propio Chromium al navegar, así que
    aquí se abre una pestaña, se navega al enlace y se captura el evento
    `download` que dispara el navegador real.
    """
    target = absolute(href)
    page = await context.new_page()
    try:
        seen_download: dict = {}
        page.on("download", lambda dl: seen_download.setdefault("dl", dl))

        for attempt in range(3):
            try:
                resp = await page.goto(target, wait_until="commit", timeout=NAV_MS)
            except Exception:
                resp = None

            deadline = time.monotonic() + 5
            while "dl" not in seen_download and time.monotonic() < deadline:
                await page.wait_for_timeout(100)

            if "dl" in seen_download:
                dl = seen_download.pop("dl")
                path = await dl.path()
                if path:
                    data = Path(path).read_bytes()
                    if b"%PDF-" in data[:1024]:
                        return data
            elif resp is not None:
                body = await resp.body()
                if b"%PDF-" in body[:1024]:
                    return body
                ctype = (resp.headers.get("content-type") or "").lower()
                if "html" in ctype or b"<html" in body[:2048].lower():
                    m = re.search(
                        r'href="([^"]*(?:GetDocumentByIdServlet|docAccCmpnt)[^"]+)"',
                        ihtml.unescape(body.decode("utf-8", "ignore")), re.I,
                    )
                    if m and absolute(m.group(1)) != target:
                        target = absolute(m.group(1))
                        continue

            await asyncio.sleep(0.6 * (2 ** attempt))
        raise RuntimeError(f"descarga fallida: {href}")
    finally:
        await page.close()


def pdf_has_external_links(data: bytes) -> bool:
    try:
        reader = PdfReader(io.BytesIO(data))
    except Exception:
        return False
    for page in reader.pages[:3]:
        try:
            for a in page.get("/Annots") or []:
                obj = a.get_object()
                act = obj.get("/A")
                if act is not None and act.get_object().get("/URI"):
                    return True
        except Exception:
            pass
    return False


def pdf_is_signed(data: bytes) -> bool:
    return b"/ByteRange" in data and b"/Contents" in data


def pdf_has_qr_csv_hint(data: bytes) -> bool:
    try:
        reader = PdfReader(io.BytesIO(data))
        text = " ".join((pg.extract_text() or "") for pg in reader.pages[:2])
    except Exception:
        return False
    return bool(re.search(
        r"csv|codigo seguro de verificacion|código seguro de verificación|"
        r"codigo qr|código qr|sede electronica|sede electrónica|"
        r"verificaci[oó]n de documento",
        text, re.I,
    ))


def pliego_embedded_urls(pliego_bytes: bytes) -> list[str]:
    """Enlaces GetDocumentByIdServlet/docAccCmpnt embebidos en la 1ª página del
    pliego. Es la fuente real de los anejos cuando la ficha no trae fila
    propia de ANEJO (caso frecuente, verificado en vivo: el pliego trae los
    anejos como anotaciones de enlace en su primera página)."""
    urls: list[str] = []
    try:
        reader = PdfReader(io.BytesIO(pliego_bytes))
    except Exception:
        return urls
    if not reader.pages:
        return urls
    page0 = reader.pages[0]

    try:
        for a in page0.get("/Annots") or []:
            try:
                act = a.get_object().get("/A")
                uri = act.get_object().get("/URI") if act is not None else None
            except Exception:
                uri = None
            if uri and _SERVLET_RE.search(str(uri)):
                urls.append(absolute(str(uri)))
    except Exception:
        pass

    try:
        text = page0.extract_text() or ""
    except Exception:
        text = ""
    for m in re.finditer(r"https?://[^\s)\]\"']+(?:GetDocumentByIdServlet|docAccCmpnt)\?[^\s)\]\"']+",
                         text, re.I):
        urls.append(m.group(0))
    for m in _SERVLET_RE.finditer(text):
        frag = m.group(0)
        if "GetDocumentByIdServlet" in frag:
            urls.append(BASE + "/FileSystem/servlet/" + frag)
        else:
            urls.append(BASE + "/wps/wcm/connect/PLACE_es/Site/area/" + frag)

    out, seen = [], set()
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


# --------------------------------------------------------------------------- #
# Selección del documento idóneo de cada tipo
# --------------------------------------------------------------------------- #
@dataclass
class DocumentoDescargado:
    categoria: str  # CONTRATO | PLIEGO | ADJUDICACION | ANEJO
    label: str
    contenido: bytes
    hash: str


@dataclass
class ResultadoScraping:
    codigo_encontrado: str
    documentos: list[DocumentoDescargado] = field(default_factory=list)


async def _descargar_primera_valida(context: BrowserContext, hrefs: list[str]) -> Optional[bytes]:
    for href in hrefs:
        try:
            return await descargar_documento(context, href)
        except Exception:
            continue
    return None


async def seleccionar_documentos(context: BrowserContext, docs: list[dict]) -> list[DocumentoDescargado]:
    """Descarga las candidatas de cada categoría y aplica la misma limpieza que
    el scraper original: contratos válidos (firmados, sin enlaces externos, con
    pista CSV/QR) hasta CONTRACT_MAX_KEEP, el pliego más reciente, la
    adjudicación válida más reciente, y todos los anejos (filas propias +
    enlaces embebidos en el pliego), deduplicados por hash de contenido."""
    def rows_of(cat: str) -> list[dict]:
        items = [d for d in docs if category(d["label"]) == cat]
        items.sort(key=lambda d: d["dt"] or datetime.min, reverse=True)
        return items

    seen_hash: set[str] = set()

    def dedup(data: bytes) -> Optional[str]:
        h = sha16(data)
        if h in seen_hash:
            return None
        seen_hash.add(h)
        return h

    salida: list[DocumentoDescargado] = []

    # CONTRATOS
    contrato_candidatos: list[tuple[dict, bytes, str]] = []
    for d in rows_of("CONTRATO"):
        data = await _descargar_primera_valida(context, d["hrefs"])
        if data is None:
            continue
        h = dedup(data)
        if h is None:
            continue
        contrato_candidatos.append((d, data, h))
    validos = [c for c in contrato_candidatos
               if not pdf_has_external_links(c[1]) and pdf_is_signed(c[1])
               and (pdf_has_qr_csv_hint(c[1]) if REQUIRE_QR else True)]
    if not validos and contrato_candidatos:
        validos = sorted(contrato_candidatos, key=lambda c: c[0]["dt"] or datetime.min, reverse=True)[:1]
    for d, data, h in sorted(validos, key=lambda c: c[0]["dt"] or datetime.min, reverse=True)[:CONTRACT_MAX_KEEP]:
        salida.append(DocumentoDescargado("CONTRATO", d["label"], data, h))

    # PLIEGO: solo la fila más reciente
    pliego_bytes: Optional[bytes] = None
    pliego_rows = rows_of("PLIEGO")
    if pliego_rows:
        data = await _descargar_primera_valida(context, pliego_rows[0]["hrefs"])
        if data is not None:
            h = dedup(data)
            if h is not None:
                salida.append(DocumentoDescargado("PLIEGO", pliego_rows[0]["label"], data, h))
                pliego_bytes = data

    # ADJUDICACIONES: se queda la más reciente válida
    adj_candidatos: list[tuple[dict, bytes, str]] = []
    for d in rows_of("ADJUDICACION"):
        data = await _descargar_primera_valida(context, d["hrefs"])
        if data is None:
            continue
        h = dedup(data)
        if h is None:
            continue
        adj_candidatos.append((d, data, h))
    validos_adj = [c for c in adj_candidatos if not pdf_has_external_links(c[1]) and pdf_is_signed(c[1])] or adj_candidatos
    if validos_adj:
        d, data, h = max(validos_adj, key=lambda c: c[0]["dt"] or datetime.min)
        salida.append(DocumentoDescargado("ADJUDICACION", d["label"], data, h))

    # ANEJOS: filas propias + enlaces embebidos en el pliego
    anejo_urls: list[str] = []
    for d in rows_of("ANEJO"):
        anejo_urls.extend(d["hrefs"])
    if pliego_bytes:
        anejo_urls.extend(pliego_embedded_urls(pliego_bytes))

    for href in dict.fromkeys(anejo_urls):
        try:
            data = await descargar_documento(context, href)
        except Exception:
            continue
        h = dedup(data)
        if h is None:
            continue
        salida.append(DocumentoDescargado("ANEJO", "ANEJO", data, h))

    return salida


# --------------------------------------------------------------------------- #
# Punto de entrada
# --------------------------------------------------------------------------- #
async def scrape_expediente(codigo_expediente: str, codigo_matriz: Optional[str] = None) -> ResultadoScraping:
    """Busca primero la matriz (si la hay) y, si PCSP no la encuentra, el
    expediente. Devuelve los documentos ya descargados y seleccionados,
    listos para persistir vía la interfaz de almacenamiento."""
    candidatos = [c for c in dict.fromkeys([codigo_matriz, codigo_expediente]) if c]
    if not candidatos:
        raise ValueError("se necesita codigo_expediente o codigo_matriz")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(locale="es-ES", accept_downloads=True)
        page = await context.new_page()
        page.set_default_timeout(UI_MS)
        page.set_default_navigation_timeout(NAV_MS)
        try:
            # A propósito, distinto de `try_open`: ninguna excepción se
            # traga aquí. Cada variante de cada candidato llama a
            # `_intentar_variante` directamente -- si alguna lanza
            # (`BloqueoTransitorioError`, timeout, formulario no
            # localizado), se propaga tal cual tan pronto ocurre. Nunca se
            # sigue probando otra variante ni el siguiente candidato tras un
            # fallo real: un entorno que bloquea o da timeout en una
            # consulta probablemente da el mismo resultado en cualquier
            # otra, así que seguir insistiendo no distingue nada y solo
            # añade carga a una Plataforma que ya está fallando (ver
            # docstring de `ExpedienteNoPublicadoError`, hallazgo real de la
            # sesión de límite de tasa). Solo llegar limpiamente al final
            # de todos los candidatos, con cada variante confirmando "sin
            # resultados" de verdad, cuenta como negativo determinista.
            matched = None
            for code in candidatos:
                for q in search_variants(code):
                    if await _intentar_variante(page, code, q):
                        matched = code
                        break
                if matched:
                    break
            if not matched:
                raise ExpedienteNoPublicadoError(
                    f"no encontrado en la Plataforma ni por matriz ni por expediente: "
                    f"{' | '.join(candidatos)}"
                )
            docs = await load_doc_rows(page)
            if not docs:
                raise RuntimeError(f"ficha abierta ({matched}) pero sin filas de documento")
            documentos = await seleccionar_documentos(context, docs)
            return ResultadoScraping(codigo_encontrado=matched, documentos=documentos)
        finally:
            await context.close()
            await browser.close()
