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
