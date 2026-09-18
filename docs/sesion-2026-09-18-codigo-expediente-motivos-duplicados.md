# Sesión 2026-09-18 — "Código de expediente" siempre relleno, motivos de celdas vacías, duplicados por código de precio y la bandera de búsqueda

Cuatro bloques de encargo del cliente, más una medición pedida para decidir en
la sesión siguiente. Ningún reproceso: todos los cambios son de presentación
(Excel), de criterio de auditoría o del endpoint — el catálogo en base de datos
no se toca (37.638 líneas antes y después).

---

## Bloque 0 — Comprobación previa, y una cifra que no cuadraba

El encargo traía cuatro mediciones hechas por el cliente sobre
`catalogo_adif_2026-09-17.xlsx`. Tres coincidieron exactamente; la tercera no.

| Comprobación | Cliente | Medido | |
|---|---:|---:|---|
| Expedientes `6.26/28510` en el Excel / filas | 10 / 274 | 10 / 274 | ✅ |
| De esos, con "Código de expediente" relleno | 3 | 3 | ✅ |
| Expedientes / filas con esa columna vacía teniendo nº de documento | 92 / **2.399** | 92 / **2.381** | ❌ 18 filas |
| De esas filas, cuántas explican esa columna vacía | 0 | 0 | ✅ |

**La diferencia de 18 quedó explicada y cuadrada al dígito, no por criterio
sino por versión del fichero.** Se probaron todas las definiciones posibles de
"vacía" (celda `None`, cadena vacía, sin recortar espacios, exigiendo o no
número de documento) y todas dan 2.381 sobre el fichero en disco; además, los
92 expedientes son "todo o nada" (ninguno mezcla filas con código y sin él).

La causa: el cliente midió una exportación **anterior** al commit `c7e8616`
del día antes, que sacó del catálogo las 22 filas de resumen de presupuesto y
bajó el Excel de 18.260 a 18.239 filas. Esas 22 filas eran de 6 expedientes, y
5 de los 6 no cruzan:

| Expediente | Filas | ¿Cruza? |
|---|---:|---|
| 6.17/28510.0007 | 6 | no |
| 6.17/28510.0056 | 6 | no |
| 6.17/28510.0123 | 3 | no |
| 3.21/28510.0052 | 3 | no |
| 6.23/28510.0105 | 1 | no |
| 6.19/28510.0064 | 3 | **sí** |

19 filas de expedientes sin cruce + 3 de uno con cruce = 22 en base de datos,
21 en el Excel. Es decir, 18 de las filas eliminadas eran de expedientes con la
columna vacía: **2.381 + 18 = 2.399**, la cifra del cliente. Ninguna medición
estaba mal; eran dos ficheros distintos.

### La base de datos, de paso

- **26 expedientes `6.26/28510`** en el sistema, de los que solo **10 aportan
  líneas** (los 10 del Excel). Los otros 16: 11 `sin_publicar`, 5
  `pendiente_revision` sin extraer.
- En base de datos **cruzan 5** del `6.26`, no 3: `0047` y `0048` también
  cruzan, pero tienen 0 líneas y por eso no llegan al Excel.
- Cobertura global del cruce: **380 de 611** expedientes.

---

## Bloque 1 — "Código de expediente" deja de depender del cruce

### La premisa del encargo era falsa, y la del repositorio también

El encargo decía que la columna se rellenaba con el número del cruce. CONTEXTO
sección 7 decía que salía del `Nº Expediente` del Excel de códigos. **Ninguna de
las dos era cierta.** `exportacion.py` escribía el `codigo_expediente` propio
del sistema y usaba el cruce solo como interruptor:

```python
_celda_texto_o_espacio(expediente.codigo_expediente if cruzado else None)
```

El valor del cruce (`CruceCodigos.codigo_proyecto`) se calcula en
`cruce_codigos.py:223` y **se descarta sin persistirlo**: no existe ningún campo
para él en el modelo.

Consecuencia real, anotada tres veces en `docs/` sin corregir la causa: el
cliente filtraba por esa columna y concluía que faltaban expedientes que sí
están. 2.381 filas de 92 expedientes, el 13 % del entregable.

### La otra premisa que se rompió: el cruce no va por número de expediente

El cliente pidió confirmar en una línea que el cruce va por número de
expediente, "porque entonces no puede haber discrepancia que contar". **No se
pudo confirmar.** `_IndiceCodigosProyecto.buscar` (`cruce_codigos.py:112-131`)
prueba cuatro claves en orden. Replicando esa lógica exacta, en solo lectura,
sobre los 611 expedientes reales:

| Clave | Expedientes | ¿El nº del cruce es el del documento? |
|---|---:|---|
| `codigo_expediente` → `Nº Expediente` | **352** | sí, por construcción |
| `codigo_expediente` → `MATRIZ` | **23** | no |
| `codigo_matriz` → `Nº Expediente` | **3** | no |
| `codigo_matriz` → `MATRIZ` | **2** | no |
| no cruza | 231 | — |

Los tres expedientes del `6.26` que el cliente usa como caso de prueba
(`0014`, `0032`, `0071`) están **entre los 28 divergentes**.

Se paró el trabajo y se reportó antes de tocar nada. El cliente confirmó la
decisión: las 28 divergencias son latentes, porque el sistema nunca escribe el
número del cruce en esa columna. Quitar el interruptor no puede introducir
ninguna discrepancia.

### Lo aplicado

- `exportacion.py`: "Código de expediente" se rellena siempre con
  `expediente.codigo_expediente`.
- "Código interno", "Código matriz" y "Estado del contrato (SAP)" **sin tocar**:
  siguen dependiendo del cruce.
- CONTEXTO sección 7 corregida, con el aviso de las cuatro claves.
- Sin campo nuevo y sin repasar el cruce, como pidió el cliente.

### Las dos columnas, medido

Tras el cambio, **"Código de expediente" y "Nº de expediente (documento)"
coinciden en las 18.239 filas. Cero discrepancias.** Son hoy dos columnas
literalmente idénticas. Decisión pendiente del cliente sobre si mantener las
dos; no se quita ninguna.

---

## Bloque 2 — Motivo para toda celda vacía

`app.celdas_vacias` cubría 8 campos, todos de la **línea**. Las columnas del
**expediente** no tenían motivo en ninguna parte del entregable.

Añadidas cuatro, en castellano llano y sin jerga interna (hay un test que
prohíbe explícitamente las palabras "cruce", "cruzado", "índice", "payload",
"null" y "campo" en estos textos):

| Columna | Texto |
|---|---|
| Código interno (sin cruce) | `no consta (este expediente no aparece en el listado de códigos de ADIF)` |
| Código interno (cruza, sin nº) | `no consta (el listado de códigos de ADIF no trae número interno para este expediente)` |
| Código matriz | `no consta (no se conoce ningún acuerdo marco del que dependa este expediente)` |
| Título expediente y Objeto del contrato (documento) | `no consta (no se ha encontrado el título en los documentos de este expediente)` |
| Estado del contrato (SAP) | `no consta (este expediente no aparece en el listado de contratos en ejecución de SAP)` |

Dos decisiones de redacción:

1. **"Título expediente" y "Objeto del contrato (documento)" comparten un solo
   motivo**, porque salen del mismo campo (`nombre_proyecto`). Repetir la misma
   frase dos veces en la misma celda no aporta nada.
2. **"Comentarios" no lleva motivo fila a fila.** Está vacía en las 18.239
   filas y siempre por el mismo motivo: es la única columna que no rellena el
   sistema (CONTEXTO sección 7, "Comentarios | Humano"). Repetirlo en cada fila
   añadiría la misma frase 18.239 veces y taparía los motivos que sí cambian de
   una fila a otra, que es justo lo que esa columna existe para destacar. Va
   una vez en la hoja Resumen. **Decisión revisable por el cliente.**

### Comprobación dura sobre el Excel nuevo

Ninguna celda vacía queda sin motivo, salvo "Comentarios" por lo anterior:

| Columna | Vacías | Con motivo | Sin motivo |
|---|---:|---:|---:|
| Código interno | 2.878 | 2.878 | 0 |
| Código matriz | 10.265 | 10.265 | 0 |
| Título expediente | 2.598 | 2.598 | 0 |
| Matrícula del material | 6.064 | 6.064 | 0 |
| Código del material | 1.517 | 1.517 | 0 |
| Cantidad | 6.555 | 6.555 | 0 |
| Precio unitario | 279 | 279 | 0 |
| Precio adjudicado | 9.164 | 9.164 | 0 |
| Baja del lote | 8.952 | 8.952 | 0 |
| Unidad de medida | 6.110 | 6.110 | 0 |
| Estado del contrato (SAP) | 8.149 | 8.149 | 0 |
| Objeto del contrato (documento) | 2.598 | 2.598 | 0 |
| **Comentarios** | 18.239 | 0 | 18.239 *(por diseño)* |

"Código de expediente" ya no aparece: 0 celdas vacías.

### Los 19 motivos distintos que quedan

| Filas | Motivo |
|---:|---|
| 10.265 | Código matriz: no consta (no se conoce ningún acuerdo marco del que dependa este expediente) |
| 8.952 | Baja del lote: no consta |
| 8.872 | Precio adjudicado: pendiente (falta la baja del lote) |
| 8.149 | Estado del contrato (SAP): no consta (este expediente no aparece en el listado de contratos en ejecución de SAP) |
| 6.340 | Cantidad: no consta |
| 5.914 | Unidad de medida: no consta |
| 5.803 | Matrícula del material: no consta |
| 2.598 | Título expediente y Objeto del contrato (documento): no consta (no se ha encontrado el título…) |
| 2.381 | Código interno: no consta (este expediente no aparece en el listado de códigos de ADIF) |
| 1.256 | Código del material: no consta |
| 497 | Código interno: no consta (el listado de códigos de ADIF no trae número interno…) |
| 279 | Precio adjudicado: pendiente (falta el precio unitario) |
| 261 | Matrícula del material: no aplica (partida alzada) |
| 261 | Código del material: no aplica (partida alzada) |
| 242 | Precio unitario: no consta |
| 215 | Cantidad: pendiente (el documento da una cantidad distinta para cada lote…) |
| 196 | Unidad de medida: no aplica (partida alzada) |
| 37 | Precio unitario: pendiente (el documento da un precio distinto para cada lote…) |
| 13 | Precio adjudicado: no consta |

16.569 filas llevan al menos un motivo; 1.670 no tienen ninguna celda vacía.

---

## Bloque 3 — Los 11 grupos duplicados pasan a aviso

`_check_duplicadas_exactas` agrupaba por seis claves **sin incluir
`codigo_precio`**, pese a que es la clave de la línea dentro del documento
(CONTEXTO sección 2). Dos filas por lo demás idénticas significan cosas
distintas según lo que traigan ahí.

Criterio nuevo (decisión del cliente):

- **Mismo código de precio, o sin código** → `error`, categoría
  `lineas_duplicadas_exactas`. La misma línea del documento contada dos veces.
  Basta **una** fila sin código para que el grupo sea error: sin código no se
  puede afirmar que el documento las liste como dos entradas propias.
- **Todos los códigos distintos** → `aviso`, categoría nueva
  `lineas_duplicadas_codigo_precio_distinto`, con el texto literal pedido: *"el
  propio documento repite el material con códigos de precio distintos"*.

La auditoría sigue sin fundir ni borrar nada.

En la hoja Resumen, la **nota doble** bajo "Nota sobre los materiales que
aparecen repetidos": entre expedientes de una misma licitación por compartir
cuadro de precios, y dentro de un mismo expediente por dos códigos de precio
distintos en el pliego.

---

## Bloque 4 — `POST /mantenimiento/ejecutar` reenvía la bandera de búsqueda

`app.mantenimiento.ciclo` leía `busqueda_desactivada` y `busqueda_fragmentos`
del payload desde que existe el descubrimiento por búsqueda, pero el endpoint
construye el payload campo a campo y **estas dos claves faltaban**. Efecto: cada
reproceso lanzado desde la API (o desde el botón de la web, que manda `{}`)
repetía la búsqueda completa en la Plataforma sin necesidad, a 10 s de
espaciado por petición.

Añadidas al modelo Pydantic y al dict del payload. El comportamiento por
defecto no cambia (`{}` deja la búsqueda activa).

**Comprobado que con la bandera puesta no hay ninguna petición**: el test
sustituye `buscar_codigos_de_fragmentos` — la única puerta por la que el ciclo
llega a la Plataforma para buscar — por un doble que **revienta si alguien lo
llama**, y comprueba que el resto del ciclo sí corre. Y un segundo test, en
espejo, verifica que sin la bandera el doble sí se llama, para que el primero
no pueda pasar por un motivo equivocado.

---

## Medición pedida — los 28 que cruzan por una clave ajena

Encargo explícito: **medir, no arreglar.** El "Código interno" es la columna que
usan en almacenes, y en estos casos sale de la fila de otro expediente.

### Los 23 de `codigo_expediente` → `MATRIZ` (2.287 líneas de catálogo)

| Expediente | Líneas | Interno hoy | Fila del Excel (Nº Exp) | ¿Fila propia? |
|---|---:|---|---|---|
| 2.24/04110.0035 | 0 | 25020 | 6.25/28510.0215 | no existe |
| 2.24/04110.0036 | 0 | 25021 | 6.25/28510.0175 | no existe |
| 4.25/28510.0124 | 4 | 25003 | 4.25/28510.0207 | no existe |
| 6.24/28510.0064 | 232 | 22003 | 6.24/28510.0073 | no existe |
| 6.24/28510.0088 | 46 | 23037 | 6.24/28510.0113 | no existe |
| 6.24/28510.0094 | 45 | 24007 | 6.24/28510.0175 | no existe |
| 6.24/28510.0117 | 103 | 21018 | 6.24/28510.0168 | no existe |
| 6.24/28510.0130 | 231 | 24008 | 6.24/28510.0152 | no existe |
| 6.24/28510.0203 | 87 | 24027 | 6.25/28510.0006 | no existe |
| 6.25/28510.0019 | 696 | 20018 | 6.25/28510.0039 | no existe |
| 6.25/28510.0027 | 36 | 24039 | 6.25/28510.0099 | no existe |
| 6.25/28510.0028 | 54 | 24038 | 6.25/28510.0085 | no existe |
| 6.25/28510.0088 | 74 | 25006 | 6.25/28510.0125 | no existe |
| 6.25/28510.0097 | 60 | 24034 | 6.25/28510.0133 | no existe |
| 6.25/28510.0141 | 17 | 25010 | 6.25/28510.0185 | no existe |
| 6.25/28510.0142 | 18 | 25009 | 6.25/28510.0146 | no existe |
| 6.25/28510.0171 | 21 | 25025 | 6.25/28510.0209 | no existe |
| 6.25/28510.0201 | 239 | 25035 | *(vacío)* | no existe |
| 6.25/28510.0206 | 15 | 25042 | 6.25/28510.0216 | no existe |
| 6.25/28510.0214 | 106 | 25044 | 6.25/28510.0226 | no existe |
| 6.25/28510.0218 | 32 | 24043 | 6.25/28510.0242 | no existe |
| 6.25/28510.0220 | 158 | 25043 | 6.25/28510.0236 | no existe |
| 6.25/28510.0221 | 13 | 25045 | *(vacío)* | no existe |

### Los 3 de `codigo_matriz` → `Nº Expediente` (92 líneas)

| Expediente | Líneas | Interno hoy | Fila del Excel | ¿Fila propia? |
|---|---:|---|---|---|
| 6.26/28510.0014 | 14 | 24036 | 6.25/28510.0016 | no existe |
| 6.26/28510.0032 | 39 | 20012 | 6.20/28510.0136 | no existe |
| 6.26/28510.0071 | 39 | 20012 | 6.20/28510.0136 | no existe |

### Los 2 de `codigo_matriz` → `MATRIZ` (0 líneas)

| Expediente | Líneas | Interno hoy | Fila del Excel | ¿Fila propia? |
|---|---:|---|---|---|
| 6.26/28510.0047 | 0 | 25021 | 6.25/28510.0175 | no existe |
| 6.26/28510.0048 | 0 | 25020 | 6.25/28510.0215 | no existe |

### El hallazgo que decide la cuestión

**Ninguno de los 28 tiene fila propia en el Excel de códigos de ADIF: 0 de 28.**
No es casualidad, es estructural — `buscar` prueba `Nº Expediente` antes que
`MATRIZ` para la misma clave, así que si existiera una fila propia habría
ganado ella.

Consecuencia para la decisión pendiente: **reordenar las cuatro claves no
cambiaría nada.** No hay ninguna fila mejor que encontrar. Las opciones reales
son otras dos:

1. **No heredar "Código interno" de una fila casada por `MATRIZ`** (dejarlo
   vacío, con su motivo). Honesto, y 2.379 líneas de catálogo perderían un
   valor que hoy es el de otro expediente.
2. **Dejarlo como está** y documentar que en estos 28 el interno es el de la
   familia, no el del expediente.

Dato de apoyo para la opción 1: hay internos **repetidos entre expedientes
distintos** por esta vía — `20012` lo comparten `6.26/28510.0032` y
`6.26/28510.0071`; `25020` y `25021` aparecen cada uno en dos expedientes de
departamentos distintos (`2.24/04110.*` y `6.26/28510.*`).

---

## Cierre

### Pruebas

**990 pasan** (968 antes, +22). Tres pruebas existentes actualizadas porque
fijaban el comportamiento anterior a propósito:
`test_lineas_duplicadas_exactas_dentro_del_mismo_lote` (usaba dos códigos de
precio distintos: es justo el caso que ahora es aviso) y las dos de
`test_api_catalogo.py` que fijaban la celda vacía y el texto exacto del motivo.

### Excel

`C:\dev\ADIF\catalogo_adif_2026-09-18.xlsx`

### Comparación con el anterior

| | 2026-09-17 | 2026-09-18 |
|---|---:|---:|
| Filas | 18.239 | **18.239** |
| Expedientes con filas | 358 | **358** |
| Materiales distintos | 8.743 | **8.743** |
| Columnas | 18 | 18, mismo orden |

**0 expedientes pierden filas, 0 materiales desaparecen, 0 filas de
diferencia.** Comparado además como multiconjunto de filas completas
(ignorando las dos columnas que esta sesión cambia a propósito): **0 filas solo
en el anterior, 0 solo en el nuevo.**

Columnas que cambian, fila a fila:

| Columna | Filas | Por qué |
|---|---:|---|
| Motivo de las celdas vacías | 10.330 | bloque 2 |
| Código de expediente | 2.381 | bloque 1 |
| Descripción / Código del material / Cantidad / Precio unitario | 6 / 2 / 2 / 2 | **reordenamiento, no cambio de contenido** |

Esas últimas son tres parejas de filas **contiguas** que intercambian posición
(970↔971, 1266↔1267, 1284↔1285, en `6.21/28510.0109`/`0110`/`0111`). El
contenido es idéntico — el multiconjunto lo demuestra. Es el orden no total ya
documentado como pendiente al cierre de la sesión 2026-09-15 ("el desempate por
`orden_aparicion` se repite entre documentos: falta `LineaCatalogo.id` como
último desempate"), no un efecto de esta sesión.

### Bloque 0 sobre el Excel nuevo: antes y después

| Comprobación | Antes (09-17) | Después (09-18) |
|---|---|---|
| 1. Expedientes `6.26/28510` / filas | 10 / 274 | **10 / 274** (igual) |
| 2. De esos, con "Código de expediente" relleno | **3** de 10 | **10** de 10 |
| 3. Expedientes / filas con esa columna vacía | 92 / 2.381 | **0 / 0** |
| 4. De esas filas, cuántas explican la columna | 0 | **0** (ya no existen) |

### Auditoría

**1 error, 7 avisos** (antes: 1 error, 6 avisos).

Los 11 grupos duplicados pasan de error a aviso, con el texto pedido:

> 11 grupo(s) de líneas con la misma matrícula, descripción, cantidad y precio
> dentro del mismo expediente y lote, pero con códigos de precio distintos: **el
> propio documento repite el material con códigos de precio distintos** — 22
> línea(s) en total.

**El error que queda no es de esta sesión.** Es
`lineas_cambian_sin_cambiar_documentos` sobre `6.23/28510.0105`, y su causa es
el arreglo del día anterior: ese expediente perdió su única fila de resumen de
presupuesto después de la auditoría 21560, y la comprobación no sabe atribuirlo
a `lineas_podadas` porque la línea la quitó el filtro de extracción, no el
podador. Verificado: los otros 5 de los 6 expedientes de aquel arreglo sí
aparecen bajo el aviso `lineas_bajan_explicado_por_poda`
(`3.21/28510.0052`, `6.17/28510.0007`, `6.17/28510.0056`, `6.17/28510.0123`,
`6.19/28510.0064`) y `0105` es exactamente el sexto. Es el pendiente ya anotado
en CONTEXTO tras la sesión del maestro de materiales: enseñar a
`detectar_crecimiento_sin_cambios` a distinguir un cambio de regla de
extracción legítimo de una subida sin explicar.

Los otros 6 avisos son los de siempre (huérfanas sin lote, precios atípicos,
cantidades con forma de año, importes de licitación compartidos y repetidos,
líneas que bajan explicadas por la poda).

---

## Pendiente de decisión del cliente

1. **Mantener o no las dos columnas** "Código de expediente" y "Nº de
   expediente (documento)", hoy idénticas en las 18.239 filas.
2. **"Comentarios"**: motivo fila a fila o la nota única del Resumen (lo
   aplicado).
3. **Los 28 que cruzan por clave ajena**: dejar el "Código interno" heredado o
   vaciarlo. Reordenar las claves queda descartado por la medición.
4. Sigue en pie, de sesiones anteriores: `LineaCatalogo.id` como último
   desempate del orden, y `detectar_crecimiento_sin_cambios`.
