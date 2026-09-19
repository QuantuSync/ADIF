"""`Código del material` (CONTEXTO.md sección 6 y 7): "el sustantivo principal
de la descripción [...] más un vocabulario controlado que crece con el uso.
El modelo solo se invoca si no casa nada, y su respuesta amplía el
vocabulario."

`derivar_codigo_material` cubre la parte determinista (sin modelo): buscar el
sustantivo principal contra el vocabulario ya conocido. `VOCABULARIO_CODIGO_MATERIAL`
ampliado en el bloque 5 de la sesión de vocabulario (2026-09-07): la versión
original (11 términos, solo los ejemplos literales de CONTEXTO.md) dejaba sin
código el 94% de las líneas del catálogo real. Ampliado extrayendo la primera
palabra de cada descripción del corpus real (`docs/...` pendiente, ver informe
de la sesión) y quedándose con los sustantivos genuinos de mayor frecuencia —
descartados explícitamente: códigos de tipo de aparato de vía sin ningún
sustantivo ("DSF-A-45-...", "SCI-A-54-...", "CZI-AG-...": identifican un
modelo, no una categoría de material), nombres de marca (SCHNEIDER, Allen
Bradley) y tokens de unidad de medida sueltos delante de la descripción real
("T de balasto...", "m de poste...", "ud SEÑAL...") — estos últimos se saltan
en `_termino_candidato` en vez de tratarse como material.

`derivar_codigo_material_con_modelo` añade la vía de modelo (bloque 5,
encargo del cliente: "si algún caso no encaja por reglas, ahí sí puede
intervenir el modelo, una vez por término nuevo y cacheado"), mismo mecanismo
que `app.extraccion.mapeo_cabecera` pero cacheado por término candidato en vez
de por firma de cabecera (`app.models.CacheCodigoMaterial`, migración 0018):
una palabra ya preguntada (con o sin match) no se vuelve a preguntar nunca.
`construir_linea_catalogo` sigue sin tocarse (mantiene su firma, CONTEXTO.md
sección 9.9 no aplica aquí pero el motivo es el mismo: no complicar una
función pura con `db`/`model_provider`) — la vía de modelo se ejercita como
paso posterior sobre las líneas ya construidas, en
`app.extraccion.pipeline_anejo.procesar_anejo`, que ya tiene `db` y
`model_provider` a mano para la etapa 5.
"""
from __future__ import annotations

import json
import re
import unicodedata
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.interfaces.model_provider import ModelProvider
from app.models import CacheCodigoMaterial

# Vocabulario inicial (CONTEXTO.md sección 6, ejemplos literales: "BRIDA",
# "PLACA", "JUNTA", "SUPLEMENTO") ampliado con los sustantivos reales más
# frecuentes del corpus (bloque 5, sesión 2026-09-07) — piezas y elementos de
# vía/aparatos de vía, componentes de instalaciones de señalización, y
# operaciones/servicios que aparecen como cabeza de la descripción con la
# misma función que un sustantivo de material ("ENRASADO", "LAVADO",
# "REMONTE"). Deliberadamente fuera: "PARTIDA" (CONTEXTO.md sección 2, la
# partida alzada es por definición una línea SIN código de material) y los
# adjetivos ordinales sueltos ("PRIMER", "SEGUNDO"...) que a veces encabezan
# una descripción sin ser el material en sí.
VOCABULARIO_CODIGO_MATERIAL = (
    "BRIDA",
    "PLACA",
    "JUNTA",
    "SUPLEMENTO",
    "GUANTE",
    "TRAVIESA",
    "BALASTO",
    "TIRAFONDO",
    "TORNILLO",
    "ARANDELA",
    "GRAPA",
    # Vía y aparatos de vía
    "CONTRACARRIL",
    "TIRANTE",
    "CABLE",
    "CARRIL",
    "CORAZÓN",
    "CRUZ",
    "BULÓN",
    "SEMICAMBIO",
    # Sesión 2026-09-17: piezas y aparatos de vía que el vocabulario no
    # tenía y que las siglas de `_SIGLAS_APARATO_VIA` también nombran.
    "AGUJA",
    "CONTRAAGUJA",
    "CRUZAMIENTO",
    "DESVÍO",
    "ESCAPE",
    "TRAVESÍA",
    "PALASTRO",
    "ENCARRILADORA",
    "CONJUNTO",
    "CERROJO",
    "JUEGO",
    "BIELA",
    "APÉNDICE",
    "BASTIDOR",
    "LLANTA",
    "CASQUILLO",
    "TIMONERÍA",
    "CONTRAAPOYO",
    "ABRAZADERA",
    "ANGULAR",
    "CALCE",
    "PASADOR",
    "CUÑA",
    "BARRA",
    "PLANCHA",
    "PLETINA",
    "PLATABANDA",
    "FORRO",
    "HORQUILLA",
    "SEMIBARRA",
    "RULO",
    "DADO",
    "VARILLA",
    "ESTRELLA",
    "YUGO",
    "TOPE",
    "CONO",
    # Herrajes / ferretería general
    "PIEZA",
    "SOPORTE",
    "EMPALME",
    "CHAPA",
    "PERFIL",
    "CERRADURA",
    "HILO",
    "KIT",
    "CONECTOR",
    "CLIP",
    "LLAVE",
    "TUBO",
    "CANDADO",
    "CAJA",
    "TACO",
    "PESTILLO",
    "FUELLE",
    "PITÓN",
    "CUPÓN",
    # Instalaciones / electromecánica y señalización
    "INTERRUPTOR",
    "MÓDULO",
    "AJUSTADOR",
    "BOBINA",
    "INDICADOR",
    "APARATO",
    "TARJETA",
    "BATERÍA",
    "HERRAMIENTA",
    "MICROPROCESADOR",
    "DETECTOR",
    "CONTROLADOR",
    "PROTECCIÓN",
    "MEMORIA",
    "RODILLO",
    "FUSIBLE",
    "PÉRTIGA",
    "LICENCIA",
    # Acrónimos que funcionan como el sustantivo principal de la línea en el
    # corpus real (nombran un tipo de equipo, no un modelo/código): "SEPA"
    # (Sistema de Enclavamiento Portátil para Agujas), "SAI" (Sistema de
    # Alimentación Ininterrumpida), "PAT" (mordaza de Puesta A Tierra).
    "SEPA",
    "SAI",
    "PAT",
    # Consumibles
    "ACEITE",
    "GRASA",
    # Operaciones/servicios que encabezan la línea igual que un sustantivo de
    # material (verificados contra el corpus real: "ENRASADO DE...", "LAVADO
    # DE BALASTO...", "REMONTE DE...").
    "ENRASADO",
    "LAVADO",
    "REMONTE",
    # Corpus fijo de prueba (fixtures de guantes/traviesas, CONTEXTO.md
    # sección 13): sustantivos reales, ausentes del muestreo del corpus
    # completo por ser minoritarios en él.
    "VERIFICADOR",
    "SOBREGUANTE",
    "SOTOGUANTE",
    "ESTAQUILLA",
)

# Palabras excluidas a propósito del vocabulario, nunca preguntadas al modelo
# (distinto de "no casa con nada todavía": esto es una exclusión de diseño).
# "PARTIDA" es la cabecera de "PARTIDA ALZADA" (CONTEXTO.md sección 2: una
# partida alzada es por definición una línea SIN código de material) — sin
# esta lista, cada partida alzada del corpus dispararía una llamada al modelo
# que siempre debe devolver "no es material", desperdiciada porque la
# respuesta ya se sabe de antemano. Los ordinales sueltos ("PRIMER",
# "SEGUNDO", "TERCER") y "OTRAS" tampoco son nunca el sustantivo del material,
# aunque encabecen la frase.
_EXCLUIDOS_DEL_MATERIAL = frozenset({"PARTIDA", "PRIMER", "SEGUNDO", "TERCER", "OTRAS", "OTRA", "OTRO", "OTROS"})

# Unidades de medida sueltas que a veces encabezan la descripción en vez del
# material (bloque 5, corpus real: "T de balasto transportado...", "m de
# poste soporte...", "ud SEÑAL DE DOBLE ASPA..."). Se saltan para mirar la
# palabra siguiente en vez de tratar la unidad como si fuera el material.
_UNIDADES_A_SALTAR = frozenset({"T", "M", "UD", "U", "KM", "ML", "KG", "UN"})

# Ordinales que encabezan la pieza ("SEGUNDA PLACA DE TALON", "TERCERA PLACA
# DE TALON", `6.20/28510.0046`): el material es la palabra siguiente. Sesión
# 2026-09-17: el modelo había cacheado "PRIMERA" -> PLACA y "SEGUNDA" -> nada.
_ORDINALES_A_SALTAR = frozenset({"PRIMERA", "SEGUNDA", "TERCERA", "CUARTA", "QUINTA"})

_PALABRA_RE = re.compile(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]+")


def _sin_acentos(palabra: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", palabra) if unicodedata.category(c) != "Mn")


# Índice normalizado (sin acentos) -> forma canónica del vocabulario, para que
# "BULON"/"BULÓN" o "CORAZoN" (acentos perdidos en la extracción de texto de
# algunos PDF) casen contra la misma entrada sin duplicar cada término dos
# veces en `VOCABULARIO_CODIGO_MATERIAL`.
_INDICE_SIN_ACENTOS: dict[str, str] = {_sin_acentos(t): t for t in VOCABULARIO_CODIGO_MATERIAL}


def _en_vocabulario(palabra: str) -> Optional[str]:
    """Casa `palabra` contra el vocabulario, tolerando acentos perdidos y el
    plural regular más común en español (visto en el corpus real: "CERROJOS",
    "BULONES", "FUSIBLES", "CASQUILLOS", "PIEZAS", "FORROS"...). Devuelve
    siempre la forma canónica (singular, con su acento) del vocabulario, para
    que la misma pieza en singular y en plural comparta un único código."""
    normalizada = _sin_acentos(palabra)
    if normalizada in _INDICE_SIN_ACENTOS:
        return _INDICE_SIN_ACENTOS[normalizada]
    for sufijo in ("S", "ES"):
        if normalizada.endswith(sufijo):
            singular = normalizada[: -len(sufijo)]
            if singular in _INDICE_SIN_ACENTOS:
                return _INDICE_SIN_ACENTOS[singular]
    return None


def _termino_candidato(descripcion: str) -> Optional[str]:
    """Primera palabra con forma de sustantivo de la descripción, saltando un
    token inicial de unidad de medida suelta (`_UNIDADES_A_SALTAR`) cuando lo
    hay. `None` si la descripción no trae ninguna palabra alfabética."""
    if not descripcion:
        return None
    palabras = [p.upper() for p in _PALABRA_RE.findall(descripcion)]
    if not palabras:
        return None
    indice = 0
    if palabras[0] in _UNIDADES_A_SALTAR and len(palabras) > 1:
        # La unidad puede ir pegada directamente al material ("ud SEÑAL...")
        # o unida por una preposición ("T de balasto...", "m de poste...") --
        # verificado contra el corpus real, las dos formas aparecen.
        indice = 2 if palabras[1] in ("DE", "DEL") and len(palabras) > 2 else 1
    if palabras[indice] in _ORDINALES_A_SALTAR and len(palabras) > indice + 1:
        indice += 1
    return palabras[indice]


# Sesión 2026-09-17 (bloque 2, `docs/sesion-2026-09-17-escaneados-codigo-
# material.md`): las siglas de la nomenclatura de aparatos de vía de ADIF SÍ
# nombran el tipo de pieza. Eran el 96 % de las líneas sin código (12.270 de
# 12.754, todas con la respuesta "no es material" del modelo en caché).
# Verificado contra el corpus, no supuesto: el mismo cuadro nombra la pieza
# con la sigla y con la palabra, bajo la misma serie de matrículas y la misma
# norma ("CAC-12000/SCI-A-..." junto a "CONTRAAGUJA CURVA-A-54-...", "AR-11250
# /SCI-A-54-..." junto a "AGUJA RECTA-A-54A-11,250M"; `6.20/28510.0046` p.25 y
# p.30); "CC 33" es el contracarril de perfil UIC-33; los `DS`/`DSH` y la
# familia `D??D/I` sin más texto cuestan 65.000-290.000 € (el desvío entero),
# mientras que los `SCI`/`SCV` y los `D??D/I` que dicen "Semicambio" cuestan
# 22.700-57.000 € (`6.22/28510.0122` p.31, `6.23/28510.0051` p.117).
# Siglas que no se pudieron verificar así (CI, CAM, ENM, CR, cables EAPSP...)
# se quedan fuera a propósito.
_SIGLAS_APARATO_VIA: dict[str, str] = {
    **dict.fromkeys(("AC", "AR"), "AGUJA"),
    **dict.fromkeys(("CAC", "CAR"), "CONTRAAGUJA"),
    "CC": "CONTRACARRIL",
    **dict.fromkeys(("CZ", "CZI", "CZV"), "CRUZAMIENTO"),
    **dict.fromkeys(("SC", "SCI", "SCV", "SCVH", "SCIL"), "SEMICAMBIO"),
    **dict.fromkeys(("DS", "DSH", "DSF", "DSFH", "DSI", "DSIH", "DSM", "DSMH"), "DESVÍO"),
    **dict.fromkeys(("ES", "ESH", "ESF", "ESFH"), "ESCAPE"),
    **dict.fromkeys(("TUD", "TUS", "TSU", "TUDI", "TUDL", "TUDIH", "TSUIH", "TUSIH"), "TRAVESÍA"),
    **dict.fromkeys(("AD", "ADH", "ADF", "ADI", "ADIH", "ADM", "ADMH", "ADMDH", "ADMIH"), "APARATO"),
    "JAE": "JUNTA",
    **dict.fromkeys(("TR", "TRAV"), "TRAVIESA"),
    "PL": "PLACA",
}

# Desvíos designados por su geometría ("DMRDH-G-60-500-...", "DIRD-B1-54-...").
_DESVIO_POR_GEOMETRIA_RE = re.compile(r"D[MRI]{2}[DI][HL]?")

# Pieza nombrada con palabra detrás de la sigla del aparato ("DMIDH-G-60-500-
# 0,071-CR-I-TC Semicambio dcha (doble)"): la palabra manda sobre la sigla.
_PIEZA_EXPLICITA_RE = re.compile(r"\b(SEMICAMBIO|CONTRACARRIL|CORAZ[OÓ]N|CRUZAMIENTO|CONTRAAGUJA|AGUJA)S?\b")

# Sigla al principio: letras mayúsculas (o "J.A.E.", "T.S.U."), seguidas de un
# separador de código, o de un espacio y algo con forma de código ("CC 33
# para...", "CAR SCI-B1-54-..."). Nunca una palabra en minúsculas.
_SIGLA_INICIAL_RE = re.compile(r"\s*((?:[A-Z]\.){2,}|[A-Z]{2,5})(?=[-‐(/.]|\s|$)")
_FORMA_DE_CODIGO_RE = re.compile(r"[A-Z0-9]+[-‐][A-Z0-9]|\d")


def _codigo_por_sigla_aparato_via(descripcion: str) -> Optional[str]:
    m = _SIGLA_INICIAL_RE.match(descripcion)
    if m is None:
        return None
    sigla = m.group(1).replace(".", "")
    resto = descripcion[m.end():]
    if resto[:1].isspace() and not _FORMA_DE_CODIGO_RE.search(resto):
        return None
    if sigla in _SIGLAS_APARATO_VIA:
        codigo = _SIGLAS_APARATO_VIA[sigla]
    elif _DESVIO_POR_GEOMETRIA_RE.fullmatch(sigla):
        codigo = "DESVÍO"
    else:
        return None
    if codigo == "DESVÍO":
        explicita = _PIEZA_EXPLICITA_RE.search(_sin_acentos(resto.upper()))
        if explicita is not None:
            return _en_vocabulario(explicita.group(1))
    return codigo


def derivar_codigo_material(descripcion: str) -> Optional[str]:
    termino = _termino_candidato(descripcion)
    if termino is None:
        return None
    return _en_vocabulario(termino) or _codigo_por_sigla_aparato_via(descripcion)


_ESQUEMA_CODIGO_MATERIAL = {
    "type": "object",
    "properties": {"codigo_material": {"type": ["string", "null"]}},
    "required": ["codigo_material"],
    "additionalProperties": False,
}


def _construir_prompt(termino: str, descripcion: str) -> str:
    return (
        "Esta es una línea de un cuadro de precios de material ferroviario de un "
        f"contrato público español: {descripcion!r}\n\n"
        f"Su primera palabra relevante es {termino!r}.\n\n"
        "Devuelve, en MAYÚSCULAS, sin acentos, en singular, el sustantivo principal que "
        "nombra el TIPO de material, pieza o elemento de esta línea (por ejemplo BRIDA, "
        "PLACA, JUNTA, TORNILLO) -- o null si la primera palabra es en realidad un código "
        "de modelo/tipo de aparato de vía sin ningún sustantivo reconocible (por ejemplo "
        "\"DSF-A-45-112/129\", \"SCI-A-54-DI-190\") o el nombre de una marca comercial."
    )


def _clasificar_con_modelo(termino: str, descripcion: str, model_provider: ModelProvider) -> Optional[str]:
    prompt = _construir_prompt(termino, descripcion)
    respuesta = model_provider.completar(prompt, esquema=_ESQUEMA_CODIGO_MATERIAL)
    if isinstance(respuesta, str):
        respuesta = json.loads(respuesta)
    valor = respuesta.get("codigo_material")
    return valor.strip().upper() or None if valor else None


def obtener_codigo_material_cacheado(db: Session, termino: str) -> Optional[CacheCodigoMaterial]:
    return db.query(CacheCodigoMaterial).filter_by(termino=termino).one_or_none()


def guardar_codigo_material_cacheado(
    db: Session, termino: str, codigo_material: Optional[str], origen: str
) -> CacheCodigoMaterial:
    """Bloque 3, sesión 2026-09-19 (quinta parte): tolera que el término ya
    esté en la caché. `termino` es `UNIQUE`, y una segunda inserción del mismo
    reventaba la extracción del documento entero con una `UniqueViolation`
    (`3.22/28510.0009`, término "CEPILLO", destapado al empezar a leerse su
    cuadro por bloques de lote). El valor cacheado no se pisa: la primera
    respuesta del modelo para un término es la que vale, y esta función solo
    existe para no volver a preguntarla."""
    entrada = CacheCodigoMaterial(termino=termino, codigo_material=codigo_material, origen=origen)
    db.add(entrada)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existente = obtener_codigo_material_cacheado(db, termino)
        if existente is None:
            raise
        return existente
    db.refresh(entrada)
    return entrada


def derivar_codigo_material_con_modelo(
    descripcion: str, db: Session, model_provider: Optional[ModelProvider]
) -> Optional[str]:
    """`derivar_codigo_material` primero (sin tocar la base de datos ni el
    modelo). Si no casa nada, mira la caché por término
    (`cache_codigo_material`) antes de llamar al modelo -- y si tampoco hay
    modelo disponible, se queda en `None` sin cachear nada (una ausencia de
    `ModelProvider` es una limitación de configuración, no una respuesta
    verificada del modelo; no se cachea como si lo fuera)."""
    valor = derivar_codigo_material(descripcion)
    if valor is not None:
        return valor

    termino = _termino_candidato(descripcion)
    if termino is None or termino in _EXCLUIDOS_DEL_MATERIAL:
        return None

    cacheado = obtener_codigo_material_cacheado(db, termino)
    if cacheado is not None:
        return _respuesta_aplicable(termino, cacheado.codigo_material, descripcion)

    if model_provider is None:
        return None

    valor_modelo = _clasificar_con_modelo(termino, descripcion, model_provider)
    guardar_codigo_material_cacheado(db, termino, valor_modelo, origen="modelo")
    return _respuesta_aplicable(termino, valor_modelo, descripcion)


def _respuesta_aplicable(termino: str, codigo: Optional[str], descripcion: str) -> Optional[str]:
    """Sesión 2026-09-17: la caché es por primera palabra, pero el modelo
    contestó mirando UNA descripción concreta -- reutilizada a ciegas, "X" ->
    BALASTO acababa en 231 líneas de equipos Ethernet y postes ("8X10/100B
    ETHERNET", "X2B-P POSTE"), "CARGA" -> BALASTO en cargas de radiofrecuencia
    y "SUMINISTRO" -> HERRAJE en el gasóleo. La respuesta solo vale para una
    descripción que nombra esa pieza ("Paquete de 1 Rodillo" -> RODILLO), o
    cuando es la propia palabra (abreviada o con una errata: "CONJ." ->
    CONJUNTO, "ADAPATADOR" -> ADAPTADOR). Se aplica igual a la respuesta
    recién pedida, para que un reproceso con la caché ya llena dé lo mismo."""
    if codigo is None:
        return None
    t, c = _sin_acentos(termino.upper()), _sin_acentos(codigo.upper())
    if len(t) >= 4 and (c.startswith(t[:4]) or t.startswith(c[:4])):
        return codigo
    raiz = c.split()[0][:5]
    if len(raiz) >= 4 and re.search(r"\b" + re.escape(raiz), _sin_acentos(descripcion.upper())):
        return codigo
    return None
