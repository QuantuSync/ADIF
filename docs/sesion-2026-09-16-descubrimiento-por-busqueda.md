# Sesión 2026-09-16 — Descubrimiento por búsqueda directa en la Plataforma

El cliente da por hecho que faltan expedientes de 2026: en el Excel solo ve
tres (`6.26/28510.0014`, `0032`, `0071`) y señala tres más que sí tienen
documentos publicados en la Plataforma (`0016` con todos, `0074` con
algunos, `0004` también).

## 1. Comprobación expediente a expediente: no faltaba ninguno

**15 expedientes `6.26/28510.*` en el sistema**, y la búsqueda directa en la
Plataforma devuelve **exactamente esos 15**, código por código. Ampliando a
`26/28510`: 21 publicados, los 21 en el sistema (y en la sindicación). Los
únicos `*.26/28510.*` que tenemos y no están publicados son tres que vienen
solo del Excel de SAP (`2.26/28510.0029`, `5002/01`, `5003/01`).

Los tres que señalaba el cliente estaban los tres, con documentos
descargados:

| Expediente | Docs descargados | Docs publicados en la ficha | Líneas |
|---|---|---|---|
| `6.26/28510.0016` | 4 | 20 | **124** (p. 10-12 del anejo de 139 págs.) |
| `6.26/28510.0074` | 3 | 6 | **1** — correcta: el cuadro tiene un solo artículo |
| `6.26/28510.0004` | 3 | 5 | **0** — defecto real, ver punto 2 |

Que de los 20 documentos de la ficha de `0016` se descarguen 4 es el diseño
(`seleccionar_documentos` se queda con el idóneo de cada categoría útil), no
una pérdida: los otros 16 son actas, informes de solvencia y recursos.

**"Solo aparecen tres en el Excel" no era descubrimiento, era una columna.**
El Excel trae 274 filas de `6.26/28510` en 10 expedientes, `0016` entre
ellos con sus 124. Lo que ve el cliente es la columna **"Código de
expediente"**, que solo se rellena si el expediente cruza con el Excel de
códigos de ADIF (`expediente.codigos_cruzados`) — y de los 15 solo cruzan
`0014`, `0032` y `0071`. El código siempre está, en "Nº de expediente
(documento)". Ya se había diagnosticado en la sesión 2026-09-15 (cuarta
parte); aquí queda verificado contra el Excel generado de verdad.

## 2. Matrícula con separadores de millar

`6.26/28510.0004` tiene su cuadro de precios en el Anejo nº 1 del PPT
(p. 7): un solo artículo, `667.500.506` MÓDEMS G.SHDSL.BIS, 100,00 €, 400
ud. `pdfplumber` lo lee bien, pero la tabla se descartaba entera por
espuria: sin columna de código de precio, la única señal de "fila de datos"
es la matrícula, y `app.extraccion.tabla._MATRICULA_DATO_RE` exigía `^\d{9}$`.

La normalización de la línea **ya** trataba la matrícula con puntos como el
mismo número desde la sesión 2026-09-14
(`app.catalogo._MATRICULA_CON_PUNTOS_RE`, patrón idéntico): el hueco estaba
solo en el detector de arriba, que decide si la tabla llega siquiera a
normalizarse.

Medido antes de arreglarlo, sobre los **117 expedientes con documentos y
cero líneas**: afecta a 3.

| Expediente | Líneas antes | Después |
|---|---|---|
| `6.26/28510.0004` | 0 | **1** |
| `6.23/28510.0034` | 0 | **21** |
| `6.24/28510.0048` | 0 | **26** (pasa a `completado`) |

Reextraídos los 15 de `6.26/28510` para comprobar que no hay regresión:
ninguno pierde ni gana una línea salvo `0004`.

### Efecto secundario: el guard de integridad denunciaba el propio arreglo

`app.mantenimiento.frescura.documentos_sin_cambios` solo comparaba la huella
de documentos, así que los tres expedientes recuperados quedaron con un
`error` que decía "posible duplicación en la extracción" — justo lo
contrario de lo que había pasado. Los documentos no cambiaron, pero la forma
de leerlos sí. El mecanismo para distinguirlo ya existía
(`VERSION_LOGICA_EXTRACCION`, el mismo que usa `debe_extraer` para decidir
reprocesar tras un cambio de código); este guard no lo consultaba. Ahora sí,
y la versión sube a `2026-09-16`. En un ciclo normal, sin despliegue de por
medio, el guard actúa igual que antes.

## 3. Descubrimiento por búsqueda directa (lo nuevo)

**Por qué.** La sindicación publica un expediente cuando hay un evento de
contratación en el mes: cubre bien lo ya adjudicado y deja fuera lo que
sigue en licitación o pendiente de resolver. Ya estaba medido que no lo
cubre todo (CONTEXTO.md sección 16: 2,5 % de los 367 del SAP), pero la causa
documentada era la antigüedad. Esta es la otra mitad, y afecta a lo más
reciente de cada año.

**Hallazgo del buscador.** El campo "Nº de expediente" hace coincidencia
**por subcadena**, no exacta ni por prefijo: `26/28510` devuelve de una vez
los 21 expedientes `2.26/`, `3.26/`, `4.26/` y `6.26/` del departamento. De
ahí que el parámetro se llame *fragmento*.

**Lo construido** (`app.scraping.descubrimiento_busqueda`, con
`app.scraping.pcsp.buscar_codigos_por_fragmento`):

- **Configurable, no atado a 2026.** `BUSQUEDA_FRAGMENTOS`, lista separada
  por comas. Vacía (por defecto) = los departamentos de
  `SINDICACION_DEPARTAMENTOS_ADIF`, que es exactamente el criterio del
  cliente ("todo expediente que contenga los dígitos 28510, en cualquier
  estado") y no hay que tocar nada para que valga en 2027. Un fragmento más
  fino (`6.26/28510`) acota una pasada concreta desde el payload del
  trabajo. `None` (no me has dicho cuáles) y `[]` (ninguno) son cosas
  distintas a propósito.
- **Con control de ritmo.** Cada búsqueda y **cada paso de página** pasan por
  `app.scraping.limitador`, el mismo turno compartido que espacia las
  descargas (`esperar_turno_async`, nuevo, para poder llamarlo desde dentro
  de una corrutina de Playwright sin bloquear el bucle de eventos). El
  episodio del 2026-09-07 no se repite por abrir una vía nueva de peticiones.
- **Dentro del ciclo de mantenimiento**, junto al descubrimiento por
  sindicación y antes del bucle de frescura, para que lo que aparezca se
  descargue y se extraiga en la misma pasada. Su fallo va aislado (red, WAF,
  formulario cambiado) y no se lleva por delante el resto del ciclo.
  `BUSQUEDA_DESCUBRIMIENTO_ACTIVO` lo apaga sin tocar código.
- **Un `sin_publicar` que la búsqueda encuentra se reabre** a `pendiente`
  (limpiando `sin_publicar_en`/`sin_publicar_version_busqueda`) sin esperar
  al plazo de `SIN_PUBLICAR_REINTENTO_DIAS`: aquí hay evidencia positiva, no
  un reintento a ciegas. No encola la descarga él mismo — el bucle de
  frescura ya lo hace, y encolarla aquí sería la misma petición por duplicado.

### La guarda que faltaba, encontrada en caliente

La primera pasada real con el fragmento `28510` dio de alta
`PcPG/2026/828510` y `EMER_HV_2020_62285100`: el buscador hace subcadena
pura y esos dígitos son parte de otro número. La sindicación ya tenía la
regla correcta ("los dígitos no pueden ir pegados a otros dígitos") dentro de
su `_cumple_criterio`. Se ha extraído a `app.criterio_expediente`, una sola
definición para las dos vías de descubrimiento, y la búsqueda la aplica sobre
sus resultados en vez de fiarse del buscador. Los dos expedientes espurios
(sin documentos, sin líneas, sin trabajos) se borraron.

### Resultado de la pasada real

| Fragmento | Códigos devueltos | Nuevos |
|---|---|---|
| `6.26/28510` | 15 | 0 |
| `26/28510` | 21 | 0 |
| `28510` | 131 válidos + 2 descartados | **129** |

**129 expedientes del departamento 28510 que ni la sindicación ni el Excel
de SAP conocían**, casi todos de 2013-2025. Quedan en `pendiente` sin
documentos; el próximo ciclo de mantenimiento los descarga y los extrae
(con la subida de `VERSION_LOGICA_EXTRACCION`, ese ciclo además reextrae
todo el corpus: será largo por diseño).

## 4. Cifras finales de `6.26/28510`

- **Publicados de verdad en la Plataforma: 15.** Los 15 están en el sistema.
- **Entran con líneas: 10** (`0004`, `0009`, `0014`, `0016`, `0030`, `0032`,
  `0040`, `0064`, `0071`, `0074`).
- **Aportan 274 filas** al Excel, una más que antes de esta sesión.
- Los 5 sin líneas (`0047`, `0048`, `0049`, `0068`, `0073`) son los pedidos
  de EPIs cuya matriz (departamento 04110) no está publicada en la
  Plataforma — límite de origen ya documentado, no un fallo del sistema.

## Pendiente al cerrar

- Los 129 expedientes nuevos están descubiertos pero sin descargar. El ciclo
  de mantenimiento los recoge solo; no se ha medido cuántas líneas aportarán.
- `PA` (66 líneas) y `P` (3) como unidad siguen pendientes de decisión del
  cliente (viene de la sesión anterior).
