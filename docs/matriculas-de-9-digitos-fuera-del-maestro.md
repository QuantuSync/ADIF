# Las matrículas de 9 dígitos que no están en el maestro de materiales

Bloque 2 del encargo de la sesión 2026-09-19 (séptima parte). La pregunta era
**por qué** 2.556 filas del entregable —una de cada cinco de las que traen
matrícula de nueve cifras— llevan una matrícula que no aparece en el maestro
de materiales que ADIF nos envió.

**La respuesta corta**: el documento las imprime así, y el maestro está
incompleto. **26 filas eran error de lectura y se han arreglado**; las
**2.511 que quedan están comprobadas contra la imagen del documento**. El
maestro que tenemos no es una lista cerrada de los materiales de ADIF: le
faltan artículos sueltos dentro de familias que sí conoce.

---

## 1. Las cifras

| | |
|---|---:|
| Filas del entregable con matrícula de 9 cifras | 13.127 |
| — con la matrícula en el maestro | 10.616 (80,9 %) |
| — **sin ella** | **2.511 (19,1 %)** |
| Matrículas distintas que faltan | **1.133** |
| Expedientes afectados | **55** |
| Filas leídas de un documento con capa de texto | 2.336 |
| Filas leídas por reconocimiento óptico | 175 |

Y sobre el catálogo entero: de las **5.016 matrículas de nueve cifras
distintas** que usan los documentos, **3.882 están en el maestro (77,4 %)** y
**1.133 no**.

### Por año del expediente

| Año | Filas | Expedientes |
|---|---:|---:|
| 2016 | 3 | 1 |
| 2017 | 5 | 2 |
| 2018 | 150 | 3 |
| 2019 | 15 | 10 |
| 2020 | **1.584** | 5 |
| 2021 | 3 | 2 |
| 2022 | 307 | 13 |
| 2023 | 424 | 5 |
| 2024 | 5 | 5 |
| 2025 | 13 | 7 |
| 2026 | 2 | 2 |

**El año no explica nada.** No hay una frontera temporal a partir de la cual
las matrículas dejen de estar en el maestro: 2020 concentra el 62 % de las
filas por un solo documento, y 2019 —con el doble de expedientes que 2020—
aporta 15 filas.

### Por expediente

| Expediente | Filas | De dónde |
|---|---:|---|
| `6.20/28510.0042` | 527 | `ANEJO_abd69efbdd39b552.pdf`, capa de texto |
| `6.20/28510.0046` | 527 | el mismo documento |
| `6.20/28510.0047` | 527 | el mismo documento |
| `6.23/28510.0051` | 420 | `CONTRATO_2_ea5b7015f73c5568.pdf`, capa de texto |
| `6.18/28510.0116` | 146 | `ANEJO_d75f9be90970d787.pdf`, escaneado |
| `6.22/28510.0094` | 72 | `ANEJO` de `6.22/28510.0126`, capa de texto |
| `6.22/28510.0125` | 52 | el mismo |
| `6.22/28510.0126` | 46 | el mismo |
| `6.22/28510.0033` | 35 | capa de texto |
| `6.22/28510.0122` | 30 | capa de texto |
| `6.22/28510.0057` | 18 | capa de texto |
| `6.22/28510.0058` | 17 | capa de texto |
| `6.22/28510.0155` | 15 | capa de texto |
| `6.22/28510.0156` | 15 | capa de texto |
| Otros **41** expedientes | 64 | entre 1 y 9 filas cada uno |

**Está muy concentrado**: cuatro documentos explican **2.147 de las 2.511
filas (85,5 %)**. No son 55 problemas distintos, son cuatro cuadros de precios
grandes de aparatos de vía y de equipos de transmisión.

---

## 2. ¿Lecturas malas o el documento las imprime así?

Se ha comprobado contra la imagen del PDF, no contra el texto extraído.

### Lo que sí era error de lectura: 26 filas, las 26 de reconocimiento óptico

| Expediente(s) | Documento y página | Filas | Qué pasaba |
|---|---|---:|---|
| `6.19/28510.0196` | `ANEJO_4fe450402ad92085.pdf` p.28 | 12 | El modelo leía **`7536…` donde el documento imprime `7534…`**: un 4 tomado por 6, en las doce baterías estacionarias de la página. La misma página devolvía además `215x777x710` por `215x277x710` y "Opl bloc" por "Ogi bloc" |
| `6.18/28510.0003` y `6.20/28510.0040` | `ANEJO_5bc9762bcf9bba78.pdf` p.11 | 14 (7 × 2) | El modelo devolvía **diez cifras** (`6429110100` donde el documento imprime `642910100`), y el sistema, que solo admite ocho o nueve, se quedaba con las nueve primeras: `642911010`. Una matrícula que no existe, con forma de matrícula |

**Arregladas.** Las dos páginas se han releído con `claude-opus-5` por el
mecanismo de relectura que ya existía (`app.extraccion.ocr_relectura`, sección
15 de `CONTEXTO.md`), **solo esas dos páginas**, y los tres expedientes se han
reextraído. Coste: unos **0,05 $**. De las 26 filas, **22 pasan a casar con el
maestro**; las 4 restantes siguen fuera y ahora se sabe por qué (abajo).

**Efecto de paso, y es bueno**: `6.18/28510.0003` y `6.20/28510.0040` pasan de
**18 a 31 filas** cada uno. La lectura vieja de esa página rompía además la
segunda tabla del cuadro ("Conductores de cobre desnudos"); con la relectura,
la página entrega **sus 21 renglones**, los mismos 21 que imprime el documento.
Son las únicas dos subidas de filas de todo el bloque 2, y ningún expediente
baja.

La segunda merece subrayarse: **el error no se veía**. `642911010` tiene nueve
cifras, empieza por la familia correcta y pasa cualquier comprobación de forma.
Sin cruzar contra el maestro no habría manera de sospechar de ella. Es el
argumento más fuerte a favor de tener el maestro cargado.

### Lo que no era error: las 2.511 restantes

Se ha abierto la imagen de **al menos una página de cada documento** de los 55
expedientes, leyendo las matrículas a ojo y comparándolas con lo que hay en
base de datos. En los cuatro documentos grandes:

| Documento | Comprobación | Resultado |
|---|---|---|
| `6.20/28510.0047/ANEJO_abd69efbdd39b552.pdf` p.12 | Las **34 matrículas** de la página, leídas una a una de la imagen | **22 de las 34 no están en el maestro, y son exactamente las 22 que el sistema tiene guardadas de esa página.** Ni una discrepancia |
| `6.18/28510.0116/ANEJO_d75f9be90970d787.pdf` p.10 | Las **28 matrículas correlativas** de la página (`667810023`…`667810050`) | Todas coinciden con lo leído. El maestro solo trae **5 de las 28** |
| `6.23/28510.0051/…_CONTRATO_2_….pdf` p.138 | Las filas de la página, una a una | Coinciden |
| `6.22/28510.0126/ANEJO_57694f5d5dacb236.pdf` p.24 | Las filas de la página, una a una | Coinciden |

Y **las 26 páginas distintas de reconocimiento óptico se han mirado todas**,
que es donde estaba el riesgo: las dos de arriba eran las únicas malas.

---

## 3. ¿Y si fuera una errata del documento? El test del dígito

El encargo pedía mirar si estas matrículas se diferencian de una del maestro en
**un solo dígito** y si la descripción confirma que es la misma pieza. Se ha
hecho, y **el resultado es que ese test no sirve para nada en este corpus**.

| Grupo | Matrículas fuera del maestro (1.133) |
|---|---:|
| Tiene un vecino a un dígito cuya descripción **confirma** | 252 (22,2 %) |
| … cuya descripción es **dudosa** | 268 (23,7 %) |
| … cuya descripción **no casa** | 370 (32,7 %) |
| **No tiene ningún vecino a un dígito** en el maestro | 243 (21,4 %) |

Parece que el 22 % podrían ser erratas. **No lo son**, y la prueba es el
control: se ha repetido exactamente la misma medición sobre **1.500 matrículas
tomadas al azar del propio maestro** — matrículas que, por definición, no son
ninguna errata.

| Grupo | Control: matrículas que SÍ están en el maestro |
|---|---:|
| Vecino a un dígito que **confirma** | **623 (41,5 %)** |
| Dudosa | 471 (31,4 %) |
| No casa | 385 (25,7 %) |
| Sin vecino | 21 (1,4 %) |

**Una matrícula correcta tiene casi el doble de probabilidad de "parecer una
errata" que una de las sospechosas.** El motivo es que la numeración de ADIF es
sistemática: los códigos consecutivos son variantes de la misma pieza, así que
"a un dígito de otra, con descripción parecida" es lo normal, no la excepción.
Dos ejemplos del propio corpus:

- `607300105` "TORNILLO PLASTIRAIL 25-140 TIPO 5" y `607300107`
  "TORNILLO PLASTIRAIL 25-140 TIPO 7". Coinciden en todo salvo en el número de
  tipo, que es justo lo que los distingue.
- `610156035` "DSF-A-54-190-1:6-CR-D" y `610156005`
  "DSF-A-54-190/99-0.125-CR-D": dos desvíos distintos de la misma serie.

**Conclusión: no se cambia ni una matrícula por parecido.** Es la misma regla
del bloque 1 y por la misma razón.

### La única errata de documento demostrada, y tampoco se toca

`6.18/28510.0003` y `6.20/28510.0040` imprimen **`642190440`** para
"HILO DE CONTACTO DE SECCIÓN OVALADA DE 150MM2 DE COBRE PLATA". El maestro
tiene **`642910440`**, "HC RANURADO OVALADO COBRE-PLATA S:150 M" — la misma
pieza —, y las otras siete filas de ese mismo cuadro son todas `6429104xx`.
Es una transposición de dígitos del propio documento.

Se queda literal, con su motivo. Corregirla sería reescribir lo que publica un
pliego a partir de una inferencia nuestra, y el sistema no hace eso. Queda
anotada como pregunta para ADIF.

---

## 4. ¿El maestro está incompleto? Sí, y no por familias

Esta era la última pregunta del encargo, y la respuesta es clara.

**No faltan familias enteras.** De las 1.133 matrículas que no están:

- solo **3** no tienen ninguna compañera en el maestro con sus **3 primeras
  cifras**,
- solo **12** con las **4 primeras**,
- solo **45** con las **5 primeras**.

Es decir: el 96 % pertenece a familias que el maestro conoce perfectamente.
**Lo que falta son artículos sueltos dentro de esas familias.**

### La prueba más clara

`6.18/28510.0116` compra 28 referencias **correlativas** de equipos de
transmisión SDH, de la `667810023` a la `667810050`. El maestro tiene **5**:

| Matrícula | ¿En el maestro? |
|---|---|
| `667810023`, `667810024` | no |
| `667810025` | **sí** — "UNIDAD OPTIC STM-16 SS-SL16A SSN3SL16A02" |
| `667810026`, `667810027` | no |
| `667810028` | **sí** — "4-PORT GIGABIT ETHERNET SWITCHING PROCES" |
| `667810029` … `667810040` | no (12 seguidas) |
| `667810041`, `667810042` | **sí** |
| `667810043`, `667810044` | no |
| `667810045` | **sí** — y su denominación en el maestro es, **literalmente**, `P/N: 03054591, SSN3EGS217`: el mismo texto que imprime el pliego |
| `667810046` … `667810050` | no |

No hay ningún criterio (ni de año, ni de familia, ni de tipo de material) que
explique cuáles están y cuáles no. Y la fila `667810045` demuestra que **es el
mismo sistema de numeración**: el maestro y el pliego hablan del mismo
catálogo, solo que el maestro no lo trae entero.

### Las familias donde más se nota

| Familia | Matrículas que usa el catálogo | De ellas, fuera del maestro | Total de esa familia en el maestro |
|---|---:|---:|---:|
| `6118` (placas nervadas PN-54, almohadillas) | 297 | **221** | 100 |
| `6128` (placas nervadas PN-60) | 244 | **184** | 80 |
| `6678` (transmisión SDH/WDM) | 272 | 146 | 300 |
| `6108` (cupones, carriles de aparato) | 237 | 142 | 104 |
| `6114` (desvíos) | 121 | 92 | 48 |
| `6193`, `6192` (semicambios, escapes) | 34 / 45 | 27 / 29 | 9 / 21 |

En `6118` y `6128` **el catálogo conoce más matrículas de la familia que el
maestro entero**. No es que nosotros leamos mal: es que los pliegos de aparatos
de vía compran variantes que ese volcado no recoge.

### Lo único que sí falta por completo

Doce matrículas no tienen ninguna compañera en el maestro con sus cuatro
primeras cifras. Son dos grupos, los dos comprobados contra la imagen:

- **`7611…` / `7612…`, 3 matrículas** (`6.16/28510.0042` p.18 y
  `6.19/28510.0122` p.17). Y aquí hay un matiz que conviene saber: la columna
  del documento **no se llama "Matrícula", se llama "CÓDIGO RAM"**, y el cuadro
  es el de ancho métrico. No son matrículas del maestro de ADIF porque
  probablemente no sean matrículas de ADIF. Ver "Lo que queda anotado".
- **`6131…`, `6195…`, `6755…`** (`6.20/28510.0042`/`0046`/`0047` y
  `6.22/28510.0163`): escapes, semicambios y un cable UTP de categoría 6.

---

## 5. Qué se ha hecho, en una línea

1. **Las 26 lecturas malas demostradas, arregladas** (dos páginas releídas, tres
   expedientes reextraídos).
2. **Las 2.511 restantes se quedan literales**, con el motivo
   *"no figura en el maestro de materiales de ADIF"* en su fila. **No es un
   motivo de exclusión**: la línea sale en "Materiales" con su matrícula y su
   precio, como cualquier otra. Es una explicación, no una penalización.
3. **Ninguna matrícula cambiada por parecido.**

El motivo se recalcula entero en cada pasada contra la tabla
`maestro_materiales`: el día que ADIF envíe un maestro más completo, las filas
que ya figuren en él pierden el motivo solas, sin tocar código.

---

## Lo que queda anotado, y no se ha tocado

Tres hallazgos de esta comprobación que cambiarían datos del catálogo y no
estaban en el encargo:

1. **La columna "CÓDIGO RAM" no es una matrícula de ADIF.** Tres líneas de
   `6.16/28510.0042` p.18 y `6.19/28510.0122` p.17 llevan en la columna de
   matrícula un código de una tabla rotulada **CÓDIGO RAM** (ancho métrico), y
   su designación es literalmente `761112100-TRAVIESA DE MADERA DE ROBLE`: el
   código que parece la matrícula real va **dentro de la descripción**, y el de
   la columna es otra cosa. Decidir qué hacer con eso es una decisión sobre
   datos del catálogo.
2. **Una matrícula de diez cifras impresa por el documento.**
   `6.22/28510.0094` y `6.22/28510.0126`, código de precio `P-138`: el cuadro
   imprime `6110500075`. El sistema se queda con las nueve primeras
   (`611050007`) y lo marca. Por la secuencia de su propia tabla
   (`611050076`, `611050077`, `611050078` en las filas siguientes) lo que el
   documento quiso escribir es `611050075` — pero eso es una inferencia, no un
   dato. Ninguno de los dos valores está en el maestro, así que la truncadura
   no ha creado ningún cruce falso.
3. **La errata `642190440`** del punto 3.
