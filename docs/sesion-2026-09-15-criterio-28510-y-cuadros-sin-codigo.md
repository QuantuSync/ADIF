# Sesión 2026-09-15 (tercera parte) — criterio 28510 sin órgano, y cuadros de precios sin código

Encargo: (1) quitar el requisito de órgano del descubrimiento (el cliente fija
como único criterio que el código contenga 28510, en cualquier estado, sin
excluir por órgano ni por área) y medir cuántos expedientes nuevos entran;
(2) de los 22 recuperados en la segunda parte de
`sesion-2026-09-15-expedientes-2026-presidencia.md`, los 8 que entraron con 0
líneas: ¿límite de origen o fallo de extracción?; (3) cierre: auditoría, Excel
y comparación con el estado anterior.

## 1. Criterio de descubrimiento

Antes (`app/sindicacion/descubrimiento.py`): una entrada de la sindicación
entraba si (a) el órgano de contratación contenía "adif" y (b) el código tenía
la forma exacta `N.AA/DDDDD.` con `DDDDD` en `SINDICACION_DEPARTAMENTOS_ADIF`.
El encargo nombraba solo (a), pero (b) también deja fuera un código con 28510
escrito de otra manera ("6.24-28510-0088"), así que cae con el mismo criterio.

Ahora (`_cumple_criterio`): entra toda entrada cuyo código contenga los
dígitos de un departamento configurado, en cualquier posición y con cualquier
separador, sin mirar el órgano. Única condición añadida: los dígitos no pueden
ir pegados a otros dígitos ("28510" dentro de "1285107" es otro número, no el
departamento). El órgano con "adif" se sigue contando
(`expedientes_adif_total`), solo como dato informativo.

Cada entrada que el filtro anterior habría descartado queda anotada, con el
motivo, en `codigos_criterio_ampliado` del resumen del periodo (y del
backfill) y en el log del worker.

### Medición: sin terminar al cerrar

Medir exige volver a leer cada ZIP mensual de la sindicación con el criterio
nuevo, porque las entradas que el filtro anterior descartaba nunca se
guardaron. Los 26 meses que el sistema ha barrido alguna vez (202408-202609)
se encolaron como 26 trabajos `sindicacion_backfill` de un mes cada uno
(19224-19229 y 19256-19275), para que un reinicio del worker solo repita un
mes. El resultado de cada mes queda en `trabajos_cola.resultado`
(`expedientes_nuevos` y `codigos_criterio_ampliado`) y en
`GET /mantenimiento/sindicacion/historial`.

La descarga va a 0,16-0,25 MB/s por conexión (160 MB el mes de 202608: 17
min), y el servidor no admite peticiones `Range` (responde 200 con el fichero
entero), así que no se puede bajar a trozos: unas 6 h para los 26 meses.

**Al cerrar: 2 de 26 meses leídos (202609 y 202608), 0 expedientes nuevos, 0
entradas que el filtro anterior habría descartado.** 202607 en curso y 23
meses en cola. Los expedientes que aparezcan se dan de alta como `pendiente`
y los descarga y extrae el siguiente ciclo de mantenimiento.

## 2. Los 8 expedientes recuperados sin líneas

Mirados contra sus documentos (texto y tablas con `pdfplumber`, y a ojo cuando
no hay texto):

| Expediente | Objeto | Qué publica | Veredicto |
|---|---|---|---|
| `2.24/28510.0050` | AdBlue, 4 lotes | Pliego técnico pp. 9-10 (y su copia en el Contrato, pp. 95-96): un cuadro por lote, "CANTIDAD ESTIMADA / DESCRIPCION / PRECIO DEL MES EN CURSO REFERENCIA / TOTAL", 59.150 litros a 0,60 € | Fallo de extracción |
| `2.25/28510.0005` | Gasóleo C | Pliego técnico, anexo II p. 8: "Nº / DESCRIPCIÓN / UD / PRECIO / IMPORTE", 89.900 a 0,808 | Fallo de extracción |
| `2.26/28510.0006` | Servicio de soporte DICOM | "Pliego de Condiciones Técnicas Particulares" p. 3-4: "DESGLOSE DE PRECIOS", 10 conceptos con unidad, cantidad y precio unitario | Fallo de extracción |
| `3.24/28510.0027` | Un compresor | Pliego técnico p. 5: "CONCEPTO / CANTIDAD / PRECIO / TOTAL", 1 a 18.000,00 € | Fallo de extracción |
| `3.24/28510.0132` | Resistencia patrón | Pliego técnico p. 4: "Concepto / Unidades / Importe", 1 a 16.125,00 € | Fallo de extracción |
| `3.25/28510.0012` | Cámara climática | Pliego técnico p. 4: "Concepto / Unidades / Importe", 1 a 24.000,00 € | Fallo de extracción |
| `3.24/28510.0126` | Dos carretillas elevadoras | Solo el presupuesto total (86.800 €). El Contrato remite los precios unitarios al pliego técnico, y el pliego técnico no los trae | Límite de origen |
| `6.17/28510.0056` | Aparatos de vía, Pobla Llarga-Silla | Los dos anejos (pliego técnico, 28 pp., y pliego administrativo, 50 pp.) son escaneados, 0 caracteres de texto. El técnico parece traer el presupuesto como imagen (pp. 19-20) | Documento escaneado: fuera de alcance sin OCR (CONTEXTO.md §15) |

### Causa de los 6 fallos

Una sola, en la etapa 4 (`app/extraccion/tabla.py`): una tabla se aceptaba solo
si alguna fila traía un código de precio (`P-001`, `P1`, `COD0001`...) o una
matrícula de 9 dígitos sin puntos. Un cuadro de uno o pocos artículos no numera
sus filas: la tabla salía de `pdfplumber` intacta y se descartaba entera como
espuria. En dos casos, además, la página no llegaba a abrirse (etapa 3): la
resistencia patrón y la cámara (densidad numérica 0,023 y 0,018, por debajo del
mínimo de 0,025, con la cabecera y una fila entre prosa).

### Arreglo

- **`tabla._filas_cuadro_sin_codigo`**: una tabla sin código ni matrícula se
  acepta si su primera fila nombra a la vez, en columnas distintas, la
  descripción ("descripción", "concepto", "designación", "denominación"), la
  cantidad ("cantidad", "unidades", "medición", "UD") y el precio ("precio",
  "importe"). Se queda con las filas que la siguen y traen descripción e importe,
  hasta la primera que no (el pie de totales: "TOTAL", "IVA"...). Un resumen de
  presupuesto por lotes, una tabla de valor estimado o de criterios no tienen
  esas tres columnas.
- **`localizador._tiene_linea_cabecera_cuadro`**: una página por debajo de la
  densidad mínima entra si una misma línea de texto nombra descripción,
  cantidad y precio (la cabecera del cuadro). La tabla la decide después la
  etapa 4.

### Efecto medido sobre el corpus entero, antes de desplegar

Con el código nuevo sobre todos los documentos (salvo pliegos administrativos
y escaneados): **43 tablas, 379 filas, en 18 expedientes**, que antes se
descartaban. Revisadas una a una: todas son cuadros de precios reales, ninguna
es un resumen de presupuesto ni una tabla de otro tipo. Además de los 6 del
encargo:

| Expediente | Qué recupera |
|---|---|
| `2.24/28510.0068` | Ferretería del laboratorio central: 101 filas (5 tablas) "DESCRIPCION / PRECIO DE REFERENCIA / MEDICIÓN ESTIMADA" |
| `6.24/28510.0129` | Cableado estructurado: 61 filas con matrícula escrita con puntos (`667.500.002`) |
| `6.25/28510.0246` | Equipamiento Huawei: 29 filas, matrícula con puntos |
| `4.26/28510.0031` | 17 filas "DESCRIPCIÓN / UNIDAD / MEDICIÓN ESTIMADA / PRECIO UNITARIO" (ya tenía 11 líneas de otra tabla) |
| `4.21/28510.0121` | Software de control: 14 filas "Id / Concepto / Precio / Medición / Total" |
| `6.20/28510.0041` | 9 filas con matrícula de 8 dígitos (`71590012`; ya tenía 336 líneas) |
| `2.24/28510.0118` | Material de balasto del laboratorio: 6 filas |
| `2.23/28510.0010` | Soporte DNS/DHCP: 4 partidas |
| `6.25/28510.0247` | Renovación de nodos: 3 filas, matrícula con puntos |
| `2.25/28510.0154` | Gasóleo C (mismo pliego que `0005`): 1 fila |
| `3.25/28510.0241` | Calibrador de humedad: 1 fila |
| `6.25/28510.0235` | Equipos SHDSL: 1 fila, matrícula con puntos |

16 de los 18 tenían 0 líneas. El localizador nuevo abre 29 páginas más en
todo el corpus y solo 3 traen tabla: las de resistencia patrón, cámara y
calibrador. No añade líneas a ningún otro expediente.

### Resultado

Desplegado y reprocesados los 18, más `0126` y `6.17/0056` (trabajo 19232,
sin sindicación):

| | Antes | Después |
|---|---:|---:|
| Líneas en base de datos | 33.924 | 34.167 (+243) |
| Excel, hoja "Materiales" | 15.067 filas | 15.308 (+241) |
| Expedientes con filas en el Excel | 253 | 269 (+16) |
| Materiales distintos en el Excel (matrícula, o descripción sin espacios ni signos) | 5.887 | 6.119 (+232, 0 perdidos) |

Solo cambian los 18 expedientes previstos. Por expediente, en el Excel:
`2.24/28510.0068` 0 → 82, `6.24/28510.0129` 0 → 61, `6.25/28510.0246` 0 →
29, `4.26/28510.0031` 11 → 28, `4.21/28510.0121` 0 → 14, `6.20/28510.0041`
336 → 345, `2.26/28510.0006` 0 → 7, `2.24/28510.0118` 0 → 5,
`2.23/28510.0010` 0 → 4, `2.24/28510.0050` 0 → 3, `6.25/28510.0247` 0 → 3, y
una fila cada uno `2.25/28510.0005`, `2.25/28510.0154`, `3.24/28510.0027`,
`3.24/28510.0132`, `3.25/28510.0012`, `3.25/28510.0241` y `6.25/28510.0235`.

Comprobado contra el PDF:

- `2.24/28510.0068` da 82 líneas de 101 filas: el pliego repite en la p. 4 las
  17 primeras herramientas del cuadro de las pp. 7-8, y una fila ("GUANTE JUBA
  JUNIT") viene dos veces en el propio cuadro. La fusión por descripción y
  precio es correcta: son 82 materiales distintos.
- AdBlue (`2.24/28510.0050`): los lotes 2, 3 y 4 salen con su lote. El lote
  1 queda sin lote, en la cola de revisión ("varias cabeceras de lote en la
  franja"): encima de su tabla está el resumen "TOTAL LOTE 1 ... LOTE 4", que
  `pdfplumber` detecta como tabla pero la etapa 4 descarta, y la franja se
  mide desde la última tabla aceptada. Cortar la franja también en las tablas
  descartadas cambia la asignación de lote de todo el corpus: no se ha hecho.
- Gasóleo (`0005`, `0154`): la columna de la cantidad se llama "UD"; el valor
  (89.900) va a unidad de medida, que lo descarta por numérico con motivo. La
  línea queda con precio (0,808 / 0,863 €) y sin cantidad.
- `4.21/28510.0121`: la cantidad "10 pers." de la formación no es un número;
  queda vacía con motivo.
- Queda sin leer la continuación del desglose de `2.26/28510.0006` en la
  página siguiente (3 filas sin cabecera: horas de técnico y dos cursos): la
  página no trae cabecera ni identificadores de fila.

### Auditoría (fin del ciclo 19232)

Tres hallazgos de gravedad "error", ninguno de este cambio:

- `lineas_cambian_sin_cambiar_documentos`: 11 expedientes. Son los de esta
  lista: cambia el código de extracción, no los documentos, que es lo que la
  comprobación no puede distinguir (mismo caso que en sesiones anteriores).
- `lineas_duplicadas_exactas`: 12 grupos y 27 líneas (antes 11 y 22). El grupo
  nuevo es de `4.26/28510.0031`: 5 filas "DESCRIPCIÓN | UNIDAD" (la cabecera
  leída como fila) de su tabla con código P1/P2.01, guardadas a las 09:35 por
  la recuperación de la segunda parte. Las 17 líneas nuevas de ese expediente
  están limpias.
- `sin_descripcion`: 1 línea, `6.25/28510.0257` P-22 (partida alzada de un
  LOTE 4 no declarado), también de las 09:35.

## Pendiente

- Terminar la medición del criterio ampliado (23 meses en cola al cerrar).
- Lote 1 de AdBlue y la continuación del desglose de `2.26/28510.0006` (ver
  arriba).
- Las 5 filas-cabecera de `4.26/28510.0031` y la línea sin descripción de
  `6.25/28510.0257`, de la sesión anterior.
- `6.17/28510.0056`: si ADIF puede facilitar el pliego técnico con texto, o
  si algún día entra el OCR (CONTEXTO.md §15).
