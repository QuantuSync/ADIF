# Sesión 2026-09-08: herencia de lote entre páginas de continuación

Continuación de `docs/sesion-2026-09-08-verificacion-excel-6599.md`: el
punto 4 de esa sesión analizaba, sin implementar, el motivo mayoritario de
las 3.102 líneas pendientes. El cliente aprobó la propuesta tras pedir
verificación adicional en tres rondas — cada una encontró algo que cambiaba
el diseño final. Quedan documentadas las tres, porque el diseño que se
implementó no es el que se propuso al principio.

---

## 0. Cómo cambió la propuesta bajo verificación

**Propuesta inicial:** heredar el lote de la tabla anterior cuando la
franja no trae ninguna cabecera "LOTE N". Verificado contra
`6.22/28510.0156` (repuestos de vía, 2 lotes, documento de 37 páginas
compartido con su hermano `6.22/28510.0122`): la tabla de "Lote 1" resultó
tener su propia ambigüedad en la página que la abre (ver bloque 1) y solo
entonces se pudo confirmar que la herencia en sí era segura.

**Primera vuelta (encargo del cliente, "existe algún otro lote candidato en
ese documento"):** se encontró que la página 26 del mismo documento repite
el cuadro de precios entero bajo "Lote 2", reiniciando la numeración en
`P-001` con las mismas descripciones y los mismos precios que la página 15.
La transición semicambios→cruzamientos que parecía un cambio de lote a
mitad de tabla resultó ser el orden interno del propio catálogo (idéntico
en los dos bloques, verificado desplazando 11 páginas: p.22 del bloque 2 ==
p.33, mismo `P-316 CZI-AG-B1-54...`, mismo precio). Sin este hallazgo, la
propuesta original ni siquiera tenía una página ancla resuelta de la que
heredar (la p.15 ya era ambigua) — hizo falta una Parte A.

**Segunda vuelta (encargo del cliente, "comprueba que la herencia también
es correcta en los demás expedientes, no solo en este"):** al reprocesar
los 16 expedientes afectados, `6.25/28510.0027` (el mismo balasto de 6
lotes que ya motivó no implementar un descarte por firma en 2026-09-07)
expuso un bug real de diseño: el estado de "último lote resuelto" no se
reiniciaba al pasar por una mención de "LOTE" rechazada (un lote real pero
no declarado). Sin el reinicio, la continuación de LOTE 6 habría heredado
el lote 1 (el último lote VÁLIDO visto, páginas antes) en vez de quedarse
huérfana — el mismo riesgo de mezclar lotes que motivó no implementar esto
en su día, llegado por una vía distinta. Corregido antes de aprobar nada:
cualquier mención de "LOTE" que no resuelva limpio, declarada o no, corta
la cadena de herencia.

**Tercera vuelta (encontrada verificando el reproceso real, no pedida
explícitamente pero bloqueante):** al reprocesar a escala, una línea que
pasa de huérfana a resuelta cambia de clave (`"P-001@p15y657"` →
`"P-001"`) — la fila huérfana vieja no se limpiaba nunca, duplicando el
material (2.152 filas así en los primeros 16 expedientes verificados). Un
primer intento de limpieza por contenido (misma página+descripción+precio)
habría podido borrar por error una huérfana real de un lote distinto que
solo coincide en precio de referencia con una tabla ya resuelta —
exactamente el riesgo del balasto, otra vez, por una tercera vía. Corregido
con una clave exacta (`clave_huerfana_hipotetica`, franja vertical incluida)
antes de reprocesar en serio.

---

## 1. Parte A: la cláusula de "urgencia mutua entre lotes"

Verificado contra el texto real, dos veces (p.15 y p.26 de
`6.22/28510.0156`): la cláusula que abre cada lote cita al otro como
repuesto de urgencia —

> "Lote 1: SEMICAMBIOS, AGUJAS Y CONTRAAGUJAS y, en caso de urgencia que no
> pueda ser atendida por el adjudicatario **del lote 2**, cruzamientos y
> contracarriles."

— así que la franja de cualquiera de los dos lotes trae dos identificadores
y caía en "varias cabeceras" sin serlo de verdad. `app.extraccion.
lote_tabla._resolver_ambiguedad_urgencia_mutua` distingue los dos por
posición gramatical: el número que precede a `:` abre la sección real; el
que sigue a "del lote"/"por el lote" es la referencia de repuesto. Nunca
compara contenido de filas. Con dos cabeceras fuertes de verdad en la misma
franja (dos tablas reales comparten página, caso ya conocido de
`6.25/28510.0027`), no se elige ninguna — sigue ambiguo, sin adivinar.

**Impacto medido:** las 152 líneas de "varias cabeceras" del catálogo
entero (76 en `6.22/28510.0122`, 76 en `6.22/28510.0156`) se resuelven al
100%.

## 2. Parte B: herencia entre páginas de continuación

`app.extraccion.lote_tabla.asociar_lote_tabla` marca
`elegible_para_herencia=True` únicamente cuando la franja no trae NINGÚN
identificador de "LOTE" — ni siquiera uno rechazado o ambiguo (condición 1
del cliente al aprobar: "la herencia es para la ausencia total de rastro,
no para el rastro dudoso"). `app.extraccion.pipeline_anejo` mantiene
`ultimo_lote_resuelto` a través de las tablas del documento en el orden en
que se procesan, y:

- lo actualiza a un lote real cuando una tabla resuelve limpio (cabecera
  propia o Parte A) o hereda;
- lo **reinicia a `None`** cuando una tabla trae una mención de "LOTE" que
  NO resuelve limpio (rechazada por no declarada, o ambigua de verdad) —
  el arreglo de la segunda vuelta de verificación;
- nunca inventa un lote si no hay ancla previa: sin `ultimo_lote_resuelto`,
  la tabla se queda huérfana como siempre.

Cada línea heredada lleva `lineas_catalogo.lote_heredado_de_pagina_anterior
= True` (migración 0022, condición 2 del cliente: "que se distinga en la
trazabilidad... si algún día una herencia resulta incorrecta, hay que poder
encontrar todas las afectadas"). `None` en cualquier otro caso, nunca
`False` explícito — mismo convenio que `heredado_de_matriz`.

## 3. La limpieza de huérfanas superadas

`app.catalogo._limpiar_huerfana_superada`, llamada desde
`guardar_lineas_catalogo` cuando una línea se guarda bajo un lote real:
busca una huérfana con `clave_linea` EXACTAMENTE igual a
`clave_huerfana_hipotetica` (la clave con sufijo de página+franja vertical
que esa misma línea habría usado de haberse quedado huérfana —
`app.extraccion.pipeline_anejo` la calcula para toda línea, resuelva o no)
y la borra si existe. Nunca compara descripción ni precio: un precio de
referencia puede repetirse igual entre tablas de lotes DISTINTOS de la
misma página (`6.25/28510.0027`, "P-1 Balasto..." a 10,85 €), y comparar
por contenido habría podido confundir esa coincidencia con la misma fila
reextraída — verificado con un test dedicado
(`test_guardar_lineas_catalogo_no_borra_huerfana_con_precio_coincidente_de_otra_tabla`)
antes de dar el arreglo por bueno.

---

## 4. Verificación contra los 16 expedientes afectados, no solo el ancla

El caso de `6.22/28510.0156` se verificó a fondo antes de aprobar la
propuesta (bloques 0-1). El resto se verificó reprocesando y comprobando la
estructura real del documento en los dos casos de mayor riesgo (más lotes
declarados = más fronteras donde el riesgo de mezcla podría manifestarse):

- **`6.25/28510.0019` (9 lotes, 371 líneas heredadas):** verificado que
  Lote 1 (p.111-116, 121 líneas) y Lote 9 (p.123-139, 230 líneas) son
  bloques limpios de principio a fin — el documento real solo menciona
  "LOTE" en las páginas que abren cada sección (111, 117, 118, 119, 120,
  121, 121, 122, 123 para lotes 1 a 9 respectivamente), nunca a mitad de
  ninguna de ellas. Sin ninguna mención perdida entre medias.
- **`6.25/28510.0027` (balasto, caso de aceptación ya existente,
  `test_expediente_0027_multi_lote_produce_baja_correcta_por_lote`):**
  Lote 1 pasa de 2 a 6 líneas completas (recupera P-3..P-6, perdidas desde
  la sesión de expedientes sin publicar); los huérfanos de Lote 2, 4, 5 y 6
  se quedan exactamente donde estaban (24, no 6) — la continuación de Lote
  6 no hereda el Lote 1 anterior. Test actualizado con las cifras
  corregidas y aserciones nuevas de `lote_heredado_de_pagina_anterior`.

De los 16 expedientes reprocesados, 5 (`6.20/28510.0115`, `6.22/28510.0033`,
`6.22/28510.0058`, `6.21/28510.0016`, `6.24/28510.0130`) no recuperaron
ninguna línea — sin ancla previa resuelta de la que heredar, se quedan
huérfanos exactamente como antes. Ninguno produjo un error.

---

## 5. Números finales

| | Antes de esta sesión | Después |
|---|---:|---:|
| Líneas pendientes de revisión (catálogo entero) | 3.102 | **494** |
| — "ninguna cabecera LOTE N" | 2.001 | 245 |
| — "banda vacía" | 821 | 121 |
| — "varias cabeceras de lote" | 152 | **0** |
| — "lote no declarado" (sin cambio, nunca elegible) | 128 | 128 |
| Líneas entregadas (catálogo completo, todo el corpus) | — | **9.914** |

2.021 líneas llevan `lote_heredado_de_pagina_anterior = True` — todas
dentro de los 16 expedientes reprocesados, verificables en cualquier
momento con esa columna si una herencia futura resultara incorrecta.

455 → 465 tests (10 nuevos: 7 en `test_lote_tabla.py` para la Parte A y la
señal de elegibilidad, contra un fixture de 5 páginas reales de
`6.22/28510.0156`; 1 de integración en `test_pipeline_anejo.py` para la
Parte B de punta a punta; 2 en `test_catalogo.py` para la limpieza de
huérfanas superadas, incluido el guard de seguridad del balasto). El caso
de aceptación existente del balasto se actualizó con las cifras corregidas,
no se relajó ninguna aserción.
