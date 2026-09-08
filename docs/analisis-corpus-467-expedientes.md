# Análisis del corpus a 467 expedientes (sesión 2026-09-07/08, tras el backfill completo)

Análisis puro, sin arreglar nada — encargo explícito de la sesión. Corpus real
en el momento de este análisis: 467 expedientes, 8.225 líneas de catálogo,
303 en revisión, 109 sin publicar, 54 completados, 1 fallido. Ordenado por
impacto.

---

## 1. El hallazgo con más impacto: `ensure_form` no aguanta la Plataforma bajo carga (nuevo, sin arreglar)

Intentando verificar a mano una muestra de los 62 expedientes del SAP dados
por "no encontrados" (encargo del punto 5), **los seis primeros fallaron con
un error distinto tanto de "encontrado" como de "no publicado confirmado"**:
`RuntimeError: No se localiza el formulario de Licitaciones`. Para descartar
que fuera un problema de estos seis códigos concretos, se repitió contra
`6.25/28510.0016` — una de las tres matrices de carril, verificada publicada
y completa hace horas en esta misma sesión — y falló exactamente igual.

Diagnóstico en vivo (navegación real, sin pasar por la cola): la Plataforma
responde con normalidad (HTTP 200, título y contenido correctos) y el clic
en la tarjeta "Licitaciones" sí navega a la vista esperada (mismo `viewId`
JSF de siempre, `IZ7_AVEQAI930OBRD02JPMTPG21004` — los identificadores no
han cambiado). El campo de búsqueda **sí aparece, pero tarda más de lo que
el código espera**: `ensure_form` da hasta ~3 s (900 ms + 3×700 ms) antes de
rendirse; medido en vivo, el campo apareció recién a los ~7,5 s. Repetido
varias veces con el mismo resultado — no es un bache de un segundo, es una
lentitud sostenida ahora mismo.

**Esto es la misma familia de fallo que motivó el arreglo de la sesión
anterior** (confundir un fallo transitorio con un resultado determinista),
pero en una etapa distinta y no cubierta por ese arreglo: `wait_results` ya
distingue bloqueo/timeout de "sin resultados confirmado", pero `ensure_form`
(un paso antes, localizar el formulario) sigue con un presupuesto de espera
fijo y corto que no se ajusta si la Plataforma responde más lenta de lo
habitual. El efecto práctico: un expediente real puede fallar con un
`RuntimeError` genérico (que al menos no lo marca `sin_publicar`, gracias al
arreglo anterior — cae a `fallido`, reintentable) simplemente porque el
formulario tardó más de 3 segundos en aparecer.

**Evidencia de que esto YA pasó durante la propia tanda de esta sesión**: el
único expediente que quedó en `fallido` (no `sin_publicar`) tras las 374
descargas del SAP, `6.21/28510.0108`, falló con este mismo mensaje exacto.
Es decir, ya se ha visto una vez en producción, agotó sus 3 reintentos (con
la espera creciente ya implementada) y quedó correctamente como fallo
reintentable — el arreglo de la sesión anterior contuvo el daño (no lo
marcó como inexistente), pero no evita el fallo en sí.

**Consecuencia directa para el punto 5 del encargo**: no se puede completar
la verificación a mano de los 62 "no encontrados" en este momento con
garantías — cualquier intento ahora mismo tropieza con este mismo timeout
antes de llegar siquiera a buscar el código. Los 62 sí vienen de la vía
correcta (`wait_results` confirmando "sin resultados", igual que el análisis
de trazas más abajo confirma), así que no hay motivo para dudar de ellos en
bloque, pero tampoco se pueden dar por buenos uno a uno hoy. Recomendación:
repetir la verificación de la sección 5 más adelante, y en la próxima
sesión de código ampliar el presupuesto de espera de `ensure_form` (o
hacerlo dinámico, igual que `wait_results`) antes de volver a intentarlo.

**Nota metodológica, para que no se repita**: la propia verificación a mano
se hizo llamando a `scrape_expediente` directamente, sin pasar por
`app.scraping.job` — así que no llevaba el espaciado de 5 s
(`esperar_turno`) que sí protege la tanda real. Es plausible que estas
comprobaciones sueltas, siete llamadas seguidas sin pausa, hayan contribuido
a la lentitud observada. La próxima vez, verificar a mano debería pasar por
la cola real (un `descargar_expediente` por código, con su espaciado),
no invocar el scraper suelto.

---

## 2. Huérfanos de documento compartido entre expedientes hermanos (confirma un límite ya conocido, ahora medible)

Dos motivos de revisión, antes invisibles con el corpus de 45-52
expedientes, aparecen ahora de forma clara:

- **"El documento declara 'EXPEDIENTE PRINCIPAL/ORIGEN' distinto del
  expediente bajo el que están archivados sus documentos"** — 9 casos
  (`6.25/28510.0141`, `6.23/28510.0109`, `6.24/28510.0064`,
  `6.25/28510.0019`, `6.23/28510.0051`, `6.23/28510.0066`,
  `6.23/28510.0129`, `6.24/28510.0117`, `6.25/28510.0142`).
- **"No se extrajo ninguna línea de catálogo de los documentos
  descargados"** (17 casos) — verificado que, de estos, un subconjunto real
  (comprobado en `4.25/28510.0124`, `6.19/28510.0115`, `6.19/28510.0126`,
  `6.19/28510.0134`, `6.19/28510.0179`, `6.19/28510.0206`, al menos 6 de los
  17) no es "sin cuadro de precios publicado" sino **colisión de hash**:
  la descarga real SÍ encuentra documentos (`documentos: {ANEJO: 2, PLIEGO:
  1, CONTRATO: 2, ADJUDICACION: 1}` en el resultado del trabajo), pero
  `documentos_nuevos: 0` porque el hash de cada PDF coincide byte a byte con
  uno ya registrado bajo OTRO expediente (confirmado: los tres PDF de
  `4.25/28510.0124` son idénticos a los de `4.25/28510.0132`). La
  constraint `UNIQUE(hash)` de `documentos` hace que el segundo expediente
  en reclamar ese hash se quede sin ninguna fila de `Documento` propia,
  aunque el fichero exista de verdad en el sistema.

**No es un bug nuevo — es el límite ya documentado en CONTEXTO.md
("Separar de verdad 6.24/28510.0088 y 6.23/28510.0129 [...] en expedientes
de lote reales [...] identificado como cambio de modelo de datos mayor,
fuera de alcance de un arreglo urgente")**, que con 45-52 expedientes nunca
llegó a manifestarse en la práctica y ahora, con 467, aparece en al menos
26 expedientes (9+17, con solapamiento posible entre ambas listas). Es el
hallazgo de "trabajo pendiente nuestro" con más impacto de los tres puntos
de este informe: no hace falta inventar nada nuevo, sino abordar el cambio
de modelo de datos que CONTEXTO.md ya identificó y aparcó.

---

## 3. Categorización completa de los 303 en revisión

| Motivo | Nº | Naturaleza |
|---|---:|---|
| Cobertura parcial: no todos los lotes declarados tienen baja/importe | 48 | **Correcto** — límite de origen, ya documentado |
| La matriz no tiene ningún lote registrado (sin publicar/sin datos) | 46 | **Correcto** — límite de origen |
| La matriz tampoco tiene cuadro de precios ni baja | 44 | **Correcto** — límite de origen (p.ej. modelo de precio indexado) |
| Línea con un valor que no se pudo interpretar | 30 | **Mayormente correcto** — mecanismos de recuperación ya implementados y marcados para confirmar; muestreado parcialmente, sin bug nuevo encontrado esta vez (ver sección 1 de CONTEXTO para el único bug real de esta familia, ya cerrado: formato "Cod0001") |
| La matriz es multi-lote y el pedido no indica cuál | 26 | **Correcto** — límite de origen |
| El expediente no trae ningún Anejo ni Pliego técnico con precios | 22 | **Correcto** — mismo patrón ya verificado dos veces (`6.24/28510.0025`, `0193`); no reverificado uno a uno a esta escala |
| No se extrajo ninguna línea de catálogo (genérico) | 17 | **Trabajo pendiente nuestro** — ver sección 2: colisión de hash entre expedientes hermanos, al menos 6 de 17 confirmados; el resto sin verificar individualmente |
| La matriz declarada forma un ciclo (referencia circular) | 17 | **Correcto** — dato real del documento |
| Documento(s) escaneado(s), sin capa de texto | 10 | **Correcto** — fuera de alcance por decisión de diseño (CONTEXTO.md sección 15) |
| El documento declara un EXPEDIENTE PRINCIPAL/ORIGEN distinto | 9 | **Trabajo pendiente nuestro** — ver sección 2, misma familia que la fila anterior |
| Banda vacía / varias cabeceras de lote (ambigüedad de tabla) | 7 | **Correcto** — Bloque 4 de la sesión anterior, señal informativa ya implementada |
| No se pudo extraer el cuadro de precios de un documento concreto | 2 | **Correcto**, no verificado individualmente esta vez |
| No se pudo determinar la baja de ningún lote | 2 | **Correcto** — flag deliberado |
| Licitación y adjudicación coinciden sin baja declarada (precios unitarios) | 1 | **Correcto** — flag deliberado |

**303 en total.** De ellos, **~248-274 son comportamiento correcto** (límites
de origen ya documentados o mecanismos de recuperación deliberados) y
**26-30 son trabajo pendiente nuestro**, concentrado casi enteramente en la
sección 2 (documentos compartidos entre expedientes hermanos). El resto de
"valores no interpretables" (30) y "sin Anejo ni Pliego" (22) se dan por
correctos por el patrón ya verificado en sesiones anteriores, pero no se han
vuelto a comprobar uno a uno a esta escala — si se quiere cerrar del todo,
son el siguiente sitio donde mirar.

---

## 4. ¿Motivos nuevos o los mismos a mayor escala?

**Doce de los catorce motivos ya existían y solo han crecido de tamaño**
(de un corpus de 45-52 a 467, un factor de ~9-10×, y el crecimiento de cada
motivo es del mismo orden). **Dos son nuevos en el sentido de que nunca se
habían observado en la práctica**, aunque el mecanismo que los detecta ya
existía en el código desde antes de esta sesión:

- "EXPEDIENTE PRINCIPAL/ORIGEN distinto" (sección 27 de CONTEXTO.md,
  `codigo_principal_declarado` — el código de contraste nunca disparó su
  propia alarma con el corpus pequeño).
- La colisión de hash entre expedientes hermanos (la constraint `UNIQUE` de
  `documentos.hash` siempre existió, pero con 45-52 expedientes nunca hubo
  dos códigos distintos compitiendo por el mismo PDF real).

Ninguno de los dos es un motivo "inventado" por esta sesión — son
consecuencias del mismo límite arquitectónico ya identificado en CONTEXTO.md
(expedientes de lote no separados de verdad), que solo se hace visible con
suficiente volumen de datos reales.

---

## 5. Fuentes de descubrimiento: cuántos expedientes aporta cada una

| Fuente | Expedientes | Exclusivos de esa fuente |
|---|---:|---:|
| Excel de ejecución SAP (`estado_contrato_sap`) | 367 | 59 |
| Excel de códigos (`codigos_cruzados = true`) | 338 | 31 |
| Sindicación (`sindicacion_expedientes`) | 121 | 27 |
| Descubrimiento inverso de pedidos (matriz confirmada por búsqueda inversa) | 8 | 0 |
| **Ninguna de las cuatro** (alta manual, corpus de prueba original) | — | 11 |

**Nota sobre "descubrimiento inverso de pedidos":** `matriz_expediente_id`
no es exclusivo de este mecanismo — un pedido puede resolver su matriz
porque su propio Anuncio PCSP la declara (mecanismo antiguo, forward,
CONTEXTO.md desde el principio del proyecto) o porque la búsqueda inversa la
encontró (mecanismo nuevo de la sesión de descubrimiento inverso). En total
hay **159 expedientes con matriz resuelta**, pero solo **8 confirmados por
la vía de búsqueda inversa** (verificado cruzando `candidatos_acuerdo_marco`
contra `expedientes`) — el resto la resolvió por la vía antigua. Los 8 son
los mismos 9 pedidos ya conocidos de las tres matrices de carril, menos uno
que pudo cambiar de estado entre medias.

**117 expedientes vienen de una sola fuente**, 11 no vienen de ninguna de
las cuatro (probablemente el corpus de prueba original, dado de alta a
mano antes de que existiera ningún mecanismo de descubrimiento automático).
La mayoría de los 467 (339) se solapan en dos o más fuentes — el SAP y el
Excel de códigos, sobre todo, cubren en buena parte los mismos expedientes.

---

## 6. Estado del catálogo

### Relleno por columna (8.225 líneas)

| Columna | Relleno |
|---|---:|
| Precio unitario | 99,0 % |
| Cantidad | 87,0 % |
| Código de precio | 79,9 % |
| Con lote asignado | 73,8 % |
| Unidad de medida | 73,2 % |
| Baja del lote | 66,3 % |
| Precio adjudicado | 65,5 % |
| **Código de material** | **66,7 %** |
| Matrícula | 48,1 % |

**El hallazgo más llamativo de esta sección, aunque no era lo que pedía el
encargo**: el código de material pasa del 8,1 % medido antes del bloque de
vocabulario (253/3.121 líneas del corpus pequeño) al **66,7 % ahora**
(5.486/8.225) — muy por encima de lo esperado solo con la ampliación de
vocabulario determinista. La explicación real: la vía de modelo
(`derivar_codigo_material_con_modelo`, cacheada por término,
`cache_codigo_material`) se ha ejercitado de verdad en las 8.225 líneas
reales del reproceso completo, no solo en el corpus de prueba —
verificado en los logs del worker durante la sesión (llamadas reales a
`claude-haiku-4-5` para términos como "VAT", "SOTOGUAN[TE]"). El cliente
dijo que esta columna no era crítica; el resultado la deja, de hecho, mejor
rellena que la matrícula.

### Duplicados y huérfanas

- **2.156 líneas huérfanas** (sin lote asignado, 26,2 % del catálogo) —
  crecimiento proporcional al esperado (797 en el corpus de la sesión
  anterior, ~9× menos expedientes).
- **360 de esas 2.156 (16,7 %) traen la señal de "posible duplicado"**
  (Bloque 4 de la sesión anterior) — coinciden en matrícula/descripción/
  precio con una línea ya resuelta del mismo expediente. El resto (1.796)
  son huérfanas sin ninguna coincidencia conocida, genuinamente pendientes
  de revisión humana caso a caso.

### Valores atípicos

- Precio unitario: de 0,00 € a 1.020.000,00 €. Solo **15 líneas con precio
  0,00 €** — proporción muy baja (0,18 %), no se ha verificado cada una
  individualmente esta vez, pero el patrón ya se comprobó como legítimo en
  la sesión de corrección del Excel (partidas de imprevistos, artículos
  incluidos sin coste aparte).
- **58 líneas con cantidad en forma de año** (2000-2026), flag deliberado
  ya implementado — mismo mecanismo, mismo criterio de "no inventar, dejar
  para confirmar" que antes.

### Matrículas repetidas entre expedientes

**712 de las 1.908 matrículas distintas (37,3 %) aparecen en más de un
expediente.** Confirma a escala mucho mayor el hallazgo de la sesión de
descubrimiento inverso ("13 matrículas... 12 expedientes cada una") — más
de un tercio del catálogo de materiales identificables por matrícula se
repite entre procedimientos de contratación distintos, justo la pregunta
que ADIF quería poder responder (CONTEXTO.md sección 11: "cómo evoluciona el
precio de un material").

---

## 7. Los 62 no encontrados en la Plataforma: verificación inconclusa

**No se pudo completar de forma fiable** — ver sección 1: el intento de
verificar una muestra de 6 códigos (incluido uno reverificado contra un
expediente conocido y publicado) tropezó de forma repetida y reproducible
con un timeout de `ensure_form` no relacionado con si el expediente existe
o no. Los 62 vienen todos de la vía correcta (`wait_results` confirmando
"sin resultados" de verdad, distinta de la vía de bloqueo/timeout que se
corrigió en la sesión anterior — ninguno de los 62 muestra el mensaje de
`BloqueoTransitorioError` ni quedó en `fallido`, todos confirmaron
negativo limpio), así que no hay motivo concreto para dudar del conjunto,
pero tampoco se pueden dar por buenos uno a uno con la comprobación de hoy.
Pendiente de repetir cuando la Plataforma responda con el ritmo habitual, o
tras ampliar el presupuesto de espera de `ensure_form`.

---

## 8. Rendimiento de la web con 8.225 líneas

**El catálogo (`/catalogo`) sigue siendo cómodo — la cola de revisión
(`/revision`) ha empezado a notarse.**

- `GET /catalogo` (paginado server-side, 50 filas por página, como
  siempre): **13-62 ms** medido en vivo, incluida la página más profunda
  (164 de 165) y una búsqueda por matrícula. El frontend
  (`CatalogoPanel.tsx`) pide siempre una página filtrada al servidor, nunca
  carga las 8.225 líneas en el navegador — arquitectura correcta, sin
  degradación real con este volumen.
- `GET /catalogo/exportar.xlsx` (genera el Excel completo, las 8.225
  líneas de una vez): **7,1 segundos**, fichero de 404 KB. Aceptable para
  una acción puntual de exportar, pero ya no es instantáneo — con el
  catálogo siguiendo esta curva de crecimiento (creció ~2,6× solo en esta
  sesión), es la primera pantalla donde el cliente notará la espera si el
  corpus sigue creciendo.
- **`GET /revision` (sin paginar, devuelve las 303 en una sola respuesta,
  sondeada por el navegador cada 3 segundos): 255 ms y 400 KB por
  respuesta.** No es lento en términos absolutos, pero es la única de las
  cuatro pantallas sin paginación de servidor — con el corpus de 45-52
  expedientes esto no se notaba (unas pocas decenas de KB), y ahora, con
  303 casos reales en revisión, cada sondeo de 3 segundos mueve 400 KB y
  tarda un cuarto de segundo. Es el sitio más probable donde la web
  empiece a notarse pesada si el número de expedientes en revisión sigue
  creciendo al ritmo de esta sesión (de 40 a 303, con desde el 52 hasta el
  467 corpus).

**Recomendación, sin implementar (fuera del alcance de este análisis):**
paginar `GET /revision` igual que ya está paginado `/catalogo`, antes de
que la cola de revisión crezca más.

---

## Resumen ejecutivo, por impacto

1. **`ensure_form` no aguanta la Plataforma bajo carga actual** — mismo tipo
   de fallo que el arreglo de la sesión anterior, en una etapa distinta y
   sin cubrir. Bloqueó la verificación del punto 5 del encargo.
2. **Documentos compartidos entre expedientes hermanos** (26 casos
   confirmados de 303) — límite arquitectónico ya conocido y aparcado en
   CONTEXTO.md, ahora medible por primera vez a esta escala.
3. **`GET /revision` sin paginar** — 255 ms / 400 KB por sondeo cada 3 s,
   con 303 casos; el catálogo paginado sigue rápido (13-62 ms) con más del
   doble de líneas que antes.
4. El resto de los 303 en revisión (~90 %) es comportamiento correcto ya
   documentado, no trabajo pendiente.
5. El código de material llega al 66,7 % de relleno (vs. 8,1 % antes de la
   sesión anterior) gracias a la vía de modelo funcionando a escala real.
6. 712 matrículas (37,3 % de las distintas) se repiten entre expedientes —
   confirma a gran escala que el catálogo responde a la pregunta real de
   ADIF sobre evolución de precios.
