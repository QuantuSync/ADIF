# Decisiones y pulido de UI

Registro histórico movido desde `CONTEXTO.md` (split de sesión 2026-09-05).
Ver `CONTEXTO.md` para el contexto vivo del proyecto.

---

## 28. Pulido a 1280px: desbordamiento horizontal, cola de revisión sin
    aprovechar la pantalla, y ruido de diagnóstico en mantenimiento
    (sesión 2026-09-04)

Sesión de correcciones puntuales sobre el rediseño visual (sección
anterior), sin tocar el motor. Encargo explícito: verificar cada arreglo
con la aplicación real abierta a 1280px, no solo compilando — hecho con
Playwright headless contra el stack real (`docker compose`, 53
expedientes, 3018 líneas de catálogo), midiendo `scrollWidth` de la página
antes y después de cada cambio, nunca solo mirando una captura.

- **Aviso de entorno, no del proyecto:** `/home/lucas/adif` (WSL) es un
  clon antiguo y desactualizado (solo tiene el esqueleto del punto 1 del
  orden de trabajo, sin `catalogo/`, `revision/` ni `mantenimiento/`) — no tiene relación con
  el stack que corre de verdad. Los contenedores reales (`adif-api-1`,
  `adif-web-1`...) se construyen desde **`/mnt/c/dev/ADIF`** (el mismo
  directorio de Windows, montado), con `docker-compose.yml` +
  `docker-compose.override.yml` — confirmado con `docker inspect
  --format '{{json .Config.Labels}}'` (`com.docker.compose.project.
  working_dir`). Cualquier sesión futura que edite código y no vea el
  cambio reflejado tras un rebuild: comprobar primero desde qué ruta se
  construyó el contenedor, no asumir que `/home/lucas/adif` es el proyecto.
  (Ver también sección 4 más abajo — ese clon se borró en la sesión siguiente.)
- **Expedientes y Catálogo desbordaban 1280px por 257px y 218px** (medido).
  Causa en Catálogo: `.descripcion` (columna Descripción) tenía
  `max-width: 30rem` — bajado a `16rem`, la única columna con margen para
  ceder (encargo explícito), y el desbordamiento desapareció del todo.
  Causa en Expedientes, más sutil — dos factores, no uno:
  1. Las notas de motivo (`.status-note`, en Estado y en Baja) no tenían
     tope de ancho salvo un `max-width: 28rem` genérico pensado para otros
     contextos (paneles de trazabilidad) — con nueve columnas a 1280px eso
     desborda. Añadido `.status-note-tight` (13rem) para uso dentro de
     celda de tabla.
  2. **Bug real de CSS, no obvio**: la celda de Baja es `.table .num`
     (`white-space: nowrap`, para que las cifras no partan línea).
     `white-space` es una propiedad heredada — la nota de motivo dentro de
     esa celda heredaba `nowrap` de su `<td>` ancestro, así que por mucho
     `max-width` que tuviera, el texto nunca partía en líneas: el cálculo
     de ancho de columna auto-layout usaba el ancho SIN partir (más de
     300px) en vez del ancho partido dentro del `max-width`. Verificado
     con `getComputedStyle` en Playwright (`whiteSpace: "nowrap"` medido
     sobre el elemento, pese a `max-width: 208px` declarado) antes de
     tocar nada — no se adivinó. Arreglado con `white-space: normal;`
     explícito en `.status-note`. Este único cambio bajó el desbordamiento
     residual de 55px a 0.
  3. Los dos botones de Acciones (`Descargar` / `Extraer`) se apilan ahora
     en columna en vez de en fila (encargo: "revisa si los botones
     necesitan tanto sitio") — de 197px a 120px, colchón adicional aunque
     no era la causa principal.
- **Columna Baja vacía: verificado que es dato real, no un fallo.**
  `GET /expedientes` ordena por `id` (creación), y en esta base de
  desarrollo los primeros ~14 ids son justo los pedidos derivados de
  acuerdo marco `esperando_matriz`/`sin_publicar` (`docs/identidad-expediente.md`
  secciones 20-22) — sin
  baja por diseño, no por error. Contados los 53: **28 de 53 (53%)** sí
  traen una baja real (directa o "varía por lote"), solo que ninguno cae
  en las primeras filas visibles sin hacer scroll. Decisión: la columna se
  queda — es información central del proyecto (CONTEXTO.md sección 4) y mayoritaria
  una vez se cuenta bien —, sin tocar el orden de listado (no pedido,
  fuera de alcance de un arreglo de descuadres; el orden sí se tocó en la
  sesión siguiente — ver `docs/hallazgos-extraccion.md` sección 29, punto 3).
- **Cola de revisión: el panel con el PDF embebido ya existía en código**
  (CSS y JSX de la sección anterior), pero la pantalla se abría sin ningún
  caso seleccionado — dos tercios en blanco hasta el primer clic, que es
  justo el síntoma que describía el encargo aunque la estructura ya
  estuviera construida. Arreglado seleccionando el primer caso de la lista
  en cuanto la lista carga (`RevisionPanel.tsx`), para que el documento y
  el formulario aparezcan sin interacción previa.
- **Bug real nuevo, encontrado al verificar la selección automática**: con
  un caso ya seleccionado, la tabla de líneas de catálogo (columna
  izquierda del panel, junto al PDF) desbordaba la página por 131px. Causa:
  un hijo de CSS Grid no encoge por debajo del ancho mínimo de su
  contenido por defecto (`min-width: auto` implícito) — la tabla de líneas
  (7 columnas) tiene un ancho mínimo mayor que la pista `minmax(0, 1fr)`
  que le correspondía junto al panel del PDF (`minmax(320px, 480px)`), así
  que el hijo empujaba la pista entera fuera del grid. Arreglado con
  `min-width: 0` en el contenedor y un scroll horizontal propio y acotado
  para esa tabla (`.table-scroll--panel`) en vez de dejar que el
  desbordamiento se propague a la página — con el `position: sticky` de la
  cabecera desactivado ahí a propósito, porque solo tiene sentido cuando
  el único scroll es el de la página entera (comentario ya existente en
  `.table-scroll`), no dentro de un panel con su propio scroll.
- **Descripciones de proyecto en la cola de revisión: recortadas a dos
  líneas** (`.revision-item .hint.proyecto`, `-webkit-line-clamp`) — en el
  corpus real llegaban a cinco líneas en mayúsculas y disparaban la altura
  de cada tarjeta.
- **Mantenimiento: la marca "abortado manualmente para diagnostico" no
  sale de ningún camino de código** (`grep` sobre todo `engine/app/*.py`:
  cero resultados) — es texto que alguien escribió a mano en la base de
  datos de desarrollo para desatascar un trabajo `en_proceso` huérfano
  durante otra sesión, nunca un fallo real del motor. Antes de esta
  sesión, la web no distinguía esta marca de un fallo real:
  `MantenimientoPanel.tsx` la trataba igual que cualquier `fallido` (barra
  de acento en tinta, punto relleno). Añadido `esInterrupcionManual`
  (detecta el texto "abortado manualmente" en el `error` del trabajo) — en
  el resumen de "última ejecución" y en la fila del histórico correspondiente,
  ahora usa el mismo tratamiento atenuado que `sin_publicar` (punto hueco,
  texto en tinta atenuada, sin la barra de acento), con una frase en
  lenguaje llano en vez del texto crudo de diagnóstico.
- **Verificado en vivo, no solo con datos ya en base de datos**: el worker
  llevaba parado 3 horas (`docker compose ps` mostraba `Exited (137)`, el
  propio efecto colateral de la sesión de diagnóstico que dejó la marca
  manual) — coherente con el propio síntoma del encargo. Reiniciado
  (`docker compose up -d worker`) y lanzado un ciclo real de mantenimiento
  end-to-end (`POST /mantenimiento/ejecutar`, sin forzar, sindicación
  desactivada) para comprobar el segundo punto del encargo ("que ese
  registro no quede como estado actual del sistema si después hubo
  ejecuciones correctas"): el ciclo tardó **≈23 minutos en completar
  (job 493)**, reprocesando el trabajo huérfano acumulado durante esas 3
  horas de worker parado — y al terminar, `/mantenimiento/estado` pasó a
  reflejar el 493 (`completado`) como última ejecución, con el 462
  (`fallido` / interrumpido manualmente) correctamente relegado al
  histórico y ya con su tratamiento atenuado. El mecanismo en sí
  (`app.mantenimiento.programacion._ultimo_trabajo_ciclo`, ya ordena por
  `created_at desc`) nunca tuvo el bug de fondo que el encargo temía — era
  puramente un problema de presentación, confirmado leyendo el código
  antes de tocar nada.

### Verificación

Las cuatro pantallas reconstruidas contra el stack real
(`docker compose build web && docker compose up -d web`, desde
`/mnt/c/dev/ADIF`) y medidas con Playwright a 1280×900: `scrollWidth -
clientWidth = 0` en las cuatro. `npx tsc --noEmit` sin errores. Sin tests
de `engine` afectados — ningún cambio de esta sesión toca `engine/`.

---

## 31. Herencia de lote entre páginas: la premisa de "cero casos" ya no
    aplica, pero el dato real desaconseja implementarla tal como estaba
    planteada (sesión 2026-09-05)

CONTEXTO.md sección 19 (y `app/extraccion/lote_tabla.py`) documentaba una
decisión explícita de no implementar herencia de lote entre páginas cuando
la franja que precede a una tabla está vacía de texto, basada en una
medición de **cero casos** en el corpus de entonces. La auditoría previa
(`docs/auditoria-previa.md`, hallazgo 5) midió **797 líneas** con motivo
"banda vacía" sobre el corpus multi-lote actual, el 72% (656) concentradas
en un único expediente, `6.25/28510.0019` (9 lotes). Encargo de esta sesión:
revisar la decisión con el dato nuevo, sin implementar nada todavía.

### Qué pasa hoy con las 797 líneas

Van a huérfanas (`lote_id = NULL`) con `motivo_revision = "banda vacía:
posible continuación de tabla partida entre páginas, sin inferir"` — el
expediente entero ya está en `pendiente_revision` por cobertura parcial de
lotes (CONTEXTO.md sección 27), así que no bloquean nada nuevo, pero
tampoco aparecen en el catálogo con su lote correcto.

### Lo que se encontró al revisar `6.25/28510.0019` fila a fila

Verificado con `SELECT` reales agrupando por página y `documento_origen_id`
(no solo el conteo agregado de la auditoría): las 656 líneas de este
expediente **no son una tabla dividida por el límite de una página que ya
tenía su lote resuelto** — son un cuadro de precios técnico, de
`ANEJO_1.pdf` (clasificado `pliego`), que se extiende de forma continua
durante **18 páginas** (20-47) sin que en ninguna de sus franjas aparezca
jamás una cabecera "LOTE N": la primera tabla de cada tramo cae como
"ninguna cabecera encontrada" (hay texto en la franja, pero no es un
marcador de lote — probablemente la cabecera de columnas repetida), y
**todas las páginas siguientes del mismo tramo, sin excepción, caen como
"banda vacía"** porque son la continuación directa de esa misma tabla sin
lote. Es decir: **no hay ningún lote ya resuelto del que heredar** al
principio de la cadena — la tabla nunca tuvo un lote identificado, ni en la
página 20 ni en ninguna posterior.

Verificado además que buena parte de esas 656 líneas son la **misma tabla
repetida entre documentos**: `CONTRATO_2.pdf` (pág. 111-139) incluye una
copia casi completa del mismo cuadro de precios de `ANEJO_1.pdf` (los
recuentos de líneas por página coinciden exactamente entre ambos
documentos), entremezclada además con la tabla de Resolución por lote (que
sí resuelve lotes 1-9 correctamente en ese mismo rango de páginas). Esta
duplicación es del mismo tipo que el mecanismo B de
`docs/hallazgos-extraccion.md` sección 30.2 (segunda tabla que repite
contenido sin columna de lote/código propia), solo que aquí las líneas
quedan huérfanas (`lote_id = NULL`) en vez de en un lote conocido — por
diseño, el arreglo de fusión por firma de material de esta sesión
**no se aplica a huérfanas** (para no fundir el mismo material ofertado en
lotes distintos), así que esta duplicación concreta sigue sin resolverse.

### Por qué la herencia, tal como está planteada, no resolvería la mayoría

El mecanismo original (`app/extraccion/lote_tabla.py`, "heredar el lote de
la tabla anterior cuando la franja está vacía") asume una cadena que
**empieza** con un lote ya identificado y solo pierde la cabecera en
páginas de continuación. El dato real de `0019` no encaja en esa forma: la
cadena entera (18 páginas) nunca tuvo cabecera de lote, así que no habría
nada válido que propagar — implementar la herencia tal cual dejaría estas
656 líneas exactamente igual de huérfanas (heredarían "ningún lote" de la
tabla anterior, que tampoco tenía uno).

Peor: en las páginas donde SÍ hay un lote resuelto cerca (111-123, la tabla
de Resolución), la tabla sin lote de `ANEJO_1`/`CONTRATO_2` aparece
**intercalada en las mismas páginas** — una herencia ciega ("usa el lote de
la tabla inmediatamente anterior en orden de lectura") podría atribuir
incorrectamente estas líneas al lote resuelto más próximo, que es el de una
tabla estructuralmente distinta. Eso sería un dato incorrecto con
apariencia de resuelto, peor que dejarlo huérfano para revisión manual —
exactamente el riesgo que CONTEXTO.md sección 19 ya anticipaba ("puede fallar
de formas silenciosas"), ahora confirmado con un caso real en vez de
hipotético.

### Recomendación (sin implementar)

1. **No implementar la herencia "hereda de la tabla anterior" tal como
   estaba diseñada** — el caso real mayoritario (656/797) no tiene ningún
   lote válido del que heredar, y el resto arriesga una atribución cruzada
   entre tablas distintas que comparten página.
2. El hueco real y accionable es la **duplicación entre documentos** de
   este mismo cuadro de precios (`ANEJO_1` vs. `CONTRATO_2`): antes de tocar
   la herencia, valdría la pena medir cuántas de las 797 líneas huérfanas
   coinciden en matrícula+descripción+precio con una línea **ya resuelta**
   en un lote conocido del mismo expediente — esas sí podrían descartarse
   con seguridad (son la misma línea que ya está en el catálogo con su lote
   correcto), sin el riesgo de fundir materiales de lotes distintos que hizo
   excluir a las huérfanas del arreglo de la sección 30.2.
3. Sesión propuesta, aparte: medir ese solape sobre el corpus completo
   (no solo `0019`) antes de decidir si construir el mecanismo del punto 2.
