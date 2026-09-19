# Información para preguntar a ADIF — el lote que declara el título, y los ficheros de entrada

Sesión 2026-09-19 (tercera parte), bloque 6. **Este documento no es un mensaje
para el cliente**: es la información medida para que la pregunta la formule
quien habla con ADIF. Cada cifra está medida contra la base de datos y los
documentos reales, y cada dato dice de dónde sale.

La pregunta de **CONTRAGUJA / CONTRAAGUJA** ya está redactada en
`docs/pregunta-cliente-contraguja-contraaguja.md` y no se repite aquí.

---

## 1 — Los once expedientes cuyo título nombra un lote que no está entre sus lotes registrados

### El hallazgo que cambia la pregunta

Antes de mirar el detalle, un dato que la sesión anterior no tenía y que
reorienta la pregunta entera:

> **El título de estos once no sale de ningún documento publicado en la
> Plataforma. Sale del propio listado de ADIF.**

Medido: `trazas_origen` guarda, para cada expediente cuyo título se leyó del
campo *Objeto del Contrato* de un documento, el documento y la página exactos
(186 expedientes del corpus lo tienen así). **Ninguno de estos once tiene esa
traza.** Su `nombre_proyecto` lo escribió la carga de los listados que ADIF nos
envió — `app.extraccion.estados_adif` y `app.extraccion.estado_sap`, columna
*Título del expediente* —, y se ha comprobado uno a uno que los once aparecen
ahí con ese título literal:

- `Ejemplo/Input/estados_expedientes_28510_20260918.xlsx` — 10 de los 11.
- `Ejemplo/Input/EXPEDIENTES_EJECUCION_SAP 1.XLSX` — 11 de los 11.

Así que la contradicción no es entre dos lecturas nuestras: es entre **lo que
el sistema de ADIF llama a ese expediente** y **los lotes que declaran los
documentos que la Plataforma publica bajo su número**.

### La tabla

| Expediente | Lote que dice el título | Lotes registrados | Lotes que declara la licitación | Filas que aporta hoy |
|---|---|---|---|---:|
| `6.21/28510.0135` | Lote 6 | 1, 3, 7 | 9 | 259 |
| `6.21/28510.0137` | Lote 8 | 1, 3, 7 | 9 | 259 |
| `6.21/28510.0138` | Lote 9 | 1, 3, 7 | 9 | 259 |
| `6.22/28510.0139` | Lote 1 | 5, 6 | 6 | 18 |
| `6.22/28510.0140` | Lote 2 | 5, 6 | 6 | 18 |
| `6.22/28510.0142` | Lote 4 | 5, 6 | 6 | 18 |
| `6.22/28510.0147` | Lote 1 | 4, 5 | 6 | 18 |
| `6.22/28510.0148` | Lote 2 | 4, 5 | 6 | 18 |
| `6.22/28510.0149` | Lote 3 | 4, 5 | 6 | 18 |
| `6.23/28510.0073` | Lote 1 | 3, 4 | 4 | 20 |
| `6.23/28510.0074` | Lote 2 | 3, 4 | 4 | 0 |

**Aviso sobre la columna de filas.** Son las líneas de catálogo del expediente
en la base de datos, medidas en esta sesión. No coinciden con las 265 filas del
Excel que daba la sesión anterior porque esa cifra era la de la hoja
"Materiales" (que deja fuera las líneas sin lote) y porque los tres primeros
comparten los seis cuadros de su licitación. Lo que importa para la pregunta no
es la cifra, sino que **ninguna de esas filas es del lote que su título
nombra**.

### Títulos completos

| Expediente | Título, literal del listado de ADIF |
|---|---|
| `6.21/28510.0135` | Lote 6. Placas asiento PAE (Pae-1, Pae-2, Pae-Z1, Pae-Z2) y PAS (Pas-1 y Pas-2) |
| `6.21/28510.0137` | Lote 8. Sujeciones |
| `6.21/28510.0138` | Lote 9. Sistema de fijacion 300-1 |
| `6.22/28510.0139` | Lote 1: Base de mantenimiento de Villarrubia |
| `6.22/28510.0140` | Lote 2: Base de mantenimiento de Gabaldón |
| `6.22/28510.0142` | Lote 4: Base de mantenimiento de Requena |
| `6.22/28510.0147` | Lote 1: Base de mantenimiento de Brihuega |
| `6.22/28510.0148` | Lote 2: Base de mantenimiento de Calatayud |
| `6.22/28510.0149` | Lote 3: Subbase de mantenimiento de La Cartuja |
| `6.23/28510.0073` | Lote 1: Base de mantenimiento de Mora |
| `6.23/28510.0074` | Lote 2: Base de mantenimiento de Calatrava |

### De qué documento sale cada cosa

Los lotes registrados **no se han deducido de nada**: cada uno lo declara por
su número un documento firmado, y `trazas_origen` guarda el documento, la
página y el fragmento literal. Tres ejemplos completos, uno por familia:

**`6.21/28510.0135`** — título "Lote 6", lotes registrados 1, 3 y 7:

| Lote | Dato | Documento | Página | Fragmento literal |
|---|---|---|---:|---|
| 1 | baja | `CONTRATO_2.pdf` | 1 | "baja económica ofertada del 20,31% será de aplicación al conjunto de precios unitarios" |
| 1 | importe de licitación | `CONTRATO_2.pdf` | 1 | "importe de licitación del lote 1 a 220.000,00 € (IVA excluido)" |
| 3 | baja | `ADJUDICACION_1.pdf` | 1 | "14,00 % de baja a todos los precios unitarios" |
| 7 | baja | `CONTRATO_1.pdf` | 1 | "baja económica ofertada del 0,50% será de aplicación al conjunto de precios unitarios" |
| 7 | importe de licitación | `CONTRATO_1.pdf` | 1 | "importe de licitación del lote 7 a 143.000,00 € (IVA excluido)" |

**`6.22/28510.0139`** — título "Lote 1", lotes registrados 5 y 6:

| Lote | Dato | Documento | Página | Fragmento literal |
|---|---|---|---:|---|
| 5 | baja | `CONTRATO_2.pdf` | 1 | "baja económica ofertada del 0,50% se aplicará al conjunto de precios unitarios" |
| 5 | importe de adjudicación | `CONTRATO_2.pdf` | 2 | "importe del contrato es de: Base imponible … 232.222…" |
| 5 | importe de licitación | `CONTRATO_2.pdf` | 2 | "importe de licitación del Lote 5 a 232.222,38 € (IVA excluido)" |
| 6 | baja | `ADJUDICACION_1.pdf` | 1 | "baja del 0,40% a precios unitarios" |
| 6 | importe de licitación | `CONTRATO_1.pdf` | 2 | "importe de licitación del Lote 6 a 659.431,85 € (IVA excluido)" |

**`6.23/28510.0073`** — título "Lote 1", lotes registrados 3 y 4:

| Lote | Dato | Documento | Página | Fragmento literal |
|---|---|---|---:|---|
| 3 | baja | `CONTRATO_2.pdf` | 1 | "baja económica del 11,21% será aplicable al conjunto de precios unitarios" |
| 3 | importe de adjudicación | `CONTRATO_2.pdf` | 2 | "importe del contrato es de: Base imponible … 1.095…" |
| 3 | importe de licitación | `CONTRATO_2.pdf` | 2 | "importe de licitación del Lote 3 a 1.095.040,00 € (IVA excluido)" |
| 4 | baja | `ADJUDICACION_1.pdf` | 1 | "baja económica del 5,00% a todos los precios unitarios" |
| 4 | importe de licitación | `CONTRATO_1.pdf` | 2 | "importe de licitación del Lote 4 a 1.530.240,00 € (IVA excluido)" |

El patrón se repite en los once: **los dos `CONTRATO_*.pdf` que la Plataforma
publica bajo el número de este expediente son los contratos de OTROS dos lotes
de su licitación**, y cada uno lo dice de sí mismo con su número de lote y su
importe. El título, en cambio, viene del listado de ADIF.

### La pista que lo vuelve incómodo

En `6.21/28510.0135`, su propio `ANEJO_3.pdf` **sí trae, en la página 6, una
sección titulada "LOTE 6 - PLACAS ASIENTO PAE (PAE-1, PAE-2, PAE-Z1, PAE-Z2) y
PAS (PAS-1 y PAS-2)"**, palabra por palabra el título que le da ADIF
(re-comprobado en esta sesión contra el texto del documento, no heredado de la
anterior). Es decir: el cuadro
del lote 6 está publicado, dentro de un documento de este expediente. Lo que
no hay es ningún documento que ligue el número `6.21/28510.0135` al lote 6, así
que esa tabla queda sin lote y el expediente se queda con los cuadros de los
lotes 1, 3 y 7, que son los que sus contratos declaran.

### Documentos que tiene cada uno

Los once tienen entre 3 y 10 documentos descargados. Los tres de
`6.21/28510.01xx` tienen exactamente los mismos diez
(`ADJUDICACION_1`, `ANEJO_1`…`ANEJO_6`, `CONTRATO_1`, `CONTRATO_2`,
`PLIEGO_1`); los de `6.22/28510.01xx` entre 7 y 8; `6.23/28510.0073` seis y
`6.23/28510.0074` tres (`ADJUDICACION_1`, `CONTRATO_1`, `CONTRATO_2`, sin
ningún anejo — por eso aporta 0 filas).

### Qué preguntar, y qué NO preguntar

**No preguntar** "¿les ponemos el lote del título?". El sistema no puede
aplicarlo sin inventar: la regla del lote del título (sesión 2026-09-19,
primera parte) exige como condición de certeza que el número del título esté
entre los lotes que el expediente ya tiene, y en estos once no lo está en
ninguno. Aplicarla igual significaría borrar los lotes que un contrato firmado
declara y crear uno que ningún documento les asigna.

**Preguntar**, con este orden:

1. **¿Por qué los lotes que declaran los contratos publicados bajo estos once
   números no incluyen el que su propio título nombra?** Para
   `6.21/28510.0135`: su título (de su SAP) dice lote 6; sus dos contratos
   publicados dicen lote 1 y lote 7, y su adjudicación lote 3.
2. **¿Cuál es el número de expediente del lote 6 de esa licitación?** Si
   existe uno propio, es el que debería llevar esas líneas, y basta con que nos
   digan el número para buscarlo.
3. **¿La Plataforma publica los contratos de estos lotes bajo el número del
   expediente principal en vez del suyo?** Es el mecanismo que ya se confirmó
   para otros 17 expedientes de la Conciliación (situación "Publicado dentro de
   la ficha de otro expediente"), y encajaría con lo observado.

**Mientras tanto no se pierde nada**: las filas siguen en el entregable con el
lote que sus documentos les dan hoy, y el material de los lotes que les faltan
sale en el expediente hermano que sí los declara.

---

## 2 — Inventario de los ficheros de entrada de `Ejemplo/Input`

Los cinco ficheros que el sistema lee de esa carpeta, más una sexta fuente prevista y hoy vacía, con las columnas que usa
de cada uno, para qué las usa y de dónde viene el fichero. **Los PDF de esa
misma carpeta no son fuentes de entrada configuradas**: son el conjunto fijo de
prueba del repositorio (CONTEXTO.md sección 13), 45 expedientes de 2018-2025
que se usan como fixtures.

### 2.1 — `Códigos de proyecto.xlsx`

| | |
|---|---|
| **Variable** | `CODIGOS_PROYECTO_PATH` |
| **Módulo** | `app.extraccion.cruce_codigos` |
| **Se recarga** | en cada cruce; se leen **todas** las hojas, no solo la primera |
| **Tamaño** | 1 hoja, 666 filas |
| **Origen** | **Otro sistema de ADIF.** Es el listado de códigos de proyecto que mantiene ADIF y que nos facilitaron al principio del proyecto. No es SAP y no es la Plataforma. |

| Columna | Para qué se usa |
|---|---|
| `Nº Interno` | La columna **"Código interno"** del Excel. Solo se escribe si la fila encontrada es la del propio expediente (`cruce_fila_propia`, sesión 2026-09-18). |
| `Nº Expediente` | Primera de las cuatro claves de cruce. Es la única que garantiza que la fila hallada sea la del propio expediente. |
| `MATRIZ` | La columna **"Código matriz"** del Excel, y segunda y cuarta claves de cruce. |
| `ESPECIALIDAD/DISCIPLINA` | **No se guarda en base de datos.** Se midió en la sesión 2026-09-09 (99,4 % de coherencia con el código interno) para la propuesta de exclusión por jefatura, y ahí se quedó. |
| `DESCRIPCIÓN` | **No se usa.** El título del expediente sale del documento o de los listados de ADIF, nunca de aquí. |

### 2.2 — `EXPEDIENTES_EJECUCION_SAP 1.XLSX`

| | |
|---|---|
| **Variable** | `ESTADO_SAP_PATH` |
| **Módulo** | `app.extraccion.estado_sap`, `POST /mantenimiento/estado-sap/cargar` |
| **Tamaño** | 1 hoja, 368 filas (367 expedientes del departamento 28510) |
| **Origen** | **SAP.** Extracto de expedientes en ejecución que ADIF sacó de su SAP y nos envió (sesión 2026-09-07). |

| Columna | Para qué se usa |
|---|---|
| `Expediente ADIF` | La clave. **Da de alta el expediente si no existe** (a diferencia del listado de estados de 2.3): es la única fuente de la que el sistema puede saber que existen los expedientes anteriores a 2021, invisibles para la sindicación. |
| `Título del expediente` | Rellena `nombre_proyecto` si no se ha leído de un documento. **Es de aquí de donde sale el título de los once expedientes del bloque 1.** |
| `Descripción del estado` | La columna **"Estado del contrato (SAP)"** del Excel (`expedientes.estado_contrato_sap`). |

### 2.3 — `estados_expedientes_28510_20260918.xlsx`

| | |
|---|---|
| **Variable** | `ESTADOS_ADIF_PATH` |
| **Módulo** | `app.extraccion.estados_adif`, `POST /mantenimiento/estados-adif/cargar` |
| **Tamaño** | 1 hoja, 359 filas (358 expedientes, todos del 28510) |
| **Origen** | **SAP.** ADIF lo envió el **18/09/2026**; es una transacción de SAP ejecutada por ellos. En su día se nos indicó no usar volcados de SAP, así que **se preguntó expresamente en el grupo de trabajo y nos autorizaron a usarlo** (CONTEXTO.md sección 7). |

| Columna | Para qué se usa |
|---|---|
| `Expediente ADIF` | La clave. **Nunca da de alta un expediente** (al contrario que 2.2): crear aquí lo que no tenemos haría que la pregunta "¿cuáles de los suyos nos faltan?" se contestara sola y en falso. |
| `Descripción del estado` | La columna **"Estado según ADIF"** de la hoja "Conciliación" (`expedientes.estado_adif`). Nunca se mezcla con "Estado que consta publicado en la Plataforma" ni escribe en `estado_contrato_sap`: son dos volcados de SAP distintos (212 códigos en común, 155 solo en el anterior, 146 solo en este). |
| `Título del expediente` | Rellena `nombre_proyecto` si falta. Misma vía que 2.2. |
| `Fecha de creación` | **No se usa.** |

**No trae presupuesto de licitación ni órgano de contratación**, así que la
validación de importes que se ofreció al cliente no se pudo hacer y se
sustituyó, con su visto bueno, por un contraste de estados.

### 2.4 — `LISTADO_MATERIALES_UNIDAD_,MEDIDA.xlsx`

| | |
|---|---|
| **Variable** | `MAESTRO_MATERIALES_PATH` |
| **Módulo** | `app.extraccion.maestro_materiales`, `POST /mantenimiento/maestro-materiales/cargar` |
| **Tamaño** | 1 hoja, 32.117 filas |
| **Origen** | **SAP.** Maestro de materiales que ADIF facilitó (sesión 2026-09-10). |

| Columna | Para qué se usa |
|---|---|
| `Material` | La matrícula, clave exacta del cruce. Admite códigos de 4 y 10 dígitos además de los 9 del dominio (`String(10)`, migración 0026). |
| `UM base` | Completa la **unidad de medida** de una línea que no la trae del documento, por matrícula exacta. **Nunca pisa** una unidad extraída de un documento real; si discrepan, se anota aparte (`unidad_medida_discrepancia_maestro`). |
| `Denominación` | **No se usa para asignar nada.** Se analizó como vía para completar la matrícula por descripción (sesión 2026-09-10) y se descartó: 8,3 % de las denominaciones mapean a más de una matrícula, y de las líneas con alta similitud el 66,6 % tiene más de un candidato. Si algún día se implementa, tiene que ser cola de candidatos para confirmación humana. |

**El nombre del fichero trae una coma donde debería haber un punto**
(`UNIDAD_,MEDIDA`). No es un error nuestro: llegó así. Se deja tal cual para
que la variable de entorno siga apuntando al fichero real.

### 2.5 — `contratos traviesas.XLSX`

| | |
|---|---|
| **Variable** | `SAP_DESGLOSE_PATH` |
| **Módulo** | `app.extraccion.sap_desglose`, `POST /mantenimiento/sap-desglose/cargar` (tabla `sap_desglose_lineas`) |
| **Tamaño** | 1 hoja, 186 filas |
| **Origen** | **SAP.** Desglose de pedidos con matrículas concretas que ADIF envió (sesión 2026-09-09, bloque 6). |

| Columna | Para qué se usa |
|---|---|
| `expediente` | Clave de cruce con el expediente. |
| `Material` | La matrícula de la línea. |
| `Cantidad prevista` | Se guarda en `sap_desglose_lineas`. |
| `Precio neto pedido` | Se guarda. Con él se verificó contra datos reales la cadena licitación → adjudicado → final (40 de 60 coinciden). |
| `Documento compras`, `Posición`, `Indicador de borrado`, `Última modificación`, `Texto breve`, `Centro` | Se guardan como contexto de la línea. |

**Cargado pero deliberadamente sin explotar**: ni la derivación del
coeficiente ni la completitud automática de matrícula están implementadas —
encargo explícito del cliente, "no lo implementes todavía".

### 2.6 — Una sexta fuente que existe pero hoy está vacía: la lista de exclusión

| | |
|---|---|
| **Variables** | `EXCLUSION_EXPEDIENTES_PATH`, `EXCLUSION_PALABRAS_TITULO_PATH` |
| **Módulo** | `app.exclusion`, aplicado dentro de `app.catalogo_consulta.consultar_catalogo` |
| **Formato** | Texto plano, una entrada por línea, `#` para comentarios. Admite código exacto (`6.24/28510.0088`), departamento completo (`28520`) o código interno (`INTERNO:NNNNN`). |
| **Origen** | **El propio cliente.** No es un volcado de ningún sistema: son los expedientes que el cliente diga que no son de su equipo. |

**Hoy no hay ningún fichero de exclusión en el repositorio** y las dos
variables están sin definir, así que no se excluye nada. Se deja inventariada
porque es la única fuente de entrada que decide qué sale del entregable, y si
algún día el cliente entrega esa lista entrará por aquí. Esconde del Excel
entregado y de `/catalogo` en la web, **nunca de la base de datos** ni de las
pantallas de gestión y revisión.

### 2.7 — Orígenes que no se sabe de dónde vienen

Ninguno. Los cinco ficheros que el sistema lee hoy de `Ejemplo/Input` tienen
procedencia conocida y escrita: **cuatro son de SAP** (2.2, 2.3, 2.4, 2.5) y
**uno es de otro sistema de ADIF** (2.1, el listado de códigos de proyecto). La
sexta fuente (2.6) la haría el propio cliente y todavía no existe.

Los cinco están montados en los contenedores desde esa carpeta, uno a uno, en
`docker-compose.override.yml` — comprobado fichero por fichero, no supuesto. De
la Plataforma de Contratación **no entra ningún fichero por esta carpeta**: lo
de la Plataforma lo descarga el sistema solo, por navegación o por sindicación,
y va al almacenamiento de documentos (`DOCUMENT_STORAGE_PATH`), no a
`Ejemplo/Input`. La carpeta de ingesta manual de PDF (`INGESTA_LOCAL_PATH`) es
otra cosa y tampoco apunta aquí.

Lo que sí conviene confirmar con ADIF, y no es una duda de origen sino de
interpretación:

- **Los dos volcados de SAP (2.2 y 2.3) se solapan pero no coinciden**: 212
  códigos en común, 155 solo en el de 2026-09-07, 146 solo en el de
  2026-09-18. En los 212 comunes el estado coincide en los 212. Merece
  preguntar si el segundo sustituye al primero o si son dos consultas
  distintas que hay que mantener las dos.
- **Los 358 códigos del listado de estados coinciden exactamente con los
  nuestros** (`md5` de las dos listas ordenadas: `016a98f7…`). Eso no es una
  buena noticia sin más: un volcado de SAP no tiene por qué coincidir
  expediente a expediente con "de cuáles hemos podido extraer líneas", así que
  **conviene confirmar con ADIF que el fichero no se generó a partir de nuestro
  catálogo** antes de presentar el "0 discrepancias" como prueba de cobertura.
