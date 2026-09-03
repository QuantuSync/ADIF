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
- **Patrón de Propuesta LC.27 multi-lote, sin verificar contra un documento
  real** (sección 19): el corpus completo de 45 expedientes no trae ninguna
  LC.27 con más de un lote, solo la Resolución de `6.25/28510.0027`. El
  extractor de `app/extraccion/lotes.py` asume la misma redacción "En el
  LOTE N..." para las dos plantillas por analogía, no por evidencia — si
  aparece una LC.27 multi-lote real, revisar ese módulo antes de confiar en
  el resultado.
- **8 expedientes reales tienen `codigo_expediente` etiquetado con el código
  de su MATRIZ, no con el suyo propio** (sección 20, sesión de herencia de
  matriz): su propio código real solo existe, sin usar, dentro del campo
  "Número de Expediente" de su Anuncio PCSP
  (`campos_pcsp.CamposAnuncioPcsp.numero_expediente`). Es la causa exacta de
  que la herencia de acuerdo marco no pueda resolver estos 8 casos —
  `_forma_ciclo` los corta por autorreferencia, correctamente, pero no hay
  forma de heredar de una matriz que es el propio expediente. **Decisión de
  diseño pendiente, sin tomar todavía**: si renombrar `codigo_expediente` a
  `numero_expediente` cuando difieren y la matriz declarada coincide con el
  propio código, o separar el pedido real en su propia fila. Toca la clave
  de idempotencia de la sección 9.9 sobre expedientes ya en producción — no
  es un ajuste de regex como el punto de arriba.

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

**Pendiente, no resuelto por esta sesión**: decidir qué hacer con las filas
mal etiquetadas (¿renombrar `codigo_expediente` al valor real de
`numero_expediente` cuando difieren de una matriz auto-declarada? ¿crear la
fila del pedido real por separado y mover los documentos? Ninguna opción es
trivial, y las dos tocan la clave de idempotencia de la sección 9.9 sobre
expedientes ya en producción — decisión de diseño nueva, no una continuación
directa de esta sesión). Hasta que se decida, estos 8 seguirán en
`pendiente_revision` con el motivo explícito, nunca heredando por
autorreferencia.

### Fixtures de regresión

`engine/tests/extraccion/test_herencia_matriz.py`, 15 casos: las tres
funciones del módulo por separado (creación/encolado de matriz, herencia con
trazabilidad, protección de ciclo simple y de cadena) y dos de extremo a
extremo con el fixture real `ANUNCIO_PCSP_CON_MATRIZ`
(`2.18_04703.0019_ADJUDICACION_1.pdf`, el mismo documento real que destapó el
hallazgo de la autorreferencia) contra `ejecutar_extraccion_expediente`. No
hizo falta ningún PDF nuevo.
