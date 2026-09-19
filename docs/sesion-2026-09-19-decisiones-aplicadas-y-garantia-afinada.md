# Sesión 2026-09-19 (segunda parte) — Las cinco decisiones aplicadas, y la garantía afinada sin aflojarla

Continúa `docs/sesion-2026-09-19-precio-desde-importe-lotes-del-titulo-y-fusion.md`.
Aquella sesión dejó **seis decisiones abiertas que cambian datos del
entregable**; el cliente contesta **cinco** y las cinco quedan aplicadas.
La sexta sigue sin tocar y se explica al final.

---

## 1 — `PA` fuera de la columna "Unidad de medida"

### Qué era

`PA` no es una unidad de medida: es el **tipo de línea** — "partida alzada",
que CONTEXTO.md sección 2 define como una reserva presupuestaria y no un
artículo de almacén. Ocupaba la celda "Unidad de medida" en 33 filas del
Excel como si midiera algo.

Comprobado antes de tocar nada: **las 33 filas, sin excepción, tienen
descripción que empieza por "Partida alzada"** y cantidad 1. No hay ni un
caso ambiguo.

### Qué se ha hecho

`app.extraccion.unidad_medida.es_marca_de_partida_alzada` reconoce la marca y
`app.catalogo._construir_campos` **no la guarda como unidad**. Dos detalles
que importan:

- **`PA` sigue dentro del vocabulario de unidades conocidas.** Si saliera de
  ahí, la línea se iría a revisión con el motivo "unidad de medida descartada
  por no ser una unidad conocida", que sería **falso**: el documento no está
  mal escrito, pone exactamente lo que quiere poner.
- Se escribe **`INVALIDADO`, no `None`** (`app.extraccion.invalidado`). Un
  `None` corriente no pisa un valor ya guardado, así que el "PA" de las
  pasadas anteriores habría sobrevivido al reproceso. Aquí la extracción sí
  ha mirado la celda y ha determinado que no es una unidad: hay que borrar lo
  que hubiera.
- El literal del documento no se pierde: sigue en `unidad_medida_original`.

El motivo de la celda vacía lo pone `app.celdas_vacias` sin ningún código
nuevo — ya daba **"no aplica (partida alzada)"** para la matrícula y el
código de material de esas mismas filas, y ahora lo da también para la
unidad. Las tres celdas de esa fila dicen lo mismo y por la misma razón.

### Comprobado en el entregable

| | |
|---|---:|
| Filas que pierden el "PA" de la columna "Unidad de medida" | **33**, en **17 expedientes** |
| Filas que siguen con "PA" en esa columna | **0** |
| Filas de partida alzada con el motivo "Unidad de medida: no aplica (partida alzada)" | **239** |

Las otras 34 filas de partida alzada del Excel **no** llevan ese motivo, y es
correcto: su documento sí les declara una unidad real (`ud` casi siempre), así
que su celda no está vacía y no hay nada que explicar. Ninguna de las 273
filas de partida alzada del entregable dice ya "PA".

---

## 2 — CONTRAGUJA / CONTRAAGUJA: no se unifica

**Decisión del cliente: la descripción sigue literal del PDF.** No se ha
tocado ni una fila.

La pregunta para ADIF queda redactada y lista en
**`docs/pregunta-cliente-contraguja-contraaguja.md`**, con sus cifras
re-medidas contra el Excel de esta sesión y el contexto por si preguntan. La
envía el cliente.

---

## 3 — La columna "Código de precio"

### Dónde va, y por qué ahí

Entra como columna **16 de 18**, la última de las que rellena el sistema.
**Ninguna columna existente cambia de posición**: detrás quedan las dos que ya
tenían su sitio reservado al final por decisiones anteriores del propio
cliente — "Motivo de las celdas vacías" (sesión 2026-09-14, *"justo antes de
Comentarios"*) y "Comentarios" (sesión 2026-09-09, *"al final de todas"*, la
única que rellena una persona a mano).

```
… Unidad de medida | Estado del contrato (SAP) | Objeto del contrato (documento)
  | Código de precio | Motivo de las celdas vacías | Comentarios
```

### Las celdas vacías llevan su motivo

`app.celdas_vacias` añade, para toda fila sin código de precio:

> **Código de precio: no consta** (el cuadro de precios de este documento no
> numera sus renglones)

No es un hueco de extracción: son cuadros que no numeran. Los tres grandes
(`6.20/28510.0042`/`0046`/`0047`) aportan solos casi 4.000 de esas filas.

### Comprobado en el entregable

| | Filas | % |
|---|---:|---:|
| Con código de precio | **9.219** | 47,1 % |
| Vacías | **10.350** | 52,9 % |
| De las vacías, **con su motivo en la columna de motivos** | **10.350** | **100 %** |

Por expediente (363 con filas): **193 la tienen en todas las suyas**, **142 en
ninguna** y **28 mezclados**.

Y la comprobación que justificaba añadirla: dentro de un mismo expediente y
lote, **el código de precio no se repite ni una sola vez** en las 9.219 filas
que lo traen — **0 grupos repetidos**. Es un identificador de verdad, no un
número decorativo, y es lo único que lleva una fila del Excel a su renglón del
PDF.

El Excel pasa de **17 a 18 columnas**, y las diecisiete anteriores conservan
su posición relativa exacta (comprobado en la comparación: *"orden de las
comunes igual: True"*).

---

## 4 — Las seis descripciones desplazadas de `6.24/28510.0171`

### Qué pasaba de verdad

No estaban "más cortas": estaban **desplazadas**. El documento trae el mismo
material en dos tablas — el cuadro de precios (p.18) y el anejo de
criterios/impacto del fallo (p.22) — con los mismos códigos y las mismas
matrículas, y `pdfplumber` corta las filas de la p.22 más arriba de donde el
documento las separa, así que la cola de cada descripción cae en la celda de
la fila **siguiente**:

| | p.18 (cuadro de precios) | p.22 (criterios) |
|---|---|---|
| `P-01` | DISYUNTOR EXTRARRÁPIDO MODELO UR26ED64S DE **SECHERON O EQUIVALENTE** | DISYUNTOR EXTRARRÁPIDO MODELO UR26ED64S DE |
| `P-02` | CONTACTO FIJO MODELO UR26ED64S DE **SECHERON O EQUIVALENTE** | **SECHERON O EQUIVALENTE** CONTACTO FIJO MODELO UR26ED64S DE |

La p.22 se escribía la última, así que en el Excel cada material salía
empezando por el final de la descripción del material **anterior** — para
quien busca en almacenes, peor que una descripción corta.

### La prueba: una identidad de cadenas, no un parecido

`app.catalogo.corregir_descripcion_desplazada_entre_tablas`. Concatenadas en
orden, las descripciones de la tabla desplazada son un **prefijo estricto** de
las de la tabla buena:

```
concat p.22 (criterios): 348 caracteres
concat p.18 (cuadro)   : 371 caracteres
¿prefijo estricto? -> Sí. Lo que falta al final: " SECHERON O EQUIVALENTE"
```

Es exactamente el mismo texto cortado en sitios distintos, y lo que sobra al
final es la cola que la última fila de la p.22 perdió porque no tiene fila
siguiente de la que recuperarla. Dos tablas de materiales distintos no
producen eso.

**No se inventa ningún texto ni se junta nada**: para la misma clave, se copia
la descripción que el mismo documento imprime en su otra tabla. Con menos de
**dos** claves compartidas no se comprueba nada — un prefijo entre dos
descripciones sueltas sí podría ser casualidad.

### Comprobado, fila a fila

Las seis quedan completas y **ninguna empieza por el trozo del material
anterior**:

```
DISYUNTOR EXTRARRÁPIDO MODELO UR26ED64S DE SECHERON O EQUIVALENTE
CONTACTO FIJO MODELO UR26ED64S DE SECHERON O EQUIVALENTE
CONTACTO MÓVIL MODELO UR26ED64S DE SECHERON O EQUIVALENTE
CÁMARA DE SOPLADO MODELO UR26ED64S DE SECHERON O EQUIVALENTE
DISPOSITIVO DE CIERRE (BOBINA) MODELO UR26ED64S DE SECHERON O EQUIVALENTE
AMORTIGUADOR MODELO UR26ED64S DE SECHERON O EQUIVALENTE
```

Descripciones incompletas o que empiezan por la cola de la anterior: **0**.
Matrícula, cantidad y precio de las seis, sin cambios.

### El mismo desplazamiento en el resto del corpus

La regla se aplicó a **todo el corpus** en el reproceso completo y saltó en
**dos expedientes, 8 filas en total**:

| Expediente | Filas | Qué corrige |
|---|---:|---|
| `6.24/28510.0171` | **6** | El caso entero: cada descripción empezaba por el final de la anterior |
| `6.22/28510.0173` | **2** | Mucho más leve: un espacio de más dentro de una palabra partida — `"SKL‐ 12"` → `"SKL‐12"`, `"23‐ NEGRA"` → `"23‐NEGRA"` |

Es decir: **el desplazamiento grave existe en un solo expediente del corpus**,
y el mecanismo (dos tablas del mismo documento cortadas en sitios distintos)
en dos. No es un patrón extendido.

---

## 5 — La garantía del reparto por lotes, afinada sin aflojarla

### El cambio, y solo ese

`_el_cuadro_declara_todos_los_lotes` deja de contar como huérfanas **las
filas del anejo de criterios técnicos que el propio documento declara del
conjunto de los lotes** (`MOTIVO_TABLA_DEL_CONJUNTO`, CONTEXTO.md sección 7).
Era un error de categoría: esas filas **no pueden tener lote por diseño** —
son la lista de materiales de la licitación entera, con su propia numeración —
y quedarían huérfanas exactamente igual se acepte o se rechace el reparto. La
garantía rechazaba el intento por filas que no se pierden.

**No se afloja nada más.** Una huérfana de verdad — banda vacía, tabla
separada por páginas, cabecera ilegible — sigue descartando el intento entero.

### La condición que puso el cliente: la prueba aritmética

> *"Condición para dar por buenas las 96 líneas nuevas de `6.22/28510.0173`.
> Pasa la misma prueba del bloque 1 de ayer: suma de cantidad por precio
> unitario de cada lote contra el presupuesto de licitación publicado de ese
> lote."*

El presupuesto por lote lo publica el expediente **dos veces, y las dos
coinciden**:

- `ADJUDICACION_1.pdf` p.2 — "Lote 1: Norte … Importe (sin impuestos)
  5.900.000 EUR"; "Lote 2: Sur … Importe (sin impuestos) 5.900.000 EUR".
- `ANEJO_1.pdf` p.5 — "Lote 1: Norte, 5.900.000,00 € sin IVA; Lote 2: Sur,
  5.900.000,00 € sin IVA."

Y la suma del cuadro repartido:

| Lote | Filas | Suma cantidad × precio unitario | Presupuesto declarado | Diferencia |
|---|---:|---:|---:|---:|
| 1 — Norte | 184 | **5.900.000,00 €** | 5.900.000,00 € | **0,00 €** |
| 2 — Sur | 184 | **5.900.000,00 €** | 5.900.000,00 € | **0,00 €** |

**Cuadra al céntimo en los dos.** No hay nada que revertir: las 96 líneas
nuevas están demostradas por la aritmética del propio documento, igual que las
54 tablas de lote del bloque 1 de ayer.

### Lo que ha cambiado, y lo que no

| Expediente | Antes | Ahora | |
|---|---:|---|---|
| `6.22/28510.0173` | **272** filas, todas en el lote sentinela "1" | **368** — 184 en el lote 1 y 184 en el lote 2 | **+96** |
| `6.25/28510.0171` | **21** filas, todas en el lote sentinela "1" | **21** — 11 en el lote 1 y 10 en el lote 2 | **+0**, pero ahora cada una en su lote real |
| **`4.25/28510.0132`** | **119** filas | **119** filas | **exactamente igual**, como pedía el cliente |

`4.25/28510.0132` sigue rechazado porque sus 106 huérfanas son de banda vacía
(93) y de tabla separada por páginas (13), **ninguna de criterios técnicos**:
la garantía no se ha aflojado para él ni un milímetro.

### Un efecto lateral, dicho antes de que lo pregunten

Las filas del anejo de criterios de esos dos expedientes pasan a contarse en
su propia categoría del Resumen ("Líneas del anejo de criterios técnicos,
común a todos los lotes"): **13.432 → 13.636, +204** (183 de `0173` y 21 de
`0171`). Y por lo mismo, las huérfanas totales pasan de 19.313 a **19.517**.
**No se pierde ninguna fila del entregable por esto**: esas líneas ya estaban
fuera de "Materiales" antes y siguen fuera; lo único que cambia es que ahora
se cuentan bajo el motivo que de verdad les corresponde.

### Y un defecto que salió al verificar, y está corregido

El primer reproceso destapó que **el arreglo del título del bloque 3 no era
idempotente para `6.22/28510.0011`**: volvía a 24 filas. La causa es la trampa
que CONTEXTO.md ya avisaba — `LOTE_UNICO` vale `"1"`, el mismo texto que un
lote real llamado "Lote 1". Tras quedarse con su único lote "1", la pasada
siguiente volvía a leer ese "1" como sentinela, el reparto del cuadro lo
partía en seis otra vez y recuperaba los cuadros de sus hermanos. Sus tres
hermanos `0012`-`0014` no lo sufrían solo porque sus lotes se llaman "2", "3"
y "4".

Arreglado con una guarda en `_lotes_candidatos_del_cuadro`: **el lote único no
es el sentinela si su número es justo el que declara el título del
expediente.** Medido antes de aplicarla: a los otros ocho expedientes del
corpus a los que alcanza (título "Lote 1" y un único lote "1") su intento de
reparto ya se lo rechazaba la garantía, así que no intentarlo siquiera no les
cambia ni una fila. Comprobado en el reproceso definitivo: los cuatro del
balasto se quedan con sus 4 filas cada uno.

---

## 6 — La sexta decisión, la que sigue sin tocar

La sesión anterior dejó **seis** decisiones que cambian datos del entregable.
El cliente contesta cinco; la sexta es:

> **Los once expedientes cuyo título declara un lote que no está entre los
> suyos.**

### Qué está en juego

`6.21/28510.0135` se titula *"Lote 6. Placas asiento PAE (Pae-1, Pae-2,
Pae-Z1, Pae-Z2) y PAS (Pas-1 y Pas-2)"* y los lotes que tiene registrados son
el **1, el 3 y el 7**. Lo mismo, con otros números, en los otros diez.

Y hay una pista que lo vuelve incómodo: en su propio `ANEJO_3.pdf` **existe
una sección titulada "LOTE 6 – PLACAS ASIENTO PAE (PAE-1, PAE-2, PAE-Z1,
PAE-Z2) y PAS (PAS-1 y PAS-2)"**, palabra por palabra su título. El sistema no
tiene registrado el lote 6 para ese expediente, así que esa tabla —la suya—
queda huérfana, y en cambio se queda con las de los lotes 1, 3 y 7, que son de
sus hermanos.

| Expediente | Dice el título | Lotes que tiene | Filas hoy |
|---|---|---|---:|
| `6.21/28510.0135` | Lote 6 | 1, 3, 7 | 73 |
| `6.21/28510.0137` | Lote 8 | 1, 3, 7 | 73 |
| `6.21/28510.0138` | Lote 9 | 1, 3, 7 | 73 |
| `6.22/28510.0139` | Lote 1 | 5, 6 | 6 |
| `6.22/28510.0140` | Lote 2 | 5, 6 | 6 |
| `6.22/28510.0142` | Lote 4 | 5, 6 | 6 |
| `6.22/28510.0147` | Lote 1 | 4, 5 | 6 |
| `6.22/28510.0148` | Lote 2 | 4, 5 | 6 |
| `6.22/28510.0149` | Lote 3 | 4, 5 | 6 |
| `6.23/28510.0073` | Lote 1 | 3, 4 | 10 |
| `6.23/28510.0074` | Lote 2 | 3, 4 | 0 |
| **Total** | | | **265** |

### Por qué la regla del título no puede tocarlos

La regla del bloque 3 exige, como tercera condición de certeza estructural,
que **el número del título esté entre los lotes que el expediente ya tiene**.
Aquí no lo está en ninguno de los once. Aplicarla igual significaría **borrar
todos sus lotes y crear uno que ningún documento les asigna**: inventar, no
deducir. Es exactamente lo que la condición existe para impedir.

### Recomendación

**No tocarlo por título, y preguntar a ADIF.** La pregunta correcta no es
"¿les ponemos el lote del título?" sino **"¿por qué los lotes registrados de
estos once no incluyen el que su propio título y su propia sección del anejo
nombran?"** Eso lo contesta la adjudicación de esas licitaciones —de dónde
salieron los lotes 1, 3 y 7 de `6.21/28510.0135`—, no una heurística sobre el
texto del título.

Mientras tanto no se pierde nada: las 265 filas siguen en el entregable, con
el lote que sus documentos les dan hoy, y el material de los lotes que les
faltan sale en el expediente hermano que sí los tiene.

---

## 7 — Cierre

### Pruebas

**1.171 pasan** (1.141 al cerrar la primera parte, **+30**). Ninguna saltada.
Las nuevas, en `engine/tests/test_decisiones_2026_09_19.py`: 7 de `PA` fuera
de la columna de unidad (incluida la de que **sigue siendo valor conocido**,
para no mandar la línea a revisión con un motivo falso, y la de que se escribe
`INVALIDADO` y no `None`), 3 de la columna "Código de precio" y su sitio, 5 de
la descripción desplazada (con sus contraejemplos: dos tablas de materiales
distintos, una sola clave compartida, dos tablas idénticas), 5 de la garantía
afinada (incluidas las dos que comprueban que **una huérfana de verdad sigue
descartando el intento**) y 3 de la idempotencia del arreglo del título.

### El reproceso completo, con la red apagada

`POST /mantenimiento/ejecutar` con `forzar: true`, `sindicacion_desactivada:
true` y `busqueda_desactivada: true`. **517 expedientes reextraídos**, 519
evaluados, **18 minutos y 34 segundos** (1.113,5 s).

| | |
|---|---|
| `descargas_lanzadas` | **0** |
| `saltados_descarga` | 519 |
| `sin_publicar_reintentados` | **0** |
| `sin_publicar_desactivado` | **True** |
| `descubrimiento` / `descubrimiento_busqueda` | `None` / `None` |

### Comparación con `catalogo_adif_2026-09-19-precio-desde-importe.xlsx`

| | Antes | Ahora |
|---|---:|---:|
| Filas de "Materiales" | 19.473 | **19.569** (+96) |
| Columnas | 17 | **18** (+1) |
| Expedientes con filas | 363 | **363** (=) |
| Filas de "Conciliación" | 534 | **534** (=) |
| Materiales distintos **por matrícula** | 11.832 | **11.832** (=) |
| Materiales distintos **por matrícula y precio** | 11.895 | **11.895** (=) |
| Materiales distintos **por lote, matrícula y precio** | 13.182 | **13.364** (+182) |

**0 expedientes desaparecen, 0 nuevos, 0 materiales perdidos** por ninguna de
las tres claves.

**Cada diferencia, una a una — son cuatro, y ninguna inesperada:**

1. **+96 filas, en un solo expediente**: `6.22/28510.0173`, de 272 a 368.
   **Es la garantía afinada** (tarea 5), y las 96 están demostradas por la
   aritmética del propio documento: los dos lotes suman 5.900.000,00 € cada
   uno, exactamente su presupuesto publicado. Ningún otro expediente cambia de
   número de filas.
2. **Una columna nueva, "Código de precio"** (tarea 3), en la posición 16 de
   18. Las diecisiete anteriores conservan su orden relativo exacto.
3. **33 celdas de "Unidad de medida" pasan de "PA" a vacía** (tarea 1), en 17
   expedientes, con su motivo. No cambia ningún otro valor de esas filas.
4. **8 descripciones cambian** (tarea 4), en 2 expedientes: las 6 de
   `6.24/28510.0171`, que dejan de empezar por el final del material anterior,
   y 2 de `6.22/28510.0173`, donde desaparece un espacio de más dentro de una
   palabra partida.

**Filas cuyo Precio unitario cambia: 0.** Ninguna de las cinco tareas toca un
precio.

Los +182 materiales distintos por lote+matrícula+precio son las mismas
matrículas de `6.22/28510.0173` contadas ahora en dos lotes en vez de en uno:
**0 perdidos**, que es lo que había que comprobar.

### Cuadre de "Conciliación" con "Materiales"

```
suma de la columna de líneas de "Conciliación": 19.569
filas de la hoja "Materiales":                  19.569
```

0 expedientes sin Situación.

### Auditoría

**0 errores y 6 avisos.**

| Aviso | Antes | Ahora |
|---|---:|---:|
| Grupos de material repetido con códigos de precio distintos | 11 | **11** |
| Huérfanas sin lote | 19.313 | **19.517** (+204, las de criterios de los dos expedientes que entran) |
| Precios atípicos | 1.488 | **1.496** (+8, las filas nuevas de `6.22/28510.0173`) |
| Cantidades con forma de año | 941 | **941** |
| Grupos de importe de licitación compartido | 54 | **54** |
| Expedientes con importe repetido entre sus lotes | 8 | **8** |

*(El primer reproceso de la sesión dio además **1 error**,
`lineas_cambian_sin_cambiar_documentos` sobre `6.22/28510.0173` y
`6.25/28510.0171` — la regla funcionando: son los dos expedientes que cambian
de número de líneas sin que cambien sus documentos, por el afinado de la
garantía. En el reproceso definitivo ya no salta, porque la ejecución anterior
de la auditoría ya los vio con sus cifras nuevas.)*

### Recuento por Situación de la hoja "Conciliación"

| Situación | Expedientes | Antes |
|---|---:|---:|
| Aporta líneas | **363** | 363 |
| Publicado sin cuadro de precios | **64** | 64 |
| Los precios están en un acuerdo marco que no está publicado | **47** | 47 |
| Otro | **26** | 26 |
| Publicado dentro de la ficha de otro expediente | **17** | 17 |
| Documentos escaneados que no se han podido leer | **15** | 15 |
| El acuerdo marco está publicado pero no publica precios unitarios | **2** | 2 |
| Pendiente de procesar | **0** | 0 |
| **Total** | **534** | 534 |

**Filas totales de "Materiales": 19.569.** Líneas en la base de datos: 39.309
en 612 expedientes.

### Excel

```
C:\dev\ADIF\catalogo_adif_2026-09-19-decisiones-aplicadas.xlsx
```

---

## Pendiente de decisión del cliente

1. **Los once expedientes cuyo título declara un lote que no está entre los
   suyos** (bloque 6 de arriba): 265 filas. Sin tocar; la pregunta es para
   ADIF.
2. **La errata CONTRAGUJA / CONTRAAGUJA**: no se unifica. La pregunta está
   redactada en `docs/pregunta-cliente-contraguja-contraaguja.md` y la envía
   el cliente.
3. **Las 946 huérfanas de las causas C y D**: 712 están en
   `6.21/28510.0112`/`0113`, cuyo cuadro llega en glifos CID sin tabla de
   caracteres. Solo las resuelve una revisión manual del documento.
4. **`6.26/28510.0064` lote 3 `P-2`**: la única línea del catálogo sin precio.
5. Si la Situación **"Otro"** (26 expedientes) debe partirse en categorías con
   nombre propio.
6. **"Comentarios"**: motivo fila a fila o la nota única del Resumen.
7. **`Precio unitario` = licitado o adjudicado** (CONTEXTO.md sección 16),
   nunca confirmado por el cliente.
8. Siguen en pie las demás decisiones abiertas de las partes anteriores.
