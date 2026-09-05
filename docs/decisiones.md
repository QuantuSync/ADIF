# Decisiones y pulido de UI

Registro histórico movido desde `CLAUDE.md` (split de sesión 2026-09-05).
Ver `CLAUDE.md` para el contexto vivo del proyecto.

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
  queda — es información central del proyecto (CLAUDE.md sección 4) y mayoritaria
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
