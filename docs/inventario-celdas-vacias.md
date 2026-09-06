# Inventario de celdas vacías

Sesión 2026-09-06, bloque 3 (CONTEXTO.md): "ninguna celda vacía sin
explicación". Regla general aplicada: si un dato no aparece, el motivo es
siempre uno de tres — **no aplica** a este tipo de línea, **no consta** en
el documento de origen, o está **pendiente** de otro dato — nunca una
variante nueva por columna.

## Componente único

`web/app/ui.tsx` exporta `DatoVacio({ motivo, titulo })`, con
`motivo: "na" | "no-consta" | "pendiente"`. Las cuatro pantallas lo usan tal
cual — antes solo `matrícula` y `precio adjudicado` (Catálogo) tenían este
tratamiento, con su propio marcado ad hoc; ahora es un solo componente
compartido, mismo CSS de siempre (`dato-vacio`, `dato-vacio--na`,
`dato-vacio--no-consta`, `dato-vacio--pendiente`, ya existente).

## Inventario por columna

| Pantalla | Columna | Motivo | Regla |
|---|---|---|---|
| Catálogo, Cola de revisión | Matrícula | no aplica / no consta | Partida alzada (CONTEXTO.md sección 2) → no aplica. Cualquier otra línea sin matrícula → no consta (~1/3 del catálogo, cifra ya medida en sesiones previas). |
| Catálogo, Cola de revisión | Código (precio) | no consta | El cuadro de precios no trae un identificador de línea distinto para esa fila. |
| Catálogo | Lote | no consta | Huérfana: la tabla de origen no se pudo asociar a un único lote sin ambigüedad (`motivo_revision` trae el detalle exacto — banda vacía, varias cabeceras LOTE N, lote no declarado...). |
| Catálogo | Cantidad | no consta | Ver sección siguiente — verificado contra el corpus real, no supuesto. |
| Catálogo | Precio unitario | no consta | Ver sección siguiente — mismo tipo de verificación que cantidad, mismo hallazgo. |
| Catálogo | Precio adjudicado | pendiente | El lote todavía no tiene baja declarada; se calcula solo en cuanto llegue. |
| Expedientes | Matriz | no aplica / no consta | La mayoría de expedientes no son pedido derivado de acuerdo marco → no aplica. Si `matriz_conflicto` es cierto (Anuncio PCSP y Excel de códigos discrepan, CONTEXTO.md sección 7) → no consta, conflicto sin resolver. |
| Expedientes | Licitación / Adjudicación / Baja (expediente y por lote) | pendiente / no consta | Pendiente mientras el expediente sigue en curso (descargando/extrayendo/esperando matriz); no consta si ya terminó y el dato no apareció en los documentos. |
| Expedientes | Adjudicatario (tabla de lotes) | no consta | El documento de adjudicación no lo declara para ese lote. |
| Mantenimiento | Terminado | pendiente | El trabajo todavía está `pendiente` o `en_proceso`. |

Columnas que YA tenían este tratamiento antes de esta sesión (sin cambios):
Matrícula y Precio adjudicado en Catálogo.

Columnas que se dejan **sin** tratamiento especial, con su motivo anotado
para que quede explícito por qué:
- **Código interno / Código de proyecto** (Excel y detalle de línea en
  Catálogo): ya explicado en prosa en el panel de trazabilidad ("sin
  cruzar con el Excel de códigos") y en el Excel (CONTEXTO.md sección 7, "el
  sistema nunca inventa una matriz"); no se duplica como badge tabular
  porque esas dos columnas no aparecen como columnas de la tabla principal,
  solo en el detalle y en el Excel.
- **Descripción**: no puede ser nula en el esquema (`nullable=False`); no
  hay caso que inventariar.
- **Comentarios**: vacío es simplemente "nadie ha escrito una nota
  todavía", no una ausencia de dato del documento — no encaja en ninguno de
  los tres motivos y no se le añade uno artificial.

## Verificación de la hipótesis de "cantidad" (encargo explícito de esta sesión)

**Antes de tocar nada**: 33,0% de las líneas del catálogo (1.009 de 3.060,
medido tras la limpieza del bloque 1) tenían `cantidad IS NULL` — no el 65%
citado en el encargo, esa cifra es de antes de la limpieza de duplicados
del bloque 1 (los duplicados eran casi todos huérfanas sin cantidad, así
que inflaban el porcentaje).

**Cruce contra la hipótesis** ("los cuadros de precios de acuerdo marco no
la traen, se fija en el pedido"): medido por si el propio expediente es un
pedido derivado (`codigo_matriz` no nulo) — resultado, **al revés de lo
esperado**: los pedidos derivados de verdad tienen cantidad en el 98,0% de
sus líneas (23 nulas de 1.153), mientras que los expedientes que NO son
pedidos derivados tienen un 51,7% de líneas sin cantidad (986 de 1.907). La
hipótesis, tal como está redactada en el encargo, no se sostiene con el
dato real.

**Lo que sí explica la mayoría**: los documentos con más líneas sin
cantidad son cuadros de precios de licitaciones "N LOTES" de material de
mantenimiento ferroviario muy variado (`6.25/28510.0019`, 9 lotes,
instalaciones de seguridad; `6.24/28510.0064`, 3 lotes, cables;
`6.24/28510.0203`, 6 lotes, traviesas; `6.25/28510.0027`, 6 lotes, balasto)
— rate cards de un catálogo amplio de materiales de mantenimiento, con
precio unitario fijado pero sin comprometer una cantidad hasta que se
decide el pedido concreto. Es el mismo fenómeno que motiva la "segunda
familia de baja" de CONTEXTO.md sección 16 (indexado por pedido), pero más
amplio: no hace falta que el expediente sea literalmente un "Acuerdo
Marco" con ese nombre para que su cuadro de precios funcione así.

**Un caso real SÍ era un fallo, no una ausencia estructural** — verificado
abriendo el PDF real con `pdfplumber` (no fiándose del dato ya guardado):
`6.25/28510.0019_ANEJO_1.pdf`, página 28 y otras. La cabecera de esa tabla
es:

```
["CÓDIGO DEL PRECIO", "Nº MATRÍCULA", "DESCRIPCIÓN", "UNIDAD DE MEDIDA",
 None, "CANTIDADES ESTIMADAS DE REFERENCIA", "PRECIO DE REFERENCIA"]
```

El mapeo determinista ata (correctamente, por el propio texto de la
cabecera) `cantidad` a la columna 5. Pero en las filas de datos de esa
misma tabla, el número real cae siempre en la columna 4 (la fantasma sin
etiquetar de la cabecera), y la columna 5 sale siempre vacía:
`['P-431', '', 'Tirante TI-22-D-AT1', 'UN', '10', None, '3.270,00 €']`.
`pdfplumber` particiona la fila de cabecera con un límite de columna
distinto al de las filas de datos — mismo fenómeno que ya cubrían
`_recuperar_descripcion_columna_fantasma` e
`_intentar_recuperar_desalineacion` para descripción/precio, pero ninguna
de las dos se disparaba aquí porque descripción y precio_unitario salían
bien en su columna de siempre.

**Arreglado, no solo documentado** (encargo explícito: "si en algún caso sí
está y no se está extrayendo, eso es un fallo que hay que arreglar, no
explicar"): `app.catalogo._recuperar_cantidad_columna_fantasma`, simétrica a
`_recuperar_descripcion_columna_fantasma` — solo se activa cuando la
cabecera SÍ declaró una columna de cantidad (para no inventar una cantidad
en una tabla que de verdad no la trae) y la columna vecina (antes o después,
ver el segundo caso real más abajo) no la usa ya otro campo del mapeo.
Nunca en silencio: la línea recuperada lleva `motivo_revision` ("cantidad
recuperada de una columna fantasma..."). Además, la recuperación exige que
`descripción` ya haya salido bien en su columna de siempre: si también
falta, no es un desplazamiento de una sola celda sino de la fila entera, y
ese caso ya lo cubre `_intentar_recuperar_desalineacion` (desplazando el
mapeo completo) — sin este guard, la recuperación de una sola celda podía
"arreglar" cantidad o precio sueltos y dejar la fila con pinta de resuelta
antes de que la desalineación completa llegara a intentarse (encontrado por
los propios tests existentes, que dejaron de pasar hasta añadir el guard).

**Segundo caso real, mismo mecanismo, columna distinta**: verificando
`precio_unitario` con el mismo método (abrir el PDF real con `pdfplumber`,
nunca fiarse del dato ya guardado) apareció el mismo fenómeno en
`6.23/28510.0051_CONTRATO_1.pdf`, página 112 — la cabecera es

```
["CÓDIGO DEL ELEMENTO", "Nº MATRÍCULA", "DESCRIPCIÓN", "UNIDAD DE MEDIDA",
 "CANTIDADES ESTIMADAS DE REFERENCIA", None, "PRECIO UNITARIO DE REFERENCIA"]
```

— la columna fantasma esta vez va DESPUÉS de "cantidad" en vez de antes,
y es `precio_unitario` el que queda atado a la columna vacía mientras el
importe real cae en la fantasma: `['P-0014', '619260075', 'DIMDH-G-60-500-
...', 'UD.', '0', '259.439,64 €', None]`. Generalizada la función a
`_recuperar_columna_fantasma(fila, mapeo, campo, parece_recuperable)`,
compartida por `cantidad` y `precio_unitario`, que prueba la columna
anterior y, si no encuentra nada recuperable, la siguiente — cubre los dos
lados vistos hasta ahora en el corpus real, no solo el primero.

Regresión cubierta en `tests/test_catalogo.py`: recuperación real de
cantidad, recuperación real de precio unitario, columna vecina no numérica
para cada uno, y cabecera sin esa columna declarada.

**Recuento final, tras reprocesar el corpus completo con el arreglo**
(`VERSION_LOGICA_EXTRACCION` subida para forzar el reproceso; ciclo de
mantenimiento manual con sindicación desactivada, más un reproceso dirigido
de los expedientes con más huecos de precio, más una segunda y tercera
limpieza de restos transitorios del arreglo del bloque 1 — detalle completo
en `docs/correccion-defectos-auditoria.md`):

- **Cantidad**: 540 de 3.036 líneas siguen sin cantidad (17,8%, bajado del
  33,0% inicial) — 427 líneas recuperadas de una columna fantasma. Lo que
  queda es la mayoría genuina: catálogos de acuerdo marco de muchos lotes
  sin cantidad comprometida, más algún caso de valor genuinamente
  ilegible (con su propio `motivo_revision` de "cantidad no
  interpretable").
- **Precio unitario**: 63 de 3.036 líneas siguen sin precio (2,1%, bajado
  de ~719 antes del arreglo, un 91% de los casos recuperados) — 1.157
  líneas recuperadas de una columna fantasma. Aquí sí es correcto que casi
  no quede ningún hueco: a diferencia de cantidad, ningún cuadro de precios
  licita sin precio, así que lo que queda es genuinamente residual (valor
  con formato irreconocible, ya marcado aparte).

**Efecto secundario esperado, no un fallo**: el expediente
`6.23/28510.0051` (1.079 líneas, el mayor concentrador de huecos de precio,
508 de las 719 originales) pasó de `completado` a `pendiente_revision`: al
recuperar 1.073 precios de una vez, esas líneas quedan marcadas para
confirmación humana (mismo criterio que cualquier otra recuperación
automática de columna fantasma, CONTEXTO.md sección 12 — "un sistema que sabe
cuándo no sabe vale más que uno que acierta cinco de cinco"). Antes de este
arreglo, ese expediente aparecía como `completado` con más de 500 precios
unitarios silenciosamente ausentes; ahora aparece, con razón, como
pendiente de una revisión masiva pero de bajo riesgo (todas las líneas con
el mismo motivo, recuperadas por la misma regla verificada). El recuento de
"completados" en la pantalla de Expedientes baja en consecuencia — es la
entrega más honesta, no una regresión.

## Excel (más sobrio que la web)

`app.exportacion`: mismo criterio, en texto liso entre paréntesis en vez
del tono tipográfico de la web (que no tiene sentido en una celda de
hoja de cálculo) — `(no aplica)` / `(no consta)`, aplicado a Matrícula,
Código del material, Cantidad, Precio unitario y Lote. Precio adjudicado
(motivo "pendiente") se deja vacío sin marcador: es una columna derivada
que no sale en el Excel de todas formas (CONTEXTO.md sección 7, columnas del
entregable). Cubierto en `tests/test_exportacion.py`.
