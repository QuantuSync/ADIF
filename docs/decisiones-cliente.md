# Criterios del cliente

Registro histórico movido desde `CONTEXTO.md` (split de sesión 2026-09-05).
Ver `CONTEXTO.md` para el contexto vivo del proyecto.

---

## 27. Hasta dónde puede llegar el sistema con el estado del contrato (18/09/2026)

**Quién lo dijo y dónde.** **Isabel Ibáñez (ADIF)**, por escrito en el grupo de
trabajo, el **18/09/2026**.

**Qué dijo, literal en su contenido.** Sin acceso a SAP, **el último estado que
la herramienta puede conocer de un expediente es "Resuelta" o "adjudicado"**.
Los estados posteriores del contrato (los que solo existen dentro de SAP: en
ejecución, recepcionado, facturado, cerrado…) **los tendrán que indicar ellos
manualmente**.

**Lo damos por aceptado.** No hay nada que discutir ni que verificar contra el
corpus: es una afirmación sobre qué publica la Plataforma y qué no, y coincide
con lo que ya se venía midiendo. Un anuncio de la Plataforma llega como mucho
hasta la adjudicación y la formalización del contrato; lo que le pase al
contrato después no se publica ahí.

**Qué cambia en el sistema.**

1. **Es el techo de la columna "Estado que consta publicado en la Plataforma"**
   de la hoja "Conciliación". El bloque 6 de la sesión 2026-09-18 (quinta
   parte) hace que esa columna use el documento descargado cuando prueba una
   etapa posterior a la del último boletín de sindicación — y la escalera de
   estados termina en "Resuelta" justo por esta decisión, no por falta de
   ganas de seguir: no hay ningún documento publicado del que se pueda leer un
   estado posterior.
2. **No cambia nada de la columna "Estado según ADIF"**, que es la otra mitad
   de la respuesta: ahí es donde caben esos estados posteriores, porque salen
   del listado que ADIF nos envía sacado de su SAP. Las dos columnas siguen
   separadas justamente por esto (sesión 2026-09-18, continuación, bloque 3):
   una dice lo que publica la Plataforma, la otra lo que sabe ADIF.
3. **No se intenta deducir un estado posterior de ningún documento.** Si algún
   día aparece un PDF que parezca decir "en ejecución", no se usa: el acuerdo
   es que eso lo indican ellos.

Ver también CONTEXTO.md sección 7, "Qué puede y qué no puede saber el sistema
sobre el estado de un expediente".

---

## 26. Criterios de alcance del cliente, y su contraste contra el corpus real (sesión 2026-09-04)

Tres criterios que llegan **del cliente**, no de nuestro propio análisis —
marcados así explícitamente porque **dos de los tres no se sostienen tal
cual contra los documentos reales** del corpus. Se verificaron contra
documentos reales antes de tocar código (encargo explícito de esta sesión):
donde contradicen lo ya documentado (CONTEXTO.md sección 3, `docs/hallazgos-extraccion.md` sección 19), se implementó
la parte que la evidencia confirma, no la versión literal del cliente. El
motivo de cada decisión queda aquí para poder explicárselo sin que parezca
que no se le hizo caso.

(la parte de autoridad del PDF sobre sindicación, que también salió de esta
sesión, se documenta en `docs/identidad-expediente.md`)

### 1. "Solo bajas de material por lotes; la obra queda fuera de alcance" (criterio del cliente)

Sin contradicción, pero **sin ningún efecto medible en el corpus actual**:
verificado que el único departamento presente en los 45 expedientes
(`28510`) es literalmente "Suministros Red Convencional" — el campo "Tipo
de Contrato" de los documentos PCSP reales muestreados a mano dice
"Suministros", nunca "Obras", y `docs/analisis-corpus.md` tampoco menciona
ningún caso de obra.

Implementado como guarda para cuando aparezca uno, no como reacción a un
caso real de hoy: `app.extraccion.campos_pcsp` ahora lee el campo "Tipo de
Contrato" del Anuncio PCSP (misma etiqueta fija ya leída en la etapa 2 de la
cascada — el dato ya estaba en el documento, solo no se leía).
`app.extraccion.orquestador._detectar_contrato_obra` lo comprueba nada más
clasificar los documentos; si dice "Obras" (o "obra"), el expediente pasa a
un estado nuevo, **`fuera_de_alcance`** (`EstadoExpediente`, migración
`0013`, `ALTER TYPE ... ADD VALUE`, no reversible) — distinto de
`sin_publicar` (ahí no hay expediente que leer) y de `pendiente_revision`
(ahí hace falta que un humano decida sobre datos reales): aquí no hay nada
que decidir, es un tipo de contrato que este motor no está pensado para
leer. El resto de la cascada de ese expediente sigue corriendo igual que
antes de detectarlo — **deliberadamente no se saltó**, a diferencia del
criterio de pliegos de abajo: ningún caso real de hoy justifica la
complejidad de cortar el pipeline a medias, y el motivo final se sobrescribe
con el mensaje correcto de todas formas. Si en el futuro un contrato de obra
real resulta caro de procesar así, es el sitio a revisar.

Ninguno de los fixtures reales de este corpus trae el literal "Tipo de
Contrato" (el que sí lo trae, el "Documento de Pliegos", no está entre los
fixtures fijos, CONTEXTO.md sección 13) — probado con un caso sintético (`PaginaTexto`
directo, sin PDF) para las dos ramas ("Suministros" no dispara nada,
"Obras" sí).

### 2. El mínimo exigible para dar por buena una baja de lote (criterio del cliente)

**Aplicado tal cual, sin contradicción.** Antes de esta sesión,
`app.extraccion.precios_unitarios.calcular_baja_efectiva` exigía que la baja
declarada en texto cuadrase (con tolerancia de medio punto) con la baja que
resultaba de los importes de licitación y adjudicación — un desajuste
mandaba el expediente entero a revisión (CONTEXTO.md sección 12, "lo que no
cuadra no se corrige solo"). El cliente pide un mínimo más laxo: lote,
expediente y baja declarada bastan. Se quitó la exigencia de que cuadren —
la baja declarada gana siempre que exista; solo sigue exigiéndose revisión
cuando no hay ninguna baja de la que partir (el caso de precios unitarios
sin baja declarada, CONTEXTO.md sección 4, no cambia).

**Efecto medido, verificado contra el stack real (no solo predicho):** de
los 7 expedientes que `docs/identidad-expediente.md` sección 22 agrupaba como "baja declarada no
cuadra con la baja por importes", **4 pasan a completado** —
`6.23/28510.0139`, `6.24/28510.0094`, `6.24/28510.0130`, `6.25/28510.0019`.
Los otros 3 de ese mismo grupo (`6.24/28510.0117`, `6.24/28510.0203`,
`6.25/28510.0028`) **siguen en revisión**: al mirar su motivo completo (no
solo el resumen de esa sección) tenían, además del desajuste de baja, un
segundo problema independiente — valores de celda que no se pudieron
interpretar (39, 3 y 4 líneas respectivamente) — que este criterio no toca.
Esa sección los agrupaba bajo un solo motivo compuesto; con el desajuste
de baja ya resuelto, el motivo restante que queda visible es justo ese
segundo problema, antes oculto detrás del primero.

### 3. Reglas sobre tipos de documento (criterio del cliente) — verificado contra los documentos reales antes de aplicar nada

**"Los pliegos no tienen contenido, son enlaces — se pueden ignorar":
contradicho en parte por el corpus real, y ya apuntado antes de esta sesión
(CONTEXTO.md sección 3).** `TipoDocumento.pliego` mezcla tres documentos distintos,
distinguibles por el marcador que los clasificó
(`app.extraccion.clasificador`):

- **"documento de pliegos"** (portada administrativa PCSP, 4-7 páginas):
  confirmado sin cuadro de precios — solo metadatos y enlaces a
  "Rectificaciones al Pliego" / versiones anteriores del documento.
  Coincide con el criterio del cliente.
- **"pliego de clausulas administrativas"** (PCAP, decenas de páginas de
  cláusulas legales): confirmado sin cuadro de precios tampoco, verificado
  contra un documento real de 93 páginas
  (`6.23/28510.0018_ANEJO_2.pdf`). Coincide con el criterio del cliente.
- **"pliego de prescripciones tecnicas"** (típicamente `*_ANEJO_1.pdf`,
  CONTEXTO.md sección 3): **contradice el criterio del cliente.** Es el pliego técnico
  completo, y el cuadro de precios es una sección interna suya — en este
  corpus, **544 líneas de catálogo reales** (21 de 21 documentos con este
  marcador aportan datos; 0 de los ~75 documentos con los otros dos
  marcadores aportan ninguna). Saltar todo lo que hoy cae en `pliego` habría
  eliminado la fuente principal de datos de la mayoría de expedientes
  completados.

Implementado como el cliente pedía, pero **solo para los dos marcadores que
la evidencia confirma vacíos**: `app.extraccion.clasificador.
es_pliego_sin_precios` distingue los tres; el orquestador salta la
localización y extracción de tabla enteras (etapas 3-4) para esos dos,
nunca para el pliego técnico.

**"Los contratos vienen en dos documentos y uno solo enlaza al otro; uno es
descartable": contradicho por el corpus real, no implementado.** Decodificado
por completo el par `CONTRATO_1`/`CONTRATO_2` de `6.23/28510.0051`: los dos
tienen ~207 páginas (ninguno es un enlace corto al otro) y son **dos
contratos distintos** — "Contrato nº: 6.23/28510.0060" con adjudicatario
MIERES RAIL, S.A. frente a "Contrato nº: 6.23/28510.0061" con adjudicatario
TALLERES ALEGRÍA, S.A. (probablemente dos lotes del mismo expediente, cada
uno con su propio contrato firmado). Y cuál de los dos aporta líneas de
catálogo no es consistente en el resto del corpus (a veces `_1`, a veces
`_2`, casi siempre ninguno) — no hay una regla estática segura. Se deja la
cascada como estaba: abre los dos, la etapa 3 (localizador) ya descarta
barato las páginas sin tabla.

**"Las adjudicaciones siempre tienen información relevante": sin
contradicción, no necesitó cambio de código.** Ya es el comportamiento
actual — `resolucion_adjudicacion` y `propuesta_lc27`/`propuesta_dt` ya se
procesan siempre por etiqueta fija (etapa 2 de la cascada) y nunca se
saltan.

**"Los anejos nunca están duplicados (los contratos sí)": consistente con
el corpus real, no necesitó cambio de código.** `TipoDocumento.anejo`
(distinto del pliego técnico con marcador `*_ANEJO_1.pdf`, que cae en
`pliego`) aparece como máximo una vez por expediente en toda la muestra
comprobada; los contratos, como arriba, sí se repiten en pares.

### Tiempo ahorrado por saltar pliegos

Medido directamente, no estimado a ciegas: `procesar_anejo`
(`app.extraccion.pipeline_anejo`) vuelve a abrir el PDF y a extraer el texto
de **todas** sus páginas, aunque la clasificación (etapa 1) ya lo había
hecho — es trabajo duplicado para cualquier documento que llega a esa
función. Con el PCAP real de 93 páginas (`6.23/28510.0018_ANEJO_2.pdf`), esa
segunda pasada de extracción de texto cuesta **7,67 s**; la localización de
páginas candidatas en sí es barata (8 ms) — el coste está casi entero en
releer el PDF. La portada administrativa (4-7 páginas) cuesta en cambio
~0,12 s, casi nada. Saltar el documento entero antes de esa segunda pasada
ahorra ese tiempo íntegro — verificado en vivo sobre `6.24/28510.0008`, que
saltó 2 documentos (`documentos_pliego_omitidos` en el resultado de
`ejecutar_extraccion_expediente`) sin cambiar su resultado (mismo
`baja_global`, mismo estado `completado`).

Con `docs/analisis-corpus.md` (27 PCAP reales y 27 portadas "Documento de
Pliegos" en el corpus): estimado sobre esas cifras, **≈ 27 × 7-8 s ≈ 3-4
minutos** ahorrados en un reproceso completo del corpus, casi enteros en los
PCAP grandes — las portadas pequeñas aportan menos de un segundo en
conjunto.

### Medición final sobre el corpus real

Reprocesados los 53 expedientes reales (45 del corpus fijo +
8 matrices de acuerdo marco descubiertas en la sesión de herencia,
`docs/identidad-expediente.md` sección 20) contra el stack real -- `docker compose`, sin dobles de test --, con
`forzar=true` y sindicación desactivada para no volver a contaminar la base
de datos. Dos reprocesos completos en esta sesión: el primero con los tres
criterios del cliente (arriba); el segundo, tras el arreglo urgente de
autoridad de fuentes (ver `docs/identidad-expediente.md`) y el de las 3 celdas con guion suelto (documentado allí también).

| | Antes de esta sesión | Tras los 3 criterios | Final |
|---|---:|---:|---:|
| `completado` | 14 | 16 | **20** |
| `pendiente_revision` | 24 | 22 | **18** |
| `sin_publicar` | 15 | 15 | 15 (sin cambio) |
| Líneas de catálogo | — | 2.208 | **2.208** (sin cambio: los arreglos posteriores no añaden líneas nuevas, solo dejan de descartar campos ya extraídos) |
| Matrículas en más de un expediente | 13 | 13 | **13** (sin cambio) |

Sobre los 45 (excluyendo las 8 matrices, todas `sin_publicar`): completado
20, pendiente_revision 18, sin_publicar 7 — suma 45.

### Limpieza de la base de datos

La base de datos de desarrollo llevaba 62 expedientes, con contaminación de
sesiones de prueba anteriores (bloque 3, intervalo corto de 45 s: cada
ejecución programada relanzaba el descubrimiento por sindicación del mes en
curso y daba de alta expedientes reales de periodos no comparables con el
corpus fijo — `4.26/28510.0020`, `6.26/28510.0016`, `3.23/28510.0135`,
`6.24/28510.0106` —, más dos re-altas de `6.20/28510.0054` y
`6.20/28510.0094` de las pruebas de reinicio de `dockerd`). Eliminados con
sus dependientes (documentos, líneas de catálogo, lotes, trazas, trabajos de
cola), dejando exactamente el corpus real: los 45 expedientes de
`docs/analisis-corpus.md` más las 8 matrices que la herencia de acuerdo
marco (`docs/identidad-expediente.md` sección 20) descubrió y creó a partir de ellos — 53 filas en total,
ninguna de prueba.

### Fixtures de regresión

`tests/extraccion/test_clasificador.py` (4 casos nuevos: el pliego técnico
real nunca se marca sin precios, la portada administrativa sintética sí, el
PCAP sintético sí, un documento no-pliego real nunca se marca).
`tests/extraccion/test_precios_unitarios.py` (1 caso renombrado: la baja
declarada que no cuadra ya no exige revisión, se da por buena).
`tests/extraccion/test_campos_pcsp.py` (2 casos: el fixture real de pedido
derivado no trae el campo y no revienta, "Obras" sintético lo dispara).
`tests/extraccion/test_orquestador.py` (3 casos para
`_detectar_contrato_obra`: marca "Obras", ignora "Suministros", ignora
documentos que no son `anuncio_pcsp`). `tests/test_catalogo.py` (2 casos: un
guion suelto en matrícula no marca revisión, un guion suelto en cantidad
tampoco — con los datos reales de `6.24/28510.0117` y `6.24/28510.0203`).
`tests/test_worker.py` (nuevo, 5 casos para `_contrastar_con_sindicacion`:
un desajuste no baja de `completado` ni toca `error`, un desajuste sobre un
expediente ya en revisión no pisa su motivo real, sin desajuste el aviso
queda vacío, un reproceso limpia un aviso que ya no aplica, un expediente
`fallido` nunca se contrasta). Ningún PDF nuevo — todo lo verificado contra
documentos reales de esta sesión (el PCAP de 93 páginas, las portadas
administrativas, el par de contratos de `6.23/28510.0051`, los dos LC.27 de
lote de `6.24/28510.0088` y `6.23/28510.0129`) se inspeccionó directamente
sobre el corpus ya descargado en el volumen de Docker, sin copiarlo al
repositorio (CONTEXTO.md sección 13: no se meten los PDFs completos).

---

## Pendientes ya resueltos (histórico)

Bullets que estaban en "Pendiente de resolver" de `CONTEXTO.md` y ya se
cerraron en sesiones posteriores. Movidos aquí íntegros al recortar
CONTEXTO.md (sesión 2026-09-05) para no perder el rastro de la decisión.

- **Resuelto (sección 21 de `docs/identidad-expediente.md`, sesión de
  corrección de identidad):** los 8
  expedientes con `codigo_expediente` etiquetado con el código de su MATRIZ
  se renombran solos, en la etapa de extracción, al valor real que declara
  su propio Anuncio PCSP.
- **Resuelto en la práctica, sin verificar la causa raíz (sección 22 de
  `docs/identidad-expediente.md`, sesión
  de expedientes sin publicar):** de las 8 matrices reales que este corpus
  necesita (5 en `2.18/04703`, 3 en `2.24/04110`) más los 6 expedientes de
  `docs/analisis-corpus.md` sin documentos, **los 14 códigos se comprobaron a mano en la
  Plataforma y no devuelven resultados** — no están publicados, no es un
  fallo del scraper. Se marcan `sin_publicar` (estado nuevo, distinto de
  `fallido` y de `pendiente_revision`) y dejan de contar como trabajo
  pendiente; las métricas del proyecto se miden desde ahora sobre los 31
  expedientes reales restantes, no sobre 45. **Por qué no están publicados
  sigue sin verificar** (archivado, publicado bajo otro código, tipo de
  procedimiento fuera de "Licitaciones") — pero ya no bloquea nada, así que
  deja de ser una prioridad. Patrón observado, con 14 casos: todo código que
  empieza por `2.`, `3.` o `4.` falla la búsqueda; todo lo que empieza por
  `6.` funciona. Es una correlación, no una regla verificada — no se ha
  construido ningún atajo de código que rechace un `2./3./4.` nuevo sin
  intentarlo, solo se documenta el patrón.
- **Resuelto en la sesión de identidad de lote (sección 27 de
  `docs/identidad-expediente.md`):** `6.24/28510.0088`
  y `6.23/28510.0129` (y 13 expedientes multi-lote más, no solo estos dos) no
  son pedidos de un solo lote — son licitaciones de varios lotes de las que
  solo teníamos documentos de una parte. El código propio de cada lote
  (`6.24/28510.0113`, `6.23/28510.0143`...) se modela ahora como
  `lotes.codigo_expediente_lote`, atributo del lote, no como fila de
  `Expediente` nueva — decisión explícita del cliente (esa sección): la
  identidad derivada de la partición en lotes no justifica la complejidad de
  expedientes nuevos. Lo que seguía pendiente aquí (cobertura parcial nunca
  mostrada como completado) queda cerrado.
- **Resuelto: sindicación como fuente secundaria** (`docs/hallazgos-sindicacion.md`,
  sección 24, "Mantenimiento automático — bloque 2"): implementada como
  descubrimiento de expedientes nuevos y contraste de importes, siempre con
  la navegación como respaldo obligatorio para los documentos en sí, nunca
  como sustituto — tal y como se dejó planteado originalmente.
