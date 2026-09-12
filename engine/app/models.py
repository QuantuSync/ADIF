import enum

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.db import Base


class EstadoExpediente(str, enum.Enum):
    pendiente = "pendiente"
    descargando = "descargando"
    descargado = "descargado"
    extrayendo = "extrayendo"
    pendiente_revision = "pendiente_revision"
    # Un pedido derivado de acuerdo marco (docs/analisis-corpus.md hallazgo 3)
    # descubrió que necesita su matriz y el sistema ya la está resolviendo
    # solo (creándola, encolando su descarga o su extracción) —
    # app.extraccion.herencia_matriz. Distinto de `pendiente_revision`: ese
    # dice "hace falta un humano", este dice "ya se está resolviendo, todavía
    # no hay nada que revisar".
    esperando_matriz = "esperando_matriz"
    completado = "completado"
    fallido = "fallido"
    # El expediente no existe en la Plataforma (docs/analisis-corpus.md,
    # sesión de expedientes sin publicar): comprobado a mano y confirmado por
    # `app.scraping.pcsp.ExpedienteNoPublicadoError` en todas las variantes de
    # separador de búsqueda. Distinto de `fallido`: ese dice "algo salió mal,
    # puede que reintentando funcione"; este dice "no hay nada que
    # reintentar, el documento no está publicado". Distinto también de
    # `pendiente_revision`: no hace falta un humano, no es trabajo pendiente,
    # es un expediente fuera de alcance del sistema.
    sin_publicar = "sin_publicar"
    # CONTEXTO.md sección 26, criterio del cliente: solo bajas de material por
    # lotes; un contrato de obra (campo "Tipo de Contrato" del Anuncio PCSP
    # distinto de "Suministros") no es un fallo de extracción, es un tipo de
    # contrato que este motor no está pensado para leer. Distinto de
    # `sin_publicar` (ahí no hay expediente que leer) y de `pendiente_revision`
    # (ahí sí hace falta un humano decidiendo sobre datos reales) -- aquí no
    # hay nada que decidir, está fuera de alcance por diseño.
    fuera_de_alcance = "fuera_de_alcance"


class TipoDocumento(str, enum.Enum):
    anuncio_pcsp = "anuncio_pcsp"
    propuesta_lc27 = "propuesta_lc27"
    resolucion_adjudicacion = "resolucion_adjudicacion"
    contrato = "contrato"
    anejo = "anejo"
    pliego = "pliego"
    # Tercera plantilla de propuesta (código "L9_CM.32-FE",
    # "INFORME-PROPUESTA DE ADJUDICACIÓN DE CONTRATO"), usada por Dirección
    # Técnica en vez de la Mesa de Contratación (docs/analisis-corpus.md
    # hallazgo 4): mismo tipo de hecho que propuesta_lc27 (declara baja y
    # adjudicatario) pero con anatomía propia, así que es su propio tipo, no
    # un alias forzado.
    propuesta_dt = "propuesta_dt"
    otro = "otro"


class OrigenDocumento(str, enum.Enum):
    """Bloque 6, sesión de comparación documento-vs-listado interno: de dónde
    viene el fichero físico -- descargado con navegador de la Plataforma
    (`app.scraping.job`, el único camino hasta esta sesión) o aportado a mano
    por el cliente vía una carpeta local (`app.ingesta_local`, expedientes
    vigentes en su SAP que todavía no están publicados). Vive en `Documento`,
    no en `DocumentoExpediente`: es una propiedad del fichero, no de qué
    expediente lo enlaza -- el mismo contenido (mismo hash) nunca cambia de
    procedencia real por enlazarse a un segundo expediente."""

    plataforma = "plataforma"
    manual = "manual"


class EstadoRevisionLinea(str, enum.Enum):
    sin_revisar = "sin_revisar"
    pendiente = "pendiente"
    confirmado = "confirmado"
    corregido = "corregido"
    descartado = "descartado"


class EstadoTrabajo(str, enum.Enum):
    pendiente = "pendiente"
    en_proceso = "en_proceso"
    completado = "completado"
    fallido = "fallido"


class ModeloPrecio(str, enum.Enum):
    # `fijo`: modelo de siempre (CONTEXTO.md sección 4), una baja porcentual
    # única por lote. `indexado_por_pedido`: segunda familia (migración
    # 0016, sesión de trabajo pendiente real 2026-09-05) -- el precio de
    # cada pedido futuro contra un Acuerdo Marco depende de índices IPRI
    # publicados por el INE y de un "Coeficiente de baja" que ADIF fija
    # pedido a pedido, ninguno de los dos presente en la licitación:
    # `baja_lote`/`precio_adjudicado` se quedan NULL a propósito para este
    # modelo, nunca por fallo de extracción.
    fijo = "fijo"
    indexado_por_pedido = "indexado_por_pedido"


class Expediente(Base):
    __tablename__ = "expedientes"

    id = Column(Integer, primary_key=True)
    codigo_expediente = Column(String(64), nullable=False, unique=True)
    codigo_matriz = Column(String(64), nullable=True)
    nombre_proyecto = Column(String(255), nullable=True)
    # Cruce con el Excel de códigos (CONTEXTO.md sección 7, "Cruce con el
    # Excel de códigos"): por clave exacta contra `codigo_expediente` /
    # `codigo_matriz`, nunca por similitud de nombre. `codigos_cruzados` es
    # `None` mientras no se ha intentado el cruce (expedientes procesados
    # antes de que existiera esta columna), `False` si se intentó y no
    # cruzó ninguna fila del Excel (el sistema nunca inventa un código:
    # `codigo_interno` se deja vacío), `True` si cruzó.
    codigo_interno = Column(String(64), nullable=True)
    codigos_cruzados = Column(Boolean, nullable=True)
    # Migración 0023 (sesión de auditoría automática, 2026-09-08, hallazgo
    # bloque 2 punto 2): qué valor de `codigo_matriz` (ya normalizado) tenía
    # el expediente la última vez que se intentó el cruce -- necesario para
    # distinguir "el cruce falló y sigue sin haber nada nuevo que probar" de
    # "el cruce falló, pero desde entonces se resolvió una matriz distinta
    # (o una matriz por primera vez) que merece un segundo intento". Un
    # pedido derivado de acuerdo marco descubierto por el mecanismo inverso
    # (`app.extraccion.descubrimiento_matriz`) resuelve su `codigo_matriz`
    # DESPUÉS de que `asegurar_cruce_codigos` ya se ejecutó una vez sobre él
    # -- sin este rastro, `codigos_cruzados=False` queda fijo para siempre
    # aunque la matriz recién conocida sí cruce (verificado con
    # `6.26/28510.0032`, `0071`, `0014`: cruzan al reintentar con su
    # `codigo_matriz` actual). `None` si nunca se intentó el cruce, o si se
    # intentó cuando el expediente todavía no tenía ninguna matriz.
    codigo_matriz_en_cruce = Column(String(64), nullable=True)
    importe_licitacion = Column(Numeric(14, 4), nullable=True)
    importe_adjudicacion = Column(Numeric(14, 4), nullable=True)
    baja_global = Column(Numeric(12, 6), nullable=True)
    # True cuando el expediente tiene 2+ lotes con baja declarada distinta
    # entre sí: ahí `baja_global` se deja en NULL a propósito (CONTEXTO.md
    # sección 4, "no hay una baja distinta por material dentro de un lote"
    # no dice nada de que todos los lotes de un expediente compartan baja) y
    # este campo es lo que le dice a la web que explique el vacío en vez de
    # dejarlo parecer un fallo de extracción (encargo de esta sesión, punto
    # 4, ajuste 3). None mientras no se sepa (expediente de un solo lote, o
    # todavía sin procesar); False si hay varios lotes pero comparten baja.
    baja_variable_por_lote = Column(Boolean, nullable=True)
    # Relación resuelta con la matriz (app.extraccion.herencia_matriz),
    # distinta de `codigo_matriz` de arriba: ese es el código de texto
    # extraído del Anuncio PCSP o del Excel, que puede no tener fila propia
    # todavía. `matriz_expediente_id` es esa fila real, una vez existe.
    matriz_expediente_id = Column(Integer, ForeignKey("expedientes.id"), nullable=True)
    # True cuando el Anuncio PCSP propio y la columna MATRIZ del Excel de
    # códigos declaran una matriz distinta entre sí: el sistema nunca elige
    # una de las dos en silencio (encargo de la sesión de herencia de
    # acuerdo marco, requisito 1 — "si discrepan, a revisión").
    matriz_conflicto = Column(Boolean, nullable=True)
    # Frescura para la ejecución incremental (CONTEXTO.md sección 23, bloque 1):
    # cuándo se descargó y cuándo se extrajo por última vez con éxito, y con
    # qué versión de la lógica de extracción (`app.mantenimiento.frescura.
    # VERSION_LOGICA_EXTRACCION`). Los estampa `app.worker` (nunca
    # `app.scraping.job` ni `app.extraccion.orquestador`, que esta sesión no
    # toca) al terminar cada intento real. `huella_documentos` es un hash del
    # conjunto de `Documento.hash` de este expediente en el momento de la
    # última extracción: si cambia (documento añadido, quitado o sustituido),
    # el ciclo de mantenimiento sabe que hay que reextraer sin releer nada.
    descargado_en = Column(DateTime(timezone=True), nullable=True)
    extraido_en = Column(DateTime(timezone=True), nullable=True)
    version_logica_extraccion = Column(String(32), nullable=True)
    huella_documentos = Column(String(64), nullable=True)
    # Cuántos lotes declara la licitación en total (del "N LOTES" del título,
    # o del campo "Nº de Lotes:" del Anuncio PCSP) -- sesión de identidad de
    # lote, CONTEXTO.md sección 27. Puede ser mayor que `len(lotes)`: la
    # numeración real tiene huecos (lotes desiertos/anulados, verificado con
    # 6.25/28510.0028 saltando su LOTE 5), así que este número nunca se usa
    # para generar identificadores de lote que faltan, solo para comparar
    # "cuántos conocemos" contra "cuántos hay" y detectar cobertura parcial.
    lotes_totales_declarados = Column(Integer, nullable=True)
    estado = Column(
        Enum(EstadoExpediente, name="estado_expediente"),
        nullable=False,
        default=EstadoExpediente.pendiente,
        server_default=EstadoExpediente.pendiente.value,
    )
    # Por qué está en fallido o pendiente_revision, con el mensaje real
    # (CONTEXTO.md, encargo de esta sesión, punto 2). `trabajos_cola.error`
    # cubre el fallo de un trabajo concreto; este cubre el motivo a nivel de
    # expediente, incluida la revisión sin que ningún trabajo haya fallado.
    error = Column(Text, nullable=True)
    # CONTEXTO.md sección 26 (regresión de 6.24/28510.0088): el documento
    # firmado (PDF) es el acto administrativo; la instantánea de sindicación
    # es un volcado de otra fuente, con su propio alcance (a veces el de la
    # licitación completa de varios lotes, no el de un lote concreto) y su
    # propia cadencia de actualización -- no tiene la misma autoridad. Un
    # desajuste entre las dos ya no manda el expediente a revisión (eso
    # escondía el motivo real de revisión detrás de un ruido de alcance
    # distinto, o sacaba de completado un expediente correcto): se guarda
    # aquí como aviso, y `estado`/`error` no se tocan.
    aviso_sindicacion = Column(Text, nullable=True)
    # Descubrimiento inverso matriz -> pedidos (sesión de descubrimiento
    # inverso): por qué NO se pudo lanzar la búsqueda de pedidos de esta
    # matriz, para que el hueco se vea como una condición señalada, nunca
    # como un silencio. Hoy el único motivo real es "sin adjudicatario
    # extraído todavía" (app.extraccion.descubrimiento_matriz) -- sin eso no
    # hay con qué filtrar la búsqueda en la Plataforma. Se limpia solo en
    # cuanto la búsqueda consigue lanzarse de verdad.
    aviso_descubrimiento_pedidos = Column(Text, nullable=True)
    # Migración 0028 (bloque 6, sesión de comparación documento-vs-listado
    # interno, `app.ingesta_local`): la carpeta de ingesta manual de este
    # expediente contenía un documento cuyo código propio declarado (Anuncio
    # PCSP "Número de Expediente", Contrato "Contrato nº") no coincide con el
    # código de la carpeta -- no se adivina cuál es el correcto, ese
    # documento no se enlaza y queda aquí para revisión manual. Se
    # recalcula entero en cada ingesta (nunca se acumula sobre un aviso
    # viejo, mismo criterio que `aviso_sindicacion`): `None` cuando la
    # ingesta más reciente no encontró ningún documento así.
    aviso_ingesta_manual = Column(Text, nullable=True)
    # Migración 0028: este expediente combina, para el mismo tipo de
    # documento (Anuncio PCSP, Propuesta LC.27, Contrato...), un documento
    # descargado de la Plataforma y uno aportado a mano
    # (`OrigenDocumento.manual`) -- señal de que puede haber dos versiones
    # del mismo hecho conviviendo. La cascada ya resuelve el desacuerdo a
    # favor de la Plataforma (`app.extraccion.orquestador`, documentos de la
    # Plataforma se evalúan primero), pero el valor descartado del aportado
    # a mano no se pierde solo porque perdió: este aviso señala que hace
    # falta revisar si el documento manual sigue haciendo falta. Recalculado
    # entero en cada extracción, nunca acumulado (mismo criterio que
    # `aviso_sindicacion`).
    aviso_conflicto_documento_manual = Column(Text, nullable=True)
    # Bloque 1, sesión del Excel de ejecución SAP (2026-09-07): estado del
    # CONTRATO frente a ADIF ("En ejecución", ...), distinto de `estado` de
    # arriba (estado de PROCESAMIENTO de este sistema: descargando,
    # completado...) — un expediente puede estar `completado` para este
    # sistema y seguir "En ejecución" para ADIF, o al revés. Dato de negocio
    # que no existe en ningún documento de la Plataforma (ni PDF ni
    # sindicación): viene solo de la exportación SAP de ADIF
    # (`app.extraccion.estado_sap`), cruzado por `codigo_expediente` exacto,
    # nunca por título. `String` libre, no `Enum`: el único valor visto hasta
    # ahora es "En ejecución", pero el vocabulario real de SAP no está
    # documentado y una exportación futura puede traer otros.
    estado_contrato_sap = Column(String(64), nullable=True)
    estado_contrato_sap_actualizado_en = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    lotes = relationship("Lote", back_populates="expediente")
    # Sesión de colisión de hash entre expedientes hermanos (2026-09-08):
    # un documento puede pertenecer a varios expedientes (mismo PDF real
    # compartido entre lotes/expedientes hermanos), así que ya no hay una
    # relación directa `Expediente -> Documento` -- pasa siempre por
    # `DocumentoExpediente`. Ver su docstring y migración 0021.
    documento_links = relationship("DocumentoExpediente", back_populates="expediente")
    # Autorreferencial: la matriz de este expediente, si ya se resolvió
    # (app.extraccion.herencia_matriz.resolver_o_encolar_matriz).
    matriz = relationship(
        "Expediente", remote_side=[id], foreign_keys=[matriz_expediente_id], back_populates="pedidos"
    )
    # Lado inverso (sesión de descubrimiento inverso, punto 2 del encargo):
    # los pedidos que ya se sabe que cuelgan de este expediente como acuerdo
    # marco -- antes solo existía la dirección pedido -> matriz.
    pedidos = relationship(
        "Expediente", foreign_keys=[matriz_expediente_id], back_populates="matriz"
    )


class Lote(Base):
    __tablename__ = "lotes"
    __table_args__ = (
        UniqueConstraint("expediente_id", "identificador_lote", name="uq_lote_expediente_identificador"),
    )

    id = Column(Integer, primary_key=True)
    expediente_id = Column(Integer, ForeignKey("expedientes.id"), nullable=False)
    identificador_lote = Column(String(64), nullable=False)
    baja_lote = Column(Numeric(12, 6), nullable=True)
    importe_licitacion = Column(Numeric(14, 4), nullable=True)
    importe_adjudicacion = Column(Numeric(14, 4), nullable=True)
    adjudicatario = Column(String(255), nullable=True)
    # Código propio de ESTE lote en la Plataforma (formato de expediente,
    # p.ej. "6.24/28510.0113"), distinto del expediente principal bajo el
    # que están archivados los documentos (sesión de identidad de lote,
    # CONTEXTO.md sección 27) -- verificado que coincide siempre con el
    # "Contrato nº" del Contrato firmado de este lote (de ahí el nombre
    # anterior de esta columna, `numero_contrato`, renombrada porque el dato
    # casi siempre se conoce antes, por la Propuesta/Resolución). Atributo
    # del lote, no una fila de `Expediente` aparte -- decisión explícita de
    # esa sesión: no complica la web/Excel/idempotencia sin ganancia clara
    # mientras nadie necesite buscarlo como expediente independiente.
    codigo_expediente_lote = Column(String(64), nullable=True)
    # True cuando `baja_lote` (y los importes, si los trae) vinieron de la
    # matriz de un pedido derivado de acuerdo marco, no de los propios
    # documentos de este expediente (app.extraccion.herencia_matriz). None
    # cuando no aplica.
    baja_heredada_de_matriz = Column(Boolean, nullable=True)
    # Migración 0016 (sesión de trabajo pendiente real, 2026-09-05): ver
    # docstring de `ModeloPrecio`. `coeficiente_transformacion` solo tiene
    # valor cuando `modelo_precio == indexado_por_pedido` -- es el único
    # parámetro de la fórmula de ese modelo que sí está en la licitación
    # (los demás, índices IPRI y Coeficiente de baja, no existen todavía en
    # ningún documento).
    modelo_precio = Column(
        Enum(ModeloPrecio, name="modelo_precio"), nullable=False, default=ModeloPrecio.fijo
    )
    coeficiente_transformacion = Column(Numeric(8, 4), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    expediente = relationship("Expediente", back_populates="lotes")
    lineas_catalogo = relationship("LineaCatalogo", back_populates="lote")


class Documento(Base):
    """El fichero físico (sesión de colisión de hash entre expedientes
    hermanos, 2026-09-08, migración 0021): solo lo que decide el CONTENIDO
    del PDF -- hash, clasificación de plantilla, ruta de almacenamiento,
    páginas. Ya no tiene `expediente_id` ni `nombre_archivo` propios: qué
    expedientes lo referencian y cómo lo llama cada uno vive en
    `DocumentoExpediente`, porque el mismo fichero real puede pertenecer a
    más de un expediente (expedientes hermanos de una licitación
    multi-lote, verificado con `4.25/28510.0124`/`0132`, bytes idénticos) y
    cada uno puede haberlo numerado distinto en su propia descarga."""

    __tablename__ = "documentos"

    id = Column(Integer, primary_key=True)
    tipo_documento = Column(Enum(TipoDocumento, name="tipo_documento"), nullable=False)
    hash = Column(String(64), nullable=False, unique=True)
    ruta_almacenamiento = Column(String(512), nullable=False)
    paginas = Column(Integer, nullable=True)
    # Migración 0028 (bloque 6, sesión de comparación documento-vs-listado
    # interno): ver docstring de `OrigenDocumento`. `server_default`
    # "plataforma" porque todo documento anterior a esta sesión llegó por
    # scraping -- nunca hubo otra vía hasta `app.ingesta_local`.
    origen = Column(
        Enum(OrigenDocumento, name="origen_documento"),
        nullable=False,
        default=OrigenDocumento.plataforma,
        server_default=OrigenDocumento.plataforma.value,
    )
    procesado_en = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    expediente_links = relationship("DocumentoExpediente", back_populates="documento")


class DocumentoExpediente(Base):
    """Relación muchos-a-muchos entre `Documento` (el fichero físico) y
    `Expediente` (quién lo referencia) -- migración 0021, ver docstring de
    `Documento` para el porqué. `nombre_archivo` vive aquí, no en
    `Documento`: es "cómo numeró ESA descarga concreta este documento
    dentro de su categoría" (`ANEJO_2.pdf`...), y puede variar entre dos
    expedientes que comparten el mismo fichero real."""

    __tablename__ = "documento_expedientes"
    __table_args__ = (UniqueConstraint("documento_id", "expediente_id", name="uq_documento_expediente"),)

    id = Column(Integer, primary_key=True)
    documento_id = Column(Integer, ForeignKey("documentos.id"), nullable=False)
    expediente_id = Column(Integer, ForeignKey("expedientes.id"), nullable=False)
    nombre_archivo = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    documento = relationship("Documento", back_populates="expediente_links")
    expediente = relationship("Expediente", back_populates="documento_links")


class LineaCatalogo(Base):
    __tablename__ = "lineas_catalogo"
    __table_args__ = (
        UniqueConstraint("lote_id", "clave_linea", name="uq_linea_lote_clave"),
    )

    id = Column(Integer, primary_key=True)
    # `expediente_id` es directo, no derivado de `lote_id` -> `lotes.expediente_id`:
    # una línea huérfana (tabla de precios cuyo lote no se pudo determinar
    # con fiabilidad, CONTEXTO.md encargo de esta sesión punto 3) no tiene
    # lote, pero sigue perteneciendo a un expediente concreto y tiene que
    # poder trazarse hasta él.
    expediente_id = Column(Integer, ForeignKey("expedientes.id"), nullable=False)
    # NULL cuando la tabla de origen de esta línea no se pudo asociar a un
    # único lote sin ambigüedad (ver `app.extraccion.lote_tabla`). No existe
    # un lote "SIN_DETERMINAR": mezclar un estado de proceso con la tabla de
    # negocio `lotes` obligaría a toda consulta futura por lote a acordarse
    # de excluirlo. La línea huérfana va a la cola de revisión vía
    # `motivo_revision` y el estado del expediente, no vía un lote falso.
    lote_id = Column(Integer, ForeignKey("lotes.id"), nullable=True)
    clave_linea = Column(String(128), nullable=False)
    orden_aparicion = Column(Integer, nullable=False)
    codigo_precio = Column(String(32), nullable=True)
    matricula = Column(String(9), nullable=True)
    descripcion = Column(Text, nullable=False)
    codigo_material = Column(String(64), nullable=True)
    cantidad = Column(Numeric(14, 3), nullable=True)
    precio_unitario = Column(Numeric(14, 4), nullable=True)
    unidad_medida = Column(String(32), nullable=True)
    baja_lote = Column(Numeric(12, 6), nullable=True)
    precio_adjudicado = Column(Numeric(14, 4), nullable=True)
    codigo_interno = Column(String(64), nullable=True)
    documento_origen_id = Column(Integer, ForeignKey("documentos.id"), nullable=True)
    pagina = Column(Integer, nullable=True)
    fragmento = Column(Text, nullable=True)
    confianza = Column(Numeric(5, 4), nullable=True)
    estado_revision = Column(
        Enum(EstadoRevisionLinea, name="estado_revision_linea"),
        nullable=False,
        default=EstadoRevisionLinea.sin_revisar,
        server_default=EstadoRevisionLinea.sin_revisar.value,
    )
    comentarios = Column(Text, nullable=True)
    # Por qué esta línea no tiene lote asignado (siempre None si `lote_id`
    # no es None). Distinto de `comentarios` (notas humanas, sección 7):
    # esto lo escribe el motor, no una persona.
    motivo_revision = Column(Text, nullable=True)
    # True cuando esta línea se copió del cuadro de precios de la matriz de
    # un pedido derivado de acuerdo marco (app.extraccion.herencia_matriz),
    # no se extrajo de los documentos propios de este expediente.
    # `documento_origen_id`/`pagina`/`fragmento` siguen apuntando al
    # documento real de origen (el de la matriz): la trazabilidad no se
    # pierde por heredar, solo se marca para que se distinga a simple vista.
    heredado_de_matriz = Column(Boolean, nullable=True)
    # True cuando `lote_id` no se leyó de una cabecera "LOTE N" propia de
    # esta tabla, sino que se heredó de la tabla inmediatamente anterior del
    # mismo documento porque la franja que la precede no traía NINGÚN rastro
    # de la palabra "LOTE" (`app.extraccion.lote_tabla`, migración 0022,
    # encargo explícito del cliente, sesión de verificación del Excel
    # 2026-09-08: "que se distinga en la trazabilidad de una línea cuyo lote
    # viene de una cabecera explícita" -- si algún día una herencia resulta
    # incorrecta, tiene que poder encontrarse TODAS las líneas afectadas por
    # el mecanismo, no solo una). Nunca se pone a partir de una franja
    # ambigua (varias cabeceras, o una no declarada): solo ausencia total.
    lote_heredado_de_pagina_anterior = Column(Boolean, nullable=True)
    # Bloque 4, sesión 2026-09-09 (migración 0025): `True` únicamente cuando
    # `unidad_medida` se rellenó desde `maestro_materiales` (app.extraccion.
    # maestro_materiales.completar_unidades_desde_maestro) porque el
    # documento propio del expediente no la traía -- mismo patrón que
    # `heredado_de_matriz`/`lote_heredado_de_pagina_anterior`: sin esta marca,
    # `documento_origen_id`/`pagina`/`fragmento` seguirían apuntando al PDF
    # real pero ese valor concreto ya no vendría de ahí.
    unidad_medida_completada_desde_maestro = Column(Boolean, nullable=True)
    # Bloque 1, sesión 2026-09-10 (migración 0026): la unidad que dice
    # `maestro_materiales` cuando esta línea YA tiene su propia
    # `unidad_medida` (del documento real) y no coincide -- nunca pisa
    # `unidad_medida`, solo deja la discrepancia anotada para revisión
    # humana (encargo explícito del cliente: "es información útil").
    # `None` en el caso normal (sin matrícula, sin maestro, o coincide).
    unidad_medida_discrepancia_maestro = Column(String(32), nullable=True)
    # Bloque 1, sesión 2026-09-11 (migración 0027): `True` únicamente cuando
    # la matrícula se aceptó desde la cola de candidatos
    # (`app.extraccion.candidatos_matricula`), no se extrajo del documento
    # -- mismo patrón que `unidad_medida_completada_desde_maestro`.
    matricula_confirmada_manualmente = Column(Boolean, nullable=True)
    # `True` cuando un humano revisó los candidatos de esta línea (cola de
    # `GET /revision/candidatos-matricula`) y determinó que ninguno es
    # correcto -- saca la línea de la cola sin borrar sus `candidatos_
    # matricula`, que siguen contando para la estadística de "líneas con al
    # menos un candidato" (encargo de esta sesión).
    matricula_candidatos_rechazados = Column(Boolean, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    expediente = relationship("Expediente")
    lote = relationship("Lote", back_populates="lineas_catalogo")
    documento_origen = relationship("Documento")
    candidatos_matricula = relationship(
        "CandidatoMatricula", back_populates="linea_catalogo", cascade="all, delete-orphan"
    )


class TrazaOrigen(Base):
    __tablename__ = "trazas_origen"

    id = Column(Integer, primary_key=True)
    entidad_tipo = Column(String(32), nullable=False)
    entidad_id = Column(Integer, nullable=False)
    campo = Column(String(64), nullable=False)
    documento_id = Column(Integer, ForeignKey("documentos.id"), nullable=False)
    pagina = Column(Integer, nullable=True)
    fragmento = Column(Text, nullable=True)
    valor_extraido = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class MapeoCabeceraCache(Base):
    """Caché de la etapa 5 (CONTEXTO.md sección 6): una cabecera de tabla ya
    vista no vuelve a pasar por el mapeo determinista ni por el modelo. La
    firma es un hash estable de la cabecera normalizada (ver
    app.extraccion.firma_cabecera); `mapeo` guarda a qué índice de columna
    corresponde cada campo del esquema (o null si esa tabla no trae ese
    campo). `JSON` genérico (no `JSONB`) a propósito: esta tabla es
    consultable en SQLite para tests sin Postgres levantado, sin perder
    validez en Postgres."""

    __tablename__ = "cache_mapeo_cabecera"

    id = Column(Integer, primary_key=True)
    firma = Column(String(64), nullable=False, unique=True)
    cabecera = Column(JSON, nullable=False)
    mapeo = Column(JSON, nullable=False)
    origen = Column(String(16), nullable=False)  # "determinista" | "modelo"
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CacheTextoDocumento(Base):
    """Bloque 6, sesión de rendimiento (`docs/sesion-2026-09-12-defecto-
    mapeo-calidad-interfaz-rendimiento.md` bloque 4): caché del texto plano
    de cada página de un documento (`app.extraccion.texto.extraer_texto`),
    responsable de ~99% del tiempo de un reproceso real -- clave por
    `Documento.hash` (el contenido, no el id ni la ruta: dos expedientes
    hermanos pueden compartir el mismo documento físico bajo dos filas de
    `documentos` distintas si llegara a duplicarse, aunque hoy no ocurre
    -- `documento_expedientes` ya resuelve eso por relación, no por fila
    duplicada). Invalidable subiendo `VERSION_LOGICA_TEXTO`
    (`app.extraccion.texto`) sin borrar ninguna fila a mano: una versión
    distinta a la guardada se trata como caché ausente y se sobrescribe.
    `JSON` genérico, mismo motivo que `MapeoCabeceraCache`: consultable en
    SQLite para tests sin Postgres levantado."""

    __tablename__ = "cache_texto_documento"

    documento_hash = Column(String(64), primary_key=True)
    version_logica_texto = Column(String(32), nullable=False)
    num_paginas = Column(Integer, nullable=False)
    paginas = Column(JSON, nullable=False)  # [{"numero": int, "texto": str}, ...]
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CacheCodigoMaterial(Base):
    """Caché del `Código del material` (CONTEXTO.md sección 6, bloque 5 de la
    sesión de vocabulario): una llamada al modelo por término candidato
    nuevo, nunca por línea ni por descripción completa -- mismo mecanismo
    que `MapeoCabeceraCache`, aplicado al término (primera palabra con forma
    de sustantivo de la descripción) en vez de a una firma de cabecera.
    `codigo_material` admite `NULL`: el modelo confirmando "esto no es un
    sustantivo de material" (p.ej. un código de catálogo puro como
    "DSF-A-45-...") también se cachea, para no volver a preguntarlo."""

    __tablename__ = "cache_codigo_material"

    id = Column(Integer, primary_key=True)
    termino = Column(String(64), nullable=False, unique=True)
    codigo_material = Column(String(64), nullable=True)
    origen = Column(String(16), nullable=False)  # "modelo"
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SindicacionExpediente(Base):
    """Bloque 2, descubrimiento por sindicación (CONTEXTO.md sección 24):
    última instantánea conocida de un expediente en el XML CODICE de
    sindicación (ZIP mensual `licitacionesPerfilesContratanteCompleto3_
    AAAAMM.zip`), guardada como fuente independiente de los PDFs — nunca se
    escribe encima de `expedientes`/`lotes` directamente. Sirve para dos
    cosas: detectar novedades (un expediente nuevo, o uno que cambió de
    `estado_pcsp`) y contrastar (`app.sindicacion.contraste`) sus importes
    contra lo que extrajo la cascada de los PDFs — dos fuentes que se
    verifican entre sí, no una sustituye a la otra.

    Clave `codigo_expediente` (no `id` de la entrada `<atom:entry>`, que
    identifica la publicación sindicada, no el expediente en sí — CONTEXTO.md
    sección 17.1: "un mismo expediente puede aparecer varias veces"). Una
    fila por expediente, siempre la más reciente por `actualizado_en`
    (`<updated>` del feed) — nunca se regresa a un dato más viejo."""

    __tablename__ = "sindicacion_expedientes"

    id = Column(Integer, primary_key=True)
    codigo_expediente = Column(String(64), nullable=False, unique=True)
    expediente_id = Column(Integer, ForeignKey("expedientes.id"), nullable=True)
    actualizado_en = Column(DateTime(timezone=True), nullable=False)
    estado_pcsp = Column(String(16), nullable=True)
    organo_contratacion = Column(String(255), nullable=True)
    titulo = Column(Text, nullable=True)
    importe_licitacion_sin_impuestos = Column(Numeric(14, 4), nullable=True)
    importe_licitacion_con_impuestos = Column(Numeric(14, 4), nullable=True)
    importe_adjudicacion_sin_impuestos = Column(Numeric(14, 4), nullable=True)
    importe_adjudicacion_con_impuestos = Column(Numeric(14, 4), nullable=True)
    adjudicatario = Column(String(255), nullable=True)
    # Lista de {identificador, nombre, importe_licitacion_sin_impuestos,
    # importe_licitacion_con_impuestos} por cada cac:ProcurementProjectLot
    # del XML. `JSON` genérico (no `JSONB`), mismo motivo que
    # `MapeoCabeceraCache`: válido también en SQLite para tests.
    lotes = Column(JSON, nullable=True)
    periodo_zip = Column(String(6), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    expediente = relationship("Expediente")


class CandidatoAcuerdoMarco(Base):
    """Caché del descubrimiento inverso matriz -> pedidos
    (app.extraccion.descubrimiento_matriz): una fila por cada código de
    expediente que la búsqueda "Contrato basado en un Acuerdo Marco" de la
    Plataforma ha devuelto alguna vez como candidato, con la matriz que su
    propia ficha declaró al comprobarlo (sección "Acuerdo Marco -> Expediente"
    de la ficha, distinta de la búsqueda que lo encontró).

    Existe porque verificar un candidato cuesta abrir su ficha en un
    navegador real -- con 92 candidatos reales para un solo adjudicatario
    (sesión de descubrimiento inverso), repetir esa apertura en cada ciclo
    sería caro sin necesidad: la matriz que declara un candidato no cambia
    una vez adjudicado, así que se lee una vez y se reutiliza siempre,
    también para las búsquedas de OTRAS matrices que puedan devolver el
    mismo candidato (el mismo adjudicatario puede tener varios acuerdos marco
    a lo largo de los años, sección 1 del encargo).

    `codigo_matriz_declarado` en `None` significa "se abrió la ficha y no
    declaraba ninguna matriz" (candidato que coincidió con el filtro de
    búsqueda pero no es en realidad un pedido derivado, o cuya ficha no se
    pudo leer) -- distinto de la fila no existir todavía (candidato nunca
    comprobado)."""

    __tablename__ = "candidatos_acuerdo_marco"

    id = Column(Integer, primary_key=True)
    codigo_expediente_candidato = Column(String(64), nullable=False, unique=True)
    codigo_matriz_declarado = Column(String(64), nullable=True)
    verificado_en = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class TrabajoCola(Base):
    __tablename__ = "trabajos_cola"

    # BigInteger con variante Integer en SQLite: sqlite solo autoasigna el
    # id de una PK declarada como INTEGER (su alias del rowid); en Postgres
    # sigue siendo bigint, igual que crea la migración 0001.
    id = Column(BigInteger().with_variant(Integer(), "sqlite"), primary_key=True)
    tipo = Column(String(64), nullable=False)
    # JSON genérico con variante JSONB solo en Postgres (mismo tipo de
    # columna real que crea la migración 0001): así esta tabla también se
    # puede crear en SQLite para tests sin Postgres levantado, igual que
    # `MapeoCabeceraCache` — ver su docstring.
    payload = Column(JSON().with_variant(JSONB(), "postgresql"), nullable=True)
    estado = Column(
        Enum(EstadoTrabajo, name="estado_trabajo"),
        nullable=False,
        default=EstadoTrabajo.pendiente,
        server_default=EstadoTrabajo.pendiente.value,
    )
    intentos = Column(Integer, nullable=False, default=0, server_default="0")
    max_intentos = Column(Integer, nullable=False, default=3, server_default="3")
    expediente_id = Column(Integer, ForeignKey("expedientes.id"), nullable=True)
    resultado = Column(JSON().with_variant(JSONB(), "postgresql"), nullable=True)
    error = Column(Text, nullable=True)
    bloqueado_por = Column(String(128), nullable=True)
    bloqueado_en = Column(DateTime(timezone=True), nullable=True)
    # Backoff creciente en reintentos (sesión de límite de tasa de la
    # Plataforma, 2026-09-07, migración 0020): NULL significa "disponible
    # ya", como siempre. `tomar_siguiente_trabajo` no recoge un trabajo
    # `pendiente` cuyo `disponible_en` esté en el futuro -- ver
    # `app.queue.calcular_espera_reintento`.
    disponible_en = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class SapDesgloseLinea(Base):
    """Desglose de SAP con las matrículas concretas de cada contrato (bloque
    6, cambios del cliente tras revisar el catálogo, migración 0024) --
    justo lo que los pliegos no traen. `codigo_expediente` es texto, no FK
    (docstring de la migración): el cruce con `Expediente` es por clave
    exacta cuando hace falta consultarlo, nunca una relación estructural.
    Clave natural de una línea de pedido de compras real en SAP:
    `documento_compras` + `posicion` -- por eso el upsert de
    `app.extraccion.sap_desglose` usa esas dos columnas, nunca `id`."""

    __tablename__ = "sap_desglose_lineas"

    id = Column(Integer, primary_key=True)
    codigo_expediente = Column(String(64), nullable=False)
    documento_compras = Column(String(32), nullable=False)
    posicion = Column(String(16), nullable=False)
    material = Column(String(64), nullable=True)
    texto_breve = Column(String(255), nullable=True)
    cantidad_prevista = Column(Numeric(14, 3), nullable=True)
    precio_neto = Column(Numeric(14, 4), nullable=True)
    unidad_medida = Column(String(32), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("documento_compras", "posicion", name="uq_sap_desglose_documento_posicion"),
    )


class MaestroMaterial(Base):
    """Maestro de materiales de SAP (bloque 4, sesión 2026-09-09, migración
    0025) -- documento de referencia de ADIF, no derivado de pliegos ni
    contratos: matrícula y unidad de medida de cada material que existe en
    SAP, independientemente de en qué expediente se haya comprado. Distinto
    de `SapDesgloseLinea` (una fila por línea de pedido de compras real,
    ligada a un expediente): esta tabla es un catálogo de referencia, una
    fila por matrícula, sin relación con ningún expediente concreto -- por
    eso la clave natural es `matricula` sola, no un compuesto.
    `app.extraccion.maestro_materiales.cargar_maestro_materiales` hace
    upsert por esa clave; `completar_unidades_desde_maestro` la usa para
    rellenar `LineaCatalogo.unidad_medida` únicamente donde falta, nunca para
    pisar un valor ya extraído de un documento real."""

    __tablename__ = "maestro_materiales"

    id = Column(Integer, primary_key=True)
    # String(10), no 9: el fichero real trae 31.665 códigos de nueve dígitos
    # pero también 440 de cuatro y 11 de diez (categorías genéricas de SAP,
    # migración 0026). Una matrícula de línea de catálogo siempre tiene
    # nueve dígitos por definición de dominio, así que las de diez nunca
    # casan con ninguna línea -- no rompe el cruce, solo evita truncar la carga.
    matricula = Column(String(10), nullable=False, unique=True)
    descripcion = Column(String(255), nullable=True)
    unidad_medida = Column(String(32), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class CandidatoMatricula(Base):
    """Bloque 1, sesión 2026-09-11 (migración 0027) -- caché recomputable
    (mismo patrón que `MapeoCabeceraCache`/`CandidatoAcuerdoMarco`), NUNCA
    fuente de verdad: `app.extraccion.candidatos_matricula.calcular_
    candidatos` la vacía y la vuelve a llenar entera en cada ejecución.
    Nunca asigna matrícula por sí sola (CONTEXTO.md, análisis de la sesión
    del maestro de materiales, bloque 2: "tiene que ser una cola de
    candidatos para confirmación humana... nunca una asignación
    automática") -- un humano acepta uno desde `POST /revision/candidatos-
    matricula/{linea_id}/aceptar`, que sí escribe `LineaCatalogo.matricula`.

    `exacto=True` cuando la descripción normalizada de la línea coincide
    letra a letra con la denominación normalizada del maestro -- destacado
    en la cola por ordenarse primero, pero sigue exigiendo confirmación
    humana igual que cualquier otro candidato: el propio análisis midió que
    2.388 de las 28.782 denominaciones distintas del maestro (8,3%) mapean
    a más de una matrícula, así que ni una coincidencia exacta de texto es
    prueba suficiente por sí sola."""

    __tablename__ = "candidatos_matricula"

    id = Column(Integer, primary_key=True)
    linea_catalogo_id = Column(
        Integer, ForeignKey("lineas_catalogo.id", ondelete="CASCADE"), nullable=False, index=True
    )
    matricula_candidata = Column(String(10), nullable=False)
    denominacion_maestro = Column(String(255), nullable=True)
    similitud = Column(Numeric(5, 4), nullable=False)
    exacto = Column(Boolean, nullable=False, default=False)
    calculado_en = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    linea_catalogo = relationship("LineaCatalogo", back_populates="candidatos_matricula")
