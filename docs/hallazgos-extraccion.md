# Hallazgos de extracción

Registro histórico movido desde `CLAUDE.md` (split de sesión 2026-09-05).
Ver `CLAUDE.md` para el contexto vivo del proyecto.

---

## 17.2 Validación del mapeo de cabecera contra la API real (sesión 2026-09-02)

Primera vez que la etapa 5 de la cascada (CLAUDE.md sección 6) se ejercita contra la
API de Anthropic real, no contra un doble de test. Caso disparador: el
`ANEJO_3.pdf` del expediente `6.24/28510.0008`, que fallaba por cabecera no
mapeable. Verificado en contenedor Linux (worker real, Postgres real), no en
un script suelto.

- **Confirmado: el prompt nunca lleva las filas de datos completas**, solo la
  cabecera y las 3 primeras filas de ejemplo — verificado leyendo el prompt
  real tal cual se envió, no el código que lo construye.
- **`CachedModelProvider` ahora se cablea en el worker real vía
  `MODEL_CACHE_DIR`** (`app/config.py`, `docker-compose.yml`), vacío por
  defecto para no cachear en disco en producción por accidente. El caso de
  desarrollo vive en `engine/.cache_modelo_dev/` (gitignored), montado como
  bind mount en el contenedor del worker.
- **Confirmado: ambas capas de caché evitan una segunda llamada real**,
  comprobado por separado: la caché de firma en `cache_mapeo_cabecera`
  (borrando el fichero de disco) y la caché de disco de
  `CachedModelProvider` (borrando la fila de `cache_mapeo_cabecera`) — cada
  una por sí sola basta para que no haya HTTP real a `api.anthropic.com`.
- **Coste medido, tres cabeceras reales:** 1397 in / 56 out, 1323 in / 56
  out (`ANEJO_3.pdf`, cabeceras corruptas con `Ó`→`�`), y 1066 in / 535 out
  (`6.25/28510.0027_ANEJO_1.pdf`, cabecera con dos columnas fantasma). El
  salto de tokens de salida en el tercer caso es razonamiento del modelo
  (`claude-opus-5` piensa por defecto — no se desactiva `thinking` en
  `AnthropicModelProvider`), no JSON más largo: el esquema de salida es el
  mismo en los tres casos. `AnthropicModelProvider.completar` ahora registra
  el prompt y el coste en tokens de cada llamada real vía `logging`
  (nunca en un acierto de `CachedModelProvider`).
- **Nuevo tipo de clave de API: "ligada a identidad".** Una clave creada en
  la consola bajo un usuario (no una clave clásica de workspace) exige la
  cabecera `anthropic-workspace-id` en cada petición a `/v1/messages` — sin
  ella, 400 `invalid_request_error`. Se añadió `ANTHROPIC_WORKSPACE_ID`
  (`app/config.py`, `.env`, `docker-compose.yml`) y se pasa por
  `default_headers` **dentro de `AnthropicModelProvider`**, nunca en la
  interfaz `ModelProvider`: es un detalle de esta implementación concreta,
  no existe para un futuro modelo autoalojado.
- **Confirmado: sin clave y con fallo de red, el expediente cae en
  `pendiente_revision` con motivo claro, nunca rompe el trabajo entero** —
  ambos casos probados contra el worker real (sin `ANTHROPIC_API_KEY`, y con
  el cliente HTTP apuntado a un host inalcanzable).
- **Bug real encontrado y corregido: `guardar_lineas_catalogo` podía violar
  la constraint `UNIQUE` de golpe cuando el mismo `clave_linea` se repetía
  más de una vez dentro de un único lote de líneas** (el mismo cuadro de
  precios reaparece varias veces en un documento, CLAUDE.md sección 3). Causa: `app/db.py`
  configura `SessionLocal` con `autoflush=False` a propósito, así que el
  `db.query(...)` de comprobación de cada fila nunca veía las filas ya
  añadidas (`db.add()`) en la misma pasada del bucle — el `INSERT` en bloque
  final las mandaba todas juntas y Postgres rechazaba el duplicado. Los
  tests existentes no lo veían: `tests/conftest.py` crea su `db_session` con
  el `autoflush=True` por defecto de SQLAlchemy, que sí encubre el problema.
  Arreglado fundiendo el lote por `clave_linea` en Python
  (`app.catalogo._combinar_por_clave`) antes de tocar la base de datos, sin
  depender de si la sesión autoflushea o no. `tests/extraccion/test_pipeline_anejo.py`
  y `tests/test_catalogo.py` actualizados a la cuenta correcta de
  creadas/actualizadas.
- **Segundo bug real, mismo síntoma dos veces por causas distintas
  (pérdida de conexión con Postgres, y el bug de arriba): un fallo a mitad
  de un trabajo dejaba la sesión de SQLAlchemy en estado "necesita
  rollback", y el propio manejo de la excepción —tanto en
  `app.worker.ejecutar_trabajo` como en el `except` exterior de
  `ejecutar_extraccion_expediente`— tocaba la sesión rota (leyendo
  `trabajo.id`, o llamando a `db.commit()`) antes de hacer `db.rollback()`.
  Eso lanzaba un `PendingRollbackError` que sustituía al error real,
  reventaba el proceso entero del worker (el trabajo se quedaba huérfano en
  `en_proceso` hasta el umbral de `docs/hallazgos-scraping.md`, sección 17) en vez de marcar el trabajo
  como fallido con el motivo correcto. Arreglado con `db.rollback()` antes
  de tocar cualquier atributo o hacer cualquier escritura en el bloque
  `except` de ambos sitios.
- **Hallazgo de dominio, no un bug:** el `ANEJO_3.pdf` de `6.24/28510.0008`
  trae, para los mismos códigos de precio que el cuadro de guantes
  (`ANEJO_1.pdf`), una segunda tabla de características técnicas —
  normativa aplicable, impacto en seguridad, unidad de medida— **sin
  columna de precio ni de cantidad**. El modelo lo detectó bien (`cantidad`
  y `precio_unitario` a `null` en el mapeo, en vez de inventar una columna),
  y la fusión por `clave_linea` en `guardar_lineas_catalogo` conservó el
  precio y la cantidad que ya traía `ANEJO_1.pdf` sin que la segunda pasada
  los borrase — exactamente el caso que describe el docstring de la función.

---

## 17.3 Migración a Haiku para el mapeo de cabecera, y coste por expediente (sesión 2026-09-02)

Disparado por el propio dato de la sección 17.2: `claude-opus-5` devolvía
hasta 535 tokens de salida para traducir una cabecera a un diccionario de 6
claves — razonamiento (`thinking`) que la tarea no necesita. Traducir una
cabecera nunca vista es correspondencia de etiquetas, no una tarea que se
beneficie de un modelo grande.

- **Modelo por defecto de `AnthropicModelProvider` cambiado a
  `claude-haiku-4-5`** (`app/interfaces/model_provider.py`,
  `app/config.py`), configurable por `ANTHROPIC_MODEL` igual que antes — el
  worker ya leía esa variable (`app/worker.py`), así que el cambio de modelo
  es solo el valor por defecto. `.env` y `.env.example` actualizados a
  `claude-haiku-4-5`.
- **Verificado contra la API real de Anthropic** (no un doble de test),
  con las cachés vacías a propósito: sesión de base de datos en memoria
  recién creada (sin filas en `cache_mapeo_cabecera`) y sin pasar por
  `CachedModelProvider`, para forzar una llamada real en cada cabecera no
  determinista. Se reprocesaron con `procesar_anejo` (cascada completa,
  etapas 3 a 6) los dos mismos documentos de la sesión 17.2:
  `6.24/28510.0008_ANEJO_3.pdf` (tabla de guantes, cabeceras con `Ó`
  corrompida) y `6.25/28510.0027_ANEJO_1.pdf` (tabla de balasto, columnas
  fantasma). Entre los dos aparecieron **5 firmas de cabecera distintas**
  (2 y 3 respectivamente — más que las 3 de la sesión 17.2 porque esta vez
  se recorrió el documento entero con la cascada real, no una cabecera
  aislada elegida a mano) y las 5 forzaron una llamada real a Haiku.
- **Los 5 mapeos salen idénticos en estructura a los que ya había validado
  Opus**, verificado línea a línea:
  - Las dos variantes de `ANEJO_3.pdf` (tabla de características técnicas
    sin precio ni cantidad) devuelven `cantidad: null` y
    `precio_unitario: null` en vez de inventar una columna — el mismo
    comportamiento correcto que documenta el hallazgo de dominio de la
    sección 17.2.
  - Las tres variantes de `ANEJO_1.pdf` (0, 1 y 2 columnas fantasma
    desplazando los índices) sitúan `cantidad` y `precio_unitario` en la
    columna correcta en las tres, y `matricula: null` en las tres (esta
    tabla de balasto no trae matrícula, no es un fallo del mapeo).
  - **Ninguna cabecera falló.** No hizo falta volver a un modelo mayor para
    ningún caso — la salvedad que pedía la tarea no aplicó.
- **Coste medido, Haiku, 5 llamadas reales:** de 829 a 1091 tokens de
  entrada, 48-49 de salida en las cinco (media 926 in / 49 out) — nunca los
  535 de salida que se vio con Opus en un caso. A precio de Haiku
  ($1,00 / $5,00 por millón de tokens entrada/salida), cada llamada cuesta
  **≈ 0,0012 $** (≈ 0,0011 €). Las tres llamadas de Opus de la sesión 17.2
  (1397/56, 1323/56, 1066/535 tokens) costaban, al precio de Opus
  ($5,00 / $25,00 por millón), entre 0,0080 $ y 0,0187 $ cada una, media
  ≈ 0,0117 $. **Haiku sale de la cascada ≈ 10 veces más barato por llamada
  que Opus para esta tarea concreta.** (Conversión USD→EUR indicativa a
  ≈0,92 €/$; la facturación real de Anthropic es en dólares.)
- **Caché de desarrollo (`engine/.cache_modelo_dev/`) vaciada** como parte
  de esta verificación: su clave es un hash de `(prompt, esquema)`, no
  incluye el modelo, así que un acierto de caché anterior a este cambio
  habría seguido sirviéndose sin pasar nunca por Haiku. Vacía no rompe
  nada — se repuebla sola en el primer uso real de cada firma.

### Coste estimado de procesar un expediente completo

Con Haiku como modelo por defecto y el precio de arriba. CLAUDE.md sección 6 fija
la regla que hace esta cuenta favorable: una llamada por firma de cabecera
nunca vista, nunca por documento ni por fila.

- **Peor caso (expediente nuevo, cachés en frío — el primer expediente que
  ve una plantilla, o el primero de la demo).** Un expediente típico trae 1
  a 3 documentos con cuadro de precios (anejo, y a veces un segundo anejo de
  características técnicas que repite el mismo cuadro, CLAUDE.md sección 3). Medido
  en este mismo expediente (`6.24/28510.0008`, con `ANEJO_1` y `ANEJO_3`):
  hasta 2-3 firmas de cabecera distintas por documento por las columnas
  fantasma y la corrupción de extracción. Cota razonable: **hasta 6-8
  llamadas al modelo por expediente** (mapeo de cabecera), más 1 llamada
  adicional por documento si trae filas huérfanas que agrupar (CLAUDE.md sección 6;
  camino no ejercitado todavía contra ningún fixture real, así que esa cota
  es sin verificar) y, rara vez, 1 llamada de `Código del material` si no
  casa nada del vocabulario controlado. **Techo defendible: ≈ 8-10 llamadas,
  ≈ 0,010-0,012 $ (≈ 0,010-0,011 €) por expediente** — sigue siendo una
  fracción de céntimo.
- **Régimen normal, caché caliente (a partir de los primeros expedientes
  procesados).** CLAUDE.md sección 3 mide que las cabeceras se repiten mucho —
  "una aparece 20 veces, otra 6, otra 4" sobre solo 7 documentos — así que
  en cuanto el catálogo de firmas se estabiliza, un expediente nuevo casi
  siempre trae solo cabeceras ya vistas. **0 llamadas al modelo en el caso
  típico**, y 1 llamada (≈ 0,0012 $) en el expediente ocasional que
  introduce una variante de cabecera realmente nueva.
- **Efecto agregado.** Sobre un lote de, por ejemplo, 45 expedientes (el
  corpus de la sección 3 de CLAUDE.md), el coste de mapeo de cabecera no pasa de un
  puñado de céntimos en total, aunque cada uno se procesara con la caché en
  frío — y baja hacia cero según crece el catálogo, por diseño (CLAUDE.md sección 6:
  "el sistema llama menos al modelo cuantos más expedientes procesa"). El
  coste de esta etapa es irrelevante frente a cualquier otro coste del
  proyecto (cómputo, almacenamiento, scraping); no es la partida que hay
  que vigilar para controlar el gasto.

---

## 18. Catálogo, revisión y exportación (cierre del punto 5 del orden de trabajo)

Sesión 2026-09-02. Implementa y verifica en vivo — contenedor Linux real,
Postgres real, los dos expedientes ya procesados (`6.24/28510.0008`,
`6.25/28510.0027`) — los cinco encargos de esta sesión: explorar el
catálogo con búsqueda por matrícula, trazabilidad, cola de revisión,
exportación a Excel y cruce con el Excel de códigos.

- **Cruce con el Excel de códigos, implementado como búsqueda determinista,
  no como etapa de la cascada** (`app/extraccion/cruce_codigos.py`): carga
  `Expedientes.xlsx` una vez por proceso (cacheado en memoria por ruta +
  fecha de modificación), indexa por `Nº Expediente` y por `MATRIZ`
  normalizados (CLAUDE.md sección 8: recorta espacios sobrantes antes de
  comparar), y busca primero por `codigo_expediente`, luego por
  `codigo_matriz` si el primero no cruza. Se intenta **una sola vez por
  expediente** (`expedientes.codigos_cruzados` pasa de `NULL` a
  `true`/`false` y no se repite) — nuevas columnas `codigo_interno` y
  `codigos_cruzados` (migración 0006). Se ejecuta al final de
  `ejecutar_extraccion_expediente`, y de forma perezosa (mismo helper,
  `asegurar_cruce_codigos`) sobre expedientes ya procesados antes de que
  existiera esta columna, en `/expedientes`, `/catalogo` y en la
  exportación — así no hace falta reprocesar nada para que el cruce
  aparezca. **Verificado con el Excel real de `Ejemplo/Input/`:** los dos
  expedientes de prueba cruzaron (`23025` y `24039`), sin tocar código.
- **`Nombre del proyecto` no se extraía todavía (columna del esquema,
  sección 7, pero ningún extractor la rellenaba).** Añadido
  `objeto_contrato` a `extraer_campos_anuncio_pcsp` (etiqueta fija
  `"Objeto del Contrato: ... \nDescripción"`, limpia) y
  `extraer_objeto_contrato_lc27` — **hallazgo nuevo:** la Propuesta LC.27 y
  la Resolución de Adjudicación (plantilla `L9_AF.01-FE`, `docs/hallazgos-scraping.md` sección 17) no
  tienen una etiqueta "objeto" en la portada (el texto viene partido a dos
  columnas por el layout del PDF), pero **ambas repiten el objeto limpio,
  en una sola pasada de texto, en el bloque "IDENTIFICACIÓN DEL DOCUMENTO"
  de la página de firmas**: `"PROPUESTA DE ADJUDICACIÓN DEL CONTRATO DE
  <objeto> EXPEDIENTE..."` / `"RESOLUCIÓN DE ADJUDICACIÓN DEL CONTRATO DE
  <objeto> EXPEDIENTE..."` — mismo patrón en las dos plantillas. Prioridad
  igual que los importes: Anuncio PCSP gana si existe. **Verificado contra
  los tres documentos reales de fixture** (`6.24/28510.0103` con matriz,
  Propuesta de `6.24/28510.0008`, Propuesta UTE de `6.24/28510.0088`,
  Resolución de `6.24/28510.0124`) y, al reprocesar en el contenedor real,
  contra los dos expedientes ya en base de datos.
- **De paso, mismo cambio: Propuesta LC.27 y Resolución de Adjudicación
  ahora comparten la extracción de importes** (`elif item.tipo in
  (propuesta_lc27, resolucion_adjudicacion)`, antes solo miraba
  `propuesta_lc27`). Antes de este cambio, un expediente con **solo**
  Resolución (sin Propuesta LC.27 ni Anuncio PCSP) no habría podido sacar
  importe de licitación/adjudicación de ningún sitio — hueco real, no
  hipotético, dado que `docs/hallazgos-scraping.md` sección 17 documenta que a veces solo existe uno
  de los dos documentos de adjudicación.
- **`Código del material`: solo la parte determinista implementada
  (CLAUDE.md sección 6), sin ruta a modelo todavía**
  (`app/extraccion/codigo_material.py`). Vocabulario inicial: los cuatro
  ejemplos literales de la sección 6 (`BRIDA`, `PLACA`, `JUNTA`,
  `SUPLEMENTO`) más los sustantivos que sí aparecen en el corpus de prueba
  fijo (`GUANTE`, `TRAVIESA`, `BALASTO`, `TIRAFONDO`, `TORNILLO`,
  `ARANDELA`, `GRAPA`). Si la primera palabra de la descripción no está en
  el vocabulario, hoy queda `None` en vez de llamar al modelo — **la
  ampliación de vocabulario vía modelo queda sin implementar**, porque
  ningún caso del corpus de prueba la necesitó todavía (los dos
  expedientes reales reprocesados sacaron `GUANTE` sin fallar ninguno).
  Cuando aparezca un caso real sin casar, este es el sitio a tocar.
- **API nueva**, todas detrás de `get_current_user` (costura de
  autenticación, sección 9.7) igual que las rutas existentes:
  - `GET /catalogo` — filtros `expediente`, `lote`, `matricula`, `q`,
    paginado. Sin filtro de `expediente`, `matricula` ya busca a través de
    todos los expedientes (la pregunta que ADIF realmente tiene, sección
    11.5) — es el mismo endpoint, no uno aparte.
  - `GET /catalogo/exportar.xlsx` — genera el Excel a demanda desde la base
    de datos (sección 9.8), paginando la consulta interna en lotes de 500
    para no cargar el catálogo entero en memoria de golpe.
  - `GET /revision`, `GET /expedientes/{id}/revision`,
    `POST /expedientes/{id}/revision/confirmar` (con o sin corrección —
    recalcula `precio_adjudicado` de todo el lote si la baja cambia),
    `PATCH /catalogo/lineas/{id}`, `POST /catalogo/lineas/{id}/confirmar`.
  - `GET /documentos/{id}/archivo` — único punto por el que la web puede
    servir un PDF (sección 9.1: la web nunca toca un PDF directamente).
- **Web**: `/catalogo` (búsqueda por matrícula en primer plano, tabla con
  filtros, panel de trazabilidad al pinchar una línea — documento, página,
  fragmento, enlace directo al PDF) y `/revision` (lista de expedientes
  pendientes, detalle con documentos enlazados, formulario de corrección y
  confirmación por expediente, confirmación por línea). Tipografía base
  subida a 17px y contraste alto en toda la web (encargo de esta sesión:
  legible en una pantalla compartida a distancia).
- **Verificado de extremo a extremo contra el stack real** (`docker compose
  up`, sin dobles de test): reprocesados los dos expedientes ya en base de
  datos, `GET /catalogo/exportar.xlsx` descargado y abierto con
  `openpyxl` dentro del contenedor — las once columnas y su orden coinciden
  exactamente con `Ejemplo/Output/receipts_20262215070445.xlsx`, con datos
  reales rellenos (`23025`, `SUMINISTRO DE GUANTES CONTRA RIESGO
  ELÉCTRICO.`, `GUANTE`, precios reales). Las tres páginas web
  (`/`, `/catalogo`, `/revision`) responden 200 y renderizan contenido real
  contra la API en contenedor.
- **Pendiente de la sección 16 de CLAUDE.md, sin resolver todavía:** si `Precio unitario`
  en el Excel de salida debe ser el licitado o el adjudicado. Esta sesión
  usa el licitado (`precio_unitario` tal cual, sin aplicar la baja) porque
  es la lectura literal de la tabla de la sección 7 ("Precio unitario |
  Cuadro de precios | No"); es una decisión de esta sesión, no una
  confirmación del cliente — sigue marcado como pendiente.

---

## 19. Extracción por lote (sesión 2026-09-02)

Disparada por el expediente real `6.25/28510.0027` ("SUMINISTRO DE BALASTO...
6 LOTES"): su Resolución de Adjudicación es multi-lote (LOTE 1 al 7,13 %,
LOTE 3 al 1,18 %, presupuestos distintos), y el motor se quedaba con la
primera baja que encontraba en el texto y la presentaba como la del
expediente entero — **dato incorrecto, no solo incompleto**. `lotes` existía
en el esquema desde el esqueleto pero no se usaba.

- **Etapa 2, camino multi-lote** (`app/extraccion/lotes.py`): la Resolución
  declara cada lote en un bloque autocontenido ("En el LOTE N... con una
  baja del X%... Base imponible... €"), anclado a la frase literal "En el
  LOTE" (no a cualquier mención suelta de "LOTE N", que también aparece sin
  baja cerca en la cabecera "DATOS DE LA LICITACIÓN" y en la tabla de
  presupuesto). El importe de licitación por lote sale de una tabla aparte
  ("Presupuesto de licitación: BASE IMPONIBLE IVA..."), con filas que
  empiezan la línea por "LOTE N" — arregla de paso la regex
  `_IMPORTE_LICITACION_RE` de `campos_lc27.py`, que fallaba con cualquier
  cabecera de tabla en medio. Si no aparece ningún "En el LOTE N", cae al
  camino de siempre: un único lote implícito (`LOTE_UNICO`), sin cambiar
  nada para los expedientes ya soportados.
- **Etapa 3.5, asociación de tabla de precios a su lote**
  (`app/extraccion/lote_tabla.py`): por la **posición de la tabla en la
  página** (la caja delimitadora que da `pdfplumber`), nunca por proximidad
  textual. Cada tabla tiene una franja vertical propia (desde el fondo de la
  tabla anterior en la misma página hasta su propio techo); si en esa franja
  aparece una única cabecera "LOTE N", esa tabla es de ese lote. Si aparecen
  cero o varias, la tabla es ambigua y sus líneas quedan huérfanas
  (`lote_id = NULL`, nunca un lote inventado ni asignado por cercanía).
- **Sin lote centinela.** Una línea sin lote determinable no cuelga de un
  lote "SIN_DETERMINAR" (contaminaría `lotes`, tabla de negocio, con un
  estado de proceso): `lineas_catalogo.lote_id` pasa a admitir NULL
  (migración 0007), y se añade `lineas_catalogo.expediente_id` directo
  (antes el único camino hasta el expediente era `lote_id -> lotes.expediente_id`,
  que una huérfana no tiene) y `lineas_catalogo.motivo_revision` (por qué
  esa línea no tiene lote, distinto de `comentarios`).
- **Herencia de lote entre páginas: deliberadamente sin implementar.**
  Cuando la franja está vacía de texto (posible tabla partida entre
  páginas) sería técnicamente inequívoco heredar el lote de la tabla
  anterior, pero es la única regla que infiere en vez de leer el documento
  directamente. **Medido sobre el corpus completo (45 expedientes, ~187
  PDFs) antes de decidir: cero casos de "banda vacía"** — de las 7 tablas de
  precios del único expediente multi-lote del corpus, las 2 que no se
  asociaron por falta de cabecera tenían la franja con texto (solo sin
  ninguna cabecera "LOTE N" reconocible), nunca vacía. La cautela no costó
  nada en este corpus y la regla de herencia no habría resuelto ni siquiera
  ese caso concreto: no se implementa.
- **`baja_variable_por_lote`** (nueva columna en `expedientes`, migración
  0007): cuando 2+ lotes tienen baja distinta entre sí, `baja_global` queda
  en `None` a propósito (CLAUDE.md sección 4: nunca se inventa una media) y
  este booleano se lo dice explícitamente a la web — nunca se deja un campo
  vacío sin explicar, que parecería un fallo de extracción.
- **Medido sobre el corpus completo de 45 expedientes** (script puntual, no
  en el repo): **1 de 45 expedientes es multi-lote** (el propio
  `6.25/28510.0027`) y **ninguna Propuesta LC.27 del corpus es multi-lote**
  — el patrón "En el LOTE N" de `lotes.py` se aplica también a LC.27 por si
  aparece alguna vez, pero **sigue sin verificar contra un documento real**
  (CLAUDE.md sección 16): si aparece una LC.27 multi-lote con redacción distinta, ese
  módulo es el sitio a revisar.
- **Bug real encontrado y corregido al verificar contra el stack real:**
  varias tablas ambiguas del mismo documento (LOTE 2, 4, 5 y 6 del Pliego,
  ninguno declarado por la Resolución) comparten `codigo_precio` — el mismo
  cuadro de precios se repite por lote (CLAUDE.md sección 3). Sin lote que las
  separase, `_combinar_por_clave` las fundía entre sí por `clave_linea` a
  secas (las 28 líneas huérfanas del expediente real colapsaban a 6 filas,
  perdiendo datos reales de lotes distintos). Arreglado en
  `pipeline_anejo.py`: las líneas huérfanas llevan la posición de su tabla
  de origen (página + franja vertical) anexada a `clave_linea`, para que
  huérfanas de tablas distintas nunca se confundan entre sí aunque
  compartan código de precio.
- **Verificado de extremo a extremo contra el stack real** (`docker compose
  up`, migración 0007 aplicada, expediente `6.25/28510.0027` reprocesado):
  la API y la web muestran sus dos lotes con las bajas correctas — LOTE 1 al
  7,13 %, LOTE 3 al 1,18 % — con "Varía por lote" en vez de una baja única
  inventada, y las 28 líneas huérfanas (sin lote determinable) mandan el
  expediente a `pendiente_revision` con el motivo detallado por tabla.

---

## 22.2 Los 21 en revisión: por impacto (parte de la sesión de expedientes sin publicar, 2026-09-03)

Ver `docs/identidad-expediente.md`, sección 22, para el resto de esta
sesión (marca `sin_publicar` y medición final sobre 31 expedientes). Este
apartado cubre solo la segunda mitad del encargo de esa sesión: atacar por
impacto las causas ya identificadas en `docs/analisis-corpus.md` que dejaban
21 expedientes en revisión.

Atacados en el orden que pedía el encargo — el que más expedientes
desbloquea primero.

**a) Otros formatos de código de precio (`app/extraccion/tabla.py`).**
`_CODIGO_PRECIO_RE` solo reconocía `P-NNN` (con guion ASCII o Unicode, CLAUDE.md sección
3). Verificado contra el corpus real completo antes
de tocar el regex — no adivinado —, los formatos reales que aparecen son:

| Formato | Ejemplo real | Expediente |
|---|---|---|
| `P` + dígitos, sin separador | `P1`, `P2` | `6.24/28510.0047` |
| `P` + dígitos, dos cifras | `P01`, `P02` | `6.24/28510.0187` |
| `PN` + dígitos | `PN001`..`PN018` | `6.24/28510.0180` |
| `PA-` + dígitos (partida alzada numerada) | `PA-01`, `PA-02` | `6.24/28510.0094` |
| `L` + dígitos + `-T` + dígitos (lote+tipo, no es semánticamente "código de precio" per CLAUDE.md sección 3, pero identifica la fila igual) | `L01-T01`..`L03-T19` | `6.24/28510.0094` |
| Sin ninguna columna de código: la matrícula de 9 dígitos identifica la fila | `642910100` | `6.20/28510.0136` |

`_CODIGO_PRECIO_RE` pasa a `^(?:P-?\d+|PN\d+|PA-\d+|L\d+-T\d+)$`, y
`_es_fila_de_datos` acepta además una matrícula de 9 dígitos exacta
(`_MATRICULA_DATO_RE`) como señal alternativa de fila de datos, para las
tablas que no traen columna de código en absoluto.

**Intento revertido, documentado como guarda de regresión**: se probó
también añadir `"codificacion del precio"` a los alias deterministas de
`codigo_precio` en `mapeo_cabecera.py` (docs/analisis-corpus.md ya señalaba
esta cabecera como una de las 5 que hoy resuelve el modelo). **Revertido**:
rompía `ANEJO_PRECIOS_BALASTO_MULTI_LOTE` (lote 3, `6.25/28510.0027`) en los
tests — esa tabla real tiene una columna fantasma cuyo índice no coincide
entre la fila de cabecera y las filas de datos, y el mapeo determinista (que
solo mira la posición del texto de cabecera) extraía `precio_unitario=None`
donde el modelo sí acierta porque ve filas de ejemplo, no solo la cabecera.
**No se necesitaba de todas formas**: el bloqueo real de los 5 expedientes de
esta sesión con esta cabecera estaba en la etapa 4 (row de datos, arriba),
no en la etapa 5 — una vez la tabla se localiza, cae al modelo como ya
estaba diseñado (CLAUDE.md sección 6), se cachea, y no hace falta el atajo
determinista. `tests/extraccion/test_mapeo_cabecera.py` guarda este caso
explícitamente para que no se repita el intento.

**b) Umbral de densidad numérica, etapa 3 (`app/extraccion/localizador.py`).**
Con el arreglo de (a) ya desplegado, `6.24/28510.0187` seguía sin ninguna
línea: su página de cuadro de precios (2 líneas, `P01`/`P02`) trae un párrafo
largo de prosa introductoria que diluye la densidad numérica a 0,0253, por
debajo del umbral de 0,04. **Medido sobre el corpus real completo antes de
bajar el umbral, no a ciegas**: con un umbral de 0,025, pasan a ser
candidatas 233 páginas más que con 0,04, de las cuales solo 15 (6,4%) traen
una tabla real — las otras 218 no cuestan más que un `find_tables()` vacío,
porque `extraer_tablas_pagina` ya descarta sin fila reconocible cualquier
tabla espuria. Umbral bajado a **0,025**. Beneficio medido, no solo el caso
que disparó el cambio: además de `6.24/28510.0187`, recupera un cuadro de
precios real en `6.24/28510.0116_ANEJO_1.pdf` (páginas 18 y 22, antes sin
ninguna página candidata en todo el expediente) y las dos primeras líneas de
LOTE 1 en el fixture real `6.25/28510.0027` (`ANEJO_PRECIOS_BALASTO_MULTI_LOTE`),
que antes se perdían por completo — el test de la sección 19 de arriba
se actualiza para reflejar el comportamiento correcto, no el limitado.

**c) Redacciones alternativas de la baja (`app/extraccion/baja.py`).**
Encargo explícito de esta sesión, con un caso concreto que viene de otra
fuente (no del corpus de PDFs de este proyecto): el símbolo de porcentaje
pegado a la etiqueta, no al número (`"% de baja:    12,5"`), y cuatro
variantes de etiqueta más (`"% baja adjudicado"`, `"% total de baja"`,
`"baja ofertada"`, `"porcentaje de baja"`). `_BAJA_ETIQUETA_RE` es un
segundo patrón, más laxo a propósito, que solo se intenta si `_BAJA_RE` (la
frase estricta "baja del N% ... precios unitarios") no encontró nada en
ningún documento del expediente — nunca antes, para no ganarle a un caso que
ya resuelve el patrón estricto. La variante `"de baja"` sola (sin la
subordinada "precios unitarios" que la distinguiría) exige el símbolo `%`
pegado a la etiqueta como ancla: sin él, "de baja" también aparece en
boilerplate laboral de pliegos ("el trabajador que se encuentre de baja
médica..."), y el `%` pegado a la etiqueta es justo la señal que lo distingue
de esa prosa. Las otras cuatro variantes son frases lo bastante específicas
para no necesitar esa misma ancla. Probado con fixtures sintéticos de texto
(no PDF: no hace falta un documento real para una expresión regular sobre
texto ya extraído), incluida una prueba explícita de que la variante laboral
NO dispara el patrón.

**d) Documento escaneado (`app/extraccion/texto.py`).** Ver CLAUDE.md secciones 3 y 15
de este documento. `es_documento_escaneado` (umbral de caracteres extraídos,
no cero exacto) marca `6.20/28510.0136_ANEJO_2.pdf` aparte, con un motivo
("documento escaneado, sin capa de texto") distinto de "no se extrajo
ninguna línea de catálogo" — antes ambos casos se confundían en el mismo
mensaje genérico. El documento se salta en la etapa 4 (nunca se abre con
`procesar_anejo`, que no encontraría nada) en vez de intentarlo igual.

### Fixtures de regresión

`engine/tests/fixtures/pdfs/`, seis recortes nuevos de documentos reales
(nunca el documento completo — CLAUDE.md sección 13):

- `6.24_28510.0047_ANEJO_1_p18.pdf`, `6.24_28510.0187_ANEJO_1_p11.pdf`,
  `6.24_28510.0180_ANEJO_1_p18.pdf`: una página cada uno, los tres formatos
  `P1`/`P01`/`PN00N`.
- `6.24_28510.0094_CONTRATO_1_p112-113.pdf`: dos páginas del Contrato real
  (2,8 MB / 118+ páginas) con `L0N-T0N` y `PA-NN` en la misma tabla.
- `6.20_28510.0136_ANEJO_3_p3.pdf`: tabla real sin columna de código, solo
  matrícula.
- `6.20_28510.0136_ANEJO_2_p1.pdf`: una página del documento escaneado real.

`tests/extraccion/test_tabla.py` (5 casos nuevos), `test_texto.py` (nuevo,
4 casos), `test_localizador.py` (1 caso), `test_mapeo_cabecera.py` (1 caso,
la guarda de regresión del intento revertido), `test_baja.py` (7 casos),
`test_orquestador.py` (2 casos nuevos + 1 actualizado para el umbral),
`test_herencia_matriz.py` (2 casos), `tests/scraping/test_job.py` (nuevo,
2 casos: `sin_publicar` agota intentos, un error genérico no). Ningún PDF
nuevo de más de 2 páginas.

---

## 29. Filas fantasma del catálogo, ruido de la columna de revisión, orden de
    expedientes y limpieza del clon viejo (sesión 2026-09-04)

### 1. Filas fantasma: no todas eran relleno — una era un bug de mapeo real

Encargo inicial: descartar en la extracción cualquier fila sin descripción
**y** sin precio (variante silenciosa del problema ya resuelto con los pies
de tabla, CLAUDE.md sección 3), contar cuántas había en base de datos y
limpiarlas. **Contadas 21** antes de tocar nada
(`descripcion` vacía y `precio_unitario` nulo).

Antes de aplicar el filtro a ciegas se investigaron las 21 una a una (nunca
a bulto): **19 eran relleno real** — continuaciones de una descripción
envuelta entre "filas" de `pdfplumber` (expediente `6.20/28510.0136`) y
filas TOTALES de pie de tabla sin ninguna etiqueta que
`_ETIQUETAS_PIE_TABLA` reconociera (expedientes `6.23/28510.0066` y
`6.23/28510.0109`, cuadro de balasto por lote) — pero **2 no lo eran**
(`6.24/28510.0187_ANEJO_1.pdf`, página 11, lote de tapas de canaleta): su
`fragmento` traía código, descripción, cantidad y precio reales (0,90 €/dm3
y 41.100,00 €), con todos los campos estructurados en `NULL`. Causa raíz
verificada reproduciendo la extracción real con `pdfplumber` dentro del
contenedor: el modelo mapeó `descripción`/`precio_unitario` a la columna
donde cae el TEXTO de la cabecera (centrado), pero en esa tabla concreta los
DATOS caen alineados a la izquierda, una columna antes, dentro del mismo
grupo de columnas — un desplazamiento de exactamente `-1` en las 5 columnas
semánticas a la vez, consistente para toda la fila. Aplicar el filtro tal
cual habría borrado dos líneas de catálogo reales y habría escondido un bug
de mapeo distinto detrás de una limpieza de datos — parada explícita a
pedir confirmación antes de seguir (memoria: no doblar en silencio un
hallazgo que cambia el planteamiento).

**Arreglo implementado** (`app/catalogo.py`, no se tocó
`app/extraccion/mapeo_cabecera.py` ni `tabla.py`): en vez de un parche al
motor de mapeo (arriesgado — verificado que el mismo desplazamiento, dentro
de la misma tabla del expediente `6.20/28510.0136`, varía fila a fila y no
siempre es `-1`, así que "corregir la cabecera" de forma general no es
seguro), la recuperación ocurre **por fila, en el punto de construir la
línea**: `_intentar_recuperar_desalineacion` solo se llama cuando
descripción y precio salen vacíos, prueba a desplazar el mapeo entero (nunca
solo esos dos campos, para no mezclar columnas de campos distintos) una
posición a cada lado, y solo acepta el desplazamiento si recupera a la vez
una descripción con pinta real (`_parece_descripcion_recuperable`: tiene
letras, no es un pie de tabla) y un precio parseable
(`_parece_precio_recuperable`). Si no hay señal de las dos cosas a la vez —
el caso de las 19 de relleno real, que no tienen ninguna descripción
recuperable en ninguna columna vecina — la fila se descarta como pedía el
encargo original. La línea recuperada **nunca se da por buena en
silencio**: siempre lleva `motivo_revision` explicando el desplazamiento
aplicado, para que un humano la confirme antes de exportarla al cliente.
`cache_mapeo_cabecera` no se toca — la corrección es por fila, no se
propaga como si fuera el mapeo bueno de esa cabecera.

---

## 30. Corrección de defectos de la auditoría previa: `codigo_precio`
    corrupto y líneas duplicadas (sesión 2026-09-05)

Sesión de arreglo directo sobre los tres hallazgos de gravedad alta/media de
`docs/auditoria-previa.md`. Los dos primeros ya tenían causa raíz verificada
en la auditoría; esta sesión solo confirmó el mecanismo exacto con `SELECT`
reales antes de tocar código y añadió la corrección en `app/catalogo.py`.

### 30.1 `codigo_precio` corrupto por pie de página CSV, sin disparar revisión

Verificado con `SELECT` real (`adif-postgres-1`) sobre los 2 expedientes de
la auditoría: **31 filas** con el patrón (18 en `6.23/28510.0042`, 13 en
`6.24/28510.0180` — la auditoría había contado 21+7=28 con un filtro más
estrecho; el recuento real incluye variantes que su filtro no capturaba).
El pie de página de verificación CSV del documento (una URL del tipo
`https://sede.adif.gob.es/csv/valida.jsp`) se cuela **invertido carácter a
carácter** en la celda del código de precio, con una cantidad creciente de
ruido según la fila (el sello de verificación se solapa en coordenadas de
página con la columna del código, y el solape crece o decrece según la
posición vertical de cada fila) — a veces delante del código
(`j.adilav/vscPN005`), a veces detrás (`PN004ps`), a veces partido a ambos
lados (`hneP-015elbac`). El precio y la matrícula de estas filas están
limpios; antes de esta sesión, nada validaba el formato del código y la
cadena corrupta se guardaba tal cual.

**Arreglo** (`app/catalogo._normalizar_codigo_precio`): se define el
conjunto de formatos de `codigo_precio` verificados contra el corpus real y
contra los fixtures ya existentes (`P-001` con guion, `P1`/`P01` sin guion a
1-2 dígitos, `PN001`/`PN09` con prefijo de señalización, `PA-01` partida
alzada numerada, `L01-T01` lote+tipo). Un valor que no encaja se procesa en
cascada:

1. Si dentro de la cadena aparece **exactamente una** coincidencia de un
   formato conocido y el resto de la cadena son solo letras y los símbolos
   de una URL invertida (`/`, `.`, `:`, nunca dígitos), se recupera el
   código aislado y la línea queda con `motivo_revision` explicando el
   recorte — mismo patrón que la recuperación de cabecera desalineada de la
   sección 29.
2. Si la cadena entera es ese mismo ruido sin ningún código aislable, se
   descarta (`codigo_precio = None`) con `motivo_revision`; el resto de la
   línea (matrícula, descripción, precio) no se pierde — la clave de la
   línea cae a la matrícula, como ya preveía `calcular_clave_linea`.
3. **Comprobación general** (no solo para este patrón): cualquier otro valor
   que no encaje en ningún formato conocido se conserva tal cual —podría ser
   un formato legítimo aún no catalogado— pero nunca en silencio: siempre
   con `motivo_revision`.

### 30.2 Líneas duplicadas: causa raíz confirmada, dos mecanismos distintos

La auditoría pidió investigar la causa antes de limpiar. Verificado con
`SELECT` reales que **no es un fallo de `_combinar_por_clave`** (esa función
ya fusionaba correctamente repeticiones con la misma `clave_linea`) sino que
la misma pieza física recibe una `clave_linea` **distinta** según de qué
tabla del documento viene, porque `calcular_clave_linea` prioriza
`codigo_precio > matrícula` (CLAUDE.md sección 7) y no todas las tablas que
repiten un material traen `codigo_precio` propio. Dos mecanismos reales,
verificados por separado:

**Mecanismo A — el mismo defecto 30.1, con clave distinta en cada
repetición.** `6.23/28510.0042`: el mismo material (p.ej. matrícula
`643470030`, "PAT 3 MORDAZA...") aparece en **3 páginas** de **2 documentos
distintos** (`ANEJO_3.pdf` p.3, `CONTRATO_1.pdf` p.105 y p.110 — el propio
contrato incluye el anejo de precios completo, repetido, más una vez
adicional). Antes de esta sesión, el ruido del pie de página CSV era
distinto en cada página (el solape varía con la posición), así que las 3
apariciones producían 3 `codigo_precio` corruptos distintos y por tanto 3
`clave_linea` distintas → 3 filas de catálogo para el mismo material. **El
arreglo de 30.1 resuelve este mecanismo sin necesitar nada más**: las 3
variantes se normalizan al mismo código limpio (`P-005`), así que
`_combinar_por_clave` (dentro del mismo documento) y la búsqueda por clave
exacta de `guardar_lineas_catalogo` (entre documentos distintos, vía el
`commit()` por documento ya existente) las funden en una sola fila de forma
natural. Verificado que las 10 grupos/28 líneas de `0042` no necesitan
ningún cambio adicional.

**Mecanismo B — segunda tabla técnica sin columna de `codigo_precio`, en
`6.23/28510.0018`, `6.23/28510.0102` y `6.25/28510.0016`.** Caso real
verificado, `6.23/28510.0018` lote 1, matrícula `601020180`: la tabla de la
página 12 (`ANEJO_1.pdf`) trae `codigo_precio="P-02"`; una segunda tabla de
características técnicas en la página 16 **del mismo documento** repite el
mismo material y el mismo precio (58,43 €) pero su tabla no tiene columna de
código en absoluto — no es ruido, es una tabla real sin esa columna. En
`0102` y `0016` el mismo patrón ocurre **entre dos documentos distintos**
(`ANEJO_1.pdf` con código, `ANEJO_3.pdf` sin él) — dos llamadas a
`guardar_lineas_catalogo` completamente separadas, así que ni
`_combinar_por_clave` en memoria ni la búsqueda por clave exacta pueden
verlas nunca como la misma línea: no hay corrupción que arreglar, la clave
es correcta para cada tabla por separado, solo que las dos claves
correctas describen la misma pieza real.

**Arreglo** (`app/catalogo._firma_material`, `_combinar_por_clave`,
`guardar_lineas_catalogo`): una firma de "misma pieza física"
(matrícula + descripción + precio unitario, los tres presentes) unifica la
`clave_linea` de dos líneas que la comparten, aunque una tenga
`codigo_precio` y la otra no — tanto dentro de un mismo documento
(`_combinar_por_clave`) como entre documentos distintos del mismo
expediente (`guardar_lineas_catalogo` cae a una búsqueda por firma en base
de datos cuando la búsqueda por clave exacta no encuentra nada). Al
fundirse, la clave final sube siempre a la canónica
(`codigo_precio` cuando se conoce), sin importar qué documento se procesó
primero.

**Deliberadamente NO se aplica a líneas huérfanas** (`lote_id is None`,
`permitir_fusion_material=False`): CLAUDE.md sección 27 y
`app/extraccion/pipeline_anejo.py` ya sufijan la `clave_linea` de las
huérfanas con su página y posición precisamente para que dos tablas
ambiguas de **lotes distintos** que comparten `codigo_precio` no se fundan
en una sola fila. Fundir también por matrícula+descripción+precio ahí
arriesgaría lo mismo al revés: el mismo material de catálogo, ofertado
legítimamente en dos lotes distintos de un acuerdo marco al mismo precio,
se fundiría en una sola fila perdiendo a qué lote pertenece cada oferta. La
fusión por firma solo es segura cuando `lote_id` ya es un valor conocido y
único para todas las líneas de la llamada.

**Verificado tras aplicar el arreglo y reprocesar los 4 expedientes**: 0
grupos de duplicados reales restantes (mismo lote, misma matrícula +
descripción + precio) en el corpus completo — ver el cierre de esta sesión
en `docs/decisiones.md` para el recuento final de líneas de catálogo.

### 30.3 Tests

`tests/test_catalogo.py`: casos nuevos —
`_normalizar_codigo_precio` (formato conocido, recuperación con ruido antes
y después del código, descarte sin código recuperable, formato no
reconocido conservado con motivo), `construir_linea_catalogo` con código
corrupto recuperable e irrecuperable, `_combinar_por_clave` con fusión por
firma dentro de un lote y sin fusión en huérfanas, y
`guardar_lineas_catalogo` fundiendo el mismo material entre dos documentos
distintos con la clave subiendo a la canónica.

### 30.4 Dos defectos reales encontrados al verificar el arreglo contra el
     corpus completo, antes de darlo por bueno

El encargo de esta sesión pedía reprocesar y dar el recuento final. Al
forzar el reproceso de los 42 expedientes reales aparecieron dos defectos
del arreglo de 30.1/30.2 que ningún test unitario había cubierto — los dos
se encontraron **antes** de dar la sesión por cerrada, verificando contra el
corpus real en vez de fiarse de que "pytest en verde" bastaba.

**1. Falso positivo: `codigo_precio` con una sola letra de cola no es ruido
de pie de página.** `6.24/28510.0185` trae dos tablas de precios reales del
mismo documento con la misma numeración pero sufijo `b` en la segunda
(`P-001` en la página 27, `P-001b` en la página 18) — **mismo material,
precio distinto**, dos entradas legítimas, no la misma línea repetida. La
recuperación de 30.1, tal como se implementó primero, trataba cualquier
resto de una sola letra como el mismo ruido de las URLs invertidas y
colapsaba `P-001b` en `P-001`, perdiendo un precio real. **Arreglo**: el
resto descartable como ruido exige un mínimo de 2 caracteres — los 31 casos
reales de pie de página verificados en 30.1 siempre traen 2 o más, nunca
uno solo, así que el mínimo no deja de recuperar ningún caso real. Con un
solo carácter de cola, el código se conserva tal cual y cae en la
comprobación general ("formato no reconocido, revisar"), nunca se funde a
ciegas.

**2. La fusión por firma solo miraba la primera fila candidata, no todas.**
Descubierto al reventar la constraint `uq_linea_lote_clave` en
`6.24/28510.0116` (lote 25, "P-01": dos filas para el mismo material, una
sin `codigo_precio` guardada como huérfana de clave de matrícula, otra ya
con "P-01" — subir la clave de la primera a la canónica colisionaba con la
segunda) y, ya corregido ese caso, en `6.23/28510.0042` (matrícula
`643480020`: **tres** filas heredadas de sesiones anteriores a este
arreglo, no dos — la búsqueda por firma, escrita para devolver un único
candidato con `.first()` antes incluso de saber si la búsqueda por clave
exacta había encontrado algo, se quedaba con la primera por id y dejaba la
tercera sin visitar). **Arreglo**: `guardar_lineas_catalogo` reúne TODAS las
filas que comparten firma con la que se está guardando (excluyendo la ya
encontrada por clave exacta, si la hay) y las absorbe todas en una sola
pasada — nunca dan por buena una fusión parcial de dos de tres.

Los dos arreglos tienen test de regresión propio
(`test_normalizar_codigo_precio_no_funde_sufijo_de_una_letra_con_el_codigo_base`,
`test_guardar_lineas_catalogo_absorbe_las_dos_filas_heredadas_cuando_la_clave_exacta_no_encuentra_ninguna`).
`pytest -q` dentro de `adif-api-1` tras la reconstrucción final: **274
passed, 0 fallos**. Verificado además contra el corpus real completo (42
expedientes reprocesados dos veces tras cada arreglo): `6.24/28510.0116`
vuelve a `completado` sin error, `P-001`/`P-001b` de `6.24/28510.0185`
siguen siendo dos líneas distintas y marcadas para revisión, y la matrícula
`643480020` de `6.23/28510.0042` queda en una única fila.

**Verificado contra el stack real**, no solo con tests: reconstruidas las
imágenes de `api`/`worker`, reprocesados los 5 expedientes afectados
(`6.20/28510.0136`, `6.23/28510.0051`, `6.23/28510.0066`,
`6.23/28510.0109`, `6.24/28510.0187`) vía
`POST /mantenimiento/ejecutar` con `forzar_expedientes` (sindicación
desactivada, para no tocar el resto del corpus). Las dos líneas de
`6.24/28510.0187` reaparecieron con sus datos reales
(`P01`/`Tapa de canaleta prefabricada de hormigón armado`/`0,90 €` y
`P02`/`Partida alzada.../41.100,00 €`) y `motivo_revision` explícito;
verificado también en la web filtrando por ese expediente. Las 14 filas
fantasma que sobrevivieron al reproceso sin cambiar (12 de
`6.20/28510.0136`, cuyo lote no se reconstruye entre reprocesos — su clave
de fila es un hash de `descripción + orden`, y con descripción vacía ya no
se genera en absoluto, así que la fila vieja queda huérfana; 2 rastros del
propio `6.24/28510.0187`, con clave distinta a las 2 nuevas recuperadas
porque antes no tenían `codigo_precio`) se borraron a mano con un `DELETE`
acotado a la misma condición (`descripción` vacía y `precio_unitario`
nulo), verificado a 0 filas después. **Catálogo: de 3.018 a 3.000 líneas**
(-14 fantasma borradas a mano, -6 más que desaparecieron solas como efecto
colateral de que `6.23/28510.0066`/`6.23/28510.0109` reconstruyen sus
`lotes` con id nuevo en cada reproceso de un expediente multi-lote — sin
investigar más, es comportamiento preexistente no tocado por esta sesión —,
+2 líneas reales recuperadas).

### 2. La columna de revisión, en blanco por defecto

`estado_revision` es `sin_revisar` para las 3.018 (ahora 3.000) líneas del
catálogo — nunca pasa a `pendiente` automáticamente, solo a mano vía
`POST /catalogo/lineas/{id}/confirmar` o al corregir en la cola de revisión
(`app/routers/revision.py`). La columna repetía "Sin confirmar" en cada
fila sin distinguir una línea con un problema real de una que nunca tuvo
ninguno — la señal real de "esto necesita ojos" es `motivo_revision`
(ya expuesto por la API, `LineaCatalogoOut.motivo_revision`, pero sin usar
en `CatalogoPanel.tsx`), no `estado_revision`.

`web/app/catalogo/CatalogoPanel.tsx`: `celdaRevision` — `confirmado`/
`corregido` muestran una insignia de acento (buena noticia, mismo criterio
que `ui.tsx`), `descartado` una insignia atenuada, una línea con
`motivo_revision` (el `title` del elemento lleva el texto completo) muestra
"Revisar" en tinta de atención, y **cualquier otra cosa — el caso por
defecto, casi todas las filas — no muestra nada**: mismo principio ya
documentado en `ui.tsx` ("un valor ausente se deja en blanco: un guion
suelto es ruido visual, no información"), aplicado aquí por primera vez a
esta columna. No se tocó `RevisionPanel.tsx`: ahí "Sin confirmar" sigue
siendo información real (es la cola de revisión, no el catálogo completo).

### 3. Orden de expedientes: por actividad reciente, no por fecha de alta

Antes: `ORDER BY id`, que en esta base pone primero los ~14 pedidos de
acuerdo marco `esperando_matriz`/`sin_publicar` (ver `docs/identidad-expediente.md`,
secciones 20-22, los
primeros ids de la base) — sin baja, sin nada que hacer con ellos todavía,
dando la impresión de que el catálogo arranca vacío.

Elegido `COALESCE(extraido_en, descargado_en) DESC NULLS LAST, id DESC`
(`app/routers/expedientes.py`) sobre la alternativa "completados primero":
`extraido_en`/`descargado_en` (frescura, `docs/mantenimiento-automatico.md` sección 23) ya
distinguen "se tocó de verdad" de "nunca se ha podido procesar", así que
ordenar por el más reciente de los dos pone arriba lo que tiene actividad
real — recién completado, o en curso ahora mismo — y hunde al fondo, sin
necesitar una regla aparte, lo que nunca se ha podido tocar
(`esperando_matriz`/`sin_publicar`). "Completados primero" habría enterrado
un expediente `extrayendo` ahora mismo detrás de uno `completado` hace
semanas, peor para una pantalla de seguimiento en vivo (CLAUDE.md sección
11.3). Verificado en la web: los 5 expedientes reprocesados en el punto 1
de esta sesión (los tocados más recientemente del corpus) aparecen en las
primeras filas.

### 4. Clon viejo en WSL, borrado

`/home/lucas/adif` (visto por primera vez en la sesión de pulido a 1280px,
ver `docs/decisiones.md`, sección 28) no era un repositorio git (`fatal: not a git repository`, sin
`.git`), solo el esqueleto de la sección 14 de CLAUDE.md (56 ficheros, sin
`catalogo/`/`revision/`/`mantenimiento/`) — comprobado antes de borrar que
no había nada que rescatar. Borrado con `rm -rf`. El stack real sigue
construyéndose desde `/mnt/c/dev/ADIF` sin cambios.

### Verificación

261 tests en verde dentro del contenedor `api` reconstruido (257 previos +
4 nuevos de `tests/test_catalogo.py`, sección 1 de esta sesión).
`docker compose build api worker web` + `docker compose up -d api worker
web` — **verificado con `md5sum` que el contenedor realmente corría el
código nuevo antes de fiarse de ningún resultado de test** (primer intento
de reconstruir sin recrear los contenedores dejó `adif-api-1` sirviendo
todavía la imagen vieja; los tests "en verde" de ese momento eran el
archivo de tests viejo sin mis casos nuevos, no una verificación real).
Playwright headless a 1280×900 contra el stack real: `/catalogo` filtrado
por `6.24/28510.0187` muestra las dos líneas recuperadas con "Revisar";
`/` (Expedientes) muestra los 5 expedientes reprocesados arriba; sin
desbordamiento horizontal en ninguna de las dos páginas
(`scrollWidth - clientWidth = 0`).

---

## 30.5 Diagnóstico en caliente del "problema de rendimiento" reproducido en
     vivo (sesión 2026-09-05, continuación)

Durante el reproceso de verificación de la sección 30.4, el ciclo de
mantenimiento forzado (`trabajos_cola.id = 539`) tardó 30,8 min en vez de
los ~22 min de la auditoría previa — a primera vista, la reaparición del
episodio de CLAUDE.md ("problema de rendimiento... probablemente
inestabilidad de `dockerd`"). Encargo explícito: capturar datos del proceso
real **sin interrumpirlo**, para decidir si hace falta arreglarlo antes de
la demo. Nada de lo siguiente cambia comportamiento del sistema — es
observación pura (`docker stats`, `/proc/1/status` y `/proc/1/stat` dentro
del contenedor, `pg_stat_activity`), muestreada cada ~65 s mientras corrían
dos reprocesos completos posteriores (jobs 586 y 629) con el arreglo de
30.1-30.4 ya desplegado.

### Causa real de los 30,8 min del job 539

El log del worker es inequívoco: el descubrimiento por sindicación de ese
ciclo concreto encontró **4 expedientes nuevos** en el ZIP de
`contrataciondelestado.es` y lanzó su descarga real (Playwright headless)
antes de extraer nada — `{'nuevos_descubiertos': 4, 'descargas_lanzadas':
4}`. Entre el último documento de la tanda de 38 "de siempre" (09:41 h,
hora del job) y el primero de los 4 nuevos hay un hueco de **~5,5 min** que
coincide exactamente con esa descarga. Confirmado reprocesando el corpus
DOS VECES MÁS, ambas con `sindicacion_desactivada: true` (sin red, sin
descargas): **1.464,5 s y 1.464,1 s** — 24,4 min, prácticamente idénticos
entre sí, para 42 expedientes (más que los 38 originales, porque ya
incluyen los 4 nuevos ya descargados). El "problema de rendimiento" del job
539 no era una reproducción del episodio de CLAUDE.md — era trabajo de red
real, esperado, simplemente no medido nunca antes en la misma tanda que la
extracción.

### 1-2. Memoria, descriptores de fichero, y expediente en curso

Muestras del proceso `python -m app.worker` (PID 1 dentro del contenedor)
durante el reproceso limpio (job 629, 09:36:59–10:02:56, 25 muestras):

| Momento | RSS | Pico histórico (`VmHWM`) | FD abiertos |
|---|---:|---:|---:|
| Inicio (09:36:59) | 496 MiB | 496 MiB | 4 |
| `6.23/28510.0139` en curso (09:45:38) — **pico de toda la tanda** | 2,89 GiB | 3,18 GiB | 4 |
| Resto de la tanda (09:46:43–10:01:51) | 1,24–1,52 GiB | 3,18 GiB (no vuelve a crecer) | 4 |
| Fin, proceso ocioso (10:02:56) | 1,38 GiB | 3,18 GiB | 4 |

**Los descriptores de fichero se quedan en 4 durante los 26 minutos
completos, sin una sola variación.** El pico de memoria (2,89 GiB) ocurre
en `6.23/28510.0139` — el mismo expediente que ya señaló la auditoría
previa como el más pesado real del corpus, no `6.23/28510.0051` (que en
esta tanda tardó 102 s, dentro de su baseline). Tras el pico, la memoria
baja y se queda estable en 1,2–1,5 GiB durante el resto de la tanda: **cero
indicio de fuga acumulativa**, coherente con la medición de la auditoría
previa.

### 3. Duración por expediente (job 629, orden real de ejecución)

Reconstruida con exactitud desde `documentos.procesado_en` (no desde el
muestreo de 65 s, que solo da una foto aproximada):

| # | Expediente | Duración (s) | | # | Expediente | Duración (s) |
|--:|---|--:|---|--:|---|--:|
| 9 | 6.20/28510.0136 | 6,2 | | 26 | 6.24/28510.0117 | 53,2 |
| 10 | 6.23/28510.0018 | 27,2 | | 27 | 6.24/28510.0124 | 32,4 |
| 11 | 6.23/28510.0042 | 24,7 | | 28 | 6.24/28510.0128 | 25,4 |
| **12** | **6.23/28510.0051** | **102,2** | | 29 | 6.24/28510.0130 | 58,6 |
| 13 | 6.23/28510.0066 | 52,8 | | 30 | 6.24/28510.0180 | 28,7 |
| 14 | 6.23/28510.0102 | 27,2 | | 31 | 6.24/28510.0185 | 32,8 |
| 15 | 6.23/28510.0104 | 8,1 | | 32 | 6.24/28510.0187 | 61,5 |
| 16 | 6.23/28510.0109 | 50,9 | | 33 | 6.24/28510.0193 | 15,1 |
| 17 | 6.23/28510.0129 | 28,6 | | 34 | 6.24/28510.0203 | 59,6 |
| **18** | **6.23/28510.0139** | **205,9** | | 35 | 6.25/28510.0016 | 26,2 |
| 19 | 6.24/28510.0008 | 36,4 | | 36 | 6.25/28510.0019 | 62,5 |
| 20 | 6.24/28510.0025 | 18,2 | | 37 | 6.25/28510.0027 | 52,3 |
| 21 | 6.24/28510.0047 | 10,6 | | 38 | 6.25/28510.0028 | 51,4 |
| 22 | 6.24/28510.0064 | 60,3 | | 39 | 6.20/28510.0094 | 37,5 |
| 23 | 6.24/28510.0088 | 48,2 | | 40 | 6.20/28510.0054 | 50,1 |
| 24 | 6.24/28510.0094 | 39,7 | | 41 | 4.26/28510.0020 | 76,3 |
| 25 | 6.24/28510.0116 | 25,4 | | 42 | 6.26/28510.0016 | 12,3 |

**Prácticamente idéntica a la de la auditoría previa** (`0051` en la
posición 12, `0139` el pico absoluto de toda la tanda en la posición 18,
~206 s en ambas mediciones separadas por un día) — la duración por
expediente es determinista y depende del expediente, no del orden ni de
cuántos van procesados antes: no hay degradación progresiva en ningún
punto de la serie.

### 4. CPU o bloqueado

En las 24 muestras tomadas mientras el ciclo estaba activo, `docker stats`
marcó **entre 90% y 106% de CPU en todas y cada una** (un proceso de un
solo hilo saturando un núcleo), y el estado del proceso
(`/proc/1/status`, comprobado 3 veces seguidas por muestra, separadas
0,3 s) fue **`R` (ejecutando) en las 24×3 = 72 comprobaciones**, nunca `D`
(esperando E/S) ni `S` prolongado. `wchan` (la función del kernel en la que
duerme un proceso bloqueado) fue `0` en las 24 muestras activas —
únicamente pasó a `hrtimer_nanosleep` en la última muestra, tras el
`completado` del job, que es el `sleep(3)` normal del bucle de sondeo del
worker ocioso. **Conclusión inequívoca: el proceso estuvo activo en CPU
todo el tiempo, nunca bloqueado.** Coincide con CLAUDE.md sección 16 ("activo
en CPU todo el tiempo" era compatible con inestabilidad de `dockerd`) pero
con una lectura distinta: aquí no hubo ningún bloqueo que la inestabilidad
de `dockerd` pudiera explicar — fue trabajo de CPU real y contabilizado
(scraping + extracción), no un cuelgue disfrazado de actividad.

### 5. Conexiones a la base de datos

`pg_stat_activity` mostró **3 conexiones constantes durante toda la
tanda**: la del worker (persistente, un `commit()` por documento — nunca
"idle in transaction" más de 74 s seguidos en ninguna muestra, y siempre
volviendo a 0-5 s poco después, coherente con transacciones cortas por
documento, no una transacción larga colgada) y dos del propio muestreo
(una para consultar `trabajos_cola`/`lineas_catalogo`, otra para leerse a
sí misma). **Ninguna consulta activa superó los 0 s de duración en el
momento de la muestra** — no hay ninguna query atascada ni ningún lock
largo. La cifra "segundos en la conexión actual" que crece de forma
continua en el log crudo (`docs/...adif_monitor.log`, no publicado) es la
antigüedad de la conexión persistente del worker, no el tiempo de una
consulta — column engañosa si se lee sin este contexto, aclarada aquí para
que una sesión futura no la malinterprete de nuevo.

### Conclusión y recomendación

**No hay nada que arreglar.** El episodio que pareció una reproducción del
problema de rendimiento de CLAUDE.md era, verificado con datos en caliente,
descubrimiento y descarga real de expedientes nuevos — trabajo esperado que
nunca se había medido junto con la extracción en la misma tanda. Dos
reprocesos limpios subsiguientes (sin descargas) fueron idénticos entre sí
en duración total (24,4 min ambos) y en el perfil por expediente (mismo
expediente más lento, mismas duraciones dentro de un pequeño margen), sin
ningún indicio de fuga de memoria, descriptores crecientes, bloqueo o
consulta atascada. La entrada de CLAUDE.md sección 16 sobre este tema se
actualiza para reflejar que el episodio queda explicado, no que "no se
reprodujo" — es una conclusión más fuerte que la de la auditoría previa,
alcanzada por tener, esta vez, un episodio real que diagnosticar en vivo en
lugar de solo su ausencia.
