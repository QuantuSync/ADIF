# Sesión 2026-09-19 (cuarta parte) — El espacio que el contrato escribe como "!" y el precio adjudicado que se calculaba demasiado pronto

Continúa `docs/sesion-2026-09-19-cantidades-escaneados-y-situaciones.md`, que
dejó **cinco cosas medidas y sin decidir**. El cliente contesta las cinco: tres
se quedan como están y dos se aplican.

| | Decisión | Qué se ha hecho |
|---|---|---|
| 1 | Los 416 ceros de cantidad **se quedan** | Nada. Es lo que imprime el documento. |
| 2 | `p-3` frente a `P-3` **no se unifica** | Nada. Los 4 duplicados se quedan, y con ellos los 2 precios que la unificación habría vaciado. |
| 3 | El `!` de `4.26/28510.0005` **se corrige, si se demuestra** | Demostrado y aplicado. |
| 4 | El precio adjudicado **se arregla, y en general** | Aplicado a todo el corpus. |
| 5 | "elemento" **no entra como alias** | Nada. `3.17/28510.0028` se queda como está. |

---

## 3 — El espacio que la fuente del contrato escribe como "!"

### La condición del cliente, y la prueba

> *"Se corrige, pero solo si demuestras que en esa fuente todos los `!`
> corresponden a espacios. Si hay un solo `!` legítimo, no lo toques y
> dímelo. Mira si esa misma fuente aparece en otros documentos del corpus."*

**La prueba, contando carácter a carácter las 304 páginas del
`CONTRATO_1.pdf` de `4.26/28510.0005`** (documento 288), separando por la
fuente de la que sale cada carácter:

| Fuente | `!` que produce | Espacios que produce |
|---|---:|---:|
| `IPRJBU+Calibri` | **126.354** | **0** |
| `FFLBTV+Calibri` | **5.633** | **0** |
| `KNYRHX+Calibri-Italic` | **3.730** | **0** |
| `UONJAM+Calibri-Bold` | **2.094** | **0** |
| `ZCLLWB+Calibri-Italic` | **9** | **0** |
| `IDDCRV+Calibri-BoldItalic` | **9** | **0** |
| `SRGVMN+Calibri-Bold` | **6** | **0** |
| `UVADMM+Calibri-BoldItalic` | **6** | **0** |
| `HVXSSI+AdifFagoNoRegular` | 8 | 4 |
| `RURNCB+AdifFagoNoRegular` | 0 | 20.165 |
| `LDFKUA+Calibri` | 0 | 8.571 |
| `Times-Roman` | 0 | 4.864 |
| …otras 30 fuentes | 0 | resto |

**Los ocho subconjuntos de Calibri que producen los `!` no emiten un solo
espacio en 304 páginas: 137.841 `!` y 0 espacios.** Una fuente que nunca
escribe un espacio y escribe `!` a razón de uno por palabra no tiene otro
significado posible. Y **no hay ningún `¡` en el documento**, que es lo que
acompañaría a una exclamación real en castellano.

Así se lee su página 304, la del cuadro de precios:

```
21.4 CUADRO!DE!PRECIOS!Nº3:!MANO!DE!OBRA!
Denominación! Precio!
Precio!Mensual!de!Mantenimiento! 75.194,99!€!
Hora!Técnico!jornada!laboral! 42,00!€!
```

### El único `!` del documento que no es un espacio, y no es una exclamación

`HVXSSI+AdifFagoNoRegular` sí produce las dos cosas: **8 `!` y 4 espacios**,
todos en la página 49. Se han mirado los ocho en su contexto, y **no son
exclamaciones: son la letra "j"**. Esa fuente no trae tabla `ToUnicode`, así
que su texto sale como identificadores de glifo y el `!` es un glifo más:

```
(cid:5)(cid:26)(cid:18)(cid:13)(cid:7)!(cid:29)(cid:4)(cid:20)(cid:4)(cid:16)   ->  "a juicio"
(cid:14)(cid:6)(cid:7)(cid:11)(cid:18)!(cid:16)(cid:13)                        ->  "la mejor"
(cid:12)(cid:6)!(cid:6)                                                      ->  "baja"
(cid:6)(cid:17)!(cid:29)(cid:17)(cid:4)(cid:20)(cid:6)(cid:20)(cid:4)(cid:21)(cid:5)  ->  "adjudicación"
```

**Así que la respuesta exacta a la condición del cliente es: en la fuente que
produce las cinco descripciones (Calibri) todos los `!` son espacios, sin una
sola excepción; y en el documento no hay ningún `!` legítimo — el único que no
es un espacio es una letra.** Por eso la regla se ha acotado para que no pueda
tocar ese caso.

### La misma fuente en otros documentos del corpus

Sí aparece, y mucho: **78 de los 1.642 documentos con texto cacheado producen
algún `!`, 175.424 en total.** No es un caso aislado de un contrato.

Y **a nivel de fuente la afirmación no es general**: revisados los 78 uno a
uno, **75 tienen alguna fuente que produce a la vez `!` y espacios**
(mayoritariamente fuentes que `pdfplumber` no resuelve, `unknown`, y
`AdifFagoNoRegular`). Es el mismo fenómeno de la página 49: glifos sin tabla
de caracteres, donde el `!` es una letra.

Por eso la regla **no mira la fuente** —`app.catalogo` no la tiene delante—
sino la celda, con tres condiciones que se cumplen o no se cumplen sin
ambigüedad.

### La regla, y por qué es demostrable

`app.catalogo._recomponer_espacios_del_signo_admiracion`, aplicada a la
descripción de cada línea. Los `!` pasan a espacios **solo si**:

1. la celda trae **al menos dos** `!`;
2. la celda **no trae ningún espacio** — una descripción con palabras necesita
   separadores, y si no hay ninguno y sí hay `!`, los `!` son los separadores;
3. la celda **no trae ningún `(cid:`** — ese mundo es el de
   `app.extraccion.glifos_cid`, y es exactamente el de la página 49.

**Medido sobre las 39.651 líneas del corpus antes de aplicarla:**

| | Líneas |
|---|---:|
| Descripciones con `!` | **5** |
| De ellas, sin ningún espacio y sin `(cid:` (las que la regla toca) | **5** |
| Descripciones con `!` **y** un espacio (donde la regla tendría que decidir) | **0** |
| `!` en matrícula, código de precio o unidad de medida | **0** |

Es decir: **no hay ni un caso en todo el corpus en el que esta regla tenga que
decidir algo dudoso.** Toca cinco filas y no puede tocar más.

### Las cinco filas

| Antes | Después |
|---|---|
| `Precio!Mensual!de!Mantenimiento!` | Precio Mensual de Mantenimiento |
| `Hora!Técnico!jornada!laboral!` | Hora Técnico jornada laboral |
| `Hora!Técnico!jornada!nocturna!` | Hora Técnico jornada nocturna |
| `Hora!Técnico!jornada!festiva!` | Hora Técnico jornada festiva |
| `Gestión!de!reparación!` | Gestión de reparación |

Con esto los cinco conceptos de servicio de `4.26/28510.0005` dejan de salir
dos veces en el Excel con dos redacciones: el anejo ya los traía limpios y
ahora el contrato dice lo mismo.

---

## 4 — El precio adjudicado, después de la baja de su lote

### El encargo

> *"Se arregla, y en general, no solo en esa fila. El precio adjudicado de una
> línea no puede calcularse antes de conocer la baja de su lote. Dime cuántas
> líneas de todo el corpus estaban afectadas por ese orden y cuántas cambian
> de precio adjudicado."*

### El alcance, medido sobre las 20.093 líneas con lote

| Comprobación | Líneas |
|---|---:|
| **A. Tienen precio y su lote tiene baja, pero el adjudicado está vacío** | **14** |
| B. Tienen adjudicado y su lote no tiene baja (valor rancio) | **0** |
| C. Su adjudicado no cuadra con la baja de su lote | **0** |
| D. La baja de la línea no es la de su lote | **0** |

**14 líneas en todo el corpus**, y ninguna otra incoherencia. El defecto era
estrecho, no sistémico — pero silencioso, y el dato que se perdía es el que el
cliente mira.

### Las 14, y las dos vías por las que la baja llega tarde

| Expediente | Líneas | Por qué su baja se conoce después |
|---|---:|---|
| `6.24/28510.0008` | **13** | Su baja del **54 %** llega por la **herencia de acuerdo marco** (`app.extraccion.herencia_matriz`), que corre después del bucle de documentos. Sus 13 guantes y verificadores tenían precio y no adjudicado. |
| `4.26/28510.0020` | **1** | Su lote 1 tiene una **baja derivada de los importes** (2,5794 %), que se calcula al cerrar el expediente. Es la fila `P-12` que destapó la comparación de entregables de la tercera parte. |

En los dos casos el problema es el mismo y es de **orden**:
`construir_linea_catalogo` deriva `precio_adjudicado = precio_unitario ×
(1 − baja)` con la baja que se conoce **en el momento de construir la línea**,
y esas dos vías resuelven la baja más tarde.

### El arreglo

`app.catalogo.recalcular_precio_adjudicado`, llamada desde el orquestador
**al final de la extracción**, cuando las bajas de los lotes ya son
definitivas: han pasado la extracción de todos los documentos, la herencia de
acuerdo marco y la baja derivada de los importes. Rederiva el adjudicado desde
cero para cada línea **que tenga lote**, y alinea la baja de la línea con la de
su lote ("no hay una baja distinta por material dentro de un lote",
CONTEXTO.md sección 4).

No es otra fuente de precio adjudicado: es **la misma derivación** de la
sección 4, aplicada cuando ya se puede. Cuatro detalles deliberados:

- **Una huérfana sin lote no se toca**: no tiene de qué derivar, y así el
  arreglo no cambia datos de líneas que no llegan al entregable.
- **`None` sí borra un valor guardado**, igual que en la construcción de la
  línea (decisión de la sesión 2026-09-09, bloque 3): el adjudicado se
  recalcula desde cero en cada pasada por diseño, así que un lote que pierde
  su baja tiene que dejar sus líneas sin adjudicado.
- **La comparación tolera el redondeo de la columna** (`numeric(14,4)`). Sin
  eso, el valor recién derivado trae más decimales que el leído de la base de
  datos y cada pasada marcaría como cambiada cada una de las 20.093 líneas.
- **Se llama también cuando el expediente espera a su matriz**: uno que espera
  tampoco debe quedarse con un adjudicado calculado con una baja que todavía
  no era la suya.

Va con 7 pruebas en `engine/tests/test_decisiones_2026_09_19_cuarta.py`,
incluida la de que no cuenta como cambio lo que ya estaba bien y la de que una
huérfana no se toca.

---

## Cierre

### Pruebas

**1.213 pasan** (1.202 al cerrar la tercera parte, **+11**). Ninguna saltada.
Las nuevas, en `engine/tests/test_decisiones_2026_09_19_cuarta.py`: 5 del
signo de admiración (las cinco descripciones reales, más los contraejemplos de
una celda con un espacio de verdad, un solo `!` y el texto en glifos CID) y 7
del precio adjudicado (el hueco que rellena, que no cuenta como cambio lo que
ya estaba bien, que un lote sin baja deja la línea sin adjudicado, que una
línea sin precio no gana nada, que una huérfana no se toca y que la baja de la
línea se alinea con la de su lote).

### El reproceso completo, con la red apagada

| | |
|---|---|
| Expedientes reextraídos | **517** (519 evaluados) |
| Tiempo | **20 min 24 s** (1.224,0 s) |
| `descargas_lanzadas` | **0** |
| `saltados_descarga` | 519 |
| `sin_publicar_reintentados` | 0 (`sin_publicar_desactivado: True`) |
| `descubrimiento` / `descubrimiento_busqueda` | `None` / `None` |

Líneas en la base de datos: 39.651 → **39.646** (−5, ver abajo).

### Excel

```
C:\dev\ADIF\catalogo_adif_2026-09-19-adjudicado-y-espacios.xlsx
```

### Comparación con `catalogo_adif_2026-09-19-cantidades-y-escaneados.xlsx`

| | Antes | Ahora | |
|---|---:|---:|---|
| Filas de "Materiales" | 19.870 | **19.865** | **−5** |
| Columnas | 18 | **18** | = |
| Expedientes con filas | 373 | **373** | = |
| Filas de "Conciliación" | 534 | **534** | = |
| Materiales distintos **por matrícula** | 12.201 | **12.201** | **=** |
| Materiales distintos **por matrícula y precio** | 15.200 | **15.200** | **=** |
| Materiales distintos **por lote, matrícula y precio** | 17.025 | **17.025** | **=** |

**0 expedientes desaparecen, 0 aparecen, y 0 materiales perdidos por ninguna
de las tres claves.**

**Cada diferencia, una a una — son dos:**

**1. `4.26/28510.0005` pasa de 10 filas a 5.** Es el **único** expediente que
cambia de número de filas, y las 5 que se van son **exactamente el duplicado**
que la tercera parte había dejado anotado: sus cinco conceptos de servicio
salían dos veces, una del anejo (limpia) y otra del contrato
(`Precio!Mensual!de!Mantenimiento!`). Al recomponer los espacios, las dos
redacciones coinciden y la fusión por firma de material las une. **Que las
tres claves de materiales distintos den exactamente la misma cifra antes y
después es la prueba de que no se pierde nada**: no desaparece un material,
desaparece una copia.

Las cinco que quedan son las del anejo, con su texto y su precio sin cambios:

```
Precio Mensual de Mantenimiento   75.194,99 €
Hora Técnico jornada laboral           42,00 €
Hora Técnico jornada nocturna          50,00 €
Hora Técnico jornada festiva           61,00 €
Gestión de reparación                 105,00 €
```

Comprobado en la base de datos: **0 descripciones con `!` en las 39.646
líneas** (eran 5).

**2. 14 celdas de "Precio adjudicado" pasan de vacía a tener valor.** Las 14
que estaban afectadas por el orden, ni una más:

| Expediente | Celdas | Ejemplos |
|---|---:|---|
| `6.24/28510.0008` | **13** | `P-001` → 11,04 €; `P-004` → 23,92 €; `P-007` → 30,36 €; `P-008` → 40,02 €; `P-012` → 10,12 € |
| `4.26/28510.0020` | **1** | `P-12` → 5.197,389 € |

Comprobado en la base de datos: **0 líneas con precio, lote con baja y
adjudicado vacío** (eran 14). Filas del entregable con precio adjudicado:
**9.116 de 19.865**.

**Ninguna otra celda del entregable cambia**: 0 cambios de descripción entre
filas comparables (las cinco que se recomponen son las que desaparecen; las
que quedan ya estaban bien), 0 de cantidad, 0 de precio unitario, 0 de lote y
0 de código de precio.

### Cuadre de "Conciliación" con "Materiales"

```
suma de la columna de líneas de "Conciliación": 19.865
filas de la hoja "Materiales":                  19.865
```

**0 expedientes sin Situación.**

### Auditoría

**0 errores y 6 avisos**, los seis de siempre:

| Aviso | Afectados | Antes |
|---|---:|---:|
| Grupos de material repetido con códigos de precio distintos | 11 grupos, 22 líneas, 3 expedientes | igual |
| Huérfanas sin lote | 19.558 líneas en 114 expedientes | igual |
| Precios atípicos | **1.521** líneas en 79 expedientes | 1.522 |
| Cantidades con forma de año | 941 líneas en 32 expedientes | igual |
| Grupos de importe de licitación compartido | 54 grupos, 24 expedientes | igual |
| Expedientes con importe repetido entre sus lotes | 8 | igual |

El único aviso que se mueve es el de precios atípicos, una línea menos: la
copia de `4.26/28510.0005` que ha desaparecido. La auditoría del propio ciclo
dio 0 errores y 7 avisos, el séptimo `lineas_bajan_explicado_por_poda` sobre
un expediente — la regla reconociendo esa misma bajada de 5 filas como
explicada, que es para lo que existe.

### Recuento por Situación y total de filas

| Situación | Expedientes |
|---|---:|
| Aporta líneas | **373** |
| Publicado sin cuadro de precios | **63** |
| Los precios están en un acuerdo marco que no está publicado | **47** |
| Publicado dentro de la ficha de otro expediente | **17** |
| Licitación por lotes de la que solo se conocen algunos lotes | **14** |
| Documentos escaneados que no se han podido leer | **8** |
| Otro | **4** |
| El acuerdo marco del que depende tampoco publica precios | **3** |
| Sus documentos son de expedientes hermanos y ninguno es el suyo | **3** |
| El acuerdo marco está publicado pero no publica precios unitarios | **2** |
| Pendiente de procesar | **0** |
| **Total** | **534** |

Sin un solo cambio respecto a la tercera parte: ninguno de los dos arreglos
mueve a ningún expediente de situación.

**Filas totales de "Materiales": 19.865.** Líneas en la base de datos: 39.646
en 612 expedientes.

---

## Lo que sigue pendiente de decisión del cliente

De las cinco de la tercera parte, quedan las tres que el cliente ha dicho
expresamente que se queden como están, ya no como pendientes sino como
decididas:

1. Los 416 ceros de cantidad **se quedan**: es lo que imprime el documento.
2. `p-3` frente a `P-3` **no se unifica**: los 4 duplicados se quedan, y con
   ellos los 2 precios que la unificación habría vaciado.
3. "elemento" **no entra como alias**: `3.17/28510.0028` se queda sin sus dos
   tablas de precios.

Y siguen en pie las de las partes anteriores: los **once expedientes cuyo
título declara un lote que no está entre los suyos**
(`docs/preguntas-cliente-lotes-del-titulo-y-ficheros-de-entrada.md`), la
errata **CONTRAGUJA / CONTRAAGUJA**
(`docs/pregunta-cliente-contraguja-contraaguja.md`), las **946 huérfanas** de
las causas C y D, **`6.26/28510.0064` lote 3 `P-2`** (la única línea del
catálogo sin precio), si **"Comentarios"** va fila a fila o con la nota única
del Resumen, y si **`Precio unitario`** es el licitado o el adjudicado.

Y el pendiente que no depende de nosotros: **el fichero de los 83 vigentes con
remanente** (`EXPEDIENTES_VIGENTES_CON_REMANENTE.xlsx`), que sigue sin llegar.
Reconfirmado en la tercera parte que no está en el repositorio ni en su
historial de git, ni escondido en ninguno de los cinco ficheros de entrada.
