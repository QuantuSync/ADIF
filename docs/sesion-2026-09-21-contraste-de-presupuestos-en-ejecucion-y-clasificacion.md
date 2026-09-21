# Sesión 2026-09-21 — Contraste de presupuestos, expedientes en ejecución de ADIF y propuesta de clasificación

Tres encargos del cliente y un cierre. Continúa
`docs/sesion-2026-09-19-matriculas-contra-el-maestro-y-unidades.md` (cerrada la
mañana del 20; el encargo pedía leer `docs/sesion-2026-09-2*.md` y **no existe
ninguno**: el registro de lo hecho el 20 está en ese documento del 19).

---

## Bloque 1 — Contraste de presupuestos visible

### Qué se pidió

El cliente preguntó dónde podía ver la comprobación de la sesión 2026-09-18
(sexta parte): la suma de cantidad × precio de cada lote contra su presupuesto
de licitación publicado. Solo vivía en nuestros registros. Pasa a ser parte del
sistema: hoja **"Contraste de presupuestos"** del Excel, pantalla
**`/contraste-presupuestos`** de la web (`GET /contraste-presupuestos`) y
sección nueva de `docs/diccionario-excel.md`.

### El hallazgo que decidió el diseño: el presupuesto por lote casi nunca estaba guardado

De los **540 lotes con filas en "Materiales"**, **215 no tenían presupuesto de
lote** en el sistema. Entre ellos estaban los cinco lotes 3 de
`6.20/28510.0054`-`0058`, justo los de la discrepancia del propio documento que
se comprobó a mano. `Lote.importe_licitacion` solo se rellena cuando lo declara
la adjudicación o el Contrato **del propio lote**.

La cifra sí está en los documentos ya descargados. El lote 3 la publica tres
veces: en el anuncio de la Plataforma (`PLIEGO_1.pdf` p.4: "Lote 3: Área
Territorial Norte. Presupuesto base de licitación Importe 9.922.000 EUR. Importe
(sin impuestos) 8.200.000 EUR"), en la lista del `ANEJO_1.pdf` p.4 ("Lote 3:
Área Territorial Norte, 8.200.000,00 € sin IVA") y en la p.103 de cada Contrato.
Medido sobre el texto ya leído, **179 de los 215** tienen su presupuesto
publicado en alguna de tres redacciones.

**Decisión: tabla aparte, nunca `Lote.importe_licitacion`.** Ese campo
interviene en la baja, en la prueba aritmética del reparto por lotes y en los
precios que un presupuesto demuestra. Rellenarlo cambiaría datos del catálogo,
y eso no entraba en el encargo. `app.extraccion.presupuesto_lote` guarda cada
aparición en `presupuestos_lote_documento` (migración **0042**), con documento,
página y fragmento, y solo la lee el contraste. Se reescribe entera al final de
la extracción de cada expediente, así que es un paso nuevo de la extracción y
obliga a **un reproceso completo en el cierre**.

**La trampa que había que esquivar.** En un expediente sin lotes declarados, el
"1" lo pone el sistema (`LOTE_UNICO`) y **no es el "Lote 1" de la licitación**.
Leerle el presupuesto del "Lote 1" de un documento compartido le daba el de
otro expediente. En la medición salieron 6 cifras así, distintas de la
guardada, y 3 conflictos. Para ese lote solo vale el presupuesto del expediente
entero. Además, una mención de lote solo se liga a una cifra si no se cruza otra
mención de lote en medio: si no, el total de la licitación se atribuía al último
lote enumerado.

Verificado **reprocesando solo tres expedientes afectados** (`6.20/28510.0054`,
`6.17/28510.0056` con documentos de reconocimiento óptico y `6.25/28510.0019`).
La extracción deja exactamente las mismas **59 apariciones** que el relleno de
prueba desde el texto ya leído.

### Contra qué cifra se compara, y cómo se sabe qué cifra es

**El tipo de cifra lo dice la etiqueta con la que se publica, nunca que la
cuenta salga**:

| Dónde se publica | Etiqueta | Qué cifra es |
|---|---|---|
| Anuncio de la Plataforma | "Importe X EUR. Importe (sin impuestos) Y EUR" | Las dos: con y sin IVA |
| Contrato | "(IVA excluido)" | Base sin IVA |
| Lista de lotes del pliego | "X € sin IVA" | Base sin IVA |
| Propuesta LC.27 | "Presupuesto de licitación: X € Y € Z €" bajo *Base imponible / IVA / Total con IVA* | La primera es la base sin IVA |
| Sindicación de la Plataforma | campos "sin impuestos" y "con impuestos" | Las dos |

Lo de la LC.27 **se comprobó en las 95 del corpus**, no se supuso. En 93 la base
más el IVA da el total al céntimo; en las otras 2 es la misma tabla con un "€" o
un dígito partido en el texto (240.000 + 50.400 = 290.400; 2.400.000 + 504.000
= 2.904.000). Si una etiqueta no es ninguna de estas, la fila empieza por *"No
se puede saber con certeza"* y dice por qué. Hoy no queda ninguna así. Había 8
cifras guardadas sin traza (`6.25/28510.0027`, `0099`, `0101`, `0141`, `0185`,
`0187`, `0218`), y el anuncio publica cada una con su etiqueta: se enlazan por
la misma cifra, nunca por otra.

**La cifra equivalente.** Los precios de un cuadro son sin IVA, así que se
compara con la base sin IVA. La excepción es el caso que ya vimos, y la
demuestra la aritmética: si la suma × 1,15 da la base **a un céntimo**, el
cuadro está a precios de ejecución material. Se compara entonces con la
ejecución material que **declara el propio documento** (redacción nueva,
"Presupuesto de Ejecución Material X €", sin lote), y si ninguno la declara, con
la base ÷ 1,15.

El céntimo de margen no es una tolerancia inventada, y se descubrió al probarlo.
En `6.17/28510.0056` lote 1, 2.975.673,96 × 1,15 = 3.422.025,054, que redondea
a ,05, y la Plataforma publica ,06. El documento redondea por separado los
gastos generales (9 %: 267.810,66) y el beneficio industrial (6 %: 178.540,44),
y así sí da 3.422.025,06. Con la regla "exacto al céntimo", el caso que motivó
el encargo no habría cuadrado. Salen así **5 lotes**: `6.17/28510.0056` lote 1,
contra su ejecución material declarada, y `3.17/28510.0124`, `3.25/28510.0164`,
`3.26/28510.0013` y `6.17/28510.0007`, contra la base ÷ 1,15.

**Una partida alzada sin cantidad cuenta una vez por su importe.** Es cantidad
1 por definición (CONTEXTO.md sección 2) y así se contó en la verificación del
18/09 (las poleas de `6.25/28510.0097`). La explicación de la fila lo dice.

### El recuento

**485 lotes contrastados y 55 que no entran** (540, los lotes con filas en
"Materiales"):

| Resultado | Lotes |
|---|---:|
| Cuadra al céntimo | **233** |
| Cuadra con diferencia menor del 0,01 % | **13** |
| No cuadra | **139** |
| No se puede cerrar: faltan cantidades | **100** |

| Por qué no entra | Lotes |
|---|---:|
| Ningún documento ni la sindicación publican presupuesto para ese lote | 40 |
| Sus líneas son el cuadro heredado del acuerdo marco (se contrasta en la fila del acuerdo marco) | 14 |
| Expediente de varios lotes que solo publica el total (`6.20/28510.0096` lote 2) | 1 |
| Sus documentos publican cifras distintas para el lote | 0 |

Los 40 sin presupuesto son casi todos lotes únicos cuyo expediente no tiene
importe leído de ningún documento ni de la sindicación: la familia
`6.19/28510.0029`-`0055` (11), `6.21/28510.0108`-`0111` (4, 214 filas cada
uno)… No se ha investigado caso a caso por qué. La lista completa sale en la
API (`lotes_fuera`).

**Los cinco casos comprobados a mano llevan lo que se comprobó.** Son el lote 3
de `6.20/28510.0054`-`0058`: 8.230.002,13 € contra 8.200.000,00 €. La
discrepancia es del ANEJO_8, cuya partida alzada sigue siendo el 3 % exacto.
También llevan su texto el lote 4 de esa misma familia (+1,60 €, menos del
0,01 %), el lote 1 de `6.22/28510.0094` (−98,89 €, el precio de P-002 que
publica distinto el anejo de criterios) y el lote 1 de `6.17/28510.0056`. **El
texto solo se escribe si la suma y la cifra de hoy son las que se comprobaron**:
si cambian, explicaría otra cosa.

**Lo que dicen los "no cuadra"**, sin tocar nada:

- Cuadros que suman muy por debajo de su presupuesto: la familia
  `6.19/28510.0115`-`0167` suma entre el 0,1 % y el 9 %. No se ha comprobado
  contra el documento por qué.
- Relaciones exactas que la columna Explicación señala: `6.23/28510.0051`
  suma **exactamente el 90 %** de sus 2.400.000 € por lote, y
  `6.21/28510.0058`/`0135`-`0138` lote 3 el **105 %**.
- `6.21/28510.0058`/`0135`-`0138` **lote 7**: 1.353.000 € contra 143.000 €, 9,46
  veces. Es la familia de "el título declara un lote que no está entre los
  suyos", ya preguntada a ADIF.
- **Tres sumas absurdas que delatan una lectura mala del catálogo**:
  `6.25/28510.0019` y `6.25/28510.0041` lote 3 suman **13.457.044.000 €**
  (11.600 veces su presupuesto de 1.160.000 €), y `6.24/28510.0188`
  **507.926.862,96 €** (2.113 veces sus 240.345,60 €). Lo mismo ocurre, sin
  presupuesto con el que compararlo, en `6.20/28510.0042`/`0046`/`0047` lote 1:
  **863.821.702.015,56 €**. **No se ha tocado ninguna**: cambiaría datos del
  catálogo y no entraba en el encargo. Quedan anotadas para decidir.

### Qué se añadió

- `app/extraccion/presupuesto_lote.py`: el lector (cuatro redacciones) y
  `registrar_presupuestos_de_lote`, llamado al final de
  `ejecutar_extraccion_expediente`.
- `app/contraste_presupuestos.py`: el contraste. Suma exactamente las filas de
  "Materiales": el Excel le pasa las que acaba de escribir, y la web usa la misma
  consulta y el mismo criterio (`lineas_de_materiales_por_lote`).
- La hoja en `app/exportacion.py`, detrás de "Conciliación", con el recuento
  por resultado y por motivo de exclusión debajo de la tabla.
- `app/routers/contraste_presupuestos.py` y la pantalla
  `web/app/contraste-presupuestos/`, con el mismo diseño que Conciliación:
  filtro por resultado con su recuento (siempre el del total), búsqueda por
  expediente y los lotes que no entran, con su motivo.
- 17 pruebas en `tests/test_contraste_presupuestos.py`.
