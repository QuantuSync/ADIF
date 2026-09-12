# Sesión 2026-09-12 — defecto de mapeo sin cabecera, barrido de calidad, repaso de interfaz, rendimiento

Sesión larga con encargo en cinco bloques, continuada el mismo día con dos
bloques más (6 y 7) sobre dos de los hallazgos que el bloque 4 y el bloque 2
habían dejado sin implementar. Resumen ejecutivo en `CONTEXTO.md` sección 16
(pendientes); aquí el detalle completo, cifras y verificación.

---

## Bloque 1 — El defecto de mapeo sin cabecera (cerrado)

**Síntoma reportado por la auditoría:** 4 grupos duplicados y 14 líneas sin
descripción en `6.22/28510.0094` y `6.22/28510.0126`.

**Causa raíz, verificada contra el PDF real** (documento compartido entre
ambos expedientes hermanos, `ANEJO_53d9b3928f16babb.pdf`, página 5, tabla sin
cabecera propia de 44 filas): en 7 de esas 44 filas (P-095 a P-102),
`pdfplumber` fusiona la columna en blanco intermedia con la de descripción
para esa fila concreta — el resto de la tabla trae
`[código, matrícula, '', descripción, '', unidad, ...]`, pero en esas 7 filas
sale `[código, matrícula, descripción, None, None, unidad, ...]`: el texto
real cae UNA COLUMNA A LA IZQUIERDA de donde el mapeo (derivado del
contenido mayoritario de la tabla, `derivar_mapeo_por_contenido`) lo espera,
y tanto la columna de descripción como la siguiente quedan en `None` en vez
de `''`.

`derivar_mapeo_por_contenido` no lo distingue: la columna con el texto
desplazado solo tiene 7/44 valores (16%, bajo `_UMBRAL_RELLENO_MINIMO`), así
que se clasifica "vacía" y el mapeo se deriva correctamente para el 84% de
las filas, dejando las 7 restantes sin ninguna recuperación existente que
las cubriera: `_recuperar_descripcion_columna_fantasma` solo miraba la
columna SIGUIENTE (no la anterior), y `_recuperar_descripcion_ultimo_recurso`
exige que la fila tampoco tenga matrícula, condición que no cumplen P-101 y
P-102 (matrícula real, 618050300/618050301).

**Arreglo, acotado:** `_recuperar_descripcion_columna_fantasma_anterior`
(`engine/app/catalogo.py`), imagen especular de la función existente, con
guarda de ambigüedad: solo se activa si la columna siguiente a la de
descripción TAMBIÉN está vacía y sin reclamar por otro campo del mapeo — la
huella real del colapso, verificada contra el PDF. Sin esa guarda, dos tests
ya existentes (partida alzada con texto en la columna anterior,
`6.25/28510.0213`; fila con dos candidatas ambiguas) pasaban a recuperar mal
o a adivinar entre candidatas — el guard los mantiene intactos.

**Verificado contra el stack real:**
- Reproceso de ambos expedientes: 0 líneas sin descripción, 0 grupos
  duplicados (antes: 14 y 4 respectivamente) en el documento compartido.
- Auditoría automática (`POST /mantenimiento/auditoria/ejecutar`): pasa de
  tener hallazgos de gravedad "error" para este caso a **0 errores**, solo
  los 4 avisos informativos ya conocidos de antes (huérfanas sin lote,
  precio desproporcionado, cantidad con forma de año, importe de licitación
  compartido entre expedientes de la misma sindicación).
- 661 tests (660 previos + 1 nuevo con la fila real de P-101), todos verdes.

Commit `8a32400`.

---

## Bloque 2 — Barrido de calidad del catálogo (medido; una parte cerrada, dos anotadas)

Catálogo en el momento del barrido: 22.363 líneas. Script de medición en
`docs/` no se conserva (era de un solo uso, scratchpad de sesión) — cifras y
metodología aquí.

### 1. Descripciones que parecen cabecera/total/nota al pie

**0 líneas.** El vocabulario de pies de tabla (`_ETIQUETAS_PIE_TABLA`) y el
descarte de fila pie-de-tabla ya cubren esto con solidez — nada que
corregir.

### 2. Precios idénticos repetidos muchas veces dentro del mismo expediente

**590 grupos** (umbral: mismo precio ≥6 veces en el mismo expediente).
Revisados los mayores: concentrados en las familias ya conocidas y
legítimas del corpus — `6.23/28510.0051`/`0060` (balasto, precios de
referencia por tonelada que se repiten entre partidas del mismo lote) y
`6.22/28510.0122`/`0155`/`0156` (carril, matrículas y precios de referencia
compartidos entre expedientes hermanos, ya documentado en la sesión de
descubrimiento inverso). No es indicio de columna mal leída en estos casos.
**Sin corregir, no hace falta.**

### 3. Cantidades implausibles más allá de "forma de año"

**47 líneas**, 44 de ellas en el trío ya conocido y contaminado
`6.20/28510.0042`/`0046`/`0047` (referencia normativa leída como cantidad,
CONTEXTO.md sección 16 — ya excluidas del Excel por el mecanismo de mapeo
incoherente). Las 3 restantes: `T x km de balasto transportado` con
cantidad ~1.180.000 — plausible para una unidad tonelada-kilómetro de
transporte a granel, no un defecto. **Sin corregir, ninguna lo necesita.**

### 4. Códigos de precio con formato desconocido — defecto real confirmado, anotado para decisión

**1.137 líneas en 15 expedientes.** El grueso (771 líneas, 8 expedientes
confirmados con `codigo_precio = matricula` exactamente) es una variante NO
cubierta de la confusión matrícula/código-de-precio que
`corregir_confusion_matricula_codigo_precio` ya corrige para otro patrón.

**Causa raíz localizada** (verificado contra
`6.22_28510.0058/ANEJO_a9e7c95651661aad.pdf` p.15, tabla real de tornillería
sin cabecera propia, sin columna de código de precio, solo matrícula): el
precio de esta tabla no lleva el símbolo `€` en la celda (`'7,40'`, no
`'7,40 €'`), y `_clasificar_columna`
(`app/extraccion/firma_estructural.py`) solo reconoce una columna como
"precio" cuando contiene `€` — así que `derivar_mapeo_por_contenido` nunca
encuentra ninguna columna de precio en esta tabla (`indices_precio == []`) y
descarta la derivación por contenido entera, cayendo al modelo. Por qué el
modelo + `corregir_confusion_matricula_codigo_precio` tampoco lo resuelven
para este caso concreto no se rastreó hasta el final en el tiempo de esta
sesión (requeriría una llamada real al modelo con logging para capturar el
mapeo exacto que produce sobre esta forma de tabla).

**Por qué no se fuerza un arreglo ahora:** el mecanismo exacto por el que la
corrección existente no ataja este caso no está confirmado con certeza —
119 líneas / 8 expedientes es un alcance acotado (no se ha extendido, ni
crecerá silenciosamente), y un cambio a ciegas en `_parece_precio` (aceptar
cualquier número con coma decimal, no solo con `€`) tiene riesgo real de
falsos positivos ya documentado en el propio código (`0,11-CR-D` como parte
de una designación técnica se parece a un decimal sin ser un precio).

**Propuesta para una sesión dedicada:** (a) trazar con logging una llamada
real al modelo sobre esta tabla para ver el mapeo exacto que produce y
extender `corregir_confusion_matricula_codigo_precio` a ese patrón
concreto, o (b) enseñar a `_clasificar_columna` a reconocer un precio sin
`€` con una segunda señal más segura que "tiene coma decimal" (p. ej.
"todos los valores de la columna interpretan con `parsear_importe_es` sin
excepción, Y la columna vive junto a `cantidad`/`unidad` ya identificadas
con seguridad").

Además, **`6.24/28510.0184` (57 líneas, contrato de equipamiento
telefónico)**: `precio_unitario=1,00€` idéntico en todas las líneas
(coincide con el valor de la columna "Cantidad Estimada", no con un precio
real) y `unidad_medida` con referencias de fabricante
(`"L30220-D600-B151"`) en vez de una unidad — verificado contra el PDF
(`CONTRATO_b15b77d1fff4f23f.pdf` p.97): la cabecera real de esa tabla es
`Matrícula | Designación | REFERENCIA DEL FABRICANTE | Precio Referencia
Adquisición | Precio Referencia Reparación | Cantidad Estimada`, con las DOS
columnas de precio vacías en el 100% de las filas del documento (dato
genuinamente ausente en el origen, no un fallo de lectura). Hay **7
variantes de esta misma familia de cabecera ya cacheadas**
(`cache_mapeo_cabecera`, firmas 76/160/165/166/167/168/176) con mapeos
inconsistentes entre sí — al menos una asigna `precio_unitario` a la
columna de cantidad. Cerrar esto bien exige auditar las 7 entradas contra
sus documentos reales y decidir, como cuestión de producto, qué hacer con
un equipo sin precio unitario real en el origen (`precio_unitario = None` y
fuera del Excel entregable, o marcado a revisión) — **no forzado en esta
sesión.**

### 5. Descripciones truncadas a mitad de palabra

**Heurística probada, descartada por poco fiable.** Un regex simple
("termina en minúscula, sin puntuación") marcó 2.362 líneas — casi todas
descripciones reales y completas en español, que legítimamente terminan en
minúscula ("Balasto sobre camión en cantera", "Remonte de balasto"). Sin una
señal más fuerte (comparar contra el `fragmento` crudo, o contra el ancho de
columna real de la tabla) esta comprobación genera casi solo falsos
positivos. **No se reporta como recuento fiable — decisión pendiente si
merece una heurística mejor o se descarta.**

### 6. Precio adjudicado no cuadra con `unitario × (1 − baja)`

**0 líneas.** El recálculo de `precio_adjudicado`/`baja_lote` en cada pasada
(sesión 2026-09-09, bloque 3) sigue siendo consistente al 100% contra las
22.363 líneas reales.

---

## Bloque 3 — Repaso de la interfaz (cerrado, un hallazgo corregido)

Repaso con datos reales (delegado a un sub-agente de solo lectura, sin
tocar el aspecto visual):

1. **Catálogo a 1280px, 19.949+ líneas, 17 columnas** — ya resuelto en una
   sesión anterior de pulido. La tabla web muestra 11 columnas (el resto
   vive en el panel de detalle/trazabilidad); paginación de servidor; CSS
   dedicado (`globals.css`, sección "pulido de 1280px") con guardas
   explícitas contra un `codigo_precio` corrupto rompiendo el layout. Sin
   defecto.
2. **Columnas del documento vs. columnas de cruce** — sin mezcla real, pero
   sin distinguir visualmente tampoco: `codigo_interno`/`codigo_matriz`
   (cruce) aparecen en el panel de detalle como pares sueltos, igual que el
   resto. Anotado como pulido menor opcional (una subcabecera "Cruce con el
   Excel de códigos"), no un defecto.
3. **Cola de candidatos de matrícula** — `GET /revision/candidatos-matricula`
   responde en 62ms sobre 9.105 candidatos reales / 1.387 pendientes;
   despacho de 1 clic (aceptar/rechazar/pendiente + nota). Sin defecto.
4. **Mantenimiento/revisión/expedientes** — las cinco pantallas usan
   `useReintentoConexion` de forma consistente (cargando/confirmado/error);
   sin regresión.
5. **Avisos de la ingesta local, solo en la API — confirmado y corregido.**
   `aviso_sindicacion`, `aviso_ingesta_manual` y
   `aviso_conflicto_documento_manual` existían en `schemas.py` desde
   sesiones anteriores pero solo `aviso_descubrimiento_pedidos` se pintaba
   en la web. Añadidos los tres a `ExpedientesPanel.tsx` con el mismo
   patrón visual (`status-note`). Verificado contra el HTML servido por el
   contenedor real: los avisos de sindicación reales de expedientes como
   `6.25/28510.0150` ya aparecen.

Commit `980f124`.

---

## Bloque 4 — Rendimiento (analizado, nada implementado por encargo explícito)

**Método:** perfil real (`cProfile`) sobre una muestra de 8 expedientes ya
descargados, llamando directamente a `ejecutar_extraccion_expediente` (sin
pasar por la cola, sin red) — reprodujo con precisión el orden de magnitud
observado en producción. Una segunda muestra de 20 expedientes, estratificada
por número de páginas, midió tiempos por expediente: de 0,27s (2 páginas,
ninguna tabla) a 64s (39 tablas, 6 llamadas al modelo).

**Desglose de tiempo, muestra de 8 expedientes, 231,9s totales:**

| Etapa | Tiempo | % |
|---|---|---|
| `pdfplumber` texto plano (`page.extract_text()`, vía `app.extraccion.texto.extraer_texto`, llamado desde `_clasificar_documentos`, etapa 1 de la cascada) | ~230s | **~99%** |
| Extracción de tablas (`find_tables` + `table.extract()`, etapas 3-4, solo páginas candidatas) | 2,3s | 0,4% |
| Localización de tablas (`find_tables`) | 1,5s | 0,3% |
| Llamadas al modelo (etapa 5) | 0,05s | 0,02% |
| Escritura en base de datos (`commit`/`flush`) | 0,8s | 0,3% |
| Apertura de PDF (`pdfplumber.open`) | 0,25s | 0,1% |

**Hallazgo central, contrario a la intuición de partida:** el cuello de
botella NO es la extracción de tablas, ni el modelo (que ya llama poquísimo,
tal como CONTEXTO.md sección 6 busca), ni la base de datos — es la
extracción de **texto plano de cada página de cada documento**, para la
clasificación de plantilla (etapa 1 de la cascada) y la localización de
campos de etiqueta fija. `page.extract_text()` de `pdfplumber` hace un
análisis de layout completo del stream de contenido del PDF
(`pdfminer.pdfinterp.execute` → tokenizador de PostScript,
`psparser.nextobject`/`nexttoken`, millones de llamadas en documentos
grandes) — mucho más caro por página que `find_tables()`, y se ejecuta
**sobre TODAS las páginas de TODOS los documentos**, no solo sobre las que
traen un cuadro de precios. Un expediente con `tablas=0` (ninguna tabla
procesada) puede tardar 30 segundos solo en esta etapa si sus documentos son
grandes.

**Confirma la cifra reportada:** el corpus activo tiene 928 documentos /
35.315 páginas en 358 expedientes (98,7 páginas/expediente de media). A
~29s/expediente medidos en la muestra estratificada, 358 expedientes ≈ 2,9
horas — coincide con las "tres a cuatro horas" reportadas, confirmando que
la muestra es representativa y que el texto plano explica prácticamente
todo el tiempo.

**Propuestas, sin implementar (para decidir en otra sesión):**

1. **Caché de texto extraído por hash de documento** — mismo principio que
   ya usa `cache_mapeo_cabecera` para el modelo: un documento ya
   descargado y sin cambios no debería volver a pagar el coste de
   `extract_text()` en cada reproceso. Es la mejora de mayor impacto y
   menor riesgo: no cambia ningún resultado de clasificación/extracción,
   solo evita repetir un trabajo idéntico. Ataca directamente el caso que
   más duele hoy — el reproceso completo forzado.
2. **Evaluar una librería de texto plano más rápida solo para
   clasificación** (p. ej. PyMuPDF/`fitz`, habitualmente 10-20× más rápida
   que `pdfminer` para texto sin necesidad de geometría de tabla) —
   manteniendo `pdfplumber` para la extracción de tablas, que sí depende de
   su geometría limpia (CONTEXTO.md sección 3). Requiere verificar contra
   el corpus real que no cambia qué marcadores se detectan antes de
   adoptarla.
3. **Acotar cuántas páginas hace falta leer para clasificar** — si los
   marcadores de plantilla y los campos de etiqueta fija aparecen siempre
   dentro de un prefijo de páginas por familia de documento, evitar leer el
   documento entero. Necesita verificación contra el corpus por familia
   antes de confiar en ello (no todos los marcadores están garantizados
   cerca del principio).
4. **Paralelizar la extracción de texto** dentro del propio worker (pool de
   procesos para las páginas, ortogonal a "un solo worker en serie" —
   no añade servicios ni colas nuevas).

**Nota de paso, no pedida pero medida:** exportar el Excel completo
(22.363 líneas) tarda 99s (`GET /catalogo/exportar.xlsx`) — no es el foco de
este bloque, pero queda anotado si el Excel llega a pedirse con más
frecuencia.

---

## Bloque 5 — Cierre

- **Auditoría automática final:** 0 errores, 4 avisos informativos (todos ya
  conocidos y catalogados en sesiones anteriores: huérfanas sin lote 2.100,
  precio desproporcionado 1.663, cantidad con forma de año 401, importe de
  licitación compartido entre expedientes de la sindicación 31 grupos).
- **Excel exportado:** hoja "Materiales" 19.968 filas × 17 columnas, hoja
  "Resumen" con 2.395 pendientes de revisión (motivos desglosados: 1.143
  tabla que parece continuar de página sin lote confirmable, 579 sin lote
  cercano en el documento, 378 lote mencionado no coincide con los
  confirmados, 295 mapeo incoherente sin cabecera). 19.968 + 2.395 = 22.363,
  cuadra exacto con la base de datos.
- **Comparación con el estado anterior** (cierre de sesión 2026-09-10,
  `docs/sesion-2026-09-10-maestro-materiales-real.md`): catálogo
  21.892 → 22.363 líneas (+471); Excel "Materiales" 18.857 → 19.968 filas
  (+1.111, más que el crecimiento bruto del catálogo porque el arreglo del
  Bloque 1 mueve líneas de "pendiente"/duplicado a "Materiales" limpio, no
  solo por expedientes nuevos); 358 expedientes activos, sin cambio (mismo
  corpus, sin nuevos descubrimientos de sindicación en el intervalo).

### Pendiente al cerrar el bloque 5 (resuelto más abajo, bloques 6 y 7)

- Bloque 2, punto 4: confusión matrícula/código-de-precio en tablas sin
  cabecera cuyo precio no lleva `€` (8 expedientes, 771 líneas) — causa
  parcialmente localizada (`_parece_precio` ciego a precios sin símbolo de
  moneda), corrección exacta sin confirmar. **Cerrado, bloque 7.**
- Bloque 4: cuatro propuestas de rendimiento analizadas y priorizadas
  (caché de texto por hash de documento es la de mejor relación
  impacto/riesgo), ninguna implementada por encargo explícito de la sesión.
  **Implementada, bloque 6.**

---

## Bloque 6 — Caché de texto extraído por hash de documento (cerrado)

Implementa la propuesta 1 del bloque 4. `CacheTextoDocumento` (migración
0029), clave `Documento.hash` (contenido, no id ni ruta), invalidable
subiendo `VERSION_LOGICA_TEXTO` (`app.extraccion.texto`) sin borrar
filas a mano -- una fila con versión distinta a la actual se trata como
caché ausente y se recalcula. `extraer_texto_cacheado` recibe una función
(`obtener_pdf`), no el PDF ya en mano: en un acierto de caché ni siquiera
se lee el fichero del almacenamiento.

**Segunda causa encontrada verificando el efecto real, que la caché sola no
bastaba para arreglar:** `procesar_anejo` (etapas 3-6, mapeo y extracción de
tablas) volvía a extraer el texto de cada página con `pdfplumber` por su
cuenta, para localizar páginas candidatas (etapa 3) -- exactamente el mismo
trabajo que `_clasificar_documentos` (etapa 1) ya había hecho segundos antes
para clasificar la plantilla, sin reutilizarlo. Confirmado con `cProfile`
sobre un expediente aislado ya con la caché caliente: `page.extract_text()`
seguía apareciendo 101 veces, 55,2s de 55,6s totales (99%), llamado desde
`pipeline_anejo.py`, no desde la caché. Corregido: `procesar_anejo` recibe
ahora el texto ya extraído del llamador (`item.paginas`) en vez de
recalcularlo -- sigue abriendo el PDF con `pdfplumber` (`ruta_pdf`), pero
solo para la geometría real de las tablas, nunca para su texto.

**Medido con un reproceso real** (perfil directo sobre los mismos 20
expedientes estratificados del bloque 4, sin red, `IDS_MUESTRA` idéntico
antes y después):

| Pasada | Tiempo total (20 expedientes) | Tiempo medio/expediente |
|---|---|---|
| Antes (bloque 4, doble extracción, sin caché) | 497-519s | ~25s |
| Después, caché en frío (recién poblada, ya sin doble extracción) | 308,2s | 15,4s |
| Después, caché en caliente (segundo reproceso, mismos documentos) | **29,6s** | **1,5s** |

**10,4× más rápido** en caliente frente al "antes". Extrapolado a los 358
expedientes activos (98,7 páginas/expediente de media): de las 3-4 horas
reportadas a **~9 minutos** con la caché ya poblada -- el primer reproceso
tras desplegar esto sigue costando lo de siempre menos la mitad (~1,5h,
al eliminar solo la extracción duplicada), pero cada reproceso posterior
sobre los mismos documentos es casi gratis en esta etapa. En la pasada
caliente, `find_tables()` (localizar tablas dentro de las páginas
candidatas, trabajo real que sigue haciendo falta) pasa a ser el coste
dominante (71,7%, 21,2s) -- ya no hay ningún "otros" sin explicar.

**Verificado:**
- 665 tests (661 + 4 nuevos), todos verdes.
- Camino real de la cola (`POST /expedientes/{id}/extraer`, recogido por
  el worker): completa correctamente con la caché activa.
- Auditoría automática tras varios reprocesos repetidos de la misma
  muestra: 0 errores, mismos 4 avisos de siempre.
- Catálogo estable en 22.363 líneas pese a reprocesar la misma muestra de
  20 expedientes cuatro veces seguidas (dos en el bloque 4, dos aquí) --
  sin duplicar nada (CONTEXTO.md sección 9.9).
- `6.22/28510.0094` (bloque 1) sigue con 0 líneas sin descripción tras
  este cambio: la caché de texto no altera ningún resultado, solo evita
  recalcularlo.

Commit `afb11af`.

---

## Bloque 7 — Confusión matrícula/código de precio sin símbolo `€` (cerrado)

**Diagnóstico terminado.** `_clasificar_columna`
(`app.extraccion.firma_estructural`) solo reconocía una columna como
"precio" si sus valores contenían el símbolo `€`. Verificado contra el PDF
real (`6.22_28510.0058/ANEJO_a9e7c95651661aad.pdf` p.15, tornillería: precio
"7,40", "5,03"... sin `€`): `clasificar_columnas` etiquetaba esa columna
como "codigo_repetido" en vez de "precio", así que `derivar_mapeo_por_
contenido` nunca encontraba ninguna columna de precio
(`indices_precio == []`) y se rendía sin más -- la tabla caía siempre al
modelo. Trazado en vivo (llamada real al modelo sobre esta tabla exacta):
el modelo devolvió `codigo_precio` apuntando a la propia columna de
matrícula, y aunque `corregir_confusion_matricula_codigo_precio` sí lo
arregla cuando se dispara, la vía de fondo seguía siendo no determinista
-- exactamente el riesgo que el propio código ya documentaba ("el modelo
puede producir variantes distintas... en otro reproceso").

**Arreglo, criterio estructural sin símbolo de moneda:** `_PRECIO_SIN_
SIMBOLO_RE` (`^\d{1,3}(?:\.\d{3})*,\d{2}$`) exige que la celda ENTERA sea
un número con la gramática monetaria española -- grupos de miles de
exactamente 3 dígitos y EXACTAMENTE dos decimales tras una coma. Verificado
que no confunde los dos casos reales ya conocidos que motivaron dejar
`_parece_precio` en solo-€: una designación técnica con coma decimal
embebida ("DS-B1-54-320/230-0,11-CR-D", el ancla `^...$` exige que no
sobre nada tras los decimales) y una cantidad con separador de miles pero
sin decimales ("1.200", "70.000", sin coma). Con esto,
`derivar_mapeo_por_contenido` resuelve la tabla de tornillería entera de
forma determinista, sin llamar al modelo en absoluto. Si una columna de
cantidad real usara alguna vez decimales con coma, quedaría ambigua entre
"precio" y "cantidad" -- `derivar_mapeo_por_contenido` ya exige exactamente
una columna de tipo "precio" y se rinde ante dos, así que esa ambigüedad
cae a revisión sin adivinar, nunca a una asignación equivocada (mismo
principio pedido: "donde no se pueda distinguir con certeza, a revisión").

**Reprocesados los 8 expedientes afectados, efecto medido:**

| Expediente | Líneas con `codigo_precio = matrícula` antes | Después |
|---|---|---|
| `6.22/28510.0033` | 217 | **0** |
| `6.22/28510.0057` | 217 | **0** |
| `6.22/28510.0058` | 217 | **0** |
| `6.24/28510.0184` | 41 | 41 (sin cambio, ver nota) |
| `6.21/28510.0097` | 5 | 5 (sin cambio, ver nota) |
| `6.21/28510.0148` | 5 | 5 (sin cambio, ver nota) |
| `6.21/28510.0149` | 5 | 5 (sin cambio, ver nota) |
| `6.24/28510.0173` | 5 | 5 (sin cambio, ver nota) |
| **Total** | **712** | **61** (-651, -91%) |

Los 3 expedientes principales (651 de las 712 líneas, 91%) quedan resueltos
del todo, sin ninguna línea de mapeo incoherente restante y sin depender del
modelo. Verificado también que las 392 líneas de cada uno de esos tres
expedientes (comparten el mismo documento, mismo patrón que el bloque 1)
salen ahora idénticas entre sí, con `codigo_precio` propio y `matricula`
propia, cada una en su columna real.

**Las 61 líneas restantes NO son el mismo defecto, sin tocar en esta
sesión:**
- `6.24/28510.0184` (41 líneas): la familia de cabeceras de equipamiento de
  telecomunicaciones sin precio real en el origen (ver bloque 2 arriba) --
  causa distinta (el documento no declara ningún precio en absoluto), fuera
  del alcance de este arreglo por diseño, sigue pendiente de decisión de
  producto.
- Los 4 expedientes de 5 líneas cada uno (`6.21/28510.0097`/`0148`/`0149`,
  `6.24/28510.0173`): **hallazgo nuevo de esta sesión**, verificado contra
  el PDF real (`6.21_28510.0149/CONTRATO_7e00edb20395e753.pdf` p.124/127):
  la tabla que trae la matrícula y la descripción es una de
  "características técnicas" sin ninguna columna de precio
  (`[matrícula, "", "", descripción, criterios_técnicos]`) -- el precio que
  aparece en el catálogo para esas matrículas viene de OTRA tabla del
  documento, no de esta. Patrón distinto de "precio sin símbolo", sin
  diagnosticar del todo en el tiempo de esta sesión: anotado para una
  sesión futura, no forzado aquí.

**Verificado:**
- 669 tests (665 + 4 nuevos), todos verdes.
- Auditoría automática tras el reproceso: 0 "error" nuevos de sustancia --
  el único hallazgo nuevo (`lineas_cambian_sin_cambiar_documentos`, 3
  expedientes) es la propia auditoría detectando, correctamente, que estos
  3 expedientes cambiaron de contenido sin cambiar de documento: es
  exactamente el efecto esperado de este arreglo (líneas antes descartadas
  por "mapeo incoherente" ahora se resuelven bien), no un defecto nuevo --
  confirmado revisando que ya no queda ninguna línea con ese motivo en los
  tres expedientes.
- Catálogo: 22.363 → 22.438 líneas (+75, coherente con líneas antes
  excluidas por mapeo incoherente que ahora se incluyen correctamente).
