# ADIF — Catálogo de materiales y cálculo de baja

Contexto permanente del proyecto. Léelo entero antes de escribir código.
Si algo de este documento contradice lo que parece obvio, gana este documento.

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

---

## 3. Hallazgos del análisis del corpus (medidos, no supuestos)

Sobre 45 expedientes y 187 PDFs reales:

- **186 de los 187 documentos tienen capa de texto.** No hace falta OCR ni
  modelo multimodal para leerlos. La excepción, confirmada en la sesión de
  expedientes sin publicar (2026-09-03): `6.20/28510.0136_ANEJO_2.pdf`
  (100 páginas) es un PDF escaneado — cada página es una imagen a página
  completa, cero caracteres extraíbles con `pdfplumber` ni con `pypdf`. Barrido
  el corpus completo buscando el mismo síntoma: es el único caso, no un
  patrón. `app.extraccion.texto.es_documento_escaneado` lo detecta (umbral de
  caracteres, no cero exacto) para que el motivo de revisión lo diga
  explícitamente ("documento escaneado, sin capa de texto") en vez de
  confundirse con "no se extrajo ninguna línea de catálogo" — son
  diagnósticos distintos. Sigue sin implementarse OCR (CLAUDE.md sección 15):
  si aparecen más documentos escaneados, la vía es rasterizar la página y
  pasarla a un modelo multimodal, coherente con la arquitectura propuesta
  (Qwen) — no un OCR aparte.
- **Dos familias de documento de adjudicación:**
  - *Anuncio PCSP* (11 de 38): formulario estándar con etiquetas fijas.
  - *Propuesta LC.27* (27 de 38): plantilla propia de ADIF.
- **El cruce con el Excel de códigos es determinista al 100%.** Los 38 documentos
  contienen un código de expediente extraíble y todos cruzan: 29 como `Nº Expediente`,
  3 como `MATRIZ`, 6 requieren afinar el patrón pero el dato está.
- **Localizar la tabla de precios descarta el 83% de las páginas.** En la muestra,
  36 páginas candidatas de 215.
- **`pdfplumber` extrae los cuadros de precios limpiamente**, con descripciones
  multilínea unidas en su celda. El texto plano de esas páginas, en cambio, sale
  entrelazado e inservible.
- **Las cabeceras varían mucho: 11 variantes distintas en solo 7 documentos.**
  Entre 6 y 9 columnas, nombres alternativos (`CÓDIGO DEL ELEMENTO` / `CÓDIGO DEL
  PRECIO`, `PRECIO DE REFERENCIA` / `PRECIO UNITARIO DE REFERENCIA`), **columnas
  fantasma vacías que desplazan los índices**, y alguna cabecera corrompida por la
  extracción. Un parser por posición fija no funciona.
- **Las cabeceras se repiten:** una aparece 20 veces, otra 6, otra 4. Esto habilita
  la caché de la sección 6.
- **Los ficheros nombrados `CONTRATO.pdf` de tamaño pequeño suelen ser el formulario
  PCSP "Anuncio de formalización de contrato", no el contrato firmado.** El nombre
  que asigna el scraper no es fiable como tipo: manda el clasificador (sección 5,
  etapa 1), nunca el nombre del fichero.
- **Los ficheros `*_ANEJO_1.pdf` son en realidad el Pliego de Prescripciones
  Técnicas completo; el cuadro de precios es una sección interna.** Consecuencia
  para la extracción: la tabla se localiza por contenido, nunca por el tipo de
  documento ni por el nombre del fichero.
- **Existe una tercera plantilla de propuesta, `L9_CM.32-FE` (Dirección
  Técnica), distinta de LC.27, que hoy cae en `otro`.** Puede estar relacionada
  con la familia pendiente de la sección 16.

---

## 4. La baja: cómo funciona de verdad

**Hallazgo central del proyecto.** En 25 de 37 contratos revisados, el pliego
establece que el licitador oferta **una sola baja porcentual por lote, aplicable a
todos los precios unitarios**. En 19 de ellos el criterio de adjudicación es
explícitamente la mayor baja sobre precios unitarios.

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

---

## 5. La cascada de extracción

Cada documento cae por la primera etapa que lo resuelva. **No saltes etapas.**

1. **Clasificar la plantilla.** Anuncio PCSP, propuesta LC.27, contrato, anejo, pliego.
   Por marcadores de texto. Decide toda la ruta posterior.
2. **Campos de etiqueta fija.** Todo lo que sea formulario PCSP se extrae por etiqueta.
   Aquí sale la baja global de la familia PCSP entera, sin tablas y sin modelo.
3. **Localizar páginas candidatas.** Por presencia de cabecera de matrícula y densidad
   numérica. Reduce de 6 a 1 antes de gastar nada.
4. **Extraer la tabla** con `pdfplumber` sobre esas páginas.
5. **Mapear cabecera → esquema.** Única etapa donde interviene el modelo. Ver sección 6.
6. **Normalizar y derivar.** Ver secciones 7 y 8.

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
- **Worker** — consume la cola: descargar, extraer, recalcular.
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

---

## 12. Validación

- Comprobar que importe licitado, importe adjudicado y baja declarada cuadran entre sí.
- Lo que no cuadre **no se corrige solo: va a la cola de revisión**.
- Detectar el caso de precios unitarios (licitación = adjudicación) y no devolver 0%.
- Un sistema que sabe cuándo no sabe vale más en la demo que uno que acierta cinco de
  cinco. No escondas los casos dudosos.

---

## 13. Estructura del repositorio

```
/web        Next.js. Cliente ligero. Desplegable por separado.
/engine     API, worker, extracción, scraping. Con su Dockerfile.
/docs       Este fichero y decisiones tomadas.
docker-compose.yml
```

La dirección de la API en la web es **una variable de entorno**, para apuntar a
local, a una instancia de pruebas o al servidor soberano sin tocar código.

**No metas los 187 PDFs en el repo.** Deja un conjunto fijo de prueba: dos anuncios
PCSP, dos propuestas LC.27, dos anejos con cabeceras distintas. Trabaja siempre
contra esos.

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
ejecución programada, paralelismo masivo, y todo lo estético que no sea legible en
una pantalla compartida.

**OCR o modelo multimodal para documentos escaneados.** Con el corpus real
actual, 186 de 187 documentos tienen capa de texto (CLAUDE.md sección 3);
construir un pipeline de OCR para el único caso conocido no está
justificado. Si en el futuro aparecen más documentos escaneados con volumen
propio, la vía prevista es rasterizar la página y pasarla a un modelo
multimodal (coherente con la arquitectura propuesta, Qwen), no un OCR
tradicional aparte — pero eso es una decisión para cuando haya casos
suficientes, no ahora.

---

## 16. Pendiente de resolver

- **Los 12 contratos que no siguen el modelo de baja única por lote.** Puede haber una
  segunda familia con precio ofertado por línea. Hay que mirarlos antes de dar el
  motor por completo. **Está sin verificar: no lo des por supuesto.**
- **Confirmar con el cliente** si el `Precio unitario` del catálogo de ejemplo es el
  licitado o el adjudicado.
- **Los 6 documentos cuyo código de expediente no captura el patrón actual.** El dato
  está en el documento; es afinar la expresión regular.
- **Ruido heredado en el Excel de ejemplo** (hecho con Copilot): matrícula repetida con
  descripción vacía, `BRIDA` alternando con `BRIDAS`. Decidir si se arranca limpio o
  el sistema normaliza lo heredado.
- **Comprobar si la plantilla `L9_CM.32-FE` sigue el modelo de baja única por lote
  o es la segunda familia con precio ofertado por línea** (ver el primer punto de
  esta sección). Sin verificar todavía.
- **Sindicación como fuente secundaria.** Queda como posible fuente secundaria
  de metadatos y descarga oportunista cuando exista `GeneralDocument` (sección
  17.1), siempre con la navegación como respaldo obligatorio, nunca como
  sustituto. No está previsto para la demo.
- **Patrón de Propuesta LC.27 multi-lote, sin verificar contra un documento
  real** (sección 19): el corpus completo de 45 expedientes no trae ninguna
  LC.27 con más de un lote, solo la Resolución de `6.25/28510.0027`. El
  extractor de `app/extraccion/lotes.py` asume la misma redacción "En el
  LOTE N..." para las dos plantillas por analogía, no por evidencia — si
  aparece una LC.27 multi-lote real, revisar ese módulo antes de confiar en
  el resultado.
- **Resuelto (sección 21, sesión de corrección de identidad):** los 8
  expedientes con `codigo_expediente` etiquetado con el código de su MATRIZ
  se renombran solos, en la etapa de extracción, al valor real que declara
  su propio Anuncio PCSP.
- **Resuelto en la práctica, sin verificar la causa raíz (sección 22, sesión
  de expedientes sin publicar):** de las 8 matrices reales que este corpus
  necesita (5 en `2.18/04703`, 3 en `2.24/04110`) más los 6 expedientes de la
  sección 3 sin documentos, **los 14 códigos se comprobaron a mano en la
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
- **Nuevo, sin resolver (sección 22):** `6.24/28510.0025` y `6.24/28510.0193`
  tienen exactamente 2 documentos (`anuncio_pcsp` + `contrato`), sin ningún
  `anejo` ni `pliego` — mismo síntoma estructural que los pedidos derivados
  de acuerdo marco (sección 3), pero estos dos usan código `6.24/28510.0NNN`
  normal, no el formato de MATRIZ (`2.18/...`, `2.24/...`): no está claro si
  son pedidos derivados con una matriz todavía no identificada, o contratos
  reales cuyo anejo de precios nunca se adjuntó a la Plataforma. Sin
  investigar caso a caso — fuera de alcance de la sesión de expedientes sin
  publicar, que se centró en los 14 códigos ya confirmados.
- **Resuelto en la sesión de identidad de lote (sección 27):** `6.24/28510.0088`
  y `6.23/28510.0129` (y 13 expedientes multi-lote más, no solo estos dos) no
  son pedidos de un solo lote — son licitaciones de varios lotes de las que
  solo teníamos documentos de una parte. El código propio de cada lote
  (`6.24/28510.0113`, `6.23/28510.0143`...) se modela ahora como
  `lotes.codigo_expediente_lote`, atributo del lote, no como fila de
  `Expediente` nueva — decisión explícita del cliente (sección 27): la
  identidad derivada de la partición en lotes no justifica la complejidad de
  expedientes nuevos. Lo que seguía pendiente aquí (cobertura parcial nunca
  mostrada como completado) queda cerrado.
- **Nuevo, sin resolver (sesión de identidad de lote, sección 27):**
  `6.23/28510.0051` tiene, con diferencia, el catálogo más grande del corpus
  (1.080 líneas, frente a las ~10-50 de un expediente típico) repartido en
  617 páginas de documentos. Reprocesarlo en un proceso recién arrancado
  tarda ~110 s, dentro de lo razonable — pero reprocesarlo como el N-ésimo
  expediente dentro de un mismo proceso Python de vida larga (el propio
  worker, o un script que encadena varios expedientes) se vuelve
  progresivamente más lento hasta parecer colgado (más de 15 minutos sin
  avanzar en un caso observado), sin ninguna excepción ni error visible —
  activo en CPU todo el tiempo, nunca bloqueado. Verificado que no es un
  bucle infinito de este código (el mismo expediente, en un proceso nuevo,
  siempre termina en menos de 2 minutos); sin verificar si la causa es una
  fuga de memoria/recursos de `pdfplumber` acumulada entre documentos
  grandes sucesivos, u otra cosa — no se ha investigado más porque es un
  problema de rendimiento del pipeline ya existente (`procesar_anejo`,
  `lote_tabla.asociar_lote_tabla`), no de esta sesión. Mitigación de hecho
  que sí funcionó: procesar expedientes grandes en procesos aislados en vez
  de un bucle largo. Candidato para una sesión de rendimiento aparte si
  aparecen más expedientes de este tamaño.

---

## 17. Hallazgos de scraping (cierre del punto 2 del orden de trabajo)

Verificado en vivo, headless, contra la Plataforma real y dentro del contenedor
Linux del worker (no solo en un script suelto). Ver `engine/app/scraping/pcsp.py`.

- **El WAF distingue por tipo de URL, no rechaza toda descarga fuera del
  navegador sin más.** Matizado en la sesión de sindicación (2026-09-02, ver
  sección 17.1): las URLs capturadas del evento `download` dentro de la sesión
  de navegador (estado JSF) sí requieren el motor de render — un cliente HTTP
  aparte, incluso replicando cabeceras de un navegador real, es rechazado. Pero
  las URLs `docAccCmpnt` con `DocumentIdParam` que trae el XML de sindicación
  se descargaron con cliente HTTP plano (`curl -k`, sin cookies ni cabeceras de
  navegador) sin problema: dos URIs reales probadas, HTTP 200 y PDF correcto en
  ambas. Pendiente: no se ha probado con volumen, así que no se descarta
  limitación de tasa. **La conclusión práctica se mantiene: la automatización
  de navegador sigue siendo necesaria, porque el problema no es la descarga —
  esa parte puede que ya esté resuelta para las URLs de sindicación — sino el
  descubrimiento del documento, y la sindicación no lo cubre de forma fiable
  (ver sección 17.1).**
- Los identificadores JSF del formulario de búsqueda y los selectores
  `GetDocumentByIdServlet` y `docAccCmpnt` siguen siendo válidos a fecha de esta
  sesión (2026-09-02).
- El camino de abrir la tarjeta "Licitaciones" antes de que aparezca el input de
  búsqueda se toma siempre en headless, no es un caso excepcional.
- La ruta de almacenamiento de cada documento va por hash de contenido, nunca
  por índice (`CONTRATO_1.pdf`, `CONTRATO_2.pdf`...), para que reprocesar un
  expediente y encontrar contenido distinto en el mismo hueco no pise el fichero
  que una fila de `documentos` anterior sigue referenciando por su hash.
- **`dockerd` no arranca solo en WSL**, y no solo al abrir la distro: durante
  esta misma sesión el contenedor del stack completo se cayó dos veces sin
  intervención (`docker compose ps` mostraba los cuatro servicios "Exited" y
  `dockerd` con un `Active: ... since` de segundos antes) con apenas minutos de
  diferencia. Los volúmenes con nombre (Postgres, documentos) sobreviven a esos
  reinicios; los trabajos de la cola que estaban `en_proceso` en ese momento se
  quedan huérfanos (bloqueados por un contenedor que ya no existe) y no se
  vuelven a recoger solos — hay que resetear su `estado` a `pendiente` a mano.
  Antes de dar por caído el worker, comprobar siempre `systemctl status docker`
  en la distro.
- **Un mismo procedimiento puede tener dos documentos de adjudicación válidos
  a la vez**: la Propuesta de Adjudicación (plantilla LC.27, firma el
  Presidente de la Mesa de Contratación) y, más tarde, la Resolución de
  Adjudicación (firma el órgano de contratación). Verificado con el
  expediente `6.24/28510.0008`: la Resolución cita explícitamente a la
  Propuesta ("de acuerdo con la Propuesta... de 29 de mayo de 2024") y ambas
  declaran los mismos importes y la misma baja (54,00% en este caso). **El
  motor debe tratarlas como el mismo hecho, no como datos en conflicto, y
  preferir la Resolución cuando existan las dos** — es el acto posterior y
  definitivo del mismo procedimiento.
- **Pendiente: recuperación de trabajos huérfanos.** Hoy un trabajo puede
  quedarse en `en_proceso` bloqueado por un worker que ya no existe (contenedor
  caído, `dockerd` reiniciado a mitad de ejecución — ver más arriba) y nada lo
  recoge de nuevo: `tomar_siguiente_trabajo` solo mira `estado = pendiente`, así
  que ese trabajo se pierde hasta que alguien lo resetea a mano. Solución
  prevista, sin implementar todavía: usar `bloqueado_en` (ya existe en el
  modelo) como marca de tiempo de bloqueo, y que el worker, antes de pedir un
  trabajo nuevo, reclame como `pendiente` cualquier trabajo `en_proceso` cuyo
  `bloqueado_en` supere un umbral razonable (p. ej. varias veces el timeout de
  navegación del scraping), respetando `intentos`/`max_intentos` igual que un
  fallo normal.

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
  dominante en el corpus de ADIF (sección 3). **Consecuencia: la sindicación
  no puede ser la fuente principal de documentos.**
- **La Propuesta LC.27 y el Anuncio PCSP de adjudicación no aparecieron nunca**
  en la muestra. Cuando hay algo de la fase de adjudicación, es el contrato
  (`GeneralDocument`, ver primer punto), y solo a veces — ausente en
  `6.24/28510.0103` y en `6.24/28510.0088` (este último aún en fase `PUB` en
  los meses descargados).
- **La MATRIZ no existe como campo estructurado.** Se buscó
  `FrameworkAgreement`/`AcuerdoMarco` en el mes completo de agosto 2024: cero
  resultados. El cruce con la matriz sigue dependiendo de la extracción por
  etiqueta fija del Anuncio PCSP (sección 7), igual que hoy.
- **No hay campo de baja porcentual en el XML.** Y lo confirma desde una
  fuente independiente el hallazgo central de la sección 4: en
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

## 17.2 Validación del mapeo de cabecera contra la API real (sesión 2026-09-02)

Primera vez que la etapa 5 de la cascada (sección 6) se ejercita contra la
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
  precios reaparece varias veces en un documento, sección 3). Causa: `app/db.py`
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
  `en_proceso` hasta el umbral de la sección 17) en vez de marcar el trabajo
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

Con Haiku como modelo por defecto y el precio de arriba. La sección 6 fija
la regla que hace esta cuenta favorable: una llamada por firma de cabecera
nunca vista, nunca por documento ni por fila.

- **Peor caso (expediente nuevo, cachés en frío — el primer expediente que
  ve una plantilla, o el primero de la demo).** Un expediente típico trae 1
  a 3 documentos con cuadro de precios (anejo, y a veces un segundo anejo de
  características técnicas que repite el mismo cuadro, sección 3). Medido
  en este mismo expediente (`6.24/28510.0008`, con `ANEJO_1` y `ANEJO_3`):
  hasta 2-3 firmas de cabecera distintas por documento por las columnas
  fantasma y la corrupción de extracción. Cota razonable: **hasta 6-8
  llamadas al modelo por expediente** (mapeo de cabecera), más 1 llamada
  adicional por documento si trae filas huérfanas que agrupar (sección 6;
  camino no ejercitado todavía contra ningún fixture real, así que esa cota
  es sin verificar) y, rara vez, 1 llamada de `Código del material` si no
  casa nada del vocabulario controlado. **Techo defendible: ≈ 8-10 llamadas,
  ≈ 0,010-0,012 $ (≈ 0,010-0,011 €) por expediente** — sigue siendo una
  fracción de céntimo.
- **Régimen normal, caché caliente (a partir de los primeros expedientes
  procesados).** La sección 3 mide que las cabeceras se repiten mucho —
  "una aparece 20 veces, otra 6, otra 4" sobre solo 7 documentos — así que
  en cuanto el catálogo de firmas se estabiliza, un expediente nuevo casi
  siempre trae solo cabeceras ya vistas. **0 llamadas al modelo en el caso
  típico**, y 1 llamada (≈ 0,0012 $) en el expediente ocasional que
  introduce una variante de cabecera realmente nueva.
- **Efecto agregado.** Sobre un lote de, por ejemplo, 45 expedientes (el
  corpus de la sección 3), el coste de mapeo de cabecera no pasa de un
  puñado de céntimos en total, aunque cada uno se procesara con la caché en
  frío — y baja hacia cero según crece el catálogo, por diseño (sección 6:
  "el sistema llama menos al modelo cuantos más expedientes procesa"). El
  coste de esta etapa es irrelevante frente a cualquier otro coste del
  proyecto (cómputo, almacenamiento, scraping); no es la partida que hay
  que vigilar para controlar el gasto.

---

## 17.4 Estabilidad de `dockerd` en WSL: `vmIdleTimeout` (sesión 2026-09-02)

Ajuste de máquina, no de proyecto — documentado también en el `README.md`
raíz porque afecta a cualquiera que desarrolle en este equipo, no solo a
este repositorio.

- **Causa encontrada de las caídas de `dockerd` de la sección 17 (nueve en
  una sola sesión):** el `vmIdleTimeout` de WSL2 (por defecto 60000 ms) —
  la VM ligera de WSL se suspende sola sin ningún comando `wsl` ni proceso
  adjunto activo durante ese tiempo, y se lleva `dockerd` con ella. No es un
  fallo de Docker ni de la distro: es el comportamiento por defecto de WSL2
  documentado para ese ajuste.
- **Corregido con `vmIdleTimeout=-1` en `C:\Users\<usuario>\.wslconfig`**
  (fuera del repositorio, uno por máquina — ver README). Aplicado con
  `wsl --shutdown` seguido de un arranque limpio; **verificado que aguanta**
  dejando la VM sin ningún comando `wsl` activo durante 90 segundos seguidos
  (por encima del umbral por defecto de 60 s que causaba la caída) y
  comprobando después que `docker.service` seguía con el mismo `Active:
  ... since` de antes de la espera, sin reinicio.
- **Matizado en la sesión de catálogo (2026-09-02, sección 18): la caída
  volvió a pasar con `vmIdleTimeout=-1` ya aplicado**, varias veces en la
  misma sesión (`journalctl -u docker` mostró `Processing signal
  'terminated'` seguido de `Stopping docker.service` cada ~50-90 s mientras
  había comandos `docker compose` activos, con la distro WSL en estado
  `Running` todo el tiempo — no es el mismo síntoma que la suspensión de VM
  documentada arriba). Causa real sin confirmar todavía. Mitigación que
  funcionó en la práctica: mantener un `docker compose up` en primer plano
  (sin `-d`) corriendo en una shell de fondo mientras se opera el stack
  desde otra — reduce la frecuencia de caídas pero no las elimina del todo.
  **No dar por cerrado el hallazgo de `vmIdleTimeout` de arriba como
  solución completa.**

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
  la Resolución de Adjudicación (plantilla `L9_AF.01-FE`, sección 17) no
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
  hipotético, dado que la sección 17 documenta que a veces solo existe uno
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
- **Pendiente de la sección 16, sin resolver todavía:** si `Precio unitario`
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
  (sección 16): si aparece una LC.27 multi-lote con redacción distinta, ese
  módulo es el sitio a revisar.
- **Bug real encontrado y corregido al verificar contra el stack real:**
  varias tablas ambiguas del mismo documento (LOTE 2, 4, 5 y 6 del Pliego,
  ninguno declarado por la Resolución) comparten `codigo_precio` — el mismo
  cuadro de precios se repite por lote (sección 3). Sin lote que las
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
  (sección 9), y porque `/catalogo` y la exportación pagan directo sobre
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

**Resuelto en la sesión de corrección de identidad (sección 21):** la
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
de idempotencia (sección 9.9) pero no es clave externa de ninguna otra tabla
— `documentos.expediente_id`, `lotes.expediente_id`,
`lineas_catalogo.expediente_id` y `trabajos_cola.expediente_id` son todos por
`id`. Renombrar la fila no mueve ni un documento, ni un lote, ni una línea de
catálogo ya extraída.

**Por qué solo en la extracción, no en el scraping ni en un paso de
"ingesta" aparte**: la identidad real solo se conoce leyendo el texto del
Anuncio PCSP, y eso ya es exactamente la etapa 2 de la cascada (sección 5).
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
búsqueda. El sistema lo encajó exactamente como está diseñado (sección 9.10,
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

## 22. Expedientes sin publicar, y cierre de los 21 en revisión (sesión 2026-09-03)

Ataca los dos encargos de esta sesión en el orden pedido: primero marcar como
fuera de alcance los códigos que la Plataforma no publica, después atacar por
impacto las causas ya identificadas en `docs/analisis-corpus.md` que dejaban
21 expedientes en revisión. Verificado de punta a punta contra el stack real
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
inmediato de intentos): las 8 matrices de la sección 16 (`2.18/04703.0019`,
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
encuentran. Documentado como correlación (sección 16), no convertido en un
atajo que rechace un código nuevo por su prefijo sin intentarlo — con 14
casos no hay base para generalizar, y CLAUDE.md sección 9 prohíbe inventar
lo que no está verificado.

**Métricas del proyecto, desde ahora sobre 31, no sobre 45**: los 14 códigos
nunca fueron expedientes "reales" que el catálogo pudiera completar, así que
medir el progreso contra 45 escondía un techo que nunca iba a alcanzarse. La
sección "Medición final" más abajo da el detalle sobre los 31.

### 2. Los 21 en revisión: por impacto

Atacados en el orden que pedía el encargo — el que más expedientes
desbloquea primero.

**a) Otros formatos de código de precio (`app/extraccion/tabla.py`).**
`_CODIGO_PRECIO_RE` solo reconocía `P-NNN` (con guion ASCII o Unicode, sección
anterior de este documento). Verificado contra el corpus real completo antes
de tocar el regex — no adivinado —, los formatos reales que aparecen son:

| Formato | Ejemplo real | Expediente |
|---|---|---|
| `P` + dígitos, sin separador | `P1`, `P2` | `6.24/28510.0047` |
| `P` + dígitos, dos cifras | `P01`, `P02` | `6.24/28510.0187` |
| `PN` + dígitos | `PN001`..`PN018` | `6.24/28510.0180` |
| `PA-` + dígitos (partida alzada numerada) | `PA-01`, `PA-02` | `6.24/28510.0094` |
| `L` + dígitos + `-T` + dígitos (lote+tipo, no es semánticamente "código de precio" per sección 3, pero identifica la fila igual) | `L01-T01`..`L03-T19` | `6.24/28510.0094` |
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
que antes se perdían por completo — el test de esa sesión (CLAUDE.md sección
19) se actualiza para reflejar el comportamiento correcto, no el limitado.

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

**d) Documento escaneado (`app/extraccion/texto.py`).** Ver sección 3 y 15
de este documento. `es_documento_escaneado` (umbral de caracteres extraídos,
no cero exacto) marca `6.20/28510.0136_ANEJO_2.pdf` aparte, con un motivo
("documento escaneado, sin capa de texto") distinto de "no se extrajo
ninguna línea de catálogo" — antes ambos casos se confundían en el mismo
mensaje genérico. El documento se salta en la etapa 4 (nunca se abre con
`procesar_anejo`, que no encontraría nada) en vez de intentarlo igual.

### 3. Medición final: 31 expedientes reales

Reprocesados los 31 desde cero contra el stack real tras desplegar los
cuatro arreglos de arriba (imágenes reconstruidas, migración `0010`
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
ya documentado, y por diseño no adivina — CLAUDE.md sección 12):

- **7 expedientes, baja declarada no cuadra con la baja por importes**
  (`6.23/28510.0139`, `6.24/28510.0094`, `0117`, `0130`, `0203`,
  `6.25/28510.0019`, `0028`). Validación funcionando como está diseñada;
  varios de estos ya se señalaban en sesiones anteriores como posibles
  pedidos derivados de acuerdo marco con importes de la matriz mal cruzados,
  sin confirmar caso a caso.
- **3 expedientes, segunda familia de baja** (`6.23/28510.0018`, `0102`,
  `6.25/28510.0016`): fórmula `Ct = Oferta × Kt × Coeficiente de baja` por
  pedido, no una baja única de lote (hallazgo 5, sección "Pendiente de
  resolver"). No hay un valor que extraer, es un modelo de cálculo distinto
  — diseño pendiente, no un fallo de extracción.
- **2 expedientes, valores ilegibles marcados y descartados en vez de
  adivinados** (`6.23/28510.0042`: matrícula `"***"`, un placeholder
  explícito; `6.23/28510.0051`: dos valores distintos en la misma celda que
  no coinciden entre sí). `6.20/28510.0136` también trae 2 filas de este
  tipo (encabezados de sección dentro del cuadro de matrículas, sin dato
  real que extraer) más su documento escaneado, ya contado aparte.
- **1 expediente, ambigüedad de lote por diseño** (`6.25/28510.0027`: LOTE
  2, 4, 5 y 6 no están entre los lotes que adjudica la Resolución — CLAUDE.md
  sección 19, "sin lote centinela", las líneas quedan huérfanas en vez de
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
  precios nunca se adjuntó — ver sección 16.

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

## 23. Mantenimiento automático — bloque 1: ejecución incremental (sesión 2026-09-04)

Cambia el objetivo del sistema: de herramienta que se lanza a mano a sistema
que se mantiene solo. Este bloque es la base de los otros dos (descubrimiento
por sindicación y ejecución programada): sin ejecución incremental, un ciclo
periódico rehace el trabajo de todos los expedientes cada vez que corre, lo
que lo vuelve inviable en la práctica (CLAUDE.md sección 17: la Plataforma es
lenta y frágil; una extracción completa de ~40 expedientes reales tarda del
orden de 25 minutos, medido en esta misma sesión — ver más abajo).

### Modelo y decisión

Cuatro columnas nuevas en `expedientes` (migración `0011`):
`descargado_en`, `extraido_en`, `version_logica_extraccion`,
`huella_documentos`. Las estampa **`app.worker`** (`procesar_descargar_expediente`
/ `procesar_extraer_expediente`), nunca `app.scraping.job` ni
`app.extraccion.orquestador` — ninguno de los dos se toca en esta sesión
(encargo explícito: "no toques el motor de extracción"). Los dos manejadores
envuelven las funciones ya existentes sin modificarlas: llaman, y después (o
en un `finally`, para la extracción) estampan frescura solo si de verdad
hubo un intento real — ver docstrings de `app.mantenimiento.frescura.
debe_estampar_extraccion` para las dos excepciones (`esperando_matriz`,
`sin_publicar`, CLAUDE.md secciones 20 y 22).

`app.mantenimiento.frescura` (puro, sin I/O salvo los dos `estampar_*` con
`db.commit()`) decide:

- **`debe_descargar(expediente, documentos)`**: `True` solo si el expediente
  no tiene ningún documento. Deliberadamente **sin** parámetro `forzar`: el
  punto 4 del encargo ("lo necesito yo para desarrollo") es casi siempre
  forzar la RE-EXTRACCIÓN tras un cambio de código, no volver a golpear la
  Plataforma real para un expediente que ya tiene sus documentos íntegros —
  forzar eso contradiría el propio punto 2 del encargo ("cada descarga
  evitada cuenta"). Forzar una redescarga real sigue disponible a mano, sin
  tocar nada, con el endpoint ya existente `POST /expedientes/{id}/descargar`.
- **`debe_extraer(expediente, documentos, forzar)`**: `True` si `forzar`, si
  `extraido_en` es `None` (nunca se extrajo, o se quedó `esperando_matriz` —
  ver arriba, así un pedido derivado de acuerdo marco se reintenta solo en
  cada ciclo hasta que su matriz esté lista, sin regla aparte), si
  `version_logica_extraccion` no coincide con la constante vigente
  (`VERSION_LOGICA_EXTRACCION`, que un desarrollador sube a mano cuando un
  cambio en `app.extraccion.*` deba forzar reproceso general), o si
  `huella_documentos` (hash del conjunto de `Documento.hash`, sección 17:
  la ruta de almacenamiento ya va por hash de contenido) no coincide con la
  huella actual. Deliberadamente **no** mira si el expediente tiene
  documentos: un pedido derivado sin ningún documento propio también
  necesita que se intente su extracción — es su único camino para cruzar
  con el Excel de códigos y heredar de su matriz (secciones 3 y 20).

### El ciclo como trabajo de la cola, no como script

`app.mantenimiento.ciclo.ejecutar_ciclo_mantenimiento` es un tipo de trabajo
más (`mantenimiento_ciclo`, CLAUDE.md sección 10: "no un script suelto"),
encolable por `POST /mantenimiento/ejecutar` (payload opcional `{"forzar":
bool, "forzar_expedientes": [id, ...]}`). Por cada expediente (excepto
`sin_publicar`, fuera de alcance por diseño desde la sección 22) decide y
**encola** `descargar_expediente`/`extraer_expediente` con la misma
`encolar_trabajo` de siempre — y después **drena la cola de forma síncrona**
(`app.queue.ejecutar_trabajo`, extraído de `app.worker` a un despachador
genérico parametrizado por una tabla de manejadores, para que el worker y el
drenaje del ciclo compartan una sola implementación) hasta vaciarla. El
drenaje recoge también la extracción que `app.scraping.job` encadena solo al
terminar una descarga con éxito, así que el bucle de decisión nunca la
encola por duplicado: si un expediente no tenía documentos, su extracción se
deja a la cadena existente en vez de repetirla (comentario en
`ejecutar_ciclo_mantenimiento`). `tomar_siguiente_trabajo` gana un parámetro
`excluir_tipos` para que este drenaje nunca se recoja a sí mismo (evita
recursión); el bucle normal del worker no lo pasa, que es como llegan a
ejecutarse los ciclos programados del bloque 3.

### Verificación contra el stack real (dos ejecuciones seguidas)

Migración `0011` aplicada sobre la base de datos real de desarrollo (53
expedientes acumulados de sesiones anteriores, 14 de ellos ya `sin_publicar`
— más de los 45/31 del corpus fijo de `docs/analisis-corpus.md` porque esta
base lleva varias sesiones de pruebas manuales encima; no se ha limpiado,
no es el objeto de esta sesión). Con las cuatro columnas nuevas a `NULL` en
las 53 filas, dos ejecuciones seguidas de `POST /mantenimiento/ejecutar`:

| | 1ª ejecución | 2ª ejecución |
|---|---:|---:|
| Duración de pared (creación del trabajo → `completado`) | **1567 s (~26 min)** | **3,5 s** |
| Duración interna del ciclo (`resultado.duracion_segundos`) | 1531,7 s | **0,005 s** |
| Expedientes evaluados | 39 | 38 |
| Descargas lanzadas | 1 | 0 |
| Extracciones lanzadas | 38 | 0 |
| Saltados (descarga / extracción) | 0 / 0 | 38 / 38 |
| Trabajos drenados | 39 | 0 |

La 1ª ejecución hizo el trabajo real: reextrajo los 38 expedientes con
documentos (estableciendo su huella y versión por primera vez) e intentó
descargar el único expediente sin documentos que no estaba ya marcado
`sin_publicar` — el intento falló (`ExpedienteNoPublicadoError`, sección 22:
no encontrado en la Plataforma por ninguna variante de búsqueda) y lo dejó
`sin_publicar`, sin encadenar ninguna extracción (coherente:
`app.scraping.job` solo encadena tras una descarga con éxito) — por eso
`trabajos_drenados` es 39 y no 40, y por eso la 2ª ejecución evalúa 38
expedientes, no 39 (ese ya queda excluido por estar `sin_publicar`). La 2ª
ejecución, con las cuatro columnas ya estampadas y sin ningún documento ni
versión cambiados, no encoló nada: terminó en milisegundos de trabajo real,
con los ~3,5 s de pared explicados casi enteros por el intervalo de sondeo
del worker (`WORKER_POLL_INTERVAL_SECONDS=3`), no por trabajo hecho.
Verificado también que los 199 tests (176 anteriores + 23 de este bloque)
pasan igual dentro del contenedor `api`, no solo en local.

### Fixtures de regresión

`engine/tests/mantenimiento/test_frescura.py` (17 casos: huella estable
frente al orden, cambia si cambia el conjunto de documentos, las cuatro
ramas de `debe_extraer`, `debe_descargar` sin y con documentos,
`debe_estampar_extraccion` en los tres estados terminales y en las dos
excepciones, los dos `estampar_*`) y
`engine/tests/mantenimiento/test_ciclo.py` (5 casos, con manejadores falsos
— sin scraping ni modelo reales, igual que el resto de esta cascada: la
extracción encadenada por una descarga se drena sin duplicarse, un
expediente al día no lanza nada, `forzar` global reprocesa aunque todo
coincida, `sin_publicar` queda fuera del ciclo, un segundo trabajo de ciclo
pendiente no se recoge a sí mismo). `tests/test_queue.py` gana 3 casos para
`excluir_tipos` y el despachador genérico `ejecutar_trabajo`. Ningún PDF
nuevo — este bloque no toca la cascada de extracción, solo decide cuándo
llamarla.

---

## 24. Mantenimiento automático — bloque 2: descubrimiento por sindicación (sesión 2026-09-04)

Cierra el segundo de los tres bloques de la sesión de mantenimiento
automático (sección 23 es el bloque 1, base de este). Hoy los expedientes
salían solo del Excel de códigos, mantenido a mano; este bloque los
descubre solo, por la vía de sindicación que CLAUDE.md sección 17.1 ya
había descartado como fuente de documentos pero dejaba abierta como
fuente de descubrimiento.

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
6.24/28510.0103 (el pedido derivado de la sección 20) contra sus entradas
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
  scraping, mismo patrón que la sección 17** ("el WAF distingue por tipo de
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
  encadenados" (CLAUDE.md sección 17.1) significa que el propio ZIP ya trae
  todas las páginas de la cadena (link rel="next" apunta a otro .atom
  del mismo ZIP): no hace falta ninguna llamada de red adicional para seguir
  la cadena.
- **descubrimiento.py** — filtra (órgano contiene "adif", departamento en
  la lista configurada), deduplica por codigo_expediente quedándose con
  la entrada más reciente por updated (CLAUDE.md sección 17.1: "un mismo
  expediente puede aparecer varias veces"), da de alta los expedientes
  nuevos (con el codigo_expediente real, el mismo que usa todo lo demás
  del sistema — es el mismo cbc:ContractFolderID que ya usan los 45 del
  corpus) y guarda una instantánea en sindicacion_expedientes (tabla
  nueva, migración 0012) — **nunca escribe encima de expedientes/
  lotes**, es una fuente independiente. Detecta cambio de estado
  (ContractFolderStatusCode: PUB→ADJ→RES...) en un expediente que
  YA tenía documentos y, solo en ese caso, encola su descarga él mismo — es
  la única señal de "novedad" que el bloque 1 no tenía por sí solo (un
  expediente con documentos nunca se redescarga solo, sección 23). Nunca
  regresa a un dato de sindicación más viejo que el ya guardado (relevante
  si algún día se reprocesa un periodo desde cero).
- **contraste.py** — bloque 2, punto 4: compara
  Expediente.importe_licitacion/importe_adjudicacion (lo que extrajo la
  cascada de los PDF, siempre "sin impuestos", CLAUDE.md sección 4) contra
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
  verificada en CLAUDE.md sección 17.1): en ProcurementProject/
  BudgetAmount, TaxExclusiveAmount es sin impuestos y TotalAmount con
  impuestos; en TenderResult/AwardedTenderedProject/LegalMonetaryTotal,
  TaxExclusiveAmount sigue sin impuestos pero el importe con impuestos es
  PayableAmount, campo distinto. Sin ambigüedad real en ninguno de los
  casos verificados esta sesión.
- **Multi-TenderResult sin verificar contra un expediente multi-lote real
  con más de una adjudicación** (igual que la sección 16 deja sin verificar
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
   recuperación de trabajo huérfano (CLAUDE.md sección 17, "pendiente"):
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

---

## 25. Mantenimiento automático — bloque 3: ejecución programada (sesión 2026-09-04)

Cierra la sesión de mantenimiento automático (secciones 23 y 24 son los
bloques 1 y 2, base de este). El ciclo completo — descubrir, descargar lo
que falte, extraer lo que falte — ya existía como trabajo de la cola
(`mantenimiento_ciclo`); este bloque lo dispara solo, sin intervención,
respetando CLAUDE.md sección 10 ("cuatro procesos, ni uno más").

### Dónde vive el planificador: dentro del worker que ya existe

`app.mantenimiento.programacion.verificar_y_lanzar_ciclo_programado` se
llama en cada vuelta de `app.worker.bucle_principal` (cada
`WORKER_POLL_INTERVAL_SECONDS`, unos segundos) — no hay un quinto proceso
"scheduler", ni un cron del sistema operativo, ni Redis. Es una comprobación
barata (dos `SELECT` contra `trabajos_cola`, nada de red ni de Playwright
en la propia comprobación):

1. Si ya hay un trabajo `mantenimiento_ciclo` `pendiente` o `en_proceso`
   (programado **o disparado a mano**, da igual el origen) no se lanza
   otro — "sin solaparse consigo mismo" (punto 2) sale gratis de la misma
   cola que ya existía, sin bloqueo nuevo.
2. Si no, se compara `ahora` contra `última_ejecución.created_at +
   MANTENIMIENTO_INTERVALO_SEGUNDOS` (semanal por defecto, cualquier
   trabajo `mantenimiento_ciclo` cuenta como "última ejecución" para este
   cálculo, sea programado o manual). Si toca, se encola uno nuevo con
   `payload.disparado_por = "programado"` — el histórico (punto 4)
   distingue así por qué corrió cada ejecución.

**El histórico es la propia `trabajos_cola`, sin tabla nueva.** CLAUDE.md
sección 10 ya la describe como "consultable con SQL para la pantalla de
seguimiento" — duplicar esa información en una tabla aparte solo la
desincronizaría. `GET /mantenimiento/historial` la expone tal cual, más
reciente primero; `GET /mantenimiento/estado` añade lo calculado (próxima
ejecución, si hay una en curso) que no está en ninguna fila por sí sola.

**Límite conocido, no un descuido**: con un único proceso `worker`
(arquitectura de cuatro procesos de la sección 10), la comprobación no
compite consigo misma. Si algún día hubiera varias réplicas del worker, dos
podrían decidir lanzar en la misma vuelta antes de que ninguna llegue a
insertar — no se ha construido un bloqueo distribuido para un caso que la
arquitectura actual no tiene.

### Web: `/mantenimiento`

Página nueva (`web/app/mantenimiento/`), enlazada en la barra de
navegación. Muestra la frecuencia configurada, cuándo fue la última
ejecución (y quién la disparó), si hay una en curso ahora mismo, cuándo
tocaría la próxima, un resumen de lo que encontró la última ejecución
(nuevos, descargas, extracciones, y el resumen de sindicación si lo trae) y
el botón "Lanzar ciclo ahora" (`POST /mantenimiento/ejecutar`, el mismo
endpoint que dispara la programación en sí, solo que `disparado_por` queda
como `"manual"`) — y la tabla de histórico completa. Sondeo cada 4 s, mismo
patrón que el resto de la web (CLAUDE.md, encargo de la sesión de
identidad, "Expedientes").

### Verificación contra el stack real, intervalo corto

`MANTENIMIENTO_INTERVALO_SEGUNDOS=45` (frente al valor de producción,
604800 = una semana) durante ~9 minutos, contra la base de datos real de
desarrollo (59 expedientes de las sesiones de los bloques 1 y 2, sin
limpiar). **Cuatro ejecuciones programadas seguidas, ninguna solapada,
histórico correcto de principio a fin** — verificado con el propio
`GET /mantenimiento/historial` sondeado cada 20 s, no solo mirando la base
de datos:

| Trabajo | Encolado | Terminado | Duración |
|---|---|---:|---:|
| 369 | 04:56:34 | 04:58:43 | 129 s |
| 372 | 04:58:46 (3 s después de que 369 terminara) | 05:01:55 | 189 s |
| 375 | 05:01:58 (3 s después de que 372 terminara) | — | — |
| 378 | 05:05:16 (tras 375) | — | — |

**Cada ciclo real tardó entre 2 y 3 minutos** — muy por encima del
intervalo de prueba de 45 s — porque cada uno descarga de verdad el ZIP de
sindicación del mes en curso (~23 MB, periodo `202609` parcial) antes de
evaluar frescura. El mecanismo de "sin solaparse" hizo exactamente lo que
tenía que hacer en ese caso: en vez de lanzar un ciclo cada 45 s y
amontonarlos, cada ejecución programada arrancó **inmediatamente después**
de que terminara la anterior (siempre a los 3 s, el intervalo de sondeo del
worker) — la cadencia real queda acotada por abajo por cuánto tarda el
propio ciclo, nunca por debajo de eso, sin necesitar ninguna lógica
adicional para conseguirlo. Ninguna de las cuatro ejecuciones duplicó
trabajo: `descubrimiento.expedientes_nuevos` fue `0` en las tres que
llegaron a completarse (los 4 expedientes del departamento 28510 del
periodo en curso ya eran conocidos desde antes de empezar esta prueba).

**Hallazgo real de paso, no un fallo de este bloque**: las tres ejecuciones
completadas relanzaron la descarga del mismo expediente
(`6.24/28510.0106`) en cada pasada. Verificado en base de datos: es un
pedido derivado de acuerdo marco (`codigo_matriz = 6.20/28510.0136`,
`matriz_expediente_id` resuelto) sin ningún documento propio — sus
importes vienen heredados de la matriz (CLAUDE.md sección 20), así que
`app.mantenimiento.frescura.debe_descargar` lo reintenta en cada ciclo
exactamente como está diseñado (bloque 1: "sin documentos propios, merece
un intento nuevo"). Coste real, no gratis: un intento de scraping real
contra la Plataforma por ciclo hasta que se resuelva o quede
`sin_publicar` — esperable para este patrón, ya documentado, no nuevo de
esta sesión.

**Recuperación de trabajo huérfano, verificada en vivo por segunda vez en
esta sesión** (la primera fue en el bloque 2): al reconstruir el
contenedor del worker para volver al intervalo de producción, el trabajo
que estaba `en_proceso` en ese instante quedó huérfano y
`reclamar_trabajos_huerfanos` lo recuperó solo pasado el umbral — sin
intervención manual.

225 tests en verde (218 del bloque 2 + 7 de este bloque —
`tests/mantenimiento/test_programacion.py`: nunca corrió lanza ahora, no
lanza antes de tiempo, lanza cuando toca, no solapa con uno en curso
propio ni con uno disparado a mano, desactivado nunca lanza, `obtener_
estado` refleja lo real), dentro del contenedor.

### Variables de entorno nuevas

`MANTENIMIENTO_INTERVALO_SEGUNDOS` (segundos, 604800 por defecto) y
`MANTENIMIENTO_PROGRAMADO_ACTIVO` (`true`/`false`) — **añadidas tanto al
servicio `worker` (quien decide) como al servicio `api`** (quien las
expone en `GET /mantenimiento/estado`): un descuido real de esta sesión,
detectado en la propia verificación en vivo, fue añadirlas solo al
`worker` y dejar que la API siguiera leyendo el valor por defecto de
`app/config.py` — la web habría mostrado "semanal" aunque el worker
estuviera de verdad lanzando cada 45 segundos. Corregido antes de dar el
bloque por cerrado, no después.

---

## 26. Criterios de alcance del cliente, y su contraste contra el corpus real (sesión 2026-09-04)

Tres criterios que llegan **del cliente**, no de nuestro propio análisis —
marcados así explícitamente porque **dos de los tres no se sostienen tal
cual contra los documentos reales** del corpus. Se verificaron contra
documentos reales antes de tocar código (encargo explícito de esta sesión):
donde contradicen lo ya documentado (sección 3, sección 19), se implementó
la parte que la evidencia confirma, no la versión literal del cliente. El
motivo de cada decisión queda aquí para poder explicárselo sin que parezca
que no se le hizo caso.

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
fixtures fijos, sección 13) — probado con un caso sintético (`PaginaTexto`
directo, sin PDF) para las dos ramas ("Suministros" no dispara nada,
"Obras" sí).

### 2. El mínimo exigible para dar por buena una baja de lote (criterio del cliente)

**Aplicado tal cual, sin contradicción.** Antes de esta sesión,
`app.extraccion.precios_unitarios.calcular_baja_efectiva` exigía que la baja
declarada en texto cuadrase (con tolerancia de medio punto) con la baja que
resultaba de los importes de licitación y adjudicación — un desajuste
mandaba el expediente entero a revisión (CLAUDE.md sección 12, "lo que no
cuadra no se corrige solo"). El cliente pide un mínimo más laxo: lote,
expediente y baja declarada bastan. Se quitó la exigencia de que cuadren —
la baja declarada gana siempre que exista; solo sigue exigiéndose revisión
cuando no hay ninguna baja de la que partir (el caso de precios unitarios
sin baja declarada, sección 4, no cambia).

**Efecto medido, verificado contra el stack real (no solo predicho):** de
los 7 expedientes que CLAUDE.md sección 22 agrupaba como "baja declarada no
cuadra con la baja por importes", **4 pasan a completado** —
`6.23/28510.0139`, `6.24/28510.0094`, `6.24/28510.0130`, `6.25/28510.0019`.
Los otros 3 de ese mismo grupo (`6.24/28510.0117`, `6.24/28510.0203`,
`6.25/28510.0028`) **siguen en revisión**: al mirar su motivo completo (no
solo el resumen de la sección 22) tenían, además del desajuste de baja, un
segundo problema independiente — valores de celda que no se pudieron
interpretar (39, 3 y 4 líneas respectivamente) — que este criterio no toca.
La sección 22 los agrupaba bajo un solo motivo compuesto; con el desajuste
de baja ya resuelto, el motivo restante que queda visible es justo ese
segundo problema, antes oculto detrás del primero.

### 3. Reglas sobre tipos de documento (criterio del cliente) — verificado contra los documentos reales antes de aplicar nada

**"Los pliegos no tienen contenido, son enlaces — se pueden ignorar":
contradicho en parte por el corpus real, y ya apuntado antes de esta sesión
(sección 3).** `TipoDocumento.pliego` mezcla tres documentos distintos,
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
  sección 3): **contradice el criterio del cliente.** Es el pliego técnico
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
8 matrices de acuerdo marco descubiertas en la sesión de herencia, sección
20) contra el stack real -- `docker compose`, sin dobles de test --, con
`forzar=true` y sindicación desactivada para no volver a contaminar la base
de datos. Dos reprocesos completos en esta sesión: el primero con los tres
criterios del cliente (arriba); el segundo, tras el arreglo urgente de
autoridad de fuentes y el de las 3 celdas con guion suelto (ver más abajo).

| | Antes de esta sesión | Tras los 3 criterios | Final |
|---|---:|---:|---:|
| `completado` | 14 | 16 | **20** |
| `pendiente_revision` | 24 | 22 | **18** |
| `sin_publicar` | 15 | 15 | 15 (sin cambio) |
| Líneas de catálogo | — | 2.208 | **2.208** (sin cambio: los arreglos posteriores no añaden líneas nuevas, solo dejan de descartar campos ya extraídos) |
| Matrículas en más de un expediente | 13 | 13 | **13** (sin cambio) |

Sobre los 45 (excluyendo las 8 matrices, todas `sin_publicar`): completado
20, pendiente_revision 18, sin_publicar 7 — suma 45.

### Seguimiento urgente: autoridad del PDF sobre la sindicación, y los 3 últimos en revisión

Encargo del cliente tras ver el primer reproceso: `6.24/28510.0088` (el
ejemplo central de la sección 4) no puede estar en revisión, y el problema
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
nunca pisa un dato más nuevo con uno más viejo, sección 24 — no es la causa
aquí). Es que `6.24/28510.0088` y `6.23/28510.0129`, tal como los tiene
identificados este sistema, no son pedidos de un solo lote: son licitaciones
de varios lotes de las que solo tenemos el papel de uno. Mismo tipo de
problema de identidad que ya se resolvió para acuerdo marco (secciones
20-21) — "el código bajo el que está archivado un documento no es
necesariamente el expediente al que pertenece de verdad" —, pero en una
variante nueva (lote de licitación directa, sin acuerdo marco de por medio)
que no había aparecido hasta esta sesión. **Separarlo bien de verdad**
(crear expedientes de lote reales, `.0113`/`.0143`, y dejar `.0088`/`.0129`
como lo que son —el expediente principal, sin cuadro de precios propio— es
un cambio de modelo de datos mayor, fuera de alcance de un arreglo urgente:
queda anotado en la sección "Pendiente de resolver" para una sesión aparte.

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
  blanco en el resto del sistema (columnas fantasma, CLAUDE.md sección 8) —
  no un valor ilegible. **Barato, arreglado**: `app.catalogo._es_celda_vacia`
  trata un guion suelto como campo vacío para matrícula, cantidad y precio
  unitario, sin generar motivo de revisión. Los dos pasan a `completado`.
- `6.25/28510.0028` (4 líneas): **no era barato.** Las celdas traen
  identificadores de glifo sin decodificar (`(cid:1005)...`, fuente sin tabla
  ToUnicode) — es justo el caso de "fuera de alcance sin OCR" de la sección
  15, no una celda con un valor reconocible. Sigue en revisión, y es
  correcto que lo esté.

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
marco (sección 20) descubrió y creó a partir de ellos — 53 filas en total,
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
repositorio (sección 13: no se meten los PDFs completos).

---

## 27. Identidad de lote: la licitación multi-lote como estructura de primera
    clase (sesión 2026-09-04)

Ataca de raíz el problema que la sección 26 solo diagnosticaba para dos
casos (`6.24/28510.0088`, `6.23/28510.0129`): **13 expedientes multi-lote
más del corpus real comparten el mismo síntoma**, silenciados hasta ahora
porque el motor no sabía leer ninguna redacción salvo la de
`6.25/28510.0027` (sección 19). El encargo explícito de esta sesión: recorrer
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
- **Acuerdo marco / pedidos derivados (secciones 20-22), sin relación con lo
  anterior más allá de compartir vocabulario** (ver punto 2). Estructura ya
  estable, no tocada en esta sesión.

### 2. Dos trampas de vocabulario verificadas, no supuestas

El corpus reutiliza dos palabras del dominio con un segundo significado
ajeno al de la sección 2 — confusión real, no hipotética, y hay que evitar
que el código las mezcle:

- **"Lote"**: en una licitación multi-lote (este documento) es la
  subdivisión en contratos concurrentes que describe el punto 1. En un
  pedido derivado de acuerdo marco (secciones 3 y 20), "Lote N" es una
  **categoría de producto dentro del catálogo del acuerdo marco** ("Pedido
  nº 7 acuerdo marco de suministro de equipos de protección individual. Lote
  4.- guantes de protección..."), sin ninguna subdivisión en contratos
  concurrentes. Dos conceptos distintos, misma palabra.
- **"Matriz"**: `6.24/28510.0094` etiqueta su expediente principal como "Nº
  EXPEDIENTE MATRIZ" — verificado en el documento real, sin relación alguna
  con `codigo_matriz`/`matriz_expediente_id` (acuerdo marco, secciones 2 y
  20). Es solo cómo esta Propuesta LC.27 concreta llama a "el expediente que
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
mismo patrón que `6.24/28510.0088` (sección 26), pero sin siquiera un
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
  sección 5). Si faltan, se acumula en `motivo_revision` — el mecanismo ya
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
stack real, uno a uno en procesos aislados (ver nota de rendimiento más
arriba en la sección "Pendiente de resolver"):

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
(CLAUDE.md sección 13: pequeños, `6.23_28510.0066_ADJUDICACION_1.pdf`
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

---

## 28. Pulido a 1280px: desbordamiento horizontal, cola de revisión sin
    aprovechar la pantalla, y ruido de diagnóstico en mantenimiento
    (sesión 2026-09-04)

Sesión de correcciones puntuales sobre el rediseño visual (sección
anterior), sin tocar el motor. Encargo explícito: verificar cada arreglo
con la aplicación real abierta a 1280px, no solo compilando — hecho con
Playwright headless contra el stack real (`docker compose`, 53
expedientes, 3018 líneas de catálogo), midiendo `scrollWidth` de la página
antes y después de cada cambio, nunca solo mirando una captura.

- **Aviso de entorno, no del proyecto:** `/home/lucas/adif` (WSL) es un
  clon antiguo y desactualizado (solo tiene el esqueleto de la sección 14,
  sin `catalogo/`, `revision/` ni `mantenimiento/`) — no tiene relación con
  el stack que corre de verdad. Los contenedores reales (`adif-api-1`,
  `adif-web-1`...) se construyen desde **`/mnt/c/dev/ADIF`** (el mismo
  directorio de Windows, montado), con `docker-compose.yml` +
  `docker-compose.override.yml` — confirmado con `docker inspect
  --format '{{json .Config.Labels}}'` (`com.docker.compose.project.
  working_dir`). Cualquier sesión futura que edite código y no vea el
  cambio reflejado tras un rebuild: comprobar primero desde qué ruta se
  construyó el contenedor, no asumir que `/home/lucas/adif` es el proyecto.
- **Expedientes y Catálogo desbordaban 1280px por 257px y 218px** (medido).
  Causa en Catálogo: `.descripcion` (columna Descripción) tenía
  `max-width: 30rem` — bajado a `16rem`, la única columna con margen para
  ceder (encargo explícito), y el desbordamiento desapareció del todo.
  Causa en Expedientes, más sutil — dos factores, no uno:
  1. Las notas de motivo (`.status-note`, en Estado y en Baja) no tenían
     tope de ancho salvo un `max-width: 28rem` genérico pensado para otros
     contextos (paneles de trazabilidad) — con nueve columnas a 1280px eso
     desborda. Añadido `.status-note-tight` (13rem) para uso dentro de
     celda de tabla.
  2. **Bug real de CSS, no obvio**: la celda de Baja es `.table .num`
     (`white-space: nowrap`, para que las cifras no partan línea).
     `white-space` es una propiedad heredada — la nota de motivo dentro de
     esa celda heredaba `nowrap` de su `<td>` ancestro, así que por mucho
     `max-width` que tuviera, el texto nunca partía en líneas: el cálculo
     de ancho de columna auto-layout usaba el ancho SIN partir (más de
     300px) en vez del ancho partido dentro del `max-width`. Verificado
     con `getComputedStyle` en Playwright (`whiteSpace: "nowrap"` medido
     sobre el elemento, pese a `max-width: 208px` declarado) antes de
     tocar nada — no se adivinó. Arreglado con `white-space: normal;`
     explícito en `.status-note`. Este único cambio bajó el desbordamiento
     residual de 55px a 0.
  3. Los dos botones de Acciones (`Descargar` / `Extraer`) se apilan ahora
     en columna en vez de en fila (encargo: "revisa si los botones
     necesitan tanto sitio") — de 197px a 120px, colchón adicional aunque
     no era la causa principal.
- **Columna Baja vacía: verificado que es dato real, no un fallo.**
  `GET /expedientes` ordena por `id` (creación), y en esta base de
  desarrollo los primeros ~14 ids son justo los pedidos derivados de
  acuerdo marco `esperando_matriz`/`sin_publicar` (secciones 20-22) — sin
  baja por diseño, no por error. Contados los 53: **28 de 53 (53%)** sí
  traen una baja real (directa o "varía por lote"), solo que ninguno cae
  en las primeras filas visibles sin hacer scroll. Decisión: la columna se
  queda — es información central del proyecto (sección 4) y mayoritaria
  una vez se cuenta bien —, sin tocar el orden de listado (no pedido,
  fuera de alcance de un arreglo de descuadres).
- **Cola de revisión: el panel con el PDF embebido ya existía en código**
  (CSS y JSX de la sección anterior), pero la pantalla se abría sin ningún
  caso seleccionado — dos tercios en blanco hasta el primer clic, que es
  justo el síntoma que describía el encargo aunque la estructura ya
  estuviera construida. Arreglado seleccionando el primer caso de la lista
  en cuanto la lista carga (`RevisionPanel.tsx`), para que el documento y
  el formulario aparezcan sin interacción previa.
- **Bug real nuevo, encontrado al verificar la selección automática**: con
  un caso ya seleccionado, la tabla de líneas de catálogo (columna
  izquierda del panel, junto al PDF) desbordaba la página por 131px. Causa:
  un hijo de CSS Grid no encoge por debajo del ancho mínimo de su
  contenido por defecto (`min-width: auto` implícito) — la tabla de líneas
  (7 columnas) tiene un ancho mínimo mayor que la pista `minmax(0, 1fr)`
  que le correspondía junto al panel del PDF (`minmax(320px, 480px)`), así
  que el hijo empujaba la pista entera fuera del grid. Arreglado con
  `min-width: 0` en el contenedor y un scroll horizontal propio y acotado
  para esa tabla (`.table-scroll--panel`) en vez de dejar que el
  desbordamiento se propague a la página — con el `position: sticky` de la
  cabecera desactivado ahí a propósito, porque solo tiene sentido cuando
  el único scroll es el de la página entera (comentario ya existente en
  `.table-scroll`), no dentro de un panel con su propio scroll.
- **Descripciones de proyecto en la cola de revisión: recortadas a dos
  líneas** (`.revision-item .hint.proyecto`, `-webkit-line-clamp`) — en el
  corpus real llegaban a cinco líneas en mayúsculas y disparaban la altura
  de cada tarjeta.
- **Mantenimiento: la marca "abortado manualmente para diagnostico" no
  sale de ningún camino de código** (`grep` sobre todo `engine/app/*.py`:
  cero resultados) — es texto que alguien escribió a mano en la base de
  datos de desarrollo para desatascar un trabajo `en_proceso` huérfano
  durante otra sesión, nunca un fallo real del motor. Antes de esta
  sesión, la web no distinguía esta marca de un fallo real:
  `MantenimientoPanel.tsx` la trataba igual que cualquier `fallido` (barra
  de acento en tinta, punto relleno). Añadido `esInterrupcionManual`
  (detecta el texto "abortado manualmente" en el `error` del trabajo) — en
  el resumen de "última ejecución" y en la fila del histórico correspondiente,
  ahora usa el mismo tratamiento atenuado que `sin_publicar` (punto hueco,
  texto en tinta atenuada, sin la barra de acento), con una frase en
  lenguaje llano en vez del texto crudo de diagnóstico.
- **Verificado en vivo, no solo con datos ya en base de datos**: el worker
  llevaba parado 3 horas (`docker compose ps` mostraba `Exited (137)`, el
  propio efecto colateral de la sesión de diagnóstico que dejó la marca
  manual) — coherente con el propio síntoma del encargo. Reiniciado
  (`docker compose up -d worker`) y lanzado un ciclo real de mantenimiento
  end-to-end (`POST /mantenimiento/ejecutar`, sin forzar, sindicación
  desactivada) para comprobar el segundo punto del encargo ("que ese
  registro no quede como estado actual del sistema si después hubo
  ejecuciones correctas"): el ciclo tardó **≈23 minutos en completar
  (job 493)**, reprocesando el trabajo huérfano acumulado durante esas 3
  horas de worker parado — y al terminar, `/mantenimiento/estado` pasó a
  reflejar el 493 (`completado`) como última ejecución, con el 462
  (`fallido` / interrumpido manualmente) correctamente relegado al
  histórico y ya con su tratamiento atenuado. El mecanismo en sí
  (`app.mantenimiento.programacion._ultimo_trabajo_ciclo`, ya ordena por
  `created_at desc`) nunca tuvo el bug de fondo que el encargo temía — era
  puramente un problema de presentación, confirmado leyendo el código
  antes de tocar nada.

### Verificación

Las cuatro pantallas reconstruidas contra el stack real
(`docker compose build web && docker compose up -d web`, desde
`/mnt/c/dev/ADIF`) y medidas con Playwright a 1280×900: `scrollWidth -
clientWidth = 0` en las cuatro. `npx tsc --noEmit` sin errores. Sin tests
de `engine` afectados — ningún cambio de esta sesión toca `engine/`.
