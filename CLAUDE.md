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
| **Matrícula** | Código de 9 dígitos del artículo en ADIF. Presente solo en ~66% de las líneas. **No es clave.** |
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
| Importe de licitación | Anuncio PCSP: *Presupuesto base de licitación → Importe (sin impuestos)*. LC.27: tabla de presupuesto. |
| Importe adjudicado | Anuncio PCSP: *Importes de Adjudicación → Importe total ofertado (sin impuestos)*. |
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
   numérica. Reduce el trabajo antes de gastar nada.
4. **Extraer la tabla** con `pdfplumber` sobre esas páginas.
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
  amplía el vocabulario.
- **El cruce con el Excel de códigos no usa modelo.** Es búsqueda por clave exacta.
- **Caché por hash de documento.** Nunca se reprocesa lo mismo dos veces.

Efecto buscado: **el sistema llama menos al modelo cuantos más expedientes procesa.**

Si te ves escribiendo un prompt que pide "extrae los datos de este documento",
párate: has salido de la cascada.

**Modelo por defecto: `claude-haiku-4-5`**, no un modelo grande — traducir
una cabecera nunca vista es correspondencia de etiquetas, no una tarea que
se beneficie de razonamiento. Verificado contra la API real: mismo
comportamiento correcto que un modelo mayor, a una fracción del coste.
Detalle y cifras en `docs/hallazgos-extraccion.md` secciones 17.2-17.3.

---

## 7. Esquema del catálogo

Columnas del entregable y su origen:

| Columna | Origen | Modelo |
|---|---|---|
| Código interno | `Nº Interno` del Excel de códigos | No, cruce |
| Código de proyecto | `Nº Expediente` del Excel | No, cruce |
| Código matriz | `MATRIZ` del Excel | No, cruce |
| Nombre del proyecto | *Objeto del Contrato* del anuncio | No, etiqueta fija |
| Matrícula del material | Cuadro de precios | No |
| Descripción del material | Cuadro de precios | No |
| Código del material | Derivado de la descripción | Solo si no casa |
| Cantidad | Cuadro de precios | No |
| Precio unitario | Cuadro de precios | No |
| Lote | Cabecera de tabla o anuncio | No |
| Comentarios | Humano | No |

Añadir internamente, aunque no salgan al Excel: `codigo_precio`, `unidad_medida`,
`baja_lote`, `precio_adjudicado`, `documento_origen`, `pagina`, `fragmento`,
`confianza`, `estado_revision`.

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
   intercambiables.** Hoy API de Anthropic, mañana modelo autoalojado. Misma firma,
   mismo esquema de salida. Cambiar de una a otra es una variable de entorno.
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
suficientes, no ahora.

---

## 16. Pendiente de resolver

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
  sindicación".
- **`expedientes.aviso_sindicacion` existe en la API pero no se muestra
  todavía en la web** — pendiente menor de la sesión de criterios del
  cliente (`docs/decisiones-cliente.md` sección 26).
- **`6.24/28510.0116` no debe usarse como ejemplo de demo hasta
  confirmarlo con el cliente.** Discrepancia real entre dos documentos del
  mismo expediente: la Propuesta de Adjudicación declara una baja del
  47,87%, el Contrato firmado declara 46,50% (sobre 1.485.000 €, no es
  redondeo). El sistema usa el 46,50% del Contrato — probablemente correcto
  (es el acto más definitivo), pero CLAUDE.md no documenta explícitamente
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
- **Residuo menor sin tocar, mismo día**: 32 grupos (67 filas) de "mismo
  material, mismo precio, repetido" en expedientes de un solo lote —
  mecanismo B de `docs/hallazgos-extraccion.md` sección 30.2 (tabla técnica
  repetida entre ANEJO y CONTRATO), sin fundir porque son líneas sin
  matrícula y `_firma_material` exige matrícula. Y 2 líneas de
  `6.23/28510.0051` con `descripcion = ''` (matrícula presente, sin ninguna
  descripción capturada). Ambos en `docs/excel-cliente-correccion.md`.

---

El registro histórico de hallazgos y decisiones de cada sesión vive en
`docs/`: `hallazgos-scraping.md`, `hallazgos-sindicacion.md`,
`hallazgos-extraccion.md`, `identidad-expediente.md`, `decisiones-cliente.md`,
`mantenimiento-automatico.md`, `decisiones.md`, `correccion-defectos-auditoria.md`,
`comparacion-corpus-sharepoint.md`, `auditoria-huerfanos-y-autorreferencia.md`,
`excel-cliente-correccion.md`, `diagnostico-caidas-dockerd.md`,
además de `analisis-corpus.md` y `auditoria-previa.md` ya existentes.
