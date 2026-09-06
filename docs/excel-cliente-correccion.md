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
CLAUDE.md) — solo faltaban en el Excel. Añadidas **al final**, sin mover
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
commits coincidía exactamente** entre las dos copias — solo `CLAUDE.md`,
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
`CLAUDE.md` (invariante 11): fuente única de verdad = el repositorio
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
