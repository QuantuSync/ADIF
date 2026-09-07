# Sesión 2026-09-07 (continuación): adjudicatario LC.27, revisión por trabajo pendiente real, huérfanos de banda vacía y vocabulario de código de material

Continuación, mismo día, de la sesión que cerró `docs/descubrimiento-inverso-
matriz-pedidos.md`. Esa sesión dejó un límite conocido: dos de las tres
matrices de carril declaran su adjudicatario solo en Propuesta LC.27, sin
Anuncio PCSP, y `app.extraccion.campos_lc27` nunca tuvo un extractor para
ese campo. Esta sesión, en orden de prioridad del cliente:

1. Extractor de adjudicatario para LC.27.
2. Backfill completo de sindicación (en curso, ver sección 5).
3. Expedientes en revisión por trabajo pendiente real, no por comportamiento
   correcto.
4. Huérfanos de banda vacía: cuántos son copia exacta, cuántos únicos.
5. Vocabulario del código de material.

---

## 1. Extractor de adjudicatario LC.27 (bloque 1) — cerrado

`app.extraccion.campos_lc27.extraer_adjudicatario_lc27`: mismo patrón que ya
usaba `app.extraccion.lotes._ADJUDICATARIO_RE` para el camino multi-lote
("a la empresa/empresas..., con NIF/CIF"), generalizado con un separador
`[\s,–-]*(?:con\s+)?` para cubrir la variante real sin la palabra "con"
(`6.23/28510.0102`: "...ARCELORMITTAL ESPAÑA, S.A.– NIF:", guion en vez de
"con"). Verificado contra los 21 documentos `propuesta_lc27` reales del
corpus (los de camino de lote único, sin ningún "LOTE N" en el texto — los
multi-lote ya cubrían esto): misma redacción base en 9 de 10, la variante
del guion en el décimo. La misma función sirve también para
`resolucion_adjudicacion` (mismo texto de firma, verificado contra
`6.24/28510.0185` y `6.26/28510.0016`) — el orquestador ya trataba las dos
plantillas en la misma rama por declarar los mismos hechos (CONTEXTO.md
sección 17).

Wireado en `orquestador._extraer_campos_expediente` con la misma prioridad
Anuncio PCSP > LC.27 que ya usan licitación/adjudicación (CONTEXTO.md
sección 4): las tres matrices de carril no traen ningún Anuncio PCSP, así
que siempre caen a la vía LC.27.

**Revisión de otras plantillas sin extractor de adjudicatario** (encargo
explícito de la sesión): `propuesta_dt` (Dirección Técnica, 2 documentos
reales del corpus) no tenía extractor de adjudicatario NI de importe/objeto
— pero ambos expedientes que la usan (`6.23/28510.0104`, `6.24/28510.0047`)
también traen un Anuncio PCSP (un fichero `*_CONTRATO_N.pdf` que en
realidad es el formulario "Anuncio de formalización de contrato", no el
contrato firmado — CONTEXTO.md sección 3) con el campo `Adjudicatario`
correctamente extraíble por `app.extraccion.campos_pcsp`. Verificado
ejecutando la extracción real sobre esos dos documentos: el regex de PCSP sí
encuentra "RIBODEL SL" y "AMURRIO FERROCARRIL Y EQUIPOS SA" — el hueco no
era de extracción sino de reproceso (esos dos expedientes llevaban desde
antes de la sesión de descubrimiento inverso, cuando el camino de lote único
implícito todavía no escribía `lote.adjudicatario`). Se resuelve solo al
reprocesar (sección 4 de abajo). **No hace falta tocar `propuesta_dt`** en
esta sesión.

### Medición contra el corpus real

Reprocesados los 52 expedientes con documentos descargados
(`completado`/`pendiente_revision`), stack real:

| | Antes | Después |
|---|---|---|
| Expedientes con `lote.adjudicatario` | 13 de 52 | **40 de 52** |

Las tres matrices de carril (`6.23/28510.0018`, `6.23/28510.0102`,
`6.25/28510.0016`) tienen ahora las tres su adjudicatario
("ARCELORMITTAL ESPAÑA, S.A.") extraído. Relanzado
`POST /mantenimiento/descubrimiento-pedidos/ejecutar` para las dos que
seguían señalando el aviso: las dos completan la búsqueda con normalidad
(`omitido: false`, 92 candidatos de la caché, 2 y 3 pedidos ya conocidos
respectivamente, 0 nuevos — no hay pedidos nuevos que descubrir, coincide
con lo ya sabido) y `aviso_descubrimiento_pedidos` queda vacío en las tres.
**Cerrado**: el descubrimiento inverso matriz → pedidos ya funciona sin
excepción para las tres matrices de carril conocidas.

Test nuevo: `tests/extraccion/test_campos_lc27.py`
(`test_adjudicatario_propuesta_lc27_camino_lote_unico`,
`test_adjudicatario_propuesta_lc27_sin_la_palabra_con_delante_del_nif`).
Fixture nueva: `6.23_28510.0102_ADJUDICACION_1_p1.pdf` (recorte a 1 página
del documento real, la variante sin "con").

---

## 2. Hallazgo de paso: sexto formato real de `codigo_precio` ("Cod0001")

Verificando por qué `4.26/28510.0020` seguía en revisión con el motivo
genérico "no se extrajo ninguna línea de catálogo de los documentos
descargados" (distinto del motivo específico ya conocido para
`6.24/28510.0025`/`0193`, "el expediente no trae ningún Anejo ni Pliego
técnico" — CONTEXTO.md sección 16): este expediente SÍ trae un
`ANEJO_1.pdf` clasificado correctamente como `pliego de prescripciones
tecnicas` (no saltado, `es_pliego_sin_precios` da `False`), y
`localizar_paginas_candidatas` SÍ encuentra 1 página candidata.

`pagina.find_tables()` (pdfplumber, sin filtrar todavía) encuentra la tabla
real sin problema: 13 filas limpias, cabecera "Código"/"DESCRIPCION"/
"PRECIO". Pero `app.extraccion.tabla._es_fila_de_datos` no reconocía
ninguna fila como fila de datos porque el código real de este documento es
"Cod0001".."Cod0305" (prefijo "Cod" + 4 dígitos) — un formato no catalogado
hasta ahora (CONTEXTO.md sección 3 solo documentaba "P-NNN", "PN-NNN",
"PA-NNN", "L NN-T NN"). Sin ningún código reconocible, `_indice_primera_
fila_datos` devolvía `None` y la tabla entera se descartaba como espuria —
**el expediente tenía la tabla intacta, y el motor la tiraba entera**.

Arreglo: `COD\d+` añadido a `_CODIGO_PRECIO_RE`
(`app.extraccion.tabla`) y a `_CODIGO_PRECIO_NUCLEO_RE`
(`app.catalogo`, para que no caiga en "formato no reconocido" en la segunda
validación), ambos con `re.IGNORECASE` por si el corpus no mantiene siempre
la misma capitalización. Verificado contra las 8 páginas reales del
documento (39-46): consistente en todas, con una única excepción de ruido
de extracción ("Cod01Q/" en la página 45, que correctamente sigue cayendo a
revisión individual en vez de forzarse).

Test nuevo: `tests/extraccion/test_tabla.py`
(`test_codigo_con_prefijo_cod_se_reconoce_como_fila_de_datos`),
`tests/test_catalogo.py`
(`test_normalizar_codigo_precio_prefijo_cod_pasa_sin_motivo`). Fixture
nueva: `4.26_28510.0020_ANEJO_1_p39.pdf`.

---

## 3. Expedientes en revisión: comportamiento correcto vs. trabajo pendiente real (bloque 3)

Inventario de las ~2.750 líneas con `motivo_revision` no vacío del corpus
real (antes del reproceso de esta sesión), agrupadas por patrón:

| Categoría | Líneas | Naturaleza |
|---|---:|---|
| `cantidad es 0` (confirmar si es real) | 807 | Correcto: flag deliberado, nunca se inventa |
| Banda vacía (sin cabecera de lote) | 797 | Correcto por diseño — ver sección 4 |
| Cantidad recuperada de columna fantasma | 364 | Correcto: recuperación ya implementada, marcada para confirmar |
| Precio unitario recuperado de columna fantasma | 298 | Correcto: idem |
| Ninguna cabecera LOTE N reconocible en la banda | 183 | Correcto: banda con texto pero sin cabecera — verificado un caso real (`6.25/28510.0019`, tabla "MATERIALES A SUMINISTRAR" sin ninguna mención de lote, sección propia del documento) |
| Tabla asociada a un LOTE no declarado | 128 | Correcto: verificado contra `6.24/28510.0130` — el Pliego Técnico es COMÚN a los 13 lotes de la licitación completa, y este expediente concreto solo declara adjudicación de los lotes 4-6 (mismo patrón de "identidad de lote" de CONTEXTO.md sección 27, no un fallo) |
| Fila fundida sin identificador propio | 60 | Correcto: mecanismo ya cerrado (`docs/excel-cliente-correccion.md` bloque 4) |
| Cantidad con forma de año | 39 | Correcto: flag deliberado (CONTEXTO.md sesión 2026-09-07 anterior) |
| **`codigo_precio` con formato no reconocido** | 30 | 30 de las 30 son `6.24/28510.0185`, formato "P-001b" ya investigado y decidido en 2026-09-05: se deja para revisión porque no está confirmado como convención estable, no un fallo pendiente |
| Ruido de pie de página en `codigo_precio` | 29 | Correcto: recuperación ya implementada |
| Matrícula no reconocible (`'***'`) | 1 | Correcto: valor enmascarado en el propio documento |
| Otras (recuperación de fila fusionada, cabecera desalineada) | 13 | Correcto: mecanismos de recuperación ya implementados |

**Único caso real de trabajo pendiente encontrado**: el formato `Cod0001` de
la sección 2 — cerrado. El resto del volumen de revisión es, verificado uno
a uno contra los documentos reales, comportamiento correcto: o bien el
propio documento es ambiguo/contradictorio y el sistema se niega a adivinar
(CONTEXTO.md sección 12), o bien es un límite de origen ya conocido y
documentado en sesiones anteriores.

A nivel de expediente, los dos casos con el motivo genérico "no se extrajo
ninguna línea de catálogo de los documentos descargados" eran:
`4.26/28510.0020` (el bug de la sección 2, ya cerrado) — no había ningún
otro expediente con este motivo genérico distinto de los ya conocidos y
documentados (`6.24/28510.0025`, `0193`, CONTEXTO.md sección 16).

---

## 4. Huérfanos de banda vacía (bloque 4) — investigado, sin heurística automática

797 líneas de catálogo sin lote asignado por banda vacía (la tabla continúa
entre páginas sin ninguna cabecera "LOTE N" reconocible antes de ella —
decisión ya tomada de no heredar el lote de la página anterior,
`app.extraccion.lote_tabla`, por riesgo de atribución cruzada).

**Primer intento, revertido**: comparar cada huérfana contra las líneas ya
resueltas (con lote) del mismo expediente por firma de material
(matrícula+descripción+precio, o descripción+precio sin matrícula — misma
firma que `app.catalogo._firma_material`) y descartarla automáticamente si
coincidía. Contra el corpus real esto identificaba 186 de las 797 (de solo
dos expedientes: `6.25/28510.0019`, 9 lotes, 168 casos; `6.24/28510.0203`, 6
lotes, 18 casos).

**Por qué se revirtió**: verificar el cambio contra la batería de tests
completa rompió el caso de aceptación multi-lote real
(`test_expediente_0027_multi_lote_produce_baja_correcta_por_lote`,
`6.25/28510.0027`, "Suministro de balasto... 6 LOTES"). El documento real
declara:

```
LOTE 1 (pág. 22): P-1 Balasto sobre camión en cantera ... 10,85 €
LOTE 3 (pág. 23): P-1 Balasto sobre camión en cantera ... 10,85 €   ← idéntico
LOTE 4 (pág. 24): P-1 Balasto sobre camión en cantera ... 10,85 €   ← idéntico
LOTE 3 (pág. 23): P-2 T de balasto transportado...     ... 21,56 €  ← distinto
LOTE 4 (pág. 24): P-2 T de balasto transportado...     ... 12,32 €  ← distinto
```

"P-1" (carga en cantera) cuesta exactamente lo mismo en los 6 lotes: es un
precio de referencia fijo, independiente de dónde se ejecute el contrato.
"P-2" (transporte) varía lote a lote porque depende de la distancia
geográfica real. Ambas son líneas reales y distintas, cada una perteneciente
a su propio lote — no es la misma fila repetida en el documento. Verificado
contra la base de datos real (expediente 43): "P-3" (transporte a punto de
carga distinto), "P-4" (lavado), "P-5" (remonte) y "P-6" (enrasado) del lote
3 aparecen también como huérfanas idénticas del lote 4 — servicios genéricos
de manipulación de balasto, sin componente geográfico, con el mismo precio
de referencia en varios lotes.

Descartar por firma habría perdido en silencio líneas reales de otros
lotes. Y no es un caso aislado: "huérfana de banda vacía" solo existe en
expedientes multi-lote por construcción (con un único lote no hay ninguna
ambigüedad de lote que resolver) — el riesgo de coincidencia de precio de
referencia entre lotes cubre el 100% del dominio donde esta heurística se
aplicaría.

**Decisión del cliente**: nunca descartar automáticamente. En su lugar, una
señal informativa en la cola de revisión.

### La señal implementada

`app.catalogo.buscar_posible_duplicado_huerfana(db, linea)`: para una
huérfana, busca (misma firma que arriba) una línea YA resuelta del mismo
expediente — nunca decide, solo informa. Expuesta como
`posible_duplicado_de` en `LineaCatalogoOut`
(`GET /expedientes/{id}/revision` y las acciones de línea), con los datos
de la línea coincidente y su lote para comparar sin abrir el PDF:
`linea_id`, `identificador_lote`, `codigo_precio`, `matricula`,
`descripcion`, `precio_unitario`.

`RevisionPanel.tsx` (web) muestra, bajo cada huérfana con coincidencia, una
comparación de dos columnas (esta línea vs. la línea ya resuelta y su lote)
y dos botones de un clic: "Confirmar como línea distinta" (reutiliza el
`Confirmar` de siempre) o "Descartar como duplicado" (reutiliza el
`Descartar` de siempre, con el motivo ya redactado apuntando a la línea con
la que coincidía, para que quede trazado el porqué). Convierte revisar las
797 huérfanas reales en una tarea de confirmar/descartar con un clic, no en
abrir 797 veces el PDF.

Verificado contra el stack real (expediente 43, `6.25/28510.0027`): la señal
aparece correctamente para las 5 huérfanas que coinciden con líneas del
lote 1 o 3, y no aparece para ninguna huérfana sin coincidencia real.

Tests nuevos: `tests/test_catalogo.py`
(`test_buscar_posible_duplicado_huerfana_encuentra_coincidencia_por_firma`,
`test_buscar_posible_duplicado_huerfana_ninguna_coincidencia_devuelve_none`,
`test_buscar_posible_duplicado_huerfana_no_aplica_a_linea_con_lote`).

**Sin cerrar**: cuántas de las 797 huérfanas reales tienen esta señal tras
el reproceso completo del corpus (pendiente, en cola detrás del backfill de
sindicación de la sección 5) — el mecanismo está verificado y funcionando,
falta la medición a escala completa.

---

## 5. Vocabulario del código de material (bloque 5)

`VOCABULARIO_CODIGO_MATERIAL` (`app.extraccion.codigo_material`) ampliado
de 11 términos (los ejemplos literales de CONTEXTO.md sección 6) a ~90,
extraídos de la frecuencia real de la primera palabra de cada descripción
del catálogo (consulta agregada contra la base de datos real, no
inventados): piezas y elementos de vía/aparatos de vía (CONTRACARRIL,
TIRANTE, CABLE, CARRIL, CORAZÓN, CRUZ, BULÓN, SEMICAMBIO...), herrajes
generales (PIEZA, SOPORTE, EMPALME, CHAPA, PERFIL...), electromecánica y
señalización (INTERRUPTOR, MÓDULO, BOBINA, FUSIBLE...), y tres acrónimos
que funcionan como el sustantivo principal de la línea en el corpus real
(SEPA, SAI, PAT — nombran un tipo de equipo, no un código).

Descartado a propósito:
- Códigos de tipo de aparato de vía sin ningún sustantivo (`DSF-A-45-...`,
  `SCI-A-54-...`): identifican un modelo, no una categoría de material.
- Nombres de marca (Schneider, Allen Bradley).
- Tokens de unidad de medida sueltos delante del material real ("T de
  balasto...", "m de poste...", "ud SEÑAL..."): `_termino_candidato` los
  salta (con o sin preposición "de" entre medias) para mirar la palabra
  siguiente, en vez de tratar la unidad como si fuera el material.
- "PARTIDA": CONTEXTO.md sección 2 define la partida alzada como una línea
  SIN código de material por definición — nunca entra al vocabulario ni se
  pregunta al modelo (lista `_EXCLUIDOS_DEL_MATERIAL`, también cubre
  ordinales sueltos "PRIMER"/"SEGUNDO"/"TERCER"/"OTRAS").

Normalización de acentos y plural a forma canónica (`_en_vocabulario`): el
corpus trae el mismo término con y sin acento por variación de la
extracción de texto (`BULON`/`BULÓN`), y en singular y plural
(`CERROJO`/`CERROJOS`) — ambas formas casan contra la misma entrada y
devuelven siempre la forma canónica.

### Vía de modelo (el encargo: "si algún caso no encaja por reglas, ahí sí
puede intervenir el modelo, una vez por término nuevo y cacheado")

`derivar_codigo_material_con_modelo(descripcion, db, model_provider)`:
regla determinista primero (sin tocar el modelo ni la base de datos); si no
casa nada, caché por término (`cache_codigo_material`, migración 0018,
mismo mecanismo que `cache_mapeo_cabecera` para el mapeo de cabecera); si
tampoco está en caché y hay `model_provider`, una llamada, se guarda el
resultado (incluido `null`, para no volver a preguntar un término que el
modelo ya confirmó que no es material) y no se vuelve a preguntar nunca.
Sin `model_provider`, se queda en `None` sin cachear (una ausencia de
modelo es una limitación de configuración, no una respuesta verificada).

Ejercitado como paso posterior en `app.extraccion.pipeline_anejo.
procesar_anejo` (que ya tiene `db`/`model_provider` a mano para la etapa 5
de mapeo de cabecera) sobre las líneas ya construidas —
`construir_linea_catalogo` sigue sin tocarse, mantiene su firma pura.
Verificado en vivo contra el stack real (reproceso de esta sesión,
`claude-haiku-4-5`): términos reales del corpus como "VAT" (código de
verificador, "VAT-1 PÉRTIGA VERIFICADORA...") y "SOTOGUAN[TE]" pasaron por
el modelo con normalidad.

Tests nuevos: `tests/extraccion/test_codigo_material.py` (12 casos:
vocabulario ampliado, partida alzada excluida, salto de unidad de medida,
normalización de acentos/plural, código de aparato de vía sin sustantivo,
y las cuatro combinaciones de la vía de modelo — usa primero, llama una vez
y cachea, confirma ausencia y la cachea, sin `model_provider` no cachea).

**Medición de relleno antes/después**: pendiente del reproceso completo del
corpus (en cola detrás del backfill de sindicación de la sección 5 —
sección 6 de este documento en realidad, la numeración es literal del
encargo). Antes de esta sesión: 253 de 3.121 líneas (8,1 %) con
`codigo_material`. Número final tras el reproceso, pendiente de actualizar
en este documento.

---

## 6. Backfill completo de sindicación (bloque 2) — en curso

Continuación de `docs/hallazgos-sindicacion.md` sección 25: dos periodos
ingeridos (`202408`, `202609`), ~25 meses intermedios nunca comprobados.

**Ritmo medido** (esta sesión, red real): cada ZIP mensual completo pesa
~150-160 MB (medido: `202608` = 160.085.565 bytes) y tarda **~11 minutos en
descargarse** en esta red — más lento que los ~460 s (~8 min) medidos en la
sesión original del 2026-09-04 para un mes completo, mismo orden de
magnitud. El parseo/filtrado, una vez descargado, es rápido (~20 s para
`202608`: 257 expedientes ADIF totales, 17 del departamento configurado, 0
nuevos, 0 con cambio de estado).

A este ritmo, backfillear los ~21 meses restantes (`202409`-`202605`)
tarda del orden de **3,5-4 horas**, casi toda en descarga de red, no en
proceso. Reportado al cliente antes de lanzarlo entero (encargo explícito de
la sesión); confirmado lanzarlo igual, en segundo plano, sin bloquear el
resto de bloques.

Lanzado como un único trabajo `sindicacion_backfill`
(`POST /mantenimiento/sindicacion/backfill`, payload con los 21 periodos
explícitos) detrás de un trabajo de prueba de 3 meses
(`202608`/`202607`/`202606`) ya en marcha. Corre de forma asíncrona en la
cola de siempre — consultable en `GET /mantenimiento/sindicacion/historial`
o en `trabajos_cola` (ids 1163 y 1218) — sigue corriendo aunque termine esta
sesión, mismo patrón que la sesión original.

**Números finales del backfill completo: pendientes de esta ejecución.**
Actualizar esta sección (expedientes ADIF totales / filtrados / nuevos /
líneas de catálogo aportadas por los nuevos, sumados sobre todos los
periodos) en cuanto termine.

---

## Pendiente al cierre de esta sesión

- Backfill completo de sindicación (sección 6): en cola, corriendo solo.
- Reproceso de verificación a escala completa de los arreglos de las
  secciones 2 y 5 (formato `Cod`, vocabulario de código de material): en
  cola, detrás del backfill de sindicación (mismo worker, una sola cola).
- Recuento final del catálogo (completados, en revisión, líneas de
  catálogo, matrículas repetidas) tras todo lo anterior: pendiente.
