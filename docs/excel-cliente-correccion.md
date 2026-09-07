# Corrección del Excel de entrega al cliente

Sesión 2026-09-06. Álvaro revisó el Excel exportado (3.036 filas, once
columnas) y señaló cinco problemas. Este documento recoge el diagnóstico,
lo que se arregló, lo que se dejó explicado sin tocar código, y los números
finales verificados.

---

## 1. Marcadores de texto en columnas numéricas

`app/exportacion.py` escribía `"(no consta)"`/`"(no aplica)"` en cualquier
celda vacía, incluidas Cantidad y Precio unitario — 540 y 16 apariciones
respectivamente, que convertían esas columnas en texto mixto en Excel.

**Arreglo**: `_celda_numero` devuelve el valor como `float` o `None` (celda
vacía), nunca un marcador. Mismo criterio aplicado a las columnas de texto
(Matrícula, Código del material, Lote) por consistencia y porque es el
formato que el cliente ya maneja: celda vacía, sin variantes. El motivo por
el que falta ya vive en `motivo_revision`/la cola de revisión interna, no
se inventa un texto nuevo para la celda. Formato de celda explícito
añadido (`#,##0.###` para Cantidad, `#,##0.00` para los importes, `0.00%`
para la baja) para que Excel no las trate como texto por estar en
"General".

Tests: `tests/test_exportacion.py` reescrito para el nuevo comportamiento.

## 2. Duplicados sin limpiar

### Lo que NO era

Verificado contra `docs/correccion-defectos-auditoria.md`: el bug de
duplicación infinita (canonicalización de `clave_linea` sin guardia de
`fusion_material`) ya se arregló y limpió la noche del 2026-09-05/06,
confirmado con cero duplicados exactos (`ROW_NUMBER() OVER (PARTITION BY
expediente_id, documento_origen_id, pagina, orden_aparicion)`).

### Lo que sí era

El hueco que `docs/decisiones.md` sección 31 ya había dejado anotado como
pendiente de medir: de las 1.108 líneas huérfanas (`lote_id IS NULL`,
tabla que no se pudo asociar a un lote sin ambigüedad), medido sobre el
corpus completo (no solo `6.25/28510.0019` como en esa sección):

- **268 líneas** eran copia exacta de una línea que YA tiene lote resuelto
  en el mismo expediente (mismo `codigo_precio`, descripción y precio
  unitario, matrícula idéntica, sin `cantidad` perdida) — repetidas solo
  porque una segunda tabla (normalmente el CONTRATO adjuntando el mismo
  cuadro de precios que ya trae el ANEJO) no pudo asociarse a lote.
  Verificado antes de borrar: las 268 estaban `sin_revisar`, sin
  comentarios humanos, todas con `motivo_revision` explicando la
  ambigüedad. **Borradas** dentro de una transacción, con volcado previo
  de `lineas_catalogo` completo (`pg_dump --data-only`, guardado en
  `/home/lucas/adif/lineas_catalogo_backup_20260906.sql` en el servidor de
  desarrollo). Catálogo: 3.036 → **2.768 líneas**.
- **840 líneas** sin ningún lote resuelto equivalente: de estas, 671 son la
  misma materia repetida entre sí (varias copias de la misma tabla técnica
  sin lote, ninguna resuelta) y 169 son líneas únicas que solo les falta
  lote. Todas siguen en la cola de revisión interna, sin tocar.

### Política de exportación (encargo de esta sesión)

`generar_excel_catalogo` gana un parámetro `incluir_pendientes_sin_lote`
(por defecto `False`, expuesto como `?incluir_pendientes=true` en
`GET /catalogo/exportar.xlsx`): las líneas huérfanas no salen en la hoja
"Materiales" por defecto — mostrarían el mismo material repetido sin que
el cliente pueda distinguir una repetición real de un artefacto de
extracción, y siguen genuinamente pendientes de que alguien les asigne
lote. Nunca desaparecen en silencio: la hoja **"Resumen"** siempre dice
cuántas líneas hay en "Materiales", cuántas quedaron fuera y, si las hay,
el desglose por motivo agrupado (`_categoria_motivo`, cuatro categorías
según `app.extraccion.lote_tabla`). Con `incluir_pendientes=true` vuelven a
"Materiales" sin tocar código.

Tests: `tests/test_exportacion.py` (categorización de motivos) y
`tests/test_api_catalogo.py` (exclusión por defecto + hoja Resumen +
inclusión con el parámetro).

### Residuo menor, sin tocar (mismo mecanismo, expedientes de un solo lote)

47 grupos (142 filas) de "mismo material, mismo precio, más de una vez" **sí
siguen** en la hoja Materiales tras el arreglo de arriba. De estos, 32
grupos (67 filas) son la misma tabla repetida entre ANEJO y CONTRATO
(mecanismo B de `docs/hallazgos-extraccion.md` sección 30.2) pero en
expedientes de **un solo lote** — ahí la línea SÍ tiene lote asignado (el
único que hay), así que no cae en el filtro de huérfanas de arriba. La
fusión por firma de material (`_firma_material`, `app/catalogo.py`) no las
funde porque son líneas sin matrícula (p. ej. "PARTIDA ALZADA A JUSTIFICAR
PARA IMPREVISTOS"), y esa firma exige matrícula presente. Sin medir ni
tocar en esta sesión — queda para una sesión aparte, con el mismo cuidado
de verificar antes de fundir/borrar.

## 3. Columnas de precio adjudicado y baja de lote

Ya vivían en cada línea (`LineaCatalogo.precio_adjudicado`,
`LineaCatalogo.baja_lote`, calculadas en `app.catalogo`, sección 4 de
CONTEXTO.md) — solo faltaban en el Excel. Añadidas **al final**, sin mover
las once columnas del formato original: "Precio adjudicado" y "Baja del
lote" (formato `0.00%`).

## 4. Código matriz vacío al 100%

No era un fallo del exportador ni del cruce. De los 58 expedientes en base
de datos, solo 8 tienen `codigo_matriz` real, y los 8 son pedidos
derivados de acuerdo marco cuya matriz sigue `sin_publicar` en la
Plataforma — por eso tienen **cero líneas de catálogo** y nunca llegan a
aparecer en el Excel. Nada que arreglar en código: se resuelve solo en
cuanto esas matrices se publiquen y hereden su cuadro de precios
(`app.extraccion.herencia_matriz`).

### Bug real encontrado en el camino: el cruce de códigos estaba roto en silencio

Al investigar el cruce con el Excel de códigos se encontró que
`docker-compose.override.yml` (deploy en `/home/lucas/adif`) monta
`Ejemplo/Input/Códigos de proyecto.xlsx` en el contenedor, y ese fichero
llevaba tiempo **ausente** del árbol de despliegue: Docker, al no
encontrar el origen del bind-mount, creó en su lugar un directorio vacío
tanto en el host como dentro del contenedor (`/data/codigos_proyecto.xlsx`
era un directorio, no un fichero). `asegurar_cruce_codigos` solo atrapa
`FileNotFoundError` — un directorio produce `IsADirectoryError` (via
`openpyxl`/`zipfile`) sin capturar, y como `codigos_cruzados` no se
reintenta nunca una vez escrito, cualquier expediente cuyo intento cayera
en una ventana con el mount roto quedaba marcado `codigos_cruzados = False`
para siempre, indistinguible de un expediente que de verdad no cruza.

Correlación verificada con timestamps: 6 expedientes
(`6.24/28510.0100`, `0101`, `0102`, `0103`, `0111`, `6.25/28510.0248` — los
pedidos derivados de acuerdo marco de la matriz `2.18/04703.00xx`/
`2.24/04110.0037`) tienen su único intento de cruce fechado
`2026-09-06 07:12:2x UTC`, exactamente en la ventana de una de las dos
caídas de `dockerd` documentadas en `docs/diagnostico-caidas-dockerd.md`
(09:12 hora local = 07:12 UTC).

**Restaurado**: el fichero real copiado de vuelta al árbol de despliegue
(`/home/lucas/adif/Ejemplo/Input/Códigos de proyecto.xlsx`), contenedores
reconstruidos. **Reprocesado** el cruce de los 16 expedientes con
`codigos_cruzados = False`: 6 (los de arriba) cruzan correctamente contra
el fichero restaurado y se corrigieron en base de datos (`codigos_cruzados
= True`, `codigo_interno` relleno). Los otros 10 (las 6 matrices
`sin_publicar` del Excel de acuerdo marco más `3.23/28510.0135`,
`4.26/28510.0020`, `6.25/28510.5001_01`, `6.26/28510.0016`) se reintentaron
también y siguen sin cruzar — confirmado con un cruce manual contra el
fichero ya restaurado: genuinamente no están en el Excel de códigos, no es
un efecto del mount roto.

Este arreglo **no cambia los números del Excel de hoy** (los 6 corregidos
siguen sin ninguna línea de catálogo propia, por la matriz sin publicar),
pero corrige datos incorrectos en base de datos y evita que futuras líneas
de estos 6 expedientes salgan sin código interno cuando su matriz se
publique.

**Comprobación permanente añadida** (encargo de esta sesión): 
`app.extraccion.cruce_codigos.validar_ruta_codigos_proyecto`, llamada al
arrancar tanto `app.main` (API) como `app.worker`. Si
`CODIGOS_PROYECTO_PATH` está configurada pero no es un fichero `.xlsx`
legible, el proceso falla al arrancar en vez de continuar con el cruce
roto en silencio. Tests en `tests/extraccion/test_cruce_codigos.py`.

## 5. Huecos menores (código interno/proyecto/nombre)

Confirmado exactamente contra la base de datos: 41 filas sin código
interno/proyecto (`6.26/28510.0016`, el único expediente con líneas de
catálogo que no cruza — confirmado gap real del Excel de códigos, no del
mount, ver punto 4) y 95 filas sin nombre de proyecto (`6.20/28510.0136`,
`6.20/28510.0054`, `6.23/28510.0018`, `6.24/28510.0116` — cuatro
expedientes cuyo Anuncio PCSP no dejó extraer el "Objeto del Contrato";
tres siguen en `pendiente_revision`, uno — `6.20/28510.0136` — ya está
`completado` con el nombre vacío, pendiente de mirar en una sesión aparte
de extracción, no de exportación).

## Hallazgo menor adicional, sin tocar (corregido: ver Bloque 2)

2 líneas (~~`6.23/28510.0051`~~ **`6.20/28510.0136`, ANEJO_3 — la atribución
a `0051` en la redacción original de este punto era un error de esta misma
sesión, corregido en el Bloque 2**, matrículas `740580020` y `740540009`)
tenían `descripcion = ''` (cadena vacía, no NULL — la columna es `NOT NULL`)
con matrícula pero sin ninguna descripción real capturada, `sin_revisar`. No
era uno de los cinco problemas de esta sesión; arreglado en el Bloque 2 de
abajo.

## Verificación final

Tras el borrado de las 268 líneas y con la política de exclusión de
huérfanas activa (`incluir_pendientes=false`, el comportamiento por
defecto del Excel que se entrega):

| Concepto | Valor |
|---|---|
| Líneas en base de datos (post-limpieza) | 2.768 |
| Líneas en "Materiales" (hoja entregada) | 1.928 |
| Líneas pendientes de revisión (hoja "Resumen") | 840 (611 banda vacía + 131 sin cabecera + 98 lote no declarado) |
| Cantidad / Precio unitario / Precio adjudicado / Baja: tipos de celda | Solo `float`/`int`/vacío — cero texto mixto |
| Matrícula / Código del material / Lote: marcadores de texto | Cero — vacío o valor real |
| Sin código interno/proyecto | 41 (gap real de cruce, confirmado) |
| Sin nombre de proyecto | 95 (gap real de extracción, confirmado) |
| Con código matriz | 0 (gap real de cobertura: las 8 matrices reales no tienen líneas propias) |
| Grupos "mismo material repetido" restantes en Materiales | 47 grupos / 142 filas — 15 grupos / 75 filas son multi-lote legítimo (mismo material, lotes distintos); 32 grupos / 67 filas son el residuo del mecanismo B en expedientes de un solo lote (sin tocar, ver punto 2) |

Suite completa: **332 tests pasan** (319 antes de esta sesión + 13 nuevos:
6 de exportación, 5 de `validar_ruta_codigos_proyecto`, 2 de política de
huérfanas en la API).

---

## Bloque 2: los dos residuos pendientes, causa raíz y arreglo (sesión 2026-09-06, continuación)

Cierra los dos hilos que el bloque 1 dejó anotados sin tocar: el residuo de
32 grupos/67 filas del mecanismo B en expedientes de un solo lote, y las 2
líneas con `descripcion = ''`.

### 1. Causa raíz del residuo: no es el mecanismo B, es uno nuevo

Verificado contra los PDF reales (no contra hipótesis): el residuo **no**
era la misma tabla repetida entre ANEJO y CONTRATO (mecanismo B). Es un
mecanismo distinto: una **segunda tabla del mismo documento** que reutiliza
el mismo material — descripción y precio idénticos — bajo un `codigo_precio`
de numeración propia, sin matrícula ninguna de las dos veces. Dos variantes
reales, ambas confirmadas abriendo el PDF con `pdfplumber`:

- **Tabla de "impacto del fallo del elemento en la seguridad operacional"**
  (`6.24/28510.0180_ANEJO_1.pdf` p.23, `6.23/28510.0051_CONTRATO_1.pdf`
  p.174): un anejo de clasificación de seguridad/normativa que vuelve a
  listar cada material del cuadro de precios real, con su descripción y
  precio, bajo su propia numeración de referencia — no es un cuadro de
  precios de licitación, es un anexo de cumplimiento normativo que coincide
  con los datos reales por diseño.
- **Línea administrativa repetida entre secciones** (`PARTIDA ALZADA A
  JUSTIFICAR PARA IMPREVISTOS`, `6.20/28510.0136` y `6.20/28510.0054`): la
  misma partida de imprevistos del presupuesto aparece como cabecera de más
  de una sección del mismo cuadro de precios.

`_firma_material` (matrícula + descripción + precio) ya fundía este patrón
cuando había matrícula (auditoría 2026-09-05); aquí no la hay nunca, así que
la firma no se disparaba y las dos copias quedaban como filas separadas.
**Medido sobre el corpus real de esta sesión: 26 grupos / 55 filas** (no 67 —
la cifra de 67 del bloque 1 fue una estimación de sesión, no una medición
directa; 55 es el recuento exacto verificado con `SELECT` antes de tocar
nada).

**Arreglo** (`app/catalogo.py`): `_firma_material` cae a (descripción,
precio unitario) cuando no hay matrícula, en vez de devolver `None`. Sigue
sin aplicarse nunca a huérfanas (`permitir_fusion_material`/`fusion_material`
ya lo garantizaban, sin tocar). El riesgo teórico de fundir por casualidad
dos materiales genuinamente distintos que compartan descripción y precio
queda acotado a **dentro del mismo lote** (el filtro de `lote_id` ya separa
lotes distintos antes de llegar a la firma) — no verificado ningún caso real
de esa casualidad en el corpus, y la fusión deja `motivo_revision` explícito
("fila fundida con otra de igual descripción y precio unitario, sin
matrícula ni código de precio...") para que quede confirmable, a diferencia
de la fusión por matrícula (señal más fuerte) que no lo anota.

### 2. Las 2 líneas con `descripcion = ''`: expediente mal atribuido, causa real distinta

El expediente correcto es **`6.20/28510.0136`** (ANEJO_3, hilo de contacto),
no `6.23/28510.0051` como decía la redacción original de este documento —
verificado contra la base de datos antes de tocar nada.

Causa real, confirmada abriendo el PDF: la fila de la matrícula `740540009`
envuelve su descripción en **varias filas visuales** ("HILO DE CONTACTO DE"
/ "SECCIÓN CIRCULAR DE" / "120 MM2 DE" / "ALEACIÓN COBRE-" / "MAGNESIO 0,5
CON" / "RANURA TIPO A"), y `pdfplumber` intercala además una columna en
blanco de más entre la matrícula y la descripción en la primera fila — la
celda de descripción sale vacía y el texto real cae en la columna
siguiente. `_recuperar_descripcion_columna_fantasma` (la función que ya
resuelve exactamente este desplazamiento) tenía un guard que exigía
`matricula is None` para intentarlo, asumiendo que el fenómeno solo ocurre
en huérfanas (partida alzada) — falso: la función no toca en absoluto la
columna de matrícula, así que la ausencia de matrícula nunca fue una
condición necesaria, solo una suposición no verificada.

**Arreglo**, dos partes:

1. `_construir_campos` intenta la recuperación de columna fantasma tenga o
   no matrícula la fila (se quita la condición `matricula is None`).
2. `construir_lineas_desde_tabla` (que sí ve la tabla completa, a
   diferencia de `construir_linea_catalogo`) encadena las filas de
   continuación siguientes — mismo mecanismo que `_combinar_filas_cabecera`
   ya usa para la cabecera — hasta la primera fila que vuelve a traer un
   dato real. La matrícula `740540009` recupera ahora su descripción
   completa, no solo el primer fragmento.

### 3. Comprobación permanente: sin descripción y sin matrícula, fuera del catálogo

`construir_linea_catalogo`: una línea sin descripción **y** sin matrícula no
identifica ningún material. Si el resto de la fila (fragmento de origen)
tiene contenido real, se conserva marcada para revisión humana; si la fila
está genuinamente en blanco, se descarta como cualquier otro relleno de
tabla — nunca entra al catálogo en silencio con una celda vacía sin
explicación.

### 4. Efecto secundario real, no una regresión: 268 huérfanas nuevas por "banda vacía"

Al reprocesar el corpus completo para aplicar los dos arreglos de arriba
(obligatorio: `VERSION_LOGICA_EXTRACCION` sube a `"2026-09-06.3"`), 5
expedientes multi-lote (`6.24/28510.0130`, `6.24/28510.0203`,
`6.25/28510.0019`, `6.25/28510.0027`, `6.25/28510.0028`) pasaron de 933 a
1.201 líneas — **+268, todas huérfanas nuevas** (`lote_id IS NULL`,
`pendiente_revision`, motivo "banda vacía: posible continuación de tabla
partida entre páginas, sin inferir").

**No es un mecanismo nuevo ni una regresión de este bloque**: es el mismo
"banda vacía" ya conocido y deliberadamente sin resolver
(`docs/decisiones.md` sección 31, "investigada, NO implementada — el resto
arriesga atribución cruzada entre tablas distintas"), que hasta esta mañana
nunca se había disparado para estos 5 expedientes. La causa es una sesión
**anterior y no relacionada**, la misma mañana de hoy (`docs/auditoria-huerfanos-y-autorreferencia.md`,
commit `828e2bc`): `_detectar_numero_lotes_pcsp` se amplió para reconocer
también un "Documento de Pliegos" como fuente de "Nº de Lotes" — estos 5
expedientes tienen ese documento, así que hoy, por primera vez, se
clasifican como multi-lote. Sus tablas de referencia ambiguas, que antes se
resolvían como una sola fila por código, ahora generan una fila huérfana por
cada banda ambigua de página — el mecanismo de "banda vacía" es el mismo de
siempre, simplemente nunca se había ejercitado para estos 5 expedientes
hasta el primer reproceso completo posterior a ese cambio (este mismo).

**Verificado, no solo asumido**: el resto del corpus (~38 expedientes) pasó
de 1.835 a 1.806 líneas (**-29**, coherente con el arreglo de los puntos 1-2
de arriba: menos duplicados, alguna línea más con descripción recuperada).
El total de la base de datos, 2.768 → 3.007 (+239), es exactamente
268 (banda vacía, expedientes no relacionados) − 29 (arreglo de este
bloque).

**Decisión del cliente (2026-09-06): dejarlas pendientes de revisión**, sin
intentar fundirlas en esta sesión — mismo criterio que ya regía para el
resto de huérfanas "banda vacía": el riesgo de atribución cruzada entre
lotes distintos es real, y no afectan al Excel entregado (huérfanas
excluidas por defecto). Sesión aparte, dedicada, si se decide abordar
`app.extraccion.lote_tabla` en algún momento.

### 5. Unificación del árbol de construcción

Encontrado de pasada, investigando por qué el reproceso tardaba en
reflejar el código nuevo: `/home/lucas/adif` (WSL, fuera de `git`) había
reaparecido como fuente real de los contenedores (`docker inspect
--format '{{json .Config.Labels}}'` →
`com.docker.compose.project.working_dir`), pese a haberse borrado ya una
vez por este mismo motivo (`docs/decisiones.md` sección 28,
`docs/hallazgos-extraccion.md` "Clon viejo en WSL, borrado"). Segunda vez
que pasa, sin que ninguna sesión lo dejara escrito la primera.

Verificado antes de tocar nada: comparado archivo a archivo contra el
commit `HEAD` real (con `git stash` para dejar el repositorio en el estado
exacto del último commit), **todo el código de aplicación de los últimos 3
commits coincidía exactamente** entre las dos copias — solo `CONTEXTO.md`,
`README.md` y un fichero de `docs/` estaban desactualizados en la copia.
**Ningún código llegó a correr sin estar en `git`.**

Medido el motivo habitual para mantener una copia nativa de WSL (velocidad
de build contra `/mnt/c/...`, penalizada por el protocolo 9p): construir
desde `/mnt/c/dev/ADIF` tardó 3,5 s (capa de Docker ya cacheada; los pasos
caros del `Dockerfile`, `pip install`/`playwright install`, no dependen de
la ruta de origen, solo del contenido de `requirements.txt`) — sin
diferencia medible que justifique una segunda copia.

**Resuelto**: contenedores reconstruidos y verificados por hash
(`md5sum` dentro del contenedor coincide con el fichero del repositorio) y
con la suite completa en verde (339 tests) sirviendo desde
`/mnt/c/dev/ADIF`. `/home/lucas/adif` borrado. Regla explícita añadida en
`CONTEXTO.md` (invariante 11): fuente única de verdad = el repositorio
versionado; si algún día hace falta una ruta nativa de Linux por
rendimiento, la única alternativa permitida es un `git worktree` del mismo
repositorio, nunca una copia de ficheros suelta.

### 6. Verificación final

| Concepto | Valor |
|---|---|
| Líneas en base de datos | 3.007 (2.768 antes del reproceso de este bloque) |
| Líneas en "Materiales" (hoja entregada) | 1.899 |
| Líneas pendientes de revisión (hoja "Resumen") | 1.108 (797 banda vacía + 183 sin cabecera + 128 lote no registrado) |
| Grupos de duplicados del mecanismo de este bloque restantes | 0 (26 grupos / 55 filas antes del arreglo) |
| Líneas con `descripcion = ''` restantes | 0 (2 antes del arreglo) |
| Líneas sin descripción y sin matrícula en el catálogo | 0 (comprobación permanente activa) |
| Descripción del material: relleno en "Materiales" | 100,0% (1.899/1.899) |
| Cantidad / Precio unitario / Precio adjudicado / Baja: tipos de celda | Solo `int`/`float`/vacío — cero texto mixto, verificado columna a columna |
| Duplicados visibles en "Materiales" (mismo proyecto+lote+matrícula+descripción+precio) | 0 |
| Huérfanas nuevas por "banda vacía" (efecto secundario, no regresión, ver punto 4) | +268, en 5 expedientes, pendientes de revisión por decisión del cliente |

Suite completa: **339 tests pasan** (332 antes de este bloque + 7 nuevos:
recuperación de descripción de columna fantasma con matrícula presente,
encadenado de fragmentos de descripción envuelta, descarte/revisión de
líneas sin descripción ni matrícula, y fusión por firma sin matrícula
dentro de un lote y entre documentos distintos).

## Bloque 3: bajas cero, cobertura de matriz, atípicos de precio y hoja Resumen en lenguaje llano (sesión 2026-09-06, segunda continuación)

Lucas verificó el Excel entregado (1.899 filas, 13 columnas, 2 hojas: sin
duplicados, sin marcadores de texto, columnas numéricas limpias,
descripción al 100%) y pidió comprobar cuatro puntos antes de cerrar.
Ninguno resultó ser un fallo de extracción; los tres primeros se
verificaron contra la base de datos real sin tocar código, y el cuarto sí
cambió `app/exportacion.py`.

### 1. Las 8 bajas con valor 0 son reales, no un valor por defecto

`trazas_origen` guarda el fragmento de texto exacto de cada baja
declarada (`app.extraccion.orquestador._traza`, campo `baja_declarada`).
Los 8 lotes con `baja_lote = 0` (`6.24/28510.0130` lotes 4-6,
`6.24/28510.0094` lotes 1-3, `6.25/28510.0028` lotes 6-7) tienen su
fragmento real anclado a documento y página:

- "baja económica del 0,00 % a todos a todos los precios unitarios"
  (documentos 104 y 132 -- el "a todos a todos" duplicado es una errata
  real del propio documento, no un artefacto de la extracción: aparece
  igual en dos documentos de expedientes distintos, consistente con una
  plantilla compartida)
- "baja del 0,00% aplicable al conjunto de precios unitarios"
  (documento 181)

El literal "0,00%" está en el propio PDF. `app.extraccion.baja.
extraer_baja_declarada` devuelve `None` (nunca 0) cuando no encuentra la
frase (ver docstring del módulo); el 0 solo aparece cuando el documento la
declara textualmente. No hace falta ningún arreglo.

### 2. Código matriz: re-confirmado con el fichero de códigos restaurado

Repetida la comprobación de la sección 4 de arriba, ahora con `Códigos de
proyecto.xlsx` ya restaurado en el árbol de despliegue. Mismo resultado:
de 58 expedientes, 8 tienen `codigo_matriz` real, y las 8 matrices
referenciadas (`2.18/04703.0019/0021/0022/0024/0025`,
`2.24/04110.0035/0036/0037`) existen como expedientes propios en base de
datos pero siguen en estado `sin_publicar` -- 0 lotes, 0 líneas, nada que
heredar (`app.extraccion.herencia_matriz`). El cruce de códigos en sí
funciona (48 de 58 expedientes cruzados); la columna vacía al 100% en
"Materiales" es consecuencia de que esos 8 expedientes no aportan ninguna
fila al catálogo, no de un fallo de cruce. La explicación del bloque 1
seguía siendo válida con el sistema ya arreglado.

### 3. Atípicos de precio: verificados, ninguno es un error de escala

- **Máximo, 1.020.000 €** (`6.24/28510.0203` lote 2): "Partida alzada a
  justificar para imprevistos", código `PN10`. Partida alzada legítima
  (CONTEXTO.md sección 2), no un error de parseo -- el mismo expediente
  repite la partida en varios lotes con importes de 780.000 a 1.020.000 €,
  coherentes entre sí.
- **Mínimo, 0,142 €** (`6.23/28510.0129` lote 2): "T x km de balasto
  transportado a punto de carga diferente al ofertado", cantidad
  600.000 t·km. Precio por unidad de una línea de transporte a granel --
  el precio bajo es correcto porque la unidad es muy pequeña (euros por
  tonelada-kilómetro), no euros por unidad de material.

Comparando cada línea con precio contra la mediana de precio de su propio
expediente (umbral: más de 50 veces la mediana, o menos de 1/50):
**114 líneas atípicas en 15 expedientes**, de las cuales:

- **50** son "partida alzada" (imprevistos) -- por naturaleza un importe
  global, no un precio unitario comparable al resto del lote.
- **10** son componentes caros dentro de un lote dominado por tornillería
  barata (bobinas de carga para cable de comunicaciones, cupones de
  carril, chapa de acero) -- precios físicamente razonables para el
  material descrito.
- **54** son piezas de fijación baratas (arandelas, tornillos, pasadores)
  dentro de un lote dominado por carril o material caro -- igual de
  razonables en el sentido contrario.

Ninguna de las 114 muestra el patrón de un error de escala (p. ej. un cero
de más o de menos frente a una línea gemela del mismo material). No se ha
tocado código: son atípicos por diseño del catálogo (lotes con material
heterogéneo, de tornillería a raíles), no fallos de extracción.

### 4. Hoja "Resumen" traducida a lenguaje llano

`app/exportacion.py`: los tres motivos de exclusión (antes texto técnico
interno, p. ej. "banda vacía: posible continuación de tabla partida entre
páginas") ahora se muestran como una explicación en dos partes -- qué ha
pasado y qué haría falta para resolverlo -- en una tabla de tres columnas
("Qué ha pasado" / "Líneas" / "Qué haría falta para resolverlo"). Ejemplo
real:

> "Esta tabla de precios parece continuar de una página a la siguiente
> del documento, y el sistema no ha podido confirmar a qué lote pertenece
> la parte que sigue." — "Que alguien abra el documento original y
> compruebe a qué lote corresponde esa parte de la tabla."

Añadida además una nota fija explicando la columna "Código del material"
(vacía en el 91,6% de las líneas de catálogo en base de datos hoy, 3.007
líneas con 253 códigos rellenos): el sistema solo la rellena cuando la
primera palabra de la descripción casa contra un vocabulario todavía
corto (`app.extraccion.codigo_material.VOCABULARIO_CODIGO_MATERIAL`, 11
palabras); ampliarlo con el modelo cuando no casa nada está
deliberadamente fuera de alcance (CONTEXTO.md sección 6, sin ningún caso
real sin casar en el corpus de prueba) -- se deja explícito en el Excel
para que una columna casi vacía no se lea como un fallo del entregable.

Tests: `tests/test_exportacion.py` (categorías con explicación no vacía y
sin jerga interna, contenido de la hoja Resumen) y
`tests/test_api_catalogo.py` (test de extremo a extremo actualizado al
nuevo formato de tres columnas).

### Verificación final

| Concepto | Valor |
|---|---|
| Líneas en "Materiales" | 1.899 (sin cambio -- este bloque no toca la generación de líneas) |
| Bajas distintas | 36, de las cuales 1 valor es 0 (8 lotes) -- verificadas contra el fragmento real del PDF vía `trazas_origen` |
| Código matriz en "Materiales" | 0/1.899 (100% vacío), re-confirmado: los 8 expedientes con matriz real no aportan líneas porque su matriz sigue `sin_publicar` |
| Precio unitario | máximo 1.020.000 €, mínimo 0,142 €, ambos verificados contra la línea de origen |
| Líneas atípicas (>50x o <1/50 de la mediana de su propio expediente) | 114, en 15 expedientes (50 partidas alzadas, 10 caras por tipo de material, 54 baratas por tipo de material) |
| Suite completa | 346 tests pasan (339 antes de este bloque + 7 nuevos de la hoja Resumen) |

Nada de lo verificado en este bloque requirió tocar la lógica de
extracción o de cálculo -- solo la hoja "Resumen" cambió de código.

## Bloque 4: la fila que fusionaba dos líneas de precio y la fila fantasma de descripción (sesión 2026-09-06, tercera continuación; cerrado el 2026-09-07)

Origen: revisando el catálogo de `6.23/28510.0051` aparecían líneas con la
baja del lote heredada pero **sin precio unitario ninguno**, es decir sin
nada de lo que derivar el precio adjudicado — indistinguibles en el Excel de
una línea genuinamente pendiente de revisión. Rastreadas hasta el documento
original (`6.23_28510.0051_ANEJO_1.pdf` p.57 y p.59, y la misma tabla
repetida en `6.23_28510.0051_CONTRATO_2.pdf` p.153 y p.155), resultaron ser
**dos defectos distintos de la misma tabla**, más un tercero que solo
apareció al verificar el arreglo contra la base de datos real.

### 1. La causa física: un desfase de una línea entre la columna de descripción y el resto

En esa tabla la primera línea de cada descripción envuelta cae, visualmente,
dentro de la banda de la fila **anterior**. `pdfplumber` corta las filas por
esa banda, así que el desfase produce dos artefactos opuestos:

- **Fila fantasma**: un trozo de descripción se emite como fila propia, con
  todas las demás columnas en blanco. No es un material nuevo — el material
  real, con su código, su unidad y su precio, ya se cuenta en la fila vecina.
- **Fila fusionada**: dos filas de datos reales y consecutivas no difieren lo
  bastante en altura y se funden en **una sola** fila extraída. El código de
  precio y el precio unitario traen entonces dos valores reales dentro de la
  misma celda (`"P-0090\nP-0091"`, `"29.240,23 €\n38.012,29 €"`).

Antes del arreglo, la fila fantasma se guardaba como línea de catálogo (baja
heredada, ningún precio) y la fila fusionada dejaba un código imposible
(`"P-0090P-0091"`) que no casaba con ningún formato conocido, con el precio
sin interpretar: los dos síntomas que veía el cliente.

### 2. Los dos arreglos en `app/catalogo.py`

- `construir_linea_catalogo` **descarta** la fila fantasma (solo descripción,
  sin código, matrícula, cantidad, unidad ni precio), igual que ya descartaba
  un pie de tabla o una fila de relleno.
- `_dividir_fila_multiple` **separa** la fila fusionada en las N líneas
  reales. Solo actúa cuando el código de precio Y el precio unitario se
  dividen en el mismo número N≥2 de líneas no vacías **y** cada valor por
  separado ya tiene forma de código/precio válida; la unidad de medida, si la
  cabecera la declara, debe dividirse en N o venir vacía. Nunca a ciegas: dos
  valores que no casen como códigos y precios reales dejan la fila como
  estaba, camino normal y a revisión como hasta ahora.

La descripción **nunca se reparte** entre las N líneas: el desfase de una
línea hace que sus fragmentos no se correspondan 1:1 con el resto de columnas
(CONTEXTO.md sección 8, nunca inventar un reparto que no se pueda verificar).
Cada línea resultante se queda con el bloque entero y se marca con
`_MOTIVO_FILA_FUSIONADA` para que un humano confirme la descripción contra el
documento, aunque el precio (y el precio adjudicado derivado) ya sea correcto.

### 3. El tercer defecto, encontrado verificando contra la base de datos real

Separar la fila **no bastaba**. Las dos líneas que salen de una fila fusionada
comparten descripción (el bloque entero, que a propósito no se reparte), no
tienen matrícula, y pueden tener el mismo precio: exactamente la firma de
`_firma_material` — `(matrícula, descripción, precio unitario)` — que
`_combinar_por_clave` y `guardar_lineas_catalogo` usan para fundir un material
repetido en dos tablas. Resultado real medido en base de datos: de la fila
`P-0058`/`P-0059` (306.351,49 € los dos, mismo precio por coincidencia) se
guardaba **una sola línea**, con `clave_linea = "P-0058"` y
`codigo_precio = "P-0059"`, y el material `P-0058` desaparecía del catálogo
entero. El mismo fallo que el arreglo venía a corregir, un paso más allá y con
peor pinta: la línea superviviente parece correcta.

Arreglo: `_firma_material` **no da firma** a una línea recuperada de una fila
fusionada. Su descripción es un bloque compartido, no una identidad. Cada una
se guarda con su propio `codigo_precio` como clave. Si alguna resultara ser de
verdad un duplicado de otra tabla, quedará como línea repetida a revisar —
verificable por un humano, y muy preferible a perder un material real sin
dejar rastro. Las tres pruebas nuevas de este punto fallan las tres con el
arreglo retirado (comprobado ejecutándolas contra una copia del árbol sin el
descarte) y pasan con él.

### Verificación final, contra el corpus real

Reprocesado el expediente (`POST /expedientes/18/extraer`, trabajo 1068,
`completado` sin error) contra el stack real:

| Concepto | Valor |
|---|---|
| Filas fusionadas separadas | 3 (`P-0058`/`P-0059`, `P-0090`/`P-0091`, `P-0099`/`P-0100`), 6 líneas de catálogo, todas marcadas para revisión |
| Material recuperado por el arreglo del punto 3 | `P-0058`, que había desaparecido del catálogo |
| Líneas fantasma en todo el corpus (solo descripción, sin ningún otro dato) | 0 |
| Líneas con baja de lote y sin precio unitario, en todo el corpus | 0 |
| Líneas con `clave_linea` distinta de su `codigo_precio` dentro de un lote | 0 |
| Líneas de catálogo del expediente / del corpus | 1.069 / 3.001 |
| Suite completa | 372 tests pasan (369 antes del punto 3 + 3 nuevos) |

Los precios adjudicados de las líneas recuperadas se derivan ya con la baja
del lote (0,2531): `P-0090` 29.240,23 € → 21.839,5278 €, `P-0091` 38.012,29 €
→ 28.391,3794 €, `P-0058` y `P-0059` 306.351,49 € → 228.813,9279 €.

## Bloque 5: cantidad con forma de año, y unidad de medida visible en todas partes (sesión 2026-09-07)

Origen: el cliente detectó que el campo `Cantidad` del catálogo a veces
contiene lo que parece un año, no una cantidad de material.

### 1. Medición inicial

**73 líneas** con `cantidad` entre 1900 y 2100, en 4 expedientes (más 1
línea adicional en 1872, fuera de ese rango pero igual de sospechosa):

| Expediente | Líneas | Rango | Documento |
|---|---|---|---|
| `6.20/28510.0054` | 34 (33 en 1996-2005 + 1 en 1872) | traviesas | `ANEJO_8.pdf` p.10 |
| `6.25/28510.0028` | 35, todas en 2000 | balasto | `ANEJO_1.pdf` |
| `6.24/28510.0064` | 4, todas en 2000 | cable | `CONTRATO_1.pdf` |
| `6.24/28510.0203` | 1, en 2000 | traviesa | `CONTRATO_1.pdf` |

### 2. Qué había realmente en la celda (verificado con `pdfplumber` contra los 4 PDF reales)

- **`6.20/28510.0054`**: la tabla real tiene 6 columnas -- `Matricula |
  Designación | E.T. | (sin cabecera) | PRECIO (€) | CANTIDAD DE
  REFERENCIA`. La celda "CANTIDAD DE REFERENCIA" trae literalmente esos
  años (1997, 2004, 2000..., y un "1872"): es el dato real del documento.
  El problema real está en la celda de al lado: "E.T." (Especificación
  Técnica, una referencia normativa como `03.360.571.8`) se guardaba como
  si fuera la unidad de medida.
- **`6.24/28510.0064`** (cable) y **`6.25/28510.0028`** (balasto):
  confirmado contra el documento -- cantidades reales y plausibles (2000
  metros de cable, 2000 toneladas de balasto), coincidencia numérica con
  un año, no un fallo. Falsos positivos del filtro, descartados como bug.

### 3. Causa: mapeo de "unidad_medida", no de "cantidad" -- y una segunda variante encontrada al arreglarlo

No es una columna fantasma desplazando "Cantidad". Es una mala asignación
de **"unidad_medida"**, y la hizo **el modelo (LLM), no las reglas
deterministas** -- confirmado en `cache_mapeo_cabecera`: 5 firmas de
cabecera distintas (ids 71-75), las 5 con `origen="modelo"`, las 5
aplicadas solo a `6.20/28510.0054`. "Cantidad" en sí estaba bien mapeada
(apunta a la columna que el propio documento llama "CANTIDAD DE
REFERENCIA"); el valor con forma de año es ambiguo en el propio PDF de
ADIF, no un error de nuestra extracción.

Verificando el fix contra el corpus real (no solo la muestra inicial de 4
expedientes) apareció una **segunda variante del mismo defecto**, en un
documento completamente distinto: `6.20/28510.0094` (candado/llave,
`ANEJO` p.4). La tabla real es `MATRICULA | DENOMINACION | (blank) |
CANTIDADES [ESTIMADAS] | (blank) | PRECIO`, y el modelo mapeó
`unidad_medida` a la columna en blanco justo después de la descripción
(`cache_mapeo_cabecera` id 77, `origen="modelo"`) -- que en realidad trae
la cantidad ("956", "102") desplazada por una columna fantasma, el mismo
fenómeno de desfase que ya resuelven `_recuperar_cantidad_columna_fantasma`
y compañía, aquí aterrizando en `unidad_medida` porque fue el modelo, no
una regla de recuperación, quien decidió el mapeo. Un vistazo a la
distribución completa de valores de `unidad_medida` en todo el corpus
(`select unidad_medida, count(*) ... group by 1`) fue lo que hizo aparecer
este segundo caso -- dos valores sueltos, "956" y "102", con pinta de
número puro entre docenas de unidades reales.

Ambas variantes comparten una firma verificable: **ninguna unidad de
medida real del corpus es nunca solo dígitos y puntos** (ud, UD., m, M, t,
kg, PA, dm3, m³... siempre llevan alguna letra), mientras que tanto una
referencia normativa como un valor de cantidad desplazado sí lo son.

### 4. El arreglo

En `engine/app/catalogo.py`, `_construir_campos`:

- Nueva validación estructural: si el valor extraído de `unidad_medida`
  tiene forma de referencia normativa o de valor puramente numérico
  (regex `^[\d.]+$`), se descarta (pasa a `null`) y se marca para
  revisión. Cubre las dos variantes encontradas y cualquier otra no vista
  todavía, sin depender solo de la caché -- la forma del valor importa más
  que la firma exacta.
- Nueva comprobación de `cantidad` implausible: cero, o forma de año
  (1900-2100, sin parte decimal). Nunca inventa ni descarta el dato -- lo
  guarda igual y lo marca en `motivo_revision` para confirmación humana.
  Deliberadamente **no** se automatizó un chequeo de "N veces la mediana
  del expediente" para cantidad: investigado contra el corpus real,
  produce falsos positivos legítimos -- `6.24/28510.0130` (pequeño
  material de sujeción de vía, comprado por decenas de miles de unidades)
  y `6.25/28510.0028` (tonelada-kilómetro de balasto frente a toneladas)
  dan cocientes de más de 50x que son reales, mismo hallazgo que ya cerró
  esto para atípicos de precio en el bloque 3.
- Las 5 entradas de caché de la primera variante (ids 71-75) y la 1 de la
  segunda (id 77) corregidas directamente (`unidad_medida: null`).
- Las 36 líneas ya guardadas con el valor malo (34 + 2) corregidas en base
  de datos: reprocesar el expediente por sí solo no bastaba, porque
  `guardar_lineas_catalogo` nunca deja que un `None` entrante pise un
  valor ya conocido (la regla correcta para el caso contrario: no perder
  un dato bueno cuando una segunda tabla trae menos columnas) -- así que
  un `unidad_medida` malo, ya guardado, sobrevive a un reproceso sin
  tocarlo a mano. La misma corrección, en cambio, sí dejó que
  `_recuperar_cantidad_columna_fantasma` (ya existente, no nuevo)
  recuperara sola "956"/"102" como cantidad real en cuanto el mapeo dejó
  de reclamar esa columna para `unidad_medida`.
- 8 tests nuevos en `engine/tests/test_catalogo.py`, 70 pasan en ese
  fichero, 380 en la suite completa.

### 5. Unidad de medida, visible en las cuatro pantallas y en el Excel

`unidad_medida` se guarda desde el principio del proyecto (etapa 6 de la
cascada) pero no aparecía en ningún sitio visible -- sin ella, una
`Cantidad` de 2000 o un `Precio unitario` de 0,142 no significan nada por
sí solos.

**Medición previa** (antes de tocar nada, condición del cliente): 95,8%
de las líneas del catálogo ya traían `unidad_medida` -- no una columna
casi vacía, seguía adelante. Tras las correcciones del punto 4 (36
valores malos limpiados), la cifra real baja ligeramente a **94,6%**
(2.839/3.001): el punto de partida incluía 36 unidades "rellenas" pero
incorrectas.

**Verificación de plausibilidad** contra 6 expedientes distintos, con
`pdfplumber` sobre el documento real (no solo contra la base de datos):
traviesas (`6.20/28510.0054`, sin unidad tras el arreglo -- la tabla real
no tiene columna de unidad), cable (`6.24/28510.0064`, "M"), balasto
(`6.25/28510.0028`, "t"), candado/llave (`6.20/28510.0094`, sin unidad
tras el arreglo -- misma causa), partida alzada (`6.24/28510.0088`, "PA"),
aceite de engrase (`6.25/28510.0019`, "KG") -- las seis coinciden
exactamente con el documento original.

**Dónde se añadió:**

- `web/app/catalogo/CatalogoPanel.tsx`: columna "Unidad" en la tabla
  (junto a Cantidad), y "Cantidad" (con su unidad) más un sufijo "(por
  unidad)" en la sección de precio y baja del panel de trazabilidad --
  antes ese panel no mostraba la cantidad en absoluto.
- `web/app/revision/RevisionPanel.tsx`: columna "Unidad" junto a Precio
  unitario en la tabla de líneas de la cola de revisión.
- `engine/app/exportacion.py`: `Unidad de medida` como decimocuarta
  columna del Excel, al final de todo, después de Precio adjudicado y
  Baja del lote -- las once columnas originales del formato del cliente
  no se tocan ni de posición ni de orden.
- Mismo criterio de celda vacía que el resto de columnas en las cuatro
  pantallas (no aplica para partida alzada sin unidad propia, no consta
  en cualquier otro caso); en el Excel, celda en blanco sin marcador de
  texto -- la misma convención ya establecida para todas las columnas de
  texto de este entregable (`app/exportacion.py`, docstring del módulo),
  para no romper filtros/ordenación en Excel.

### Verificación final

| Concepto | Valor |
|---|---|
| Líneas con `unidad_medida` implausible (referencia normativa o numérica pura) tras el arreglo | 0 |
| Líneas corregidas en base de datos | 36 (34 traviesas + 2 candado/llave) |
| Firmas de cabecera de caché corregidas | 6 (ids 71-75, 77) |
| `unidad_medida` en todo el catálogo | 2.839/3.001 (94,6%) |
| `unidad_medida` en el Excel entregado ("Materiales") | 1.748/1.893 (92,3%) |
| Columnas del Excel | 14 (11 originales + Precio adjudicado + Baja del lote + Unidad de medida, en ese orden) |
| Suite completa | 380 tests pasan (372 antes de este bloque + 8 nuevos) |
