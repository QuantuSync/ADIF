# Sesión 2026-09-18 (cuarta parte) — Barrido de los no publicados, cifras en glifos y los lotes que declara el propio cuadro de precios

Tres encargos y una comprobación. Continúa
`docs/sesion-2026-09-18-estados-adif-y-acuerdos-marco.md`.

---

## 0 — Lo que devolvió la Plataforma para los 4 acuerdos marco (bloque 6 de la parte anterior)

Pedido literal. Los seis expedientes se buscaron hoy, uno a uno, por número de
expediente:

| Expediente | Trabajo | Hora | Qué devolvió la Plataforma |
|---|---:|---|---|
| `4.23/04110.0256` | 21573 | 11:59 | **encontrado** — `encontrado_como: 4.23/04110.0256`, 6 enlaces, 6 documentos nuevos (3 ANEJO, 1 PLIEGO, 1 CONTRATO, 1 ADJUDICACIÓN) |
| `4.24/04110.0187` | 21574 | 11:59 | `no encontrado en la Plataforma ni por matriz ni por expediente: 4.24/04110.0187` |
| `4.24/04110.0189` | 21575 | 11:59 | `no encontrado en la Plataforma ni por matriz ni por expediente: 4.24/04110.0189` |
| `2.24/04110.0036` | 21576 | 11:59 | `no encontrado en la Plataforma ni por matriz ni por expediente: 2.24/04110.0036` |
| `2.24/04110.0035` (matriz de `0048`) | 21585 | 12:07 | `no encontrado en la Plataforma ni por matriz ni por expediente: 2.24/04110.0035` |
| `2.24/04110.0037` (matriz de `0049`) | 21586 | 12:07 | `no encontrado en la Plataforma ni por matriz ni por expediente: 2.24/04110.0037` |

**Por qué los 49 siguen siendo 49.** El único de los seis que está publicado,
`4.23/04110.0256`, **no publica ningún cuadro de precios**: lo que trae su PCAP
(p.17-22) es el modelo de proposición económica en blanco, con las unidades
puestas y la columna "PRECIO UNITARIO" vacía, que es la que rellena el
licitador. Su Resolución de Adjudicación es solo del Lote nº5 y su Anuncio de
formalización solo del Lote 3. No hay de dónde leer un precio unitario, así
que los 5 pedidos siguen aportando 0 líneas y ninguno de los 49 se resuelve.
Detalle completo en el documento de la parte anterior, bloque 6.

---

## 1 — Barrido de los expedientes dados por no publicados

### Qué se hizo

Los **73** expedientes del 28510 que la Conciliación da hoy por no publicados
(75 menos `6.26/28510.0057` y `0083`, encontrados esta misma mañana) se
volvieron a buscar en la Plataforma, uno a uno, con el espaciado de siempre.

### Resultado

| | |
|---|---:|
| Expedientes buscados | **73** |
| **Aparecen en la Plataforma** | **0** |
| Líneas que aportan | **0** |
| Siguen sin encontrarse | **73** |

Los 73 devolvieron literalmente lo mismo: `no encontrado en la Plataforma ni
por matriz ni por expediente: <código>`. **Ninguno estaba marcado en falso**,
así que no hay ningún caso al que atribuir una causa: la marca era correcta en
los 73.

**Sobre `6.26/28510.0057` y `6.26/28510.0083`, que sí aparecieron esta mañana.**
Tampoco fueron marcas falsas, y la evidencia es del propio documento: su
anuncio declara *"Fecha de envío \[al DOUE\] 14/09/2026"* y su "Documento de
Pliegos" lleva *"Publicado en la Plataforma de Contratación del Sector Público
el **18-09-2026**"*, a las 10:11 y 10:18 — es decir, **se publicaron hoy**, dos
días después del negativo del 16/09 a las 21:21. La búsqueda de aquel día
contestó bien; lo que no existía todavía era la publicación. Lo que sí quedaba
abierto es cuánto tardaría el sistema en enterarse solo, y eso es lo que
arregla el apartado siguiente.

### La marca ya caducaba — y ahora caduca antes para lo reciente

**Corrección de la premisa del encargo, medida antes de tocar nada.** `sin_publicar`
dejó de ser definitivo en la sesión 2026-09-15: `app.mantenimiento.frescura`
(`debe_rebuscar_sin_publicar`, `sin_publicar_reintento_desde`) y
`app.mantenimiento.ciclo._reintentar_sin_publicar` ya vuelven a buscar cada
ciclo lo que toca, hasta `SIN_PUBLICAR_REINTENTOS_POR_CICLO` (50) por vuelta.
Un expediente mal marcado **no se queda fuera para siempre**. Lo que pasa es
que el plazo no había vencido para ninguno todavía: los últimos cinco ciclos lo
dicen en su propio resumen.

```
ciclo  fecha        reintentados  aplazados  en plazo
21032  09-17 10:06             0          0        95
20512  09-17 08:41             0          0        95
19992  09-17 07:51             0          0        95
19321  09-16 21:15             0          0        81
19232  09-15 10:51             0          0        81
```

Todos se confirmaron el 08/09 o el 16/09 con la versión de búsqueda vigente, y
el plazo son **14 días**: los primeros reintentos automáticos habrían caído el
22/09.

**Lo que sí faltaba, y es el caso real de hoy.** Catorce días es razonable para
un expediente de 2014 que lleva una década sin publicarse —cada búsqueda evitada
cuenta contra una Plataforma lenta y frágil (CONTEXTO.md sección 14)— pero no
para uno del año en curso: `6.26/28510.0057` se buscó el 16/09, no estaba, y el
18/09 ya estaba publicado. Con catorce días se habría encontrado solo el
**30/09, doce días tarde**.

`plazo_sin_publicar` (`app.mantenimiento.frescura`) hace ahora que el plazo
dependa del **año que va en el propio código del expediente**:

| Antigüedad del expediente | Plazo | Efecto con el ciclo semanal |
|---|---:|---|
| año en curso o el anterior (`SIN_PUBLICAR_ANIOS_RECIENTES=1`) | **3 días** (`SIN_PUBLICAR_REINTENTO_DIAS_RECIENTES`) | se vuelve a buscar **en cada ciclo** |
| más antiguo | 14 días (`SIN_PUBLICAR_REINTENTO_DIAS`) | en ciclos alternos, como hasta hoy |

El año se lee de forma estructural, por su posición en el código, nunca
buscando "algo que parezca un año" (`28510` también son cifras): `6.26/28510.0057`
→ 2026, `19/28510` → 2019, `28510/2023` y `28510Z/2018` → por detrás de la
barra. Un código que no encaje en ninguna de las dos formas conocidas **no se
adivina: se trata como viejo**, que es el comportamiento conservador.

---

## 2 — `6.26/28510.0064`: las 36 filas

### Las cifras en glifos, descodificadas y comprobadas

`app.extraccion.glifos_cid`. La regla, entera:

1. En una fuente sin tabla `ToUnicode` los diez dígitos son diez glifos
   consecutivos, así que el mapa es una traslación `cid → cid − desplazamiento`.
   El desplazamiento **no se supone**: se acota con los propios identificadores
   de la fila (todos tienen que caer en 0-9) y, con los diez dígitos presentes,
   queda **un único candidato**.
2. Se confirma con **la aritmética de la propia fila**: tiene que existir en
   ella una cantidad y un importe tales que `cantidad × precio = importe`.
3. Si la cuenta no sale —o sale con dos desplazamientos distintos— **no se
   escribe nada**: la fila se queda como estaba y va a revisión.

La única celda anclada al mapeo de cabecera es la del precio, que es la que se
guarda. La cantidad y el importe se buscan entre las demás celdas de la fila
**sin exigir que estén en su columna nominal**, porque estas tablas vienen
desplazadas por una columna fantasma (la cabecera llama CANTIDADES a la columna
4 y el "30.000" cae en la 3; `app.catalogo._recuperar_columna_fantasma` ya lo
recupera después). No es buscar "algo parecido": la prueba es la
multiplicación, y los dos valores que la sostienen se descartan — solo se
guarda el precio.

El `fragmento` sigue siendo el **texto literal del documento**, con sus
`(cid:...)`, y lleva delante la marca de lo que se hizo y la cuenta que lo
demuestra, igual que el reconocimiento óptico marca las suyas:

```
[cifras descodificadas de identificadores de glifo; el PDF no trae tabla de
caracteres. Comprobado: 27.000 × 16,2 = 437.400, que es el importe que trae la
propia fila] P-2 | T de balasto transportado... | t | 27.000 |
(cid:1005)(cid:1010),(cid:1006)... | (cid:1008)(cid:1007)(cid:1011)...
```

### Los 6 lotes, por geometría

**El mecanismo de atribución por geometría ya existía** y es exactamente el que
pedía el encargo (`app.extraccion.lote_tabla`: cada tabla tiene una franja
vertical propia, desde el fondo de la tabla anterior hasta su propio techo, y
si en esa franja aparece una única cabecera "LOTE N", la tabla es de ese lote;
nunca por proximidad ni por parecido de texto). **No llegaba a ejecutarse
nunca** en este expediente: la etapa solo entra cuando el expediente conoce más
de un lote, y `6.26/28510.0064` conocía uno —el sentinela `LOTE_UNICO`— porque
no tiene todavía ninguna adjudicación que desglose los 6 por número. Las seis
tablas caían en el mismo lote y sus filas se fundían por clave.

`_lotes_candidatos_del_cuadro` (`app.extraccion.orquestador`) le deja
intentarlo, **sin poder perder ni una fila**:

- Solo cuando el expediente declara N>1 lotes, **no** tiene ninguno
  identificado por número, no es él mismo uno de los lotes, y **su lote
  sentinela no lleva ningún dato atribuido** (ni baja, ni importe de
  licitación, ni de adjudicación). Esto último importa: partir en N un lote que
  ya lleva una baja convertiría un dato del conjunto de la licitación en un
  dato del lote 1, que es la atribución equivocada que CONTEXTO.md sección 26
  ya descartó para `6.24/28510.0088`.
- Se procesa el documento con los N lotes y **el resultado solo se acepta si el
  propio cuadro de precios atribuye TODAS sus filas a un lote y cubre los N**.
  Con una sola fila huérfana se descarta el intento entero y se procesa como
  siempre. Una huérfana se quedaría fuera del entregable, y este cambio no
  puede quitar ni una fila de lo que ya salía: esa garantía es la que hace que
  no haga falta medir expediente a expediente antes de activarlo.

El expediente lo dice en su motivo, sin jerga:

> los 6 lotes de este expediente se han identificado por las cabeceras "LOTE N"
> del propio cuadro de precios, no por un documento de adjudicación (no hay
> ninguno todavía): ANEJO_1.pdf — confirmar antes de dar por buena la
> atribución de cada precio a su lote

### Resultado: 36 filas, 30 verificadas, 6 a revisión

De 6 líneas sin precio a **36 líneas en 6 lotes**:

| Lote | Filas | Con precio | Por qué |
|---|---:|---:|---|
| 1 | 6 | **6** | descodificadas y comprobadas contra su columna TOTALES |
| 2 | 6 | **6** | ídem |
| 3 | 6 | **0** | **su tabla no publica columna de totales**: no hay con qué comprobar la descodificación, y sin comprobación no se escribe el número |
| 4 | 6 | **6** | ídem |
| 5 | 6 | **6** | ídem |
| 6 | 6 | **6** | ídem (única tabla sin columna fantasma) |
| **Total** | **36** | **30** | |

Las 6 de lote 3 llevan su motivo (*"precio unitario no interpretable: la celda
trae identificadores de glifo sin decodificar (fuente sin ToUnicode)"*) y
**salen igual en el entregable**, con la celda de precio vacía y explicada: no
se pierde ninguna fila.

### ¿Afecta a más expedientes del corpus?

Medido sobre la caché de texto de los 1.6xx documentos:

| | |
|---|---:|
| Documentos con algún `(cid:` en su texto | **230** |
| De ellos, con **cifras** en glifos (dos o más seguidos) | **178** |
| Expedientes que los referencian | **197** |
| Líneas del catálogo que hoy llevan el motivo de "precio no interpretable" por esta causa | **6, todas de `6.26/28510.0064`** |

La diferencia entre 197 y 1 es la clave: casi todas esas cifras están en
páginas que **no son cuadro de precios** (el cuerpo de un Contrato firmado de
100 páginas, sobre todo), y la cascada solo abre como tabla las páginas
candidatas. Solo llegan al catálogo las que caen dentro de un cuadro de
precios.

**El arreglo está armado para todo el corpus, pero solo actúa cuando cada
expediente se vuelve a extraer**, y en esta sesión solo se ha reextraído
`6.26/28510.0064`. Los 196 expedientes restantes son el techo de lo que podría
aparecer en un reproceso completo, no una previsión: hasta que no se
reprocesen, no se sabe en cuántos hay de verdad una cifra de cuadro de precios
en glifos.

---

## 3 — `6.25/28510.0221`

El único de los 10 desfases donde el estado de ADIF (*Finalizado*) va por
delante del nuestro (*Pendiente de adjudicación*, del boletín de 07/2026).

**No hay ningún documento publicado que no tengamos.** Buscado y descargado de
nuevo hoy:

```
{"documentos": {"ANEJO": 4, "PLIEGO": 1, "CONTRATO": 0, "ADJUDICACION": 1},
 "expediente": "6.25/28510.0221", "enlaces_nuevos": 0,
 "encontrado_como": "6.25/28510.0221", "documentos_nuevos": 0}
```

Seis documentos, los seis ya los teníamos desde el 15/09. **Y entre ellos está
su Resolución de Adjudicación**, que leemos bien:

- *"SUMINISTRO DE TRAVIESAS DE MADERA PARA LOS ALMACENES DE ADIF. 2 LOTES.
  EXPEDIENTE PRINCIPAL Nº 6.25/28510.0221. • **LOTE 2**. TRAVIESAS DE MADERAS
  TROPICALES Y ELEMENTOS AUXILIARES. **EXPEDIENTE Nº 6.26/28510.0003**."*
- Adjudicataria **MADERAS TORREIRA SL** (NIF B36173466), 3.046.032,00 € (base
  imponible), **baja del 5,51 %** aplicable al conjunto de precios unitarios.
  Comité de contratación del 2 de junio de 2026.

**Entonces, ¿por qué el desfase?** Porque la columna "Estado que consta
publicado en la Plataforma" de la hoja sale de la **sindicación mensual**, y el
último boletín que ha listado este expediente es el de **07/2026**, con el
expediente todavía en "Pendiente de adjudicación". La adjudicación se publicó
después y ningún boletín ingerido la ha vuelto a listar — un boletín refleja un
evento de ese mes, no "sigue vigente" (CONTEXTO.md sección 16). El estado de
ADIF ("Finalizado") y el documento que tenemos coinciden; el que va por detrás
es el dato de la sindicación.

**Hallazgo de paso, que merece mirarse.** El expediente del **lote 2** de esta
licitación es `6.26/28510.0003`, y ese código está hoy en la lista de los 73
dados por no publicados — buscado esta misma tarde, sin resultado. Es
coherente: sus documentos se publican bajo el expediente principal, no bajo el
suyo. Pero significa que **un expediente puede estar "no publicado" por su
propio número y aun así tener su adjudicación publicada dentro de la ficha de
otro**. No se toca nada hoy; queda anotado.

**Lo que esto dice de la columna de estado**, y es lo único accionable: cuando
el sistema ya tiene descargada de la Plataforma una Resolución de Adjudicación
de un expediente, sabe más que el último boletín de sindicación sobre él.
Hacer que la columna use ese documento cuando es más reciente es un cambio
pequeño y bien fundado (CONTEXTO.md sección 12: "el documento firmado manda"),
pero cambia una columna que el cliente ya tiene delante: **queda propuesto, sin
aplicar**.

---

## Cierre

### Pruebas

**1.078 pasan** (1.046 al cerrar la parte anterior, **+32**). Ninguna saltada.
Las nuevas: 13 de `glifos_cid` (con las cadenas reales del documento, incluida
la que **no** debe descodificarse por no tener importe que la confirme), 7 del
criterio de los lotes del cuadro (`_lotes_candidatos_del_cuadro`,
`_el_cuadro_declara_todos_los_lotes`, con el caso de la fila huérfana y el del
lote que ya lleva datos), 9 del plazo por antigüedad y el año del código, y 3
más.

### Excel

```
C:\dev\ADIF\catalogo_adif_2026-09-18-glifos-y-lotes.xlsx
```

### Comparación con `catalogo_adif_2026-09-18-estados-adif.xlsx`

| | Antes | Ahora |
|---|---:|---:|
| Filas de "Materiales" | 18.293 | **18.323** (+30) |
| Expedientes con filas | 362 | 362 |
| Materiales distintos (expediente + matrícula + descripción) | 17.323 | 17.323 |
| Filas de "Conciliación" | 518 | 518 |

**0 expedientes pierden filas, 0 materiales desaparecen.** Una única diferencia,
y es la del encargo:

| Expediente | Antes | Ahora | Por qué |
|---|---:|---:|---|
| `6.26/28510.0064` | 6 | **36** | los 6 conceptos de precio × sus 6 lotes, ya separados |

Los materiales distintos no suben porque las 30 filas nuevas son los mismos
seis materiales repetidos en otros cinco lotes: misma matrícula y misma
descripción, distinto lote y distinto precio.

**El arreglo de los lotes del cuadro queda armado para todo el corpus pero solo
actúa al reextraer**, y en esta sesión solo se ha reextraído
`6.26/28510.0064`. Hay **91 expedientes** que cumplen la primera condición
(declaran más de un lote y no tienen ninguno identificado por número); cuántos
de ellos pasarían además la comprobación dura —que su cuadro de precios
atribuya todas sus filas y cubra los N— solo se sabrá cuando se reprocesen. Por
construcción, los que no la pasen se quedan exactamente como están.

### Cuadre de "Conciliación" con "Materiales"

```
suma de la columna de líneas de "Conciliación": 18.323
filas de la hoja "Materiales":                  18.323
```

0 expedientes sin Situación.

### Auditoría

**1 error, 6 avisos.** El error es `lineas_cambian_sin_cambiar_documentos` sobre
**`6.26/28510.0064`** (6 → 36 líneas sin que cambiaran sus documentos): real y
explicado, las 30 nuevas vienen de los dos arreglos de esta parte, no de leer
nada nuevo. La regla que lo marca ("cualquier subida es error, sin excepción")
**no se toca**, por el mismo motivo de siempre: es la que impide que la
atribución automática se convierta en una puerta de atrás. El error de la parte
anterior (`6.25/28510.0081`) ya no aparece, porque la auditoría compara contra
la ejecución anterior y ese expediente lleva dos estable en 6 líneas.

Los seis avisos son los de siempre: 11 grupos de material repetido con códigos
de precio distintos, 19.233 huérfanas sin lote, 1.995 precios atípicos, 606
cantidades con forma de año, 56 grupos de importe de licitación compartido y 8
de importe repetido en el mismo expediente.

### Recuento por Situación de la hoja "Conciliación"

| Situación | Expedientes |
|---|---:|
| Aporta líneas | **362** |
| Publicado sin cuadro de precios | **64** |
| Los precios están en un acuerdo marco que no está publicado | **49** |
| Documentos escaneados que no se han podido leer | **15** |
| Otro | **28** |
| Pendiente de procesar | **0** |
| **Total** | **518** |

### Pendiente de decisión del cliente

1. **Que la columna de estado publicado use el documento cuando es más reciente
   que el último boletín de sindicación** (`6.25/28510.0221`). Propuesto, sin
   aplicar.
2. **Reprocesar los 91 candidatos al reparto por lotes del cuadro de precios**,
   y medir en cuántos entra. Ninguno puede perder filas por construcción, pero
   sí cambiaría a qué lote se atribuyen las suyas.
3. **Un expediente puede constar "no publicado" por su propio número y tener su
   adjudicación publicada bajo el expediente principal de su licitación**
   (`6.26/28510.0003`, lote 2 de `6.25/28510.0221`). Sin tocar.
4. Siguen en pie las seis de la parte anterior.
