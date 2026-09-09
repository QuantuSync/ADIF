import hashlib
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Callable, Optional

from sqlalchemy.orm import Session

from app.extraccion.codigo_material import derivar_codigo_material
from app.extraccion.normalizacion import (
    limpiar_codigo_celda,
    limpiar_texto_celda,
    normalizar_guiones,
    parsear_importe_es,
    parsear_numero_es,
)
from app.extraccion.tabla import TablaExtraida
from app.extraccion.texto import normalizar
from app.models import LineaCatalogo, Lote

# `LineaCatalogo.codigo_precio` es `String(32)` (app/models.py) -- se lee del
# propio modelo, no se repite el número a mano, para que no puedan divergir.
_CODIGO_PRECIO_LONGITUD_MAXIMA = LineaCatalogo.codigo_precio.type.length

# Sesión de rodaje sobre el corpus completo (2026-09-03): en varias tablas
# reales, una fila que no es una línea de material (un pie de tabla como
# "PRESUPUESTO DE LICITACIÓN", "IVA", "TOTAL CON IVA", o una partida alzada
# sin celda de matrícula propia) desplaza sus columnas y el texto de esa fila
# cae en la columna de matrícula — que es `varchar(9)` y revienta el INSERT
# con cualquier texto más largo. CONTEXTO.md sección 2: la matrícula "no es"
# nunca texto, es un código de 9 dígitos; cualquier valor con una letra ya es
# la señal de que esta fila no es lo que el mapeo de cabecera cree que es.
_MATRICULA_VALIDA_RE = re.compile(r"^\d+$")

# Hallazgo real (aviso del cliente, sesión 2026-09-07): el modelo, cuando
# una tabla no trae ninguna columna de unidad de medida de verdad, tiende a
# mapear "unidad_medida" a una columna en blanco o ajena en vez de devolver
# `null` -- dos variantes reales distintas, las dos resueltas por el
# modelo, ninguna por las reglas deterministas:
# - `6.20/28510.0054` ANEJO_8 p.10 (traviesas): mapeó "unidad_medida" a la
#   columna "E.T." (Especificación Técnica, una referencia normativa como
#   "03.360.571.8") en 5 variantes de la misma cabecera
#   (`cache_mapeo_cabecera` ids 71-75, `origen="modelo"`).
# - `6.20/28510.0094` ANEJO p.4 (candado/llave): mapeó "unidad_medida" a
#   una columna sin cabecera de texto (`id` 77, `origen="modelo"`) que en
#   realidad trae el valor de "CANTIDADES ESTIMADAS" desplazado una
#   columna a la izquierda por una columna fantasma -- el mismo fenómeno de
#   desfase que ya resuelven `_recuperar_cantidad_columna_fantasma` y
#   companía, aquí aterrizando en unidad_medida en vez de cantidad porque
#   el modelo, no una regla de recuperación de columna fantasma, fue quien
#   decidió el mapeo.
# Ninguna unidad de medida real del corpus es nunca solo dígitos y puntos
# (ud, UD., m, M, t, kg, PA, dm3, m³... siempre llevan alguna letra) --
# tanto una referencia normativa como un valor de cantidad desplazado sí
# lo son. Igual que `_MATRICULA_VALIDA_RE` arriba: la FORMA del valor
# extraído es la señal de que la columna no es la que el mapeo cree que
# es, sin importar de dónde vino el mapeo (modelo o determinista) ni
# cuántas variantes de cabecera existan sin descubrir todavía.
_UNIDAD_MEDIDA_IMPLAUSIBLE_RE = re.compile(r"^[\d.]+$")

# Bloque 3, segunda tanda de cambios del cliente tras revisar el catálogo
# (sesión 2026-09-09): verificado contra el corpus real que el 7,3% que
# resultó ser un defecto de extracción (bloque 4) no agota el 100% de las
# líneas sin unidad -- `6.20/28510.0136_ANEJO_3.pdf` ("hilo de contacto" y
# familia, matrículas 642910100 y similares) no declara ninguna columna de
# unidad en absoluto, pero la propia celda de cantidad trae el número y la
# unidad pegados ("120000 Kg", "1200 m") y la de precio unitario trae la
# unidad tras el símbolo de división ("9,61 €/Kg", "4,05 €/m") -- ninguna
# de las dos rompe `parsear_numero_es`/`parsear_importe_es` (que ya
# descartan cualquier carácter que no sea dígito o separador), así que
# cantidad y precio ya salían bien: solo la unidad se perdía por no tener
# columna propia que leer. Verificado con un barrido real de los 64
# documentos detrás de las líneas sin unidad de todo el corpus (bloque 4
# del diagnóstico anterior): "Kg" y "m" son los dos únicos tokens que
# aparecen así, pegados a un número de cantidad o tras "€/" en el precio --
# no se amplía esta lista sin verificar un caso real nuevo primero (mismo
# criterio que las redacciones de baja, CONTEXTO.md sección 4).
_UNIDAD_EMBEBIDA_EN_CANTIDAD_RE = re.compile(r"^[\d.,]+\s*(Kg|m)\.?$", re.IGNORECASE)
_UNIDAD_EMBEBIDA_EN_PRECIO_RE = re.compile(r"€\s*/\s*(Kg|m)\b", re.IGNORECASE)


def _extraer_unidad_embebida(cantidad_bruta: Optional[str], precio_bruto: Optional[str]) -> Optional[str]:
    """Solo se llama cuando la cabecera no declaró ninguna columna de
    unidad de medida (o su valor salió descartado por implausible, ver
    `_UNIDAD_MEDIDA_IMPLAUSIBLE_RE`) -- nunca pisa una unidad ya resuelta
    en su propia columna. Mira primero la celda de cantidad (el caso más
    común en el corpus verificado) y, si no encuentra nada ahí, la de
    precio -- una fila puede traer cantidad vacía del todo y la unidad
    solo en el precio (verificado: `740560006`/`740570001`, cantidad
    vacía, precio "14,70 €/Kg")."""
    if cantidad_bruta:
        coincidencia = _UNIDAD_EMBEBIDA_EN_CANTIDAD_RE.match(cantidad_bruta.strip())
        if coincidencia:
            return coincidencia.group(1)
    if precio_bruto:
        coincidencia = _UNIDAD_EMBEBIDA_EN_PRECIO_RE.search(precio_bruto)
        if coincidencia:
            return coincidencia.group(1)
    return None


# Mismo aviso del cliente: en la misma tabla, la columna "CANTIDAD DE
# REFERENCIA" del documento original trae valores en un rango que parece un
# año (1872, 1996-2005, la mayoría exactamente "2000") en vez de una
# cantidad de material plausible. A diferencia de "unidad_medida" arriba,
# aquí el mapeo SÍ es correcto -- la cabecera del documento dice literalmente
# "CANTIDAD DE REFERENCIA" y el valor extraído coincide con esa columna) --
# así que no hay nada que "arreglar" en el mapeo: es la propia tabla del
# documento la que trae un valor ambiguo (¿cantidad real de existencias
# redondas, o un año de referencia/homologación mal etiquetado en el propio
# documento?). Verificado que un valor en este rango NO siempre es un error
# -- `6.24/28510.0064` (cable, "2000 M") y `6.25/28510.0028` (balasto,
# "2.000,00 t") tienen la misma cifra y son cantidades reales plausibles,
# confirmadas contra su documento de origen -- así que este rango nunca se
# usa para "corregir" nada, solo para marcar la línea y que un humano lo
# confirme contra el documento, igual de barato si acaba siendo una
# cantidad real que si acaba siendo un año.
_CANTIDAD_ANIO_MIN = 1900
_CANTIDAD_ANIO_MAX = 2100


def _cantidad_parece_implausible(cantidad: Decimal) -> Optional[str]:
    """Devuelve el motivo de revisión si `cantidad` no parece una cantidad de
    material plausible, o `None` si no hay nada que marcar. Solo señales
    baratas y sin falsos positivos costosos (una cantidad real marcada de
    más solo cuesta una confirmación humana, nunca se descarta ni se
    corrige sola): un valor en rango de año, o cero. Nunca se usan aquí
    umbrales de "N veces la mediana del expediente" -- investigado en la
    misma sesión (aviso del cliente): en `6.24/28510.0130` (pequeño material
    de sujeción de vía, comprado por decenas de miles de unidades) y en
    `6.25/28510.0028` (toneladas-kilómetro de balasto frente a toneladas),
    la heterogeneidad de unidades y de tipo de material dentro de un mismo
    expediente produce cocientes de más de 50x que son legítimos -- ningún
    caso real de escala incorrecta en el corpus, igual que ya se concluyó
    para los atípicos de precio en `docs/excel-cliente-correccion.md`
    bloque 3. Un umbral así aquí solo añadiría ruido, no señal."""
    if cantidad == 0:
        return "cantidad es 0: confirmar si es un valor real del documento (p.ej. un elemento de catálogo sin pedido estimado en este contrato) o un dato perdido"
    if cantidad == cantidad.to_integral_value() and _CANTIDAD_ANIO_MIN <= cantidad <= _CANTIDAD_ANIO_MAX:
        return (
            f"cantidad ({cantidad:.0f}) está en un rango que parece un año, no una cantidad de material: "
            "confirmar contra el documento original"
        )
    return None

# Coincidencia exacta (tras normalizar y quitar espacios): estas filas no son
# una línea de material, son el resumen de la tabla — se descartan enteras,
# no se guardan con matrícula vacía ni con ningún otro campo relleno.
_ETIQUETAS_PIE_TABLA = frozenset({
    "presupuestodelicitacion",
    "presupuestodeadjudicacion",
    "baseimponible",
    "totalconiva",
    "totaliva",
    "subtotal",
    "importetotal",
    "iva",
    "total",
})


def _es_pie_de_tabla(texto_normalizado_sin_espacios: str) -> bool:
    return texto_normalizado_sin_espacios in _ETIQUETAS_PIE_TABLA


def _es_partida_alzada(texto_normalizado_sin_espacios: str) -> bool:
    # "Partida alzada a justificar para imprevistos" y variantes: CONTEXTO.md
    # sección 2 la define como línea legítima ("sin matrícula ni código de
    # material"), así que el texto no se descarta — se recupera como
    # descripción, nunca como matrícula.
    return texto_normalizado_sin_espacios.startswith("partidaalzada")


# Sesión de los 3 expedientes que seguían en revisión tras el criterio de
# lote laxo del cliente (CONTEXTO.md sección 26): un guion suelto en una celda
# de matrícula/cantidad/precio unitario es la misma convención administrativa
# que un hueco en blanco ("no aplica a esta fila"), verificado contra las 39
# filas reales de `6.24/28510.0117` — la propia tabla usa el guion en la
# celda de matrícula Y en la de código de elemento de la misma fila,
# sistemáticamente, nunca solo en una fila suelta. No es un dato ilegible que
# haga falta revisar, es la forma en que el documento dice "vacío" — igual
# que CONTEXTO.md sección 2 ya trata la ausencia de matrícula en el ~34% de las
# líneas como algo normal, no un error. Distinto de un valor con identificadores
# de glifo sin decodificar (CID) o de dos valores duplicados que no coinciden:
# esos sí son ilegibles de verdad y siguen yendo a revisión (ver
# `parsear_numero_es`).
def _es_celda_vacia(valor: Optional[str]) -> bool:
    if valor is None:
        return False
    return normalizar_guiones(valor).strip() == "-"


# Sesión de defectos de auditoría (2026-09-05, docs/correccion-defectos-
# auditoria.md): formatos de codigo_precio verificados contra el corpus real
# y contra `tests/test_catalogo.py` / `tests/fixtures/__init__.py`. CONTEXTO.md
# sección 3 solo menciona "P-001, P-067"; el corpus real trae más variantes,
# todas confirmadas: "P-001" (con guion), "P1"/"P01" (sin guion, 1-2
# dígitos), "PN001"/"PN09" (prefijo de señalización), "PA-01" (partida
# alzada numerada), "L01-T01" (lote+tipo, traviesas). "COD0001" añadido en el
# bloque 3 de la sesión de expedientes en revisión (2026-09-07,
# `4.26/28510.0020_ANEJO_1.pdf`, instalaciones de seguridad): sin esta
# variante, `app.extraccion.tabla._es_fila_de_datos` no reconocía ninguna
# fila de la tabla real como fila de datos y la tabla entera se descartaba
# antes de llegar aquí -- se añade también aquí para que, una vez aceptada
# en la etapa 4, no vuelva a caer en "formato no reconocido" en esta segunda
# validación. Un codigo_precio que no encaje aquí no se guarda en silencio
# (encargo de esta sesión, punto 1): ver `_normalizar_codigo_precio`.
_CODIGO_PRECIO_NUCLEO_RE = re.compile(r"(?:P|PN|PA|COD)-?\d{1,4}|L\d{1,2}-T\d{1,2}", re.IGNORECASE)
_CODIGO_PRECIO_VALIDO_RE = re.compile(rf"^(?:{_CODIGO_PRECIO_NUCLEO_RE.pattern})$", re.IGNORECASE)

# Quinto formato, sesión de expedientes en revisión (2026-09-05),
# `6.26/28510.0016`: la cabecera real de esa tabla dice literalmente
# "PARTIDA", no "Código de precio", y numera las filas 1..41 sin ningún
# prefijo de letra -- verificado que son únicas dentro del lote (sin
# colisión), igual de identificador de línea dentro del documento que
# "P-001" (CONTEXTO.md sección 2), solo que sin prefijo. Aparte de
# `_CODIGO_PRECIO_NUCLEO_RE` (no dentro): ese patrón también se usa para
# aislar el código real en medio de ruido de pie de página
# (`_normalizar_codigo_precio` más abajo), y un dígito suelto ahí
# recuperaría números sueltos de cualquier ruido, no solo de este formato
# verificado.
_CODIGO_PRECIO_BARE_RE = re.compile(r"^\d{1,4}$")

# El pie de página de verificación CSV del documento (una URL del tipo
# "https://sede.adif.gob.es/csv/valida.jsp") se cuela invertido carácter a
# carácter en la celda del código cuando el sello de verificación se solapa
# en coordenadas con esa columna — hallazgo real, `6.23/28510.0042` (21
# líneas) y `6.24/28510.0180` (7 líneas), verificado en
# docs/correccion-defectos-auditoria.md: el ruido resultante es siempre
# letras y los símbolos de una URL invertida (`/`, `.`, `:`), nunca dígitos,
# así que el código real siempre se puede aislar como el único fragmento que
# encaja en `_CODIGO_PRECIO_NUCLEO_RE` dentro de la cadena corrupta.
_RUIDO_PIE_PAGINA_RE = re.compile(r"^[A-Za-zÀ-ÿ/.:]+$")


def _normalizar_codigo_precio(bruto: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """Valida y, si hace falta, recupera el código de precio ya limpio de
    espacios/guiones (`limpiar_codigo_celda`). Devuelve `(codigo,
    motivo_revision)`:

    - Formato conocido (`_CODIGO_PRECIO_VALIDO_RE` o `_CODIGO_PRECIO_BARE_RE`,
      un número suelto bajo cabecera "PARTIDA") -> se guarda tal cual, sin
      motivo.
    - Ruido de pie de página con el código real todavía aislable dentro de
      la cadena -> se recupera el código limpio, con motivo — igual que la
      recuperación de cabecera desalineada (`_intentar_recuperar_desalineacion`):
      el dato se conserva, pero marcado para que un humano lo confirme.
    - Ruido de pie de página sin ningún código aislable (la celda entera es
      el pie de página, no trae código) -> se descarta (`None`), con
      motivo. El resto de la línea (matrícula, descripción, precio) no se ve
      afectado y puede seguir siendo una línea de catálogo válida.
    - Cualquier otro valor que no encaje en ningún formato conocido del
      corpus (comprobación general del encargo, no solo el caso del pie de
      página) -> se conserva tal cual, porque podría ser un formato
      legítimo todavía no catalogado, pero NUNCA en silencio: siempre con
      `motivo_revision`.
    """
    limpio = limpiar_codigo_celda(bruto)
    if limpio is None:
        return None, None
    if _CODIGO_PRECIO_VALIDO_RE.match(limpio) or _CODIGO_PRECIO_BARE_RE.match(limpio):
        return limpio, None

    coincidencias = list(_CODIGO_PRECIO_NUCLEO_RE.finditer(limpio))
    if len(coincidencias) == 1:
        nucleo = coincidencias[0]
        resto = limpio[: nucleo.start()] + limpio[nucleo.end() :]
        # Mínimo 2 caracteres de ruido, no 1 (hallazgo real, sesión
        # 2026-09-05, `6.24/28510.0185`): "P-001b"/"P-002b"... son códigos
        # DISTINTOS de "P-001"/"P-002" (mismo material, precio distinto —
        # dos tablas de precios reales del mismo documento, no ruido), y una
        # sola letra de cola encaja en el mismo patrón que el ruido real de
        # pie de página. Los 31 casos reales de pie de página verificados
        # (`6.23/28510.0042`, `6.24/28510.0180`) traen siempre 2 o más
        # caracteres de ruido — nunca uno solo — así que exigir el mínimo no
        # deja de recuperar ningún caso real y evita fundir dos códigos
        # legítimos y distintos en uno.
        if len(resto) >= 2 and _RUIDO_PIE_PAGINA_RE.match(resto):
            return nucleo.group(), (
                "codigo_precio recuperado tras descartar ruido de pie de página colado en la celda "
                f"({limpio!r} -> {nucleo.group()!r})"
            )

    if _RUIDO_PIE_PAGINA_RE.match(limpio):
        return None, (
            f"codigo_precio descartado: pie de página de verificación colado en la celda, "
            f"sin código recuperable ({limpio!r})"
        )

    # Mismo tipo de fallo que la matrícula (comentario de cabecera de este
    # módulo): una celda de "REFERENCIA DEL FABRICANTE"/código con varias
    # filas fundidas en una (`_dividir_fila_multiple` no aplica sin una
    # columna de precio con la que dividir en el mismo N, CONTEXTO.md
    # sección 8) puede superar los 32 caracteres de la columna y reventar el
    # INSERT completo del lote entero, no solo esta línea (hallazgo real,
    # `6.24/28510.0208`, tabla de reparación de repuestos sin columna de
    # importe unitario). Se descarta en vez de truncar -- truncar
    # inventaría un código distinto que no está en el documento.
    if len(limpio) > _CODIGO_PRECIO_LONGITUD_MAXIMA:
        return None, (
            f"codigo_precio descartado: {len(limpio)} caracteres, no cabe en la columna "
            f"({_CODIGO_PRECIO_LONGITUD_MAXIMA} máx.), probablemente varias filas fundidas en una: {limpio!r}"
        )

    return limpio, (
        f"codigo_precio con formato no reconocido en el corpus, revisar antes de dar por bueno: {limpio!r}"
    )


def _acumular_motivo(motivo: Optional[str], nuevo: Optional[str]) -> Optional[str]:
    if not nuevo:
        return motivo
    return f"{motivo}; {nuevo}" if motivo else nuevo


def _acumular_motivo_unico(motivo: Optional[str], nuevo: str) -> str:
    """Como `_acumular_motivo`, pero no repite `nuevo` si una fusión por
    firma ya lo dejó anotado en una vuelta anterior (una firma puede
    absorber más de dos filas, CONTEXTO.md sección 9 sobre idempotencia:
    reprocesar no debe ni duplicar filas ni duplicar texto de motivo)."""
    if motivo and nuevo in motivo:
        return motivo
    return _acumular_motivo(motivo, nuevo)


def _valor_en(fila: list[Optional[str]], indice: Optional[int]) -> Optional[str]:
    if indice is None or indice < 0 or indice >= len(fila):
        return None
    return fila[indice]


# Sesión de filas fantasma (2026-09-04): una fila cuya descripción y precio
# unitario salen vacíos del mapeo normal no siempre es una fila de relleno
# (pie de tabla, fragmento de una descripción envuelta) — a veces es una
# línea real cuyo `fragmento` trae código, descripción, cantidad y precio,
# pero el mapeo de cabecera y los datos de esa tabla concreta quedan
# desplazados una columna entre sí (hallazgo real, `6.24/28510.0187_ANEJO_1.pdf`
# p.11: `pdfplumber` coloca el texto de cabecera, centrado, en una columna
# física distinta de donde cae el texto de los datos, alineado a la
# izquierda, dentro del mismo grupo de columnas). Verificado que el
# desplazamiento es uniforme para toda la fila, nunca solo en un campo.
_LETRA_RE = re.compile(r"[A-Za-zÀ-ÿ]")


def _parece_descripcion_recuperable(texto: Optional[str]) -> bool:
    limpio = limpiar_texto_celda(texto)
    if not limpio or len(limpio) < 3 or not _LETRA_RE.search(limpio):
        return False
    clave = normalizar(limpio).replace(" ", "")
    return not _es_pie_de_tabla(clave)


# Sesión de duplicados de partidas alzadas (2026-09-05, expediente
# 6.20/28510.0054): un contrato firmado puede incluir, como anejo propio,
# una copia íntegra del mismo cuadro de precios que ya existe como documento
# `anejo` independiente del expediente — legítimo (el contrato adjunta su
# anejo firmado), no un error de scraping. Verificado contra el PDF real:
# `CONTRATO_b77dfe4d8c537500.pdf` páginas 114-126 reproducen palabra por
# palabra el "LISTADO DE MATERIALES A SUMINISTRAR" de `ANEJO_6ab4839cc...pdf`.
#
# El defecto: en varias páginas de esa copia dentro del contrato,
# `pdfplumber` intercala una columna en blanco extra entre la matrícula y la
# designación que no existe en el anejo independiente — la cabecera
# combinada (`_combinar_filas_cabecera`) sale idéntica en ambos documentos
# (la columna fantasma está vacía también en las filas de cabecera), así que
# la firma de cabecera y su mapeo cacheado coinciden, pero aplicado a las
# filas de datos del contrato deja la celda de descripción vacía y el texto
# real cae en la columna siguiente, no mapeada.
#
# Para una fila con matrícula esto pasa inadvertido: `calcular_clave_linea`
# prioriza la matrícula (que sí sale bien, en su columna de siempre) como
# clave, así que las dos copias de la misma fila material se funden en una
# sola por clave exacta sin que importe cuál trajo la descripción vacía. Pero
# una partida alzada (CONTEXTO.md sección 2: nunca trae matrícula) cae en el
# `hash(descripción + orden_aparicion)` de `calcular_clave_linea` — con la
# descripción vacía en la copia del contrato y presente en la del anejo, el
# hash sale distinto para lo que es la misma línea real, y las dos copias se
# guardan como filas separadas en vez de fundirse.
def _recuperar_descripcion_columna_fantasma(
    fila: list[Optional[str]], mapeo: dict[str, Optional[int]]
) -> Optional[str]:
    """Solo se llama cuando la fila no tiene matrícula (huérfana: partida
    alzada u otra fila sin matrícula ni código de precio) y su descripción
    salió vacía con el mapeo normal. A diferencia de
    `_intentar_recuperar_desalineacion`, que desplaza el mapeo entero, aquí
    solo se prueba la columna inmediatamente posterior a la de descripción —
    desplazar el mapeo entero perdería la matrícula en una fila que sí la
    trajera, y esta función nunca se llama para esas.

    No se acepta la recuperación si esa columna siguiente ya la usa otro
    campo del mapeo (p. ej. cuando descripción y unidad de medida son
    columnas contiguas de verdad): ahí la celda no es una columna fantasma,
    es el dato legítimo de otro campo, y copiarlo como descripción sería
    inventar un valor que no es tal."""
    indice_descripcion = mapeo.get("descripcion")
    if indice_descripcion is None:
        return None
    indice_siguiente = indice_descripcion + 1
    if indice_siguiente in {indice for campo, indice in mapeo.items() if campo != "descripcion"}:
        return None
    candidata = _valor_en(fila, indice_siguiente)
    if not _parece_descripcion_recuperable(candidata):
        return None
    return limpiar_texto_celda(candidata)


# Sesión de verificación del Excel exportado (2026-09-08): último recurso
# antes de dar una fila por "sin descripción ni matrícula" -- verificado
# contra dos documentos reales (`6.22/28510.0039` p.14, `6.25/28510.0213`
# p.18) que a una "PARTIDA ALZADA A JUSTIFICAR..." (CONTEXTO.md sección 2:
# legítima, nunca lleva matrícula ni código de material propio) le faltan
# columnas intermedias respecto al resto de la tabla, así que su único texto
# real cae en la columna que la cabecera de ESA tabla llama "código de
# precio" o "código ADIF" -- una columna que el mapeo, correctamente para el
# resto de filas, no asigna nunca a `descripcion` (a veces ni siquiera a
# ningún campo: la cabecera no encajó con ningún alias determinista y quedó
# sin mapear del todo). Distinto de `_recuperar_descripcion_columna_fantasma`
# (que solo prueba la columna siguiente a la de descripción, con el índice
# de descripción ya conocido): aquí no hay ninguna columna "de al lado" que
# probar porque la propia columna de descripción sale vacía Y no hay
# matrícula con la que orientarse, así que se explora toda la fila.
def _recuperar_descripcion_ultimo_recurso(
    fila: list[Optional[str]], mapeo: dict[str, Optional[int]]
) -> Optional[str]:
    """Solo se llama cuando descripción Y matrícula salieron vacías con el
    mapeo normal (ninguna otra columna del mapeo identifica el material).
    Prueba cualquier columna de la fila que el mapeo no reclame para NINGÚN
    campo -- nunca le quita el valor a un campo que sí lo reclama. Solo se
    acepta si hay EXACTAMENTE una columna candidata con pinta de descripción
    real: con dos o más, no hay forma de saber cuál es la buena sin
    adivinar, y se deja la fila como estaba (a revisión, sin inventar)."""
    reclamadas = {indice for indice in mapeo.values() if indice is not None}
    candidatas = [
        indice
        for indice in range(len(fila))
        if indice not in reclamadas and _parece_descripcion_recuperable(_valor_en(fila, indice))
    ]
    if len(candidatas) != 1:
        return None
    return limpiar_texto_celda(_valor_en(fila, candidatas[0]))


# Sesión de inventario de celdas vacías (2026-09-06, bloque 3): antes de
# etiquetar la cantidad vacía como "no consta" en toda la web, se verificó
# contra el documento real detrás del mayor concentrador de nulos
# (`6.25/28510.0019_ANEJO_1.pdf`, página 28) con la propia cascada
# (`pdfplumber` + `extraer_tablas_pagina`) en vez de fiarse del dato ya
# guardado. Hallazgo real: la cabecera de esa tabla es
# `["CÓDIGO DEL PRECIO", "Nº MATRÍCULA", "DESCRIPCIÓN", "UNIDAD DE MEDIDA",
# None, "CANTIDADES ESTIMADAS DE REFERENCIA", "PRECIO DE REFERENCIA"]` — el
# mapeo determinista, correctamente, ata `cantidad` a la columna que trae el
# texto "CANTIDADES ESTIMADAS DE REFERENCIA" (índice 5). Pero en las FILAS
# de datos de esa misma tabla, el valor numérico real cae sistemáticamente
# en la columna fantasma sin etiquetar que la precede (índice 4): `['P-431',
# '', 'Tirante TI-22-D-AT1', 'UN', '10', None, '3.270,00 €']` — la columna 5
# (la que "cantidad" señala) es SIEMPRE `None` en cada fila, y la 4 (fantasma
# en la cabecera) trae siempre el número real. `pdfplumber` particiona la fila
# de cabecera con un límite de columna que no coincide con el de las filas de
# datos, mismo fenómeno que ya cubren `_recuperar_descripcion_columna_fantasma`
# y `_intentar_recuperar_desalineacion` para descripción/precio, pero ninguna
# de esas dos se dispara aquí (descripción y precio_unitario salen bien en su
# columna de siempre, la fila no cae ni en pie de tabla ni en fragmento
# huérfano) — sin este recorte, esas líneas se etiquetarían como "no consta"
# en la web cuando el dato SÍ está en el documento, uno de los "falsos
# huecos" que el bloque 3 pedía verificar antes de dar por buenos.
def _parece_cantidad_recuperable(texto: Optional[str]) -> bool:
    if not texto or _es_celda_vacia(texto):
        return False
    try:
        parsear_numero_es(texto)
    except ValueError:
        return False
    return True


def _parece_precio_recuperable(texto: Optional[str]) -> bool:
    if not texto or _es_celda_vacia(texto):
        return False
    try:
        parsear_importe_es(texto)
    except ValueError:
        return False
    return True


# Mismo hallazgo, un segundo caso real (sesión de inventario de celdas
# vacías, bloque 3): `6.23/28510.0051_CONTRATO_1.pdf`, página 112 — la
# cabecera trae el mismo patrón de columna fantasma, pero esta vez la
# fantasma va DESPUÉS de "PRECIO UNITARIO DE REFERENCIA" en vez de antes de
# "CANTIDADES...":
# `['CÓDIGO DEL ELEMENTO', 'Nº MATRÍCULA', 'DESCRIPCIÓN', 'UNIDAD DE MEDIDA',
#   'CANTIDADES ESTIMADAS DE REFERENCIA', None, 'PRECIO UNITARIO DE REFERENCIA']`
# En las filas de datos, el precio real cae en la columna 5 (la fantasma) y
# la 6 (la que "precio_unitario" señala) sale siempre `None`:
# `['P-0014', '619260075', 'DIMDH-G-60-500-...', 'UD.', '0', '259.439,64 €', None]`.
# Mismo mecanismo que `cantidad` arriba, generalizado: la columna fantasma
# puede caer antes O después del campo que la cabecera etiqueta, así que la
# recuperación prueba la anterior primero (el caso ya conocido) y, si no
# encuentra nada recuperable ahí, la siguiente.
def _recuperar_columna_fantasma(
    fila: list[Optional[str]],
    mapeo: dict[str, Optional[int]],
    campo: str,
    parece_recuperable: Callable[[Optional[str]], bool],
) -> Optional[str]:
    """Solo se llama cuando el mapeo normal identificó una columna para
    `campo` (la cabecera SÍ declara ese campo) pero esa columna sale vacía
    en esta fila concreta. Prueba la columna inmediatamente anterior y,
    si no, la siguiente — igual que `_recuperar_descripcion_columna_fantasma`
    prueba solo un lado, pero aquí hace falta cubrir los dos casos reales
    verificados contra el corpus — y solo si ningún otro campo del mapeo ya
    la reclama: así nunca le quita un valor legítimo a otro campo que de
    verdad viva ahí."""
    indice = mapeo.get(campo)
    if indice is None:
        return None
    otros_indices = {i for c, i in mapeo.items() if c != campo}
    for candidato_indice in (indice - 1, indice + 1):
        if candidato_indice < 0 or candidato_indice in otros_indices:
            continue
        candidata = _valor_en(fila, candidato_indice)
        if parece_recuperable(candidata):
            return limpiar_texto_celda(candidata)
    return None


def _recuperar_cantidad_columna_fantasma(
    fila: list[Optional[str]], mapeo: dict[str, Optional[int]]
) -> Optional[str]:
    return _recuperar_columna_fantasma(fila, mapeo, "cantidad", _parece_cantidad_recuperable)


def _recuperar_precio_columna_fantasma(
    fila: list[Optional[str]], mapeo: dict[str, Optional[int]]
) -> Optional[str]:
    return _recuperar_columna_fantasma(fila, mapeo, "precio_unitario", _parece_precio_recuperable)


def _mapeo_desplazado(
    mapeo: dict[str, Optional[int]], offset: int, longitud_fila: int
) -> dict[str, Optional[int]]:
    desplazado: dict[str, Optional[int]] = {}
    for campo, indice in mapeo.items():
        if indice is None:
            desplazado[campo] = None
            continue
        nuevo = indice + offset
        desplazado[campo] = nuevo if 0 <= nuevo < longitud_fila else None
    return desplazado


def _intentar_recuperar_desalineacion(
    fila: list[Optional[str]], mapeo: dict[str, Optional[int]]
) -> Optional[dict]:
    """Solo se llama cuando el mapeo normal deja descripción y precio unitario
    vacíos. Prueba a desplazar el mapeo entero (nunca solo esos dos campos,
    para no mezclar columnas de campos distintos) una posición a cada lado, y
    solo acepta el desplazamiento si recupera a la vez una descripción y un
    precio con pinta real. Nunca se aplica a ciegas ni se guarda como el
    mapeo bueno de la cabecera (`cache_mapeo_cabecera` no se toca): la línea
    recuperada siempre lleva `motivo_revision` para que un humano la
    confirme antes de darla por buena."""
    if mapeo.get("descripcion") is None or mapeo.get("precio_unitario") is None:
        return None  # la cabecera nunca declaró estos campos: no hay nada que desplazar
    for offset in (-1, 1):
        desplazado = _mapeo_desplazado(mapeo, offset, len(fila))
        if not _parece_descripcion_recuperable(_valor_en(fila, desplazado.get("descripcion"))):
            continue
        if not _parece_precio_recuperable(_valor_en(fila, desplazado.get("precio_unitario"))):
            continue
        estado, campos = _construir_campos(fila, desplazado)
        if estado != "ok" or not campos["descripcion"] or campos["precio_unitario"] is None:
            continue
        campos["motivo_revision"] = _acumular_motivo(
            campos["motivo_revision"],
            f"cabecera desalineada con los datos (columnas desplazadas {offset:+d}): "
            "mapeo corregido automáticamente, confirmar antes de dar por buena",
        )
        return campos
    return None


def calcular_clave_linea(codigo_precio, matricula, descripcion, orden_aparicion):
    """Clave no nula para una línea de catálogo dentro de un lote.
    Prioridad: codigo_precio > matricula > hash(descripcion + orden de aparición).
    Los nulos de Postgres no colisionan en un UNIQUE, así que la clave nunca
    puede ser nula si se quiere que el constraint detecte duplicados."""
    if codigo_precio:
        return codigo_precio.strip()
    if matricula:
        return matricula.strip()
    base = f"{descripcion.strip()}|{orden_aparicion}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


# Marcador estable (no una columna de `LineaCatalogo`): `construir_lineas_desde_tabla`
# lo busca en `motivo_revision` para saber que la descripción de esta línea
# se recuperó de una columna fantasma y puede seguir envuelta en las filas
# siguientes del mismo cuadro (ver docstring de esa función).
_MOTIVO_DESCRIPCION_COLUMNA_FANTASMA = (
    "descripción recuperada de la columna siguiente: la cabecera de esta tabla trae una columna "
    "en blanco de más antes de la descripción en este documento, confirmar antes de dar por buena"
)


def _construir_campos(
    fila: list[Optional[str]], mapeo: dict[str, Optional[int]]
) -> tuple[str, Optional[dict]]:
    """Núcleo de la etapa 6, sin el envoltorio de `LineaCatalogo` ni la
    decisión de fila fantasma (ver `construir_linea_catalogo`): aplica un
    mapeo de columnas a una fila cruda. Se factoriza aparte porque
    `_intentar_recuperar_desalineacion` necesita ejecutar esta misma lógica
    con un mapeo desplazado, no solo con el original.

    Devuelve `("pie_de_tabla", None)` cuando la fila es un resumen de tabla
    (CONTEXTO.md sección 2, sesión de rodaje 2026-09-03) y `("ok", campos)` en
    cualquier otro caso — `campos["descripcion"]` puede ser `""` y
    `campos["precio_unitario"]` puede ser `None`, eso lo decide el
    llamador."""

    def _valor(campo: str) -> Optional[str]:
        return _valor_en(fila, mapeo.get(campo))

    matricula_bruta = _valor("matricula")
    codigo_precio, motivo_codigo_precio = _normalizar_codigo_precio(_valor("codigo_precio"))
    matricula = limpiar_codigo_celda(matricula_bruta)
    descripcion = limpiar_texto_celda(_valor("descripcion")) or ""
    unidad_medida = limpiar_texto_celda(_valor("unidad_medida"))

    motivo_revision: Optional[str] = motivo_codigo_precio

    if unidad_medida and _UNIDAD_MEDIDA_IMPLAUSIBLE_RE.match(unidad_medida):
        # Ver docstring de `_UNIDAD_MEDIDA_IMPLAUSIBLE_RE`: esto es solo
        # dígitos y puntos -- una referencia normativa (p.ej.
        # "03.360.571.8") o un valor de otra columna desplazado a esta
        # (p.ej. "956"), nunca una unidad de medida real. La columna que el
        # mapeo cree que es "unidad_medida" no lo es de verdad -- se
        # descarta en vez de guardarse como si fuera una unidad real.
        motivo_revision = _acumular_motivo(
            motivo_revision,
            f"unidad de medida descartada por ser solo numérica, no una unidad real (p.ej. \"ud\", "
            f"\"m\", \"t\"): {unidad_medida!r} — puede ser una referencia normativa o un valor "
            f"desplazado de otra columna, revisar el mapeo de esta cabecera",
        )
        unidad_medida = None

    if matricula is not None and not _MATRICULA_VALIDA_RE.match(matricula):
        clave = normalizar(matricula).replace(" ", "")
        if _es_pie_de_tabla(clave):
            return "pie_de_tabla", None
        if _es_celda_vacia(matricula):
            matricula = None
        elif _es_partida_alzada(clave):
            # La celda de matrícula de esta fila no existe de verdad (una
            # partida alzada no tiene, CONTEXTO.md sección 2): el texto que
            # debía caer en descripción aterrizó aquí porque a esta fila le
            # falta una columna respecto a las demás de la tabla. Se
            # recupera de la celda cruda (`matricula_bruta`), no de
            # `matricula`, que ya perdió los espacios entre palabras al
            # limpiarse como si fuera un código.
            if not descripcion:
                descripcion = limpiar_texto_celda(matricula_bruta) or matricula
            matricula = None
        else:
            motivo_revision = _acumular_motivo(
                motivo_revision, f"valor de matrícula no reconocible, descartado: {matricula!r}"
            )
            matricula = None

    cantidad_bruta = _valor("cantidad")
    cantidad = None
    if cantidad_bruta and not _es_celda_vacia(cantidad_bruta):
        try:
            cantidad = parsear_numero_es(cantidad_bruta)
        except ValueError as exc:
            motivo_revision = _acumular_motivo(motivo_revision, f"cantidad no interpretable: {exc}")
    elif descripcion and mapeo.get("cantidad") is not None:
        # Exige `descripcion` ya resuelta en su columna de siempre (igual que
        # el guard de `precio_unitario` un poco más abajo): si descripción
        # TAMBIÉN está vacía, esto no es un desplazamiento de una sola
        # columna sino de la fila entera, y toca `_intentar_recuperar_desalineacion`
        # más abajo, no este recorte de una sola celda -- sin esta condición,
        # una recuperación coincidente aquí podía "arreglar" cantidad sola y
        # dejar la fila con pinta de resuelta antes de que la desalineación
        # completa llegara a intentarse.
        recuperada = _recuperar_cantidad_columna_fantasma(fila, mapeo)
        if recuperada is not None:
            cantidad = parsear_numero_es(recuperada)
            motivo_revision = _acumular_motivo(
                motivo_revision,
                "cantidad recuperada de una columna fantasma sin etiquetar junto a \"cantidad\" en la "
                "cabecera de esta tabla, confirmar antes de dar por buena",
            )

    if cantidad is not None:
        motivo_cantidad = _cantidad_parece_implausible(cantidad)
        if motivo_cantidad is not None:
            motivo_revision = _acumular_motivo(motivo_revision, motivo_cantidad)

    precio_bruto = _valor("precio_unitario")
    precio_unitario = None
    if precio_bruto and not _es_celda_vacia(precio_bruto):
        try:
            precio_unitario = parsear_importe_es(precio_bruto)
        except ValueError as exc:
            motivo_revision = _acumular_motivo(motivo_revision, f"precio unitario no interpretable: {exc}")
    elif descripcion and mapeo.get("precio_unitario") is not None:
        # Mismo guard que arriba, mismo motivo: sin `descripcion` ya resuelta,
        # esto puede ser una fila con la cabecera entera desplazada, no solo
        # el precio -- se deja para `_intentar_recuperar_desalineacion`, que
        # desplaza el mapeo completo en vez de una sola celda.
        recuperado = _recuperar_precio_columna_fantasma(fila, mapeo)
        if recuperado is not None:
            precio_unitario = parsear_importe_es(recuperado)
            motivo_revision = _acumular_motivo(
                motivo_revision,
                "precio unitario recuperado de una columna fantasma sin etiquetar junto a \"precio "
                "unitario\" en la cabecera de esta tabla, confirmar antes de dar por buena",
            )

    if unidad_medida is None:
        unidad_medida = _extraer_unidad_embebida(cantidad_bruta, precio_bruto)
        if unidad_medida is not None:
            motivo_revision = _acumular_motivo(
                motivo_revision,
                f"unidad de medida ({unidad_medida!r}) recuperada de la propia celda de cantidad o "
                "precio, sin columna propia en la cabecera de esta tabla: confirmar antes de dar por buena",
            )

    # Hallazgo real (sesión de limpieza del Excel al cliente, 2026-09-06,
    # `6.20/28510.0136_ANEJO_3.pdf` p.4, matrículas 740540009/740580020): el
    # guard original exigía `matricula is None` asumiendo que la columna
    # fantasma solo aparece en filas huérfanas (partida alzada). Falso: el
    # mismo desplazamiento de columna ocurre en filas CON matrícula válida —
    # `_recuperar_descripcion_columna_fantasma` no toca la columna de
    # matrícula (ya extraída antes, de su propia columna), así que exigir su
    # ausencia solo dejaba sin recuperar una descripción que sí estaba en el
    # documento. Antes de este arreglo, esas dos filas se guardaban con
    # `descripcion = ""` para siempre: nadie puede identificar el material
    # sin descripción, y ninguna otra copia del mismo material existía en el
    # documento para rellenarla por fusión.
    if not descripcion and precio_unitario is not None:
        # Exige precio_unitario ya interpretado en su columna de siempre: sin
        # esto, una fila de relleno real (fragmento de descripción envuelta
        # entre páginas, sin precio en ninguna posición cercana) se recuperaría
        # como si fuera una fila de datos legítima solo por tener texto en la
        # columna siguiente (`test_construir_linea_catalogo_fragmento_wrap_sin_precio_se_descarta`).
        # El caso real que motiva esta recuperación (partida alzada del
        # contrato, ver docstring de `_recuperar_descripcion_columna_fantasma`)
        # siempre trae su precio bien interpretado; solo la descripción se
        # desplaza.
        recuperada = _recuperar_descripcion_columna_fantasma(fila, mapeo)
        if recuperada:
            descripcion = recuperada
            # Texto reutilizado tal cual por `construir_lineas_desde_tabla`
            # (marcador estable, no una columna de `LineaCatalogo`) para
            # saber que esta línea puede seguir envuelta en las filas
            # siguientes -- ver `_MOTIVO_DESCRIPCION_COLUMNA_FANTASMA`.
            motivo_revision = _acumular_motivo(motivo_revision, _MOTIVO_DESCRIPCION_COLUMNA_FANTASMA)

    return "ok", {
        "codigo_precio": codigo_precio,
        "matricula": matricula,
        "descripcion": descripcion,
        "unidad_medida": unidad_medida,
        "cantidad": cantidad,
        "precio_unitario": precio_unitario,
        "motivo_revision": motivo_revision,
    }


def construir_linea_catalogo(
    fila: list[Optional[str]],
    mapeo: dict[str, Optional[int]],
    pagina: int,
    documento_origen_id: Optional[int],
    expediente_id: int,
    baja_lote: Optional[Decimal],
    orden_aparicion: int,
) -> Optional[dict]:
    """Etapa 6 (normalización + derivación, CONTEXTO.md secciones 4 y 8): una
    fila cruda de tabla + el mapeo de columnas de la etapa 5 -> los campos de
    una `LineaCatalogo`. `precio_adjudicado` se deriva aquí, no se busca en
    ningún documento (CONTEXTO.md sección 4: "no existe una tabla de precios
    adjudicados").

    `expediente_id` viaja en la línea desde este punto (encargo de esta
    sesión, punto 3): una línea cuya tabla de origen no se pudo asociar a un
    único lote sin ambigüedad se guarda igualmente, con `lote_id=None` —
    huérfana pero trazable hasta su expediente.

    Devuelve `None` cuando la fila es un pie de tabla (CONTEXTO.md sección 2,
    sesión de rodaje 2026-09-03): no es una línea de material, es un resumen
    ("PRESUPUESTO DE LICITACIÓN", "IVA", "TOTAL CON IVA") que el mapeo de
    cabecera no distingue de una fila de datos. Nunca lanza por un valor de
    `cantidad`/`precio_unitario` ilegible (identificadores de glifo sin
    decodificar, celdas con el valor duplicado que no coinciden entre sí):
    ese campo queda en `None` y la línea lleva `motivo_revision` explicando
    por qué, en vez de tirar la tabla entera por una fila.

    También devuelve `None` cuando la fila sale sin descripción y sin precio
    unitario (sesión de filas fantasma, 2026-09-04): filas de separación o
    relleno del cuadro de precios (pies de tabla sin etiqueta reconocible,
    fragmentos de una descripción envuelta entre páginas, matrículas
    huérfanas) que el mapeo de cabecera toma por una fila de datos. Antes de
    descartarla se prueba `_intentar_recuperar_desalineacion`: si el
    `fragmento` sí trae una descripción y un precio reales, solo
    desplazados de columna respecto al mapeo, la línea se conserva con
    `motivo_revision` en vez de perderse — no toda fila vacía es relleno."""
    estado, campos = _construir_campos(fila, mapeo)
    if estado == "pie_de_tabla":
        return None

    if (
        campos["descripcion"]
        and campos["codigo_precio"] is None
        and campos["matricula"] is None
        and campos["cantidad"] is None
        and campos["precio_unitario"] is None
        and campos["unidad_medida"] is None
    ):
        # Fila fantasma de desbordamiento de descripción (arreglo de
        # 6.23/28510.0051, sesión 2026-09-06): en tablas donde la primera
        # línea de una descripción envuelta cae en la banda visual de la
        # fila ANTERIOR (desfase de una línea entre la columna de
        # descripción y el resto -- ver `docs/excel-cliente-correccion.md`
        # bloque 4 para el caso real completo), `pdfplumber` extrae ese
        # fragmento en su propia fila, con todas las demás columnas en
        # blanco. No es una línea de material nueva -- el material real,
        # con su código, su unidad y su precio, ya se cuenta en la fila
        # vecina (la fusión que `_dividir_fila_multiple` puede tener que
        # deshacer, o una fila normal que arrastra el fragmento en su
        # propia celda de descripción) -- así que se descarta aquí, igual
        # que un pie de tabla o una fila de relleno (más abajo en esta
        # misma función). Sin este descarte quedaba como un material
        # fantasma con la baja del lote heredada pero sin ningún precio que
        # derivar: indistinguible en el catálogo de una línea genuinamente
        # pendiente de revisión.
        return None

    if not campos["descripcion"] and campos["precio_unitario"] is None:
        recuperados = _intentar_recuperar_desalineacion(fila, mapeo)
        if recuperados is None:
            return None
        campos = recuperados

    precio_unitario = campos["precio_unitario"]
    precio_adjudicado = None
    if precio_unitario is not None and baja_lote is not None:
        precio_adjudicado = precio_unitario * (Decimal("1") - baja_lote)

    descripcion = campos["descripcion"]
    matricula = campos["matricula"]
    if not descripcion and matricula is None:
        # Último recurso antes de dar la fila por ilegible del todo (ver
        # docstring de `_recuperar_descripcion_ultimo_recurso`): una partida
        # alzada real cuyo único texto cayó en una columna que el mapeo no
        # reclama para nada -- se recupera como descripción en vez de
        # perderse, siempre marcada para confirmar contra el documento.
        recuperada = _recuperar_descripcion_ultimo_recurso(fila, mapeo)
        if recuperada:
            descripcion = recuperada
            campos["motivo_revision"] = _acumular_motivo(
                campos["motivo_revision"],
                "descripción recuperada de una columna sin asignar en el mapeo de esta cabecera "
                "(probable partida alzada con columnas intermedias ausentes en esta fila), "
                "confirmar antes de dar por buena",
            )
        else:
            # Encargo de esta sesión (limpieza del Excel al cliente,
            # 2026-09-06): sin descripción NI matrícula, ninguna otra columna
            # identifica qué material es esta fila -- no es una línea de
            # catálogo utilizable, aunque traiga un precio real (llegar aquí
            # ya implica precio_unitario presente: el guard de arriba
            # descarta como relleno cualquier fila sin descripción que
            # TAMPOCO traiga precio). Con contenido real en el fragmento de
            # origen (el precio, un código de precio, una cantidad) se
            # conserva para revisión humana en vez de perderse en silencio;
            # una fila genuinamente en blanco se descarta como cualquier otro
            # relleno de tabla.
            fragmento_bruto = " | ".join((celda or "").strip() for celda in fila)
            if not fragmento_bruto.replace("|", "").strip():
                return None
            campos["motivo_revision"] = _acumular_motivo(
                campos["motivo_revision"],
                "línea sin descripción ni matrícula: ningún dato de la fila identifica qué material es, "
                "confirmar contra el documento de origen",
            )

    return {
        "clave_linea": calcular_clave_linea(
            campos["codigo_precio"], campos["matricula"], descripcion, orden_aparicion
        ),
        "expediente_id": expediente_id,
        "orden_aparicion": orden_aparicion,
        "codigo_precio": campos["codigo_precio"],
        "matricula": campos["matricula"],
        "descripcion": descripcion,
        "codigo_material": derivar_codigo_material(descripcion),
        "unidad_medida": campos["unidad_medida"],
        "cantidad": campos["cantidad"],
        "precio_unitario": precio_unitario,
        "baja_lote": baja_lote,
        "precio_adjudicado": precio_adjudicado,
        "documento_origen_id": documento_origen_id,
        "pagina": pagina,
        "fragmento": " | ".join((celda or "").strip() for celda in fila),
        "motivo_revision": campos["motivo_revision"],
    }


def _es_fragmento_continuacion_pura(fila: list[Optional[str]], mapeo: dict[str, Optional[int]], indice_fragmento: int) -> bool:
    """Una fila de continuación de descripción envuelta (sesión de limpieza
    del Excel al cliente, 2026-09-06) no trae ningún otro dato real -- solo
    el siguiente trozo de frase en `indice_fragmento`, con el resto de
    columnas mapeadas vacías. Si cualquier otro campo mapeado trae un valor,
    esto no es continuación: es la siguiente fila de datos real (o un dato
    legítimo de otra columna), y no se debe absorber."""
    for campo, indice in mapeo.items():
        if indice is None or indice == indice_fragmento:
            continue
        valor = _valor_en(fila, indice)
        if valor and not _es_celda_vacia(valor):
            return False
    return _parece_descripcion_recuperable(_valor_en(fila, indice_fragmento))


# Sesión de verificación del Excel exportado (2026-09-08, 38 líneas sin
# descripción): imagen especular de `_MOTIVO_DESCRIPCION_COLUMNA_FANTASMA` de
# arriba. Ahí la descripción de una fila real se desborda hacia las filas
# SIGUIENTES; aquí es el PRECIO el que llega tarde -- la banda visual de la
# columna de precio de esta tabla queda desplazada una fila hacia abajo
# respecto a matrícula/descripción (verificado contra el documento real,
# `6.19/28510.0194_ANEJO_1.pdf` p.9 y `6.20/28510.0029_ANEJO_1.pdf` p.4: la
# fila con matrícula y descripción sale con su propia celda de precio vacía,
# y el precio real aparece solo, sin ningún otro dato, en la fila
# inmediatamente siguiente). Sin este arreglo, `construir_linea_catalogo`
# guardaba DOS líneas por cada una real: la línea con matrícula/descripción
# pero sin precio (silenciosa, sin motivo_revision, indistinguible de un
# precio genuinamente no publicado) y una segunda línea fantasma con solo el
# precio, sin descripción ni matrícula -- exactamente la fila "sin
# expediente, ni matrícula, ni descripción, solo un precio" que aparecía en
# el Excel entregado al cliente. `_recuperar_precio_columna_fantasma`
# (arriba) no cubre este caso porque no es una columna fantasma DENTRO de la
# misma fila -- es una fila entera de más, y probar la celda vecina ahí
# puede recuperar por error un valor plausible pero equivocado (verificado:
# en `6.20/28510.0029` recuperaba la cantidad "1" de "PEDIDO INICIAL" como si
# fuera el precio).
_MOTIVO_PRECIO_FILA_SIGUIENTE = (
    "precio unitario recuperado de la fila siguiente: la banda de precio de esta tabla queda "
    "desplazada una fila respecto a la matrícula/descripción, confirmar contra el documento de origen"
)


def _es_fila_precio_continuacion(fila: list[Optional[str]], mapeo: dict[str, Optional[int]]) -> bool:
    """Verdadero cuando `fila` no trae más dato real que un precio unitario
    con pinta válida -- mismo patrón que `_es_fragmento_continuacion_pura`,
    aplicado a la columna de precio en vez de a la de descripción. Nunca se
    llama si la propia fila de origen ya trae su precio: ver
    `construir_lineas_desde_tabla`."""
    indice_precio = mapeo.get("precio_unitario")
    if indice_precio is None:
        return False
    for campo, indice in mapeo.items():
        if indice is None or indice == indice_precio:
            continue
        valor = _valor_en(fila, indice)
        if valor and not _es_celda_vacia(valor):
            return False
    return _parece_precio_recuperable(_valor_en(fila, indice_precio))


# Marcador estable, mismo patrón que `_MOTIVO_DESCRIPCION_COLUMNA_FANTASMA`:
# `_dividir_fila_multiple` lo añade a cada línea recuperada de una fila
# fusionada -- la descripción de esas líneas puede traer texto de la línea
# vecina (nunca se reparte, ver docstring de esa función), así que un
# humano debe confirmarla antes de darla por buena aunque el precio ya sea
# correcto y derivable.
_MOTIVO_FILA_FUSIONADA = (
    "línea recuperada de una fila que fusionaba varias líneas de precio en una sola celda del "
    "documento (código y precio unitario con más de un valor); la descripción puede incluir texto "
    "de la línea vecina, confirmar contra el documento original"
)


def _dividir_fila_multiple(
    fila: list[Optional[str]], mapeo: dict[str, Optional[int]]
) -> Optional[tuple[list[list[Optional[str]]], bool]]:
    """Arreglo de 6.23/28510.0051 (sesión 2026-09-06): en tablas donde el
    desfase de una línea entre la columna de descripción y el resto (ver
    la fila fantasma que descarta `construir_linea_catalogo`) hace que dos
    filas de datos reales y consecutivas no difieran lo bastante en altura,
    `pdfplumber` las funde en una sola fila extraída -- el código de precio
    y el precio unitario de esa fila fusionada traen entonces dos valores
    reales, uno por línea de texto dentro de la misma celda
    (`"P-0090\\nP-0091"`, `"29.240,23 €\\n38.012,29 €"`), en vez de uno solo.

    Solo se activa cuando el código de precio Y el precio unitario --las
    dos columnas que de verdad identifican y valoran una línea-- se dividen
    en el MISMO número N>=2 de líneas nunca vacías, y cada una por separado
    ya tiene forma de código/precio válido (nunca a ciegas: dos valores que
    no casen como códigos o precios reales no dividen la fila, se dejan
    para que el camino normal los mande a revisión como hasta ahora). La
    unidad de medida, si la cabecera la declara, debe dividirse también en
    N o venir vacía en las dos.

    La descripción solo se reparte 1:1 cuando TAMBIÉN se divide en
    exactamente N líneas no vacías (verificado con el duplicado real de
    6.23/28510.0051, sesión de auditoría 2026-09-08: P-0058/P-0059,
    "CAM1H-60-1500-TC-D\\nCAM1H-60-1500-TC-I", dos piezas D/I completas al
    mismo precio -- el mismo patrón que P-0056/P-0057 dos filas más arriba,
    sin fusionar, con precio igualmente idéntico -- confirmado contra el PDF
    real, `pdfplumber` funde dos filas SIMPLES consecutivas, no una
    descripción envuelta). Cuando el número de líneas de descripción no
    coincide con N (el caso que motivó no repartir nunca, en la sesión
    original: una de las N filas fusionadas traía a su vez una descripción
    envuelta en más de una línea, así que el recuento por sí solo no basta
    para emparejarlas 1:1 con garantía), se mantiene el comportamiento
    anterior -- cada fila resultante se queda con el mismo bloque de
    descripción completo tal cual, y `construir_lineas_desde_tabla` marca
    cada una con `_MOTIVO_FILA_FUSIONADA` para que un humano la confirme.

    Devuelve `None` cuando no aplica (la fila sigue su camino normal, de una
    sola línea por campo), o una tupla `(filas_divididas, descripcion_dividida)`
    -- el segundo valor le dice a la persona que llama si hace falta marcar
    la línea para revisión (`False`) o si el reparto de descripción ya quedó
    verificado sin ambigüedad (`True`)."""
    indice_codigo = mapeo.get("codigo_precio")
    indice_precio = mapeo.get("precio_unitario")
    if indice_codigo is None or indice_precio is None:
        return None

    def _lineas_no_vacias(indice: Optional[int]) -> list[str]:
        valor = _valor_en(fila, indice)
        if not valor:
            return []
        return [linea.strip() for linea in valor.splitlines() if linea.strip()]

    codigos = _lineas_no_vacias(indice_codigo)
    precios = _lineas_no_vacias(indice_precio)
    n = len(codigos)
    if n < 2 or len(precios) != n:
        return None
    if not all(_CODIGO_PRECIO_VALIDO_RE.match(limpiar_codigo_celda(c) or "") for c in codigos):
        return None
    if not all(_parece_precio_recuperable(p) for p in precios):
        return None

    indice_unidad = mapeo.get("unidad_medida")
    unidades = _lineas_no_vacias(indice_unidad) if indice_unidad is not None else []
    if unidades and len(unidades) != n:
        return None

    indice_descripcion = mapeo.get("descripcion")
    descripciones = _lineas_no_vacias(indice_descripcion) if indice_descripcion is not None else []
    descripcion_dividida = len(descripciones) == n

    filas_divididas = []
    for i in range(n):
        nueva_fila = list(fila)
        nueva_fila[indice_codigo] = codigos[i]
        nueva_fila[indice_precio] = precios[i]
        if unidades:
            nueva_fila[indice_unidad] = unidades[i]
        if descripcion_dividida:
            nueva_fila[indice_descripcion] = descripciones[i]
        filas_divididas.append(nueva_fila)
    return filas_divididas, descripcion_dividida


def construir_lineas_desde_tabla(
    tabla: TablaExtraida,
    mapeo: dict[str, Optional[int]],
    documento_origen_id: Optional[int],
    expediente_id: int,
    baja_lote: Optional[Decimal],
    orden_inicial: int,
) -> list[dict]:
    # Una fila de pie de tabla (CONTEXTO.md sección 2, sesión de rodaje
    # 2026-09-03) devuelve None de `construir_linea_catalogo`: se descarta
    # aquí, nunca llega a `guardar_lineas_catalogo`.
    filas = tabla.filas
    resultado: list[dict] = []
    # Filas ya absorbidas como el precio de la fila anterior (ver más abajo,
    # `_es_fila_precio_continuacion`): no se procesan una segunda vez como si
    # fueran su propia línea.
    saltadas: set[int] = set()
    for indice, fila in enumerate(filas):
        if indice in saltadas:
            continue
        # `_dividir_fila_multiple` (arreglo de 6.23/28510.0051, sesión
        # 2026-09-06): una fila que fusiona varias líneas de precio en una
        # sola celda del documento se reparte aquí en varias líneas de
        # catálogo reales, cada una marcada para revisión -- la descripción
        # puede traer texto de la línea vecina, nunca se reparte. Una fila
        # fusionada no participa en la absorción de fragmentos de más abajo
        # (esa lógica es para una fila normal, de una sola línea real).
        resultado_division = _dividir_fila_multiple(fila, mapeo)
        if resultado_division is not None:
            sub_filas, descripcion_dividida = resultado_division
            for sub_fila in sub_filas:
                linea = construir_linea_catalogo(
                    sub_fila, mapeo, tabla.pagina, documento_origen_id, expediente_id, baja_lote,
                    orden_inicial + len(resultado),
                )
                if linea is None:
                    continue
                if not descripcion_dividida:
                    linea["motivo_revision"] = _acumular_motivo(linea["motivo_revision"], _MOTIVO_FILA_FUSIONADA)
                resultado.append(linea)
            continue

        # Precio desplazado a la fila siguiente (ver docstring de
        # `_MOTIVO_PRECIO_FILA_SIGUIENTE`): se recupera ANTES de construir la
        # línea, parcheando una copia de la fila, para que
        # `_recuperar_precio_columna_fantasma` (dentro de `_construir_campos`)
        # nunca llegue a disparar sobre una celda de precio que en realidad no
        # está vacía por desplazamiento de columna, sino por desplazamiento de
        # fila entera -- confundir los dos casos recuperaba un valor vecino
        # plausible pero equivocado (verificado, `6.20/28510.0029` recuperaba
        # la cantidad "1" de "PEDIDO INICIAL" como si fuera el precio).
        indice_precio = mapeo.get("precio_unitario")
        precio_de_fila_siguiente: Optional[str] = None
        valor_precio_propio = _valor_en(fila, indice_precio) if indice_precio is not None else None
        if indice_precio is not None and (not valor_precio_propio or _es_celda_vacia(valor_precio_propio)):
            siguiente_precio = indice + 1
            if siguiente_precio < len(filas) and _es_fila_precio_continuacion(filas[siguiente_precio], mapeo):
                precio_de_fila_siguiente = _valor_en(filas[siguiente_precio], indice_precio)
                fila = list(fila)
                fila[indice_precio] = precio_de_fila_siguiente

        linea = construir_linea_catalogo(
            fila, mapeo, tabla.pagina, documento_origen_id, expediente_id, baja_lote, orden_inicial + len(resultado)
        )
        if linea is None:
            continue
        if precio_de_fila_siguiente is not None:
            saltadas.add(siguiente_precio)
            linea["motivo_revision"] = _acumular_motivo(linea["motivo_revision"], _MOTIVO_PRECIO_FILA_SIGUIENTE)
            linea["fragmento"] += " | " + precio_de_fila_siguiente.strip()
        motivo = linea.get("motivo_revision") or ""
        indice_descripcion = mapeo.get("descripcion")
        if _MOTIVO_DESCRIPCION_COLUMNA_FANTASMA in motivo and indice_descripcion is not None:
            # La descripción recuperada de una columna fantasma (más arriba
            # en `_construir_campos`) puede seguir envuelta en las filas
            # siguientes -- mismo fenómeno que `_combinar_filas_cabecera` ya
            # resuelve para la cabecera, aquí aplicado a filas de datos.
            # Hallazgo real, `6.20/28510.0136_ANEJO_3.pdf` p.4: la
            # descripción de "HILO DE CONTACTO..." sigue en hasta 5 filas de
            # continuación tras la fila con matrícula y precio.
            indice_fragmento = indice_descripcion + 1
            siguiente = indice + 1
            while siguiente < len(filas) and _es_fragmento_continuacion_pura(filas[siguiente], mapeo, indice_fragmento):
                fragmento = limpiar_texto_celda(_valor_en(filas[siguiente], indice_fragmento))
                if fragmento:
                    linea["descripcion"] = f"{linea['descripcion']} {fragmento}".strip()
                    linea["fragmento"] += " | " + fragmento
                siguiente += 1
        resultado.append(linea)
    return resultado


@dataclass(frozen=True)
class ResultadoGuardadoCatalogo:
    creadas: int
    actualizadas: int


def _firma_material(datos: dict) -> Optional[tuple]:
    """Firma de "misma pieza física" para detectar una línea real repetida
    en dos tablas del mismo documento con distinta completitud de columnas
    (defecto de duplicados de la auditoría 2026-09-05, ver
    docs/correccion-defectos-auditoria.md): una segunda tabla de
    características técnicas puede repetir el material con su mismo precio
    pero sin columna de `codigo_precio` propia — verificado contra el corpus
    real, `6.23/28510.0018` lote 1, matrícula `601020180`, mismo precio
    58,43 € en páginas 12 (con `codigo_precio="P-02"`) y 16 (sin código).
    `calcular_clave_linea` les asigna claves distintas (codigo_precio vs.
    matrícula) precisamente porque prioriza codigo_precio cuando existe, así
    que ninguna fusión por clave exacta las ve nunca como la misma fila sin
    esta firma aparte.

    Con matrícula, descripción y precio unitario presentes, el triplete
    identifica la misma pieza física con o sin código de precio, sea cual
    sea el documento de origen. Sin matrícula, se cae a (descripción,
    precio) igual — hallazgo real, sesión de limpieza del Excel al cliente
    2026-09-06: una tabla de "impacto del fallo del elemento en la
    seguridad operacional" o de normativa aplicable (`6.24/28510.0180`,
    `6.23/28510.0042`, `6.23/28510.0051`) repite el mismo material con su
    mismo precio bajo un `codigo_precio` DISTINTO de numeración propia, sin
    matrícula ninguna de las dos veces — igual que una "PARTIDA ALZADA A
    JUSTIFICAR PARA IMPREVISTOS" (nunca lleva matrícula, CONTEXTO.md sección
    2) puede repetirse como cabecera de sección en varias páginas del mismo
    cuadro de precios. `_combinar_por_clave` y `guardar_lineas_catalogo`
    solo llaman a esta función dentro de un lote ya resuelto
    (`permitir_fusion_material`/`fusion_material`, nunca en huérfanas): dos
    materiales genéricos que coincidan en descripción y precio POR
    CASUALIDAD en LOTES o EXPEDIENTES distintos nunca se ven aquí, porque el
    filtro de lote/expediente ya los separa antes de llegar a esta firma —
    el riesgo real de "casualidad" que motivaba excluir del todo el caso sin
    matrícula queda acotado a dentro del propio lote, donde no se ha
    verificado ningún caso real en el corpus. El llamador marca
    `motivo_revision` cuando la fusión ocurre sin matrícula (señal más
    débil que con ella), para que quede confirmable.

    Una línea recuperada de una fila fusionada CUYA DESCRIPCIÓN QUEDÓ
    AMBIGUA (`_MOTIVO_FILA_FUSIONADA`, `_dividir_fila_multiple` con
    `descripcion_dividida=False`) no tiene firma: su descripción es el bloque
    entero de la fila del documento, el MISMO para las N líneas que salen de
    ella porque ahí nunca se reparte a ciegas. Sin este descarte, dos
    materiales reales y distintos de una misma fila fusionada que además
    coincidan en precio (caso real `6.23/28510.0051`, P-0058 y P-0059,
    306.351,49 € los dos) comparten firma exacta —matrícula nula,
    descripción idéntica, mismo precio— y `_combinar_por_clave` los funde en
    una sola línea: uno de los dos códigos desaparece del catálogo, y el que
    queda hereda la clave del otro. Es justo el fallo que este arreglo venía
    a corregir, disimulado un paso más allá. La descripción compartida no es
    una identidad válida para estas líneas, así que no participan en la
    fusión por firma: cada una se guarda con su propio `codigo_precio` como
    clave, marcada para revisión. Si alguna de ellas resultara ser de verdad
    un duplicado de otra tabla, quedará como línea repetida a revisar —
    verificable por un humano, y muy preferible a perder un material real
    sin dejar rastro."""
    if _MOTIVO_FILA_FUSIONADA in (datos.get("motivo_revision") or ""):
        return None
    matricula = datos.get("matricula")
    descripcion = datos.get("descripcion")
    precio_unitario = datos.get("precio_unitario")
    if not descripcion or precio_unitario is None:
        return None
    return (matricula, descripcion, precio_unitario)


def buscar_posible_duplicado_huerfana(db: Session, linea: LineaCatalogo) -> Optional[tuple[LineaCatalogo, Lote]]:
    """Bloque 4, sesión de huérfanos de banda vacía (2026-09-07): señal
    INFORMATIVA para la cola de revisión, nunca una decisión automática.

    Se probó primero descartar en silencio la huérfana cuando coincidía en
    firma con una línea ya resuelta (mismo mecanismo, un `continue` en vez de
    un `return`) — revertido antes de llegar a esta sesión: el caso de
    aceptación real `6.25/28510.0027` ("Suministro de balasto, 6 LOTES")
    demuestra que un precio de referencia puede coincidir legítimamente entre
    LOTES DISTINTOS de la misma licitación ("P-1 Balasto sobre camión en
    cantera" cuesta 10,85 € en los seis lotes por igual — precio fijo,
    independiente de dónde se ejecute — mientras "P-2 T de balasto
    transportado..." varía lote a lote, coste real de transporte) sin ser la
    misma fila repetida. Descartar por firma habría perdido en silencio
    líneas reales de otros lotes. "Huérfana de banda vacía" solo existe en
    expedientes multi-lote por construcción (`app.extraccion.lote_tabla`), así
    que ese riesgo cubre el 100% del dominio donde esto se aplicaría — de ahí
    que la decisión final del cliente sea mostrar la coincidencia, nunca
    actuar por su cuenta (mismo principio que CONTEXTO.md sección 12, "un
    contraste externo puede señalar un desajuste, pero no tiene autoridad
    para cambiar el estado").

    Solo se calcula para huérfanas (`linea.lote_id is None`, comprobado aquí
    por si el llamador no lo hizo); usa la misma firma que
    `_combinar_por_clave`/`guardar_lineas_catalogo` (matrícula+descripción+
    precio, o descripción+precio sin matrícula) para no introducir un
    segundo criterio de "misma pieza" que pueda divergir del ya usado para
    fusionar de verdad dentro de un lote."""
    if linea.lote_id is not None:
        return None
    firma = _firma_material(
        {
            "matricula": linea.matricula,
            "descripcion": linea.descripcion,
            "precio_unitario": linea.precio_unitario,
            "motivo_revision": linea.motivo_revision,
        }
    )
    if firma is None:
        return None
    matricula, descripcion, precio_unitario = firma
    return (
        db.query(LineaCatalogo, Lote)
        .join(Lote, LineaCatalogo.lote_id == Lote.id)
        .filter(
            LineaCatalogo.expediente_id == linea.expediente_id,
            LineaCatalogo.matricula == matricula,
            LineaCatalogo.descripcion == descripcion,
            LineaCatalogo.precio_unitario == precio_unitario,
        )
        .first()
    )


_MOTIVO_FUSION_SIN_MATRICULA = (
    "fila fundida con otra de igual descripción y precio unitario, sin matrícula ni código de "
    "precio que las distinga como la misma línea con certeza: confirmar que es el mismo material"
)


def _combinar_por_clave(lineas: list[dict], permitir_fusion_material: bool = True) -> list[dict]:
    """El mismo cuadro de precios puede reaparecer varias veces dentro de un
    único documento (CONTEXTO.md sección 3 y docstring de `guardar_lineas_catalogo`),
    así que `lineas` puede traer la misma `clave_linea` repetida antes de tocar
    la base de datos. Doblarlas aquí, en Python, con la misma regla de fusión
    que ya aplica `guardar_lineas_catalogo` fila a fila (un valor `None` nunca
    pisa uno ya conocido) — no depender de que la sesión autoflushee entre
    iteraciones, que `SessionLocal` (app/db.py) desactiva a propósito.

    `permitir_fusion_material=False` desactiva además la fusión por
    `_firma_material` (mismo triplete matrícula+descripción+precio bajo
    `clave_linea` distinta): `guardar_lineas_catalogo` lo hace para las
    líneas huérfanas (`lote_id is None`), porque ahí `clave_linea` ya lleva
    un sufijo de página a propósito (`app.extraccion.pipeline_anejo`) para
    no fundir tablas ambiguas de lotes distintos que comparten
    `codigo_precio` — fusionar también por matrícula ahí arriesgaría
    confundir el mismo material ofertado en dos lotes distintos con una
    única fila.

    La clave canónica de cada firma prefiere siempre la que trae
    `codigo_precio`, sin importar en qué orden aparecen las tablas
    (`6.24/28510.0116`: la tabla sin código está en la página 18, la que sí
    lo trae en la 22 — si se quedara con "la primera vista" a secas, la
    fila fundida heredaría la clave de matrícula pese a conocerse ya el
    código)."""
    clave_por_firma: dict[tuple, tuple[str, bool]] = {}
    if permitir_fusion_material:
        for datos in lineas:
            firma = _firma_material(datos)
            if firma is None:
                continue
            tiene_codigo = bool(datos.get("codigo_precio"))
            actual = clave_por_firma.get(firma)
            if actual is None or (tiene_codigo and not actual[1]):
                clave_por_firma[firma] = (datos["clave_linea"], tiene_codigo)

    combinadas: dict[str, dict] = {}
    for datos in lineas:
        firma = _firma_material(datos) if permitir_fusion_material else None
        clave = clave_por_firma[firma][0] if firma is not None else datos["clave_linea"]
        existente = combinadas.get(clave)
        if existente is None:
            nuevo = dict(datos)
            nuevo["clave_linea"] = clave
            combinadas[clave] = nuevo
        else:
            if firma is not None and firma[0] is None:
                existente["motivo_revision"] = _acumular_motivo_unico(
                    existente.get("motivo_revision"), _MOTIVO_FUSION_SIN_MATRICULA
                )
            for campo, valor in datos.items():
                if valor is not None:
                    existente[campo] = valor
            existente["clave_linea"] = clave
    return list(combinadas.values())


def _limpiar_huerfana_superada(db: Session, expediente_id: int, clave_huerfana_hipotetica: Optional[str]) -> None:
    """Ver docstring de `guardar_lineas_catalogo`. Solo se llama cuando la
    línea se acaba de guardar bajo un `lote_id` real (nunca para huérfanas:
    no tendría de qué "superarse"). Comparación exacta de `clave_linea`
    -- `app.extraccion.pipeline_anejo` calcula `clave_huerfana_hipotetica`
    con el mismo sufijo de página+franja vertical que la línea llevaría si
    fuese huérfana, así que dos tablas distintas de la misma página con
    contenido coincidente (mismo precio de referencia en dos lotes, caso
    real del balasto) nunca comparten esta clave, aunque compartan
    descripción y precio."""
    if clave_huerfana_hipotetica is None:
        return
    huerfana = (
        db.query(LineaCatalogo)
        .filter_by(expediente_id=expediente_id, lote_id=None, clave_linea=clave_huerfana_hipotetica)
        .one_or_none()
    )
    if huerfana is not None:
        db.delete(huerfana)


def guardar_lineas_catalogo(
    db: Session, lote_id: Optional[int], lineas: list[dict]
) -> ResultadoGuardadoCatalogo:
    """Escritura por clave, no añadido ciego (CONTEXTO.md sección 9.9): una
    línea ya vista para este lote se actualiza, nunca se duplica. La
    actualización solo pisa los campos que la nueva extracción sí trae
    (`None` no borra un valor ya conocido) — necesario porque el mismo
    cuadro de precios puede reaparecer en el documento con menos columnas
    (p.ej. una tabla de "criterios técnicos" que repite código, descripción
    y precio pero no trae cantidad): la segunda pasada no debe borrar la
    cantidad que sí trajo la primera.

    No hace `commit()`: el llamador decide cuándo (CONTEXTO.md, sesión de
    rodaje 2026-09-03, punto 3 — antes cada llamada confirmaba por su cuenta,
    así que un documento con varios lotes podía dejar committed las líneas
    de un grupo y fallar en el siguiente, dejando el catálogo con restos de
    un expediente marcado como fallido). `ejecutar_extraccion_expediente`
    hace un único `commit()` por documento tras guardar todos sus grupos: o
    se guarda entero, o el `rollback()` del `except` lo deshace entero.

    `lote_id=None` es el caso huérfano (CONTEXTO.md, encargo de esta sesión,
    punto 3): una tabla cuyo lote no se pudo determinar sin ambigüedad. El
    filtro de existencia siempre incluye `expediente_id` además de
    `lote_id`, aunque `lote_id` ya identifique el lote cuando no es None —
    sin él, dos huérfanas del mismo `codigo_precio` ("P-001", frecuente
    entre expedientes distintos) en dos expedientes distintos colisionarían
    entre sí, porque Postgres no deduplica `NULL` en la constraint UNIQUE de
    `lote_id`: aquí la idempotencia de las huérfanas la garantiza este
    filtro explícito, no la constraint de base de datos.

    Cuando `lote_id` no es huérfano, la búsqueda de la línea existente cae
    además a `_firma_material` (defecto de duplicados de la auditoría
    2026-09-05, docs/hallazgos-extraccion.md sección 30.2): la segunda tabla
    que repite un material sin `codigo_precio` propio puede vivir en OTRO
    documento del mismo expediente (`6.23/28510.0102` y `6.25/28510.0016`:
    la tabla con código está en `ANEJO_1`, la que repite sin código está en
    `ANEJO_3` — dos llamadas a esta función completamente distintas, así
    que `_combinar_por_clave` en memoria nunca las ve juntas), o incluso
    puede llevar YA guardada como dos filas sueltas de una sesión anterior
    a este arreglo (`6.24/28510.0116`, lote 25, "P-01" — ver la fila
    `duplicado_por_firma` de abajo). La búsqueda por firma se hace SIEMPRE
    que hay firma, no solo cuando la búsqueda exacta falla: el orden en que
    `_combinar_por_clave` ve las tablas del documento no está garantizado
    (una puede procesarse antes que otra), así que la clave exacta podía
    encontrar cualquiera de las dos filas heredadas — absorber la otra pase
    lo que pase es lo único que no depende de ese orden. Nunca se hace para
    huérfanas, por la misma razón que `_combinar_por_clave` tampoco fusiona
    por firma ahí.

    **Huérfanas "copia exacta de una línea ya resuelta", bloque 4 de la
    sesión de huérfanos de banda vacía (2026-09-07): investigado, NO
    implementado a propósito.** Un primer intento fundía (descartaba) una
    huérfana cuando su firma de material (`_firma_material`) coincidía con
    una línea ya resuelta del mismo expediente, en cualquier lote. Contra el
    corpus real medía 186 casos así — pero verificar el caso de aceptación
    multi-lote (`tests/extraccion/test_orquestador.py::
    test_expediente_0027_multi_lote_produce_baja_correcta_por_lote`, 6.25/
    28510.0027) destapó que la coincidencia de firma NO implica "misma fila
    repetida": en una licitación de balasto a 6 lotes, "P-1 Balasto sobre
    camión en cantera" cuesta 10,85 € EN LOS SEIS LOTES por igual (precio de
    referencia fijo, independiente del lote), mientras "P-2 T de balasto
    transportado..." varía lote a lote (coste de transporte, sí depende de
    la geografía) — el propio documento real de prueba. Fundir por firma
    habría descartado en silencio líneas reales y distintas de otros lotes
    solo porque coinciden en precio con la del lote ya resuelto. Los dos
    expedientes reales que aportaban los 186 casos (`6.25/28510.0019`, 9
    lotes; `6.24/28510.0203`, 6 lotes) son ambos multi-lote — exactamente el
    contexto donde este riesgo aplica, y "huérfana de banda vacía" solo
    existe en expedientes multi-lote por construcción (`app.extraccion.
    lote_tabla` no tiene ambigüedad de lote que resolver con uno solo). Sin
    una señal que distinga "de verdad la misma fila repetida" de "coincidencia
    de precio de referencia entre lotes", este descarte automático es
    inseguro en todo su dominio de aplicación — no se implementa. Ver el
    informe de la sesión para el detalle completo y la propuesta pendiente de
    aprobación del cliente.

    **Huérfana superada por herencia de lote: se limpia aquí (sesión de
    herencia de lote entre páginas de continuación, 2026-09-08).**
    `app.extraccion.pipeline_anejo` añade un sufijo de página/franja vertical
    a `clave_linea` únicamente cuando la línea es huérfana (`identificador_lote
    is None`, docstring de ese módulo) — necesario para no confundir dos
    tablas ambiguas de la misma página que repiten el mismo código. Cuando
    una línea que antes era huérfana pasa a resolverse a un lote real (una
    cabecera que antes no se leía bien, o -desde esta sesión- una herencia
    de la tabla anterior), su clave cambia de "P-001@p15y657" a "P-001" sin
    más — la búsqueda por clave exacta de este bucle nunca encuentra la fila
    huérfana vieja para actualizarla, así que queda duplicada para siempre
    (hallazgo real al reprocesar: 2.152 filas así en los primeros
    expedientes verificados). `_limpiar_huerfana_superada` la busca por
    `clave_huerfana_hipotetica` (que `pipeline_anejo` calcula para TODA línea,
    resuelva o no, con el mismo sufijo de página+franja vertical que tendría
    si fuera huérfana) y la borra si existe — comparación EXACTA de clave,
    nunca por contenido (descripción/precio): un precio de referencia puede
    repetirse igual entre tablas de lotes DISTINTOS de la misma página
    (hallazgo real, `6.25/28510.0027`, "P-1 Balasto..." a 10,85 € en varios
    lotes) y comparar por contenido confundiría esa coincidencia con la
    misma fila reextraída — exactamente el riesgo de mezclar lotes que esta
    sesión verificó antes de aprobar la propuesta. La franja vertical de la
    tabla de origen, codificada en la propia clave, es la única señal que
    distingue sin ambigüedad dos tablas de la misma página."""
    creadas = 0
    actualizadas = 0
    fusion_material = lote_id is not None
    for datos in _combinar_por_clave(lineas, permitir_fusion_material=fusion_material):
        # Transitorio, nunca una columna de `LineaCatalogo` -- se retira
        # antes de que `datos` se use para crear/actualizar la fila real,
        # y se guarda aparte para la limpieza de huérfana superada de más
        # abajo (ver docstring de esta función).
        clave_huerfana_hipotetica = datos.pop("clave_huerfana_hipotetica", None)
        existente = (
            db.query(LineaCatalogo)
            .filter_by(lote_id=lote_id, expediente_id=datos["expediente_id"], clave_linea=datos["clave_linea"])
            .one_or_none()
        )

        # Todas las filas que comparten firma con esta, no solo la primera:
        # un material puede llevar heredadas más de dos filas sueltas de
        # antes de este arreglo (`6.23/28510.0042`, matrícula `643480020` —
        # la búsqueda por clave exacta de la propia página que se está
        # guardando puede aterrizar en cualquiera de ellas según el orden en
        # que se procesan los documentos, así que quedarse solo con
        # `.first()` antes de saber cuál es `existente` podía dejar la
        # tercera fila sin visitar nunca).
        firma = None
        duplicados_por_firma: list[LineaCatalogo] = []
        if fusion_material:
            firma = _firma_material(datos)
            if firma is not None:
                matricula, descripcion, precio_unitario = firma
                consulta = db.query(LineaCatalogo).filter_by(
                    lote_id=lote_id,
                    expediente_id=datos["expediente_id"],
                    matricula=matricula,
                    descripcion=descripcion,
                    precio_unitario=precio_unitario,
                )
                if existente is not None:
                    consulta = consulta.filter(LineaCatalogo.id != existente.id)
                duplicados_por_firma = consulta.order_by(LineaCatalogo.id).all()

        # Firma sin matrícula (`_firma_material`, docstring): señal más débil
        # que con ella, se anota en `motivo_revision` para que la fusión
        # quede confirmable en vez de silenciosa. Se calcula antes de
        # vaciar `duplicados_por_firma` más abajo.
        fusion_sin_matricula = firma is not None and firma[0] is None and bool(duplicados_por_firma)

        if existente is None and duplicados_por_firma:
            existente = duplicados_por_firma.pop(0)

        if existente is None:
            db.add(LineaCatalogo(lote_id=lote_id, **datos))
            creadas += 1
        else:
            # `clave_linea` se recalcula aparte, más abajo: cuando la fila
            # existente se encontró por firma (no por clave exacta),
            # `datos["clave_linea"]` puede ser justo la clave *distinta* que
            # disparó esa búsqueda — fundirla aquí a ciegas, como cualquier
            # otro campo, la downgradearía de vuelta a la clave de matrícula
            # si esta llamada es la que no trae `codigo_precio`.
            for campo, valor in datos.items():
                if campo == "clave_linea":
                    continue
                if campo in ("precio_adjudicado", "baja_lote"):
                    # Ambos se recalculan desde cero en cada pasada -- nunca
                    # "esta pasada no trajo el dato" (que es lo que justifica
                    # no pisar el resto de campos). `precio_adjudicado` es
                    # derivado (CONTEXTO.md sección 4: `precio_unitario *
                    # (1 - baja_lote)`, o `None` si falta cualquiera de los
                    # dos); `baja_lote` se copia de `lote.baja_lote`, que
                    # `app.extraccion.orquestador` ya sobrescribe sin
                    # condición en cada extracción -- un `None` aquí SÍ
                    # significa "ya no se puede confirmar", nunca "no se
                    # miró". Hallazgo real, sesión de medición del alcance
                    # 2026-09-08: 336 líneas de `6.20/28510.0041` seguían con
                    # el precio adjudicado de una baja ya corregida a
                    # "desconocida" porque este bucle nunca llegaba a
                    # borrarlo -- verificado de nuevo, sesión del bloque 3 de
                    # cambios del cliente: la propia `baja_lote` por línea
                    # tenía el mismo hueco (seguía en 97,73 % pese a que
                    # `lote.baja_lote` ya estaba en blanco).
                    setattr(existente, campo, valor)
                elif valor is not None:
                    setattr(existente, campo, valor)
            for duplicado in duplicados_por_firma:
                # Filas heredadas de antes de este arreglo para la misma
                # pieza física: se absorben en `existente` (los campos que
                # le falten se rellenan desde cada una) y se borran, en vez
                # de dejarlas como duplicados que ningún reproceso futuro
                # vuelve a mirar.
                for campo in LineaCatalogo.__table__.columns.keys():
                    if campo in ("id", "lote_id", "clave_linea"):
                        continue
                    valor_heredado = getattr(duplicado, campo)
                    if valor_heredado is not None and getattr(existente, campo) is None:
                        setattr(existente, campo, valor_heredado)
                db.delete(duplicado)
            if fusion_material and existente.codigo_precio:
                # Prioridad de `calcular_clave_linea` aplicada de nuevo tras
                # la fusión: si el código de precio ya se conoce (propio o
                # recién fundido desde la otra tabla), esa es la clave
                # canónica, gane quien gane la carrera de documentos. Ya no
                # puede colisionar con la fila absorbida justo arriba, pero
                # sí, en teoría, con una tercera fila totalmente ajena que
                # comparta el mismo `codigo_precio` sin compartir matrícula
                # -- un problema de datos real que conviene que reviente
                # aquí, no que se disimule.
                #
                # Guardado tras `fusion_material` (bug de duplicación
                # infinita en huérfanas, auditoría 2026-09-05,
                # docs/correccion-defectos-auditoria.md): para una línea
                # huérfana (`lote_id is None`, `fusion_material=False`),
                # `clave_linea` no es solo el `codigo_precio` -- lleva el
                # sufijo de página/franja que añade
                # `app.extraccion.pipeline_anejo` precisamente para
                # distinguir dos tablas ambiguas que repiten el mismo
                # código (docstring de ese módulo). Sin este guard, esta
                # rama "limpiaba" esa clave de vuelta al `codigo_precio`
                # desnudo en cuanto la línea se actualizaba una vez -- el
                # siguiente reproceso, que vuelve a calcular la clave CON
                # sufijo, ya no encontraba la fila existente (la búsqueda
                # exacta por `clave_linea` fallaba) y creaba una fila nueva
                # en su lugar. Repetido en cada ciclo de mantenimiento, esto
                # duplicaba sin límite las huérfanas de los expedientes
                # multi-lote con banda vacía (`6.25/28510.0019` y otros seis
                # expedientes, ~4.500 líneas de sobra medidas en esa
                # auditoría). Con el guard, esta "canonicalización" solo se
                # aplica cuando de verdad hace falta: dentro de un lote
                # conocido, tras fundir por firma de material.
                clave_ideal = existente.codigo_precio.strip()
                if clave_ideal:
                    existente.clave_linea = clave_ideal
            if fusion_sin_matricula:
                existente.motivo_revision = _acumular_motivo_unico(
                    existente.motivo_revision, _MOTIVO_FUSION_SIN_MATRICULA
                )
            actualizadas += 1
        if lote_id is not None:
            _limpiar_huerfana_superada(db, datos["expediente_id"], clave_huerfana_hipotetica)
    return ResultadoGuardadoCatalogo(creadas=creadas, actualizadas=actualizadas)
