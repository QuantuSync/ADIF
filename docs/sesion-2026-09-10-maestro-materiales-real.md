# Sesión 2026-09-10 — Maestro de materiales real, defectos pendientes y reproceso completo

Continuación de la sesión 2026-09-09 (bloque 4: `docs/sesion-2026-09-09-cambios-cliente-catalogo.md`),
que dejó preparada la carga del maestro de materiales de SAP sin tener
todavía el fichero real. Esta sesión lo recibe y lo carga.

## Bloque 1 — Cargar el maestro real y completar unidades

### El fichero real no trae las columnas que se habían supuesto

La migración 0025 y `app.extraccion.maestro_materiales` (sesión 2026-09-09)
se prepararon con nombres de columna tomados por analogía del desglose de
SAP del bloque 6 anterior: `Material` / `Texto breve` / `Unidad medida
base`. El fichero real, `LISTADO_MATERIALES_UNIDAD__MEDIDA.xlsx`
(32.116 filas, una hoja, sin huecos), trae en cambio:

| Columna real | Columna que se había supuesto |
|---|---|
| `Material` | `Material` (coincide) |
| `Denominación` | `Texto breve` |
| `UM base` | `Unidad medida base` |

Corregido en `COLUMNA_DESCRIPCION`/`COLUMNA_UNIDAD_MEDIDA`
(`app/extraccion/maestro_materiales.py`) y en el test existente. Sin este
arreglo la carga habría insertado 32.116 materiales con descripción y
unidad siempre `None` (la hoja SÍ trae la columna mínima requerida,
`Material`, así que no falla — falla en silencio, sin dar ningún error).

Verificado también contra el fichero real: 31.665 matrículas de nueve
dígitos, 440 de cuatro y 11 de diez (categorías genéricas de SAP, p. ej.
`1000` = "Material de subestaciones"), 0 huecos en las tres columnas, 18
unidades distintas, `UN` en el 96% de las filas, 29.375 denominaciones
distintas sobre 32.116 filas — cifras coherentes con las que dio el
cliente. `MaestroMaterial.matricula` ensancha de `String(9)` a `String(10)`
(migración 0026) para no truncar los códigos de diez dígitos al cargar; no
afecta al cruce porque una matrícula de línea del catálogo es siempre de
nueve dígitos por definición de dominio (CONTEXTO.md sección 2).

### Discrepancia documento vs. SAP: implementada, con un ajuste de normalización

Encargo explícito: si el documento ya trae una unidad y el maestro dice
otra, no pisar la del documento — marcar la discrepancia para revisión.
`completar_unidades_desde_maestro` pasó de "solo tocar líneas sin unidad" a
recorrer TODA línea con matrícula: si le falta unidad, la rellena (como
antes); si ya la tiene y no coincide con el maestro, anota la del maestro
en `unidad_medida_discrepancia_maestro` (migración 0026) sin tocar
`unidad_medida`.

Primera pasada contra los datos reales: 3.636 discrepancias — sospechoso
por volumen. Desglosado, 3.281 (90%) eran documento="UD"/"UD."/"ud" contra
maestro="UN": la misma unidad real ("unidad"), abreviada de forma distinta
en los pliegos y en SAP, no una discrepancia de sustancia. Añadido un
diccionario de sinónimos verificado (`_SINONIMOS_UNIDAD`, solo variantes
gráficas de "unidad": `UD`/`UDS`/`UNIDAD`/`UNIDADES` → `UN`, más recorte de
puntos finales) antes de comparar — deliberadamente sin ampliarlo a otras
unidades sin verificar caso por caso. Recalculado: **354 discrepancias
reales**, con señal útil de verdad:

| Documento | Maestro (SAP) | Filas | Lectura |
|---|---|---|---|
| `m`/`M` (metros) | `UN` | 143 | posible material que se compra por unidad, no por metro, o viceversa |
| `Kg` | `M` / `UN` | 126 | mismo tipo de discrepancia real de magnitud |
| `50,00 €`, `1.950,00 €`, ... | `UN` | ~30 | **la columna de unidad del catálogo tiene un precio metido dentro** — defecto de extracción pre-existente (columna desplazada), no del maestro — misma familia que el defecto de "unidad ajena" ya cerrado en la sesión 2026-09-07, sección 7 de CONTEXTO.md, pero un caso no cubierto por esa validación porque no es solo dígitos y puntos |
| `DIN 934`, `DIN 125-A`, ... | `UN` | ~9 | referencia normativa del material colada en la columna de unidad, mismo patrón |

Las 354 quedan anotadas en `unidad_medida_discrepancia_maestro` — visibles
por API (`LineaCatalogoOut.unidad_medida_discrepancia_maestro`,
`fila_a_dict`) para quien las quiera revisar; no se corrige nada
automáticamente. No se añadió pantalla propia en la web esta sesión (fuera
de lo pedido en el bloque 1 — el bloque solo pedía cargar y completar,
"marca la discrepancia para revisión" se cumple dejándola en trazabilidad,
consultable, igual que `posible_duplicado_de` en el bloque 4 de la sesión
2026-09-07 antes de tener su propio botón en `RevisionPanel.tsx`).

### Resultado numérico

Medido contra la base real, antes y después:

| | Antes | Después |
|---|---|---|
| Líneas con `unidad_medida` | 17.100 / 22.721 (75,3%) | 19.249 / 22.721 (**84,7%**) |
| Líneas que ganan unidad | — | **2.149** |
| Sin matrícula en el maestro (matrícula del catálogo no aparece en SAP) | — | 432 |
| Discrepancias reales detectadas | — | 354 |

El 15,3% restante sin unidad (3.472 líneas) es la suma de: sin matrícula en
absoluto (el maestro solo alcanza líneas que YA tienen matrícula, 40,7% del
corpus — completar matrícula sigue sin implementar, ver más abajo), y 432
líneas con matrícula que no está en el maestro de SAP (probablemente
materiales dados de baja en SAP, o matrículas mal extraídas — no
investigado en este bloque, coherente con "no lo implementes todavía" del
bloque 4 anterior para todo lo que sea cruce difuso).

### Despliegue

`MAESTRO_MATERIALES_PATH` añadido a `docker-compose.yml` (servicio `api`,
mismo patrón que `SAP_DESGLOSE_PATH`) y `docker-compose.override.yml`
(bind-mount de `Ejemplo/Input/LISTADO_MATERIALES_UNIDAD_,MEDIDA.xlsx` —
nótese la coma en el nombre real del fichero, no el doble guión bajo que
se esperaba; documentado aquí porque un `ls` a ciegas no lo habría
detectado). Migración 0026 aplicada. 580 tests (17 nuevos de este módulo)
pasan contra el stack real.

`POST /mantenimiento/maestro-materiales/cargar` → 32.116 leídas, 32.116
nuevas, 0 sin matrícula. `POST
/mantenimiento/maestro-materiales/completar-unidades` → resultado de
arriba.

## Bloque 2 — La denominación como vía para la matrícula (análisis, sin implementar)

Encargo: analizar si la denominación del maestro sirve para proponer
matrícula a las líneas sin ella, **sin implementar nada**. Medido con
`difflib` (índice invertido por palabra para acotar candidatos, sin
dependencias nuevas) contra las 13.735 líneas reales del catálogo sin
matrícula (no las 11.340 que traía el encargo — la cifra del cliente es de
antes del reproceso de la sesión 2026-09-09 que hizo crecer el catálogo de
22.097 a 22.721 líneas; mismo fenómeno, población algo mayor hoy).

| Categoría | Líneas | % |
|---|---|---|
| Coincidencia exacta (normalizada: mayúsculas, sin acentos, espacios colapsados) | 1.182 | 8,6% |
| Alta similitud (`difflib` ≥ 0,85), no exacta | 2.712 | 19,7% |
| Sin ningún parecido razonable | 9.841 | 71,6% |

**Riesgo de coincidencia múltiple, confirmado y con dos causas distintas:**

1. **Estructural, del lado del maestro.** De las 28.782 denominaciones
   normalizadas distintas (32.116 filas), 2.388 (8,3%) mapean a más de una
   matrícula distinta — afecta a 5.722 filas del maestro (17,8% del total).
   Es decir: incluso una coincidencia exacta y limpia con una denominación
   del maestro tiene ~1 entre 5 de probabilidad de no bastar por sí sola
   para identificar una única matrícula. De las 1.182 coincidencias
   exactas de la tabla de arriba, 33 caen en una denominación ambigua.
2. **Del umbral de similitud en sí.** De las 2.712 líneas de "alta
   similitud", **1.807 (66,6%)** tienen más de un candidato por encima del
   umbral 0,85 a la vez — la mayoría de los "casi seguro" no lo son tanto.
   Caso real que lo ilustra (de la propia muestra): *"TORNILLO CABEZA
   HEXAGONAL, M22X325 MM"* enlaza con 0,958 de similitud a *"TORNILLO
   CABEZA EXAGONAL M22X275 MM"* — **son tornillos de longitud distinta**
   (325 mm vs. 275 mm), un candidato de similitud alta pero
   sustancialmente incorrecto si se asignara solo. La similitud de texto
   no distingue una cifra que cambia en medio de una cadena por lo demás
   idéntica — justo el patrón que este catálogo tiene por decenas (M22,
   M25... × distintas longitudes).

El 71,6% "sin parecido" no es, en su mayoría, una carencia del método: es
descripción de servicio o partida alzada real (CONTEXTO.md sección 2,
"partida alzada... es legítima, no un error") que nunca tuvo matrícula
porque no es un material de catálogo — "Balasto sobre camión en cantera",
"PARTIDA ALZADA PARA IMPREVISTOS", "Engrasador completo con 1 distribuidor.
Carril 54 kg/ml" no tienen mejor candidato porque no deberían tenerlo.

**Conclusión, sin implementar nada (encargo explícito):** si esto se
construye, tiene que ser una cola de candidatos para confirmación humana
(mismo patrón ya en producción para `posible_duplicado_de`,
`app.catalogo.buscar_posible_duplicado_huerfana`, sesión 2026-09-07),
nunca una asignación automática ni siquiera para el 8,6% de coincidencia
exacta — la ambigüedad estructural del maestro (2.388 denominaciones que no
identifican un material único) hace que ni una coincidencia perfecta de
texto sea prueba suficiente por sí sola.

## Bloque 3 — Dos defectos pendientes

### 1. El precio unitario de 33.611.401 €: causa raíz encontrada y corregida

Localizado: `6.20/28510.0042`, `0046` y `0047` (mismo documento compartido
entre los tres expedientes hermanos, `codigo_precio` `611450216`,
"CZI-OB-B1-54-0,11(S/PROL)"). Comprobado contra el PDF real
(`pdfplumber` sobre la página 32 del anejo): la fila real es
`['611450216', 'CZI-OB-B1-54-0,11(S/PROL)', 'P16.2263.00', '03.361.140.1',
'', '7.915,61 €', '', None]` — el precio real es **7.915,61 €** (columna 5),
coherente con sus vecinos de tabla (todos entre 6.800 € y 9.040 €).

Causa raíz, verificada en `parsear_numero_es`
(`app/extraccion/normalizacion.py`): la columna 4 (donde vive el precio en
el resto de filas de esta tabla) sale vacía SOLO en esta fila, así que
`_recuperar_columna_fantasma` prueba la columna vecina anterior (índice 3)
antes que la siguiente (índice 5, la correcta) — y la anterior,
`'03.361.140.1'` (la referencia normativa E.T. del material, no un
importe), pasaba el parseo igual: `parsear_numero_es` no comprobaba que los
puntos de una cifra sin coma formaran una agrupación de miles real (grupos
de 3 dígitos tras el primero), así que le quitaba los puntos sin más y
devolvía `33611401`. Corregido con `_grupos_de_miles_validos`: rechaza
cualquier cadena cuyo último grupo no tenga exactamente 3 dígitos (salvo
que no haya ningún punto). 4 tests nuevos, 585 pasan.

**Revisados los otros casos del mismo tipo, por debajo de ese valor:** las
3.257 líneas del corpus que usan esta misma vía de recuperación de columna
fantasma para el precio se revisaron por magnitud — ninguna otra se acerca
al orden de los millones; la siguiente más alta es 458.451,02 €
(`6.23/28510.0051`/`0060`, código `P-0001`..`P-0006`), dentro de rango
plausible para equipo ferroviario caro y ya marcada con el mismo
`motivo_revision` de siempre para confirmación humana. No hay más casos del
defecto de agrupación de miles inválida en el rango investigado.

Verificado reprocesando los 3 expedientes reales contra el stack: las tres
líneas pasan de 33.611.401,00 € a 7.915,61 €, idéntico al valor real del
documento.

### 2. Los "9 grupos duplicados, 18 filas": el planteamiento no era correcto

**Esto cambia el planteamiento del encargo — anotado aquí, no bloqueado
esperando respuesta.** El encargo asumía que eran el hueco de idempotencia
ya documentado (`guardar_lineas_catalogo` no borra una fila de un reproceso
anterior cuya clave cambió). Verificado contra el PDF real y contra un
reproceso deliberado de los 3 expedientes: **no lo son.**

Los 18 registros son 9 pares/tríos de **materiales real y físicamente
distintos** (comprobado contra la página 35 del mismo anejo:
`615250090` "SCI-P-54-DD-318 P/DS-P-54-318-0'09-CR-D", `615250091`
"SCI-P-54-DI 318 P/DS-P-54-318-0'09-CR-D" y `615260094` "SCI-P-60-AR-CAC-
D.D. P/DSH-P-60-318-0,09" — tres matrículas de 9 dígitos distintas, tres
descripciones distintas, tres piezas de agujas de vía D/I con el mismo
precio de catálogo del fabricante, 18.268,00 € los tres) que **pierden su
matrícula y su descripción por el mismo defecto de mapeo de columnas de
"tabla sin cabecera"** ya conocido para este trío de expedientes (CONTEXTO.md,
sesión 2026-09-09): el modelo asigna la columna 0 (la matrícula real) a
`codigo_precio`, intenta leer `matricula` de la columna 1 (que es en
realidad la descripción) y la descarta por no tener forma de matrícula, y
`descripcion` acaba apuntando a una columna vacía para estas filas cortas
de 5 celdas. El texto real de la descripción SÍ queda, de hecho, capturado
-- dentro de `motivo_revision` ("valor de matrícula no reconocible,
descartado: ..."), solo que no en la columna `descripcion`.

Prueba decisiva: se reprocesaron los 3 expedientes a propósito para este
bloque. Si fuera un hueco de idempotencia, un reproceso adicional habría
generado una tercera copia (la clave inestable produce una fila nueva cada
vez). **No ocurrió** — las mismas 18 filas, con los mismos `id`, siguen
ahí, ni una más ni una menos: la clave es estable, el guardado es
idempotente de verdad para estas filas. Lo que parecía "duplicado" es un
artefacto de mirar solo las columnas visibles (`codigo_precio`,
`matricula`, `descripcion`, `precio_unitario`) después de que tres
materiales reales y distintos quedaran todos en blanco por el mismo motivo.

**Decisión: no se borra ni se fusiona nada.** Hacerlo habría eliminado 9
materiales reales y distintos del catálogo del cliente por parecerse en una
consulta SQL superficial — exactamente el tipo de "corrección automática
silenciosa" que CONTEXTO.md prohíbe (sección 12: "lo que no cuadra no se
corrige solo, va a la cola de revisión"). Las 18 filas ya están excluidas
del Excel entregable (mismo mecanismo de `evaluar_coherencia_mapeo` de la
sesión 2026-09-09, "tabla descartada del catálogo entregable"), así que no
hay impacto visible para el cliente hoy. Rediseñar el mapeo de columnas
para esta forma concreta de tabla sin cabecera (filas cortas, sin columna
de código de precio) queda pendiente para una sesión dedicada — no se
intenta aquí por el riesgo de tocar el mecanismo de caché de firma
estructural compartido con el resto del corpus sin una verificación
completa.

## Bloque 4 — Poda de filas huérfanas obsoletas

Cierra el hueco de idempotencia documentado desde la sesión de
verificación del Excel de 6.599 líneas (2026-09-08): `guardar_lineas_catalogo`
nunca borraba una línea de un reproceso anterior del MISMO documento que ya
no aparece en el nuevo, porque una línea sin `codigo_precio` ni matrícula
usa `hash(descripción + orden_aparicion)` como clave (`calcular_clave_linea`)
— si un arreglo posterior cambia qué texto cae en `descripcion` para esa
fila (exactamente lo que hicieron varios arreglos de mapeo de cabecera a lo
largo de esta y otras sesiones), la clave cambia y la fila vieja queda
huérfana en vez de sustituirse. 5 filas así se limpiaron a mano en su día;
sin poda automática, cada arreglo de mapeo futuro deja el mismo residuo.

**El bloqueo de aquella sesión era decidir qué pasa si solo se reprocesa un
subconjunto de las tablas de un documento — resuelto: no pasa.**
`procesar_anejo` (`app.extraccion.orquestador`) extrae siempre el documento
entero (todas sus tablas, todos sus grupos/lotes) en una sola pasada, y el
resultado solo se usa si termina sin excepción — si falla, ese documento
entero se salta este ciclo (`db.rollback()`) y la poda ni se invoca. Podar
por `(expediente_id, documento_id)` tras un `procesar_anejo` que sí terminó
es seguro: el conjunto de `id` tocados por TODAS las llamadas a
`guardar_lineas_catalogo` de ese documento en este ciclo es, por
construcción, el conjunto completo y actual de lo que ese documento
produce hoy.

Implementado: `guardar_lineas_catalogo` devuelve ahora `ids_tocadas`
(creadas + actualizadas, tras un `flush()` para tener `id` asignado);
`podar_lineas_obsoletas_de_documento` (`app/catalogo.py`) borra, dentro de
`(expediente_id, documento_id)`, cualquier línea que no esté en ese
conjunto — excluye explícitamente `heredado_de_matriz` como red de
seguridad barata (aunque el propio límite de documento ya la protege,
CONTEXTO.md sección 3: el pedido nunca procesa por su cuenta el documento
de la matriz). El orquestador acumula `ids_tocadas` de todos los grupos de
un documento y poda una sola vez al terminarlo, nunca dentro del bucle de
grupos (para que un grupo no pode lo que otro grupo del mismo documento
acaba de tocar). Silenciosa a propósito, sin `motivo_revision` (mismo
criterio que `_limpiar_huerfana_superada`, que ya borra huérfanas
superadas sin generar aviso): podar es idempotencia esperada, no un
hallazgo dudoso — se cuenta igual (`lineas_podadas`, nuevo campo en el
resumen de `POST /expedientes/{id}/extraer` y del ciclo de mantenimiento)
para que quede visible en el informe del reproceso. 7 tests nuevos
(`ids_tocadas`, y cinco variantes de la poda: borra lo obsoleto, no toca
otro documento, no toca otro expediente, no borra `heredado_de_matriz`,
sin nada que podar). 591 tests pasan.

Verificado contra el stack real: reprocesados los 3 expedientes del bloque
3 (otra vez) más una muestra aleatoria de 15 expedientes reales ya
completados — 22.724 líneas antes y después, ni una de más ni una de
menos, `lineas_podadas` presente en el resultado de cada trabajo (en `0`
para esta muestra: no había residuo que podar porque ya se habían
reprocesado varias veces con el código actual). El mecanismo queda armado
para el reproceso completo del bloque 5, que es donde de verdad se espera
que encuentre y limpie el residuo real de sesiones anteriores.

## Bloque 5 — Reproceso completo: copia de seguridad, foto de relleno, y un defecto encontrado en vivo

Copia de seguridad manual antes de empezar: `adif_20260910_160317.dump`
(2.866.750 bytes, 8 copias conservadas). Foto de relleno por columna antes
del reproceso (22.724 líneas):

| Columna | Relleno |
|---|---|
| `codigo_precio` | 84,9% |
| `matricula` | 39,5% |
| `descripcion` | 99,6% |
| `codigo_material` | 62,6% |
| `cantidad` | 65,9% |
| `precio_unitario` | 99,4% |
| `unidad_medida` | 84,7% |
| `baja_lote` | 54,0% |
| `precio_adjudicado` | 53,3% |
| `codigo_interno` | 0,0% (columna vestigial, nunca escrita a nivel de línea -- no es una regresión de esta sesión) |
| líneas con lote asignado | 90,2% |

Lanzado `POST /mantenimiento/ejecutar` (`forzar: true`,
`sindicacion_desactivada: true`) a las 16:03:55 UTC, trabajo `4097`, 358
expedientes activos.

### Defecto encontrado en vivo: `parsear_numero_es` sin `try/except` en cinco puntos más

A la hora y cuarto de reproceso (189/358 completados), 1 expediente
(`6.20/28510.0062`) apareció `fallido` con
`agrupación de miles no válida en '1.10' (¿un código, no un número?)` --
efecto colateral directo del arreglo del bloque 3: rechaza correctamente
un valor ambiguo, pero en cinco puntos del código la llamada a
`parsear_numero_es`/`parsear_importe_es`/`parsear_porcentaje_es` no estaba
protegida con `try/except`, así que la excepción escapaba hasta el
`except Exception` de cabecera de `ejecutar_extraccion_expediente`
(`orquestador.py:1312`), que sí marca `expediente.estado = fallido` y
**vuelve a lanzar la excepción** (`raise`) -- exactamente para que
`app.worker`/`app.queue.ejecutar_trabajo` puedan registrar el fallo del
`trabajo_cola`, pero con el efecto de que el expediente entero queda
`fallido` (una interrupción real) en vez de `pendiente_revision` (el
degradado correcto, CONTEXTO.md sección 12: "lo que no cuadra va a la cola
de revisión"). Localizado y corregido en los cinco puntos reales:

1. `app.extraccion.campos_pcsp.importe_como_decimal` -- el causante real
   del fallo de `6.20/28510.0062` (camino "Nº Lote: NNN" del Anuncio PCSP).
   Degrada a `INVALIDADO` (el mismo estado de tres que ya usa esta función
   para "encontrado pero no atribuible"), no a una excepción.
2. `app.extraccion.lotes._importe_o_none` (nuevo, dos puntos de llamada:
   `importes_licitacion` y `importe_adjudicacion` por lote) -- degrada a
   `None`, mismo criterio que "no encontrado".
3. `app.extraccion.orquestador` (camino LC27, `licitacion_lc27`/
   `adjudicacion_lc27`) -- ahora con `try/except` alrededor, deja el valor
   sin resolver (`None`) para que un documento posterior pueda resolverlo.
4. `app.extraccion.modelo_precio_indexado.detectar_modelo_precio_indexado`
   -- sigue buscando en las páginas siguientes en vez de abortar (alcance
   real limitado: solo los 3 expedientes conocidos de la segunda familia de
   baja).
5. `app.extraccion.baja` (`buscar_baja_en_texto`,
   `extraer_baja_declarada`) -- prueba el siguiente patrón/página en vez de
   propagar, defensa en profundidad aunque una baja con más de 3 dígitos en
   la parte entera es improbable en la práctica.

7 tests nuevos, 594 pasan. Solo 1 expediente había fallado por esta causa
en el momento de encontrarlo.

### Efecto secundario del despliegue en caliente: el ciclo se reinició, no se reanudó

Para que el arreglo cubriera el resto del reproceso (en marcha) se
reconstruyó y redesplegó `api`/`worker` (`docker compose up -d`). Esto
recreó el contenedor `worker`, interrumpiendo el trabajo `mantenimiento_ciclo`
(`4097`) a mitad de ejecución (~1h30, 200/358 completados). El mecanismo de
recuperación de trabajos huérfanos (`app.queue.reclamar_trabajos_huerfanos`,
umbral 300s) lo detectó como huérfano y lo reintentó (`intentos` 1→2) --
pero el reintento **no reanudó por donde iba: volvió a ejecutar
`ejecutar_ciclo_mantenimiento` desde el principio** con el mismo payload
(`forzar: true`), así que re-evaluó y re-encoló los 358 expedientes
completos, sin distinguir los ~200 que el primer intento ya había
reprocesado con éxito segundos antes. Pendientes de extracción pasó de 156
a 511 de golpe (duplicados para buena parte de los ya hechos).

**Sin corrupción de datos** (CONTEXTO.md sección 9.9: reprocesar es
idempotente, así que repetir un expediente ya hecho no lo daña, solo
desperdicia tiempo) pero sí una duplicación real de horas de cómputo. **No
se ha cortado el reproceso** (encargo explícito del cliente: cortarlo ahora
sería peor). Causa raíz, riesgo real para este entorno concreto, y
propuesta de arreglo (sin implementar, para la próxima sesión) documentados
en CONTEXTO.md, sección "Pendiente de resolver" -- resumen: (1)
`bloqueado_en` nunca se refresca mientras un trabajo corre, así que
CUALQUIER reinicio del worker durante un `mantenimiento_ciclo` real (que
dura horas por diseño) lo marca huérfano casi con certeza, no como caso
raro -- y este entorno de desarrollo reinicia `dockerd`/WSL varias veces al
día, hallazgo ya documentado en sesiones anteriores; (2) `debe_extraer`
con `forzar=True` no distingue "obsoleto desde antes de este ciclo" de "ya
resuelto por un intento anterior de este mismo ciclo" -- la información
para distinguirlo (`Expediente.extraido_en` vs. `TrabajoCola.created_at`
del propio ciclo) ya existe, solo falta la comprobación.

**Riesgo abierto mientras el reproceso de esta sesión termina:** el trabajo
`4097` va ya por su segundo intento de tres (`max_intentos=3`) -- un tercer
reinicio del worker antes de que termine lo marcaría `fallido` en firme, no
huérfano-y-reintentable. El worker no se ha vuelto a tocar desde este
hallazgo.

### Resultado final

Pendiente de cerrar hasta que el reproceso (ahora en su segunda pasada
completa) termine -- ver el bloque 6 para el resultado final, la
comparación de relleno antes/después y el informe de cierre.
