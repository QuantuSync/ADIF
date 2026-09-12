# Sesión 2026-09-12 (continuación) — huecos reales, confusión matrícula/precio, determinismo, ingesta local

Sesión larga en seis bloques, continuación de la sesión del mismo día
(`sesion-2026-09-12-defecto-mapeo-calidad-interfaz-rendimiento.md`).
Resumen ejecutivo en `CONTEXTO.md` sección 16; aquí el detalle completo,
cifras y verificación.

---

## Bloque 1 — Análisis de los 1.886 huecos reales (solo análisis, sin tocar código)

Catálogo en el momento del análisis: 22.438 líneas, 2.489 pendientes (603
duplicado exacto ya separado + 1.886 con hueco real: banda vacía 954, lote
no registrado 378, mapeo incoherente 314, ninguna cabecera 240).

**Concentración extrema, no repartida.** Las 1.886 líneas caen en solo 32
expedientes. El 72,4% (1.365 líneas) está en dos tríos de expedientes
hermanos:

| Familia | Expedientes | Líneas | % del total |
|---|---|---|---|
| Carril (SCI) | `6.22/28510.0122`, `0155`, `0156` | 915 | 48,5% |
| Acuerdo marco vía | `6.24/28510.0130`, `0152`, `0153` | 450 | 23,9% |

**Patrón estructural encontrado, verificado contra la base de datos real**
(`lote_id`, `lotes.identificador_lote`, precios):

- Familia `0130/0152/0153`: cada expediente declara sus lotes propios como
  4/5/6, pero su `ANEJO_1` trae el cuadro de precios íntegro de **todos**
  los lotes del acuerdo marco -- las tres categorías de motivo para esta
  familia son, verificado línea a línea, el mismo fenómeno: contenido de
  lotes ajenos, no un hueco de extracción.
- Mismo patrón confirmado en la familia del balasto (`6.25/28510.0027`,
  `0028`, `0080`): "LOTE 5" consistentemente ausente en varios expedientes
  distintos que declaran lotes {1,2,3,4,6,7} -- contenido de otro pedido
  del mismo marco, no un error de registro.
- Familia `0122/0155/0156`: la tabla repite el mismo material tres veces
  -- dos copias correctamente resueltas con lote (814 líneas) y una
  tercera sin cabecera cercana, con un precio ligeramente distinto (~0,27%)
  al de las copias resueltas -- probablemente una tabla de referencia
  distinta de la de pedido, genuinamente ambiguo, no se fuerza un lote
  (mismo riesgo ya descartado con el balasto, CONTEXTO.md sección 16).

**Calidad del dato:** no es ruido de tabla. 87-98% de las líneas puntúan
2-3 de 4 en completitud (identificador + cantidad + unidad + precio); 0
líneas sin matrícula y sin descripción a la vez en ninguna categoría. El
problema es de atribución de lote, no de lectura.

**Límite de origen, sin arreglo posible:** `6.20/28510.0042/0046/0047` (84
líneas, trío ya conocido y contaminado, excluido por diseño) y la familia
`0130/0152/0153` (450 líneas, estructuralmente no son de este expediente).

**Con trabajo real pendiente, acotado:** `6.22/28510.0094/0125/0126` (170
líneas, mapeo incoherente más allá del desplazamiento puntual ya cerrado
en el bloque 1 de la sesión anterior) y `6.22/28510.0033/0057/0058` (36
líneas, "ninguna cabecera", residuo menor tras el bloque 7 de la sesión
anterior).

---

## Bloque 2/3 — Las 61 líneas del bloque 7 y las 57 de equipamiento sin precio (cerrado en gran parte)

Las dos tareas se solapaban por completo en `6.24/28510.0184` y se
resolvieron juntas. Tres causas reales distintas, verificadas contra el
PDF antes de tocar código:

### Causa 1 — precio_unitario mapeado a la columna de cantidad

`6.24/28510.0184_CONTRATO_b15b77d1fff4f23f.pdf` p.96-98: tabla de
equipamiento de telecomunicaciones ("REFERENCIAS PARA SUMINISTRAR Y/O
REPARAR..."), columnas Matrícula/Designación/Referencia fabricante/**Precio
Referencia Adquisición**/**Precio Referencia Reparación**/Cantidad
Estimada -- verificado con `pdfplumber.find_tables()` directo que las dos
columnas de precio están **vacías en el 100% de las filas reales**: el
documento no declara precio para este material, confirmado, no una
sospecha. Sin más pista que 2-3 filas de ejemplo, el modelo mapeaba
`precio_unitario` a la columna de cantidad ("1" repetido), produciendo un
"precio" de 1,00 € idéntico en cada fila.

Arreglo: `corregir_confusion_precio_cantidad` (determinista, usa
`clasificar_columnas` ya existente) descarta esa asignación cuando la
columna no tiene forma de precio real. `evaluar_coherencia_mapeo` se
relaja para aceptar `precio_unitario` sin columna **solo** cuando
`clasificar_columnas` confirma que ninguna columna de la tabla tiene forma
de precio -- nunca tapa el caso real ya cubierto donde sí existe una
columna de precio y el mapeo simplemente no la encontró
(`6.20/28510.0042/0046/0047`).

### Causa 2 — confusión matrícula/código-precio también con cabecera real

Ya se había corregido para tablas *sin* cabecera (bloque 7, sesión
anterior). Caso nuevo con cabecera real:
`6.21/28510.0149_ANEJO_bd79fa987e814be3.pdf` p.6/9 -- cabecera `[None, "Nº
MATRÍCULA", None, "DESCRIPCIÓN", "CRITERIOS TECNICOS"]` desalineada con sus
propios datos: la matrícula real cae en la columna anterior sin nombre,
"Nº MATRÍCULA" etiqueta una columna vacía al 100%. `corregir_confusion_
matricula_codigo_precio` se aplica ahora siempre (no solo sin cabecera
propia) y cubre esta tercera variante. 3 de 4 expedientes afectados quedan
a 0 líneas con este defecto (`6.21/28510.0097`, `0148`, `0149`); el cuarto
(`6.24/28510.0173`) pasa por una vía distinta (`_intentar_recuperar_
desalineacion`) sin cubrir todavía, anotado abajo.

### Causa 3 — pie de verificación de firma electrónica colado en la matrícula

`6.24/28510.0184` p.96-98: un pie de verificación de firma electrónica
(invertido y con cada carácter duplicado por cómo `pdfplumber` lo
superpone en esas páginas) cae en la misma celda que la matrícula real,
con o sin salto de línea entre los dos textos. `_matricula_recuperable_de_
celda_multilinea` busca el único patrón de 9 dígitos en la celda cruda,
sin exigir separador -- nunca si hay más de uno (fila fusionada real, dos
matrículas legítimas pegadas).

**Resultado medido, `6.24/28510.0184`** (94→101 líneas tras recuperar
matrículas antes descartadas): `codigo_precio=matrícula` 41→23,
`precio_unitario` falso 57→25. No llega a 0 de forma fiable -- ver el
límite de determinismo del bloque 4 debajo, el mismo mecanismo que lo
explica.

9 tests nuevos (671→680 pasan). Commit `d71396b`.

---

## Bloque 4 — Determinismo (dos causas reales, corregidas y verificadas)

Reprocesado el corpus completo dos veces seguidas (22.445 líneas):
**872 líneas cambiaban de `documento_origen_id`/`página`/`precio_unitario`
entre pasadas y 1.396 cambiaban de `id` sin que ningún dato real
cambiara.**

### Causa 1 — consulta de documentos sin `order_by`

`ejecutar_extraccion_expediente` listaba los documentos de un expediente
sin `order_by`: Postgres no garantiza el orden de filas sin él, y
`_priorizar_por_origen` (ordenación estable) solo preserva un orden de
partida que tenía que ser estable ya, sin serlo. Caso real,
`6.23/28510.0042`: la fila "P-001" existe de verdad en dos documentos del
mismo expediente (ANEJO_1 y CONTRATO); cuál de los dos ganaba la línea del
catálogo dependía del orden arbitrario de la consulta. Arreglo:
`order_by(Documento.id)` -- no codifica ninguna prioridad semántica, solo
un punto de partida estable; esa prioridad ya la deciden los mecanismos
existentes.

### Causa 2 — sentinela de migración confundido con un lote real

`_eliminar_lote_sentinela_obsoleto` (mecanismo de migración de la sesión
2026-09-07/08, para sustituir el lote implícito `LOTE_UNICO = "1"` por
lotes reales) confundía un lote **real** declarado "1" con el sentinela
del mismo nombre, y lo borraba y recreaba en **cada** reproceso, para
siempre, no solo la primera vez que migraba. Confirmado en 11 expedientes
reales del corpus (`6.23/28510.0051` entre ellos, título "2 LOTES", su
único lote real se llama "1" -- 1.071 de las 1.396 líneas que cambiaban de
`id`). Arreglo: comprueba si `lotes_declarados` de esta misma pasada ya
declara el identificador "1" antes de borrar nada; si lo declara, no es un
sentinela, es el mismo lote reconfirmándose.

**Verificado en vivo, dos pasadas más tras el arreglo: resultado idéntico
byte a byte, 0 diferencias en 22.445 líneas.** 2 tests nuevos (680→681
pasan). Commit `e8e2976`.

**Límite conocido, sin cerrar del todo:** sobre tablas sin cabecera propia
el modelo se llama sin caché persistente (`cabecera_sin_senal`), así que
puede devolver una forma distinta en cada reproceso -- verificado con 3
llamadas reales seguidas sobre la misma tabla de `6.24/28510.0184`: 2/3
correctas, 1/3 con la matrícula en otra columna (capturada de forma segura
por `evaluar_coherencia_mapeo`, cae a revisión, nunca corrompe el dato,
pero tampoco converge a 0). Cerrarlo del todo exigiría una caché
persistente de firma estructural entre reprocesos (hoy `cache_estructural`
es un diccionario en memoria, por documento y por pasada) -- cambio de
arquitectura mayor, para una sesión dedicada.

---

## Bloque 5 — Ingesta desde carpeta (probada de verdad, un hallazgo real corregido)

Montada una carpeta real con la convención de
`docs/ingesta-manual-convencion-carpetas.md` (documentos reales de
`Ejemplo/Input/`, ya que la macro del cliente sigue sin construirse):
carpetas nombradas con el código saneado, ficheros con nombre libre.
Verificado contra el stack real:

- **Registra, clasifica y marca el origen correctamente**: documento
  nuevo → `Documento(origen=manual)`, clasificado por contenido igual que
  el scraper, enlazado vía `DocumentoExpediente` con el nombre de fichero
  real conservado para trazabilidad.
- **Dispara la extracción** (`extraer_expediente` encolado) solo cuando la
  huella del expediente cambia de verdad.
- **La comprobación cruzada funciona** cuando el documento declara su
  propio código y no coincide con la carpeta: no se enlaza, se marca
  `aviso_ingesta_manual`.

**Hallazgo real, corregido:** el mismo documento (mismo hash), copiado
primero en una carpeta que no coincide con su código declarado (rechazado,
correcto) y después en la carpeta correcta (registrado bien), quedaba
**enlazado sin aviso** en una tercera pasada sobre la carpeta original --
la comprobación de código solo se repetía para contenido genuinamente
nuevo; en cuanto el documento ya era conocido por *cualquier* carpeta, la
comprobación se saltaba entera. Viola directamente lo que la documentación
promete. Arreglo: la comprobación corre siempre; `extraer_texto_cacheado`
(caché por hash de documento del bloque de rendimiento de la sesión
anterior) evita reintroducir el coste que la ausencia de caché evitaba a
propósito ahí.

**Verificado en vivo:** hallazgo reproducido contra el stack real (enlace
erróneo creado, confirmado y limpiado a mano), arreglo desplegado, dos
pasadas seguidas sobre la misma carpeta dan el mismo resultado correcto
(`enlaces_nuevos=0`, `documentos_codigo_declarado_distinto=5`, sin
recrear el enlace erróneo). 1 test nuevo (681→682 pasan). Commit `14b8c75`.

---

## Bloque 6 — Cierre

**Auditoría automática:** 0 errores, 4 avisos informativos, todos ya
conocidos y catalogados (2.175 huérfanas sin lote, 1.659 precios
atípicos, 401 cantidades con forma de año, 31 grupos de importe de
licitación compartido entre expedientes de la sindicación).

**Excel exportado:** hoja "Materiales" 19.898 filas × 17 columnas, hoja
"Resumen" con 2.547 pendientes de revisión (954 banda vacía, 603
duplicado sin pérdida, 378 lote no registrado, 372 mapeo incoherente, 240
ninguna cabecera).

**Comparación con el estado anterior** (cierre de la sesión anterior del
mismo día, `sesion-2026-09-12-defecto-mapeo-calidad-interfaz-
rendimiento.md`): catálogo 22.363 → 22.445 líneas (+82); Excel
"Materiales" 19.968 → 19.898 filas (**−70**, a pesar de que el catálogo
creció) -- el trade-off esperado del bloque 2/3: varias líneas que antes
se entregaban con un precio inventado (1,00 €, o `codigo_precio` igual a
la matrícula) ahora se detectan y se excluyen o marcan correctamente en
vez de contaminar el entregable, así que "mapeo incoherente" sube de 295
a 372 (+77) mientras el resto de categorías del Resumen se mantiene
exactamente igual (954/603/378/240, sin cambios -- ninguno de los tres
bloques tocó esas causas). Es una mejora de calidad, no una regresión: se
prefiere excluir a inventar.

### Pendiente al cerrar esta sesión

- **Determinismo de tablas sin cabecera propia (bloque 4):** no cierra al
  100% sin una caché persistente de firma estructural entre reprocesos --
  hoy solo dentro del mismo documento y la misma pasada. Impacto acotado
  (verificado: cae a revisión, nunca corrompe), pero no converge solo.
- **`6.24/28510.0173` (5 líneas, bloque 2):** confusión matrícula/código
  vía `_intentar_recuperar_desalineacion` (desplazamiento ±1 columna),
  camino distinto de las tres causas ya cubiertas -- sin diagnosticar del
  todo en esta sesión.
- **Familia `0130/0152/0153` y balasto (bloque 1, ~470 líneas):**
  estructuralmente no son huecos de este expediente (contenido de otros
  lotes del mismo acuerdo marco) -- decisión de producto pendiente: ¿vale
  la pena una categoría de Resumen específica ("pertenece a otro lote del
  acuerdo marco, no a este pedido") en vez de "revisar", para no pedirle a
  un humano que confirme lo mismo cientos de veces?
- **`6.22/28510.0094/0125/0126` (170 líneas) y `0033/0057/0058` (36
  líneas), bloque 1:** mapeo incoherente/ninguna-cabecera más allá de lo
  ya cerrado en sesiones anteriores, sin auditar a fondo esta sesión.
- **Familia `0122/0155/0156` (bloque 1, 915 líneas, la mayor del
  análisis):** tercera copia del cuadro de precios con un precio
  ligeramente distinto de las dos ya resueltas -- genuinamente ambiguo
  (¿precio de referencia vs. de pedido?), no se fuerza un lote sin
  confirmar con el cliente qué representa esa tercera copia.

Commits de esta sesión: `d71396b` (bloque 2/3), `e8e2976` (bloque 4),
`14b8c75` (bloque 5). 671→682 tests, todos verdes. Dos reprocesos
completos consecutivos verificados byte a byte idénticos tras el bloque 4.
