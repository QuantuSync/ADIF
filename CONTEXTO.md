# ADIF — Catálogo de materiales y cálculo de baja

Contexto permanente del proyecto. Léelo entero antes de escribir código.
Si algo de este documento contradice lo que parece obvio, gana este documento.

El registro histórico de hallazgos y decisiones de cada sesión vive en
`docs/` (ver el cierre de este documento) — este fichero se queda solo con
lo que hace falta saber siempre.

---

## 1. Qué se construye

Un sistema que, partiendo de los documentos publicados en la Plataforma de
Contratación del Sector Público, produce:

1. **Un catálogo único de materiales.** Una fila por artículo, lote y expediente,
   con su precio unitario licitado y su precio adjudicado. Es el entregable
   principal.
2. **La baja de cada expediente.** Global y por lote.

El catálogo es acumulativo: **hay un solo catálogo para todos los expedientes**,
no uno por expediente.

### Qué se conserva del trabajo previo

El scraping de la Plataforma funciona y resuelve un problema real. Se rescata la
lógica (navegación, búsqueda por MATRIZ con caída a Nº Expediente, deduplicación
por hash, selección del documento idóneo de cada tipo). Se descarta su envoltorio:
`.cmd` de Windows, Microsoft Edge, modo no headless, `ADIF Coloab.py`.

---

## 2. Vocabulario del dominio

No lo inventes ni lo traduzcas. Usa estos términos en código y en datos.

| Término | Significado |
|---|---|
| **Expediente** | Procedimiento de contratación. Formato `6.24/28510.0088`. |
| **Matriz** | Expediente del acuerdo marco del que cuelga un pedido. Un mismo código puede ser expediente en una fila y matriz en otra. |
| **Lote** | Subdivisión de un expediente. Cada lote da lugar a un contrato independiente y **tiene su propia baja**. |
| **Matrícula** | Código de 9 dígitos del artículo en ADIF (en pliegos antiguos, de 8: "59020019", aceptado desde la sesión 2026-09-17). Presente solo en ~66% de las líneas. **No es clave.** |
| **Código de precio** | `P-001`, `P-067`. Identificador de la línea dentro del documento. **Esta sí es clave.** |
| **Baja** | Porcentaje de rebaja ofertado. Ver sección 4. |
| **Partida alzada** | Línea sin matrícula ni código de material, cantidad 1, importe a tanto alzado. Es legítima, no un error. |

**Dos trampas de vocabulario, verificadas contra el corpus real (sesión de
identidad de lote, ver `docs/identidad-expediente.md` sección 27) — el
corpus reutiliza estas dos palabras con un segundo significado, y el código
no debe mezclarlos:**

- **"Lote"** tiene dos sentidos distintos según el documento. En una
  licitación multi-lote (título "N LOTES"), es la subdivisión en contratos
  concurrentes, cada uno con su propio expediente correlativo y su propia
  baja. En un pedido derivado de acuerdo marco, "Lote N" es una **categoría
  de producto dentro del catálogo del acuerdo marco** (p. ej. "Lote 4.-
  guantes de protección"), sin ninguna subdivisión en contratos. Dos
  conceptos, misma palabra.
- **"Matriz"** normalmente significa el expediente de acuerdo marco (tabla
  de arriba). Pero al menos una Propuesta LC.27 real (`6.24/28510.0094`)
  etiqueta su propio expediente agrupador de lotes como "Nº EXPEDIENTE
  MATRIZ", sin relación alguna con acuerdo marco. Ese valor se captura solo
  para contraste/trazabilidad (`codigo_principal_declarado`) — **nunca se
  escribe en `expediente.codigo_matriz`**, porque haría creer que el
  expediente es un pedido derivado de acuerdo marco cuando no lo es.

---

## 3. Hallazgos del análisis del corpus (medidos, no supuestos)

Sobre 45 expedientes y 187 PDFs reales. Detalle completo, cifras y
metodología en `docs/analisis-corpus.md`; aquí solo lo que cambia cómo se
escribe código:

- **Actualizado 2026-09-17 (corpus de 1.623 documentos): 140 escaneados,
  5.298 páginas, 113 expedientes, casi todos de 2016-2019**; 60 son pliegos
  técnicos con ~1.800 filas de catálogo que hoy no se leen (67 expedientes
  sin ninguna línea), ver `docs/sesion-2026-09-17-escaneados-codigo-material.md`
  bloque 1 y sección 15. Texto original de la sesión de análisis:
- **186 de los 187 documentos tienen capa de texto.** No hace falta OCR ni
  modelo multimodal para leerlos (ver sección 15, "Fuera de alcance"). La
  única excepción conocida, `6.20/28510.0136_ANEJO_2.pdf`, es un PDF
  escaneado — `app.extraccion.texto.es_documento_escaneado` lo detecta
  (umbral de caracteres, no cero exacto) y lo marca con un motivo de
  revisión distinto de "no se extrajo ninguna línea de catálogo".
- **Dos familias de documento de adjudicación:** *Anuncio PCSP* (formulario
  estándar con etiquetas fijas) y *Propuesta LC.27* (plantilla propia de
  ADIF). Existe una tercera plantilla minoritaria, `L9_CM.32-FE` (Dirección
  Técnica), que hoy cae en `otro` — ver sección 16.
- **El cruce con el Excel de códigos es determinista al 100%** cuando el
  documento trae un código de expediente extraíble.
- **Localizar la tabla de precios descarta la mayoría de las páginas**
  antes de gastar nada en extracción real.
- **`pdfplumber` extrae los cuadros de precios limpiamente**, con
  descripciones multilínea unidas en su celda. El texto plano de esas
  páginas, en cambio, sale entrelazado e inservible — la tabla se localiza
  y se lee como tabla, nunca como texto corrido.
- **Las cabeceras varían mucho** — entre 6 y 9 columnas, nombres
  alternativos, columnas fantasma vacías que desplazan los índices, y
  cabeceras corrompidas por la extracción. Un parser por posición fija no
  funciona; de ahí la etapa 5 de la cascada (sección 6).
- **Las cabeceras se repiten mucho entre documentos.** Esto habilita la
  caché de firma de cabecera de la sección 6.
- **Los ficheros nombrados `CONTRATO.pdf` de tamaño pequeño suelen ser el
  formulario PCSP "Anuncio de formalización de contrato", no el contrato
  firmado.** El nombre que asigna el scraper no es fiable como tipo: manda
  el clasificador (sección 5, etapa 1), nunca el nombre del fichero.
- **Los ficheros `*_ANEJO_1.pdf` son en realidad el Pliego de Prescripciones
  Técnicas completo; el cuadro de precios es una sección interna.**
  Consecuencia: la tabla se localiza por contenido, nunca por el tipo de
  documento ni por el nombre del fichero.
- **Un pedido derivado de acuerdo marco puede no tener cuadro de precios ni
  baja propios** — viven en los documentos de la MATRIZ. Ver
  `docs/identidad-expediente.md` para el mecanismo de herencia.
- **Una licitación puede repartirse en varios lotes, cada uno con su propio
  código de expediente correlativo y su propia baja**, declarados dentro
  del mismo documento de adjudicación. Ver `docs/identidad-expediente.md`
  sección 27 para la extracción generalizada de esta estructura, y la
  trampa de vocabulario "Lote"/"Matriz" en la sección 2 de arriba.

---

## 4. La baja: cómo funciona de verdad

**Hallazgo central del proyecto.** En la mayoría de los contratos revisados
del corpus, el pliego establece que el licitador oferta **una sola baja
porcentual por lote, aplicable a todos los precios unitarios**.

Consecuencias:

- **No existe una tabla de precios adjudicados.** No la busques.
- **El precio adjudicado de cada línea es una derivación:**
  `precio_adjudicado = precio_licitado × (1 − baja_lote)`
- **No hay una baja distinta por material dentro de un lote.** Todos los materiales
  de un lote bajan lo mismo.
- **La fórmula ingenua `1 − adjudicado/licitación` da 0% en estos expedientes**, porque
  el presupuesto es un techo de gasto y no cambia. Ejemplo real: expediente
  6.24/28510.0088, licitación 1.000.000 €, adjudicación 1.000.000 €, baja real 0,50%.
  Detectar este caso y no devolver 0% es un requisito, no una mejora.
- **El mínimo exigible para dar una baja de lote por buena es laxo, por
  decisión del cliente** (ver `docs/decisiones-cliente.md` sección 26):
  basta con que exista una baja declarada en texto para el lote — no hace
  falta que cuadre con la baja que resultaría de los importes de
  licitación/adjudicación. Solo se exige revisión cuando no hay ninguna
  baja de la que partir.

### Dónde está cada dato

| Dato | Origen |
|---|---|
| Baja de lote | Declarada en texto en la propuesta LC.27 y en el contrato. Se extrae, no se calcula. |
| Importe de licitación | Anuncio PCSP: *Presupuesto base de licitación → Importe (sin impuestos)*. LC.27: tabla de presupuesto. Si falta, el Contrato del lote: *"Ascendiendo el importe de licitación del lote N a X € (IVA excluido)"* (sesión 2026-09-15). |
| Importe adjudicado | Anuncio PCSP: *Importes de Adjudicación → Importe total ofertado (sin impuestos)*. Si falta, el Contrato del lote: *"El importe del contrato es de: Base imponible X €"* (sesión 2026-09-15; coincide con la adjudicación en los 24 casos en que hay las dos). |
| Precio unitario licitado | Cuadro de precios unitarios del anejo. |
| Precio unitario adjudicado | Derivado. |

**Guarda la baja en cada línea del catálogo**, aunque sea la misma para todo el lote.
Permite consultar sin recomponer, deja el sistema preparado para los expedientes que
no siguen este modelo, y hace la baja auditable en vez de implícita.

**Redacciones de la baja en texto, verificadas contra el corpus real** (no
inventes una más sin comprobarla primero): "baja del N% ... precios
unitarios" (la forma estricta), variantes con etiqueta laxa ("% de baja",
"% baja adjudicado", "% total de baja", "baja ofertada", "porcentaje de
baja" — solo se intentan si la forma estricta no encontró nada, y exigen el
símbolo `%` pegado a la etiqueta para no disparar con boilerplate laboral
de "baja médica"), y una forma invertida ("N % de baja..." en vez de "baja
del N%..."). Detalle y regexes exactos en `docs/hallazgos-extraccion.md`
sección 22.2 y `docs/identidad-expediente.md` sección 27.

---

## 5. La cascada de extracción

Cada documento cae por la primera etapa que lo resuelva. **No saltes etapas.**

1. **Clasificar la plantilla.** Anuncio PCSP, propuesta LC.27, contrato, anejo, pliego.
   Por marcadores de texto. Decide toda la ruta posterior.
2. **Campos de etiqueta fija.** Todo lo que sea formulario PCSP se extrae por etiqueta.
   Aquí sale la baja global de la familia PCSP entera, sin tablas y sin modelo.
3. **Localizar páginas candidatas.** Por presencia de cabecera de matrícula y densidad
   numérica. Reduce el trabajo antes de gastar nada. Una página que continúa una
   tabla ya abierta entra por traer identificadores de fila (código de precio o
   matrícula), no por densidad: con descripciones largas, una continuación tiene
   la densidad de un párrafo (sesión 2026-09-14). Y una página con tres o más
   líneas que traen a la vez identificador de fila e importe entra aunque la
   prosa que rodea al cuadro baje su densidad (sesión 2026-09-15), igual que
   una con una línea que nombra a la vez descripción, cantidad y precio (la
   cabecera de un cuadro de un solo artículo, misma sesión).
4. **Extraer la tabla** con `pdfplumber` sobre esas páginas. Si una tabla sale
   sin ninguna fila de datos, segundo intento sin imantar las líneas
   verticales (`snap_x_tolerance` 1): el borde de una tabla vecina puede
   arrastrar el suyo y dejarla sin su primera columna (sesión 2026-09-15). Una
   tabla sin líneas horizontales entre filas sale como una sola fila con un
   valor por línea en cada celda: esos valores nunca se pegan en un número.
   Una tabla sin ninguna fila con código de precio ni matrícula de 9 dígitos
   es espuria, salvo que su primera fila nombre en columnas distintas la
   descripción, la cantidad y el precio: entonces es un cuadro sin código y se
   leen las filas con descripción e importe hasta el pie de totales (sesión
   2026-09-15, `docs/sesion-2026-09-15-criterio-28510-y-cuadros-sin-codigo.md`).
5. **Mapear cabecera → esquema.** Única etapa donde interviene el modelo. Ver sección 6.
6. **Normalizar y derivar.** Ver secciones 7 y 8.

**Excepción: los pliegos sin cuadro de precios se saltan las etapas 3-4
enteras.** Por criterio del cliente, verificado contra el corpus real
(`docs/decisiones-cliente.md` sección 26): la portada administrativa PCSP y
el Pliego de Cláusulas Administrativas nunca traen cuadro de precios, así
que `app.extraccion.clasificador.es_pliego_sin_precios` los detecta y el
orquestador no vuelve a abrir ni a extraer texto de esos documentos. **El
pliego técnico (`*_ANEJO_1.pdf`) NO entra en esta excepción** — es la
fuente principal de datos de la mayoría de expedientes completados, pese a
llamarse "pliego".

---

## 6. Cuándo se permite llamar al modelo

**Regla dura: el modelo se llama para traducir una cabecera de tabla nunca vista.
Para nada más.**

- **Una llamada por firma de cabecera, no por documento, no por página, no por fila.**
  Calcula una firma de la cabecera, búscala en caché persistente. Si está, ya sabes
  qué columna es cada cosa. Si no, una llamada, guardas el mapeo, y no vuelves a
  preguntarlo nunca.
- **No le pases las filas de datos.** Solo la cabecera y dos o tres filas de ejemplo
  para desambiguar.
- **Aplicar el mapeo a las filas restantes es código, no modelo.**
- **Filas huérfanas** (descripción partida, matrícula ausente, cabecera corrompida):
  se agrupan y van en **una** llamada por documento, nunca una por fila.
- **El `Código del material` no usa modelo.** Es el sustantivo principal de la
  descripción (`BRIDA`, `PLACA`, `JUNTA`, `SUPLEMENTO`) más un vocabulario controlado
  que crece con el uso. El modelo solo se invoca si no casa nada, y su respuesta
  amplía el vocabulario. **Excepción, decisión del cliente (sesión
  2026-09-14):** si la tabla trae su propia columna de tipo de pieza
  ("REPUESTO": "Semicambio", "Aguja", "Cruzamiento obtuso"...), su valor
  literal manda sobre la derivación. Existe en la familia
  `6.21/28510.0108` (`docs/sesion-2026-09-14-revision-cliente-pliegos.md`) y,
  como "TIPO DE TRAVIESA", en `6.24/28510.0094`/`0175`-`0177` (sesión
  2026-09-17). **Las siglas de aparatos de vía nombran la pieza** (`AC`/`AR`
  aguja, `CAC`/`CAR` contraaguja, `CC` contracarril, `CZ*` cruzamiento, `SC*`
  semicambio, `DS*` y `D??D/I` desvío, `ES*` escape, `TUD`/`TSU` travesía...),
  verificado en el corpus (`app.extraccion.codigo_material._SIGLAS_APARATO_VIA`).
  La respuesta cacheada del modelo es por primera palabra: solo vale para una
  descripción que nombra esa pieza.
- **El cruce con el Excel de códigos no usa modelo.** Es búsqueda por clave exacta.
- **Caché por hash de documento.** Nunca se reprocesa lo mismo dos veces.

Efecto buscado: **el sistema llama menos al modelo cuantos más expedientes procesa.**

Si te ves escribiendo un prompt que pide "extrae los datos de este documento",
párate: has salido de la cascada.

**Modelo por defecto: un modelo pequeño del proveedor configurado
(`MODEL_ID`)**, no un modelo grande — traducir una cabecera nunca vista es
correspondencia de etiquetas, no una tarea que se beneficie de
razonamiento. Verificado contra la API real: mismo comportamiento correcto
que un modelo mayor, a una fracción del coste. Detalle y cifras en
`docs/hallazgos-extraccion.md` secciones 17.2-17.3.

---

## 7. Esquema del catálogo

Columnas del entregable y su origen. Las once primeras son el formato
original del cliente, en su orden exacto — nunca se reordenan. Tres más
añadidas después, siempre al final, sin desplazar las once: **precio
adjudicado** y **baja del lote** (sesión de corrección del Excel al
cliente); **unidad de medida** (aviso del cliente, sesión 2026-09-07: sin
ella, una Cantidad de 2000 o un Precio unitario de 0,142 no significan nada
por sí solos — pueden ser metros de cable o toneladas de balasto, o un
precio por tonelada-kilómetro).

| Columna | Origen | Modelo |
|---|---|---|
| Código interno | `Nº Interno` del Excel de códigos | No, cruce |
| Código de expediente | `Nº Expediente` del Excel | No, cruce |
| Código matriz | `MATRIZ` del Excel | No, cruce |
| Título expediente | *Objeto del Contrato* del anuncio | No, etiqueta fija |
| Matrícula del material | Cuadro de precios | No |
| Descripción del material | Cuadro de precios | No |
| Código del material | Columna "REPUESTO" del cuadro si existe; si no, derivado de la descripción | Solo si no casa |
| Cantidad | Cuadro de precios | No |
| Precio unitario | Cuadro de precios | No |
| Lote | Cabecera de tabla o anuncio | No |
| Comentarios | Humano | No |
| Precio adjudicado | Derivado (precio unitario × (1 − baja de lote)) | No |
| Baja del lote | Declarada en texto en la propuesta/contrato | No |
| Unidad de medida | Cuadro de precios | No |
| Motivo de las celdas vacías | Derivado (`app.celdas_vacias`): por qué falta cada dato de la fila — no aplica / no consta / pendiente | No |

**Celdas vacías en el Excel (sesión 2026-09-14):** la celda se deja vacía
— un marcador de texto rompería las columnas numéricas — y su motivo va en
la columna "Motivo de las celdas vacías" (justo antes de "Comentarios", que
sigue la última), con el mismo criterio de tres motivos que la web. En
particular, una cantidad o un precio que el documento da distinto para cada
lote bajo el mismo código de precio es "pendiente", nunca "no consta".

**Anejo de criterios técnicos (sesión 2026-09-14, tercera parte):** en una
licitación por lotes, la lista "materiales a suministrar en el expediente
“… N LOTES”" es del conjunto de los lotes, con su propia numeración -- sus
líneas no son de ningún lote, no salen en "Materiales" y el Resumen las
cuenta en su propia fila, fuera de "pendientes de revisión".

`unidad_medida` se guarda desde el principio del proyecto (etapa 6 de la
cascada, junto a cantidad y precio) — lo nuevo en la sesión 2026-09-07 es
que deja de ser solo interno y pasa a mostrarse en las cuatro pantallas y
en el Excel, con el mismo criterio de celda vacía (no aplica/no consta) que
el resto de columnas. 94,6% de las líneas del catálogo la traen; el 5,4%
restante es, verificado contra el corpus real, un cuadro de precios que de
verdad no declara ninguna columna de unidad (no un hueco de extracción) —
ver `docs/excel-cliente-correccion.md` bloque 5. **Solo se guarda como unidad
un valor del vocabulario de unidades conocidas**
(`app.extraccion.unidad_medida`, sesión 2026-09-15): cualquier otro se
descarta y la línea va a revisión.

Añadir internamente, aunque no salgan al Excel como columna propia:
`codigo_precio`, `documento_origen`, `pagina`, `fragmento`, `confianza`,
`estado_revision`.

### Cruce con el Excel de códigos

El anuncio PCSP trae **los dos códigos escritos en campos fijos**:
- *Número de Expediente* → `Nº Expediente`
- *Licitación basada en el acuerdo marco → Expediente* → `MATRIZ`

**El cruce es por clave exacta, no por similitud de nombre.** El match por
descripción existe solo como red de seguridad para expedientes sin código legible,
y en ese caso va con umbral y cola de revisión.

**El sistema nunca inventa una matriz.** Si no cruza, se deja vacío y se marca.

### Clave del catálogo

`expediente + lote + codigo_precio`

**No uses la matrícula como clave** (falta en un tercio de las filas). **No uses
`Nº Interno`** (se repite entre filas: agrupa varios pedidos de un mismo
procedimiento).

### Lista de exclusión de expedientes

Bloque 5, cambios del cliente tras revisar el catálogo: expedientes que no
son del equipo del cliente se excluyen del Excel entregado y de `/catalogo`
en la web, pero **se conservan en base de datos** y siguen visibles en las
pantallas de gestión/revisión — la exclusión es solo de la vista, nunca un
borrado. Configurable sin tocar código (`EXCLUSION_EXPEDIENTES_PATH`,
`app/exclusion.py`): un fichero de texto plano, una entrada por línea,
código exacto (`6.24/28510.0088`) o departamento completo (`28520`, el
mismo segmento de `codigo_expediente` que ya usa la sindicación), `#` para
comentarios. Aplicado dentro de `app.catalogo_consulta.consultar_catalogo`
(la única implementación que usan tanto `/catalogo` como el Excel), nunca
como parámetro que el llamador pueda desactivar.

---

## 8. Normalización — errores que van a aparecer

- **Formato numérico español.** `1.234.567,89`. Parsearlo con `float()` da 1.234 o
  revienta. Normalizador propio, probado, aplicado antes de cualquier comparación.
- **`Decimal`, nunca `float`.** Con euros y porcentajes los errores de coma flotante
  salen en la tercera cifra y se ven en la demo.
- **El modelo devuelve el literal, tu código normaliza.** Nunca al revés.
- **Códigos con espacios sobrantes.** En el Excel hay valores como `6.25/28510.0146 `.
  Un cruce exacto fallaría en silencio. Recorta y unifica separadores antes de comparar.
- **El símbolo `€` viene dentro de la celda**, a veces con salto de línea.
- **Los nombres de carpeta pueden ser la matriz, no el expediente.** Guarda los dos
  códigos por separado desde el principio.
- **Celdas `None` por columnas fantasma.** El mapeo de cabecera las neutraliza.
- **Un guion suelto (`-`) en una celda es la convención administrativa de
  "no aplica a esta fila"**, no un valor ilegible — se trata como campo
  vacío (matrícula, cantidad, precio unitario), sin generar motivo de
  revisión.

---

## 9. Invariantes de arquitectura

Estas reglas no se rompen ni siquiera "solo para la demo".

1. **La web nunca toca un PDF, ni la base de datos, ni ejecuta cómputo.** Solo llama
   a la API por HTTP. Si haces un atajo aquí, rompes el argumento de soberanía sin
   que se note hasta el día de la migración.
2. **El acceso al modelo pasa siempre por una interfaz con implementaciones
   intercambiables.** Hoy la API comercial de un proveedor, mañana un modelo
   autoalojado. Misma firma, mismo esquema de salida. Cambiar de una a otra
   es una variable de entorno.
3. **El almacenamiento de documentos pasa por una interfaz mínima**
   (guardar, recuperar, listar). Hoy disco local, mañana almacenamiento de objetos.
4. **Todo en contenedores desde el primer día.** Lo que corre en local es lo que
   correrá en el servidor.
5. **Nada específico de un proveedor cloud.** Ni servicios gestionados propietarios,
   ni SDK de un fabricante concreto, ni colas de proveedor. PostgreSQL estándar y
   contenedores. El destino final es OVHcloud; puede haber un tránsito por Azure;
   **ninguno de los dos debe aparecer en el código.**
6. **La cola de trabajos va en PostgreSQL**, con bloqueo por fila. Sin Redis, sin
   Celery, sin broker. Menos servicios, menos modos de fallo, y la cola queda
   consultable con SQL para la pantalla de seguimiento.
7. **Autenticación: ninguna, pero con costura.** Todas las rutas pasan por una función
   que hoy devuelve un usuario ficticio. Añadirla luego se toca en un sitio.
8. **El Excel es una vista generada, no la fuente.** Los datos viven en la base de
   datos con su traza. El Excel se regenera a demanda.
9. **Idempotencia.** Reprocesar un expediente actualiza sus filas, nunca las duplica.
   Escritura por clave, no añadido ciego. El catálogo es acumulativo y una segunda
   ejecución que duplique filas destruye la confianza del cliente.
10. **Trazabilidad obligatoria.** Cada cifra queda anclada a documento, página y
    fragmento. Es lo que la versión hecha con Copilot no puede ofrecer, y es donde
    se decide la comparación.
11. **Una sola fuente de verdad: el repositorio versionado.** Los contenedores
    reales se construyen siempre desde este repositorio (`git`), nunca desde una
    copia suelta del código fuera de control de versiones — ni en WSL, ni en
    ningún otro sitio. **Prohibido mantener una segunda copia del árbol de
    trabajo para acelerar builds o por cualquier otro motivo**: si hace falta una
    ruta nativa de Linux por rendimiento de compilación (WSL2 penaliza
    fuertemente compilar contra una ruta `/mnt/c/...`), la única forma permitida
    es un `git worktree` del mismo repositorio — nunca una copia de ficheros
    (`cp`/`rsync`) que pueda divergir sin que `git status` lo note. Antes de
    reconstruir un contenedor y fiarte de su resultado, comprueba con `docker
    inspect --format '{{json .Config.Labels}}'` desde qué ruta se construyó
    (`com.docker.compose.project.working_dir`) — si no es este repositorio (o un
    `git worktree` suyo), párate: el código desplegado puede no ser el
    versionado. **Ya ha pasado dos veces** (`docs/decisiones.md` sección 28,
    `docs/hallazgos-extraccion.md` sección "Clon viejo en WSL, borrado", y de
    nuevo en la sesión de limpieza de duplicados de 2026-09-06): un clon o copia
    suelta en `/home/lucas/adif` sirviendo los contenedores reales sin que
    ninguna sesión lo dejara escrito. No es un hallazgo que redescubrir cada vez,
    es una regla que no se vuelve a romper.

---

## 10. Procesos

Cuatro, ni uno más:

- **API** — FastAPI. Única frontera con datos y ficheros.
- **Worker** — consume la cola: descargar, extraer, recalcular. También lanza
  el ciclo de mantenimiento programado (ver `docs/mantenimiento-automatico.md`)
  desde su propio bucle — no hay un quinto proceso "scheduler".
- **PostgreSQL** — estado, catálogo, trazas, cola.
- **Web** — Next.js. Cliente ligero.

El scraping **es un tipo de trabajo de la cola**, con su estado, reintentos y
registro. No un script suelto. Corre en contenedor Linux con **Chromium headless**,
no Edge.

---

## 11. Qué hace la web

1. Gestionar la lista de expedientes a procesar.
2. Lanzar la descarga desde la Plataforma.
3. Seguimiento por expediente: descargando, extrayendo, pendiente de revisión,
   completado, fallido, y por qué.
4. **Cola de revisión**: casos que no cuadran, con el documento al lado, para
   confirmar o corregir.
5. Explorar el catálogo con filtros y **búsqueda por matrícula a través de todos los
   expedientes** (es la pregunta que ADIF realmente tiene: cómo evoluciona el precio
   de un material).
6. Exportar el Excel único.
7. Ver el estado del mantenimiento automático (`/mantenimiento`): última
   ejecución, próxima, histórico, y lanzar un ciclo a mano.

---

## 12. Validación

- Comprobar que importe licitado, importe adjudicado y baja declarada cuadran entre sí
  cuando no hay una baja declarada explícita de la que partir (ver sección 4:
  el mínimo exigible es laxo cuando sí la hay).
- Lo que no cuadre **no se corrige solo: va a la cola de revisión**.
- Detectar el caso de precios unitarios (licitación = adjudicación) y no devolver 0%.
- Un sistema que sabe cuándo no sabe vale más en la demo que uno que acierta cinco de
  cinco. No escondas los casos dudosos.
- **Un contraste externo (p. ej. sindicación) puede señalar un desajuste,
  pero no tiene autoridad para cambiar el estado de un expediente ni pisar
  su motivo de revisión** — se guarda como aviso informativo aparte. El
  documento firmado manda; ver `docs/identidad-expediente.md` (sección
  "autoridad del PDF sobre la sindicación") para el caso real que forzó
  esta regla.

---

## 13. Estructura del repositorio

```
/web        Next.js. Cliente ligero. Desplegable por separado.
/engine     API, worker, extracción, scraping. Con su Dockerfile.
/docs       Este fichero, y el registro histórico de hallazgos y decisiones.
docker-compose.yml
```

La dirección de la API en la web es **una variable de entorno**, para apuntar a
local, a una instancia de pruebas o al servidor soberano sin tocar código.

**No metas los 187 PDFs en el repo.** Deja un conjunto fijo de prueba: dos anuncios
PCSP, dos propuestas LC.27, dos anejos con cabeceras distintas. Trabaja siempre
contra esos.

**Aviso de entorno (WSL):** el stack real (contenedores `adif-api-1`,
`adif-web-1`...) se construye desde `/mnt/c/dev/ADIF` — comprobar siempre
desde qué ruta se construyó un contenedor (`docker inspect --format
'{{json .Config.Labels}}'`) antes de asumir que un cambio de código no se
reflejó tras un rebuild. Detalle en `docs/decisiones.md` sección 28.

---

## 14. Orden de trabajo (por riesgo, no por comodidad)

1. **Esqueleto.** Docker levantado, API que responde, base de datos, web que muestra algo.
2. **Scraping headless en contenedor.** *El mayor riesgo del proyecto.* La Plataforma
   puede comportarse distinto sin ventana. Hay que saberlo pronto, no al final.
3. **Cola y seguimiento.** Lanzar desde la web, ver el estado cambiar.
4. **Extracción.** La cascada completa.
5. **Catálogo, revisión y exportación.**

Si aprieta el tiempo, se recorta en profundidad el punto 5. Nunca el 2.

Cierra cada sesión con algo que funcione y comprobado sobre un documento real.

---

## 15. Fuera de alcance

Autenticación real, gestión de usuarios, SharePoint, despliegue en producción,
ejecución programada manual fuera del ciclo de mantenimiento automático,
paralelismo masivo, y todo lo estético que no sea legible en
una pantalla compartida.

**OCR o modelo multimodal para documentos escaneados.** Con el corpus real
actual, 186 de 187 documentos tienen capa de texto (sección 3);
construir un pipeline de OCR para el único caso conocido no está
justificado. Si en el futuro aparecen más documentos escaneados con volumen
propio, la vía prevista es rasterizar la página y pasarla a un modelo
multimodal (coherente con la arquitectura propuesta, Qwen), no un OCR
tradicional aparte — pero eso es una decisión para cuando haya casos
suficientes, no ahora. **Sesión 2026-09-17: ya hay casos suficientes para
plantearlo** (140 documentos, ~1.800 filas, 67 expedientes; piloto real con
`claude-haiku-4-5`: una página densa, 21 filas, 1 dígito mal en una medida,
~0,01 $; coste total estimado ~6-11 $ una vez, 2-3 sesiones de desarrollo).
Pendiente de decisión del cliente; choca con la regla de la sección 6.
**Decidido e implementado el mismo día** (`app.extraccion.ocr`): `OCR_MODO`
("escaneados" por defecto, "desactivado"), solo para documentos sin capa de
texto, caché por hash (`cache_ocr_documento`), líneas marcadas
(`texto_reconocido`, motivo y prefijo "[reconocimiento óptico]" en fragmento y
trazas). Segundo uso permitido del modelo, además del de la sección 6. Lanzado
sobre el corpus: +2.316 líneas en 54 expedientes, ~10,75 $.

---

## 16. Pendiente de resolver

- **Excel de ejecución SAP (367 expedientes, departamento 28510): estado de
  contrato incorporado, cobertura del descubrimiento medida (sesión
  2026-09-07, `docs/sesion-2026-09-07-sap-ejecucion-cobertura.md`).**
  `expedientes.estado_contrato_sap` (fuente de entrada permanente, igual que
  el Excel de códigos: `ESTADO_SAP_PATH`, `app.extraccion.estado_sap`,
  `POST /mantenimiento/estado-sap/cargar`, repetible) implementado, cargado
  (367 filas, 327 expedientes nuevos, 40 actualizados) y visible en la web y
  el Excel. **Hallazgo central**: el descubrimiento por sindicación cubre
  solo el 2,5 % de los 367 (9 expedientes, todos de 2024-2026) — una entrada
  de sindicación refleja un evento de contratación en ese mes, no "sigue
  vigente", así que el tercio del SAP anterior a 2021 (127 expedientes) es
  estructuralmente invisible para ese mecanismo, no solo pendiente de
  barrer. El Excel de SAP no es un complemento menor, es la única fuente de
  la que el sistema puede saber que esos expedientes existen. Encolado el
  proceso de los ≈335 que faltan (29 prioritarios con prefijo `2.`/`3.`/`4.`
  + un ciclo de mantenimiento para el resto), corriendo sin supervisión
  detrás del backfill de sindicación de 21 meses que ya ocupaba el único
  worker — ritmo medido (46 s/descarga, 37,6 s/extracción) y estimación
  (~8,5 h + lo que quede del backfill) documentados, sin resultado final
  todavía al cerrar la sesión. **Hallazgo de paso**: los "25 expedientes con
  prefijo `2.`/`3.`/`4.` dados por no publicados en su día" que traía el
  encargo no corresponden a ningún dato real del sistema — los únicos
  `sin_publicar` con esos prefijos son el conjunto fijo de PDFs de prueba de
  `Ejemplo/Input/` (departamentos 04703/04110/28520/20810/27520, sección 13),
  no los 25 códigos reales del SAP (departamento 28510), que se crearon
  nuevos con esta carga y nunca se habían buscado en la Plataforma.

- **Segunda familia de baja: diseñada e implementada de forma acotada**
  (sesión 2026-09-05). Los 3 expedientes conocidos (`6.23/28510.0018`,
  `0102`, `6.25/28510.0016`, todos Acuerdo Marco de carril, ArcelorMittal)
  usan `P(t) = Precio_ofertado × Kt × Coeficiente de baja` por pedido futuro,
  no una baja única de lote (sección 4). Ni `Kt` (índices IPRI de energía y
  acero) ni el Coeficiente de baja existen en ningún documento de la
  licitación — se fijan pedido a pedido, en el futuro. Implementado:
  `lotes.modelo_precio` (`fijo`/`indexado_por_pedido`, migración `0016`),
  `lotes.coeficiente_transformacion` (el único parámetro real que sí está en
  la licitación), detector por marcador literal
  (`app.extraccion.modelo_precio_indexado`), y los 3 expedientes pasan a
  `completado` con `baja_lote` `NULL` por diseño. Deliberadamente sin
  implementar: extracción de los pesos de `Kt`/grupos IPRI, ni cálculo de
  `Kt` en sí (exigiría consultar al INE en vivo). Puede haber más casos de
  esta familia u otras variantes (p. ej. el hilo de cobre indexado a LME de
  `6.20/28510.0136`) sin identificar: no lo des por supuesto. Ver
  `docs/identidad-expediente.md` sección 28.
  **Cerrado, sesión 2026-09-07** (`docs/descubrimiento-inverso-matriz-
  pedidos.md`): comprobado con los documentos reales de los 9 pedidos
  conocidos de las 3 matrices (no solo con los de la matriz, ya cerrado en
  la sesión de 2026-09-05) que el "Coeficiente de baja" **no está publicado
  en ningún documento de la Plataforma** — ni de la matriz ni del pedido.
  No es una limitación del sistema, es que ADIF y el adjudicatario lo
  acuerdan fuera de la Plataforma. Nada más que implementar aquí sin
  inventar un dato.
- **Confirmar con el cliente si `Precio unitario` en el catálogo es el
  licitado o el adjudicado.** Sigue usándose el licitado — decisión de
  sesión, no confirmación del cliente (`docs/hallazgos-extraccion.md`
  sección 18).
- **6 documentos cuyo código de expediente no captura el patrón actual de
  regex.** El dato está en el documento; falta afinar la expresión regular.
- **Ruido heredado en el Excel de ejemplo** (hecho con Copilot): matrícula
  repetida con descripción vacía, `BRIDA` alternando con `BRIDAS`. Decidir
  si se arranca limpio o el sistema normaliza lo heredado.
- **Comprobar si la plantilla `L9_CM.32-FE` (Dirección Técnica) sigue el
  modelo de baja única por lote o es la segunda familia** — sin verificar
  todavía.
- **Patrón de extracción de lote para Propuesta LC.27 multi-lote sigue sin
  verificar contra un documento real.** La generalización de
  `docs/identidad-expediente.md` sección 27 lo cubre por analogía con la
  Resolución de Adjudicación, no por evidencia — si aparece una LC.27
  multi-lote real con redacción distinta, revisar ese módulo antes de
  confiar en el resultado.
- **`6.24/28510.0025` y `6.24/28510.0193`: confirmado sin cuadro de precios
  publicado en la Plataforma, no un fallo del scraper** (sesión 2026-09-05,
  `docs/hallazgos-extraccion.md` sección 31.1). Verificado en vivo contra la
  Plataforma real: la ficha de ambos solo publica Adjudicación y Contrato,
  ningún Anejo ni Pliego — el propio Contrato remite el cuadro de precios a
  "el Anejo 1 del PPT", nunca publicado para estos dos expedientes. Siguen
  en `pendiente_revision` con un motivo que ya lo dice explícitamente
  (posible ausencia de origen a escalar a ADIF, no un valor que este sistema
  pueda inventar).
- **Rendimiento de `6.23/28510.0051`: explicado, cerrado.** Auditoría previa
  (`docs/auditoria-previa.md` bloque 1, sesión 2026-09-04): una tanda de 38
  expedientes completó en 21,6 min sin cuelgue, `0051` dentro de su baseline
  (108 s). Sesión de corrección de defectos (2026-09-05): el ciclo de
  mantenimiento forzado tardó **30,8 min** en una ejecución real — a
  primera vista, otra reproducción del episodio. Diagnóstico en caliente
  (RSS/FD por minuto, `docker stats`, `pg_stat_activity`, todo mientras
  corría, sin tocarlo) descartó un cuelgue: el proceso estuvo el 100% del
  tiempo en estado `R` (ejecutando, nunca `D`/bloqueado), CPU al ~100-106%
  sin caídas, memoria con un único pico de 2,9 GiB durante
  `6.23/28510.0139` (no `0051`) que baja y se estabiliza en 1,3-1,5 GiB el
  resto de la tanda, 4 descriptores de fichero constantes de principio a
  fin, y una única conexión a Postgres sin ninguna consulta de larga
  duración. **La causa real de los 30,8 min**: el descubrimiento por
  sindicación de ese ciclo encontró 4 expedientes nuevos y los descargó de
  la Plataforma real (Playwright headless) antes de extraer — trabajo real
  y esperado, no una fuga. Dos reprocesos limpios posteriores, forzados con
  `sindicacion_desactivada: true` (sin descargas), completaron en **24,4
  min cada uno para 42 expedientes**, de forma idéntica entre sí, sin
  ninguna anomalía — `6.23/28510.0139` es sistemáticamente el expediente
  más lento del corpus (~206 s en las tres mediciones), no `0051`. **No hay
  fuga ni cuelgue que arreglar**: el "problema de rendimiento" original
  queda explicado como la suma de tiempo de scraping real más la
  heterogeneidad esperada de duración por expediente. Detalle completo
  (curva minuto a minuto) en `docs/hallazgos-extraccion.md` sección 30.5.
- **Separar de verdad `6.24/28510.0088` y `6.23/28510.0129` (y expedientes
  similares) en expedientes de lote reales.** Identificado como cambio de
  modelo de datos mayor (crear filas de `Expediente` nuevas para cada
  lote), fuera de alcance de un arreglo urgente. Ver
  `docs/identidad-expediente.md`, sección "autoridad del PDF sobre la
  sindicación". **Sesión 2026-09-14:** cuando el expediente de lote SÍ
  existe y lo sabe (la adjudicación o su propio Contrato ligan su número a
  su código), guarda solo su lote y se queda con las tablas que no declaran
  lote, salvo el anejo de criterios del conjunto (decisión del cliente,
  tercera parte de `docs/sesion-2026-09-14-revision-cliente-pliegos.md`).
- **Abierto al cerrar la sesión 2026-09-14 (tercera parte): cerrado en la
  sesión 2026-09-15** (`docs/sesion-2026-09-15-verificacion-localizador-
  tablas.md`), ver la entrada de esa sesión al final de esta sección. Sigue
  en pie: el anejo de criterios se guarda una vez por documento y expediente
  (volumen, no hueco).
- **`expedientes.aviso_sindicacion` existe en la API pero no se muestra
  todavía en la web** — pendiente menor de la sesión de criterios del
  cliente (`docs/decisiones-cliente.md` sección 26).
- **`6.24/28510.0116` no debe usarse como ejemplo de demo hasta
  confirmarlo con el cliente.** Discrepancia real entre dos documentos del
  mismo expediente: la Propuesta de Adjudicación declara una baja del
  47,87%, el Contrato firmado declara 46,50% (sobre 1.485.000 €, no es
  redondeo). El sistema usa el 46,50% del Contrato — probablemente correcto
  (es el acto más definitivo), pero CONTEXTO.md no documenta explícitamente
  una prioridad Contrato-vs-Propuesta (solo Propuesta LC.27 vs. Resolución
  de Adjudicación, sección 17). Verificado en
  `docs/auditoria-previa.md` bloque 3, parte A.
- **Excel al cliente: corregido (sesión 2026-09-06).** Marcadores de texto
  fuera de las columnas numéricas, precio adjudicado y baja de lote
  añadidas, huérfanas sin lote excluidas del Excel por defecto (con hoja
  "Resumen" y parámetro `incluir_pendientes` para volver a incluirlas), 268
  huérfanas redundantes limpiadas, y un bind-mount de Docker roto en
  silencio (fichero de códigos ausente) que dejaba el cruce mal para
  siempre en 6 expedientes, ya corregido con una comprobación de arranque
  permanente. Detalle completo y números finales en
  `docs/excel-cliente-correccion.md`.
- **Residuo de duplicados y descripciones vacías: corregido (sesión
  2026-09-06, bloque 2).** Los 26 grupos/55 filas de "mismo material, mismo
  precio, repetido sin matrícula" no eran el mecanismo B de
  `docs/hallazgos-extraccion.md` sección 30.2 (tabla repetida entre ANEJO y
  CONTRATO) sino uno nuevo: una segunda tabla del mismo documento (anejo de
  "impacto del fallo en la seguridad operacional", o una partida alzada
  repetida entre secciones) que reutiliza el material sin matrícula bajo un
  `codigo_precio` propio — `_firma_material` cae ahora a
  (descripción, precio) cuando no hay matrícula, acotado al mismo lote. Las
  2 líneas con `descripcion = ''` eran en realidad `6.20/28510.0136` (no
  `6.23/28510.0051`, error de atribución de la sesión anterior): descripción
  envuelta en varias filas con una columna fantasma que el guard de
  recuperación excluía por exigir ausencia de matrícula sin necesitarlo.
  Añadida comprobación permanente: sin descripción y sin matrícula, la línea
  no entra al catálogo. Detalle, causa raíz verificada contra los PDF reales
  y números finales en `docs/excel-cliente-correccion.md` bloque 2. Efecto
  secundario real (no una regresión de este arreglo): el reproceso disparó
  por primera vez el mecanismo ya conocido de "banda vacía" en 5 expedientes
  multi-lote, +268 huérfanas pendientes de revisión — causa en una sesión
  anterior no relacionada de ese mismo día (ampliación de
  `_detectar_numero_lotes_pcsp`), dejadas pendientes por decisión del
  cliente, mismo bloque 2.
- **Cuatro comprobaciones del Excel entregado: verificadas, ninguna era un
  fallo de extracción (sesión 2026-09-06, bloque 3).** (1) Las 8 bajas de
  lote con valor 0 son reales — `trazas_origen` guarda el fragmento
  textual exacto ("baja económica del 0,00 % ...", "baja del 0,00% ...")
  anclado a documento y página; la extracción nunca guarda 0 por defecto,
  solo cuando el propio documento lo declara. (2) Código matriz vacío al
  100% en el Excel: re-confirmado ya con el fichero de códigos restaurado
  (bloque 1) — los 8 expedientes con matriz real siguen sin ninguna línea
  porque sus 8 matrices siguen `sin_publicar` en la Plataforma, no por un
  fallo de cruce (48/58 expedientes cruzan bien). (3) Precio máximo
  (1.020.000 €) y mínimo (0,142 €) verificados contra la línea de origen:
  una partida alzada de imprevistos y un precio por tonelada-kilómetro de
  transporte de balasto, ambos legítimos. Comparando cada línea contra la
  mediana de su propio expediente, 114 líneas atípicas en 15 expedientes
  (50 partidas alzadas, 10 caras y 54 baratas por heterogeneidad de
  material dentro del mismo lote) — ninguna con patrón de error de escala.
  (4) La hoja "Resumen" (`app/exportacion.py`) traduce ahora los tres
  motivos de exclusión a lenguaje llano (qué ha pasado / qué haría falta
  para resolverlo, tabla de tres columnas) e incluye una nota fija sobre
  por qué "Código del material" queda vacía en la mayoría de las filas
  (vocabulario controlado todavía corto, CONTEXTO.md sección 6 — no un dato
  perdido). Detalle completo y números finales en
  `docs/excel-cliente-correccion.md` bloque 3.
- **Estados de carga y error de la web: corregido (sesión 2026-09-06).**
  Las cuatro pantallas mezclaban "sin respuesta confirmada todavía" con
  "confirmado que no hay datos": mientras la API no había respondido
  nunca (carga inicial, o la API arrancando y reintentando la conexión a
  la base de datos), cada panel ya enseñaba su recuento en cero y su
  "sin expedientes/casos/ejecuciones todavía" a la vez que, tras el
  umbral de 3 fallos ya existente, el banner de error -- tres mensajes
  contradictorios a la vez, que se leían como datos perdidos.
  `useReintentoConexion` añade un tercer estado, `confirmado` (solo tras
  al menos una respuesta real de la API, nunca vuelve a `false`), del que
  se deriva `cargando`. Las cuatro pantallas distinguen ahora sin mezcla:
  cargando (un aviso, sin cifras), corte real confirmado (solo el
  banner), y confirmado con datos (cifras reales, ceros incluidos si son
  de verdad). Regla: nunca un recuento en cero sin respuesta confirmada.
  Verificado en vivo contra el stack real, incluido un reinicio real y
  repetido de los cuatro contenedores durante la propia sesión. Detalle
  y capturas en `docs/estados-carga-web.md`.
- **Copias de seguridad automáticas: montadas (sesión 2026-09-06).** No
  había ninguna copia periódica de la base de datos, solo volcados
  puntuales a mano antes de cada limpieza -- con un entorno que se
  reinicia solo varias veces al día, perder el volumen `postgres_data` se
  llevaría por delante los expedientes procesados y el catálogo entero.
  Mismo mecanismo que el ciclo de mantenimiento (sección 10, "cuatro
  procesos, ni uno más"): un tipo de trabajo más de la cola
  (`copia_seguridad`), lanzado desde el propio bucle del worker
  (`app.mantenimiento.programacion`, generalizada por tipo de trabajo en
  vez de duplicada). `pg_dump --format=custom` diario por defecto
  (`BACKUP_INTERVALO_SEGUNDOS`/`BACKUP_ACTIVO`), retención configurable
  (`BACKUP_RETENCION`, 14 por defecto, purga las más antiguas), guardado en
  un volumen de Docker propio (`copias_seguridad_bd`) deliberadamente
  distinto del de PostgreSQL. Procedimiento de restauración **probado de
  verdad**: copia real restaurada en una base limpia, recuentos y `md5` de
  todas las filas idénticos byte a byte entre origen y restaurada,
  documentado en `README.md`. Hallazgo de paso: `README.md` todavía
  instruía a sincronizar el repositorio a `~/adif` dentro de WSL para
  compilar ahí -- exactamente el patrón que el invariante 11 de arriba
  prohíbe -- corregido en la misma sesión. Detalle completo, verificación
  en vivo y números en `docs/copias-de-seguridad.md`.
- **"Failed to fetch" desde el navegador: dos causas reales, ambas
  corregidas (sesión 2026-09-06).** El cliente reportó las cuatro
  pantallas fallando desde un navegador real en Windows mientras `curl`
  respondía bien -- la pista correcta para diagnosticar esto, porque
  `curl` nunca aplica CORS y un navegador sí. (1) `CORS_ALLOWED_ORIGINS`
  solo cubría `http://localhost:3000`: un navegador abierto en
  `http://127.0.0.1:3000` (mismo sitio, origen distinto para CORS) veía la
  página cargar pero cada `fetch()` a la API fallaba -- el valor por
  defecto cubre ahora los dos orígenes. (2) Más grave y menos obvio: un
  corte transitorio de conexión a la base de datos (el mismo `dockerd`/WSL
  reiniciándose a mitad de sesión) dejaba que `sqlalchemy.exc.OperationalError`
  se propagara sin capturar desde `get_db()` -- Starlette atrapa eso en su
  propio `ServerErrorMiddleware`, que envuelve el `CORSMiddleware` de la
  app por **fuera**, así que esa respuesta nunca llevaba
  `Access-Control-Allow-Origin` y el navegador lo reportaba como bloqueo de
  CORS, indistinguible a simple vista de un origen mal configurado.
  Reproducido de forma determinista (`docker network disconnect` sobre
  postgres, sin depender de pillar un reinicio real) y arreglado con un
  `@app.exception_handler(OperationalError)` en `engine/app/main.py` que
  devuelve un `503` explícito con la cabecera CORS ya puesta -- ese `503`
  es además justo lo que `useReintentoConexion` (entrada de arriba) ya sabe
  interpretar como "reintentar", no un error opaco. Verificado con Chromium
  real (no `curl`): las cuatro pantallas cargan datos reales en una misma
  pasada. Detalle completo, reproducción y verificación en
  `docs/estados-carga-web.md`.
- **Tolerancia a reinicios de `dockerd`: arreglada en lo que sí está en
  mano del motor (sesión 2026-09-06).** `docs/diagnostico-caidas-dockerd.md`
  ya documentaba que Modo de espera moderno reinicia el *init* de WSL con
  cierta frecuencia (fuera del alcance de este repositorio, requiere
  privilegios de administrador de Windows) — esta sesión ataca la
  consecuencia que sí depende del código: `depends_on: condition:
  service_healthy` de `docker-compose.yml` solo lo respeta `docker compose
  up`, nunca la restauración de contenedores que hace `dockerd` al
  arrancar, así que `api`/`worker` podían arrancar antes de que `postgres`
  resolviera por DNS y morían con un `OperationalError` sin atrapar,
  reiniciando el contenedor entero en vez de reintentar. Añadido
  `app.esperar_bd` (reintentos con espera antes de `alembic upgrade
  head`/`python -m app.worker`, `engine/tests/test_esperar_bd.py`) y,
  encontrado verificando en vivo, un segundo fallo real: un hallazgo de
  conexión transitorio *dentro* del bucle del worker (no de un trabajo
  concreto, que ya aislaba los suyos) también mataba el proceso entero —
  atrapado ahora en `bucle_principal`, reintenta en la siguiente vuelta
  (`engine/tests/test_worker.py`). Verificado contra el stack real,
  forzando y observando docenas de reinicios reales de `dockerd` en vivo:
  cero trazas sin atrapar desde el arreglo. Del lado de la web: la home
  ("/") se quedaba en un banner de error estático para siempre si su fetch
  inicial del servidor fallaba una sola vez — ahora monta siempre
  `ExpedientesPanel`, que sondea solo y se recupera; y los cuatro paneles
  (`ExpedientesPanel`, `CatalogoPanel`, `RevisionPanel`,
  `MantenimientoPanel`) usan `useReintentoConexion` para no mostrar un
  banner rojo hasta varios fallos seguidos, ni por un corte de un par de
  segundos que ya se resolvió solo. `ADIF-WSL-Docker-Watchdog` (tarea
  programada de Windows, reasegura `docker` cada minuto) y
  `ADIF-WSL-Docker-Autostart` corregidas para ejecutarse sin ventana
  visible de consola (`wscript.exe` + `run-hidden.vbs`, antes invocaban
  `wsl.exe` directamente). Detalle completo, hallazgos en vivo y
  verificación en `docs/tolerancia-reinicios-dockerd.md`.
- **Líneas con baja pero sin precio en `6.23/28510.0051`: corregido
  (sesión 2026-09-06, cerrado el 2026-09-07).** En esa tabla la primera
  línea de cada descripción envuelta cae en la banda visual de la fila
  anterior, y ese desfase de una línea producía dos artefactos opuestos en
  `pdfplumber`: una **fila fantasma** (solo un trozo de descripción, el
  resto de columnas en blanco) que se guardaba como línea de catálogo con
  la baja del lote heredada y ningún precio del que derivar el adjudicado,
  y una **fila fusionada** (dos filas de datos reales fundidas en una) cuyo
  código y precio traían dos valores dentro de la misma celda
  (`"P-0090\nP-0091"`), imposibles de interpretar. `construir_linea_catalogo`
  descarta ahora la primera y `_dividir_fila_multiple` separa la segunda en
  sus N líneas reales — solo cuando código Y precio se dividen en el mismo
  N≥2 y cada valor por separado ya tiene forma válida, nunca a ciegas. La
  descripción no se reparte entre ellas (el desfase impide una
  correspondencia 1:1 verificable, sección 8): cada línea se queda el bloque
  entero y se marca para revisión. Tercer defecto, encontrado verificando el
  arreglo contra la base de datos real y no cubierto por las pruebas de
  unidad: esas líneas comparten descripción, no tienen matrícula y pueden
  compartir precio, así que `_firma_material` las veía como el mismo
  material y `_combinar_por_clave` las volvía a fundir — de `P-0058`/`P-0059`
  quedaba una sola fila, con la clave de uno y el código del otro, y un
  material real desaparecía del catálogo. `_firma_material` ya no da firma a
  una línea recuperada de una fila fusionada: su descripción es un bloque
  compartido, no una identidad. Verificado reprocesando el expediente
  entero contra el stack real: 3 filas fusionadas separadas (6 líneas, todas
  marcadas), 0 líneas fantasma, 0 líneas con baja y sin precio y 0 claves
  incoherentes en todo el corpus. Detalle completo en
  `docs/excel-cliente-correccion.md` bloque 4.
- **Cantidad con forma de año, y unidad de medida ausente de las cuatro
  pantallas: corregido (sesión 2026-09-07).** El cliente detectó que
  `Cantidad` a veces trae lo que parece un año. Rastreado hasta dos
  variantes reales de un mismo defecto: el modelo, al mapear una cabecera
  sin ninguna columna de unidad real, tiende a asignar `unidad_medida` a
  una columna ajena en vez de devolver `null` — la referencia normativa de
  un material (`6.20/28510.0054`, traviesas, "E.T." → "03.360.571.8") o un
  valor de otra columna desplazado por una columna fantasma
  (`6.20/28510.0094`, candado/llave, "956"/"102"). `cantidad` en sí estaba
  bien mapeada en ambos casos — el valor con forma de año en las traviesas
  es el dato real de una columna que el propio documento llama "CANTIDAD DE
  REFERENCIA", ambiguo en origen, no un fallo de extracción. Arreglado con
  una validación estructural nueva en `_construir_campos`
  (`engine/app/catalogo.py`): una `unidad_medida` extraída que sea solo
  dígitos y puntos nunca es una unidad real, se descarta y se marca para
  revisión — cubre las dos variantes encontradas y cualquiera futura no
  vista todavía, sin depender solo de corregir la caché. Las 5 firmas de
  cabecera ya cacheadas con este mapeo (todas resueltas por el modelo,
  ninguna por las reglas deterministas) se corrigieron directamente, y las
  36 líneas ya guardadas con el valor malo se corrigieron en base de datos
  (el reproceso solo no basta: "un `None` nunca pisa un valor ya
  conocido" es la regla correcta para el caso contrario). Añadida además
  una comprobación de `cantidad` implausible (forma de año, o cero) que
  marca para revisión sin inventar ni descartar el dato nunca — deliberado
  no automatizar un chequeo de "N veces la mediana del expediente": produce
  falsos positivos legítimos (material pequeño comprado a granel, toneladas
  frente a tonelada-kilómetro), mismo hallazgo que ya cerró esto para
  precios en el bloque 3. Segunda mitad de la sesión: `unidad_medida` ya se
  guardaba desde el principio del proyecto pero no aparecía en ningún sitio
  visible — añadida a las cuatro pantallas (tabla de catálogo, detalle con
  trazabilidad, tabla de la cola de revisión) y al Excel como decimocuarta
  columna, al final, sin alterar el orden de las once originales. 94,6% de
  las líneas del catálogo la traen; verificado contra 6 expedientes
  distintos con `pdfplumber` sobre el documento real que las unidades
  guardadas son plausibles para su material. Detalle completo, las cuatro
  sondas de medición y los números finales en
  `docs/excel-cliente-correccion.md` bloque 5.
- **Orden por defecto de `/catalogo`: la primera pantalla sin filtrar daba
  la impresión contraria a la realidad (corregido, sesión 2026-09-07,
  mismo día que el punto anterior).** El único orden que existía
  (alfabético por expediente/lote) aterrizaba siempre en los mismos
  expedientes — alfabéticamente primeros ("6.20/..." antes que "6.23/...")
  y, coincidencia del corpus, justo los que tienen las tablas de origen más
  escasas (`6.20/28510.0054`, `0136`, `0094`: sin columna de código de
  precio ni de unidad en el documento real, verificado contra el PDF, no un
  fallo). El cliente veía "No consta"/"No aplica" en casi toda la pantalla
  al abrir el catálogo sin filtrar, aunque el 94,6%-96,9% del catálogo real
  esté bien relleno. Nuevo criterio por defecto, "completitud"
  (`app.catalogo_consulta._puntuacion_completitud`): puntúa de 0 a 4 cuánto
  trae cada línea (un identificador propio -- código de precio o
  matrícula, cualquiera de los dos cuenta, nunca se exigen ambos porque la
  matrícula falta por diseño en buena parte del corpus --, cantidad,
  unidad de medida, precio unitario) y ordena por eso primero, con el
  mismo desempate de siempre como segundo criterio para que paginar
  siga siendo estable. El alfabético de siempre se deja disponible con
  `?orden=alfabetico` (`ORDENES_VALIDOS`), y un selector visible en
  `CatalogoPanel.tsx` ("Líneas más completas primero" / "Alfabético").
  Verificado abriendo `/catalogo` en un navegador real: la primera pantalla
  (25 filas) pasa de una celda vacía por columna en casi cada fila a solo
  "Pendiente" en Precio adjudicado (baja de lote todavía no declarada para
  ese expediente concreto -- estado real, no un hueco) y nada más.
- **Expedientes publicados que faltaban: causa real encontrada y arreglada
  (sesión 2026-09-07, caso `6.26/28510.0014`).** El cliente reportó un
  expediente ausente que sí está publicado en la Plataforma. Diagnóstico
  del caso concreto: **existe en la Plataforma** (el scraper real lo
  encuentra al momento, "Pedido nº3 acuerdo marco de suministro de carril
  nuevo...", 3.005.618,56 € de licitación, 2 documentos descargados sin
  ningún problema); **no aparece en el Excel de códigos** (ninguna de las
  666 filas de su única hoja); **no aparece en la sindicación**, en
  ninguno de los dos únicos periodos jamás ingeridos. La búsqueda funciona
  perfectamente en cuanto se dispara — el fallo está en el descubrimiento,
  nunca llegó a dispararse solo.

  Causa raíz medida contra la base de datos real: `descubrir_novedades`
  siempre aceptó un `periodo` explícito, pero **nada la llamaba nunca con
  otra cosa que el mes en curso** — solo dos periodos se habían ingerido
  jamás, `202408` (prueba puntual de la sesión original) y `202609` (el mes
  en curso de esta sesión). **Unos 25 meses intermedios nunca se
  comprobaron.** Un expediente cuyo único cambio de estado cayó en uno de
  esos meses saltados queda invisible para siempre, aunque esté publicado
  con normalidad. Segunda comprobación, también real: el cruce con el
  Excel de códigos (`app.extraccion.cruce_codigos._cargar_indice`) leía
  siempre `libro.worksheets[0]`, la primera hoja — mismo defecto que tenía
  el scraper heredado. El fichero de ejemplo de este repositorio solo trae
  una hoja, así que no se pudo reproducir contra datos reales, pero se
  corrige igual (lee todas las hojas) porque el fichero real que mantiene
  ADIF puede traer más de una y el código no debe asumirlo. Filtro de
  departamento (`SINDICACION_DEPARTAMENTOS_ADIF=28510`) descartado como
  causa: el expediente es del departamento correcto, y `docs/hallazgos-
  sindicacion.md` sección 24 ya había medido con datos reales que 28510 es
  el departamento correcto para material de suministro (obra civil de otros
  departamentos generaría `pendiente_revision` en masa sin ser un fallo
  real).

  Arreglo: `app.sindicacion.descubrimiento.descubrir_backfill` +
  `periodos_recientes`, nuevo trabajo de cola `sindicacion_backfill`
  (`POST /mantenimiento/sindicacion/backfill`, payload `periodos` o
  `meses`) — recorre varios periodos pasados llamando a
  `descubrir_novedades` una vez por cada uno, aislando el fallo de un mes
  concreto del resto de la tanda. `_cargar_indice` lee ahora todas las
  hojas del Excel de códigos, no solo la primera. 12 tests nuevos, 393
  pasan. Verificado en vivo contra la Plataforma y la sindicación reales de
  esta sesión: expediente descubierto y descargado a mano
  (`6.26/28510.0014`, ya en `pendiente_revision` con documentos reales);
  backfill real lanzado para varios meses recientes, mes en curso (202609)
  procesado correctamente (61 expedientes ADIF totales, 4 del departamento
  configurado, 0 nuevos — coincide con lo ya conocido). El backfill de
  meses completos anteriores es lento en esta red (varios minutos por mes,
  el ZIP mensual supera los 100 MB) — sigue corriendo en la cola del
  sistema de forma asíncrona, consultable en
  `GET /mantenimiento/sindicacion/historial`; números finales en
  `docs/hallazgos-sindicacion.md` sección 25. **Continuado, sesión
  2026-09-07 (continuación):** ritmo medido con datos reales (~150-160 MB
  y ~11 min por mes en esta red), reportado antes de lanzarlo entero. Los
  ~21 meses restantes (`202409`-`202605`) lanzados como un único
  `sindicacion_backfill` en segundo plano — al ritmo medido, del orden de
  3,5-4 horas, casi toda en descarga. Números finales pendientes de esta
  ejecución en
  `docs/sesion-2026-09-07-adjudicatario-revision-vocabulario.md`.
- **Descubrimiento inverso matriz → pedidos: implementado (sesión
  2026-09-07, `docs/descubrimiento-inverso-matriz-pedidos.md`).** Hasta
  ahora el sistema solo resolvía pedido → matriz; nunca al revés. Verificado
  en vivo que ni la ficha de la matriz ni la sindicación enlazan sus
  pedidos, pero el buscador de la Plataforma sí permite acotar por
  `Sistema de contratación = Contrato basado en un Acuerdo Marco` +
  Órgano + Adjudicatario — encontró los 9 pedidos conocidos entre 92
  candidatos reales. Cada candidato se confirma abriendo su propia ficha
  ("Acuerdo Marco → Expediente") porque un adjudicatario puede tener más de
  un acuerdo marco a lo largo de los años; el resultado se cachea
  (`candidatos_acuerdo_marco`, migración `0017`) para no reabrir fichas ya
  comprobadas, y corre semanalmente (`descubrimiento_pedidos`, mismo
  mecanismo que el ciclo de mantenimiento y las copias de seguridad) o a
  mano por matriz. Si una matriz no tiene adjudicatario extraído, lo señala
  (`Expediente.aviso_descubrimiento_pedidos`) en vez de saltársela en
  silencio. `Expediente.pedidos` (relación inversa) y `ExpedientesPanel.tsx`
  ya presentan la matriz junto a sus pedidos. Procesados los 9 pedidos
  reales contra el stack: 9/9 `completado`, 120 líneas de catálogo
  heredadas, 13 matrículas pasan a aparecer en 12 expedientes cada una (su
  matriz + sus 3 pedidos, × 3 familias) — confirma con datos reales que los
  expedientes de carril comparten matrículas entre sí. Dos hallazgos de
  paso corregidos en la misma sesión: `lotes.adjudicatario` nunca se
  guardaba en el camino de lote único implícito (solo el multi-lote
  explícito), y una segunda forma real del campo MATRIZ ("Identificador
  contrato original", sin la sección "Licitación basada en el acuerdo
  marco"). **Cerrado, sesión 2026-09-07 (continuación)**
  (`docs/sesion-2026-09-07-adjudicatario-revision-vocabulario.md`):
  `app.extraccion.campos_lc27.extraer_adjudicatario_lc27` añadido (mismo
  patrón "a la empresa..., con NIF/CIF" que ya usaba el camino multi-lote,
  generalizado para cubrir una variante real sin la palabra "con"). Las
  tres matrices de carril tienen ya su adjudicatario extraído y las tres
  completan el descubrimiento inverso sin aviso. Adjudicatario pasa de 13 a
  40 de 52 expedientes reprocesados. De paso, sexto formato real de
  `codigo_precio` encontrado y corregido ("Cod0001", prefijo + 4 dígitos,
  `4.26/28510.0020`): sin él, una tabla real de 13 filas limpias se
  descartaba entera como espuria y el expediente quedaba sin catálogo pese
  a tener la tabla intacta.
- **Huérfanos de banda vacía: señal informativa añadida, sin descarte
  automático (sesión 2026-09-07, continuación,
  `docs/sesion-2026-09-07-adjudicatario-revision-vocabulario.md`).** Un
  intento de descartar automáticamente una huérfana que coincide en
  matrícula/descripción/precio con una línea ya resuelta del mismo
  expediente se revirtió al romper el caso de aceptación multi-lote real
  (`6.25/28510.0027`, "Suministro de balasto, 6 LOTES"): un precio de
  referencia ("P-1 Balasto sobre camión en cantera") puede coincidir
  legítimamente entre lotes distintos de la misma licitación sin ser la
  misma fila repetida — verificado con datos reales. Como "huérfana de
  banda vacía" solo existe en expedientes multi-lote por construcción, ese
  riesgo cubre el 100% del dominio de esta heurística: no se implementa.
  En su lugar, `app.catalogo.buscar_posible_duplicado_huerfana` calcula la
  señal (nunca decide) y `RevisionPanel.tsx` la muestra como una
  comparación de un vistazo con dos botones de un clic (confirmar como
  distinta / descartar como duplicado, con motivo ya redactado) — de las
  797 huérfanas reales de banda vacía, cuántas traen la señal tras el
  reproceso completo queda pendiente de medir (ver doc de la sesión).
- **Vocabulario del código de material ampliado, con vía de modelo cacheada
  (sesión 2026-09-07, continuación,
  `docs/sesion-2026-09-07-adjudicatario-revision-vocabulario.md`).** De 11
  a ~90 sustantivos reales del corpus (extraídos por frecuencia real, no
  inventados), con salto de tokens de unidad de medida sueltos y
  normalización de acentos/plural a forma canónica.
  `derivar_codigo_material_con_modelo` añade la vía de modelo con caché por
  término (`cache_codigo_material`, migración 0018, mismo mecanismo que
  `cache_mapeo_cabecera`) para lo que la regla no casa. Relleno antes: 8,1 %
  (253/3.121 líneas); número final tras el reproceso completo, pendiente.
  **Actualizado tras el análisis del corpus a 467 expedientes
  (`docs/analisis-corpus-467-expedientes.md`): 66,7 % (5.486/8.225
  líneas)** — muy por encima de lo esperado solo con vocabulario, gracias a
  la vía de modelo funcionando a escala real (verificado en los logs del
  worker durante el reproceso completo).
- **Análisis del corpus a 467 expedientes: hecho, dos hallazgos nuevos sin
  arreglar** (`docs/analisis-corpus-467-expedientes.md`). (1)
  `app.scraping.pcsp.ensure_form` tiene un presupuesto de espera fijo y
  corto (~3 s) que no aguanta la Plataforma cuando responde más lenta de lo
  habitual (medido en vivo: el formulario apareció a los ~7,5 s) — mismo
  tipo de fallo que motivó el arreglo de límite de tasa de esta sesión
  (confundir un fallo transitorio con algo determinista), pero en una etapa
  anterior y no cubierta por ese arreglo. Bloqueó la verificación a mano de
  los 62 expedientes del SAP dados por "no encontrados" (encargo del
  cliente, sin completar). (2) Documentos compartidos entre expedientes
  hermanos (mismo hash de PDF bajo dos códigos de expediente distintos, la
  constraint `UNIQUE(documentos.hash)` deja al segundo sin ninguna fila
  propia) confirmado en al menos 26 de los 303 expedientes en revisión —
  no es un bug nuevo, es el límite ya documentado más arriba ("Separar de
  verdad [...] en expedientes de lote reales [...] fuera de alcance de un
  arreglo urgente"), que con 45-52 expedientes nunca llegó a manifestarse y
  ahora, con 467, sí. **Cerrado, sesión 2026-09-08:** `Documento` pasa a
  relación muchos-a-muchos con `Expediente` vía `DocumentoExpediente`
  (migración 0021) — el fichero físico (hash, tipo, ruta) se separa de la
  relación con cada expediente que lo referencia, así que un documento
  puede enlazarse con más de uno sin duplicar el fichero. (3) `GET
  /revision` no está paginado (a diferencia de
  `/catalogo`): 255 ms / 400 KB por respuesta con 303 casos, sondeado cada 3
  segundos por la web — sigue siendo rápido en términos absolutos, pero es
  la única de las cuatro pantallas sin paginación de servidor y el primer
  sitio donde se notará si la cola de revisión sigue creciendo.
- **Verificación del Excel de 6.599 líneas: tres defectos de origen
  corregidos, cuarto analizado sin implementar (sesión 2026-09-08,
  `docs/sesion-2026-09-08-verificacion-excel-6599.md`).** Causa central:
  `app.extraccion.firma_cabecera.calcular_firma_cabecera([])` hashea igual
  cualquier tabla sin cabecera detectada (típico de una tabla que continúa
  sin repetir cabecera), así que el mapeo del modelo aprendido para la
  PRIMERA tabla así del corpus se reaplicaba a ciegas a todas las demás,
  con columnas en otro orden — origen de las líneas sin expediente, sin
  descripción y con precio a cero que reportó el cliente (`6.24/28510.0184`,
  `0209`, `6.21/28510.0108`, `0109`). Arreglado: una cabecera sin ninguna
  celda con texto real nunca se cachea ni se lee de caché
  (`app.extraccion.mapeo_cabecera.mapear_cabecera`). Dos causas más,
  puntuales, detrás de las 38 líneas sin descripción: un patrón nuevo,
  imagen especular del "fila fantasma" de 2026-09-06 (el precio, no la
  descripción, llega en la fila siguiente —
  `app.catalogo._es_fila_precio_continuacion`) y una partida alzada cuyo
  texto cae en una columna que el mapeo no reclama para nada
  (`app.catalogo._recuperar_descripcion_ultimo_recurso`). **Gap de
  idempotencia encontrado de paso, sin corregir:** `guardar_lineas_catalogo`
  no borra una fila de una extracción anterior que ya no aparece en la
  nueva — invisible mientras la clave de línea es estable, pero una fila
  sin `codigo_precio` ni matrícula usa `hash(descripción + orden)` como
  clave, así que si la descripción cambia entre dos reprocesos de la misma
  fila (justo lo que hacen los dos arreglos de arriba) la fila vieja queda
  huérfana en vez de sustituirse. 5 filas así, limpiadas a mano tras
  verificar cada una contra su reemplazo real; una poda automática
  necesitaría decidir primero qué pasa si solo se reprocesa un subconjunto
  de las tablas de un documento, fuera de esta sesión.
  **Cerrado, bloque 4, sesión 2026-09-10:** el subconjunto nunca ocurre —
  `procesar_anejo` extrae siempre el documento entero en una pasada, y solo
  se usa si termina sin excepción. `podar_lineas_obsoletas_de_documento`
  (`app/catalogo.py`) borra, dentro de `(expediente_id, documento_id)`,
  cualquier línea que `guardar_lineas_catalogo` no tocó en este ciclo;
  `guardar_lineas_catalogo` devuelve `ids_tocadas` para que el orquestador
  las acumule por documento y pode una sola vez al terminarlo. Silenciosa,
  sin `motivo_revision` (mismo criterio que `_limpiar_huerfana_superada`);
  contada en `lineas_podadas` del resumen. 7 tests nuevos, 591 pasan.
  Verificado en el stack real (3 expedientes del bloque 3 + muestra de 15
  más): 22.724 líneas antes y después, sin cambios — el mecanismo queda
  armado para que el reproceso completo del bloque 5 limpie el residuo real
  acumulado de sesiones anteriores. **Cuarto punto,
  analizado sin tocar código:** el motivo mayoritario de las 3.102 líneas
  pendientes ("ninguna cabecera LOTE N", 2.001 líneas) concentra el 79,7 %
  en un único documento de 37 páginas compartido por dos expedientes
  hermanos (`6.22/28510.0122`/`0156`) — una tabla de 17 páginas bajo un
  solo lote, cuya cabecera "Lote 1" solo aparece una vez, nunca repetida en
  las páginas de continuación. `app.extraccion.lote_tabla` ya había
  decidido, explícita y deliberadamente, no implementar herencia de lote
  entre páginas hasta medir el impacto real (docstring del módulo,
  variante "banda vacía" ya documentada, 821 líneas) — lo que el corpus a
  467 expedientes añade es que hay una SEGUNDA variante del mismo
  fenómeno, más grande, no contemplada en esa medición: una página de
  continuación cuya franja trae texto (pie de página, nota) pero nunca la
  palabra "LOTE", que cae en el cubo "ninguna cabecera" en vez de en
  "banda vacía" y por eso nunca se sumó al mismo problema. **Aprobado e
  implementado, misma sesión** (`docs/sesion-2026-09-08-herencia-lote-
  continuacion.md`): la propuesta cambió dos veces bajo verificación antes
  de aprobarse. (1) El documento ancla resultó tener SU PROPIA ambigüedad
  (la cabecera de cada lote cita al otro como repuesto de urgencia, "en
  caso de urgencia que no pueda ser atendida por el adjudicatario del lote
  M") — sin resolver eso primero (Parte A,
  `app.extraccion.lote_tabla._resolver_ambiguedad_urgencia_mutua`, por
  posición gramatical, nunca por contenido) no había ancla de la que
  heredar. (2) Verificando los demás expedientes afectados (no solo el
  ancla), `6.25/28510.0027` (balasto, 6 lotes) expuso que el estado de
  "último lote resuelto" no se reiniciaba al pasar por una mención de LOTE
  rechazada (no declarada) — sin el reinicio, una continuación real
  heredaría el último lote VÁLIDO visto páginas antes, el mismo riesgo de
  mezclar lotes que motivó no implementar esto en su día. Corregido antes
  de reprocesar en serio. Resultado: 3.102 → 494 pendientes,
  `lineas_catalogo.lote_heredado_de_pagina_anterior` (migración 0022) deja
  trazabilidad explícita de cada línea heredada, nunca `False` -- solo
  `True` o ausente. 10 tests nuevos (465 total), incluido un guard de
  seguridad para el mismo riesgo del balasto llegado por una tercera vía
  (limpieza de huérfanas superadas por clave exacta, nunca por contenido).
- **Auditoría automática del catálogo: montada (sesión 2026-09-08,
  `docs/sesion-2026-09-08-auditoria-automatica.md`).**
  `app.mantenimiento.auditoria` (trabajo de cola `auditoria_catalogo`,
  mismo patrón que `copia_seguridad`): se encola y ejecuta sola al terminar
  cada ciclo de mantenimiento, **solo detecta y avisa, nunca corrige**.
  Ocho comprobaciones de solo lectura (duplicadas exactas, campos
  esenciales vacíos, precios a cero/negativos/desproporcionados, cantidades
  con forma de año, bajas fuera de rango, firma de cabecera cacheada
  vacía/corrupta, líneas que cambian sin cambiar documentos, y campos
  vacíos por columna crecientes entre ejecuciones), visible en
  `/mantenimiento` junto al botón manual
  (`POST /mantenimiento/auditoria/ejecutar`). Primer informe real sobre
  10.408 líneas / 467 expedientes: 0 errores, 4 avisos (huérfanas sin lote,
  precios atípicos, cantidades con forma de año, bajas >90% — todos
  categorías ya conocidas del corpus, ninguna nueva).
  **De paso, dos hallazgos del mismo encargo:** (1) el duplicado exacto de
  `6.23/28510.0051` (`P-0058`/`P-0059`) tenía causa real y distinta de lo ya
  cerrado en la sesión 2026-09-06/07 -- `_dividir_fila_multiple` separaba
  bien el código y el precio de una fila fusionada por `pdfplumber`, pero
  nunca la descripción, ni siquiera cuando (como aquí) se divide limpiamente
  1:1 con el número de códigos; corregido, con red de seguridad para el
  caso ambiguo donde el número de líneas no coincide (ver el doc de sesión
  para el caso real que sí motivaba esa cautela). (2) De las 708 líneas del
  catálogo sin código interno ni de proyecto (22 expedientes), 19 no
  figuran en el Excel de códigos de ADIF en absoluto (no es un fallo del
  sistema); 3 (pedidos derivados de acuerdo marco descubiertos por el
  mecanismo inverso, sesión 2026-09-07) sí tienen un fallo de cruce real:
  su `codigo_matriz` se resuelve DESPUÉS de que `asegurar_cruce_codigos` ya
  intentó (y falló) el cruce una única vez. **Cerrado, mismo día (bloque
  3 del doc de sesión):** `asegurar_cruce_codigos` reintenta cuando
  `codigo_matriz` cambia desde el último intento (migración 0023,
  `codigo_matriz_en_cruce`) -- 708 → 616 líneas sin código. El alcance real
  del defecto de importe de licitación medido con precisión (12 documentos
  del Anuncio PCSP agrupan varios lotes bajo "Nº Lote: NNN", tercera
  variante multi-lote, 27 expedientes) y corregido:
  `app.extraccion.lotes_pcsp` da a cada expediente el importe de
  licitación/adjudicación/adjudicatario de su propio bloque, emparejado
  por `nombre_proyecto`. De paso, un nuevo estado explícito,
  `app.extraccion.invalidado.INVALIDADO` ("encontrado pero no atribuible
  con confianza", que SÍ puede borrar un valor ya guardado, a diferencia de
  `None`) -- sin él, 12 de los 14 expedientes de "balasto" seguían
  mostrando el adjudicatario de un lote hermano después de corregir la
  extracción. Mismo defecto extendido a la baja declarada por texto
  (`app.extraccion.baja.extraer_codigo_propio_documento`, "Contrato nº: X"):
  verificado que `6.24/28510.0018` tenía la baja de su hermano `0017`
  (5,07 % en vez de 0,40 %) -- ya corregido. Detalle completo, la tabla de
  las 38 líneas afectadas y los números finales en el bloque 3 de
  `docs/sesion-2026-09-08-auditoria-automatica.md`.
- **Seis cambios del cliente tras revisar el catálogo (sesión 2026-09-09):**
  columnas del Excel renombradas (bloque 1), punto final de `Cantidad`
  corregido (bloque 2), `baja_lote` por línea con el mismo hueco que ya
  tenía `precio_adjudicado` -- también se recalcula desde cero en cada
  pasada, así que un `None` también debe borrar el valor guardado
  (bloque 3, 30 expedientes con "Nº Lote: NNN" reprocesados), unidad de
  medida diagnosticada sin tocar código (bloque 4: 20,1 % vacía, solo 7,3 %
  es un defecto de extracción real -- verificado contra el PDF -- el resto
  es el documento sin columna de unidad o con la unidad embebida en otra
  celda), lista de exclusión de expedientes (bloque 5,
  `EXCLUSION_EXPEDIENTES_PATH`), y desglose de SAP con matrículas concretas
  cargado como fuente permanente (bloque 6, `SAP_DESGLOSE_PATH`,
  `sap_desglose_lineas`) con la cadena de precios licitación→adjudicado→final
  verificada contra datos reales (40/60 coinciden) pero sin implementar
  todavía ni la derivación del coeficiente ni la completitud automática de
  matrícula (encargo explícito: "no lo implementes todavía"). Detalle
  completo y números en `docs/sesion-2026-09-09-cambios-cliente-catalogo.md`.
- **Auditoría del reproceso de 16.647→22.097 líneas, mapeo de cabeceras sin
  cabecera y documentos de adjudicación (sesión 2026-09-09, continuación,
  `docs/sesion-2026-09-09-auditoria-mapeo-documentos.md`).** No se restaura
  la copia de seguridad: la mayoría del crecimiento bruto era basura
  localizada en `6.20/28510.0042/0046/0047` (mapeo del modelo desplazado
  una columna sobre tablas sin cabecera, 3.183 líneas con ~2% de cantidad
  real pero con lote al 100% -- contaminaban el Excel), no un fallo general
  del reproceso; el resto del crecimiento (≈2.400 líneas de otros
  expedientes) es aportación real de calidad igual o mejor que la media.
  **Arreglado:** `evaluar_coherencia_mapeo` (`app.extraccion.
  mapeo_cabecera`) valida el mapeo de una tabla sin cabecera contra TODAS
  sus filas antes de aceptarlo (no solo las 2-3 que ve el modelo) y excluye
  del Excel, sin tocar `lote_id`/`clave_linea` (por idempotencia -- una
  primera versión que sí lo hacía duplicaba filas en cada reproceso), la
  línea de una tabla cuyo mapeo resulta incoherente. **Caché de tablas sin
  cabecera implementada:** `app.extraccion.firma_estructural` clasifica
  cada columna por su contenido (no por número de columnas a secas, que ya
  falló una vez, sesión 2026-09-08) para reutilizar un mapeo ya validado
  entre tablas sin cabecera del MISMO documento, nunca entre documentos --
  verificado que el caso real que tumbó el intento anterior
  (`6.22/28510.0126`) queda correctamente descartado. **Hallazgo que
  revisó el planteamiento del cliente:** el "documento de adjudicación
  equivocado" de `6.22/28510.0126/0125/0094` no lo es -- el boletín de
  Consejo de Administración adjunto sí menciona los tres expedientes con su
  baja real, solo que es una plantilla que el clasificador todavía no
  reconoce (cae en `otro`). De 16 documentos reales del corpus con el mismo
  patrón, 10 mencionan su propio expediente o su matriz (mismo caso, no un
  error); los 6 restantes no traen ningún código legible por texto vacío o
  codificación de fuente rota, no por pertenecer a otro expediente -- cero
  casos confirmados de "documento de otro expediente" en esta muestra. Se
  implementó igual un detector genérico
  (`_detectar_documento_adjudicacion_no_relacionado`) como red de
  seguridad de solo lectura, que de paso reveló que `6.24/28510.0109` y
  `6.24/28510.0216` tenían este mismo boletín adjunto sin ningún aviso.
  **Pendiente:** reprocesar el corpus completo (467 expedientes, ~4-5 h
  estimadas) para que estos arreglos, verificados contra una muestra real
  representativa, alcancen también al resto del corpus; extracción de baja
  para la plantilla de boletín de Consejo de Administración (nueva
  plantilla en la cascada, sesión propia); 6 documentos `ADJUDICACION_*.pdf`
  sin código legible, candidatos a revisión manual contra la Plataforma.
  **Cerrado, sesión 2026-09-09 (continuación),
  `docs/sesion-2026-09-09-reproceso-completo-y-bloques-2-3-4.md`:**
  reproceso forzado del corpus completo lanzado (`POST /mantenimiento/
  ejecutar`, `forzar: true`, `sindicacion_desactivada: true`, sin ninguna
  descarga de red), 358/358 expedientes activos en 3 h 6,7 min. Catálogo
  22.097 → 22.721 líneas (+2,8%); Excel entregado con 19.432 filas. La
  auditoría automática de fin de ciclo pasó de 0 a 3 hallazgos de gravedad
  "error", los tres concentrados en el trío ya conocido
  `6.20/28510.0042/0046/0047` (líneas duplicadas exactas, líneas sin
  descripción, recuento que cambia sin cambiar documentos) — investigado
  contra el Excel real exportado, no solo contra la base de datos: 0 de las
  102 líneas sin descripción llegan al entregable (la exclusión por mapeo
  incoherente de la sesión anterior ya las filtra), y de los 48 grupos de
  duplicados exactos solo sobrevive un residuo pequeño (24 líneas sobre
  19.432, 0,12%). Causa raíz no es nueva: el hueco de idempotencia de
  `guardar_lineas_catalogo` con filas sin `codigo_precio` ni matrícula ya
  documentado en la sesión de verificación del Excel de 6.599 líneas
  (2026-09-08) — sigue pendiente de una poda automática que decida primero
  qué pasa si solo se reprocesa un subconjunto de las tablas de un
  documento. No se restauró la copia de seguridad previa al reproceso
  (`adif_20260909_191412.dump`): el residuo es pequeño y ya acotado.
  **Misma sesión, tres bloques más:** (1) verificado que el sistema ya
  distingue un cero real de un dato ausente en cantidad y precio, en las
  cuatro capas (base de datos, extracción, web, Excel) — ningún cambio de
  código hizo falta. (2) Analizada la propuesta del cliente de agrupar el
  catálogo por código interno para separar su jefatura de otras áreas:
  confirmada con datos reales (99,4% de coherencia entre código interno y
  la columna `ESPECIALIDAD/DISCIPLINA` del Excel de códigos, hoy no
  guardada en base de datos) — mecanismo de exclusión por código interno
  (`INTERNO:NNNNN` en `EXCLUSION_EXPEDIENTES_PATH`) implementado y
  desplegado, sin decidir qué excluir. (3) Preparada la carga del maestro
  de materiales de SAP que ADIF va a facilitar (`MAESTRO_MATERIALES_PATH`,
  migración 0025, tabla `maestro_materiales`): completa `unidad_medida`
  por matrícula exacta sin pisar valores ya extraídos de documentos reales;
  completar matrícula queda deliberadamente sin implementar (necesita
  cruce difuso por descripción con cola de revisión, mismo criterio que el
  cliente ya aplicó al desglose de SAP de la sesión anterior).
- **Maestro de materiales de SAP: recibido y cargado (bloque 1, sesión
  2026-09-10, `docs/sesion-2026-09-10-maestro-materiales-real.md`).** El
  fichero real (`LISTADO_MATERIALES_UNIDAD__MEDIDA.xlsx`, 32.116 filas, sin
  huecos) trae columnas distintas de las que se habían supuesto al
  preparar la carga (`Denominación`/`UM base`, no `Texto breve`/`Unidad
  medida base`) — corregido, junto con `maestro_materiales.matricula`
  ensanchada a `String(10)` (migración 0026, códigos de SAP de 4 y 10
  dígitos además de los 9 del dominio). `unidad_medida` pasa de 75,3% a
  **84,7%** (2.149 líneas ganan unidad); 432 líneas con matrícula no
  aparecen en el maestro de SAP. Añadida detección de discrepancia
  documento-vs-SAP (`unidad_medida_discrepancia_maestro`, nunca pisa
  `unidad_medida`): 354 casos reales tras filtrar sinónimos gráficos de
  "unidad" (`UD`/`UDS`/`UNIDAD` → `UN`, que por sí solos habrían inflado la
  cifra a 3.636 sin ser una discrepancia de sustancia) — de los 354, ~30
  son un precio o una referencia normativa (DIN) metidos en la columna de
  unidad, mismo patrón que el defecto de "unidad ajena" ya cerrado en
  2026-09-07 pero no cubierto por esa validación.
- **Denominación del maestro como vía para la matrícula: analizado, sin
  implementar (bloque 2, sesión 2026-09-10).** De 13.735 líneas sin
  matrícula: 8,6% coincide exacto con una denominación del maestro, 19,7%
  con alta similitud (`difflib` ≥ 0,85) no exacta, 71,6% sin parecido
  razonable (mayoría partidas alzadas/servicios reales sin matrícula por
  diseño, CONTEXTO.md sección 2). Riesgo de coincidencia múltiple
  confirmado y serio: 2.388 de las 28.782 denominaciones normalizadas
  distintas del maestro (8,3%) mapean a más de una matrícula; de las líneas
  de "alta similitud", el 66,6% (1.807) tiene más de un candidato por
  encima del umbral a la vez, con un caso real de dos tornillos de longitud
  distinta (M22×325 vs. M22×275) enlazados a 0,958 de similitud. Si esto se
  implementa algún día, tiene que ser cola de candidatos para confirmación
  humana, nunca asignación automática — ni siquiera para el 8,6% exacto.
- **Precio unitario de 33.611.401 €: causa raíz encontrada y corregida
  (bloque 3.1, sesión 2026-09-10).** `parsear_numero_es`
  (`app/extraccion/normalizacion.py`) aceptaba cualquier cadena con puntos
  como separador de miles válido sin comprobar que los grupos tuvieran tres
  dígitos — una referencia normativa con puntos (`03.361.140.1`,
  recuperada por error de una columna fantasma vecina en
  `6.20/28510.0042`/`0046`/`0047`) se colaba como `33.611.401`. Corregido
  (`_grupos_de_miles_validos`, 4 tests nuevos); verificado contra el PDF
  real que el precio correcto es 7.915,61 € y que el reproceso de los 3
  expedientes lo corrige solo. Revisadas las 3.257 líneas que usan la misma
  vía de recuperación: ninguna otra se acerca a ese orden de magnitud
  (la siguiente más alta, 458.451,02 €, es plausible y ya está marcada
  para revisión).
- **"9 grupos duplicados, 18 filas" en `6.20/28510.0042`/`0046`/`0047`: el
  planteamiento del encargo no era correcto (bloque 3.2, sesión
  2026-09-10).** No es el hueco de idempotencia conocido — verificado
  reprocesando los 3 expedientes a propósito: las mismas 18 filas, mismos
  `id`, sin ninguna copia adicional (una clave inestable habría generado
  una tercera copia; no ocurrió). Son 9 pares/tríos de materiales reales y
  distintos (matrículas de 9 dígitos y descripciones distintas,
  verificado contra el PDF, p. ej. piezas de aguja D/I con el mismo precio
  de fabricante) que pierden matrícula y descripción por el defecto de
  mapeo de "tabla sin cabecera" ya conocido para este trío — no por
  duplicación. **No se borra ni se fusiona nada** (destruiría 9 materiales
  reales); ya están excluidas del Excel entregable por el mismo mecanismo
  de la sesión 2026-09-09, así que no hay impacto visible para el cliente.
  Rediseñar el mapeo de columnas para esta forma de tabla sin cabecera
  queda pendiente de una sesión dedicada.
- **Un `mantenimiento_ciclo` interrumpido se reinicia entero en vez de
  reanudarse: documentado, sin implementar (bloque 5, sesión 2026-09-10,
  encargo explícito del cliente -- "lo vemos cuando termine el
  reproceso").** Destapado en vivo durante el reproceso completo de 358
  expedientes: reiniciar el contenedor `worker` a mitad del ciclo (para
  desplegar el arreglo del bloque 3, ver más arriba) dejó el propio trabajo
  `mantenimiento_ciclo` (id 4097, ~1h30 de ejecución en ese momento)
  huérfano -- `reclamar_trabajos_huerfanos` lo detectó por `bloqueado_en`
  vencido y lo reintentó. El reintento no reanudó por donde iba: volvió a
  ejecutar `ejecutar_ciclo_mantenimiento` desde el principio con el mismo
  payload (`forzar: true`), así que re-encoló los 358 expedientes enteros
  -- incluidos los ~200 que el primer intento ya había reprocesado con
  éxito segundos antes. Pendientes de extracción pasó de 156 a 511 de golpe.
  No corrompe nada (CONTEXTO.md sección 9.9: reprocesar es idempotente), pero
  duplica horas de trabajo ya hecho.

  **Dos causas distintas, compuestas:**
  1. `app.queue.reclamar_trabajos_huerfanos` usa un único umbral
     (`worker_orphan_threshold_seconds`, 300 s) para todo tipo de trabajo, y
     `tomar_siguiente_trabajo` fija `bloqueado_en` una sola vez al arrancar
     el trabajo -- nunca se refresca mientras corre. Un `extraer_expediente`
     normal (30-200 s medidos) nunca se acerca a ese umbral, pero
     `mantenimiento_ciclo` **drena la cola de forma síncrona dentro de sí
     mismo** (`app/mantenimiento/ciclo.py`, docstring del módulo) y puede
     durar horas (3h07 medidas en la sesión 2026-09-09, ~3h en esta) --
     **cualquier reinicio del worker durante un ciclo real, deliberado o no,
     lo marca huérfano casi con certeza**, no como caso raro. Esto no es
     hipotético: CONTEXTO.md sección 13 y
     `docs/tolerancia-reinicios-dockerd.md` ya documentan que este entorno
     de desarrollo sufre reinicios de `dockerd`/WSL varias veces al día.
  2. Aunque el reintento esté justificado (un `dockerd` real caído a mitad,
     no solo un redeploy), `debe_extraer` (`app/mantenimiento/frescura.py`)
     no distingue "obsoleto desde antes de que este ciclo empezara" de "ya
     lo hizo un intento anterior de ESTE MISMO ciclo": con `forzar=True`
     devuelve `True` sin mirar nada más, así que el reintento no tiene forma
     de saber que gran parte del trabajo ya está hecho.

  **Propuesta, sin implementar:**
  - Para la causa 1: heartbeat, no umbral más alto -- refrescar
    `trabajo.bloqueado_en = now()` en cada vuelta del drenaje síncrono de
    `ejecutar_ciclo_mantenimiento` (ya hay una vuelta por trabajo drenado,
    es el punto natural). Un umbral más alto solo retrasaría detectar un
    cuelgue real de horas; un heartbeat detecta un cuelgue real rápido y
    tolera una ejecución larga y sana indefinidamente.
  - Para la causa 2: la información ya existe, como señaló el cliente --
    `Expediente.extraido_en` (cuándo se completó de verdad la última
    extracción) y `TrabajoCola.created_at` (cuándo se pidió ESTE ciclo, fijo
    entre reintentos). Añadir a `debe_extraer` una comprobación previa a la
    de `forzar`: si `expediente.extraido_en` es posterior a
    `trabajo.created_at` del propio ciclo, ya lo hizo un intento anterior de
    este mismo ciclo -- se salta, incluso con `forzar=True`. `forzar` pasa a
    significar "ignora lo obsoleto de antes de pedir este ciclo", no "repite
    ciegamente en cada reintento de este mismo ciclo". Cambio pequeño y
    localizado (una condición más al principio de `debe_extraer`, un
    parámetro nuevo que ya tienen sus dos llamadores a mano).
  - Riesgo operativo inmediato mientras esto siga sin arreglar: el trabajo
    4097 de esta sesión ya va por su segundo intento (`intentos=2` de
    `max_intentos=3`) -- un tercer reinicio del worker antes de que termine
    lo marcaría `fallido` sin más reintentos, no huérfano-y-reintentable. No
    tocar el worker hasta que termine este reproceso.
  **Cerrado el reproceso, mismo bloque:** terminó sin más incidentes
  (segundo intento, 4h19min). Único fallo real: `6.20/28510.0062` (el
  mismo defecto ya corregido, ocurrido antes del despliegue del arreglo) --
  reprocesado a mano después, termina en `pendiente_revision` con motivo
  legítimo, sin volver a tumbar el expediente. La auditoría automática de
  fin de ciclo marcó 15 expedientes como "error" (recuento cambia sin
  cambiar documentos) -- verificado que es la poda del bloque 4 actuando
  por primera vez sobre residuo real (832 líneas podadas en total,
  `lineas_podadas` de cada expediente cruzado contra la lista de la
  auditoría), no un defecto nuevo; pendiente de una sesión futura enseñar a
  `detectar_crecimiento_sin_cambios` a distinguir esto de una subida sin
  explicar. Catálogo: 22.724→21.892 líneas (−832, exactamente lo podado);
  relleno de `unidad_medida` 84,7%→86,6%, `matricula` 39,5%→40,1%,
  `cantidad` 65,9%→67,6%, resto de columnas estable o en ligera subida.
  Excel exportado (`GET /catalogo/exportar.xlsx`): 18.857 filas en
  "Materiales" (19.432 en la sesión anterior, baja por la poda y por
  exclusiones más precisas, no por pérdida de datos) + 3.035 pendientes de
  revisión en "Resumen", cuadra exacto con el total de la base de datos.
  Detalle completo, la tabla de relleno antes/después por columna y el
  cierre de los seis bloques del encargo en
  `docs/sesion-2026-09-10-maestro-materiales-real.md`.
- **Defecto de mapeo sin cabecera de la auditoría (`6.22/28510.0094`/`0126`):
  cerrado (sesión 2026-09-12, bloque 1,
  `docs/sesion-2026-09-12-defecto-mapeo-calidad-interfaz-rendimiento.md`).**
  Causa real: en un subconjunto de filas de una tabla sin cabecera,
  `pdfplumber` fusiona la columna en blanco intermedia con la de
  descripción para esa fila concreta, desplazando el texto una columna a la
  izquierda -- `derivar_mapeo_por_contenido` mapea bien la mayoría de la
  tabla (84% de las filas) pero ninguna recuperación existente cubría las
  filas desplazadas (la de columna fantasma solo miraba la columna
  siguiente, no la anterior). Añadida
  `_recuperar_descripcion_columna_fantasma_anterior` con guarda de
  ambigüedad. Verificado en el stack real: 0 líneas sin descripción, 0
  grupos duplicados, auditoría automática a 0 errores.
- **Barrido de calidad del catálogo a 22.363 líneas: medido, dos hallazgos
  cerrados, dos anotados para decisión (sesión 2026-09-12, bloques 2 y 7).**
  Confirmado sin defecto: descripciones-cabecera (0), precios repetidos
  dentro de expediente (590 grupos, todos legítimos -- balasto/carril con
  precios de referencia compartidos), cantidades extremas (47, ya conocidas
  o plausibles), descuadre precio adjudicado/baja (0). **Cerrado, bloque 7:**
  de las 771 líneas en 8 expedientes con `codigo_precio` igual a la
  matrícula, 651 (91%, 3 expedientes) resueltas del todo -- causa real,
  `_clasificar_columna` solo reconocía el símbolo `€` como precio, ciego a
  tablas cuyo precio no lo lleva (`6.22/28510.0058` p.15); arreglado con un
  criterio estructural (`_PRECIO_SIN_SIMBOLO_RE`, gramática monetaria
  española estricta), sin depender del modelo. Sin cerrar: **61 líneas
  residuales** repartidas en dos causas distintas -- 41 de
  `6.24/28510.0184` (equipamiento de telecomunicaciones sin precio real en
  el origen, decisión de producto pendiente) y 20 en 4 expedientes pequeños
  (`6.21/28510.0097`/`0148`/`0149`, `6.24/28510.0173`) con un patrón NUEVO
  encontrado esta sesión: el precio del catálogo viene de una tabla
  distinta de la que trae la matrícula, sin diagnosticar del todo. Heurística
  de "descripción truncada" probada y descartada por poco fiable (2.362
  falsos positivos sobre texto español legítimo).
- **Repaso de interfaz con datos reales: cerrado (sesión 2026-09-12, bloque
  3).** Catálogo a 1280px, cola de candidatos de matrícula (62ms, 1.387
  pendientes) y coherencia entre paneles ya estaban bien. Corregido:
  `aviso_sindicacion` y `aviso_conflicto_documento_manual` (junto con
  `aviso_ingesta_manual`, sección 16 más abajo) se muestran ahora en
  `/expedientes`, mismo patrón que `aviso_descubrimiento_pedidos`.
- **Rendimiento de un reproceso completo: perfilado y arreglado, 10,4×
  más rápido (sesión 2026-09-12, bloques 4 y 6,
  `docs/sesion-2026-09-12-defecto-mapeo-calidad-interfaz-rendimiento.md`).**
  Hallazgo del bloque 4, contrario a la intuición: **~99% del tiempo era
  texto plano** (`page.extract_text()` de `pdfplumber`, etapa 1 de la
  cascada, sobre TODAS las páginas de TODOS los documentos, además
  extraído POR DUPLICADO -- una vez para clasificar, otra dentro de
  `procesar_anejo` para localizar tablas), no extracción de tablas ni
  modelo ni base de datos. **Bloque 6:** `CacheTextoDocumento` (migración
  0029, clave `Documento.hash`, invalidable subiendo `VERSION_LOGICA_TEXTO`
  sin borrar filas a mano) más la eliminación de la doble extracción
  (`procesar_anejo` reutiliza el texto ya extraído del llamador). Medido
  con un reproceso real (misma muestra de 20 expedientes antes/después):
  308s en frío → **29,6s en caliente** (10,4×); extrapolado a los 358
  expedientes activos, de 3-4 horas a **~9 minutos** con la caché ya
  poblada. Verificado por el camino real de la cola y con la auditoría
  automática (0 errores, catálogo estable sin duplicar nada tras varios
  reprocesos repetidos).
- **Huecos reales, confusión matrícula/precio, determinismo e ingesta
  local: seis bloques cerrados, sesión 2026-09-12 (continuación),
  `docs/sesion-2026-09-12-huecos-determinismo-ingesta.md`.** (1) Análisis
  de las 1.886 líneas con hueco real (sin arreglar nada): concentradas en
  32 expedientes, el 72,4% en dos tríos de expedientes hermanos que
  comparten documento — verificado que gran parte no es hueco de
  extracción sino contenido de OTROS lotes del mismo acuerdo marco,
  adjuntado íntegro a un pedido que solo cubre su propio lote (familia
  `6.24/28510.0130`/`0152`/`0153`, y el mismo patrón confirmado en la
  familia del balasto). (2) Confusión matrícula/precio y precio/cantidad:
  tres causas reales cerradas en `6.24/28510.0184` y otros 3 expedientes
  (precio mapeado a la columna de cantidad en tablas sin precio real;
  confusión matrícula/código también con cabecera real y desalineada de
  sus propios datos; un pie de verificación de firma electrónica colado en
  la celda de matrícula). (3) **Determinismo: dos causas reales
  encontradas y corregidas** — una consulta de documentos sin `order_by`
  (Postgres no garantiza el orden; cuando el mismo `codigo_precio` existe
  de verdad en dos documentos del mismo expediente, cuál ganaba dependía
  del orden arbitrario) y `_eliminar_lote_sentinela_obsoleto` confundiendo
  un lote REAL declarado "1" con el sentinela de migración del mismo
  nombre (lo borraba y recreaba en cada reproceso, para siempre, en 11
  expedientes reales). Verificado con dos reprocesos completos
  consecutivos: resultado idéntico byte a byte. (4) **Ingesta local
  probada de verdad por primera vez** contra el stack real: registra,
  clasifica, extrae y marca el origen correctamente; hallazgo real
  corregido — un documento ya conocido por OTRA carpeta se enlazaba sin
  repetir la comprobación de código declarado, saltándose la protección
  contra carpetas mal puestas. Pendiente: el determinismo de tablas sin
  cabecera propia no cierra al 100% sin una caché persistente de firma
  estructural entre reprocesos (hoy solo dura una pasada); `6.24/28510.0173`
  con una variante de confusión matrícula/precio sin cubrir;
  `6.22/28510.0094`/`0125`/`0126` y `0033`/`0057`/`0058` con residuo de
  mapeo incoherente sin auditar a fondo; decisión de producto pendiente
  sobre si dar una categoría de Resumen propia a "pertenece a otro lote
  del acuerdo marco" en vez de pedir revisión humana repetida.
- **Revisión del cliente sobre el Excel — código del material y matrículas:
  cerrado (sesión 2026-09-14,
  `docs/sesion-2026-09-14-revision-cliente-pliegos.md`).** Los tres pliegos
  del cliente son dos documentos: `Adif 1` = anejo de criterios técnicos de
  la familia `6.21/28510.0108`/`0109`-`0113` (doc 588); `Adif 2` y `Adif 3`
  = el mismo pliego de tornillería de `6.21/28510.0015`/`0016`/
  `6.20/28510.0115` (doc 495; `Adif 3` es una copia escaneada). (1) Código
  del material: el sistema no leía ninguna columna, lo derivaba de la
  descripción y por eso coincidía con "REPUESTO"; decisión del cliente:
  REPUESTO manda (secciones 6 y 7). Solo esa familia tiene la columna. (2)
  Matrículas: el doc 495 trae 103; el catálogo tenía **0** en su campo (34
  metidas en `codigo_precio`, 69 sin leer). No era límite de origen: cabecera
  en fuente sin mapa Unicode ("(cid:NN)") → el localizador no abría la
  tabla y el modelo intercambió matrícula y código; ahora 103/103. (3)
  Hallazgo de paso, el más grande: **el localizador no abría páginas de
  continuación con descripciones largas** (densidad < 0,20) — 246 páginas
  con filas reales en 30 documentos, 46 expedientes. Arreglado (basta un
  identificador de fila si la página anterior es candidata), junto con
  códigos con sufijo de variante ("P-39B"), herencia del mapeo por geometría
  de columnas, cabeceras ilegibles tratadas como "sin cabecera" (nunca al
  modelo ni a la caché; 2 entradas de caché así borradas) y una guarda nueva:
  mismo código de precio con precios distintos en el mismo documento y lote
  (cuadros de varios lotes en un documento compartido) → valor vacío con
  motivo, nunca "el último gana". Unidad de medida con 3+ dígitos (planos,
  normas, precios: 1.273 líneas) descartada. Revisando el reproceso salieron
  tres fallos más de captura de matrícula, también arreglados: sello CSV
  colado en la columna de matrícula (`6.24/28510.0209`), columna llamada
  "CÓDIGO ADIF" (`6.25/28510.0251`/`0213`) y matrícula en la columna fantasma
  de al lado (`6.24/28510.0173`, el pendiente del 12-09). Y una excepción a la
  guarda de choques: las notas de subsanación ("donde aparece / debiendo
  ser") se quedan con la corrección. **Resultado, corpus completo:**
  22.445 → 24.339 líneas; líneas con matrícula 12.720 → 13.244 (+524, 486
  pares expediente-matrícula nuevos, 0 perdidos; las 199 matrículas que
  estaban en `codigo_precio` pasan a su campo); con código de material
  14.248 → 16.074. Excel: 19.898 → 21.384 filas, matrícula 11.386 → 11.924,
  expedientes con líneas 215 → 232; huérfanas (cola de revisión) 2.175 →
  2.694. La guarda de choques deja vacíos 285 cantidades y 49 precios que
  antes se mostraban con "el último gana" (368 líneas marcadas, 74
  expedientes) — decisión revisable. Dos reprocesos seguidos con el mismo
  código dan resultado idéntico; auditoría a 0 errores. 718 tests.
- **Continuación de la misma sesión, respuesta del cliente al reproceso
  (`docs/sesion-2026-09-14-revision-cliente-pliegos.md`, bloques C1-C3).**
  Los precios y cantidades con choque se quedan vacíos (decisión del
  cliente), pero **el Excel explica ahora cada celda vacía**: columna nueva
  "Motivo de las celdas vacías" (antes de "Comentarios"), con los tres
  motivos de la web — no aplica / no consta / **pendiente** (valor distinto
  para cada lote en el documento; falta la baja o el precio) —, decidido en
  el motor (`app.celdas_vacias`) y servido igual a la web; leyenda y
  recuento en la hoja Resumen. **Identidad de lote**: lo "ya resuelto" para
  otras familias era el código de cada lote, pero **ningún expediente de
  lote se restringía a su lote** — 39 expedientes de 12 familias mostraban
  4.955 líneas (y la baja y el importe) de lotes ajenos; ahora un expediente
  que es uno de los lotes (su código es el de uno de los lotes declarados)
  guarda solo el suyo, y el principal sigue con todos. El Contrato ("Contrato
  nº" + "LOTE N") manda sobre la identidad de cada lote: corrige la errata
  de la Resolución de tornillería (el LOTE 2 llamado "LOTE 1"), las
  referencias cruzadas "adjudicatario del LOTE N" ya no roban el código de
  otro lote (`0033`, `0122`), y su baja gana si contradice la de la
  adjudicación (`0057`: 10,50 %, no el 0,50 % del LOTE 2); nunca añade un
  lote que la adjudicación no nombra (corregido en la tercera parte: sí lo
  añade). **Huérfanas nuevas** (519): 83 eran
  legítimas sin aplicar — el "LOTE N" en las filas de título de la tabla o
  al final de la página anterior (`4.26/28510.0020`) —, el resto son
  criterios técnicos comunes a todos los lotes o lotes no declarados; y la
  herencia de lote solo se aplica entre páginas contiguas (heredaba el
  último lote a 5 y a 22 páginas de distancia en cuadros comunes a todos
  los lotes), mientras que el "LOTE N" al pie de la página anterior corrige
  tablas que antes heredaban el lote equivocado (`6.25/28510.0214`). De
  paso: una cantidad y una unidad imposibles (una fila de casillas leída
  como 111.111.111.111.111) tumbaban al guardar dos Contratos enteros de
  `0122`/`0155`/`0156` — ahora se descartan con motivo —, y una matrícula
  partida por el ancho de columna ("59420000\n0") duplicaba 10 líneas de
  `6.25/28510.0251` con la matrícula en `codigo_precio` (defecto de la
  primera parte de la sesión, que el estado guardado ocultaba). **Resultado,
  corpus completo:** 24.339 → 22.115 líneas; sin lote 2.694 → 5.875 (tablas
  comunes que se heredaban como de un lote y anexos que antes no se
  guardaban); Excel 21.384 → 15.979 filas (casi todo, el mismo material
  repetido en cada hermano), 274 con Cantidad o Precio "pendiente". Seis
  reprocesos completos; E1 = E2, E3 = E4 y E5 = E6 línea a línea;
  auditoría a 0 errores. 743 tests.
  Pendiente de decisión del cliente: 36 expedientes cuyo Contrato dice que
  son el LOTE N pero muestran otro lote (2.713 líneas) — resuelto en la
  tercera parte, abajo.
- **Tercera parte de la misma sesión (`docs/sesion-2026-09-14-revision-
  cliente-pliegos.md`, T1-T4).** Las 5.875 líneas sin lote eran, contra los
  documentos: 4.239 del **anejo de criterios técnicos** del conjunto de los
  lotes ("materiales a suministrar en el expediente “… N LOTES”": la lista
  de la licitación entera, con su propia numeración), 208 del cuadro de la
  partida alzada común de `4.26/28510.0020`, 492 de tablas de lotes que el
  expediente no tiene y 936 de los Contratos de `0122` (que eran el anejo
  de criterios, no un anexo de precios); **no se perdía material** (5.512
  → 5.519 materiales distintos en el Excel). Tres premisas de la
  continuación corregidas: `0060` no es un cuadro común sin "LOTE N" (trae
  "Lote 1:" y "Lote 2:"), la regla de no añadir lotes que solo nombra un
  Contrato salía de esa lectura, y el anejo de criterios dice de sí mismo
  que es de todos. **Decisión del cliente:** un expediente de lote que sabe
  cuál es el suyo (adjudicación o Contrato propio) se queda con las tablas
  que no declaran lote, salvo el anejo de criterios; los lotes que solo
  nombra un Contrato se registran (el principal `0051` recupera su LOTE 2);
  sin documento de lotes, el lote implícito es el LOTE N del Contrato
  propio. Salvaguardas verificadas en el PDF: continuación de una tabla de
  otro lote, última mención de lote de otro lote antes de la tabla (cabecera
  en una página que el localizador no abre), Contrato de otro lote.
  Trazabilidad: `lineas_catalogo.lote_del_expediente` (migración 0030).
  **P-0996** (`0051`/`0060`): el anejo de criterios y el cuadro numeran
  distinto el mismo material; la fusión por firma ya no pasa el código de
  una tabla a la otra, nunca renombra a una clave ocupada, no junta dos
  códigos propios de la misma tabla (parejas reales con el mismo texto y
  precio, P-0166/P-0178) y no absorbe al guardar una línea de otro código
  que la misma pasada acaba de guardar desde otro documento. Descartar las
  líneas de un lote hermano solo si su expediente está en el catálogo (si
  no, se conservan sin lote: `6.21/28510.0066`); "Lote 1." con punto
  resuelve la cláusula de urgencia mutua (`0125`/`0126`). El Resumen del
  Excel cuenta el anejo de criterios en su propia fila, fuera de
  "pendientes de revisión", y no manda el expediente a revisión.
  **Estado al cerrar:** última medición completa con el código casi final
  (pasadas F9 = F10, idénticas línea a línea con `id` incluidos): 33.150
  líneas, 18.504 sin lote -- 13.288 del anejo de criterios, 2.161 de lotes
  no declarados, 2.522 sin cabecera o continuación de otro lote, 461 de un
  hermano fuera del catálogo --; ningún documento del corpus falla al
  guardar (P-0996 resuelto); auditoría sin errores salvo 11 parejas de
  códigos distintos con el mismo texto y precio que el propio documento
  repite (verificadas en el PDF). Después entraron tres cambios sin pasada
  completa verificada: "Lote nº1" (`4.25/28510.0207`/`0208`), y los
  motivos "EXPEDIENTE PRINCIPAL distinto" y "cobertura parcial" que ya no
  se piden a un expediente de lote que sabe cuál es el suyo (reproceso
  dirigido de los 20 afectados). Una pasada completa (F11) quedó lanzada
  al cerrar, sin revisar. **Sin hacer:** el Excel final y la comparación de
  materiales distintos con el estado final (la última, D → E5, dio 5.512 →
  5.519, sin material perdido). 766 tests.
- **Verificación de la pasada completa, tablas que no entraban y
  pendientes antiguos (sesión 2026-09-15,
  `docs/sesion-2026-09-15-verificacion-localizador-tablas.md`).** F11 = F12
  byte a byte. Los motivos de expediente de lote se cumplen (0 de 98). "Lote
  nº1" se lee bien, pero destapó un defecto de idempotencia: las líneas que
  un pedido heredó de su matriz en una pasada antigua no se borraban nunca
  (la poda las deja fuera a propósito) y las marcas de origen
  (`heredado_de_matriz`, `lote_heredado_de_pagina_anterior`,
  `lote_del_expediente`) no se recalculaban ("un `None` no pisa"): `0207`
  (LOTE 1) mostraba P-03/P-04 del LOTE 2. Ahora las marcas se recalculan en
  cada pasada y `podar_lineas_heredadas_obsoletas` borra las heredadas que la
  herencia ya no escribe. **La premisa del localizador era falsa**: abre las
  páginas de `0064` y de los Contratos de `0122`; lo que falla en `0122` es
  `pdfplumber` (tabla sin líneas horizontales → una fila con 41 códigos), sin
  pérdida de material porque el anejo trae el mismo cuadro limpio. Medido:
  246 → 10 páginas con filas que el localizador no abre; arregladas las 4
  que perdían material ("Mat." como marcador: carril de `6.21/28510.0041`;
  cuadros de balasto por debajo de la densidad mínima); quedan 6, ninguna
  con material que falte. **"LOTE 6: RAM
  NORTE"** sí se detectaba, pero sin su primera columna: el borde de la
  tabla vecina arrastra el suyo al "imantar" líneas; segundo intento con
  `snap_x_tolerance` 1 solo para tablas descartadas (recupera exactamente esa
  en todo el corpus). Una celda con varios valores, uno por línea, ya no se
  lee como un número (600.200.201 en `6.21/28510.0152`); una regresión de la
  primera versión de esa regla (30 precios de `0108`-`0113` a 4-5 € en F14)
  se corrigió y verificó en la misma sesión. **`6.22/28510.0058` y otros
  lotes sin importe**: el Contrato propio lo declara ("El importe del
  contrato es de: Base imponible X") y ahora rellena los huecos, nunca pisa
  (lotes propios sin importe de adjudicación 40 → 17; en 4 lotes sin baja
  declarada, con los dos importes ya distintos, la baja se deriva de ellos
  como en otros 83 lotes). Pendiente de decisión del cliente: las 2.161
  líneas de lotes no declarados (categoría del Resumen, y si ~65 materiales
  que solo están ahí deben verse en el Excel). Pendiente sin tocar:
  `trazas_origen` duplica las trazas de lote en cada pasada (7.848 filas de
  `baja_declarada` para 440 distintas), contra el invariante 9.
  **Sin terminar al cerrar**: la pasada final F16 terminó pero no se revisó,
  y el Excel final y su comparación de materiales distintos no se hicieron
  (última medida, F13: 5.519 → 5.463, sin material perdido de la base de
  datos).
- **Expedientes de 2026 del departamento 28510 que faltaban (sesión
  2026-09-15, `docs/sesion-2026-09-15-expedientes-2026-presidencia.md`).**
  No era el órgano ni el estado de tramitación: los 15 `6.26/28510.*` estaban
  descubiertos (Presidencia y Consejo, estados RES/ADJ/EV/PUB). Seis tenían
  `sin_publicar` por búsquedas del 2026-09-07 anteriores al arreglo de límite
  de tasa, y el ciclo nunca vuelve a buscar un `sin_publicar`. Al buscarlos de
  nuevo aparecieron los seis: +57 líneas (5 de ellos con líneas). Los 5
  pedidos de EPIs de Presidencia (`0047`/`0048`/`0049`/`0068`/`0073`) siguen
  sin líneas: su matriz (departamento 04110) no aparece en la Plataforma. La
  columna "Código de expediente" del Excel solo se rellena si el expediente
  cruza con el Excel de códigos; el código siempre está en "Nº de expediente
  (documento)". **Segunda parte, misma sesión:** reintentados los 34
  `sin_publicar` cuya última búsqueda era anterior al arreglo (el encargo
  decía 43; ningún dato del sistema da esa cifra): aparecen 22, los 22 del
  28510 que están en la sindicación, con 710 líneas (515 en el Excel); los
  12 restantes, 11 de ellos del conjunto de prueba, son negativos
  confirmados. Y
  **`sin_publicar` deja de ser definitivo**: `sin_publicar_en` y
  `sin_publicar_version_busqueda` (migración 0031,
  `VERSION_LOGICA_BUSQUEDA`) distinguen el negativo confirmado con la
  búsqueda corregida del que viene de antes. El ciclo semanal vuelve a
  buscar los no confirmados en seguida y los confirmados cada 14 días
  (`SIN_PUBLICAR_REINTENTO_DIAS`, tope `SIN_PUBLICAR_REINTENTOS_POR_CICLO`).
  Un fallo transitorio al reintentar ya no lo pasa a `fallido`.
- **Criterio de descubrimiento del cliente, y cuadros de precios sin código
  (sesión 2026-09-15, tercera parte,
  `docs/sesion-2026-09-15-criterio-28510-y-cuadros-sin-codigo.md`).** El
  descubrimiento por sindicación ya no mira el órgano de contratación ni la
  forma exacta del código: entra todo expediente cuyo código contenga los
  dígitos de `SINDICACION_DEPARTAMENTOS_ADIF` (28510), en cualquier estado
  (decisión del cliente). Lo que el filtro anterior habría perdido se anota en
  `codigos_criterio_ampliado` de cada periodo. De los 8 expedientes que
  entraron sin líneas en la segunda parte, 6 eran un fallo de extracción: un
  cuadro de uno o pocos artículos sin código de precio ni matrícula se
  descartaba entero como tabla espuria (sección 5, etapa 4). Los otros dos
  son `3.24/28510.0126` (el pliego técnico solo da el presupuesto total:
  límite de origen) y `6.17/28510.0056` (anejos escaneados, sección 15).
  Aceptar esos cuadros (etapas 3 y 4, sección 5), medido antes de desplegar
  sobre todo el corpus, recupera 43 tablas en 18 expedientes, 16 de ellos
  sin ninguna línea, y ninguna tabla que no sea un cuadro de precios. Excel
  15.067 → 15.308 filas, expedientes con filas 253 → 269, materiales
  distintos 5.887 → 6.119, 0 perdidos. **Sin terminar al cerrar:** la
  medición del criterio ampliado exige releer los 26 meses de sindicación (~6
  h a la velocidad de descarga de la Plataforma); leídos 2 (202609 y
  202608), 0 expedientes nuevos; los otros 24 quedaron en la cola, un
  trabajo por mes.
- **Unidades de medida que no lo son, cobertura de 2026 y restos de
  auditoría (sesión 2026-09-15, cuarta parte,
  `docs/sesion-2026-09-15-unidades-y-cobertura-2026.md`).** De 40 valores
  distintos de unidad, ya sin planos ni normas, no eran unidades "Fibra
  monomodo" (51 líneas, `6.24/28510.0125`: la caché 298 mapeaba
  "CARACTERÍSTICAS" como unidad; corregida, junto con la 98, "E.T."),
  "Precio mensual" y "ud ud ud" (restos de pasadas antiguas) y "UNIDAD" (la
  cabecera repetida de `4.26/28510.0031`). **Validación nueva**
  (`app.extraccion.unidad_medida.es_unidad_conocida`): una unidad que no es
  de la lista, o una compuesta de ellas ("t x km", "€/Ton*mes"), se descarta
  y la línea va a revisión; también en el relleno desde el maestro de SAP.
  Una fila que repite la cabecera en mitad de la tabla ya no es una línea, y
  una partida alzada con un signo del sello lateral delante ("∅") se
  reconoce (`6.25/28510.0257` P-22): 0 líneas sin descripción, auditoría con
  un solo error (las 11 parejas conocidas). Cobertura de 2026: 24
  expedientes `*.26/28510.*` (21 en la sindicación, 3 solo en el SAP), 14 con
  líneas, 343 filas en el Excel; el "3" del cliente es la columna "Código de
  expediente", que solo se rellena si cruza con el Excel de códigos.
  Pendiente: `4.26/28510.0005` y `6.26/28510.0004` sin líneas, sin
  investigar. El contenedor `api` no tiene proveedor de modelo: una
  extracción lanzada desde él falla en las tablas sin cabecera. **Quinta
  parte:** la unidad se guarda sin el prefijo de la base del precio ("€/UD"
  → "UD", 4.084 líneas de `6.21/28510.0108`-`0113`) ni la llamada de nota
  ("dm3**" → "dm3"), decisión del cliente (`limpiar_unidad`). "PERSONALIZADO"
  no existe como unidad en el sistema. `PA` (66 líneas) y `P` (3) pendientes
  de decisión del cliente. El orden del catálogo/Excel no es total (el
  desempate por `orden_aparicion` se repite entre documentos): falta
  `LineaCatalogo.id` como último desempate.
- **Descubrimiento por búsqueda directa en la Plataforma (sesión 2026-09-16,
  `docs/sesion-2026-09-16-descubrimiento-por-busqueda.md`).** No faltaba
  ningún expediente de 2026: los 15 `6.26/28510.*` que publica la Plataforma
  son los 15 que tenemos, `0016`/`0074`/`0004` incluidos y con documentos
  descargados. El "solo aparecen tres en el Excel" es la columna "Código de
  expediente", que solo se rellena si el expediente cruza con el Excel de
  códigos (10 expedientes con líneas, 274 filas; 3 con esa columna).
  **Lo nuevo**: la sindicación cubre lo que ha tenido un evento de
  contratación en el mes — en la práctica lo adjudicado — y deja fuera lo que
  sigue en licitación o pendiente. El buscador sí lo lista, y su campo "Nº de
  expediente" hace coincidencia **por subcadena** (`26/28510` devuelve los 21
  del departamento de una vez). `app.scraping.descubrimiento_busqueda` corre
  **dentro del ciclo de mantenimiento**, junto a la sindicación y antes del
  bucle de frescura, con `BUSQUEDA_FRAGMENTOS` (vacía = los departamentos de
  `SINDICACION_DEPARTAMENTOS_ADIF`, el criterio del cliente, válido para
  cualquier año) y **cada búsqueda y cada paso de página** por el mismo
  limitador que espacia las descargas (`esperar_turno_async`). Un
  `sin_publicar` que la búsqueda encuentra se reabre sin esperar plazo:
  es evidencia positiva. La pasada real con `28510` encontró **129
  expedientes que ni la sindicación ni el Excel de SAP conocían**
  (2013-2025), todavía sin descargar. **La guarda "los dígitos no pueden ir
  pegados a otros dígitos" es obligatoria** sobre los resultados del buscador
  (devolvía `PcPG/2026/828510`): extraída a `app.criterio_expediente`, una
  sola definición para las dos vías. **Además**: la matrícula con puntos de
  miles ("667.500.506") ya cuenta como fila de datos (`6.26/28510.0004` +1,
  `6.23/28510.0034` +21, `6.24/28510.0048` +26), y
  `frescura.documentos_sin_cambios` mira ya `VERSION_LOGICA_EXTRACCION` — sin
  eso, todo arreglo de la cascada marcaba como "posible duplicación" justo a
  los expedientes que acababa de recuperar.
- **Ciclo completo, vigentes con remanente, 2026 del SAP, unidades y
  duplicados (sesión 2026-09-16, noche,
  `docs/sesion-2026-09-16-noche-ciclo-vigentes-unidades.md`).** El espaciado
  entre peticiones a la Plataforma es ya `SCRAPING_SEPARACION_MINIMA_SEGUNDOS`
  (10 s en el worker). **Unidad de medida en forma única**
  (`normalizar_unidad`: "UD."/"UN"/"Ud." → `ud`, "T"/"Ton" → `t`,
  "Txkm"/"Ton*km" → `t·km`), con el valor tal como venía en
  `lineas_catalogo.unidad_medida_original` (migración 0032): de 32 valores
  distintos a 17; `PA`, `P` y `transporte` se quedan como están. **Los 11
  grupos duplicados del Excel son legítimos**: el propio documento repite
  texto y precio con códigos de precio distintos (`0051`/`0060`,
  `4.25/28510.0132`), y el Excel no lleva la columna de código de precio.
  **De los 13 expedientes de 2026 del SAP del cliente, 11 no están
  publicados en la Plataforma** (buscados uno a uno): dados de alta como
  `sin_publicar`, el ciclo los vuelve a buscar cada 14 días.
  **Ciclo completo** (1 h 47 min, 10 s entre peticiones): los 129
  expedientes del descubrimiento por búsqueda se encuentran y descargan
  todos; 34 aportan 1.110 líneas (644 filas del Excel); de los 95 sin
  líneas, 47 solo tienen documentos escaneados (anteriores a 2020: el límite
  de la sección 15 deja de ser un caso aislado). Dos defectos corregidos de
  paso: el objeto del contrato de un anuncio sin línea "Descripción" se comía
  media página y tumbaba la extracción (`nombre_proyecto` y
  `trazas_origen.valor_extraido` a texto, migración 0033), y una fila de
  totales con la etiqueta fuera de la columna de matrícula entraba como línea
  sin descripción ("21% IVA 7.350,00 €" leído como 217.350 €). Catálogo
  34.210 → 35.323 líneas; Excel 15.351 → 15.998 filas, 0 materiales
  perdidos, auditoría con el único error de los 11 duplicados legítimos.
  **Sin hacer:** el cruce con los 83 vigentes con remanente (el fichero no
  llegó a estar en `Ejemplo/Input/`).
- **Escaneados, código del material y pendientes antiguos (sesión
  2026-09-17, `docs/sesion-2026-09-17-escaneados-codigo-material.md`).**
  **Escaneados, solo análisis**: 140 documentos (5.298 páginas) en 113
  expedientes, casi todos 2016-2019; 60 son pliegos técnicos con ~1.800 filas
  de catálogo, todas de 67 expedientes que hoy no tienen ninguna línea (solo
  21 con baja legible). Piloto de lectura por imagen con `claude-haiku-4-5`
  sobre una página real: 21 filas, un dígito mal en una medida; ~6-11 $ en
  total, 2-3 sesiones; pendiente de decisión del cliente (sección 15).
  **Código del material 63,9 % → 94,7 %** (Excel 64,8 % → 93,6 %): las
  siglas de aparatos de vía nombran la pieza (sección 6), "TIPO DE TRAVIESA"
  es columna de tipo, y la respuesta cacheada del modelo ya no se reparte a
  descripciones que no nombran esa pieza ("X" → BALASTO estaba en 231 líneas
  de equipos Ethernet); el código se recalcula en cada pasada. **Trazas sin
  duplicar**: 36.912 → 2.106 (migración 0034, `app.extraccion.traza`),
  estables tras un reproceso completo. **Filas fundidas**: `6.24/28510.0208`
  separada (6 → 15); `6.21/28510.0152` p.114 sigue fundida (su columna de
  código es la de "CODIFICACIÓN DEL PRECIO", alias ya revertido una vez).
  Unidades (18) y los 11 duplicados legítimos, sin cambios. Excel 15.998 →
  16.007 filas, 0 materiales perdidos.
  **Continuación, decisión del cliente:** reconocimiento óptico implementado
  y lanzado (sección 15), matrícula de 8 cifras aceptada en todos los
  documentos, títulos "pliego de condiciones administrativas/generales" como
  pliego sin precios. Catálogo 35.332 → 37.660 líneas, expedientes con líneas
  306 → 361, Excel 16.007 → 18.260 filas, 0 materiales perdidos. Los 6
  expedientes que fallaron por saldo agotado, relanzados: completan, sin
  líneas (sin cuadro, o cuadro sin cantidad ni código en `6.18/28510.0071`;
  lectura mala en la tabla apaisada de `3.16/28510.0044`). Coste total real
  del reconocimiento ~12,5 $. Auditoría: solo los 11 duplicados legítimos.
  Después, aviso del cliente: 22 filas de resumen de presupuesto ("Suma",
  "IVA (21%)", "Presupuesto de Ejecución Material"...) entraban como líneas
  con la etiqueta en la descripción; ahora son pie de tabla por palabras de
  concepto (`app.catalogo._es_concepto_de_presupuesto`). Catálogo 37.638
  líneas, Excel 18.239 filas, materiales distintos 14.980 → 17.202 (la cifra
  9.848 → 12.003 dada antes estaba mal calculada), 0 materiales perdidos.

---

El registro histórico de hallazgos y decisiones de cada sesión vive en
`docs/`: `hallazgos-scraping.md`, `hallazgos-sindicacion.md`,
`hallazgos-extraccion.md`, `identidad-expediente.md`, `decisiones-cliente.md`,
`mantenimiento-automatico.md`, `decisiones.md`, `correccion-defectos-auditoria.md`,
`comparacion-corpus-sharepoint.md`, `auditoria-huerfanos-y-autorreferencia.md`,
`excel-cliente-correccion.md`, `diagnostico-caidas-dockerd.md`,
`tolerancia-reinicios-dockerd.md`, `estados-carga-web.md`,
`copias-de-seguridad.md`, `descubrimiento-inverso-matriz-pedidos.md`,
`sesion-2026-09-07-adjudicatario-revision-vocabulario.md`,
`sesion-2026-09-07-sap-ejecucion-cobertura.md`,
`analisis-corpus-467-expedientes.md`,
`sesion-2026-09-08-cobertura-sap-367.md`,
`sesion-2026-09-08-verificacion-excel-6599.md`,
`sesion-2026-09-08-herencia-lote-continuacion.md`,
`sesion-2026-09-08-auditoria-automatica.md`,
`sesion-2026-09-09-cambios-cliente-catalogo.md`,
`sesion-2026-09-09-auditoria-mapeo-documentos.md`,
`sesion-2026-09-09-reproceso-completo-y-bloques-2-3-4.md`,
`sesion-2026-09-10-maestro-materiales-real.md`,
`sesion-2026-09-12-defecto-mapeo-calidad-interfaz-rendimiento.md`,
`sesion-2026-09-12-huecos-determinismo-ingesta.md`,
`sesion-2026-09-14-revision-cliente-pliegos.md`,
`sesion-2026-09-15-verificacion-localizador-tablas.md`,
`sesion-2026-09-15-expedientes-2026-presidencia.md`,
`sesion-2026-09-15-criterio-28510-y-cuadros-sin-codigo.md`,
`sesion-2026-09-15-unidades-y-cobertura-2026.md`,
`sesion-2026-09-16-descubrimiento-por-busqueda.md`,
`sesion-2026-09-16-noche-ciclo-vigentes-unidades.md`,
`sesion-2026-09-17-escaneados-codigo-material.md`,
además de `analisis-corpus.md` y `auditoria-previa.md` ya existentes.
