"""Cruce con el Excel de códigos (CONTEXTO.md sección 7, "Cruce con el Excel
de códigos" y sección 16, "confirmar con el cliente..."): las tres primeras
columnas del catálogo — código interno, código de proyecto y código matriz —
salen de `Expedientes.xlsx` por clave exacta, nunca por similitud de nombre.

No usa modelo, no es una etapa de la cascada de extracción (CONTEXTO.md sección
5): es una búsqueda determinista sobre un fichero de referencia, igual de
mecánica que un `JOIN`. El Excel se carga entero una vez por proceso (es un
fichero de unos pocos cientos de filas, sección 3) y se cachea en memoria por
ruta + fecha de modificación, para no releerlo en cada expediente.

"El sistema nunca inventa una matriz. Si no cruza, se deja vacío y se marca"
(sección 7): `CruceCodigos.cruzado` es la marca; ningún campo se rellena con
una suposición cuando es `False`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import openpyxl
from sqlalchemy.orm import Session

from app.config import settings

_ESPACIOS = re.compile(r"\s+")


@dataclass(frozen=True)
class CruceCodigos:
    codigo_interno: Optional[str]
    codigo_proyecto: Optional[str]
    codigo_matriz: Optional[str]
    cruzado: bool
    # Sesión 2026-09-18 (bloque 2, decisión del cliente): `True` solo cuando
    # la fila encontrada es la DEL PROPIO EXPEDIENTE -- `codigo_expediente`
    # contra la columna `Nº Expediente`, la primera de las cuatro claves que
    # prueba `_IndiceCodigosProyecto.buscar`. Las otras tres encuentran la
    # fila de OTRO expediente (medido sobre los 611 reales: 352 entran por la
    # primera, 28 por las otras tres), y de esa fila salía hasta hoy el
    # "Código interno" -- la columna por la que buscan en almacenes. Ver
    # `asegurar_cruce_codigos`.
    fila_propia: bool = False


def normalizar_codigo_expediente(valor: Optional[str]) -> Optional[str]:
    """Recorta espacios sobrantes y unifica separadores (CONTEXTO.md sección 8:
    "En el Excel hay valores como '6.25/28510.0146 '. Un cruce exacto fallaría
    en silencio.")."""
    if valor is None:
        return None
    limpio = _ESPACIOS.sub("", str(valor).strip())
    return limpio or None


class AutoreferenciaMatrizError(ValueError):
    """Un expediente no puede declararse su propia matriz (CONTEXTO.md sección
    2, trampa de vocabulario "Matriz"). Verificada en cuatro variantes reales
    del mismo síntoma, cada una desde un origen de dato distinto
    (docs/identidad-expediente.md): el PDF propio ("Nº EXPEDIENTE MATRIZ" de
    una Propuesta LC.27 multi-lote), el Excel de códigos (columna MATRIZ
    igual a la propia "Nº Expediente" para una licitación multi-lote sin
    acuerdo marco real, caso `6.23/28510.0109`), la corrección de identidad
    (mitigado por diseño: nunca puede autorreferenciarse) y la corrección
    manual desde la cola de revisión. De ahí que la comprobación viva en un
    único punto (`asignar_matriz`) en vez de repetirse -- y a veces
    olvidarse -- en cada sitio que escribe `expediente.codigo_matriz`."""


def asignar_matriz(expediente, candidato: Optional[str], *, sobrescribir: bool = False) -> bool:
    """Único punto de escritura de `expediente.codigo_matriz`. Normaliza el
    candidato (espacios sobrantes, CONTEXTO.md sección 8) y lo compara contra
    el propio `codigo_expediente` antes de escribir, venga el dato de donde
    venga (PDF, Excel de códigos, corrección manual).

    Lanza `AutoreferenciaMatrizError` si el candidato (ya normalizado) es
    igual al propio `codigo_expediente` -- nunca lo escribe en silencio, para
    que cada llamador decida qué hacer con el intento (motivo de revisión en
    la cascada, error 400 en la corrección manual).

    `sobrescribir=False` (por defecto) no pisa un valor ya existente -- es
    "rellenar solo si está vacío", el caso de la cascada de extracción y del
    cruce con el Excel. `sobrescribir=True` es para una corrección manual
    explícita, que sí puede reemplazar un valor previo.

    Devuelve `True` si escribió algo, `False` si no había nada que escribir
    (candidato vacío) o si ya había un valor y `sobrescribir=False`."""
    candidato_norm = normalizar_codigo_expediente(candidato)
    if not candidato_norm:
        return False
    if candidato_norm == normalizar_codigo_expediente(expediente.codigo_expediente):
        raise AutoreferenciaMatrizError(
            f"el expediente {expediente.codigo_expediente} no puede ser su propia matriz "
            f"(candidato: {candidato})"
        )
    if expediente.codigo_matriz and not sobrescribir:
        return False
    expediente.codigo_matriz = candidato_norm
    return True


class _IndiceCodigosProyecto:
    """Índice en memoria de `Expedientes.xlsx` (columnas `Nº Interno`,
    `Nº Expediente`, `MATRIZ`), por las dos claves por las que puede cruzar
    un código extraído (CONTEXTO.md sección 3: "29 como Nº Expediente, 3 como
    MATRIZ")."""

    def __init__(self, filas: list[dict]):
        self._por_nexpediente: dict[str, dict] = {}
        self._por_matriz: dict[str, dict] = {}
        for fila in filas:
            clave_nexp = normalizar_codigo_expediente(fila.get("Nº Expediente"))
            clave_matriz = normalizar_codigo_expediente(fila.get("MATRIZ"))
            if clave_nexp and clave_nexp not in self._por_nexpediente:
                self._por_nexpediente[clave_nexp] = fila
            if clave_matriz and clave_matriz not in self._por_matriz:
                self._por_matriz[clave_matriz] = fila

    def buscar(
        self, codigo_expediente: str, codigo_matriz: Optional[str]
    ) -> Optional[tuple[dict, bool, bool]]:
        """Devuelve la fila encontrada, si el cruce fue por `Nº Expediente`
        (`True`) o por `MATRIZ` (`False`), y si la fila es la DEL PROPIO
        EXPEDIENTE (solo la primera de las cuatro claves).

        La primera distinción importa para la matriz: cuando
        `codigo_expediente` cruza por la columna MATRIZ (CONTEXTO.md sección
        3: "3 como MATRIZ"), significa que el propio expediente ES el acuerdo
        marco de esa fila — su columna MATRIZ vale, trivialmente, el propio
        `codigo_expediente` que se buscó. Devolver ese valor como "la matriz
        de este expediente" sería inventarla por auto-referencia (sección 7:
        "el sistema nunca inventa una matriz").

        La segunda importa para el "Código interno" (sesión 2026-09-18,
        bloque 2): las cuatro claves no son intercambiables. Solo
        `codigo_expediente` → `Nº Expediente` garantiza que la fila hallada
        describa a este expediente; las otras tres encuentran la fila de otro
        (el pedido que declara a este como su matriz, o la matriz de este),
        y su `Nº Interno` es el de ESE otro expediente."""
        propia = True
        for clave in (codigo_expediente, codigo_matriz):
            clave_normalizada = normalizar_codigo_expediente(clave)
            if clave_normalizada is None:
                propia = False
                continue
            fila = self._por_nexpediente.get(clave_normalizada)
            if fila is not None:
                return fila, True, propia
            fila = self._por_matriz.get(clave_normalizada)
            if fila is not None:
                # Por MATRIZ, la fila es la de otro expediente incluso cuando
                # la clave buscada fue el `codigo_expediente` propio.
                return fila, False, False
            propia = False
        return None


class CodigosProyectoPathInvalida(RuntimeError):
    """`CODIGOS_PROYECTO_PATH` está configurada pero no apunta a un `.xlsx`
    legible (sesión del Excel al cliente, encargo del usuario: "que falle de
    forma visible en vez de continuar con el cruce roto"). Caso real que
    motiva esto: un bind-mount de Docker cuyo origen no existía creó en su
    lugar un directorio vacío en la ruta montada -- `asegurar_cruce_codigos`
    solo atrapa `FileNotFoundError` (pensado para la ruta sin configurar),
    así que un directorio ahí producía un `IsADirectoryError` sin capturar
    en la primera petición que tocara un expediente aún sin intentar, y
    -- porque `codigos_cruzados` no se reintenta nunca una vez escrito
    (docstring de `asegurar_cruce_codigos`) -- cualquier expediente cuyo
    intento cayera justo en esa ventana quedaba marcado `codigos_cruzados =
    False` para siempre, indistinguible de un expediente que de verdad no
    cruza. Verificar esto al arrancar, una vez, es mucho más barato que
    perseguirlo expediente a expediente después."""


def validar_ruta_codigos_proyecto(ruta: Optional[str]) -> None:
    """Se llama una vez al arrancar la API y el worker (`app.main`,
    `app.worker`). Sin ruta configurada no hay nada que validar -- cruce
    desactivado es una configuración válida (docstring de
    `asegurar_cruce_codigos`)."""
    if not ruta:
        return
    camino = Path(ruta)
    if not camino.is_file():
        raise CodigosProyectoPathInvalida(
            f"CODIGOS_PROYECTO_PATH={ruta!r} no es un fichero (¿bind-mount con el origen "
            "ausente, que Docker sustituyó por un directorio vacío?)"
        )
    try:
        libro = openpyxl.load_workbook(camino, read_only=True)
        libro.close()
    except Exception as exc:
        raise CodigosProyectoPathInvalida(
            f"CODIGOS_PROYECTO_PATH={ruta!r} no se puede abrir como .xlsx: {exc}"
        ) from exc


_cache: dict[str, tuple[float, _IndiceCodigosProyecto]] = {}


def _cargar_indice(ruta_excel: str) -> _IndiceCodigosProyecto:
    ruta = Path(ruta_excel)
    mtime = ruta.stat().st_mtime
    entrada = _cache.get(ruta_excel)
    if entrada is not None and entrada[0] == mtime:
        return entrada[1]

    # Hallazgo real (aviso del cliente, sesión 2026-09-07, caso
    # 6.26/28510.0014): antes solo se leía `libro.worksheets[0]`, la
    # primera hoja -- el scraper heredado tenía la misma limitación, leía
    # solo la hoja de expedientes en ejecución. El fichero de ejemplo de
    # este repositorio solo trae una hoja ("Hoja1"), así que esto no se
    # pudo reproducir contra datos reales todavía, pero el fichero real que
    # mantiene ADIF puede traer más de una (p.ej. una hoja separada para
    # procedimientos en tramitación) -- se leen todas, nunca solo la
    # primera. Cada hoja tiene su propia cabecera (no se asume el mismo
    # orden de columnas entre hojas); una fila repetida en dos hojas con el
    # mismo Nº Expediente se queda con la primera vista, mismo criterio que
    # ya usa `_IndiceCodigosProyecto` para duplicados dentro de una hoja.
    libro = openpyxl.load_workbook(ruta, read_only=True, data_only=True)
    filas: list[dict] = []
    for hoja in libro.worksheets:
        filas_iter = hoja.iter_rows(values_only=True)
        primera = next(filas_iter, None)
        if primera is None:
            continue  # hoja vacía, sin cabecera siquiera
        cabecera = [str(c).strip() if c is not None else "" for c in primera]
        filas.extend(dict(zip(cabecera, fila)) for fila in filas_iter)
    libro.close()

    indice = _IndiceCodigosProyecto(filas)
    _cache[ruta_excel] = (mtime, indice)
    return indice


def cruzar_codigo_proyecto(
    ruta_excel: str, codigo_expediente: str, codigo_matriz: Optional[str] = None
) -> CruceCodigos:
    indice = _cargar_indice(ruta_excel)
    encontrado = indice.buscar(codigo_expediente, codigo_matriz)
    if encontrado is None:
        return CruceCodigos(
            codigo_interno=None, codigo_proyecto=None, codigo_matriz=None, cruzado=False, fila_propia=False
        )
    fila, coincide_por_nexpediente, fila_propia = encontrado

    nº_interno = fila.get("Nº Interno")
    return CruceCodigos(
        # Sesión 2026-09-18, bloque 2: el `Nº Interno` de una fila que no es
        # la de este expediente pertenece a otro expediente -- no se devuelve.
        # `cruzado` sigue siendo `True`: la fila existe y su columna MATRIZ
        # puede seguir aportando información (ver `asegurar_cruce_codigos`).
        codigo_interno=(
            str(nº_interno).strip() if fila_propia and nº_interno is not None else None
        ),
        codigo_proyecto=normalizar_codigo_expediente(fila.get("Nº Expediente")),
        # Solo cuando el cruce fue por Nº Expediente el campo MATRIZ de la
        # fila es información nueva (la matriz real de este expediente). Por
        # MATRIZ, ese campo es el propio codigo_expediente buscado (ver
        # docstring de `buscar`): no hay matriz que devolver.
        codigo_matriz=normalizar_codigo_expediente(fila.get("MATRIZ")) if coincide_por_nexpediente else None,
        cruzado=True,
        fila_propia=fila_propia,
    )


def asegurar_cruce_codigos(db: Session, expediente) -> Optional[str]:
    """Intenta el cruce, y lo reintenta si hace falta, y deja la sesión con
    el cambio aplicado pero sin `commit` — lo hace la persona que llama,
    igual que el resto de mutaciones sobre `expediente` en esta cascada
    (CONTEXTO.md sección 7: cruce por clave exacta, "el sistema nunca inventa
    una matriz"). Se usa tanto al terminar la extracción de un expediente
    como, de forma perezosa, sobre expedientes ya procesados antes de que
    existiera esta columna (routers de catálogo y de expedientes).

    Un cruce que ya tuvo éxito (`codigos_cruzados=True`) nunca se repite: ya
    tiene su `codigo_interno`, no hay nada que ganar. Uno que falló
    (`codigos_cruzados=False`) tampoco se repite MIENTRAS `codigo_matriz`
    siga siendo el mismo que en el último intento (`codigo_matriz_en_cruce`,
    migración 0023) -- pero sí se reintenta en cuanto cambia (o aparece por
    primera vez). Hallazgo real, sesión de auditoría automática 2026-09-08
    (docs/sesion-2026-09-08-auditoria-automatica.md, bloque 2 punto 2): un
    pedido derivado de acuerdo marco descubierto por el mecanismo inverso
    (`app.extraccion.descubrimiento_matriz`) resuelve su `codigo_matriz`
    DESPUÉS de que este cruce ya se ejecutó una vez sobre él -- sin este
    reintento, `codigos_cruzados=False` quedaba fijo para siempre aunque la
    matriz recién conocida sí cruzara (verificado con `6.26/28510.0032`,
    `0071`, `0014`: cruzan al reintentar con su `codigo_matriz` actual).

    Devuelve un motivo de revisión, o `None` si no hay nada que avisar (la
    mayoría de las llamadas ignoran el valor de vuelta, que solo le importa
    al orquestador de extracción). Encargo de la sesión de herencia de
    acuerdo marco, requisito 1: la matriz declarada en el Anuncio PCSP propio
    (si existe, ya está en `expediente.codigo_matriz` cuando esto se llama) y
    la columna MATRIZ del Excel son dos fuentes independientes del mismo
    dato — si las dos existen y no coinciden, no se elige una en silencio,
    se marca `matriz_conflicto` y se explica por qué."""
    matriz_actual = normalizar_codigo_expediente(expediente.codigo_matriz)
    if expediente.codigos_cruzados is not None:
        # Sesión 2026-09-18, bloque 2: un cruce que tuvo éxito antes de que
        # existiera `cruce_fila_propia` no sabe por cuál de las cuatro claves
        # entró, así que no se puede decidir si su "Código interno" es el
        # suyo o el de otro expediente -- se rehace una vez (el índice ya está
        # en memoria, no cuesta nada) y a partir de ahí vuelve a no repetirse.
        ya_sabido = not (expediente.codigos_cruzados and expediente.cruce_fila_propia is None)
        if ya_sabido and (
            expediente.codigos_cruzados or matriz_actual == expediente.codigo_matriz_en_cruce
        ):
            return None
    if not settings.codigos_proyecto_path:
        return None
    try:
        resultado = cruzar_codigo_proyecto(
            settings.codigos_proyecto_path, expediente.codigo_expediente, expediente.codigo_matriz
        )
    except FileNotFoundError:
        return None
    expediente.codigos_cruzados = resultado.cruzado
    expediente.codigo_matriz_en_cruce = matriz_actual
    expediente.cruce_fila_propia = resultado.fila_propia if resultado.cruzado else None
    if not resultado.cruzado:
        return None

    # `codigo_interno` se recalcula entero en cada intento, nunca se acumula:
    # un `None` de un cruce por fila ajena tiene que BORRAR el valor heredado
    # en una pasada anterior, no dejarlo puesto (mismo criterio que
    # `baja_lote`/`precio_adjudicado`, CONTEXTO.md sesión 2026-09-09 bloque 3).
    expediente.codigo_interno = resultado.codigo_interno
    if not resultado.codigo_matriz:
        return None

    propia = normalizar_codigo_expediente(expediente.codigo_matriz)
    del_excel = normalizar_codigo_expediente(resultado.codigo_matriz)
    if propia and del_excel and propia != del_excel:
        expediente.matriz_conflicto = True
        return (
            f"la matriz declarada en el Anuncio PCSP ({expediente.codigo_matriz}) no coincide con la "
            f"columna MATRIZ del Excel de códigos ({resultado.codigo_matriz})"
        )
    try:
        asignar_matriz(expediente, resultado.codigo_matriz)
    except AutoreferenciaMatrizError:
        # Ruido heredado en el Excel de ejemplo (CONTEXTO.md "Pendiente de
        # resolver"): al menos una fila declara su propia columna MATRIZ
        # igual a su "Nº Expediente" para una licitación multi-lote sin
        # acuerdo marco real (caso 6.23/28510.0109, verificado). No es un
        # dato que el sistema pueda corregir por su cuenta -- se ignora sin
        # escribir nada, igual que cualquier otro cruce que no aporta un
        # candidato válido (sección 7: "el sistema nunca inventa una
        # matriz").
        pass
    return None
