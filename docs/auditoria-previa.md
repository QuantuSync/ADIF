# Auditoría previa a entrega (sesión de diagnóstico, 2026-09-04)

Sesión de diagnóstico y verificación pura — **no se ha cambiado ningún
comportamiento del motor ni de la web**, salvo el punto 0, que ya venía
acordado de la sesión anterior y solo se ha verificado que está desplegado.
Todo lo demás son mediciones y lecturas contra el stack real (`docker
compose`, Postgres real, PDFs reales del volumen de desarrollo) o consultas
SQL de solo lectura. Todo lo marcado **verificado** viene de una consulta,
una medición o una lectura de documento real hecha en esta sesión; todo lo
marcado **supuesto** es una hipótesis sin comprobar.

Estado del corpus en el momento de esta auditoría: **7 `completado`, 31
`pendiente_revision`, 15 `sin_publicar`** (53 expedientes). El encargo
mencionaba "8 completados" y "30 en revisión" — los números reales de hoy son
7 y 31, un expediente de diferencia en cada sentido; no se ha investigado por
qué (puede deberse a un reproceso entre la sesión anterior y esta). 3.000
líneas de catálogo.

---

## Resumen ordenado por gravedad

| # | Gravedad | Hallazgo | Bloque |
|---|---|---|---|
| 1 | **Alta** | `6.24/28510.0116` (uno de los 7 `completado`, candidato a ejemplo de demo) tiene dos documentos reales del mismo expediente con bajas distintas: 47,87% (Propuesta de Adjudicación) vs 46,50% (Contrato firmado). El sistema usa el 46,50% del Contrato, probablemente correcto, pero sin ninguna regla documentada en CONTEXTO.md que lo confirme como intencional. Confirmar con el cliente antes de usarlo en la demo. | 3 |
| 2 | **Media-Alta** | El problema de rendimiento de `6.23/28510.0051` **no se reprodujo** en una tanda real de 38 expedientes (mayor que los 20 pedidos): terminó en 108 s, dentro de su baseline aislado, sin cuelgue. Buena noticia para el riesgo inmediato de la demo, pero la causa raíz del episodio de >15 min documentado sigue sin confirmarse ni descartarse — ver limitaciones del bloque 1. | 1 |
| 3 | **Media** | 108 líneas de catálogo duplicadas de verdad (mismo lote, misma matrícula+descripción, mismo precio) en 4 expedientes, causadas por una segunda tabla técnica que repite el material sin código de precio — se exportarían al Excel como filas repetidas. | 2 |
| 4 | **Media** | 28 líneas de catálogo (2 expedientes, uno de ellos `completado`) tienen `codigo_precio` contaminado por el pie de página de verificación CSV del documento, invertido y colado en la celda (p. ej. `j.adilav/vscPN005`). El precio y la cantidad de esas líneas son correctos; el código no, y no dispara revisión. | 3 (ampliado en 2) |
| 5 | **Media** | La premisa de CONTEXTO.md sección 19 ("cero casos de banda vacía en el corpus") ya no es cierta con el corpus multi-lote actual: 797 líneas tienen `motivo_revision` de tipo "banda vacía", el 72% concentradas en un solo expediente (`6.25/28510.0019`, 9 lotes). No bloquea nada nuevo (ese expediente ya está en revisión por cobertura parcial), pero es una brecha real entre lo documentado y el dato de hoy. | 2 |
| 6 | **Baja** | Discrepancia de recuento: el encargo decía "8 completados / 30 en revisión"; hoy son 7 y 31. Sin investigar la causa. | — |
| 7 | **Baja** | 2 líneas de catálogo con `descripcion` vacía pero `precio_unitario` y matrícula reales, sin `motivo_revision` que lo señale — se verían como un hueco en el Excel. | 2 |
| 8 | **Informativo** | Matrícula rellena en el 35% de las líneas, no el ~66% que documenta CONTEXTO.md sección 2 sobre la muestra original de 45 expedientes — el corpus ampliado trae más tablas sin columna de matrícula. No investigado más a fondo. | 2 |

Los 5 casos de trabajo pendiente **ya documentado** en CONTEXTO.md (segunda
familia de baja sin modelar, 3 expedientes; 2 expedientes sin ninguna línea
extraída) no se listan como hallazgos nuevos — ver bloque 3, parte B.

---

## Bloque 1 — Rendimiento de `6.23/28510.0051`

**Método**: se disparó el ciclo de mantenimiento real
(`POST /mantenimiento/ejecutar`, `forzar: true`) desde el worker real
(`adif-worker-1`), que — CONTEXTO.md sección 23 — encola y **drena de forma
síncrona dentro del propio proceso Python de larga vida**: es exactamente el
escenario "N-ésimo expediente en un proceso de vida larga" descrito como
origen del problema. Sin `forzar_expedientes` explícito, el ciclo forzó los
**38 expedientes reales con documentos** (más que los 20 pedidos), con
`6.23/28510.0051` en la posición 12 de 38 de la ejecución real.

**Resultado del ciclo** (`trabajos_cola.id = 500`): completado en 1.294,97 s
(~21,6 min) para las 38 extracciones, sin ninguna saltada.

### Duración por expediente, orden real de ejecución

| # | Expediente | Duración (s) | | # | Expediente | Duración (s) |
|--:|---|--:|---|--:|---|--:|
| 1 | 6.24/28510.0103 | 0,47 | | 20 | 6.24/28510.0025 | 16,80 |
| 2 | 6.24/28510.0100 | 7,86 | | 21 | 6.24/28510.0047 | 12,10 |
| 3 | 6.24/28510.0101 | 0,43 | | 22 | 6.24/28510.0064 | 60,25 |
| 4 | 6.24/28510.0102 | 0,39 | | 23 | 6.24/28510.0088 | 47,77 |
| 5 | 6.24/28510.0111 | 0,39 | | 24 | 6.24/28510.0094 | 39,46 |
| 6 | 6.25/28510.0215 | 0,44 | | 25 | 6.24/28510.0116 | 25,65 |
| 7 | 6.25/28510.0175 | 0,40 | | 26 | 6.24/28510.0117 | 53,71 |
| 8 | 6.25/28510.0248 | 0,42 | | 27 | 6.24/28510.0124 | 30,62 |
| 9 | 6.20/28510.0136 | 6,09 | | 28 | 6.24/28510.0128 | 25,75 |
| 10 | 6.23/28510.0018 | 27,25 | | 29 | 6.24/28510.0130 | 59,10 |
| 11 | 6.23/28510.0042 | 23,67 | | 30 | 6.24/28510.0180 | 28,93 |
| **12** | **6.23/28510.0051** | **108,42** | | 31 | 6.24/28510.0185 | 32,76 |
| 13 | 6.23/28510.0066 | 53,37 | | 32 | 6.24/28510.0187 | 61,44 |
| 14 | 6.23/28510.0102 | 27,72 | | 33 | 6.24/28510.0193 | 15,13 |
| 15 | 6.23/28510.0104 | 8,08 | | 34 | 6.24/28510.0203 | 59,50 |
| 16 | 6.23/28510.0109 | 51,45 | | 35 | 6.25/28510.0016 | 27,00 |
| 17 | 6.23/28510.0129 | 28,86 | | 36 | 6.25/28510.0019 | 60,44 |
| **18** | **6.23/28510.0139** | **206,76** | | 37 | 6.25/28510.0027 | 53,65 |
| 19 | 6.24/28510.0008 | 36,46 | | 38 | 6.25/28510.0028 | 51,69 |

**`6.23/28510.0051` tardó 108,4 s en la posición 12 de 38 — dentro del
baseline aislado ya documentado (~110 s, <2 min). No se reprodujo el síntoma
de "progresivamente más lento hasta parecer colgado".** Ningún expediente de
los 38 superó los 207 s.

**Hallazgo colateral, no buscado pero real**: el expediente inmediatamente
posterior a `0051`, `6.23/28510.0139`, fue el más lento de toda la tanda
(206,8 s) pese a que CONTEXTO.md no lo documenta como grande (solo Anuncio PCSP
+ 2 Contratos, sin anejo, fixture de test de 24 KB). Sus documentos reales en
el volumen de desarrollo deben ser considerablemente más grandes que el
fixture — sin verificar el tamaño real en esta pasada.

### Curva de memoria (`adif-worker-1`, RSS del proceso, 171 muestras cada ~7-9 s)

| Tramo | En curso | RSS mín–máx | Patrón |
|---|---|---|---|
| Inicio–18:37:12 | fin `0042`, `0051` | 1,26–1,80 GiB | subida moderada, sin pico |
| 18:37:12–18:40:12 | `0066`…inicio `0139` | 1,34–1,70 GiB | oscila, tiende a bajar |
| **18:40:12–18:43:35** | **`0139` (el más lento de la tanda)** | **1,34–2,99 GiB** | **4 ciclos de diente de sierra**: sube a ~2,7-3,0 GiB en ~25-30 s y cae de golpe a ~1,4-1,6 GiB, cuatro veces seguidas |
| 18:43:35–fin (25 expedientes más) | `0008`…`0028` | 1,40–1,85 GiB | estable, **sin tendencia de crecimiento neto** |

El pico máximo absoluto de toda la tanda (2,99 GiB) ocurre durante `0139`, no
durante `0051`. La última muestra (1,51 GiB, justo antes de `completado`) es
prácticamente igual al rango de la primera mitad de la tanda — **no hay fuga
acumulativa en esta corrida de 38 expedientes**. Descriptores de fichero
abiertos al terminar: 4 — sin indicio de fuga de `pdfplumber`.

### Hipótesis, ordenadas por qué tan bien encajan con lo medido hoy

1. **Descartada en esta corrida**: fuga de memoria monotónica de `pdfplumber`
   — la memoria vuelve a un rango estable tras cada documento grande y no
   crece con el número de expedientes procesados.
2. **Descartada en esta corrida**: sesión de SQLAlchemy que crece sin límite
   — el patrón es de picos y caídas por documento, no una rampa continua.
3. **Sin verificar, la más plausible dado lo medido**: el cuelgue de >15 min
   puede necesitar una tanda sustancialmente más larga que un único pase por
   los 38 expedientes reales (p. ej. reprocesar el corpus completo varias
   veces seguidas en el mismo proceso, el patrón real de un worker que lleva
   días sin reiniciarse). Esta corrida no lo prueba ni lo descarta.
4. **Sin verificar, alternativa**: el episodio original puede no ser un
   problema de recursos del proceso Python en absoluto, sino la
   inestabilidad de `dockerd`/WSL ya documentada (CONTEXTO.md secciones 17 y
   17.4) — "activo en CPU todo el tiempo" también es compatible con un
   contenedor en un estado extraño tras una caída parcial de Docker.
5. El pico real de memoria de esta tanda lo causó `0139`, no `0051` — si el
   episodio original ocurrió con otra combinación de documentos grandes
   seguidos, el cuello de botella podría no estar ligado específicamente a
   `0051` sino al volumen acumulado de documentos grandes en una ventana
   corta.

### Limitaciones explícitas de esta medición

No se repitió `0051` varias veces en la misma tanda. No se dejó el worker
corriendo más allá de un pase completo del corpus (21,6 min). No se
instrumentó memoria a nivel de objeto Python (`tracemalloc`) dentro del
proceso — solo RSS externo. No se investigó por qué `0139` fue el más lento y
con más memoria de toda la tanda.

### Recomendación (sin implementar nada)

El riesgo inmediato para la demo es bajo si se procesa una tanda de tamaño
razonable de una vez — no se reprodujo el cuelgue con una tanda mayor que la
pedida. Si se quiere eliminar el riesgo sin investigar más la causa raíz, la
mitigación ya verificada que funciona (CONTEXTO.md, "Pendiente de resolver") es
procesar expedientes grandes en procesos aislados en vez de una tanda larga
sin reiniciar — no algo nuevo que construir.

---

## Bloque 2 — Auditoría del catálogo (3.000 líneas)

Todo verificado con `SELECT` real contra `adif-postgres-1`, sin ninguna
escritura.

### Precio unitario y relleno por columna

| | Cuenta | % |
|---|---:|---:|
| Con `precio_unitario` | 2.347 | 78,2% |
| Sin `precio_unitario` | 653 | 21,8% |

| Columna | Con dato | % |
|---|---:|---:|
| Matrícula | 1.055 | 35,2% |
| Descripción (no vacía) | 2.998 | 99,9% |
| Cantidad | 1.987 | 66,2% |
| Lote asignado | 1.892 | 63,1% |

Matrícula al 35% queda por debajo del ~66% que documenta CONTEXTO.md sobre la
muestra original de 45 expedientes — el corpus ampliado trae más tablas sin
columna de matrícula; no investigado más a fondo, fuera de alcance de este
bloque.

**2 líneas con descripción vacía pero datos reales** (`id` 2050 y 2056,
expediente `6.20/28510.0136`, `precio_unitario = 9,29 €`, matrícula real, sin
`motivo_revision`). Distintas de las "filas fantasma" ya limpiadas en la
sesión anterior (CONTEXTO.md sección 29) — estas sí tienen precio, solo falta
el texto de descripción. Se verían como un hueco en el Excel.

### Precio adjudicado (derivado)

| | Cuenta | % |
|---|---:|---:|
| Con `precio_adjudicado` | 1.204 | 40,1% |
| Sin `precio_adjudicado` | 1.796 | 59,9% |

Desglose de las 1.796 sin derivar:

| Causa | Cuenta |
|---|---:|
| Sin `precio_unitario` (no hay de qué derivar) | 653 |
| Con `precio_unitario` pero sin `baja_lote` en la línea | 1.143 |
| Con ambos pero `precio_adjudicado` sigue NULL (posible bug) | **0** |

La derivación funciona de forma consistente allí donde tiene los dos
insumos — cero casos del tercer tipo. El cuello de botella real son las
1.143 líneas sin `baja_lote`: en su mayoría son líneas huérfanas sin lote
determinado (sección 5 abajo) y las de la "segunda familia de baja" (3
expedientes, sin baja única que aplicar por diseño — CONTEXTO.md sección 22).

### Revisión

`estado_revision`: las 3.000 líneas están en `sin_revisar` — esperable antes
de la entrega, nadie las ha tocado desde la cola de revisión todavía.

`motivo_revision` (el motor marca la línea): 1.113 de 3.000 (37,1%), agrupado:

| Motivo | Cuenta | Expediente(s) principal(es) |
|---|---:|---|
| "banda vacía: posible continuación de tabla partida..." | 797 | `0019` (656), `0117` (60), `0130` (37), `0203` (24), `0094` (20) |
| "ninguna cabecera LOTE N encontrada en la franja..." | 183 | mismo grupo |
| "la tabla se asocia al LOTE N, que no está entre los lotes adjudicados" | 128 | multi-lote con huecos de numeración |
| "cabecera desalineada con los datos (columnas desplazadas)" | 2 | recuperación de desalineación (sección 29) |
| "precio unitario no interpretable" | 2 | valor de celda ilegible |
| "valor de matrícula no reconocible, descartado: '***'" | 1 | `6.23/28510.0042` |

**El motivo "banda vacía" (797 líneas, 72% de las huérfanas) contradice la
medición de CONTEXTO.md sección 19** ("cero casos de banda vacía en el corpus
completo") — esa premisa ya no se sostiene con el corpus multi-lote actual:
un solo expediente, `6.25/28510.0019` (9 lotes), concentra 656 de los 797
casos. No bloquea nada nuevo (ese expediente ya está en revisión por
cobertura parcial de lotes), pero es una brecha documental real que vale la
pena anotar para una futura sesión sobre herencia de lote entre páginas.

### Precios anómalos

Cero precios en cero o negativos (`Numeric` nunca los guarda). 561 líneas
(18,7%) superan 10x o bajan de 0,1x la mediana de precio de su propio
expediente — pero **515 de las 561, muestreadas a mano sobre
`6.23/28510.0051`, son precios reales y dispares por naturaleza** (un desvío
completo de 325.426,97 € junto a un contracarril individual de 1.435,69 € en
el mismo lote) — heterogeneidad esperable de un catálogo de material
ferroviario, no errores. El umbral 10x/0,1x no es un buen discriminador de
anomalía en este corpus.

### Descripciones tipo cabecera/total

**Cero coincidencias reales** tras filtrar `TOTAL`, `SUBTOTAL`, `SUMA`, `BASE
IMPONIBLE`, `I.V.A`, `LOTE N` como descripción completa y longitud <4 — solo
capturó las 2 líneas de descripción vacía ya reportadas. Señal positiva: el
catálogo no trae ruido de tabla colado como material.

### Líneas duplicadas dentro del mismo lote

Mismo `codigo_precio` repetido en el mismo lote: 0 casos. **Misma matrícula +
misma descripción repetida en el mismo lote: 50 grupos, 108 líneas**,
concentradas en 4 expedientes: `6.23/28510.0018` (13 grupos/26 líneas),
`6.23/28510.0102` (13/26), `6.25/28510.0016` (13/26), `6.23/28510.0042`
(10/28). Los tres primeros coinciden con los 3 expedientes de "segunda
familia de baja" ya pendientes en CONTEXTO.md sección 22.

Verificado a mano un caso real (`6.23/28510.0018`, lote 10, matrícula
`601020180`, "CARRIL RN 45 BARRA 180 M..."): las dos filas vienen del mismo
documento (`ANEJO_1`) pero de páginas distintas (12 y 16), mismo precio
exacto (58,43 €) — una segunda tabla de características técnicas que repite
las mismas filas de material, esta vez con precio incluido (a diferencia del
caso ya documentado en CONTEXTO.md sección 17.2, donde la segunda tabla no
traía precio). No es un fallo de `_combinar_por_clave`: las dos filas tienen
`clave_linea` distinta (una con código de precio, otra sin él), así que el
mecanismo de deduplicación por clave nunca las ve como la misma fila —
producen una línea de catálogo duplicada de verdad, visible en el Excel como
dos filas con el mismo material y precio.

### Resumen del bloque 2

El grueso del catálogo está sano: sin ceros/negativos, sin cabeceras coladas
como material, ninguna duplicación por fallo de fusión en sentido estricto.
Dos brechas que sí vale la pena mirar antes de entregar: (a) 108 líneas
duplicadas reales visibles en el Excel; (b) el 37% de líneas con
`motivo_revision` está dominado por un solo expediente cuya premisa de diseño
ya no aplica al corpus actual. Los "outliers de precio" y el bajo relleno de
matrícula no son señales de error, son la naturaleza heterogénea del catálogo.

---

## Bloque 3 — Repaso del estado general

### Parte A — Los 7 `completado`, uno a uno

| Expediente | Baja/importes en DB | Verificado contra el documento real | Resultado |
|---|---|---|---|
| 6.23/28510.0104 | 20,00% · 55.400/55.400 € | Anuncio PCSP contiene "20" y "55.400" | **OK** |
| 6.24/28510.0008 | 54,00% · 138.000/138.000 € | Adjudicación contiene "54" y "138.000" | **OK** |
| 6.24/28510.0047 | 0,13% · 59.880/59.880 € | La baja vive en la Propuesta DT, no en el mismo documento que los importes — ambos confirmados por separado | **OK** |
| 6.24/28510.0116 | 46,50% · 1.485.000/1.485.000 € | **Discrepancia real**: Propuesta LC.27 declara 47,87%, Contrato firmado declara 46,50%. La BD usa el 46,50% del Contrato. Importes coinciden en ambos documentos. | **Ver nota** |
| 6.24/28510.0128 | 0,20% · 150.000/(sin adjudicación) | Adjudicación contiene "0,20" y "150.000"; `importe_adjudicacion` NULL sin investigar por qué (no bloquea `completado`, criterio del cliente sección 26) | **OK en lo verificado** |
| 6.24/28510.0180 | 24,99% · 2.250.000/2.250.000 € | Adjudicación contiene "24,99" y "2.250.000" | **OK en baja/importe** (ver hallazgo `codigo_precio` corrupto) |
| 6.24/28510.0185 | 39,00% · 2.500.000/2.500.000 € | Adjudicación contiene "39" y "2.500.000" | **OK** |

**Nota sobre `6.24/28510.0116`**: no es un bug de extracción — los dos
números están literalmente en dos documentos reales distintos del mismo
expediente. CONTEXTO.md sección 17 documenta una regla de prioridad para el par
Propuesta LC.27 / Resolución de Adjudicación ("preferir la Resolución,
CONTEXTO.md sección 17"), pero **no documenta explícitamente una prioridad
Contrato-vs-Propuesta**. Es plausible que el Contrato (acto más definitivo)
sea el correcto, pero **antes de usar este expediente como ejemplo en la
demo, confirmar con el cliente** — 47,87% vs 46,50% sobre 1.485.000 € no es
ruido de redondeo.

**Hallazgo nuevo — `codigo_precio` corrupto por el pie de página invertido**:
28 líneas de catálogo (2 expedientes: `6.23/28510.0042`, 21 líneas;
`6.24/28510.0180`, 7 líneas — uno de los 7 `completado`) tienen el texto del
pie de verificación CSV del documento, invertido carácter a carácter,
concatenado delante del código real (p. ej. `j.adilav/vscPN005`). El precio y
la cantidad de esas líneas están limpios; solo el código, y **no dispara
`motivo_revision`** — se exportaría al Excel tal cual sin que nadie lo note.

### Parte B — Los 31 `pendiente_revision`, agrupados por motivo

| Grupo | Expedientes | Correcto por diseño / Pendiente |
|---|---:|---|
| Matriz de acuerdo marco `sin_publicar` | 8 | **Correcto por diseño** (CONTEXTO.md sección 22) |
| Documento escaneado, sin capa de texto | 1 (`6.20/28510.0136`) | **Correcto por diseño**, fuera de alcance sin OCR (sección 15) |
| Segunda familia de baja (sin baja declarada en ningún documento) | 3 (`0018`, `0102`, `0016`) | **Trabajo pendiente real** — sin diseñar cómo modelarla |
| Cobertura parcial de lotes multi-lote | 12 | **Correcto por diseño** (sección 27), causa de fondo es de origen de datos |
| "No se extrajo ninguna línea de catálogo" | 2 (`0025`, `0193`) | **Trabajo pendiente, sin investigar** (secciones 16/22) |
| Tablas huérfanas / banda vacía, sin cobertura parcial | 3 (`0094`, `0117`, `0203`) | **Correcto por diseño** (sección 19, sin lote centinela) |
| Celdas con valor no interpretable | 2 (`0042`, `0187`) | **Correcto por diseño** (sección 26) |

**26 de 31 son comportamiento correcto ya documentado; 5 son trabajo
pendiente real** (3 de la segunda familia de baja + 2 sin ninguna línea
extraída) — coincide con lo que CONTEXTO.md ya tenía anotado, sin motivos
nuevos no documentados.

### Parte C — Trazabilidad: 10 líneas al azar

10 líneas (`ORDER BY random() LIMIT 10`), 6 expedientes y 6 documentos de
origen distintos. Para cada una se abrió el PDF real en la página indicada
con `pdfplumber` y se confirmó que la cifra clave del `fragmento` (precio
unitario) aparece en el texto de esa página real.

**10 de 10 aciertan.**

### Parte D — Batería de tests

`pytest -q` dentro de `adif-api-1`: **261 passed, 1 warning (deprecación de
PyPDF2, sin relación con la lógica del proyecto), 0 fallos**, en 40 s.

---

## Verificación del punto 0 (cambios de la sesión anterior)

El commit `3c0d344` ("Expedientes: agrupa los no publicados, aparte y
plegados") ya estaba aplicado y desplegado antes de empezar esta sesión —
verificado que `adif-web-1` sirve el bundle con el marcador `grupo-no-publicados`
y que la página renderiza el grupo plegado "N expedientes no publicados". No
se ha necesitado ningún cambio adicional.
