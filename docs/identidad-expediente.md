# Identidad de expediente

Registro histórico movido desde `CONTEXTO.md` (split de sesión 2026-09-05).
Ver `CONTEXTO.md` para el contexto vivo del proyecto.

---

## 20. Herencia de acuerdo marco (sesión de herencia de matriz, 2026-09-03)

Cierra (parcialmente — ver más abajo) el hallazgo 3 de
`docs/analisis-corpus.md`: 14 pedidos derivados de acuerdo marco sin cuadro
de precios ni baja propios, porque viven en los documentos de la MATRIZ.

### Modelo

- **`expedientes.matriz_expediente_id`** (FK a `expedientes.id`, migración
  `0009`): la matriz *resuelta*, distinta de `codigo_matriz` (el código de
  texto que ya se extraía — Anuncio PCSP o Excel de códigos). Se rellena la
  primera vez que `app.extraccion.herencia_matriz.resolver_o_encolar_matriz`
  identifica o crea la fila de la matriz.
- **`expedientes.matriz_conflicto`**: cuando el Anuncio PCSP propio y la
  columna MATRIZ del Excel declaran una matriz distinta entre sí (requisito
  1 del encargo: "si discrepan, a revisión"). Antes de esta sesión,
  `asegurar_cruce_codigos` solo usaba la MATRIZ del Excel como reserva si el
  Anuncio no traía ninguna — nunca comparaba las dos fuentes.
- **Estado nuevo `esperando_matriz`** (enum `estado_expediente`, valor
  añadido por `ALTER TYPE ... ADD VALUE`, no reversible): un pedido cuya
  matriz el sistema ya está resolviendo solo (creándola, encolando su
  descarga o su extracción). Distinto de `pendiente_revision` — ese
  significa "hace falta un humano", este "ya se está resolviendo".
- **`lotes.baja_heredada_de_matriz`** y **`lineas_catalogo.heredado_de_matriz`**:
  booleanos de lectura rápida para la web. La trazabilidad real no depende de
  ellos — `documento_origen_id`/`pagina`/`fragmento` de cada línea heredada
  siguen apuntando al documento real de la matriz, copiados tal cual al
  copiar la línea.
- **Copiar, no referenciar.** Las líneas heredadas se materializan como
  `LineaCatalogo` normales del pedido, vía el mismo `guardar_lineas_catalogo`
  idempotente de siempre (mismo mecanismo, misma clave). Se descartó
  referenciar en caliente porque todo el sistema ya es snapshot-y-traza
  (CONTEXTO.md sección 9), y porque `/catalogo` y la exportación pagan directo sobre
  `lineas_catalogo` sin saber resolver "esta línea vive en otro expediente".
- **"Lo propio del pedido manda" se decide a nivel de tabla completa, no
  fila a fila**: si el pedido ya aportó alguna línea propia a su lote, no se
  mezcla con las de la matriz — se manda a revisión con el conteo exacto de
  líneas de cada lado (ajuste 3 de la sesión de diseño: "sin ese dato, quien
  revise no puede decidir"). Solo se hereda la tabla completa cuando el
  pedido no aportó ninguna línea propia. Lo mismo con la baja: la propia
  gana si existe.
- **Matriz multi-lote sin dato en el pedido para elegir uno: a revisión**,
  nunca se asigna a ciegas.
- **Protección contra ciclos** (ajuste 1 de la sesión de diseño):
  `_forma_ciclo` corta antes de crear o seguir una matriz si el pedido se
  referencia a sí mismo, o si la cadena de matrices (A -> B -> A, o más
  larga, tope de 10 saltos) vuelve sobre un expediente ya visitado. Resultó
  ser el caso dominante del corpus real — ver más abajo.
- **Descarga de la matriz** (ajuste 1): si la matriz no existe como
  expediente, se crea y se encola su descarga (`descargar_expediente`, que
  ya encadena a `extraer_expediente` sola, `app/scraping/job.py`); si ya
  existe con documentos pero sin procesar, se encola directamente su
  extracción. Un `TrabajoCola` activo del mismo tipo para esa matriz evita
  encolar por duplicado (dos pedidos pueden compartir matriz).
- **`reencolar_pedidos_esperando_matriz`**: al terminar el procesamiento de
  un expediente que resulta ser matriz de otros — con cualquier desenlace,
  `completado`, `pendiente_revision` o `fallido` -, se reencola la
  extracción de los pedidos que estaban `esperando_matriz` de él. Dispara
  tanto al final de `ejecutar_extraccion_expediente` (éxito y fallo) como en
  el `except` de `ejecutar_scraping_expediente` (si la matriz falla ya en la
  descarga, antes de llegar nunca a generarse un trabajo de extracción que
  disparase el reencolado normal — sin este segundo punto, esos pedidos se
  quedarían `esperando_matriz` para siempre).
- **Límite conocido, no un descuido (ajuste 2 del encargo): reprocesar una
  matriz ya resuelta a mano no refresca sola a los pedidos que ya heredaron
  de ella.** `reencolar_pedidos_esperando_matriz` solo dispara cuando la
  matriz *termina un trabajo de extracción* — un reproceso posterior de una
  matriz que ya estaba `completado`/`pendiente_revision`/`fallido` no tiene
  ningún gancho que avise a sus pedidos. Si hace falta, hay que reencolarlos
  a mano. No se implementó un listener permanente a propósito: sería más
  alcance del que pide el encargo.

### Verificación contra el corpus real: 0 de 14 pedidos resueltos, y por qué

Reprocesados los 45 expedientes reales desde cero (worker real, scraping
real habilitado, sin dobles de test). Resultado idéntico al de antes de esta
sesión en todos los agregados — **cero cambio neto**, porque ningún pedido
llegó a heredar nada:

| | Antes | Después |
|---|---:|---:|
| `completado` | 10 | 10 |
| `pendiente_revision` | 35 | 35 |
| Líneas de catálogo | 2.041 | 2.041 (+0) |
| Matrículas en >1 expediente | 13 | 13 |
| Matrices nuevas descubiertas | — | **0** |
| Trabajos `descargar_expediente` encolados | — | **0** |

**Los 14 pedidos derivados reales de este corpus se reparten en dos
bloqueos, ninguno resuelto:**

- **7 sin ningún documento** (`2.24/28520.0128`, `2.25/28520.0161`,
  `3.24/20810.0090`, `3.24/28520.0129`, `3.25/27520.0055`,
  `4.24/27520.0090`, `6.25/28510.5001_01`): sin documentos que leer, y el
  cruce con el Excel de códigos (que sí se intenta ahora incluso sin
  documentos, requisito 1 del encargo) tampoco les encuentra una MATRIZ. No
  hay ningún dato del que partir — motivo sin cambios, "extracción encolada
  sin documentos descargados para este expediente". Causa raíz sin
  verificar, igual que antes (hallazgo 3 de `docs/analisis-corpus.md`: por
  qué el scraping no descargó nada para estos 7).
- **8 con 2 documentos PCSP, todos cortados por autorreferencia**
  (`2.18/04703.0019`, `0021`, `0022`, `0024`, `0025`, `2.24/04110.0035`,
  `0036`, `0037`): **hallazgo nuevo, verificado leyendo el documento real**
  (`2.18_04703.0019_ADJUDICACION_1...pdf`): su "Licitación basada en el
  acuerdo marco → Expediente" declara literalmente `2.18/04703.0019` — el
  mismo código que ya tiene `expedientes.codigo_expediente` para esta fila.
  No es un dato corrupto ni una matriz mal declarada: es que **la fila de
  este expediente en la base de datos está etiquetada con el código de la
  MATRIZ, no con el del pedido** — el código real del pedido
  (`6.24/28510.0103` en este caso) solo existe dentro del texto del
  documento, en el campo "Número de Expediente"
  (`campos_pcsp.CamposAnuncioPcsp.numero_expediente`), que hoy se extrae
  pero **nunca se usa ni se guarda en ningún sitio**. `_forma_ciclo` detecta
  la autorreferencia y corta, tal como se diseñó (requisito 1 de la sesión
  de diseño: "protege contra el ciclo") — el mecanismo de herencia funciona
  exactamente como se pidió, pero no puede resolver estos 8 casos reales
  porque la premisa de la que parte ("codigo_expediente identifica al
  pedido, codigo_matriz a su matriz") no se cumple para ellos. Es
  exactamente el mismo síntoma que ya documentaba el hallazgo 3 del corpus
  ("el propio texto del Anuncio PCSP declara un 'Número de Expediente'
  distinto del `codigo_expediente` guardado"), confirmado ahora como la
  causa exacta del bloqueo, no solo una curiosidad del dato.
- **Cero conflictos de matriz** (`matriz_conflicto`) en las 45: en ningún
  caso el Anuncio PCSP y el Excel discreparon.

**Resuelto en la sesión de corrección de identidad (sección 21 más abajo):** la
decisión fue renombrar `codigo_expediente` al valor real en el sitio (no
crear una fila nueva) — es seguro precisamente porque ninguna otra tabla
referencia el código como clave externa (todas usan `expediente_id`), así
que renombrar no duplica ni pierde nada de lo ya extraído. Ver sección 21
para el mecanismo y la verificación contra los 8 casos reales.

### Fixtures de regresión

`engine/tests/extraccion/test_herencia_matriz.py`, 15 casos: las tres
funciones del módulo por separado (creación/encolado de matriz, herencia con
trazabilidad, protección de ciclo simple y de cadena) y dos de extremo a
extremo con el fixture real `ANUNCIO_PCSP_CON_MATRIZ`
(`2.18_04703.0019_ADJUDICACION_1.pdf`, el mismo documento real que destapó el
hallazgo de la autorreferencia) contra `ejecutar_extraccion_expediente`. No
hizo falta ningún PDF nuevo.

---

## 21. Corrección de identidad de expediente, y reingesta de los 7 sin
    documentos (sesión 2026-09-03)

Ataca junto los dos bloqueos de la sección 20 y del hallazgo 3 de
`docs/analisis-corpus.md`, en el orden que pedía el encargo: primero corregir
la identidad, después reingerir. Verificado de punta a punta contra el stack
real (contenedor Linux, Postgres real, imágenes reconstruidas con el código
nuevo) y contra la Plataforma real (scraping real, sin dobles de test).

### 1. Regla: el código de expediente sale del documento, nunca del término de búsqueda

**Nuevo módulo `app/extraccion/identidad_expediente.py`**, invocado en
`ejecutar_extraccion_expediente` justo después de clasificar los documentos y
antes de cualquier otro dato que dependa de la identidad (importes, baja,
matriz declarada, cruce con el Excel). Si los Anuncio PCSP propios del
expediente declaran un "Número de Expediente" (`campos_pcsp.numero_expediente`,
ya se extraía, nunca se usaba) distinto del `codigo_expediente` guardado,
corrige la fila **en el sitio**: el código del documento pasa a ser
`codigo_expediente`, y el código con el que estaba registrado (en la
práctica, siempre el de su MATRIZ) pasa a `codigo_matriz` si no había uno ya
declarado distinto (si lo había, se marca `matriz_conflicto` en vez de
pisarlo en silencio, mismo criterio que `asegurar_cruce_codigos`).

Nunca corrige a ciegas: si los distintos Anuncio PCSP de un mismo expediente
declaran códigos distintos entre sí, o si el código real ya pertenece a otra
fila (un caso de fusión, no de renombrado — no implementado, fuera de
alcance), se deja la identidad como está y se añade un motivo a la cola de
revisión en vez de adivinar.

**Por qué renombrar en el sitio es seguro**: `codigo_expediente` es la clave
de idempotencia (CONTEXTO.md sección 9.9) pero no es clave externa de ninguna otra tabla
— `documentos.expediente_id`, `lotes.expediente_id`,
`lineas_catalogo.expediente_id` y `trabajos_cola.expediente_id` son todos por
`id`. Renombrar la fila no mueve ni un documento, ni un lote, ni una línea de
catálogo ya extraída.

**Por qué solo en la extracción, no en el scraping ni en un paso de
"ingesta" aparte**: la identidad real solo se conoce leyendo el texto del
Anuncio PCSP, y eso ya es exactamente la etapa 2 de la cascada (CONTEXTO.md sección 5).
El scraping descarga bytes sin leerlos; no hay nada que corregir ahí. Un
expediente se registra por primera vez con el código que se tenga a mano —
casi siempre el término de búsqueda, sea por la web (`POST /expedientes`) o
por `herencia_matriz.resolver_o_encolar_matriz` creando una matriz — y esta
función es lo que lo corrige la primera vez que sus propios documentos se
leen de verdad.

### 2. Verificación contra los 8 casos reales

Antes de escribir código, se extrajo a mano (dentro del contenedor `api`,
con las funciones ya existentes) el "Número de Expediente" real de los 16
documentos de los 8 expedientes mal etiquetados. Los 8 son pedidos
**distintos** con matrices **distintas**, no el mismo caso repetido:

| Fila mal etiquetada (antes) | Código real (`numero_expediente`) | Matriz real |
|---|---|---|
| `2.18/04703.0019` | `6.24/28510.0103` | `2.18/04703.0019` |
| `2.18/04703.0021` | `6.24/28510.0100` | `2.18/04703.0021` |
| `2.18/04703.0022` | `6.24/28510.0101` | `2.18/04703.0022` |
| `2.18/04703.0024` | `6.24/28510.0102` | `2.18/04703.0024` |
| `2.18/04703.0025` | `6.24/28510.0111` | `2.18/04703.0025` |
| `2.24/04110.0035` | `6.25/28510.0215` | `2.24/04110.0035` |
| `2.24/04110.0036` | `6.25/28510.0175` | `2.24/04110.0036` |
| `2.24/04110.0037` | `6.25/28510.0248` | `2.24/04110.0037` |

Ninguno de los 8 códigos reales existía ya como fila separada (comprobado
por consulta directa antes de tocar nada): no hacía falta el camino de
fusión, un simple renombrado bastaba. Tras reconstruir las imágenes con el
código nuevo y reencolar `extraer_expediente` para los 8: **los 8 se
renombraron correctamente**, cada uno con su `codigo_matriz` puesto al valor
antiguo y su `matriz_expediente_id` enlazado a una fila de matriz nueva (no
duplicada) — verificado en base de datos, no solo en test.

### 3. Reingesta de los 7 expedientes sin documentos

`6.25/28510.5001_01` **descartado sin lanzar scraping**: no tiene forma de
expediente válida (`CODIGO_EXPEDIENTE_RE`, `\d+\.\d+/\d+\.\d+`) — el sufijo
`_01` lo delata como algo distinto de un código de la Plataforma.

Los otros 6 (`2.24/28520.0128`, `2.25/28520.0161`, `3.24/20810.0090`,
`3.24/28520.0129`, `3.25/27520.0055`, `4.24/27520.0090`) se lanzaron contra
la Plataforma real vía `POST /expedientes/{id}/descargar` (scraping real,
Chromium headless, sin ningún doble). **Resultado: 6 de 6 no encontrados**,
cada uno agotando sus reintentos con
`"no encontrado en la Plataforma ni por matriz ni por expediente: <código>"`
— el mismo error que ya lanzaba `scrape_expediente` cuando ninguna variante
de búsqueda (`search_variants`: separadores `/`, `_`, `-`, sin separador)
encuentra una fila en la tabla de resultados. **La causa raíz que
`docs/analisis-corpus.md` dejaba sin verificar queda verificada, en un
sentido negativo**: no es un defecto del scraper (mismo código que sí
encuentra los 45 expedientes con documentos), es que estos 6 códigos no son
localizables por búsqueda en la Plataforma ahora mismo. Por qué (¿expediente
archivado fuera del índice de búsqueda, publicado bajo otro código,
procedimiento distinto que no aparece en "Licitaciones"?) sigue sin
verificar — fuera de alcance de esta sesión.

**Hallazgo que amplía el mismo síntoma**: de las 8 matrices nuevas que la
corrección de identidad del punto 1 llegó a descubrir y encolar
automáticamente (`resolver_o_encolar_matriz`), **las 8 fallaron igual, con
el mismo error exacto** — ninguna de las 5 matrices de la familia
`2.18/04703` ni las 3 de `2.24/04110` se encuentra en la Plataforma por
búsqueda. El sistema lo encajó exactamente como está diseñado (CONTEXTO.md sección 9.10,
sección 12): cada matriz cae a `fallido` con su motivo, y
`reencolar_pedidos_esperando_matriz` reencola a los 8 pedidos, que
`intentar_heredar_de_matriz` manda a `pendiente_revision` con
`"la matriz <código> no tiene ningún lote registrado (estado: fallido)"` —
nunca un cuelgue en `esperando_matriz`, nunca una excepción sin capturar.

**Entre los 6 expedientes de este punto y las 8 matrices del punto 2 hay 14
códigos reales de la Plataforma que hoy no se encuentran por búsqueda.** Es
la misma familia de problema que el hallazgo 3 del corpus señalaba sin
verificar, ahora con 14 casos reales que lo confirman en vez de 7. Sigue
siendo trabajo de scraping, no de extracción — ninguna de las herramientas
de este proyecto puede intentar una búsqueda que la propia Plataforma no
resuelve.

### 4. Reproceso completo de los 45 y medición

Reencolada la extracción de los 45 expedientes tras reconstruir las
imágenes con el código nuevo:

| | Antes de esta sesión | Después |
|---|---:|---:|
| `completado` | 10 | **10** |
| `pendiente_revision` | 35 | **35** |
| Líneas de catálogo | 2.041 | **2.041 (+0)** |
| Matrículas en >1 expediente | 13 | **13** |
| Expedientes con identidad corregida | — | **8 / 8** |
| Matrices nuevas descubiertas | 0 | **8** |
| Matrices encontradas y procesadas | — | **0 / 8** |

**Cero cambio en los agregados del catálogo, pero no es un resultado nulo**:
la identidad de los 8 pedidos ya es correcta (`codigo_expediente` real,
`codigo_matriz` real, `matriz_expediente_id` enlazado a una fila propia, sin
duplicar ninguna), lo que antes era imposible por el ciclo de
autorreferencia. Los 8 siguen en `pendiente_revision` — ya no por un dato mal
etiquetado, sino porque su matriz real no se encuentra en la Plataforma, un
bloqueo distinto y ahora explícito en `expediente.error` en vez de escondido
detrás de "forma un ciclo". Ninguno de los 14 pedidos derivados del hallazgo
3 aporta líneas de catálogo todavía: los 6 sin documentos y las 8 matrices
comparten la misma causa sin resolver del punto 3.

### Fixtures de regresión

`engine/tests/extraccion/test_identidad_expediente.py`, 7 casos: la función
`corregir_identidad_expediente` aislada (no-op cuando el código ya es
correcto, corrección cuando no lo es, no pisa una matriz ya declarada
distinta, no fusiona con una fila que ya tiene el código real, dos Anuncio
PCSP que discrepan van a revisión sin corregir) y un caso de extremo a
extremo con el mismo fixture real de la sección 20
(`ANUNCIO_PCSP_CON_MATRIZ`, `2.18_04703.0019_ADJUDICACION_1.pdf`): antes del
arreglo, esta fila se quedaba en `pendiente_revision` por "forma un ciclo";
con la identidad corregida antes de resolver la matriz, deja de ser un ciclo
real y pasa a `esperando_matriz`. No hizo falta ningún PDF nuevo.

---

## 22. Expedientes sin publicar (sesión 2026-09-03)

Ataca el primero de los dos encargos de esta sesión: marcar como
fuera de alcance los códigos que la Plataforma no publica. El segundo
encargo (atacar por impacto las causas que dejaban 21 expedientes en
revisión) está en `docs/hallazgos-extraccion.md`, sección 22.2. Verificado
de punta a punta contra el stack real
(imágenes reconstruidas, migración `0010` aplicada, reproceso completo desde
el worker real) — nunca solo con tests aislados.

### 1. `sin_publicar`: comprobado a mano, no solo por el scraper

Comprobación manual en la Plataforma (no solo el intento automático de
`scrape_expediente`): buscar `2.18/04703.0019` por número de expediente no
devuelve ningún resultado. Es la misma conclusión a la que ya había llegado
el scraping real en la sesión de corrección de identidad (sección 21), pero
esta vez confirmada por fuera del propio sistema antes de decidir marcarlo
como definitivo.

**Estado nuevo `sin_publicar`** (`EstadoExpediente`, migración `0010`,
`ALTER TYPE ... ADD VALUE`, no reversible): significa "este expediente no
existe en la Plataforma", no "hace falta revisarlo" ni "algo falló y puede
que reintentando funcione". Se distingue de los otros dos estados que se le
podían confundir:

- de `fallido`: ese sugiere que reintentar podría cambiar el resultado
  (timeout, WAF, formulario no localizado); `sin_publicar` es un resultado
  negativo determinista, reintentar no va a encontrar nada nuevo.
- de `pendiente_revision`: ese dice "hace falta un humano decidiendo algo
  sobre datos reales de este expediente"; `sin_publicar` dice que no hay
  datos que decidir, el expediente está fuera de alcance del sistema.

**Mecanismo** (`app/scraping/pcsp.py`, `app/scraping/job.py`): nueva
excepción `ExpedienteNoPublicadoError(RuntimeError)`, lanzada solo cuando
ninguna variante de búsqueda encuentra una fila de resultados — nunca para
timeouts, WAF ni otros fallos de scraping, que siguen siendo `fallido` y
elegibles para reintento normal. `ejecutar_scraping_expediente` la captura
aparte: marca `sin_publicar`, y **agota los intentos del trabajo ahí mismo**
(`trabajo.intentos = trabajo.max_intentos`) en vez de dejar que la cola
reintente dos veces más una búsqueda que ya se sabe que no cambia de
resultado — cada intento es una sesión real de Chromium headless contra la
Plataforma, no algo gratis. `app.extraccion.herencia_matriz._ESTADOS_TERMINADOS`
incluye ahora `sin_publicar`: sin esto, una matriz sin publicar (sin
documentos, sin trabajo activo) se releería en cada pedido que la referencia
como "hace falta encolar su descarga", reintentando para siempre.
`ejecutar_extraccion_expediente` corta en seco si el expediente ya está
`sin_publicar` al empezar — guarda contra un trabajo de extracción encolado
por error (o a mano) que lo devolvería a `pendiente_revision` con un motivo
mucho menos claro, perdiendo la marca ya verificada.

**Los 14 códigos marcados, verificados contra la Plataforma real** (scraping
real, sin dobles de test, cada uno con un único intento gracias al agotado
inmediato de intentos): las 8 matrices de CONTEXTO.md sección 16 (`2.18/04703.0019`,
`0021`, `0022`, `0024`, `0025`; `2.24/04110.0035`, `0036`, `0037`) y los 6
expedientes sin documentos (`2.24/28520.0128`, `2.25/28520.0161`,
`3.24/20810.0090`, `3.24/28520.0129`, `3.25/27520.0055`, `4.24/27520.0090`).
Los 8 pedidos reales que dependen de esas matrices (`6.24/28510.0100`,
`0101`, `0102`, `0103`, `0111`, `6.25/28510.0175`, `0215`, `0248`) **no** se
marcan `sin_publicar` — son expedientes reales, encontrados y descargados,
que siguen en `pendiente_revision` con un motivo ahora preciso: "la matriz
`<código>` no tiene ningún lote registrado (estado: sin_publicar)".

**Patrón observado, no una regla de código**: los 14 códigos no publicados
empiezan todos por `2.`, `3.` o `4.`; los que empiezan por `6.` siempre se
encuentran. Documentado como correlación (CONTEXTO.md sección 16), no convertido en un
atajo que rechace un código nuevo por su prefijo sin intentarlo — con 14
casos no hay base para generalizar, y CONTEXTO.md sección 9 prohíbe inventar
lo que no está verificado.

**Métricas del proyecto, desde ahora sobre 31, no sobre 45**: los 14 códigos
nunca fueron expedientes "reales" que el catálogo pudiera completar, así que
medir el progreso contra 45 escondía un techo que nunca iba a alcanzarse. La
sección "Medición final" más abajo da el detalle sobre los 31.

### 3. Medición final: 31 expedientes reales

Reprocesados los 31 desde cero contra el stack real tras desplegar los
cuatro arreglos de `docs/hallazgos-extraccion.md` sección 22.2
(imágenes reconstruidas, migración `0010`
aplicada):

| | Antes de esta sesión (sobre 45) | Después (sobre 31) |
|---|---:|---:|
| `completado` | 10 | **14** |
| `pendiente_revision` | 35 | **17** |
| `sin_publicar` | — | **14** (fuera de la medición, ver punto 1) |
| Líneas de catálogo (sobre los 31) | 2.041 (sobre 45) | **2.208** |
| Matrículas en más de un expediente | 13 | **13** (sin cambio: siguen siendo las de carril, bloqueadas por la segunda familia de baja) |

**Los 17 que siguen en `pendiente_revision`, agrupados por motivo — cuáles
son comportamiento correcto y cuáles trabajo pendiente:**

Comportamiento correcto (el sistema detecta una contradicción real o un caso
ya documentado, y por diseño no adivina — CONTEXTO.md sección 12):

- **7 expedientes, baja declarada no cuadra con la baja por importes**
  (`6.23/28510.0139`, `6.24/28510.0094`, `0117`, `0130`, `0203`,
  `6.25/28510.0019`, `0028`). Validación funcionando como está diseñada;
  varios de estos ya se señalaban en sesiones anteriores como posibles
  pedidos derivados de acuerdo marco con importes de la matriz mal cruzados,
  sin confirmar caso a caso.
- **3 expedientes, segunda familia de baja** (`6.23/28510.0018`, `0102`,
  `6.25/28510.0016`): fórmula `Ct = Oferta × Kt × Coeficiente de baja` por
  pedido, no una baja única de lote (CONTEXTO.md sección 16, "segunda familia
  de baja"). No hay un valor que extraer, es un modelo de cálculo distinto
  — diseño pendiente, no un fallo de extracción.
- **2 expedientes, valores ilegibles marcados y descartados en vez de
  adivinados** (`6.23/28510.0042`: matrícula `"***"`, un placeholder
  explícito; `6.23/28510.0051`: dos valores distintos en la misma celda que
  no coinciden entre sí). `6.20/28510.0136` también trae 2 filas de este
  tipo (encabezados de sección dentro del cuadro de matrículas, sin dato
  real que extraer) más su documento escaneado, ya contado aparte.
- **1 expediente, ambigüedad de lote por diseño** (`6.25/28510.0027`: LOTE
  2, 4, 5 y 6 no están entre los lotes que adjudica la Resolución —
  `docs/hallazgos-extraccion.md` sección 19, "sin lote centinela", las
  líneas quedan huérfanas en vez de
  asignarse por cercanía).
- **1 expediente, formato de código inválido** (`6.25/28510.5001_01`,
  sección 21: el sufijo `_01` lo descarta como candidato a búsqueda desde el
  principio).

Trabajo pendiente, no resuelto por esta sesión (estructural, necesita
investigación futura, no un ajuste de expresión regular):

- **2 expedientes, ningún documento con cuadro de precios**
  (`6.24/28510.0025`, `6.24/28510.0193`): los dos tienen exactamente 2
  documentos (`anuncio_pcsp` + `contrato`), sin `anejo` ni `pliego` — mismo
  síntoma estructural que los pedidos derivados de acuerdo marco, pero con
  código `6.24/28510.0NNN` normal, no de MATRIZ. Sin investigar si son
  pedidos derivados con una matriz sin identificar o contratos cuyo anejo de
  precios nunca se adjuntó — ver CONTEXTO.md sección 16.

---

## 27. Identidad de lote: la licitación multi-lote como estructura de primera
    clase (sesión 2026-09-04)

Ataca de raíz el problema que la sección "autoridad del PDF sobre la
sindicación" (más abajo, de `docs/decisiones-cliente.md` sección 26) solo
diagnosticaba para dos
casos (`6.24/28510.0088`, `6.23/28510.0129`): **13 expedientes multi-lote
más del corpus real comparten el mismo síntoma**, silenciados hasta ahora
porque el motor no sabía leer ninguna redacción salvo la de
`6.25/28510.0027` (`docs/hallazgos-extraccion.md` sección 19). El encargo explícito de esta sesión: recorrer
el corpus entero antes de tocar código, generalizar la extracción contra
todas las variantes reales encontradas — no contra una — y nunca dejar que
una cobertura parcial de lotes se disfrace de expediente completo.

### 1. La estructura real, verificada documento a documento (no supuesta)

Tres relaciones distintas coexisten en el corpus, y conviene no confundirlas:

- **Expediente principal ⟷ lote con número propio.** Cuando el título de una
  licitación dice "N LOTES" (N≥2), el propio documento declara dos
  identificadores: `EXPEDIENTE PRINCIPAL Nº X` (a veces `EXPEDIENTE ORIGEN
  Nº`, o "`Nº EXPEDIENTE MATRIZ`" — ver la trampa de vocabulario del punto 2)
  para el conjunto, y por cada lote que el documento cubre, `LOTE N:
  <descripción>. EXPEDIENTE Nº Y` — un código con el mismo formato que
  cualquier expediente (`6.NN/28510.0NNN`), distinto y casi siempre
  correlativo al principal. Verificado en **15 de los 38 expedientes con
  documentos (39%)**: `6.23/28510.0051` (2 lotes), `0066` (4), `0109` (2),
  `0129` (3), `0139` (2, sección 3 más abajo), `6.24/28510.0064` (3), `0088`
  (2), `0094` (3), `0117` (3), `0124` (2), `0130` (**13**), `0203` (6),
  `6.25/28510.0019` (**9**), `0027` (6), `0028` (7).
- **Contrato ⟷ lote.** El "Contrato nº" del Contrato firmado coincide
  siempre con el "EXPEDIENTE Nº" que ese mismo lote declaró en su
  adjudicación — verificado en `0088` (lote1=`.0113`, lote2=`.0114`), `0027`
  (lote1=`.0099`, lote3=`.0101`), `0129` (lote2=`.0143`), `0066`
  (lote1=`.0073`, lote2=`.0074`). **Y esto solo ocurre cuando hay lotes**: en
  un expediente de un solo lote (`6.24/28510.0008`), "Contrato nº" es
  idéntico al expediente. La numeración independiente del contrato es
  consecuencia de la partición en lotes, no un fenómeno aparte — no hace
  falta modelarlo como una tercera entidad.
- **Acuerdo marco / pedidos derivados (secciones 20-22 de arriba), sin relación con lo
  anterior más allá de compartir vocabulario** (ver punto 2). Estructura ya
  estable, no tocada en esta sesión.

### 2. Dos trampas de vocabulario verificadas, no supuestas

El corpus reutiliza dos palabras del dominio con un segundo significado
ajeno al de CONTEXTO.md sección 2 — confusión real, no hipotética, y hay que evitar
que el código las mezcle:

- **"Lote"**: en una licitación multi-lote (este documento) es la
  subdivisión en contratos concurrentes que describe el punto 1. En un
  pedido derivado de acuerdo marco (CONTEXTO.md sección 3 y sección 20 de arriba), "Lote N" es una
  **categoría de producto dentro del catálogo del acuerdo marco** ("Pedido
  nº 7 acuerdo marco de suministro de equipos de protección individual. Lote
  4.- guantes de protección..."), sin ninguna subdivisión en contratos
  concurrentes. Dos conceptos distintos, misma palabra.
- **"Matriz"**: `6.24/28510.0094` etiqueta su expediente principal como "Nº
  EXPEDIENTE MATRIZ" — verificado en el documento real, sin relación alguna
  con `codigo_matriz`/`matriz_expediente_id` (acuerdo marco, CONTEXTO.md sección 2 y
  sección 20 de arriba). Es solo cómo esta Propuesta LC.27 concreta llama a "el expediente que
  agrupa los lotes". **Guarda de código**: `app.extraccion.lotes` captura
  este valor como `codigo_principal_declarado` únicamente para
  contraste/trazabilidad (si no coincide con `expediente.codigo_expediente`,
  se manda a revisión con el motivo explícito) — **nunca se escribe en
  `expediente.codigo_matriz`**, porque hacerlo reintroduciría el bug de
  autorreferencia de las secciones 20-21 (una fila etiquetada con el código
  de su propia licitación agrupadora, tratada como si fuera una matriz de
  acuerdo marco). Verificado con un test de aceptación contra el documento
  real de `0094` (`test_codigo_principal_declarado_nunca_se_confunde_con_matriz`).

### 3. El caso más peligroso: cobertura cero sin ningún documento que la desglose

`6.23/28510.0139` no tiene ninguna Propuesta LC.27 ni Resolución de
Adjudicación — solo un Anuncio PCSP con el campo estructurado **"Nº de
Lotes: 2"** (`campos_pcsp.numero_lotes`, nuevo) y dos Contratos, cada uno de
un lote distinto, sin ningún documento que diga cuál es cuál. Antes de esta
sesión figuraba `completado`: el camino de lote único implícito
(`LOTE_UNICO`) le atribuía al expediente entero la baja/importe de un solo
Contrato, sin saber que representaba solo uno de los dos lotes reales — el
mismo patrón que `6.24/28510.0088` (`docs/decisiones-cliente.md` sección 26), pero sin siquiera un
documento que lo desglosara. Ahora: `lotes_totales_declarados=2` (del campo
PCSP, único origen posible aquí) contra 0 lotes identificados por número →
`"cobertura parcial: 0 de 2 lotes identificados por número"`, nunca
`completado`.

### 4. Modelo de datos: atributo del lote, no expediente nuevo

Decisión explícita del cliente, con justificación de la sección 1 (punto
"Contrato ⟷ lote"): la identidad del lote es derivada de la partición, no
una entidad independiente — crear 40-50 filas de `Expediente` nuevas
complicaría la web, el Excel y la idempotencia sin ganancia clara mientras
nadie necesite buscar un lote como expediente propio. Si algún día hace
falta, se promueve.

- **`lotes.numero_contrato`** (columna existente desde la migración 0001,
  nunca poblada) **renombrada a `lotes.codigo_expediente_lote`** — nombre
  más preciso, porque el dato casi siempre se conoce antes por la
  Propuesta/Resolución, no solo por el Contrato firmado (aunque ambos
  declaran el mismo valor, verificado). Migración `0015`, reversible
  (`ALTER COLUMN ... RENAME`).
- **`expedientes.lotes_totales_declarados`** (integer, nullable, migración
  `0015`): el N de "N LOTES" del título, o del campo "Nº de Lotes:" del
  Anuncio PCSP cuando no hay narrativa de lote (punto 3). **Nunca se usa
  para generar una secuencia 1..N** — verificado con `6.25/28510.0028`
  ("7 LOTES" cuyo LOTE 5 no aparece en ningún sitio del documento, desierto
  o anulado sin verificar cuál): la numeración real tiene huecos, y
  `lotes_totales_declarados` solo sirve para comparar "cuántos conocemos"
  contra "cuántos hay", nunca para inventar el que falta.
- **Cobertura parcial, sin estado nuevo ni columna booleana**: se compara
  `lotes_totales_declarados` contra los lotes que sí traen `baja_lote` o
  `importe_adjudicacion` (no basta con que el lote *exista* por nombre,
  CONTEXTO.md sección 5). Si faltan, se acumula en `motivo_revision` — el mecanismo ya
  existente hace que eso nunca llegue a `completado`, sin tocar la máquina
  de estados.
- **Lote conocido por nombre pero sin bloque de adjudicación**: se modela
  igual que cualquier otro (`Lote` con `identificador_lote` y
  `codigo_expediente_lote` si se declaró, baja/importe/adjudicatario en
  `NULL`) — "existe, sin datos", no se omite ni se inventa.

### 5. Extracción generalizada, no enumerada por variante

Catalogadas las 15 variantes reales antes de tocar `app.extraccion.lotes`
(recopilación completa en la sesión, no repetida aquí): "En el LOTE N."
(`0027`, la única que reconocía el código anterior), "- ADJUDICAR el
contrato de \<título repetido\> - LOTE N: ..." con importe antes de la baja
(`0028`, `0124`), título repetido con "Nº DE EXPEDIENTE:" y baja antes de
importe (`0203`), numerado "1º.-/2º.-/3º.-" (`0094`), lista con dos puntos
"- LOTE N: ... EXPEDIENTE Nº X: \<empresa\>" (`0117`, `0130`, `0019`), y
documentos de un solo lote que nunca repiten "LOTE N" en el cuerpo (`0051`,
`0066`, `0088`, `0109`, `0129`).

En vez de un regex por variante, dos pasadas independientes sobre las
páginas **concatenadas** (un bloque de adjudicación puede partirse por un
salto de página — verificado en `6.24/28510.0117`, la baja de LOTE 2 queda
en la página siguiente a su importe):

1. **Ventaneo por ocurrencia de `LOTE\s*N`** (con o sin "En el"/"-"/"▪"/"•"/
   numeración delante — el único ancla que comparten las 15 variantes):
   cada aparición abre una ventana hasta la siguiente aparición de
   cualquier `LOTE N` o el final del texto. Un documento de un solo lote
   simplemente tiene una única ventana gigante (desde la cabecera hasta la
   firma), así que no necesita ninguna rama especial.
2. **Sub-extractores genéricos por ventana**: código propio (etiquetado
   "EXPEDIENTE Nº"/"Nº DE EXPEDIENTE:", o pelado sin etiqueta — verificado
   en `6.25/28510.0019`, LOTE 1: "...MATERIAL AUXILIAR. 6.25/28510.0039:"),
   baja (`app.extraccion.baja.buscar_baja_en_texto`, factorizada de
   `extraer_baja_declarada` para reutilizarla aquí) e importe adjudicado
   ("Base imponible...€", el mismo patrón que ya usaba `campos_lc27` para
   el camino de un único lote). El orden baja/importe dentro del texto deja
   de importar porque cada sub-extractor busca su propio patrón, no una
   secuencia fija.

**Dos bugs reales de regex encontrados verificando contra los documentos,
no supuestos:**

- `_LOTES_TOTALES_RE` (total de "N LOTES" del título) leía "88\nLOTE 1:" (los
  dos últimos dígitos de "...6.24/28510.0088" seguidos de un salto de línea
  y el "LOTE 1" real) como si fuera "88 LOTES" — devolvía 88 en vez de 2.
  Arreglado con un lookahead negativo que exige que tras "LOTE(S)" no venga
  inmediatamente un número.
- `_BAJA_RE` no toleraba puntuación suelta entre "del" y el número: `0203`
  trae literalmente "con una baja del. 10,75%," (un punto de más). Arreglado
  aceptando `[.,]?` opcional en ese hueco.

**Redacción nueva de baja, no vista hasta esta sesión**: `0051` dice "con un
25,31 % de baja a todos los precios unitarios" — el número precede a "% de
baja" en vez de seguir a "baja del", el orden inverso de `_BAJA_RE`. Nuevo
patrón `_BAJA_INVERTIDA_RE` en `app.extraccion.baja`, con el mismo riesgo
bajo de falso positivo que ya limita `_BAJA_ETIQUETA_RE` (exige un número
inmediatamente antes de "% de baja", no basta la palabra "baja" sola).

### 6. Medición final: 12 de los 20 `completado` estaban mal, 0 se recomponen

Reprocesados los 15 expedientes multi-lote reales (más `0139`) contra el
stack real, uno a uno en procesos aislados (ver nota de rendimiento en
CONTEXTO.md, "Pendiente de resolver"):

| | Antes de esta sesión | Después |
|---|---:|---:|
| `completado` (sobre 38 con documentos) | 20 | **8** |
| `pendiente_revision` | 18 | **30** |
| `sin_publicar` | 15 | 15 (sin cambio) |
| Líneas de catálogo | 2.208 | **3.018** |
| Matrículas en más de un expediente | 13 | 13 (sin cambio) |

**De los 20 `completado` anteriores, 12 mostraban datos de un solo lote
presentados como si fueran del expediente entero** (`0066`, `0109`, `0129`,
`0139`, `0064`, `0088`, `0094`, `0117`, `0124`, `0130`, `0203`, `0019` — los
15 multi-lote menos los 3 que ya estaban en `pendiente_revision` antes por
otra causa: `0051`, `0027`, `0028`). **Ninguno de los 15 se recompone a
`completado`**: los 12 con cobertura genuinamente incompleta quedan con el
motivo exacto ("cobertura parcial: N de M lotes..."); los 3 con cobertura
completa de sus lotes conocidos (`0094` 3/3, `0117` 3/3, `0203` 6/6) siguen
en `pendiente_revision` por motivos ya existentes y correctos (fragmentos de
tabla huérfanos entre páginas, celdas ilegibles) — la cobertura de lote deja
de ser su problema, pero no inventa que están limpios cuando no lo están.
**Es exactamente el resultado que pedía el encargo**: un dato que se ve bien
y está mal es peor que tenerlo en revisión, y ahora ninguno de los 15 se ve
bien sin estarlo de verdad.

El aumento de líneas de catálogo (+810) no es principalmente por lotes
nuevos descubiertos, sino por `6.23/28510.0051`: con la identidad de lote
corregida, su cuadro de precios completo (1.080 líneas, el catálogo más
grande del corpus) se guarda por primera vez sin que el guion de
autorreferencia del lote lo bloqueara a medias.

### Fixtures de regresión

`engine/tests/fixtures/pdfs/`, cinco documentos reales completos añadidos
(CONTEXTO.md sección 13: pequeños, `6.23_28510.0066_ADJUDICACION_1.pdf`
(153 KB), `6.24_28510.0117_ADJUDICACION_1.pdf` (146 KB),
`6.25_28510.0028_ADJUDICACION_1.pdf` (144 KB),
`6.24_28510.0094_ADJUDICACION_1.pdf` (207 KB, la trampa "Nº EXPEDIENTE
MATRIZ"), `6.23_28510.0139_ADJUDICACION_1.pdf` (24 KB, el Anuncio PCSP sin
desglose) — reutilizados también los ya existentes `PROPUESTA_LC27_UTE`
(`0088`) y `RESOLUCION_ADJUDICACION` (`0124`), que ya cubrían dos de las
variantes sin saberlo.

`engine/tests/extraccion/test_lotes.py` (7 casos, generalización contra
cada variante real), `test_baja.py` (2 casos: orden invertido, puntuación
suelta), `test_campos_pcsp.py` (1 caso: `numero_lotes`),
`test_orquestador.py` (6 casos: lote único con número real en vez del
sentinela, cobertura completa sin motivo espurio, hueco en la numeración,
cobertura cero sin desglose, sustitución del lote sentinela obsoleto al
migrar, guarda de vocabulario "matriz"). 257 tests en verde, ninguno nuevo
de más de 210 KB.

### Seguimiento (sesión 2026-09-14, revisión del cliente): el expediente de lote

Esta sección daba a cada lote su código propio, pero ningún expediente se
restringía a su lote: un expediente que ES el LOTE N (su código es el
"EXPEDIENTE Nº" de ese lote) guardaba las líneas, la baja y el importe de
todos los lotes de la licitación, porque comparte los documentos con sus
hermanos. Desde esa sesión (detalle en
`docs/sesion-2026-09-14-revision-cliente-pliegos.md`, bloque C1):

- Si exactamente uno de los lotes declarados trae el código del propio
  expediente, el expediente solo guarda ese lote; el principal (su código no
  es el de ningún lote) sigue con todos.
- El Contrato firmado ("Contrato nº: X" + "LOTE N") tiene la última palabra
  sobre la identidad de cada lote: corrige erratas de número en la
  adjudicación, completa código y baja, y su baja gana si contradice la que
  la adjudicación atribuye a ese lote. Nunca añade un lote que la
  adjudicación no nombra.
- "… POR EL ADJUDICATARIO DEL LOTE N" dentro de la descripción de otro lote
  es una referencia cruzada, no el arranque de un bloque.

---

## Seguimiento urgente: autoridad del PDF sobre la sindicación, y los 3 últimos en revisión (parte de la sesión de criterios del cliente, sección 26 de `docs/decisiones-cliente.md`)

Encargo del cliente tras ver el primer reproceso de esa sesión:
`6.24/28510.0088` (el
ejemplo central de CONTEXTO.md sección 4) no puede estar en revisión, y el problema
de fondo es de diseño — sindicación no tiene la misma autoridad que el
documento firmado.

**Investigado antes de tocar nada (encargo explícito: "dime cuál de las dos
fuentes tiene razón, con eso decidimos").** Decodificados a mano los dos
`ADJUDICACION_1.pdf` reales. Ninguna de las dos fuentes está mal — miden
alcances distintos:

- `6.24/28510.0088`: su propio PDF dice "SUMINISTRO DE TRAVIESAS DE MADERA...
  **2 LOTES**. EXPEDIENTE Nº 6.24/28510.0088 · **LOTE 1**: TRAVIESAS DE
  MADERAS EUROPEAS... **EXPEDIENTE Nº 6.24/28510.0113**" — el documento que
  tenemos archivado bajo `.0088` es la adjudicación del LOTE 1 (expediente
  propio `.0113`, 1.000.000 €), no la del expediente principal completo (2
  lotes, 2.000.000 €, que es justo lo que declara sindicación).
- `6.23/28510.0129`: mismo patrón exacto — "EXPEDIENTE PRINCIPAL Nº
  6.23/28510.0129 · **LOTE 2**... **EXPEDIENTE Nº 6.23/28510.0143**", con el
  importe del LOTE 2 (1.180.620 €) coincidiendo con lo que extrae el motor,
  frente al total de los 3 lotes (2.705.670 €) que declara sindicación.

**No es una cuestión de qué fuente es más fiable ni de qué ZIP es el más
reciente** (lo segundo, comprobado igualmente: la lógica de
`descubrir_novedades` ya se queda con la entrada de mayor `<updated>` y
nunca pisa un dato más nuevo con uno más viejo, `docs/hallazgos-sindicacion.md`
sección 24 — no es la causa
aquí). Es que `6.24/28510.0088` y `6.23/28510.0129`, tal como los tiene
identificados este sistema, no son pedidos de un solo lote: son licitaciones
de varios lotes de las que solo tenemos el papel de uno. Mismo tipo de
problema de identidad que ya se resolvió para acuerdo marco (secciones
20-21 de arriba) — "el código bajo el que está archivado un documento no es
necesariamente el expediente al que pertenece de verdad" —, pero en una
variante nueva (lote de licitación directa, sin acuerdo marco de por medio)
que no había aparecido hasta esta sesión (resuelta después en la sección 27
de arriba). **Separarlo bien de verdad**
(crear expedientes de lote reales, `.0113`/`.0143`, y dejar `.0088`/`.0129`
como lo que son —el expediente principal, sin cuadro de precios propio— es
un cambio de modelo de datos mayor, fuera de alcance de un arreglo urgente:
queda anotado en CONTEXTO.md, "Pendiente de resolver", para una sesión aparte.

**Lo que sí se implementó, urgente, coherente con la propuesta del
cliente:** el contraste con sindicación ya no cambia `estado` ni `error` de
ningún expediente — nunca baja uno de `completado`, nunca añade ruido al
motivo real de uno en revisión. Se guarda como aviso informativo aparte,
`expedientes.aviso_sindicacion` (columna nueva, migración `0014`),
recalculado en cada reproceso (`app.worker._contrastar_con_sindicacion`) —
`contrastar_expediente` (`app.sindicacion.contraste`) sigue detectando el
desajuste exactamente igual que antes, pero ya no decide qué hacer con él,
eso es responsabilidad de quien la llama. **Sin exponer todavía en la web**
(fuera de alcance del arreglo urgente): el campo está en la API
(`ExpedienteOut.aviso_sindicacion`), falta añadirlo a la pantalla.

**Los 3 expedientes que seguían en revisión tras el criterio de lote laxo,
mirados uno a uno (encargo: "si son celdas concretas, puede ser barato"):**

- `6.24/28510.0117` (39 líneas) y `6.24/28510.0203` (1 línea): un guion
  suelto (`-`) en la celda de matrícula o de cantidad, la misma convención
  administrativa de "no aplica a esta fila" que ya se trata como hueco en
  blanco en el resto del sistema (columnas fantasma, CONTEXTO.md sección 8) —
  no un valor ilegible. **Barato, arreglado**: `app.catalogo._es_celda_vacia`
  trata un guion suelto como campo vacío para matrícula, cantidad y precio
  unitario, sin generar motivo de revisión. Los dos pasan a `completado`.
- `6.25/28510.0028` (4 líneas): **no era barato.** Las celdas traen
  identificadores de glifo sin decodificar (`(cid:1005)...`, fuente sin tabla
  ToUnicode) — es justo el caso de "fuera de alcance sin OCR" de CONTEXTO.md
  sección 15, no una celda con un valor reconocible. Sigue en revisión, y es
  correcto que lo esté.

---

## 28. Segunda familia de baja: modelo de precio indexado por pedido
     (sesión de trabajo pendiente real, 2026-09-05)

Diseña y implementa una versión acotada de lo pendiente en CONTEXTO.md sección
16 ("segunda familia de baja, sin diseñar todavía"), tras verificar los tres
documentos reales de los tres expedientes conocidos (`6.23/28510.0018`,
`6.23/28510.0102`, `6.25/28510.0016`) — los tres son Acuerdo Marco de
"SUMINISTRO DE CARRIL NUEVO PARA LAS NECESIDADES DE LA RED FERROVIARIA DE
INTERÉS GENERAL", mismo adjudicatario (ArcelorMittal España), texto de
fórmula idéntico carácter a carácter entre los tres.

### La fórmula real, verificada

```
P-1(t)      = P-1(Oferta presentada por el licitador) × Kt × Coeficiente de baja
P-i(t)      = P-i indicado en el PPT × Coeficiente de transformación ofertado × Kt × Coeficiente de baja   (i = 2..13)
Kt          = 0,26 · (Et / E0) + 0,33 · (St / S0) + 0,41
```

- `Et`/`E0`: índice IPRI (INE) del grupo 351 (energía eléctrica), en el
  momento del pedido / en el momento de publicación de la licitación.
- `St`/`S0`: índice IPRI del grupo 241 (acero), mismos momentos.
- **Coeficiente de baja**: ofertado por el licitador **en cada pedido**,
  ≤ 1. **No está en ningún documento de la licitación** — se fija en el
  futuro, pedido a pedido, cuando ADIF solicita oferta al adjudicatario del
  Acuerdo Marco y le facilita los valores de `Et`/`St` de ese momento.
- **Coeficiente de transformación**: sí está fijado en la licitación —
  verificado en los tres casos: **1,276**, declarado en la Propuesta de
  Adjudicación y en el Contrato ("con un coeficiente de transformación para
  el P-1 de 1,276 y con un coeficiente de transformación para P-2 a P-13 de
  1,276"). `6.25/28510.0016` trae además un ejemplo numérico real firmado
  por el adjudicatario en su Proposición Económica: PPT 99,55 €/m × 1,276 =
  127,03 €/m ofertado.

**Consecuencia central**: `precio_adjudicado` de este modelo **no es
calculable desde los documentos de la licitación, nunca** — no porque falte
un dato que buscar mejor, sino porque el valor no existe hasta que se cursa
un pedido real contra el Acuerdo Marco, con datos (índices IPRI del momento,
oferta del licitador para ese pedido) que no están en ningún PDF del
expediente. Distinto de "no se encontró la baja" (sección 4: ahí el dato
existe en algún documento y toca buscarlo mejor) — aquí el dato
estructuralmente no existe todavía.

### Qué se implementó (acotado, encargo explícito de esta sesión)

- **`lotes.modelo_precio`** (migración `0016`, enum `fijo` /
  `indexado_por_pedido`, `ModeloPrecio` en `app.models`): señal explícita y
  auditable de por qué `baja_lote`/`precio_adjudicado` se quedan `NULL` en
  un lote — no un motivo de texto suelto que se pierde en el histórico de
  `trabajos_cola`.
- **`lotes.coeficiente_transformacion`** (`Numeric(8,4)`, nullable): el
  único parámetro real de la fórmula que sí está en la licitación.
- **`app.extraccion.modelo_precio_indexado.detectar_modelo_precio_indexado`**:
  busca el marcador literal "Coeficiente de baja: Ofertado por el licitador
  para cada pedido" (idéntico en los tres reales, ancla específica que no
  dispara con nada ajeno a este modelo) y, si lo encuentra, el "coeficiente
  de transformación para el P-1 de N" en cualquier página del mismo
  expediente. Una llamada de regex, sin modelo — la frase es literal y fija
  en la plantilla, no varía de redacción entre los tres casos vistos.
- **`app.extraccion.orquestador`**: en el camino de lote único implícito
  (CONTEXTO.md, "camino de siempre"), si se detecta el modelo indexado, se
  salta `calcular_baja_efectiva` entero (esa función no aplica: no hay baja
  que cuadrar ni derivar) y el lote queda con `baja_lote = NULL`,
  `modelo_precio = indexado_por_pedido`, sin que el chequeo final de "no se
  pudo determinar la baja de ningún lote" lo marque como incompleto.
  Idempotente: un reproceso que ya no detecte el marcador revierte el lote a
  `modelo_precio = fijo` en vez de dejar un valor obsoleto.
- **Respuesta a si esto es `pendiente_revision` o `completado`**: se decidió
  que sea **`completado`** cuando el resto del expediente (importes,
  cobertura de lotes) está resuelto. Razón: el modelo aplicado correctamente
  no deja nada que un humano pueda decidir — no hay una baja que buscar
  mejor ni un valor que confirmar, es una propiedad estructural del tipo de
  contrato, igual que un pedido derivado de acuerdo marco sin cuadro de
  precios propio (sección 20) es `completado` tras heredar, no
  `pendiente_revision`. Un texto explicativo en lenguaje llano viaja en el
  resultado del trabajo (`nota_modelo_precio_indexado`, mismo mecanismo que
  `aviso_documento_escaneado` de `docs/hallazgos-extraccion.md` sección
  31.2) para que quede claro, si alguien lo mira, que `baja_lote` vacío aquí
  es a propósito, no un hueco sin explicar.
- Tests: `tests/extraccion/test_modelo_precio_indexado.py` (4 casos: detecta
  el marcador, extrae el coeficiente de otra página, tolera el espacio
  suelto real de `6.25/28510.0016` ("de 1, 276"), no detecta nada sin el
  marcador). Verificado además con reproceso real de los tres expedientes
  contra el stack completo (Postgres real, PDFs reales) — no solo con los
  tests aislados.

### Qué NO se implementó, y por qué (encargo explícito: "no implementes la
     extracción estructurada de los pesos Kt ni de los grupos IPRI")

- **Los pesos de `Kt`** (0,26 energía / 0,33 acero / 0,41 constante) y los
  **grupos IPRI de referencia** (351 energía, 241 acero) no se extraen ni se
  guardan en ninguna columna. Son constantes de la plantilla de contrato,
  iguales en los tres casos vistos — extraerlas no cambia ningún resultado
  hoy, y nadie las consume.
- **`Kt` no es calculable ni con estos pesos**: hace falta consultar al INE
  los índices IPRI reales del grupo 351/241 en dos momentos concretos (fecha
  de publicación de la licitación, fecha de solicitud de cada pedido) — una
  fuente de datos externa, viva, fuera del alcance de una extracción de PDF
  y de las invariantes de arquitectura (CONTEXTO.md sección 9, "nada
  específico de un proveedor" no aplica aquí, pero sí el principio general:
  no se construye una integración nueva sin un caso de uso real que la
  necesite).
- **Si en el futuro hace falta calcular un precio real de un pedido
  concreto** (no solo el precio de referencia del PPT, que ya se captura
  como `precio_unitario` de siempre): la vía prevista, sin construir, sería
  una pantalla o endpoint aparte que reciba los índices IPRI del momento
  (introducidos a mano o vía una integración con el INE, decisión de
  cliente) y el "Coeficiente de baja" de ese pedido concreto, y calcule
  `P(t)` bajo demanda — nunca algo que el catálogo acumulativo intente
  precomputar, porque el resultado cambia con cada pedido y con cada
  publicación de índice IPRI.
- **Otras posibles variantes de esta familia sin verificar**: los tres casos
  conocidos son todos del mismo contrato-tipo de carril. Si aparece un
  Acuerdo Marco de otro material con una fórmula de indexación distinta (por
  ejemplo, el "hilo de cobre" de `6.20/28510.0136_ANEJO_2.pdf`, que declara
  una fórmula ligada a la cotización LME del cobre — ver
  `docs/hallazgos-extraccion.md` sección 31.2, sin cuadro de precios propio
  en ese documento así que sin verificar más a fondo), el marcador literal
  de este detector no lo va a reconocer, y caerá en el motivo genérico de
  siempre. No generalizar el detector sin un caso real que lo confirme.

### Recuento final de la sesión

Ver `docs/hallazgos-extraccion.md` sección 31.4 para el recuento conjunto de
los cinco casos atacados en esta sesión.

---

## 29. Cuarta variante de autorreferencia de matriz, y unificación del punto
     de escritura (sesión 2026-09-06)

Ver `docs/auditoria-huerfanos-y-autorreferencia.md` sección 2 para el
detalle completo. Resumen: `6.23/28510.0109` autorreferenciaba su matriz
(`codigo_matriz == codigo_expediente`) por una vía nueva, no vista en las
secciones 20-21 ni 27 de arriba — ni el PDF ni la cascada de extracción,
sino el propio Excel de códigos de referencia (`CODIGOS_PROYECTO_PATH`), que
declara `MATRIZ` igual al propio "Nº Expediente" para una licitación
multi-lote sin acuerdo marco real. Comprobación sistémica: **7 filas** con
el mismo patrón exacto, no solo la que se reportó. Los cinco sitios del
código que escribían `expediente.codigo_matriz` (Excel, campo PCSP de
acuerdo marco, corrección de identidad, corrección manual desde la cola de
revisión, alta por API) se unificaron detrás de un único punto,
`app.extraccion.cruce_codigos.asignar_matriz`, que comprueba la
autorreferencia una sola vez para los cinco. Las 7 filas ya corruptas se
corrigieron con una actualización directa (el cruce con el Excel no se
repite nunca por diseño, así que el arreglo de código por sí solo no las
habría corregido).
