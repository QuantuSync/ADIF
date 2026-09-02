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

- **Ningún documento está escaneado.** Todos tienen capa de texto. No hace falta OCR
  ni modelo multimodal para leer estos documentos.
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
