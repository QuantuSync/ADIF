# Sesión 2026-09-19 (sexta parte) — Las seis decisiones del cliente, las tres entradas que esperamos, el mantenimiento sin nadie delante y el diccionario del Excel

Continúa `docs/sesion-2026-09-19-residuales-cobertura-de-lotes-y-conciliacion-en-la-web.md`.
Siete bloques.

Regla de la sesión, cumplida: commit y push a main al terminar cada bloque, con
las pruebas en verde; verificación por reproceso de los expedientes afectados,
y **un solo reproceso completo, en el cierre**.

---

## Bloque 1 — Las seis decisiones pendientes

### 1.1 — `3.18/28510.0082`: el IMPORTE que no es precio unitario

**El hecho.** El `ANEJO_1.pdf` de ese expediente imprime su cuadro de precios
**dos veces**, en la p.7 y en la p.238, con la cabecera
`MATRICULA | DESIGNACIÓN | U | IMPORTE` (y `IMPORTE **`, con la llamada a una
nota al pie, en la copia de la p.7). Ese cuadro **no publica precio unitario**:
su única columna de dinero es el importe del renglón. El mapeo, que necesita un
`precio_unitario` para que la tabla llegue a ser cuadro de precios, se lo daba a
la única columna de euros que había — y publicaba **49.604,00 € como precio de
un aire acondicionado**, cuando son dieciséis.

**Lo que se ha hecho, que es exactamente lo que pidió el cliente**: aplicar la
regla ya aprobada de precio desde importe, con la columna en su sitio.

1. `corregir_columna_importe_tomada_por_precio` mueve la columna a `importe` y
   deja la tabla **sin precio**. La detección es por **coincidencia exacta** del
   nombre, con el mismo vocabulario cerrado que ya usaba
   `completar_columna_importe` — "IMPORTE UNITARIO" sigue deliberadamente
   fuera, porque eso sí es un precio. Se le ha añadido una sola tolerancia: la
   llamada a nota al pie (`IMPORTE **` → `importe`), porque el asterisco no es
   parte del nombre de la columna y la misma tabla aparece con y sin él.
2. `liberar_unidad_que_son_solo_cifras`, **solo en esa misma cabecera ya
   demostrada mal mapeada**: la columna "U" que el mapeo dio a `unidad_medida`
   y cuyos valores son todos cifras peladas (16, 11, 15, 7, 75, 1) no es una
   columna de unidades — el sistema ya los descartaba uno a uno con el motivo
   "unidad de medida descartada por ser solo numérica". Se libera, y pasa a
   `cantidad` si no había otra columna para ella (que es el caso de la copia de
   la p.7).
3. A partir de ahí manda la regla de siempre, con **dos diferencias medidas**:
   - **La comprobación es por cuadro, no por lote entero.** Sumar las dos
     copias del mismo cuadro daría 791.630,00 € y tiraría un cuadro que cuadra
     al céntimo. Cada copia se comprueba sola y las dos escriben lo mismo, que
     es lo que después funde `guardar_lineas_catalogo` por clave.
   - **El total contra el que se comprueba puede ser el presupuesto de
     licitación publicado del lote**, porque un cuadro así no declara pie de
     totales. Es la misma prueba que ya exigía el cliente para el reparto por
     lotes.
4. **Todo o nada dentro del cuadro**: si a una sola fila le falta la cantidad o
   su división no es exacta, la suma ya no es la del cuadro y no hay nada
   demostrado.

**El resultado, al céntimo.** Las ocho filas dividen exactas y suman
**395.815,00 €**, que es exactamente el presupuesto de licitación publicado de
su lote 1:

| Matrícula | Cantidad | Importe del documento | Precio unitario demostrado |
|---|---:|---:|---:|
| 650000030 | 16 | 49.604,00 € | **3.100,25 €** |
| 650000031 | 11 | 36.770,25 € | **3.342,75 €** |
| 650000032 | 15 | 57.472,50 € | **3.831,50 €** |
| 650000033 | 7 | 29.900,50 € | **4.271,50 €** |
| 650000034 | 15 | 93.153,75 € | **6.210,25 €** |
| 650000035 | 11 | 84.262,75 € | **7.660,25 €** |
| (Instalación y puesta en marcha) | 75 | 27.918,75 € | **372,25 €** |
| (Materiales necesarios para la instalación) | 1 | 16.732,50 € | **16.732,50 €** |
| | | **395.815,00 €** | **= presupuesto del lote 1** |

**Y si no se confirma, las filas se quedan fuera**, que es la otra mitad de lo
que pidió el cliente: `MOTIVO_IMPORTE_SIN_PRECIO_NI_CONFIRMACION` es un
marcador de **exclusión del entregable**, como `MOTIVO_MAPEO_INCOHERENTE`, no
un aviso más. La fila se conserva en base de datos con su traza, pero no sale
al Excel: lo único que podría escribir en su columna de precio sería el importe
de un renglón entero haciéndose pasar por el precio de una unidad.

**Dos defectos reales encontrados al verificar, los dos corregidos:**

- **La recuperación de la descripción exigía un precio ya resuelto**, y un
  cuadro sin columna de precio no la puede cumplir nunca. Las dos filas sin
  matrícula de `3.18/28510.0082` se quedaban sin descripción, y sin descripción
  no llegan a ser línea: el expediente pasaba de 8 filas a 6. El importe del
  renglón es exactamente la misma evidencia que se le pide al precio —que la
  fila trae una cifra de dinero propia y no es relleno—, así que vale, **y solo
  cuando no hay columna de precio**.
- **El orden importaba.** `descartar_bloques_de_lote_que_no_cuadran` juzga un
  bloque de lote por la suma de cantidad × precio unitario de su lote, y corría
  **antes** de que estas líneas tuvieran precio: su suma de cero descartaba el
  bloque entero. Medido en `3.21/28510.0098`, que perdía la línea de su lote 3.
  Resuelto sacando `resolver_cuadros_sin_precio_propio` a su propia llamada,
  antes de esa guarda; el resto de la regla de siempre no se toca.

**Alcance medido antes de aplicarlo.** De las **497 cabeceras cacheadas** del
corpus, **3** tienen el `precio_unitario` sobre una columna nombrada IMPORTE o
TOTAL. Los expedientes que las usan se localizaron por el texto cacheado de sus
documentos y se reprocesaron uno a uno: `3.18/28510.0082`, `3.21/28510.0098`,
`3.25/28510.0241`, `3.24/28510.0132`, `3.25/28510.0012`, `4.19/28510.0212`,
`3.19/28510.0183`, `3.19/28510.0178` y `28510/2023`.

**Efecto colateral, y es bueno.** `3.21/28510.0098` pasa de 4 líneas a 5. Su
cuadro "Concepto | Unidades | Importe" es el caso que la quinta parte de esta
sesión tuvo que **descartar** porque 3 × 210.000,00 € daba el triple del
presupuesto de su lote. Ahora la división lo resuelve: 210.000,00 / 3 =
**70.000,00 €**, y 3 × 70.000,00 = 210.000,00 = el presupuesto del lote 1. Sus
tres líneas huérfanas de un "LOTE 2" que el expediente no declara se quedan sin
precio y fuera del entregable, con su motivo — nunca estuvieron dentro, porque
no tienen lote.

### 1.2 — `6.17/28510.0116`: las matrículas con letra final

**El hecho.** Sus tres matrículas llevan una letra al final (`69520000N`,
`69520015N`, `69520020N`). No son matrículas válidas, y la celda ya salía vacía
con su motivo. Lo que faltaba era lo que pidió el cliente: **que el literal no
se pierda**.

**Lo que se ha hecho.** El literal se conserva al final de la Descripción del
material, marcado como lo que es:

```
CELDA DE LÍNEA, corte y aislamiento íntegro en SF6, interruptor rotativo III
con conexión-seccionamiento-puesta a tierra. [...] [matrícula impresa en el
documento, no válida: 69520000N]
```

**Por qué en la descripción y no en el motivo de revisión**: el motivo de
revisión no es ninguna de las 18 columnas del Excel, y en almacenes buscan por
la descripción. Sin esto, el literal no llega al entregable por ningún camino.

**Por qué solo para esa forma exacta** (8 o 9 cifras y **una sola** letra): un
literal sin forma de matrícula es ruido de otra columna leído en la celda
equivocada, y ensuciaría la descripción sin aportar nada. Medido sobre las 235
líneas del corpus con matrícula descartada: **33 cumplen esa forma**, en 4
expedientes — `6.17/28510.0116` (3), `6.19/28510.0115` (10),
`6.19/28510.0161` (10) y `6.19/28510.0163` (10). Las otras 202 traen cosas
como `18.309`, `ET03.364.203.4` o `NODISPONE`, y no se tocan.

**La línea no pierde nada más**: conserva su precio, y la celda de matrícula
sigue vacía con su motivo, que es exactamente lo que dijo el cliente.

### 1.3 — La numeración de lotes desplazada: no se toca

`3.22/28510.0009` y `3.21/28510.0096`. **No se ha tocado una sola línea de
código por esto**, que es lo que dijo el cliente. La pregunta, con sus cifras y
la explicación de por qué el sistema no puede decidirlo sin inventar, está en
`docs/preguntas-pendientes-cliente.md`, pregunta 3.

### 1.4 — Las dos filas sueltas

**La fila `12.01` de `3.16/28510.0044`: entra.** Su tabla, leída con
reconocimiento óptico, es:

```
["12",    "Seguridad y Salud", "",  "",         ""]
["12.01", "",                  "1", "1.980,50", "1.980,50 €"]
["",      "",                  "",  "TOTAL",    "824.323,67 €"]
```

La aritmética del documento **la demuestra dos veces**: su propia fila cuadra
(1 × 1.980,50 = 1.980,50) y es **la que cierra el TOTAL declarado** — las 14
líneas que ya entraban suman 822.343,17 € y con ella suman 824.323,67 €, el
presupuesto de licitación que el propio pliego escribe en letra.

Lo único que le faltaba era la descripción, y el documento **sí la imprime**:
es el rótulo de su sección, en la fila inmediatamente anterior, cuyo número
(`12`) es **prefijo estricto** del suyo (`12.01`). No se inventa ningún texto
ni se busca parecido: la prueba es la numeración del propio cuadro.
`_hereda_de_la_fila_de_seccion`, con cuatro guardas: la fila de sección no trae
ni una cifra en las columnas de la tripleta (es solo un rótulo), su número es
prefijo **con punto** del de la fila, el rótulo es la única columna de texto de
esa fila de sección, y la fila que hereda no tiene texto propio en ninguna
columna. `3.16/28510.0044` pasa de **14 a 15 líneas**.

**La cuarta fila del lote 1 de `3.21/28510.0096`: entra.** "Potenciómetro
rotatorio, componente 20299800", 10 × 150,00 = 1.500,00. Sus tres celdas
numéricas caen **una columna a la derecha** de las de las otras tres filas de su
misma tabla, así que no cuadraba en las columnas de la tripleta y la fila se
descartaba entera.

Entra solo porque la aritmética lo demuestra: el desplazamiento es **el mismo
para las tres celdas** (nunca una a una, que sería recomponer la fila a gusto),
las tres celdas de la tripleta están **vacías** —no es que traigan otra cosa— y
las tres desplazadas cumplen `cantidad × precio = importe` al céntimo. La fila
**se devuelve sin tocar**: quien lee sus valores después es la recuperación de
columna fantasma que ya existe, que solo mira la columna vecina libre y deja su
propio motivo en la línea. El fragmento de traza sigue siendo la fila tal y como
la imprime el documento.

Con ella, el lote 1 de ese expediente suma **11.500 + 4.600 + 4.600 + 1.500 =
22.200,00 €**, exactamente su presupuesto de licitación publicado.
`3.21/28510.0096` pasa de **3 a 4 líneas**.

### 1.5 — Los tres cuadros cuya única columna de texto es la referencia

**El hecho.** `2.23/28510.0098` (p.4 y p.9), `6.22/28510.0051` y
`6.22/28510.0159` (p.9) listan insertos y fresas de mecanizado con la cabecera
`TIPO | CANTIDAD | PRECIO UD. | PRECIO TOTAL`, y su columna "TIPO" es la
referencia de fabricante (`SFT01-2388L-PH-6920`, `WCMX-04 02 08-R53`,
`SNC-55 R16 T03 IN6530`). La quinta guarda de la etapa 4, añadida en la quinta
parte de esta sesión, los dejaba fuera enteros porque entraban como líneas de
catálogo **sin descripción**.

**Lo que decidió el cliente, y lo que se ha hecho.** Esa referencia se acepta
como Descripción del material, y esas líneas quedan marcadas de forma visible,
igual que las de reconocimiento óptico: `lineas_catalogo.descripcion_desde_referencia`
(migración 0040), su `motivo_revision`, y el prefijo
`[descripción tomada de la referencia del documento]` en el fragmento. Además,
el Resumen del Excel lleva su recuento y una nota que lo explica.

**Lo que NO se afloja**: la tabla sigue necesitando una columna de texto fuera
de la tripleta —una de puras cifras sigue sin entrar— y cada fila sigue
necesitando letras en ella para llegar a ser línea.

**Cuántas líneas entran: 35.**

| Expediente | Líneas |
|---|---:|
| `2.23/28510.0098` | **15** |
| `6.22/28510.0051` | **10** |
| `6.22/28510.0159` | **10** |

**Y por qué 35 y no las 45 que la quinta parte contó.** Los cuadros de
`6.22/28510.0051` y `0159` tienen 20 renglones cada uno, pero **la mitad escribe
su precio con punto decimal a la inglesa** (`12.5`, `8.5`, `14.5`, `16.5`). En
formato español eso es 125, y 140 × 125 no da 1.750: **la guarda aritmética las
descarta**. Es el comportamiento correcto y deliberado — ninguna entra con un
precio inventado —, y queda anotado por si el cliente quiere decidir algo sobre
esos renglones. Las 35 que entran cuadran todas contra el importe de su propia
fila.

---

## Bloque 2 — Las tres entradas que esperamos del cliente

Montadas, probadas sobre datos sintéticos (**17 pruebas**,
`engine/tests/test_entradas_pendientes_del_cliente.py`) y documentadas en
`docs/entradas-pendientes-del-cliente.md`, que dice para cada una **qué forma
espera el sistema, qué hace si llega con otra, y el comando exacto**.

Las tres siguen el mecanismo de las cinco fuentes de entrada que ya existen: una
variable de entorno con la ruta dentro del contenedor, montada por bind-mount, y
un endpoint repetible. **Sin la variable, devuelven `configurado: false` y no
tocan nada.**

### 2.1 — `EXPEDIENTES_VIGENTES_CON_REMANENTE.xlsx`

`app.extraccion.vigentes_remanente`,
`POST /mantenimiento/vigentes-remanente/cruzar`.

**Lectura tolerante, en tres escalones**: por encabezado que contenga
"expediente" o "contrato"; si no, por la **forma** de los códigos (la única
columna con al menos el 60 % de valores con forma de código de ADIF, en las dos
escrituras del corpus); si tampoco, `formato_reconocido: false` y **no se toca
nada**. Nunca se mezclan dos hojas.

**El cruce da lo que pidió el cliente**: para cada uno, su **Situación en la
Conciliación** —la misma lista que escribe el Excel, construida con el mismo
recuento de filas de "Materiales", nunca una consulta propia— y, para los que no
estén, **la búsqueda en la Plataforma**, que es un `descargar_expediente` de la
cola de siempre.

**Este módulo sí da de alta el expediente que no exista**, a diferencia de
`estados_adif`, y está razonado: allí el alta falsearía la pregunta "¿cuáles de
los suyos nos faltan?"; aquí la pregunta es la contraria y no se puede contestar
sin buscarlos. Con `?buscar=false` informa sin tocar la red ni dar de alta nada.

### 2.2 — El listado de estados de ADIF con presupuesto de licitación

Sin ruta nueva: es el **mismo fichero** que ya cargamos, con una columna más. Se
sustituye y se vuelve a llamar a `POST /mantenimiento/estados-adif/cargar`.

La columna se reconoce por **contenido** del encabezado (`presupuesto`,
`importe de licitacion`, `pbl`), con `adjudicacion`, `adjudicado` e `iva`
deliberadamente **fuera**: un importe adjudicado no es el presupuesto de
licitación, y contrastarlos daría diferencias en casi todas las filas. Con dos o
más candidatas no se adivina. **El fichero de hoy no la trae**, y eso está
probado explícitamente con sus cuatro columnas reales.

El valor va a `expedientes.presupuesto_licitacion_adif` (migración 0041) y
**nunca escribe en `importe_licitacion`**, que sale de los documentos
publicados. La comparación es la hoja **"Presupuestos ADIF"**: coincidencias,
diferencias **de mayor a menor** (por valor absoluto) y expedientes sin importe,
con un orden estable dentro de cada bloque para que dos exportaciones seguidas
den el mismo fichero. **La hoja no se escribe si no hay nada que comparar.**

### 2.3 — El catálogo antiguo de ADIF

`app.catalogo_antiguo`, `GET /mantenimiento/catalogo-antiguo/informe.xlsx` y
`/resumen`.

**Formato desconocido quiere decir lectura por contenido**: se miran las diez
primeras filas de cada hoja —el encabezado puede no ser la primera— y se elige
la que resuelva **más** columnas de las tres (matrícula, descripción, precio).
Eso es lo que impide que un título de portada como "CATÁLOGO DE MATERIALES
ADIF" se lleve el puesto por contener la palabra "material". Una columna
"Importe total del pedido" no pasa por precio unitario.

**El emparejamiento es el que pidió el cliente**: por matrícula exacta primero;
**solo cuando no la hay**, por descripción normalizada. **Nunca al revés**: una
matrícula que no casa no se reintenta por descripción, que sería el cruce por
parecido de nombre que CONTEXTO.md sección 7 prohíbe.

**Contra qué se compara**: contra los materiales del entregable, con los mismos
filtros y el mismo criterio de inclusión que la hoja "Materiales".

**El informe va aparte**, que era la condición explícita: su propio `.xlsx` con
cuatro hojas (solo en el suyo / solo en el nuestro / diferencias de precio /
resumen), nunca una hoja del Excel del catálogo.

---

## Bloque 3 — El mantenimiento sin nadie delante

Todo en `docs/mantenimiento-sin-supervision.md`, medido contra el stack real.
Resumen:

- **Cuatro ciclos automáticos**, todos dentro del bucle del worker que ya
  existe: mantenimiento (7 días), copia de seguridad (24 h), descubrimiento
  inverso de pedidos (7 días) y auditoría (sin programación propia: al final de
  cada ciclo de mantenimiento). Más la vigilancia de huérfanos, en cada vuelta.
- **La caducidad de `sin_publicar` funciona como se diseñó**: 3 días para el año
  en curso y el anterior, 14 para lo demás, y el plazo largo para lo que no se
  sabe leer. **Dos pruebas nuevas** lo demuestran **dentro del ciclo**, que es
  quien decide — hasta ahora solo estaba probada la función pura.
- **La copia de seguridad se hace sola** (programadas los días 15, 16, 17 y 18),
  se guarda en un volumen propio distinto del de PostgreSQL y conserva 14.
  **Restauración probada de verdad** en una base aparte: ocho recuentos
  idénticos y los `md5` de expedientes y de líneas **idénticos byte a byte**.
- **Un ciclo muerto a mitad con SIGKILL**: lo `pendiente` lo recoge el bucle
  normal del worker en cuanto vuelve —sin esperar al ciclo siguiente— y lo
  `en_proceso` se reclama solo a los 300 s. El segundo intento del ciclo saltó
  **516 de 519** y tardó **9,7 s** en vez de reextraer lo ya hecho.

**No se ha encontrado nada roto en los cuatro puntos.** Lo único que faltaba era
cobertura de prueba, y se ha añadido. Tres límites conocidos quedan anotados en
el documento: la programación no compite consigo misma con un solo worker, un
ciclo huérfano tres veces acaba `fallido` hasta el siguiente programado, y las
copias manuales cuentan para la retención de 14.

---

## Bloque 4 — Un único documento de preguntas

`docs/preguntas-pendientes-cliente.md`: **once preguntas**, cada una con su
contexto, los expedientes y filas afectados y qué haremos según lo que
contesten. Incluye las siete que pedía el encargo y cuatro más que seguían
abiertas de partes anteriores (las 946 huérfanas de las causas C y D,
`6.26/28510.0064` lote 3 `P-2`, "Comentarios" fila a fila o nota única, y si
`Precio unitario` es el licitado o el adjudicado).

**No hay ningún mensaje redactado para el cliente**, que era la condición: solo
el documento con la información medida.

---

## Bloque 5 — Diccionario del Excel

`docs/diccionario-excel.md`, para quien no sabe nada del sistema: qué contiene
cada hoja, qué es cada una de las 18 columnas de "Materiales" y las 11 de
"Conciliación", de dónde sale cada dato, **cuándo puede quedar vacío y con qué
motivo**, qué significan los tres motivos de celda vacía (no aplica / no consta
/ pendiente) y las once Situaciones de la Conciliación. Con las dos marcas
nuevas que el Resumen cuenta y una sección de preguntas frecuentes.

---

## Bloque 6 — Las cifras del sistema

Medidas el 2026-09-19 al cerrar la sesión, después del reproceso completo. **Lo
que no se puede medir con certeza va dicho, no estimado.**

### El corpus

| Cifra | Valor |
|---|---:|
| Expedientes en el corpus | **612** |
| — en revisión / sin publicar / completados | 454 / 93 / 65 |
| Expedientes publicados según la Conciliación | **534** |
| Expedientes que aportan líneas al entregable | **390** |
| Expedientes con alguna línea en base de datos | 394 |
| Documentos descargados | **1.638** (1.637 de la Plataforma, 1 aportado a mano) |
| Páginas de esos documentos | **54.871** |
| Documentos con su texto en caché | 1.642 (54.883 páginas) |

> Los 1.642 documentos con texto cacheado son cuatro más que los 1.638
> descargados: la caché es por hash de contenido y conserva la lectura de
> documentos que después se retiraron o se sustituyeron. No es un descuadre.

### El catálogo

| Cifra | Valor |
|---|---:|
| Filas de la hoja "Materiales" | **20.035** |
| Líneas en base de datos | **40.016** |
| Líneas sin lote (no salen al entregable) | 19.758 |
| Lotes registrados | 695 |
| Pares expediente+lote presentes en el entregable | 540 |
| Filas con matrícula | 13.484 (67,3 %) |
| Filas con Código del material | 18.397 (91,8 %) |
| Filas con precio adjudicado | 9.205 |
| Trazas de origen | 2.108 |

**Materiales distintos**, según con qué clave se cuenten:

| Clave | Materiales |
|---|---:|
| Por matrícula | **5.306** |
| Por descripción normalizada | **8.547** |
| Por matrícula y precio | 6.441 |
| Por lote, matrícula y precio | 7.334 |

> **No hay una sola cifra de "materiales distintos", y no se debe dar como si
> la hubiera.** La matrícula falta en un tercio de las filas, así que contar
> solo por ella deja fuera todo lo que no la trae; contar por descripción
> cuenta dos veces el mismo material escrito de dos formas. Las cuatro cifras
> son correctas y miden cosas distintas.

### El código

| Cifra | Valor |
|---|---:|
| Líneas de código (Python, TypeScript, CSS) | **56.100** |
| — motor (`engine/app`) | 27.685 |
| — pruebas (`engine/tests`) | 21.031 |
| — migraciones | 1.937 |
| — web (`web/app`) | 5.442 |
| Ficheros en el repositorio | **355** (210 `.py`, 61 `.md`, 51 `.pdf` de prueba, 18 `.ts`/`.tsx`) |
| Pruebas | **1.304**, todas en verde, ninguna saltada |
| Migraciones | **41** |
| Tablas en la base de datos | **16** de dominio, más `alembic_version` y una tabla temporal de una sesión anterior (`tmp_snap_antes_ocr`) |
| Endpoints de la API | **49** |
| Documentos en `docs/` | 59 |

### El modelo

| Cifra | Valor |
|---|---:|
| Formatos de cabecera aprendidos | **497** |
| — resueltos **sin modelo** (vocabulario determinista) | **177 (35,6 %)** |
| — resueltos con una llamada al modelo | 320 |
| Términos de Código del material en caché | 867 |
| Documentos leídos por reconocimiento óptico | **140** (1.657 páginas) |
| — páginas releídas con un modelo mejor (`claude-opus-5`) | 4 |
| Tokens del reconocimiento óptico | 3.567.523 de entrada, 1.209.845 de salida |

**El coste acumulado del modelo NO está registrado por el sistema.** Se guardan
los tokens de cada página leída, pero no el precio: no hay ninguna tabla ni
campo de coste, y calcularlo aquí sería aplicar una tarifa de memoria a cifras
que el sistema no valida. Lo que sí está escrito, sumado de los registros del
worker en su momento, es **~10,75 $** del lanzamiento del reconocimiento óptico
sobre el corpus (sesión 2026-09-17) y **0,17 $** de la relectura de
`3.16/28510.0044` con `claude-opus-5` (quinta parte de esta sesión). El coste de
las llamadas de cabecera nunca se midió aparte.

### El reproceso

| Cifra | Valor |
|---|---:|
| Tiempo de un reproceso completo, con la red apagada | **21 min 45 s** (1.305,2 s) |
| Expedientes reextraídos | 517 de 519 evaluados |
| Descargas lanzadas | **0** |
| Tiempo de una exportación del Excel | **3 min 13 s** |

---

## Bloque 7 — Cierre

### Pruebas

**1.304 pasan** (1.259 al cerrar la quinta parte, **+45**). Ninguna saltada.
Las nuevas: `engine/tests/test_decisiones_2026_09_19_sexta.py` (24),
`engine/tests/test_entradas_pendientes_del_cliente.py` (17) y dos en
`engine/tests/mantenimiento/test_ciclo.py`. Más dos reescritas en
`test_decisiones_2026_09_19_quinta.py` —las que codificaban justo las
decisiones que el cliente ha cambiado ahora—, con la guarda que **no** se
afloja conservada en una prueba propia.

### El reproceso completo, con la red apagada

`POST /mantenimiento/ejecutar` con `forzar: true`, `sindicacion_desactivada:
true` y `busqueda_desactivada: true`. **Uno solo, en el cierre**, como pedía la
regla de la sesión.

| | |
|---|---|
| Expedientes reextraídos | **517** (519 evaluados) |
| Tiempo | **21 min 45 s** (1.305,2 s) |
| `descargas_lanzadas` | **0** |
| `saltados_descarga` | 519 |
| `sin_publicar_reintentados` | 0 (`sin_publicar_desactivado: true`) |
| `descubrimiento` / `descubrimiento_busqueda` | `None` / `None` |

### Dos exportaciones seguidas

Descargadas una detrás de otra y comparadas **entrada por entrada del `.zip`**
(un `.xlsx` es un zip de XML), con el `sha256` de cada una:

```
mismas entradas: True
entradas con contenido distinto: ['docProps/core.xml']
  A: <dcterms:created>2026-09-19T20:27:18Z</dcterms:created>
  B: <dcterms:created>2026-09-19T20:30:31Z</dcterms:created>
```

**Idénticas salvo la fecha de creación del fichero**, que es exactamente lo que
pedía el encargo. Mismo tamaño al byte (1.955.388).

### El Excel

```
C:\dev\ADIF\catalogo_adif_2026-09-19-decisiones-y-entradas.xlsx
```

### Comparación con `catalogo_adif_2026-09-19-residuales-y-conciliacion.xlsx`

| | Antes | Ahora | |
|---|---:|---:|---|
| Filas de "Materiales" | 19.997 | **20.035** | **+38** |
| Columnas | 18 | **18** | = (mismo orden) |
| Expedientes con filas | 387 | **390** | +3 |
| Filas de "Conciliación" | 534 | **534** | = |
| Materiales distintos por matrícula | 5.306 | **5.306** | **=** |
| Materiales distintos por matrícula y precio | 6.441 | **6.441** | **=** |
| Materiales distintos por lote, matrícula y precio | 7.334 | **7.334** | **=** |

**0 expedientes desaparecen. 0 expedientes pierden filas. Los 6 que cambian,
suben.**

| Expediente | Antes | Ahora | Por qué |
|---|---:|---:|---|
| `2.23/28510.0098` | 0 | **15** | Decisión 5: la referencia del inserto como Descripción del material |
| `6.22/28510.0051` | 0 | **10** | Decisión 5 |
| `6.22/28510.0159` | 0 | **10** | Decisión 5 |
| `3.16/28510.0044` | 14 | **15** | Decisión 4: la fila `12.01` con el rótulo de su sección |
| `3.21/28510.0096` | 3 | **4** | Decisión 4: la cuarta fila del lote 1, desplazada una columna |
| `3.21/28510.0098` | 1 | **2** | Decisión 1: su cuadro de "Concepto, Unidades e Importe" ya se puede leer |

**Las celdas que cambian de valor en filas comparables: 39, y todas
explicadas.**

| Cambio | Celdas | Explicación |
|---|---:|---|
| Descripción del material | **18** | El literal de la matrícula con letra final, añadido al final (decisión 2). En el Excel hay **33** filas con esa marca; 18 salen aquí porque las otras 15 tienen la descripción corta y la comparación las ve como fila nueva, no como fila cambiada |
| Precio unitario | **8** | Las 6 filas con matrícula de `3.18/28510.0082` (de su importe a su precio real), la fila `09.01` de `3.16/28510.0044` y la de `3.21/28510.0098` |
| Precio adjudicado | **8** | Consecuencia de lo anterior |
| Cantidad | **3** | Las dos filas sin matrícula de `3.18/28510.0082` (75 y 1, que antes salían vacías) y la de `3.16/28510.0044` |
| Motivo de las celdas vacías | **2** | Consecuencia: la celda de cantidad que se rellena deja de tener motivo |

**Los seis "materiales perdidos" que la comparación señala por matrícula y
precio son las seis filas de `3.18/28510.0082`**, y no es una pérdida: el
material sigue ahí, con **su precio real** en vez del importe del renglón. El
recuento total no baja porque entran los seis pares nuevos.

**Un cambio que no estaba previsto y hay que contar**: la fila `09.01` de
`3.16/28510.0044` pasa de `cantidad 931,03 / precio 83.792,70 €` a
`cantidad 90 / precio 931,03 €`. Es una **corrección**, no una regresión: su
tabla no tiene cabecera propia y hasta ahora traía **una sola fila de datos**,
con la que las columnas eran ambiguas; al entrar la fila `12.01` son dos, y el
mapeo las resuelve bien. La prueba está en el propio documento: 90 × 931,03 =
**83.792,70 €**, la cifra que su pliego escribe en texto para "instalación,
pruebas y puesta en servicio". Y con ella, **las 15 líneas del expediente suman
824.323,67 € exactos**, su presupuesto de licitación publicado.

### Cuadre de "Conciliación" con "Materiales"

```
suma de la columna de líneas de "Conciliación": 20.035
filas de la hoja "Materiales":                  20.035
```

**0 expedientes sin Situación.** `comprobar_cuadre` revienta la exportación si
alguna de las dos cosas falla, así que el Excel no habría salido de otro modo.

### Auditoría

**0 errores y 6 avisos**, tanto la que corre al final del propio ciclo como una
segunda lanzada a mano después.

| Aviso | Afectados | Antes |
|---|---:|---:|
| Huérfanas sin lote | 19.758 líneas en 118 expedientes | 19.758 en 118 |
| Precios atípicos | 1.544 líneas en 83 expedientes | 1.545 en 84 |
| Cantidades con forma de año | 941 líneas en 32 expedientes | igual |
| Grupos de importe de licitación compartido | 54 grupos, 24 expedientes | igual |
| Grupos de material repetido con códigos de precio distintos | 12 grupos, 4 expedientes | igual |
| Expedientes con importe repetido entre sus lotes | 8 | igual |

El único que se mueve es "precios atípicos", y a la baja: una línea menos, en
`3.18/28510.0082`, porque su precio ha dejado de ser dieciséis veces el real.

### Recuento por Situación y total de filas

| Situación | Expedientes | Antes |
|---|---:|---:|
| Aporta líneas | **390** | 387 |
| Publicado sin cuadro de precios | **54** | 57 |
| Los precios están en un acuerdo marco que no está publicado | **47** | 47 |
| Publicado dentro de la ficha de otro expediente | **17** | 17 |
| Licitación por lotes de la que solo se conocen algunos lotes | **9** | 9 |
| Documentos escaneados que no se han podido leer | **6** | 6 |
| El acuerdo marco del que depende tampoco publica precios | **3** | 3 |
| Sus documentos son de expedientes hermanos y ninguno es el suyo | **3** | 3 |
| Otro | **3** | 3 |
| El acuerdo marco está publicado pero no publica precios unitarios | **2** | 2 |
| Pendiente de procesar | **0** | 0 |
| **Total** | **534** | 534 |

**Filas totales de "Materiales": 20.035.** Líneas en base de datos: 40.016 en
612 expedientes, 394 de ellos con alguna línea. **0 líneas sin descripción** en
el entregable.

### La web

Las **seis** pantallas abiertas con Chromium de verdad (el del contenedor del
scraping, no `curl`): `/`, `/catalogo`, `/conciliacion`, `/revision`,
`/revision/candidatos-matricula` y `/mantenimiento`. Todas pintan datos reales,
**0 banners de error** y **0 errores de consola**.

Y la comprobación que pedía el encargo: **`/conciliacion` da exactamente las
mismas cifras que el Excel** — 534 expedientes, **20.035 líneas sumadas** y el
mismo recuento en las once Situaciones, una a una.

---

## Lo que queda anotado, y no se ha tocado

**Una sola cosa medida que cambia datos del catálogo y no estaba en el
encargo**, así que no se ha tocado:

1. **Los precios con punto decimal a la inglesa de `6.22/28510.0051` y
   `6.22/28510.0159`**: la mitad de los renglones de sus cuadros escribe el
   precio como `12.5`, `8.5`, `14.5` o `16.5`, que en formato español es 125,
   85, 145 y 165. La guarda aritmética los descarta —140 × 125 no da 1.750— y
   por eso entran 35 líneas y no las 45 que la quinta parte contó. **Ninguna
   entra con un precio inventado**, que es lo correcto; decidir que ahí el punto
   es un separador decimal es una decisión sobre datos del catálogo y es del
   cliente.

Y siguen en pie las once preguntas abiertas, ahora todas en un solo sitio:
`docs/preguntas-pendientes-cliente.md`.
