# Descubrimiento inverso: matriz → pedidos (sesión 2026-09-07)

Hasta esta sesión el sistema solo resolvía una dirección: dado un pedido,
encontrar su acuerdo marco (`app.extraccion.herencia_matriz`, sesión de
herencia de matriz). Nunca había recorrido la dirección contraria — dado un
acuerdo marco, encontrar los pedidos que cuelgan de él — que es la que
importa para la segunda familia de baja (CONTEXTO.md sección 16): los
precios de referencia están en la matriz, la baja real en cada pedido, y sin
las dos piezas el precio adjudicado no se puede calcular.

Caso de comprobación: los tres últimos acuerdos marco de carril
(`6.23/28510.0018`, `6.23/28510.0102`, `6.25/28510.0016`, todos
ArcelorMittal España) y sus nueve pedidos conocidos.

---

## 1. Descubrimiento inverso: qué funciona y qué no

Verificado en vivo contra la Plataforma real, headless, dentro del
contenedor `worker` (mismo motor que el resto del scraping).

- **La ficha de la matriz NO enlaza sus pedidos.** Se volcó el texto
  completo de la ficha de `6.23/28510.0018`: trae "Sistema de contratación:
  Establecimiento del Acuerdo Marco" pero ninguna sección de "pedidos" ni
  "contratos basados en este acuerdo marco".
- **La sindicación tampoco lo trae** — ya lo había cerrado la sesión de
  2026-09-02 (`docs/hallazgos-sindicacion.md` sección 17.1): cero resultados
  buscando `FrameworkAgreement`/`AcuerdoMarco` en el ZIP completo de un mes.
- **El buscador de la Plataforma SÍ permite acotar, sin un campo directo de
  "Expediente del Acuerdo Marco".** Las 23 etiquetas reales del formulario
  avanzado (volcadas en vivo) no incluyen ese campo. Pero sí existe
  `Sistema de contratación = "Contrato basado en un Acuerdo Marco"`
  (`<select id="...tipoSistemaContratacion">`, valor `"3"`), combinable con
  `Órgano de contratación` y `Adjudicatario` (ambos texto libre, coincidencia
  parcial).
- **Cada ficha de pedido SÍ declara su matriz de forma estructurada** — no
  solo en el PDF (CONTEXTO.md sección 7), también en la propia ficha HTML:
  sección "Acuerdo Marco → Expediente: 6.23/28510.0018", volcada en vivo
  desde la ficha real de `6.24/28510.0040`.

**Método verificado**: para una matriz dada, buscar con
`Órgano=ADIF` + `Sistema de contratación=3` + `Adjudicatario=<el de la
matriz>`, paginar todos los resultados, y para cada candidato abrir su
propia ficha y confirmar que "Acuerdo Marco → Expediente" coincide
exactamente con el código de la matriz buscada.

**Por qué hace falta el segundo paso (no basta con la búsqueda sola)**:
el mismo adjudicatario puede tener más de un acuerdo marco a lo largo de
los años. La búsqueda `Órgano=ADIF` + `Sistema=3` +
`Adjudicatario=ARCELORMITTAL` devolvió **92 resultados reales en 5
páginas**, de los que solo 9 (los conocidos) pertenecen a las tres matrices
de esta sesión — el resto son pedidos de *otros* acuerdos marco de carril,
de departamentos distintos (`27510`, `20810`, `06510`, `05510`, `21510`) y
de años distintos (2022-2026). Los 9 pedidos conocidos aparecieron **los
9, sin excepción**, entre esos 92 candidatos.

Implementado en `app.scraping.pcsp.buscar_candidatos_acuerdo_marco` (la
búsqueda y paginación) y `leer_matriz_declarada` (la lectura de la ficha de
cada candidato), combinados en `descubrir_candidatos_acuerdo_marco`.

---

## 2. Ajuste del cliente: adjudicatarios múltiples

Un acuerdo marco puede repartir sus lotes entre varios adjudicatarios. El
descubrimiento (`app.extraccion.descubrimiento_matriz._adjudicatarios_de`)
recoge el adjudicatario distinto de **cada** lote de la matriz (no solo el
del primero) y lanza una búsqueda por cada uno, uniendo los candidatos.

Si ningún lote tiene adjudicatario extraído todavía, la búsqueda no puede
acotarse y el descubrimiento **lo señala explícitamente**
(`Expediente.aviso_descubrimiento_pedidos`, migración 0017) en vez de
saltarse la matriz en silencio — visible en la ficha de la matriz en
`/expedientes` (bloque de pedidos, sesión de descubrimiento inverso).

---

## 3. Coste: caché de candidatos y frecuencia semanal

Verificar un candidato cuesta abrir su ficha en un navegador real. Con 92
candidatos reales para un solo adjudicatario, repetir esa apertura en cada
ciclo sería caro sin necesidad — la matriz que declara un candidato no
cambia una vez adjudicado.

- **Caché** (`CandidatoAcuerdoMarco`, migración 0017): una fila por
  candidato ya comprobado, con la matriz que su ficha declaró. Se reutiliza
  también entre matrices distintas que compartan un candidato de la
  búsqueda (mismo adjudicatario, acuerdo marco distinto) — un candidato ya
  verificado no se vuelve a abrir nunca, ni para la matriz que lo descartó
  ni para ninguna otra.
- **Frecuencia**: trabajo de cola propio (`descubrimiento_pedidos`), mismo
  mecanismo genérico que ya usan el ciclo de mantenimiento y las copias de
  seguridad (`app.mantenimiento.programacion`) — semanal por defecto
  (`DESCUBRIMIENTO_PEDIDOS_INTERVALO_SEGUNDOS`, activable/desactivable con
  `DESCUBRIMIENTO_PEDIDOS_ACTIVO`), sin solaparse consigo mismo. Botón
  manual tanto general (`POST /mantenimiento/descubrimiento-pedidos/ejecutar`
  sin `matriz_expediente_id`, recorre todas las matrices ya conocidas) como
  por matriz concreta (con `matriz_expediente_id`, botón "Buscar más
  pedidos" en su ficha).
- **Universo recorrido por defecto**: solo expedientes que ya son matriz de
  al menos un pedido conocido (`descubrimiento_matriz.matrices_conocidas`)
  — no tiene sentido buscarle pedidos a un expediente que todavía no se
  sabe que sea un acuerdo marco; eso lo establece la primera vez algún
  pedido que lo declara (`app.extraccion.herencia_matriz`, dirección de
  siempre). El descubrimiento inverso amplía lo que ya se sabe, no
  descubre acuerdos marco desde cero.

---

## 4. La baja de la segunda familia: limitación confirmada del origen

**Comprobado con los documentos reales de los 9 pedidos conocidos — no es
una limitación del sistema, es que el dato no está publicado en ningún
documento de la Plataforma para estos acuerdos marco.**

Se descargaron los documentos reales de los 9 pedidos (scraping real,
`app.scraping.pcsp.scrape_expediente`, sin ningún doble):

| Pedido | Documentos publicados |
|---|---|
| 6.24/28510.0040 | Adjudicación, Formalización |
| 6.24/28510.0076 | Adjudicación, Formalización |
| 6.24/28510.0109 | Adjudicación, Formalización |
| 6.24/28510.0216 | Adjudicación, Formalización |
| 6.25/28510.0030 | Adjudicación, Formalización |
| 6.25/28510.0115 | Adjudicación, Formalización |
| 6.25/28510.0191 | Adjudicación, Formalización |
| 6.25/28510.0234 | Adjudicación, Formalización |
| 6.26/28510.0014 | Adjudicación, Formalización |

**Los 9 pedidos, sin excepción, solo publican los dos formularios PCSP de
etiqueta fija** (el mismo tipo de documento que hoy alimenta la etapa 2 de
la cascada, CONTEXTO.md sección 5) — nunca una Propuesta LC.27, nunca un
Anejo con cuadro de precios propio. Se extrajo el texto completo de los 18
documentos (`pdfplumber`) y se buscó, sin encontrar ninguna coincidencia:

- La frase literal `"Coeficiente de baja"` — 0 apariciones en los 18.
- La variable `Kt` — 0 apariciones en los 18.
- Cualquier desglose por material o por código de precio — los 18
  documentos solo declaran importes agregados a nivel de expediente
  (`Importe total ofertado (sin impuestos)`), nunca un cuadro de precios
  unitario.

Cada documento sí trae, en cambio, el campo "Licitación basada en el
acuerdo marco → Expediente" (o su variante "Identificador contrato
original") — confirma que la Plataforma sabe perfectamente que estos son
pedidos derivados y de qué acuerdo marco, pero no publica el coeficiente
con el que se calculó su precio.

**Consecuencia**: el "Coeficiente de baja" de estos acuerdos marco
(docs/identidad-expediente.md sección 28: "ofertado por el licitador en
cada pedido, no está en ningún documento de la licitación") sigue sin
existir en ningún documento público — ni en los de la matriz (ya
verificado en la sesión de 2026-09-05) ni, ahora verificado, en los del
propio pedido. **No es una limitación del sistema: es que ADIF y el
adjudicatario acuerdan ese coeficiente fuera de la Plataforma de
Contratación**, y no hay ningún documento al que el sistema pueda acceder
para leerlo. Nada que implementar sin inventar un dato — sigue el mismo
diseño ya cerrado en la sesión de 2026-09-05 (`lotes.modelo_precio =
indexado_por_pedido`, `baja_lote`/`precio_adjudicado` en `NULL` a
propósito).

---

## 5. Hallazgo de paso: baja heredada sin marcar en pedidos indexados

`app.extraccion.herencia_matriz.intentar_heredar_de_matriz` copiaba las
líneas de catálogo de la matriz (precios de referencia) a cada pedido, pero
**no propagaba `lote.modelo_precio`/`coeficiente_transformacion`** — el
pedido se quedaba con `modelo_precio = fijo` (su valor por defecto) porque
sus propios documentos nunca traen el marcador literal que lo detectaría
(vive solo en los de la matriz, confirmado en el punto 4 de arriba: los 18
documentos reales de los 9 pedidos no traen ese marcador). Efecto real en
`app.extraccion.orquestador` (línea ~941): el chequeo final
`not any(l.baja_lote is not None or l.modelo_precio == indexado_por_pedido
for l in lotes)` se disparaba igual que si fuera un fallo real de
extracción, mandando el pedido a `pendiente_revision` con el motivo "no se
pudo determinar la baja de ningún lote" — indistinguible de un fallo real.

Corregido: `intentar_heredar_de_matriz` propaga `modelo_precio`/
`coeficiente_transformacion` de la matriz al lote del pedido (idempotente:
si la matriz deja de declarar el modelo indexado en un reproceso, revierte
al pedido a `fijo`). `LoteOut.modelo_precio` ya se exponía en la API pero no
se usaba en la web — la web (`ExpedientesPanel.tsx`) ya distingue ahora
"Baja indexada por pedido" (nota explícita) de "No consta" (fallo real),
tanto a nivel de expediente de un solo lote como en la tabla de lotes
multi-lote.

Tests: `tests/extraccion/test_herencia_matriz.py`
(`test_hereda_modelo_precio_indexado_sin_marcarlo_como_fallo`,
`test_revierte_modelo_precio_si_la_matriz_deja_de_declararlo`).

---

## 6. Relación en los dos sentidos (web)

- `Expediente.pedidos` (relación SQLAlchemy inversa de `matriz`, nueva) y
  `ExpedienteOut.pedidos` (resumen ligero: código, estado, baja, importe
  adjudicado) — la matriz ya trae la lista de sus pedidos en la misma
  respuesta que sus propios lotes/precios de referencia.
- `ExpedientesPanel.tsx`: bajo el código de un expediente que ya es matriz
  de alguien, un desplegable "N pedidos" con su tabla (código, estado, baja,
  adjudicación) y el botón "Buscar más pedidos" (dispara el trabajo de
  descubrimiento sobre esa matriz concreta). Si la matriz no tiene
  adjudicatario extraído, el aviso del punto 2 aparece en el mismo sitio en
  vez del desplegable.

---

## 7. Hallazgo de paso: `lotes.adjudicatario` nunca se guardaba en el camino de lote único

Al intentar verificar el descubrimiento inverso contra las 3 matrices reales
(no un doble): las tres tenían `lotes.adjudicatario = NULL`, pese a que sus
documentos declaran el adjudicatario con toda claridad ("Adjudicatario:
ARCELORMITTAL ESPAÑA SA"). Causa raíz: `app.extraccion.campos_pcsp` ya
extraía el campo (`CamposAnuncioPcsp.adjudicatario`, por etiqueta fija) desde
el principio del proyecto, pero `app.extraccion.orquestador` solo lo
guardaba en `lotes.adjudicatario` para el camino **multi-lote explícito**
(`LoteDeclarado.adjudicatario`, sesión de identidad de lote) — el camino de
**lote único implícito**, que usa la mayoría del corpus, leía el campo en
`_extraer_campos_expediente` y lo descartaba sin asignarlo a ningún sitio.
Sin adjudicatario, el descubrimiento inverso no tiene con qué acotar su
búsqueda: exactamente el caso que el ajuste 1 del cliente pedía señalar, no
saltarse en silencio.

**Corregido**: `_extraer_campos_expediente` ahora también recoge
`campos.adjudicatario` (misma trazabilidad que licitación/adjudicación —
`_traza(..., "adjudicatario", ...)`) y el camino de lote único lo asigna a
`lote.adjudicatario` cuando lo encuentra (nunca pisa un valor ya conocido
con `None`, mismo criterio que el resto del código). Verificado contra el
stack real: `6.23/28510.0018` reprocesado, `lotes.adjudicatario` pasa de
`NULL` a `"ARCELORMITTAL ESPAÑA SA"` — y una segunda ejecución del
descubrimiento inverso sobre esta matriz, ahora con adjudicatario real,
completó en **~1 minuto** (frente a los ~20 minutos de la primera, sin
caché) con `candidatos_verificados_ahora: 0` — confirma en producción que la
caché del punto 3 funciona de verdad, no solo en el diseño.

**Límite real, no arreglado en esta sesión**: `6.23/28510.0102` y
`6.25/28510.0016` (las otras dos matrices de carril) clasifican su
adjudicación como **Propuesta LC.27**, no Anuncio PCSP — y
`app.extraccion.campos_lc27` nunca ha tenido un extractor de adjudicatario
(no solo para el camino de lote único: tampoco existía para el multi-lote).
Añadirlo es trabajo nuevo de extracción (localizar el campo en la plantilla
LC.27 real, verificarlo contra documentos reales), no una propagación de un
dato ya extraído — fuera del alcance de esta sesión. Consecuencia visible:
el descubrimiento inverso automático de estas dos matrices seguirá
señalando `aviso_descubrimiento_pedidos` (ajuste 1) hasta que exista ese
extractor. Candidato claro para una sesión futura.

Test: `tests/extraccion/test_orquestador.py`
(`test_lote_unico_guarda_adjudicatario_del_anuncio_pcsp`).

---

## 8. Recuento de los 9 pedidos procesados

Verificado contra el stack real (scraping real, extracción real, sin
dobles): los 9 pedidos existen en la Plataforma, se descargaron y
extrajeron, y **los 9 quedaron `completado`** (no `pendiente_revision`) —
gracias al arreglo del punto 5, la baja vacía por el modelo indexado ya no
se confunde con un fallo real.

| Pedido | Matriz | Estado | Líneas de catálogo (heredadas) |
|---|---|---|---|
| 6.24/28510.0040 | 6.23/28510.0018 | completado | 13 |
| 6.24/28510.0076 | 6.23/28510.0018 | completado | 13 |
| 6.24/28510.0109 | 6.23/28510.0018 | completado | 13 |
| 6.24/28510.0216 | 6.23/28510.0102 | completado | 13 |
| 6.25/28510.0030 | 6.23/28510.0102 | completado | 13 |
| 6.25/28510.0115 | 6.23/28510.0102 | completado | 13 |
| 6.25/28510.0191 | 6.25/28510.0016 | completado | 14 |
| 6.25/28510.0234 | 6.25/28510.0016 | completado | 14 |
| 6.26/28510.0014 | 6.25/28510.0016 | completado | 14 |

- **Pedidos que entran: 9 de 9** — todos localizados en la Plataforma real,
  todos vinculados a su matriz correcta (con el arreglo del punto 8.1 abajo
  para el caso `6.26/28510.0014`), todos `completado`.
- **Líneas de catálogo aportadas: 120** (13 × 6 + 14 × 3) — todas
  heredadas del cuadro de precios de referencia de su matriz
  (`heredado_de_matriz = true`), con `baja_lote`/`precio_adjudicado` en
  `NULL` por diseño (punto 4: el coeficiente no está publicado) y
  `modelo_precio = indexado_por_pedido` marcándolo explícitamente.
- **Matrículas que pasan a aparecer en más de un expediente: 13.** Las 13
  matrículas del cuadro de precios de referencia (P-1 a P-13, el mismo
  catálogo de tipos de carril en las tres licitaciones) pasan de aparecer
  en 1 expediente (solo su matriz) a aparecer en **12 expedientes cada una**
  (su matriz + sus 3 pedidos, × las 3 familias) — confirma, ahora con datos
  reales y no solo por diseño de esquema, lo que CONTEXTO.md sección 16 ya
  apuntaba: "son además los que comparten matrículas entre sí". Verificado
  con una consulta directa sobre `lineas_catalogo` (agrupando por
  `matricula`, contando `expediente_id` distintos): exactamente 13 filas
  con recuento 12, ninguna con un recuento mayor por colisión accidental
  con otro expediente del corpus.

### 8.1 Segundo hallazgo de paso: forma alternativa del campo MATRIZ

Al procesar `6.26/28510.0014` (ya existía en base de datos de una sesión
anterior, sección 25 de `docs/hallazgos-sindicacion.md`) apareció un
segundo real, verificado contra sus dos documentos reales: ni el Anuncio de
adjudicación ni el de formalización de este pedido traían la sección
"Licitación basada en el acuerdo marco" que `_MATRIZ_RE` ya sabía leer —
solo el campo "Identificador contrato original" (en "Proceso de
Licitación"), con el mismo dato, verificado también presente (y coincidente)
en los documentos donde sí aparece la forma estricta. Añadido
`_MATRIZ_ALTERNATIVA_RE` en `app.extraccion.campos_pcsp`, probado solo
cuando la forma estricta no encuentra nada — mismo criterio que las
variantes laxas de la baja (CONTEXTO.md sección 4). Tests:
`tests/extraccion/test_campos_pcsp.py`
(`test_matriz_por_identificador_contrato_original_cuando_falta_la_forma_estricta`,
`test_forma_estricta_manda_sobre_la_alternativa_si_ambas_aparecen`).

---

## 9. Estado final de las tres matrices (no forma parte del encargo)

Las tres matrices siguen en `pendiente_revision` — pero por un motivo
**anterior a esta sesión y ajeno a ella**: verificado contra
`trabajos_cola`, la última extracción real de `6.25/28510.0016` antes de
esta sesión corrió a las 09:20 del mismo día (esta sesión empezó a crear
pedidos a las 11:56), con el motivo "13 línea(s) con un valor que no se
pudo interpretar" en su Contrato y su Anejo — un problema real de la propia
tabla de precios de esa matriz, no relacionado con el descubrimiento
inverso ni con la segunda familia de baja. No se ha tocado: está fuera del
encargo de esta sesión y ya tiene su propio motivo explícito en
`Expediente.error`, listo para la cola de revisión.

---

## 10. Migración y configuración nuevas

- Migración `0017`: `expedientes.aviso_descubrimiento_pedidos`, tabla
  `candidatos_acuerdo_marco`.
- `DESCUBRIMIENTO_PEDIDOS_INTERVALO_SEGUNDOS` (semanal por defecto),
  `DESCUBRIMIENTO_PEDIDOS_ACTIVO` (activo por defecto).
- Endpoints: `POST /mantenimiento/descubrimiento-pedidos/ejecutar`
  (payload opcional `matriz_expediente_id`), `GET
  .../descubrimiento-pedidos/estado`, `GET
  .../descubrimiento-pedidos/historial`.
