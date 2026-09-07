# Hallazgos de sindicación

Registro histórico movido desde `CONTEXTO.md` (split de sesión 2026-09-05).
Ver `CONTEXTO.md` para el contexto vivo del proyecto.

---

## 17.1 Hallazgos de sindicación (datos abiertos, sesión 2026-09-02)

Sesión dedicada a comprobar si el XML CODICE de sindicación (ZIP mensual
`licitacionesPerfilesContratanteCompleto3_AAAAMM.zip`) puede simplificar el
descubrimiento de documentos. No tocó extracción ni el scraper. Verificado
contra los ZIP de agosto 2024 y mayo 2025, cruzando tres expedientes reales
ya presentes en `engine/tests/fixtures/pdfs`: `6.24/28510.0103` (pedido de
acuerdo marco, matriz `2.18/04703.0019`), `6.24/28510.0088` y
`6.24/28510.0193`.

- **Existe un cuarto tipo de referencia documental que la especificación no
  cita en el apartado 4.9**: `cac-place-ext:GeneralDocument`. Es ahí, no en
  `LegalDocumentReference`/`TechnicalDocumentReference`/
  `AdditionalDocumentReference`, donde apareció el único contrato firmado que
  se encontró en toda la muestra.
- **La cobertura documental es inconsistente y no se puede dar por
  garantizada.** El expediente `6.24/28510.0103` — un pedido derivado de
  acuerdo marco — no tiene **ninguna** referencia documental en ninguno de
  sus estados (`ADJ` y `RES`), pese a que el scraper sí encuentra su
  `ADJUDICACION_1.pdf` navegando. Los pedidos de acuerdo marco son un patrón
  dominante en el corpus de ADIF (CONTEXTO.md sección 3). **Consecuencia: la sindicación
  no puede ser la fuente principal de documentos.**
- **La Propuesta LC.27 y el Anuncio PCSP de adjudicación no aparecieron nunca**
  en la muestra. Cuando hay algo de la fase de adjudicación, es el contrato
  (`GeneralDocument`, ver primer punto), y solo a veces — ausente en
  `6.24/28510.0103` y en `6.24/28510.0088` (este último aún en fase `PUB` en
  los meses descargados).
- **La MATRIZ no existe como campo estructurado.** Se buscó
  `FrameworkAgreement`/`AcuerdoMarco` en el mes completo de agosto 2024: cero
  resultados. El cruce con la matriz sigue dependiendo de la extracción por
  etiqueta fija del Anuncio PCSP (CONTEXTO.md sección 7), igual que hoy.
- **No hay campo de baja porcentual en el XML.** Y lo confirma desde una
  fuente independiente el hallazgo central de la sección 4 de CONTEXTO.md: en
  `6.24/28510.0103` y en `6.24/28510.0193`, el importe de licitación y el de
  adjudicación (`TaxExclusiveAmount` en ambos bloques) son el mismo número.
  La baja real (0,30 % en `6.24/28510.0193`) solo estaba en el texto del
  contrato, no en ningún campo del XML.
- **Nomenclatura de importes, verificada con datos reales — no hay
  inversión.** En `ProcurementProject/BudgetAmount`, `TaxExclusiveAmount` es
  el importe sin impuestos y `TotalAmount` el importe con impuestos. En
  `TenderResult/AwardedTenderedProject/LegalMonetaryTotal`,
  `TaxExclusiveAmount` sigue siendo sin impuestos, pero el importe con
  impuestos se llama `PayableAmount`, no `TotalAmount` — son campos distintos
  en cada bloque, así que el error del apartado 4.11.3 de la especificación
  no genera ambigüedad real: los dos expedientes contrastados con su PDF
  cuadraron exactamente.
- **Un mismo expediente puede aparecer varias veces con el mismo `<id>`**
  dentro de un mismo ZIP mensual — hasta tres versiones distintas observadas
  para `6.24/28510.0193` en mayo 2025 (`ADJ`, `RES`, `RES`). Hay que quedarse
  siempre con la más reciente por `<updated>`.

---

## 24. Mantenimiento automático — bloque 2: descubrimiento por sindicación (sesión 2026-09-04)

Cierra el segundo de los tres bloques de la sesión de mantenimiento
automático (bloque 1 en `docs/mantenimiento-automatico.md`, sección 23, base
de este). Hoy los expedientes salían solo del Excel de códigos, mantenido a
mano; este bloque los descubre solo, por la vía de sindicación que la
sección 17.1 de arriba ya había descartado como fuente de documentos pero
dejaba abierta como fuente de descubrimiento.

### Hallazgo que cambió el planteamiento, resuelto con el usuario antes de escribir código

Antes de construir el filtro se comprobó, contra el ZIP real de agosto 2024
(122 MB comprimidos, 89 ficheros .atom, ~1,3 GB de XML), qué trae
realmente filtrar "por órgano de contratación = ADIF": **219 expedientes
únicos**, repartidos en más de treinta códigos de departamento distintos
(27507, 20830, 24108, 30108, 04110, 28520...) bajo cuatro
órganos reales (ADIF - Presidencia, ADIF -Consejo de Administración,
ADIF Alta Velocidad - Presidencia, ADIF Alta Velocidad - Consejo de
Administración) — desde obra civil de Alta Velocidad por decenas de
millones de euros hasta los expedientes de suministro que ya conoce el corpus.
**Los 45 expedientes del corpus, y todos los ejemplos de este documento,
son del departamento 28510** — verificado cruzando 6.24/28510.0088 y
6.24/28510.0103 (el pedido derivado de `docs/identidad-expediente.md`,
sección 20) contra sus entradas
reales del feed: aparecen tal cual, órgano ADIF - Presidencia, importes
coincidentes con lo ya extraído de los PDF. Filtrar solo por órgano habría
dado de alta en masa expedientes de un tipo de contrato (obra civil, sin
baja única por lote) que la cascada de extracción no está pensada para
leer — pendiente_revision en masa que no sería un fallo real, solo alcance
mal puesto.

Se preguntó al usuario cómo acotar el descubrimiento antes de construir el
filtro (memoria de sesión: pausar ante un hallazgo que cambia el
planteamiento). Decisión: **filtrar por departamento, configurable, no una
constante en código** — SINDICACION_DEPARTAMENTOS_ADIF (lista separada
por comas, 28510 por defecto). Añadir un departamento nuevo es cambiar una
variable de entorno, nunca desplegar código nuevo. El informe de esta
sesión mide, para dimensionar el alcance potencial: 219 expedientes ADIF
totales en agosto de 2024, 5 tras el filtro de departamento (agosto) — y,
verificado también contra el periodo en curso de esta sesión (septiembre de
2026, ver más abajo), 61 totales / 4 tras el filtro.

### Qué se construye

Paquete nuevo app/sindicacion/:

- **cliente.py** — descarga el ZIP mensual
  (licitacionesPerfilesContratanteCompleto3_AAAAMM.zip, sindicación 643)
  en streaming a disco (httpx.stream, chunks de 1 MB, nunca
  response.content entero — el fichero real pasa de 100 MB). **Hallazgo de
  scraping, mismo patrón que la sección 17 de `docs/hallazgos-scraping.md`**
  ("el WAF distingue por tipo de
  URL"): una petición HEAD sin cabeceras se queda sin respuesta; una GET
  con User-Agent de navegador real responde 200 con curl plano, sin
  sesión de navegador ni Playwright — verificado en vivo, dos veces
  (agosto 2024 completo, ~122 MB en ~460 s; y el periodo en curso de esta
  sesión). No se aisló si lo que importaba era el método o la cabecera; por
  seguridad, el cliente siempre manda una User-Agent real.
- **atom_parser.py** — parseo incremental del XML CODICE:
  zipfile.ZipFile.open() da cada .atom en streaming (nunca se carga el
  ZIP ni un miembro entero en memoria) y ElementTree.iterparse procesa una
  entry a la vez, liberándola (clear(), más el truco estándar de
  limpiar también los hermanos ya procesados de la raíz) — verificado
  procesando las 44.355 entradas de un solo .atom en ~18 s. "Ficheros ATOM
  encadenados" (sección 17.1 de arriba) significa que el propio ZIP ya trae
  todas las páginas de la cadena (link rel="next" apunta a otro .atom
  del mismo ZIP): no hace falta ninguna llamada de red adicional para seguir
  la cadena.
- **descubrimiento.py** — filtra (órgano contiene "adif", departamento en
  la lista configurada), deduplica por codigo_expediente quedándose con
  la entrada más reciente por updated (sección 17.1 de arriba: "un mismo
  expediente puede aparecer varias veces"), da de alta los expedientes
  nuevos (con el codigo_expediente real, el mismo que usa todo lo demás
  del sistema — es el mismo cbc:ContractFolderID que ya usan los 45 del
  corpus) y guarda una instantánea en sindicacion_expedientes (tabla
  nueva, migración 0012) — **nunca escribe encima de expedientes/
  lotes**, es una fuente independiente. Detecta cambio de estado
  (ContractFolderStatusCode: PUB→ADJ→RES...) en un expediente que
  YA tenía documentos y, solo en ese caso, encola su descarga él mismo — es
  la única señal de "novedad" que el bloque 1 no tenía por sí solo (un
  expediente con documentos nunca se redescarga solo, sección 23 de
  `docs/mantenimiento-automatico.md`). Nunca
  regresa a un dato de sindicación más viejo que el ya guardado (relevante
  si algún día se reprocesa un periodo desde cero).
- **contraste.py** — bloque 2, punto 4: compara
  Expediente.importe_licitacion/importe_adjudicacion (lo que extrajo la
  cascada de los PDF, siempre "sin impuestos", CONTEXTO.md sección 4) contra
  sindicacion_expedientes.importe_*_sin_impuestos, con tolerancia (1%
  relativo o 1 euro absoluto, lo mayor) para no disparar por ruido de redondeo
  entre dos fuentes independientes. Si no cuadra: si el expediente estaba
  completado, baja a pendiente_revision con el motivo (los dos valores,
  para que quien revise no tenga que ir a buscarlos); si ya estaba en
  revisión por otra causa, se añade el motivo sin pisar el que ya había.
  Nunca contrasta un fallido (no hay un importe fiable con el que
  comparar, y esconder el motivo real del fallo sería peor que no
  contrastar). Se invoca desde app.worker.procesar_extraer_expediente,
  justo después de estampar frescura (bloque 1) — mismo sitio, mismo
  finally, sin tocar app.extraccion.orquestador.
- **Nomenclatura de importes, confirmada de nuevo con datos reales** (ya
  verificada en la sección 17.1 de arriba): en ProcurementProject/
  BudgetAmount, TaxExclusiveAmount es sin impuestos y TotalAmount con
  impuestos; en TenderResult/AwardedTenderedProject/LegalMonetaryTotal,
  TaxExclusiveAmount sigue sin impuestos pero el importe con impuestos es
  PayableAmount, campo distinto. Sin ambigüedad real en ninguno de los
  casos verificados esta sesión.
- **Multi-TenderResult sin verificar contra un expediente multi-lote real
  con más de una adjudicación** (igual que CONTEXTO.md deja sin verificar
  la Propuesta LC.27 multi-lote): _adjudicacion en atom_parser.py suma
  los importes de todos los cac:TenderResult que traiga el expediente y
  concatena los adjudicatarios, a nivel de expediente — nunca por lote. Si
  aparece un caso real con varios TenderResult, revisar esa función antes
  de confiar en el agregado.

### app.mantenimiento.ciclo, integración con el bloque 1

El descubrimiento corre **al principio** del ciclo (ejecutar_ciclo_
mantenimiento), antes del bucle de decisión de frescura, para que un
expediente recién descubierto entre en el mismo ciclo que lo descubrió, sin
esperar al siguiente. Un fallo del descubrimiento (red, periodo sin ZIP
disponible) se registra en resumen.descubrimiento y **no impide el resto
del ciclo** — descargar/extraer lo que ya se conocía sigue su curso
(db.rollback() antes, mismo patrón que app.queue.ejecutar_trabajo).
Payload nuevo, además del forzar/forzar_expedientes del bloque 1:
sindicacion_desactivada (para tests y para una ejecución que no debe tocar
la red) y sindicacion_periodo (backfill manual de un mes concreto,
POST /mantenimiento/ejecutar) — el mes en curso por defecto.
sindicacion_ruta_zip existe en el payload del trabajo (para reprocesar un
ZIP ya descargado sin volver a la red) pero **no se expone en la API
pública**: es un camino de fichero del contenedor, no algo que la web deba
poder pasar.

### Verificación contra el stack real, dos periodos reales

Migración 0012 aplicada, imágenes reconstruidas. **218 tests en verde**
(199 del bloque 1 + 19 de este bloque), dentro del contenedor. Dos
ejecuciones reales, sin ningún doble de test:

1. **Agosto 2024** (mes ya cerrado, mismo ZIP verificado en la sesión de
   exploración — reutilizado desde caché local para no repetir una descarga
   de ~460 s ya probada por separado con curl, y para poder acotar
   exactamente qué periodo se estaba verificando): sindicacion_periodo:
   "202408". Resultado real: **219 expedientes ADIF totales, 5 tras el
   filtro de departamento, 2 nuevos** (3.23/28510.0135, 6.24/28510.0106
   — los otros 3 códigos del filtro ya eran expedientes conocidos del
   corpus). Los 2 nuevos se descargaron de verdad (scraping real, sin
   doble), se extrajeron, y **el contraste de sindicación encontró una
   discrepancia real en los dos**: 3.23/28510.0135 (un expediente
   multi-lote de 8 lotes) extrajo 8.545,90 euros de licitación donde
   sindicación declara 271.629,53 euros — la cascada se quedó con un solo
   lote en vez del total, un fallo real de extracción en un caso nuevo, no
   un ruido del contraste; 6.24/28510.0106 extrajo 10.000.000 euros donde
   sindicación declara 2.360.111,18 euros. Los dos expedientes quedaron
   pendiente_revision con el motivo exacto, en vez de completado con un
   importe erróneo — exactamente el comportamiento que pedía el encargo
   ("si no cuadran, a revisión"), y la primera vez que el contraste
   encuentra algo real, no solo en un test. **Fuera de alcance de esta
   sesión, anotado y no arreglado (encargo: "no toques el motor de
   extracción")**: por qué 3.23/28510.0135 solo trae un lote — candidato
   para una sesión futura sobre extracción multi-lote.
2. **El mes en curso de esta sesión** (sindicacion_periodo sin especificar
   → por defecto), descarga real desde el contenedor: **61 expedientes ADIF
   totales, 4 tras el filtro, 0 nuevos** (los 4 ya eran expedientes
   conocidos). Sirvió, de paso, para verificar en vivo un caso real de
   recuperación de trabajo huérfano (`docs/hallazgos-scraping.md`, sección 17,
   "pendiente"):
   este trabajo se interrumpió a mitad de ejecución al reconstruir el
   contenedor del worker con el arreglo del punto anterior, quedó
   en_proceso sin dueño, y reclamar_trabajos_huerfanos lo recuperó solo
   pasado el umbral — el reintento no duplicó nada (los expedientes que el
   primer intento ya había llegado a crear antes de la interrupción
   aparecieron como "sin cambios", no como "nuevos" otra vez): confirma en
   vivo, no solo en test, la idempotencia de descubrir_novedades.

**Efecto acumulado en la base de datos real de desarrollo** (que ya llevaba
53 expedientes de sesiones anteriores, más que el corpus fijo de 45/31 —
sin limpiar, no es el objeto de esta sesión): 59 expedientes tras las dos
ejecuciones (+6), 16 completado, 28 pendiente_revision, 15
sin_publicar.

### Fixtures de regresión

engine/tests/sindicacion/fixtures.py: fabrica ZIPs sintéticos con la misma
forma y los mismos espacios de nombres que el ZIP real (verificado contra
él en esta sesión), para no depender de la red en ningún test.
test_atom_parser.py (5 casos: campos básicos, adjudicación con varios
TenderResult, departamento sin patrón, filtro aplicado antes de emitir,
varios .atom en un mismo ZIP), test_descubrimiento.py (6 casos: alta
nueva, departamento fuera de lista, órgano no ADIF, cambio de estado
reencola descarga, mismo estado no reencola nada, dato viejo nunca pisa uno
más nuevo), test_contraste.py (6 casos), y
tests/mantenimiento/test_ciclo_descubrimiento.py (2 casos: un expediente
descubierto se procesa en el mismo ciclo que lo descubre, un fallo del
descubrimiento no impide el resto). tests/mantenimiento/test_ciclo.py se
actualiza para desactivar la sindicación por defecto (sindicacion_
desactivada: true) — esos tests son del bloque 1, no deben tocar la red.

## 25. Expedientes publicados que faltaban: backfill de meses pasados (sesión 2026-09-07)

Origen: el cliente reportó un caso concreto, `6.26/28510.0014`, publicado
en la Plataforma pero ausente del sistema.

### Diagnóstico del caso concreto

| Pregunta | Respuesta |
|---|---|
| ¿Está en base de datos? | No, antes de esta sesión. |
| ¿Existe en la Plataforma? | **Sí** — `POST /expedientes/{id}/descargar` real lo encuentra al momento: "Pedido nº3 acuerdo marco de suministro de carril nuevo para las necesidades de la red ferroviaria de interés general", 3.005.618,56 € de licitación, 2 documentos descargados (`anuncio_pcsp` x2) sin ningún error. |
| ¿Aparece en el Excel de códigos? | No, en ninguna de las 666 filas de su única hoja ("Hoja1"). |
| ¿Aparece en la sindicación? | No, en ninguno de los dos únicos periodos jamás ingeridos en la base de datos real (`202408`, `202609`). |

La búsqueda (el scraper) funciona perfectamente en cuanto se dispara a
mano. El fallo está enteramente en el **descubrimiento**: nada disparó
nunca la búsqueda de este expediente en concreto.

### Alcance: por qué el descubrimiento no lo encontró solo

`descubrir_novedades` (sección 24 de arriba) siempre aceptó un `periodo`
explícito (`AAAAMM`) — el mecanismo en sí nunca tuvo la limitación.
Medido contra `sindicacion_expedientes` real: solo **dos periodos** se
habían ingerido jamás —

| Periodo | Expedientes ADIF (dept. 28510) |
|---|---|
| `202408` | 3 (prueba puntual de la sesión original, sección 24) |
| `202609` | 4 (el mes en curso de esta sesión) |

`app.mantenimiento.ciclo` (la única llamadora automática, vía el ciclo de
mantenimiento semanal) usa `periodo_actual()` por defecto en cada
ejecución — **ningún mecanismo revisitaba nunca un mes ya pasado**. Entre
`202409` y `202608`, unos 25 meses, no se comprobó ni uno. Un expediente
cuyo único cambio de estado cayó en un mes saltado queda invisible para
siempre, aunque siga publicado con normalidad — exactamente el caso de
`6.26/28510.0014`.

**Filtro de departamento, descartado como causa**: `SINDICACION_DEPARTAMENTOS_ADIF`
sigue en su valor por defecto (`28510`), sin sobrescribir en `.env` ni en
`docker-compose.yml`; el expediente reportado es justo de ese
departamento. La sección 24 ya había medido con datos reales, contra el
ZIP completo de agosto 2024, que 28510 es el departamento correcto para
material de suministro — otros departamentos traen obra civil de Alta
Velocidad que la cascada de extracción no está pensada para leer.

**Segunda causa relacionada, encontrada al revisar "todas las hojas" del
Excel de códigos**: `app.extraccion.cruce_codigos._cargar_indice` leía
siempre `libro.worksheets[0]` — la primera hoja, sin más. Mismo defecto
que el scraper heredado ("solo leía la hoja de expedientes en ejecución").
El fichero de ejemplo de este repositorio (`Ejemplo/Input/Códigos de
proyecto.xlsx`, 666 filas) solo trae una hoja ("Hoja1"), así que no se
pudo reproducir el hallazgo contra datos reales ni medir cuántas filas
adicionales aportaría una segunda hoja — pero el fichero real que
mantiene ADIF puede traer más de una (p.ej. una hoja separada para
procedimientos "en tramitación"), y el código no debe asumir que siempre
habrá solo una. Se corrige igual, de forma defensiva: lee todas las hojas
del workbook, cada una con su propia cabecera.

### El arreglo

- `app.sindicacion.descubrimiento.descubrir_backfill(db, periodos)` +
  `periodos_recientes(n, hasta=None)`: recorre varios periodos pasados
  llamando a `descubrir_novedades` una vez por cada uno (mismo mecanismo
  de siempre, nunca modificado) — el fallo de un mes concreto (ZIP no
  publicado todavía, corte de red) se anota aparte y la tanda sigue con el
  resto, nunca aborta. `periodos_recientes` devuelve del más reciente al
  más antiguo, para que una tanda grande interrumpida a medias deje sin
  repasar los meses más antiguos, nunca los recientes.
- Trabajo de cola nuevo, `sindicacion_backfill`
  (`POST /mantenimiento/sindicacion/backfill`, payload `{"periodos": [...]}`
  o `{"meses": N}`, 12 por defecto) — deliberadamente **distinto** del
  ciclo completo (`mantenimiento_ciclo`, que ya podía reprocesar un mes
  con `sindicacion_periodo` pero solo uno, y de paso descarga/extrae todo
  lo que falte): un backfill de varios meses no necesita ese coste
  añadido, solo el barrido de descubrimiento.
- `app.extraccion.cruce_codigos._cargar_indice`: lee todas las hojas del
  Excel de códigos, no solo la primera; una hoja vacía (sin cabecera
  siquiera) no revienta la lectura.
- 12 tests nuevos (`test_descubrimiento.py`: `periodos_recientes` con
  cambio de año, `descubrir_backfill` agregando periodos y aislando un
  fallo; `test_cruce_codigos.py`: cruce contra la segunda hoja, hoja
  vacía; `test_worker.py`: el trabajo nuevo con periodos explícitos y con
  `meses` por defecto). 393 tests pasan en total.

### Verificación contra la Plataforma y la sindicación reales

- `6.26/28510.0014` descubierto y descargado a mano
  (`POST /expedientes/{id}/descargar`, expediente ya existente en base de
  datos por alta manual mientras se diagnosticaba el caso): ahora en
  `pendiente_revision`, con nombre de proyecto e importe reales, 2
  documentos descargados. Pendiente el siguiente paso normal del sistema
  (extracción), no distinto de cualquier otro expediente recién
  descubierto.
- Backfill real lanzado (`meses: 3`, trabajo 1083): periodo `202609` (mes
  en curso, parcial, 23 MB) procesado en menos de 2 minutos —
  `{"expedientes_adif_total": 61, "expedientes_filtrados": 4,
  "expedientes_nuevos": 0, "expedientes_sin_cambios": 4}`, coincide
  exactamente con lo ya conocido (verificación de que el mecanismo
  funciona, no solo que compila). El siguiente periodo (`202608`, mes
  completo) es sensiblemente más grande y, en la red de esta sesión,
  bastante más lento que los ~460 s medidos en la sesión original para un
  mes completo — seguía descargando al cierre de esta sesión. Al ser un
  trabajo de cola normal (mismo mecanismo que cualquier descarga o
  extracción), sigue corriendo de forma asíncrona en el sistema aunque la
  sesión termine; estado y resultado consultables en
  `GET /mantenimiento/sindicacion/historial` o directamente en
  `trabajos_cola` (id 1083). Ningún error hasta el momento — el ZIP
  simplemente tarda.
