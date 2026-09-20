# Sesión 2026-09-19 (séptima parte) — Las matrículas contra el maestro de materiales y las unidades raras

Continúa `docs/sesion-2026-09-19-decisiones-del-cliente-entradas-y-mantenimiento.md`.
Cuatro bloques, los cuatro terminados. **La sesión se paró a petición del
cliente con el bloque 4 empezado y se retomó la mañana del 2026-09-20**: el
reproceso completo es de la noche del 19 y no se repitió; el Excel, la
comparación y la auditoría en cero son de la mañana siguiente. La sección del
bloque 4 lo desglosa.

Regla de la sesión: commit y push a main al terminar cada bloque, con las
pruebas en verde; verificación reprocesando solo los expedientes afectados, y
**un solo reproceso completo, en el cierre**. Cumplida, con una salvedad
anotada: los bloques 2 y 3 fueron a un mismo commit porque comparten el
fichero de pruebas.

El encargo partía de una revisión que hizo el cliente por su cuenta del Excel
`catalogo_adif_2026-09-19-decisiones-y-entradas.xlsx` contra el maestro de
materiales de ADIF (`Ejemplo/Input/LISTADO_MATERIALES_UNIDAD_,MEDIDA.xlsx`,
32.116 materiales: 31.665 de nueve cifras, 440 de cuatro y 11 de diez).

**Sus tres cifras de partida se reproducen exactamente**: 390 filas con
matrícula de 8 dígitos (378 distintas, ninguna en el maestro), 2.556 filas con
matrícula de 9 dígitos que no está en el maestro, y **44 "casos"** de
equivalencia por sufijo — que resultan ser 44 **pares** (matrícula de 8,
candidata de 9), sobre 23 matrículas distintas.

---

## Bloque 1 — Las matrículas de 8 dígitos

### 1.1 — ¿Las imprime el documento, o perdemos un dígito?

**Las dos cosas, y saberlo separaba lo que había que arreglar de lo que no.**

Lo primero que salió al mirar de dónde venían las 390 filas: **377 de 377 son
de documentos escaneados, leídos por reconocimiento óptico**; solo 13 salen de
un documento con capa de texto. Eso hacía la hipótesis del cliente —"estamos
perdiendo un dígito al leer"— mucho más plausible de lo que parecía.

La comprobación se hizo **contra la imagen del PDF**, no contra el texto
extraído: se rasterizaron las **31 páginas distintas** que aportan esas 390
filas y se leyeron sus matrículas a ojo.

**El documento SÍ imprime 8 dígitos en 18 de los 20 expedientes.** Ejemplos
verificados:

| Expediente | Página | Lo que imprime |
|---|---|---|
| `6.16/28510.0042` (178 filas) | 11-17 | `60300100`, `60300101`, `60300103`… la tabla entera, en las siete páginas |
| `6.16/28510.0161` (133 filas) | 11-17 | `60120010`, `60120020`, `60120030`… |
| `6.18/28510.0066` (28 filas) | 10 | `59020019`… `59020046`, correlativas |
| `6.16/28510.0174` (11 filas) | 18, 20 | `60102180`, `60104155`, `60106018`… |
| `6.20/28510.0041` (6 filas) | 35 | `71590012`, `71590015`, `71590018`… (capa de texto) |

Tres detalles que confirman que no es un problema de lectura:

- **Hay páginas que mezclan las dos longitudes.** `6.16/28510.0165` p.9 imprime
  `591200015`, `591200023`, `591200017`, `591200016`, `591200002` **y**
  `59100085`, en la misma tabla. `6.19/28510.0215` p.13 y `6.19/28510.0113`
  p.13, igual. Un fallo de lectura no elegiría.
- **El de 8 dígitos a veces es una errata del propio pliego.**
  `6.20/28510.0042`/`0046`/`0047` p.12 imprime `61286119` para
  "PLACA NERVADA ESPECIAL PNE-60-119" en una columna donde todo lo demás es de
  nueve (`612860120`, `613860108`…). Es un documento con capa de texto: ahí no
  hay reconocimiento óptico que culpar.
- **`6.19/28510.0126`/`0167` p.18** imprime `60251340` cuando sus vecinas de
  tabla son `642510300` y `642510320`. Otra errata del pliego, leída bien.

### 1.2 — Las ocho que sí eran error de lectura

| Expediente | Página | Filas | Lo que imprime el documento | Lo que leíamos |
|---|---|---:|---|---|
| `6.19/28510.0207` | 13 | 4 | `645710150`, `645710200`, `645710175`, `645710700` | `64571015`, `64571020`, `64571017`, `64571070` |
| `6.19/28510.0207` | 15 | 3 | `647120100`, `647120150`, `647120301`, `647120302` | `64712010`, `64712015`, `64712030` |
| `6.17/28510.0023` | 9 | 1 | `664410004` | `66641004` |

El modelo de reconocimiento óptico **perdía el último dígito** en las siete de
`6.19/28510.0207`, y solo en las que empiezan por `6457101`/`6471201` — en la
misma página leía bien `591220250`, `740400510` y `740400511`, de nueve cifras.

Y en la p.15 la truncadura **fundía dos líneas en una**: `647120301` (AP81-4) y
`647120302` (AP81-5) daban las dos `64712030`, y el catálogo se quedaba con
una. Por eso ese expediente tenía 4 líneas en esa página y el documento
imprime 5.

**Arreglado con el mecanismo que ya existía**
(`app.extraccion.ocr_relectura`, sección 15 de `CONTEXTO.md`): relectura de
**esas tres páginas y solo esas**, con `claude-opus-5`, y reextracción de los
dos expedientes. Las ocho quedan con sus nueve cifras, y `6.19/28510.0207`
pasa de **22 a 23 filas**. Coste: unos 0,04 $.

**La lección, y no es menor**: los pares de equivalencia que más "certeza"
daban —`64712015` → `647120150` "APOYO MANUAL AP62", `64571015` →
`645710150`— **no eran equivalencias entre dos formatos: eran la misma
matrícula a la que le faltaba un dígito**. 12 de los 44 pares de partida
desaparecen al corregir la lectura. El parecido que más convence puede ser el
síntoma de un error, no una equivalencia.

### 1.3 — El motivo, y por qué la matrícula se queda literal

Las **382 filas** que quedan (370 matrículas distintas, 20 expedientes) llevan
en su línea el motivo:

> *matrícula con formato antiguo de 8 dígitos, no figura en el maestro actual
> de ADIF*

`app.catalogo.matriculas_fuera_del_maestro` lo calcula contra la tabla
`maestro_materiales`, **una consulta por llamada a `guardar_lineas_catalogo`**,
no una por línea. Va ahí y no en `_construir_campos` porque el maestro vive en
base de datos y esa función no ve la sesión. Cuatro condiciones:

1. **Idempotente**: `motivo_revision` se recalcula entero en cada pasada, así
   que reprocesar no duplica el texto ni deja el motivo pegado.
2. **Se retira solo**: el día que ADIF mande un maestro que ya las traiga, el
   motivo desaparece sin tocar código. Probado.
3. **Sin maestro cargado no escribe nada.** Sin listado contra el que
   comprobar no se puede afirmar que una matrícula no figure en él, y marcar
   382 filas por el hueco de una fuente de entrada sería un motivo falso.
4. **No es motivo de exclusión**: la fila sale en "Materiales" con su
   matrícula, como cualquier otra. Probado también.

### 1.4 — La tabla de candidatas: 386 pares, ninguno aplicado

`docs/matriculas-8-digitos-y-el-maestro.md`, con cada matrícula de 8 dígitos,
sus candidatas de 9, la denominación del maestro de cada una, la descripción
del documento y el veredicto.

| Grupo | Pares |
|---|---:|
| Confirma con certeza | **2** |
| Dudosa | **5** |
| No casa | **25** |
| Sin ninguna candidata | **354** |
| **Total** | **386** |

**Los dos que "confirman" no sirven ninguno de los dos**, y eso es lo
importante del documento:

- `66441037` → `664410373` "VENTILADORES MANDOS CENTRALES HIPATH". La
  descripción confirma… y **el propio documento lo desmiente**:
  `6.17/28510.0023` p.11 compra **las dos**, una debajo de la otra, con
  referencias de fabricante distintas (`S30807-K6723-X` y `C39165-A7070`) y
  precios distintos (82,50 € y 109,22 €).
- `60730000` → `607300000` "TIRAFONDO DE VIA, TIPO NUMERO 6, GALV./CROMAT".
  Este sí tiene a favor una evidencia independiente: la candidata aparece en
  el catálogo, en tres pliegos de 2022, con **la misma descripción** y un
  precio coherente con la inflación (0,87 € en 2016 → 1,72 € en 2022). Lo
  mismo pasa con `60731000` → `607310000` (2,00 € → 3,02 €), clasificado como
  dudoso porque el maestro añade "CON ARANDELA".

Son los dos candidatos con más fundamento de los 386 pares, y **tampoco se
tocan**: decidir que dos códigos de ADIF son el mismo material es una decisión
de ADIF.

---

## Bloque 2 — Las matrículas de 9 dígitos que no están en el maestro

Todo medido en `docs/matriculas-de-9-digitos-fuera-del-maestro.md`. Resumen:

**26 filas eran error de lectura, las 26 de reconocimiento óptico, y están
arregladas:**

- `6.19/28510.0196` p.28: el modelo leía `7536…` donde el documento imprime
  `7534…` — un 4 tomado por 6 en las doce baterías estacionarias de la página.
  Corregidas, **las doce pasan a estar en el maestro**, con su denominación
  ("BATERIA 11 OSP 1100"…).
- `6.18/28510.0003` y `6.20/28510.0040` p.11 (el mismo documento): el modelo
  devolvía **diez cifras** (`6429110100` donde el documento imprime
  `642910100`), y el sistema, que solo admite ocho o nueve, se quedaba con las
  nueve primeras: `642911010`. **Ese error no se veía**: nueve cifras, familia
  correcta, forma impecable. Sin cruzar contra el maestro no había manera de
  sospecharlo.

Las dos páginas releídas con `claude-opus-5` y los tres expedientes
reextraídos. **Efecto de paso**: la lectura vieja de esa página rompía además
la segunda tabla del cuadro, así que `6.18/28510.0003` y `6.20/28510.0040`
pasan de **18 a 31 filas** cada uno — los 21 renglones que imprime la página,
ni uno más.

**Las 2.511 restantes están comprobadas contra la imagen y se quedan
literales**, con el motivo *"no figura en el maestro de materiales de ADIF"*.
La comprobación más concluyente: en `6.20/28510.0047/ANEJO` p.12 se leyeron a
ojo las 34 matrículas de la página — **22 no están en el maestro, y son
exactamente las 22 que el sistema tiene guardadas**.

### El test del dígito no discrimina, y está medido

El encargo pedía comprobar si esas matrículas se diferencian de una del maestro
en un solo dígito con descripción que lo confirme. Se hizo, y el resultado
**parece** prometedor: el 22,2 % de las 1.133 matrículas que faltan lo cumple.

Pero el control lo tumba: repitiendo la misma medición sobre **1.500
matrículas tomadas al azar del propio maestro** —que por definición no son
erratas— la cifra sube al **41,5 %**. Una matrícula correcta "parece una
errata" casi el doble de a menudo que una de las sospechosas, porque la
numeración de ADIF es sistemática: `607300105` es "TORNILLO PLASTIRAIL 25-140
TIPO 5" y `607300107` es el "TIPO 7". **Ninguna matrícula cambiada por
parecido.**

### El maestro está incompleto, y no por familias

- Solo **3** de las 1.133 no tienen ninguna compañera en el maestro con sus 3
  primeras cifras; **12** con las 4 primeras; **45** con las 5.
- `6.18/28510.0116` compra **28 referencias correlativas** de equipos de
  transmisión SDH (`667810023`…`667810050`). El maestro trae **5**, salteadas,
  sin ningún criterio. Y la denominación de una de ellas (`667810045`) es
  **literalmente** el mismo texto que imprime el pliego: es el mismo sistema
  de numeración, solo que el listado no lo trae entero.
- En las familias `6118` y `6128` (placas nervadas PN-54 y PN-60) **el
  catálogo conoce más matrículas que el maestro entero**: 297 y 244 frente a
  100 y 80.

---

## Bloque 3 — Las unidades

### `Ml` es metro lineal: unificado con `m`

Las tres filas son de `6.17/28510.0007` p.20, el presupuesto de licitación de
un suministro de balasto: "Colocación de lámina geotextil" (800 Ml), "Muro de
contención…" (400 Ml) y "Ejecución de zona de paso próxima a la vía" (400 Ml).
El mismo cuadro usa `m3` y `m2` para volumen y superficie en las filas de al
lado, y `PA` para la partida alzada. **Un muro de contención no se mide en
mililitros.**

`app.extraccion.unidad_medida` no lo unificaba por esa duda exacta ("ml puede
ser metro lineal o mililitro", sesión 2026-09-16). El corpus la deshace, así
que `ml` entra en `_FORMA_UNICA` y **el literal se conserva en
`unidad_medida_original`**: la unificación es reversible y se ve. "m/l"
(metros partido por litros) sigue sin tocarse, porque es una compuesta.

### `transporte`: es una unidad de verdad, y no se ha tocado

15 filas de `6.21/28510.0108`-`0112`, tres conceptos repetidos entre cinco
expedientes hermanos: "Importe mínimo de un transporte por ferrocarril",
"Transporte por camión especial hasta 300 Km" y "… a una distancia mayor a 300
Km".

**Qué es**: el cuadro escribe en su columna de precio **`€/transporte`**, en
las mismas tablas en las que escribe `€/Ton*km` para las filas de
tonelada-kilómetro (4.084 líneas de esa misma familia de expedientes). No es
un concepto colado de otra columna: es **el denominador del precio**, lo que se
paga por cada transporte, igual que `t·km` es lo que se paga por tonelada y
kilómetro.

**Qué NO debería ser**: `t·km` es justo la unidad de las OTRAS filas del mismo
cuadro, las que sí se pagan por tonelada-kilómetro. Cambiarla por `t·km` diría
que 1.900,00 € es el precio de un camión por tonelada y kilómetro, cuando es
el precio del viaje entero. Y dejarla vacía con su motivo perdería un dato que
el documento sí publica.

**Se queda como está**, y la decisión es del cliente. Ver
`docs/preguntas-pendientes-cliente.md`.

### El repaso del resto: `P` es el único valor raro que queda

Las 18 unidades del Excel, con su recuento:

| Unidad | Filas | |
|---|---:|---|
| `ud` | 10.509 | |
| *(vacía)* | 7.604 | con su motivo en la columna de motivos |
| `m` | 918 | |
| `kg` | 451 | |
| `t` | 311 | |
| `t·km` | 82 | tonelada-kilómetro, transporte de balasto |
| `m3` | 69 | |
| `dm3` | 16 | |
| `m3·km` | 15 | |
| `transporte` | 15 | arriba |
| `h` | 11 | |
| `ud/día` | 8 | alquiler de equipo |
| `m2` | 8 | |
| `t·mes` | 5 | |
| `mes` | 4 | |
| `Ml` → `m` | 3 | arriba |
| `elemento·mes` | 3 | |
| `P` | 3 | abajo |

**`P` es la única rareza que queda, y tiene una particularidad: no sale de
ningún documento.** Son las tres filas de la matrícula `612860020` ("PLACA
NERVADA PN-60- 1:20") en `6.20/28510.0042`/`0046`/`0047`. Su cuadro de precios
—comprobado contra la imagen de la p.8— **no tiene columna de unidad**:
`MATRÍCULA | DESIGNACIÓN | PLANO | ET | PRECIO`. El valor llega por la otra
vía, la que rellena la unidad desde el maestro de materiales cuando la línea
tiene matrícula y no tiene unidad: en el maestro, la "UM base" de `612860020`
es **`P`**, un código propio de SAP cuyo nombre completo ese listado no trae
(16 materiales del maestro lo usan). No es un fallo de lectura ni un valor
inventado: es la unidad que ADIF tiene registrada. **Pregunta para ADIF: qué
es `P`.**

Todo lo demás son unidades estándar o compuestas legítimas. **Ninguna otra
rareza.** (En base de datos hay además `l`, `par` y `juego`, en líneas que no
llegan al entregable.)

---

## Bloque 4 — Cierre

La sesión se paró a mano con este bloque empezado y se retomó la mañana
siguiente (2026-09-20). Lo que sigue son las cifras del cierre completo; al
final de la sección queda escrito qué se midió en cada mitad, porque el
reproceso completo —la parte cara— es de la noche anterior y no se repitió.

### Pruebas

**1.328 pasan**, ninguna saltada (1.304 al cerrar la sexta parte, **+24**).
Las nuevas están en `engine/tests/test_matriculas_y_unidades_2026_09_19_septima.py`
(24: las 21 de los bloques 1 a 3 y 3 del Resumen del Excel) y tres reescritas
o añadidas en `engine/tests/extraccion/test_unidad_medida.py` (la que
codificaba explícitamente que "ml" no se unificaba, que es justo la decisión
que cambia).

### El reproceso completo, con la red apagada

`POST /mantenimiento/ejecutar` con `forzar: true`, `sindicacion_desactivada:
true` y `busqueda_desactivada: true`. **Uno solo**, como pedía la regla de la
sesión (ciclo 30254).

| | |
|---|---|
| Expedientes reextraídos | **517** (519 evaluados) |
| Tiempo | **21 min 40 s** (1.300,2 s) |
| `descargas_lanzadas` | **0** |
| `saltados_descarga` | 519 |
| `descubrimiento` / `descubrimiento_busqueda` | `None` / `None` |

### El entregable

```
C:\dev\ADIF\catalogo_adif_2026-09-20-matriculas-y-unidades.xlsx
```

1.958.194 bytes, 3 min 11 s de generación, tres hojas ("Materiales",
"Conciliación", "Resumen"), **18 columnas**, las mismas y en el mismo orden
que el Excel anterior.

### La comparación con `catalogo_adif_2026-09-19-decisiones-y-entradas.xlsx`

**20.035 → 20.062 filas (+27).** 390 expedientes aportan líneas en los dos,
**ninguno desaparece, ninguno pierde filas**, y solo tres las ganan:

| Expediente | Filas | Por qué |
|---|---|---|
| `6.18/28510.0003` | 18 → **31** (+13) | La lectura vieja de la p.11 rompía la segunda tabla del cuadro. Son los 21 renglones que imprime la página, ni uno más |
| `6.20/28510.0040` | 18 → **31** (+13) | El mismo documento que el anterior |
| `6.19/28510.0207` | 22 → **23** (+1) | La truncadura de matrícula fundía `647120301` (AP81-4) y `647120302` (AP81-5) en una sola línea |

**Ningún material desaparece.** Salen 51 matrículas y entran 34, y las 51
están una a una explicadas: todas son la lectura vieja de una matrícula que
esta sesión corrigió.

| Expediente | Salen | Entran | Qué pasó |
|---|---:|---|---|
| `6.17/28510.0023` | 25 (`66641004`, `666410102`…`666411089`) | 25 (`664410004`, `664410102`…`664411089`) | La relectura de la p.9 corrigió la familia entera: un `6` por un `4` en la tercera cifra. El maestro trae **267** matrículas `6644…` y **ninguna** `6664…` |
| `6.19/28510.0207` | 7 (`64571015`…, `64712030`…) | 8 (`645710150`…, `647120302`) | El dígito perdido; una línea más porque la truncadura fundía dos |
| `6.18/28510.0003` y `6.20/28510.0040` | 7 (`642911010`…`642911044`) | 19 | Las diez cifras truncadas a nueve, más la segunda tabla que la lectura vieja rompía (`642950…`, `642970…`) |
| `6.19/28510.0196` | 12 (`753600007`…`753600095`) | — | Corregidas a `7534…`, que **ya estaban en ese mismo expediente** por otra página: por eso no figuran como "nuevas". El maestro trae **87** matrículas `7534…` y **ninguna** `7536…` |

**Las 25 de `6.17/28510.0023` merecen una nota**, porque el bloque 1 contó
una sola: la relectura óptica se pide por página, no por matrícula, así que
arreglar `66641004` arregló de paso las otras 24 de la misma página, todas
con el mismo fallo (`6664…` por `6644…`). El maestro lo confirma sin margen:
no existe ni una matrícula `6664…` en sus 32.116 filas.

Las descripciones cambian en **esos cinco expedientes y solo ahí**
(`6.17/28510.0023` −8/+8, `6.19/28510.0196` −24/+24, `6.19/28510.0207` −5/+5,
`6.18/28510.0003` y `6.20/28510.0040` −3/+16 cada uno). Son la misma
relectura mejorando el texto de la página entera:
`TARJETA HIBRIDA DE LINEAS Y ABONAOS` → `ABONADOS`,
`MÓDULO SUBSCRIBER LINE MODULE DIGITAL(2B10)` → `(2B1Q)`,
`MÓDULO NCI21` → `NCU12`, `Modem superviviencia` → `supervivencia`,
`2V 9 0SP 900 (215x19x/10)` → `(215x193x710)`.

**Fuera de esos cinco expedientes, el Excel no cambia en una sola celda**:
comparando la terna (expediente, matrícula, descripción) de las otras 19.968
filas, 0 aparecen y 0 desaparecen.

Las unidades cambian exactamente lo previsto: `Ml` **3 → 0**, `m` 918 →
**921** (las tres de `Ml`), `kg` 451 → **477** (+26, los cables de las dos
tablas recuperadas) y la unidad vacía 7.604 → **7.605** (+1, la línea
recuperada de `6.19/28510.0207`). +26 y +1 son las 27 filas nuevas. **17
unidades distintas**, una menos porque `Ml` ya no existe.

### El Resumen del Excel: los dos motivos nuevos

| | |
|---|---:|
| Líneas con matrícula de 8 dígitos fuera del maestro | **382** |
| Líneas con matrícula de 9 dígitos fuera del maestro | **2.500** |

### Una diferencia de 11 filas que hay que dejar escrita

La medición del bloque 2 dice **2.511** filas del entregable con matrícula de
nueve cifras fuera del maestro, y el Resumen cuenta **2.500** con el motivo.
Las dos cifras son correctas y la diferencia está localizada: **11 filas están
fuera del maestro y no llevan el motivo.**

- **9 son líneas heredadas de un acuerdo marco** (`heredado_de_matriz`). La
  herencia (`app.extraccion.herencia_matriz`) deja `motivo_revision` fuera de
  `datos` a propósito, porque ahí "no hay motivo" significa "no se ha
  evaluado", y `guardar_lineas_catalogo` solo anota el motivo donde ese campo
  ya viene evaluado (`if "motivo_revision" in datos`). Son la matrícula
  `642950151` en ocho expedientes (`6.20/28510.0040`, `6.22/28510.0074`,
  `6.22/28510.0161`, `6.23/28510.0017`, `6.23/28510.0079`, `6.23/28510.0110`,
  `6.26/28510.0032`, `6.26/28510.0071`) y `642190440` en `6.20/28510.0040`.
- **2 son copias sueltas** de una matrícula que en ese mismo expediente sí
  lleva el motivo en sus otras apariciones: `611050007` en `6.22/28510.0094`
  (la copia cuya celda el sistema descartó por ilegible, `6,111E+09`) y
  `619050222` en `6.22/28510.0125`.

**No se ha tocado.** Añadir el motivo a esas 11 filas cambia datos del
catálogo y no estaba en el encargo. Anotado para el cliente.

### Conciliación, cuadre y recuento por Situación

La hoja "Conciliación" trae **534 expedientes** y su total de líneas es
**20.062**, el mismo número de filas que "Materiales" — `comprobar_cuadre` lo
exige para dejar generar el fichero, así que el cuadre no es una comprobación
posterior: sin él no habría Excel.

| Situación | Expedientes |
|---|---:|
| Aporta líneas | **390** |
| Publicado sin cuadro de precios | 54 |
| Los precios están en un acuerdo marco que no está publicado | 47 |
| Publicado dentro de la ficha de otro expediente | 17 |
| Licitación por lotes de la que solo se conocen algunos lotes | 9 |
| Documentos escaneados que no se han podido leer | 6 |
| El acuerdo marco del que depende tampoco publica precios | 3 |
| Sus documentos son de expedientes hermanos y ninguno es el suyo | 3 |
| Otro | 3 |
| El acuerdo marco está publicado pero no publica precios unitarios | 2 |
| Pendiente de procesar | **0** |
| **Total** | **534** |

### Auditoría: **0 errores**, 6 avisos

| Categoría | Gravedad | Afectados |
|---|---|---:|
| `sin_lote` | aviso | 19.758 líneas en 118 expedientes |
| `precio_desproporcionado` | aviso | 1.544 líneas en 83 expedientes |
| `cantidad_forma_anio` | aviso | 941 líneas en 32 expedientes |
| `importe_licitacion_compartido_entre_expedientes` | aviso | 24 |
| `importe_licitacion_repetido_en_el_mismo_expediente` | aviso | 8 |
| `lineas_duplicadas_codigo_precio_distinto` | aviso | 12 grupos, 26 líneas, 4 expedientes |

Los seis son los de siempre. **El error que quedó anoche ha desaparecido
solo, sin reprocesar nada**, que es exactamente lo que se predijo: era
`lineas_cambian_sin_cambiar_documentos` en `6.18/28510.0003`,
`6.20/28510.0040` y `6.19/28510.0207`, los tres expedientes a los que esta
sesión les releyó páginas con `claude-opus-5`. La comprobación mira
`documentos` y el recuento de líneas, no `cache_ocr_documento`, así que vio
cambiar las líneas sin cambiar el documento. Al pasar el recuento nuevo a ser
el de referencia, el aviso se apagó. **No se arregló con otro reproceso.**

Totales de la auditoría: 40.043 líneas, 612 expedientes. Columnas vacías:
`lote_id` 49,34 %, `cantidad` 48,42 %, `codigo_precio` 34,41 %,
`unidad_medida` 27,51 %, `precio_unitario` 2,90 %.

### Qué se midió en cada mitad

Porque la sesión se partió en dos y conviene que quede claro qué es de cuándo:

| | Noche del 19 | Mañana del 20 |
|---|---|---|
| Bloques 1, 2 y 3 | completos y subidos | — |
| Reproceso completo | **hecho** (ciclo 30254) | no se repitió |
| Pruebas | 1.328 | 1.328, vueltas a pasar con la imagen reconstruida |
| Excel | — | exportado, comparado y cuadrado |
| Auditoría | 6 avisos y 1 error | 6 avisos, **0 errores** |

La imagen del contenedor se reconstruyó antes de exportar: el código no está
montado en volumen, así que los dos contadores nuevos del Resumen no habrían
salido en el Excel sin ese paso.
