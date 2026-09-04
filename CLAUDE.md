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
