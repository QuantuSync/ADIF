# Ficheros huérfanos y autorreferencia de matriz (sesión 2026-09-06)

Ataca dos anomalías de datos detectadas de pasada en sesiones anteriores y
dejadas sin investigar: los 7 ficheros huérfanos de `3.23/28510.0135`
(`docs/comparacion-corpus-sharepoint.md`, bloque 5) y la autorreferencia de
matriz de `6.23/28510.0109` (cuarta variante del mismo síntoma que
`docs/identidad-expediente.md` secciones 20-21 y 27 ya documentan).

---

## 1. Ficheros huérfanos de `3.23/28510.0135`

### Causa: no es un fallo de registro, es una limpieza de base de datos que borró datos reales

Verificado con los 7 ficheros (hash SHA-256[:16] recalculado y comparado
contra el nombre de fichero: los 7 coinciden, ningún fichero corrupto ni
manipulado) y con el histórico de sesiones:

- `docs/hallazgos-sindicacion.md` (sesión de sindicación, bloque 2):
  `3.23/28510.0135` se descubrió el mes de agosto de 2024 por descubrimiento
  real de sindicación, se descargó de verdad de la Plataforma, se extrajo, y
  el contraste de sindicación encontró una discrepancia real (licitación
  8.545,90 € extraída contra 271.629,53 € declarados por sindicación) — en
  ese momento el expediente SÍ tenía fila propia en `expedientes` y en
  `documentos`.
- `docs/decisiones-cliente.md` (sesión de criterios de alcance, "Limpieza de
  la base de datos"): una limpieza posterior identificó
  `3.23/28510.0135` (junto con `6.24/28510.0106`, `4.26/28510.0020`,
  `6.26/28510.0016`, y dos re-altas de `6.20/28510.0054`/`0094`) como
  "contaminación de sesiones de prueba" (un intervalo de mantenimiento corto
  de 45 s relanzaba el descubrimiento por sindicación repetidamente) y
  **borró la fila de `expedientes` con sus dependientes** (documentos,
  líneas de catálogo, lotes, trazas, trabajos de cola) por SQL directo, sin
  pasar por ningún endpoint de la API (no existe un `DELETE /expedientes` —
  verificado, `engine/app/routers/expedientes.py` solo tiene `GET` y
  `POST`).

**El diagnóstico de esa limpieza estaba equivocado para `3.23/28510.0135` (y
probablemente para `6.24/28510.0106`, no verificado aquí): no era un
expediente de prueba, era un expediente real del corpus, descubierto y
procesado legítimamente**, que solo compartía el síntoma superficial
("apareció en una sesión con el ciclo de mantenimiento a intervalo corto")
con los verdaderos artefactos de prueba (`6.20/28510.0054`/`0094`, re-altas
de pruebas de reinicio de `dockerd`, esos sí sin valor).

**Por qué quedaron ficheros huérfanos**: el borrado eliminó las filas de la
base de datos pero nunca tocó `/data/documentos` (el volumen `documentos` de
Docker, gestionado por `app.interfaces.document_storage.LocalDiskStorage`) —
no existe ningún código que borre ficheros de almacenamiento junto con un
expediente (no hay ningún camino de borrado de expediente en la aplicación
en absoluto), así que un borrado por SQL directo, sin pasar por una función
que también supiera limpiar el almacenamiento, no podía haber dejado otra
cosa que ficheros huérfanos.

### Comprobación sistémica: solo este expediente, ningún patrón más amplio

Comparado el listado completo de carpetas en `/data/documentos` (43) contra
las carpetas con al menos un `documentos.ruta_almacenamiento` registrado en
la base de datos (42): **una sola carpeta huérfana, `3.23_28510.0135`**. Los
otros cinco códigos que la misma limpieza borró (`6.24/28510.0106`,
`4.26/28510.0020`, `6.26/28510.0016`, `6.20/28510.0054`, `6.20/28510.0094`)
no dejaron ningún fichero en el volumen — o nunca llegaron a descargarse, o
si se descargaron sus ficheros ya no están (no investigado, fuera de
alcance: no hay nada que recuperar de ellos ahora mismo). No hay un segundo
caso de "documento guardado sin registrar" que arreglar en el código: la
causa fue un borrado manual sin su contraparte de almacenamiento, no un
fallo del camino normal de escritura (`app.scraping.job.ejecutar_scraping_expediente`,
que guarda y registra cada documento en el mismo bucle, confirmado leyendo
el código — no hay ninguna rama que guarde sin registrar).

**Se decide no construir una función de borrado de expediente en esta
sesión** (no pedida, y no hay ningún borrado pendiente que la necesite): el
hueco real era la ausencia total de un camino de borrado, que hizo que la
única limpieza real de esta base de datos se hiciera por SQL directo sin
ninguna comprobación. Anotado para si en el futuro hace falta borrar
expedientes de verdad: esa función tendría que borrar `storage.recuperar`
en sentido inverso (listar y borrar los ficheros de
`documentos.ruta_almacenamiento` antes o junto con las filas), no solo las
filas.

### Resolución: registrado y reprocesado

Los 7 ficheros son legítimos (hash íntegro, contenido de PDF real y
legible). Registrado el expediente `3.23/28510.0135` (id nuevo) y sus 7
documentos exactamente como lo habría hecho
`app.scraping.job.ejecutar_scraping_expediente` (mismo `tipo_documento` por
categoría, misma ruta de almacenamiento ya existente) sin volver a descargar
de la Plataforma real — los ficheros ya estaban íntegros en el volumen.
Encolada su extracción normal (`extraer_expediente`).

### Segundo hallazgo, verificando el resultado de la extracción: el mismo bug de sindicación de agosto de 2024, ahora explicado y arreglado

El primer reproceso (con el código de antes de esta sesión) reprodujo
exactamente el síntoma que `docs/hallazgos-sindicacion.md` ya había medido
en 2024: solo 1 de los 8 lotes reales con datos, motivo genérico "no se
extrajo ninguna línea de catálogo" en vez de señalar los 7 lotes que faltan.

**Causa raíz encontrada**: `3.23/28510.0135` ("Adquisición de ocho lotes de
maquinaria y herramientas...") no tiene ningún documento clasificado
`anuncio_pcsp` — sus 7 documentos son `resolucion_adjudicacion`, `contrato`
×2, `pliego` ×3 y `otro`. El único documento que declara "Nº de Lotes: 8" es
un **"Documento de Pliegos"**, clasificado `pliego` (con el marcador
"documento de pliegos", `es_pliego_sin_precios` = `True`, correcto: no trae
cuadro de precios).

`app.extraccion.orquestador._detectar_numero_lotes_pcsp` (sección 27 de
`docs/identidad-expediente.md`) solo miraba documentos
`TipoDocumento.anuncio_pcsp` — nunca encontraba el "Nº de Lotes: 8" de este
expediente porque vive en un documento tipado `pliego`, aunque el propio
docstring de `app.extraccion.clasificador` ya documentaba (sin sacar la
consecuencia) que "Documento de Pliegos" "comparte exactamente la misma
anatomía de etiquetas fijas" que un Anuncio PCSP. La cobertura parcial (1 de
8) nunca se calculaba: el expediente se quedaba con el motivo genérico de
"no hay catálogo", que no explica que faltan 7 lotes enteros — justo el tipo
de "dato que se ve bien y está mal" que CLAUDE.md sección 12 pide evitar
("un sistema que sabe cuándo no sabe vale más que uno que acierta cinco de
cinco").

**Arreglo, deliberadamente acotado** (no se toca la clasificación de
"documento de pliegos" como `pliego`, ni `es_pliego_sin_precios`, ni las
etapas 3-4 de la cascada que sí deben seguir saltándose para este tipo de
documento — CLAUDE.md sección 26, criterio del cliente, sigue vigente sin
cambios): `_detectar_numero_lotes_pcsp` ahora también acepta un documento
`pliego` cuyo marcador de clasificación fue literalmente "documento de
pliegos" (nuevo campo `_Documento.marcador`, y el helper
`_es_documento_de_pliegos_pcsp`, `engine/app/extraccion/orquestador.py`).
Un "pliego de cláusulas administrativas" (el otro marcador que también cae
en `pliego_sin_precios`) sigue excluido: no comparte esa anatomía de campos
fijos.

**Resultado verificado tras el arreglo, reprocesando el expediente real**:
`pendiente_revision`, motivo `"cobertura parcial: 1 de 8 lotes declarados
tienen baja/importe (con datos: 2)"` (el `2` es el identificador del único
lote con dato, "Lote 2" — coincide con el importe de licitación de
8.545,90 € que sindicación y el propio Contrato ya declaraban en 2024, ahora
explicado en vez de escondido detrás de un motivo genérico). Nunca
`completado`: sigue faltando el dato real de los otros 7 lotes, que este
sistema no puede inventar.

**Alcance del arreglo más allá de este expediente**: subido
`app.mantenimiento.frescura.VERSION_LOGICA_EXTRACCION` a `"2026-09-06.2"`
para forzar el reproceso de todo el corpus (igual que hace cualquier cambio
de la cascada, CLAUDE.md sección 23) y comprobar si algún otro expediente
real tiene el mismo patrón ("Documento de Pliegos" como única fuente de "Nº
de Lotes") sin detectar hasta ahora. Recuento del reproceso completo, más
abajo en la sección 3.

### Fixtures de regresión

`engine/tests/extraccion/test_orquestador.py`, 2 casos nuevos con
`_Documento`/`PaginaTexto` sintéticos (mismo patrón que los tests ya
existentes de `_detectar_contrato_obra`, sin necesidad de un PDF real):
`_detectar_numero_lotes_pcsp` encuentra "Nº de Lotes: 8" en un documento
marcado "documento de pliegos", e ignora el mismo campo en un "pliego de
clausulas administrativas".

---

## 2. Autorreferencia de matriz: cuarta variante, y seis casos más sin detectar

### Causa concreta de `6.23/28510.0109`

`6.23/28510.0109` no tiene ningún documento `anuncio_pcsp` (es
`propuesta_lc27` + `contrato` ×2 + `pliego` ×3), así que ninguno de los
caminos ya conocidos de autorreferencia (el campo "Licitación basada en el
acuerdo marco" del Anuncio PCSP, o la trampa de vocabulario "Nº EXPEDIENTE
MATRIZ" de una Propuesta LC.27, sección 27) pudo haber escrito el valor.

La causa real está en **el Excel de códigos de referencia
(`CODIGOS_PROYECTO_PATH`)**: su fila para `Nº Expediente = 6.23/28510.0109`
declara `MATRIZ = 6.23/28510.0109` — literalmente el mismo código, en el
dato de origen del cliente, no en ningún PDF. Verificado leyendo el Excel
real dentro del contenedor. La licitación es multi-lote genuina
("SUMINISTRO DE BALASTO RFIG - LINEA NORTE - 2 LOTES", coincide con la
"cobertura parcial: 1 de 2 lotes" que ya tenía el expediente por otra vía) y
no tiene ninguna matriz de acuerdo marco real — probablemente quien mantiene
el Excel usó la columna MATRIZ como "N/A, es su propio expediente agrupador"
para estas filas, el mismo tipo de confusión de vocabulario que la sección 2
de `CLAUDE.md` ya documenta para el PDF, ahora encontrada también en el
Excel.

`app.extraccion.cruce_codigos.asegurar_cruce_codigos` copiaba ese valor tal
cual a `expediente.codigo_matriz` sin comprobar nunca si coincidía con el
propio `codigo_expediente` — a diferencia de `cruzar_codigo_proyecto`
(arreglado en la sesión de pulido de la web, commit `0ce0562`: "evita
inventar la matriz cuando el expediente es su propia MATRIZ"), que solo
cubría el caso de cruzar por la columna MATRIZ, no el caso de que la propia
fila de "Nº Expediente" traiga una MATRIZ autorreferenciada.

### Comprobación sistémica: seis casos más, mismo origen

Consulta directa (`codigo_matriz = codigo_expediente`) sobre la base de
datos real: **7 filas, no 1** — `6.23/28510.0109`, `6.23/28510.0051`,
`6.23/28510.0066`, `6.23/28510.0139`, `6.24/28510.0124`, `6.20/28510.0054`,
`6.20/28510.0094`. Las 7 tienen el mismo patrón exacto en el Excel: su
propia fila de "Nº Expediente" declara `MATRIZ` igual a sí misma. Ninguna es
un acuerdo marco real; las que tienen descripción explícita en el Excel
("2 LOTES") son licitaciones multi-lote genuinas, coherente con el caso de
`0109`.

Las 7 ya estaban en `pendiente_revision` por otros motivos (cobertura
parcial de lotes, valores ilegibles) antes de esta sesión — la
autorreferencia no cambiaba su `estado`, pero sí mostraba un dato de matriz
falso en el catálogo y en la web mientras tanto.

### Arreglo: un único punto de escritura

`app.extraccion.cruce_codigos.asignar_matriz` (nueva función) es ahora el
único sitio del código que escribe `expediente.codigo_matriz`. Normaliza el
candidato y compara contra el propio `codigo_expediente` antes de escribir;
lanza `AutoreferenciaMatrizError` si coinciden, para que cada llamador
decida qué hacer con el intento (ignorar en silencio en la cascada de
extracción y en el cruce con el Excel — sección 7: "el sistema nunca inventa
una matriz" —, error 400 en la corrección manual desde la API). Soporta
`sobrescribir=False` (no pisa un valor ya existente, el caso por defecto) y
`sobrescribir=True` (corrección manual explícita).

Los cinco sitios que antes escribían `codigo_matriz` cada uno con su propia
comprobación (o sin ninguna) ahora pasan todos por `asignar_matriz`:

| Sitio | Antes | Después |
|---|---|---|
| `cruce_codigos.asegurar_cruce_codigos` (Excel) | Sin comprobación — la causa de esta sesión | `asignar_matriz`, atrapa `AutoreferenciaMatrizError` y no escribe nada |
| `orquestador` (campo "Licitación basada en acuerdo marco" del Anuncio PCSP) | Solo comprobaba `not expediente.codigo_matriz` | `asignar_matriz` |
| `identidad_expediente.corregir_identidad_expediente` (renombrado de identidad) | Ya era seguro por construcción (el código nunca puede coincidir con el recién renombrado) | `asignar_matriz`, mismo comportamiento, ahora por el punto único |
| `routers/revision.confirmar_revision_expediente` (corrección manual) | Sin comprobación | `asignar_matriz(sobrescribir=True)`, error 400 si autorreferencia |
| `routers/expedientes.crear_expediente` (alta manual/API) | Sin comprobación | `asignar_matriz`, error 400 si autorreferencia |

### Resolución de los datos ya corruptos

Los 7 expedientes ya tenían `codigos_cruzados = True` (el cruce con el Excel
ya se había intentado y no se repite nunca, por diseño —
`asegurar_cruce_codigos` es "una vez por expediente"), así que un simple
reproceso con el código arreglado no habría corregido el dato ya escrito: el
arreglo evita la próxima autorreferencia, no deshace la que ya ocurrió.
Corregido con una actualización directa dirigida
(`UPDATE expedientes SET codigo_matriz = NULL WHERE codigo_matriz =
codigo_expediente`, verificado antes y después, 7 filas afectadas, 0
restantes) — no hacía falta reprocesar la cascada entera para estos 7:
ningún otro dato (importe, baja, cobertura de lotes) dependía del valor de
`codigo_matriz` para ellos, y `matriz_expediente_id`/`matriz_conflicto`
seguían `NULL`/`False` en los 7 (nunca llegaron a intentar resolver una
matriz de acuerdo marco a partir del dato falso).

### Fixtures de regresión

`engine/tests/extraccion/test_cruce_codigos.py` (5 casos nuevos):
`asignar_matriz` escribe cuando no hay autorreferencia, lanza
`AutoreferenciaMatrizError` en autorreferencia, no pisa un valor existente
sin `sobrescribir`, sí lo pisa con `sobrescribir=True`, candidato vacío no
hace nada; y un caso de aceptación con el Excel real reconstruido
(`asegurar_cruce_codigos` con una fila `MATRIZ` autorreferenciada no escribe
nada, reproduce exactamente `6.23/28510.0109`).
`engine/tests/test_api_catalogo.py` (2 casos nuevos): `POST
/expedientes/{id}/revision/confirmar` y `POST /expedientes` devuelven 400
ante una matriz autorreferenciada y no escriben nada.

---

## 3. Recuento del reproceso completo

Ciclo de mantenimiento manual lanzado con `VERSION_LOGICA_EXTRACCION =
"2026-09-06.2"` (fuerza el reproceso de todo el corpus, igual que cualquier
cambio de la cascada): descubrimiento de sindicación sin novedades (61
expedientes ADIF totales, 4 tras el filtro, 0 nuevos — ninguna descarga
lanzada), 43 expedientes evaluados (58 en la base menos los 15
`sin_publicar`, que no se reprocesan por diseño, CLAUDE.md sección 22), 43
extracciones relanzadas, 0 fallidas, 1.587 s de duración total.

| | Antes de esta sesión | Después |
|---|---:|---:|
| `completado` | 4 | **4** (sin cambio) |
| `pendiente_revision` | 38 (+1 nuevo, `3.23/28510.0135`, tras registrarlo) | **39** |
| `sin_publicar` | 15 | 15 (sin cambio) |
| Líneas de catálogo | 3.036 | **3.036** (sin cambio) |
| Expedientes con `codigo_matriz` autorreferenciada | 7 | **0** |
| Ficheros huérfanos en el volumen de documentos | 1 (`3.23/28510.0135`, 7 ficheros) | **0** |

**Cero cambio en los agregados del catálogo aparte de las dos correcciones
esperadas** (0135 registrado y en revisión con su motivo real; 0109 y los
otros 6 con la matriz falsa quitada): el reproceso completo del corpus con
`_detectar_numero_lotes_pcsp` ampliado no encontró ningún otro expediente
con el mismo patrón ("Documento de Pliegos" como única fuente de "Nº de
Lotes"), y ninguna otra extracción cambió de resultado — la ampliación era
correcta y acotada al caso real que la motivó, sin efectos colaterales en el
resto de los 42 expedientes reprocesados.

`3.23/28510.0135` y `6.23/28510.0109` quedan ambos en `pendiente_revision`
con su motivo real y explícito ("cobertura parcial: 1 de 8" y "1 de 2"
respectivamente) — comportamiento correcto, no un fallo pendiente: falta
dato real de los lotes que ni sindicación ni ningún documento local
declaran, y este sistema no lo inventa (CLAUDE.md sección 7 y 12).
