# Sesión 2026-09-17 — Documentos escaneados, código del material, pendientes

Cifras medidas contra la base de datos real y los PDF reales.

## Bloque 1 — Expedientes con documentos escaneados (análisis, sin implementar)

### Cuántos

"Escaneado" = el criterio del sistema (`app.extraccion.texto.es_documento_escaneado`:
menos de 10 caracteres de texto en todo el documento), medido sobre la caché
de texto de los 1.623 documentos del corpus. Solo hay 1 documento más con la
mitad de las páginas sin texto (7 páginas): el fenómeno es de documento
entero, no de páginas sueltas.

| | Corpus completo |
|---|---|
| Documentos escaneados | **140** (de 1.623) |
| Páginas | **5.298** |
| Expedientes con algún documento escaneado | **113** |
| … de ellos, sin ninguna línea de catálogo | **85** |
| … con líneas (el escaneado es un documento secundario) | 28 |

Por año del código (los 113): 2015 2, 2016 10, 2017 15, 2018 15, **2019 60**,
2020 4, 2024 3, 2025 3. Los de 2024-2025 comparten un único pliego
administrativo escaneado (100 páginas, `6.20/28510.0136_ANEJO_2.pdf`) y ya
tienen sus líneas por otros documentos. **Es un fenómeno de 2016-2019**, no
algo que vaya a crecer con las publicaciones nuevas.

### Qué documentos son

Clasificados mirando las páginas (primera, ¼, ½, ¾ y última de cada uno):

| Tipo | Documentos | Aporta catálogo |
|---|---|---|
| Pliego de prescripciones técnicas (PPT) | **60** | sí, casi siempre al final |
| Pliego administrativo / cuadro de características | **60** | no ("Relación de artículos: NO PROCEDE", modelo DEUC en blanco) |
| Resolución de adjudicación / contrato | 10 | no, pero traen la baja |
| Actas de mesa, criterios de solvencia, informes | 8 | no |
| Planos / fichas técnicas (una de 670 páginas) | 2 | no |

El nombre del fichero no ayuda: tanto el PPT como el administrativo se llaman
`ANEJO_1`/`ANEJO_2` según el expediente.

### Cuántas líneas se pierden

Se contaron, página a página, las filas de artículo de los cuadros de los 60
PPT (todas sus 1.362 páginas renderizadas):

- **~1.800 filas con precio** (y ~50 sin precio) en 54 de los 60 PPT; 6 no
  traen cuadro (solo presupuesto global o normas).
- **Todas son de expedientes que hoy tienen 0 líneas**: ningún expediente
  con líneas pierde filas por esto. **67 expedientes** ganarían catálogo
  (39 de los 129 del descubrimiento por búsqueda del 16-09 y 28 que ya
  estaban). Los otros 18 de los 85 sin líneas tienen escaneado solo el
  administrativo o la adjudicación: su falta de líneas es otra.
- Los más grandes: `6.18/28510.0116` (190 filas, red SDH/WDM),
  `6.19/28510.0122` (185, traviesas de madera), `6.16/28510.0042` (170,
  traviesas), `6.17/28510.0024` (130, red IP), `6.16/28510.0161` (125,
  tornillos y tirafondos), `6.19/28510.0008` (90), `6.19/28510.0152` (80).
- Seis PPT son de licitaciones por lotes compartidas entre 2-4 expedientes
  hermanos: cada expediente de lote se quedaría con su lote, así que las
  líneas de catálogo serían del mismo orden que las filas.

**Estimación: ~1.800-2.000 líneas de catálogo** (+5 % sobre 35.323) y del
orden de **+1.700 filas en el Excel** (+11 % sobre 15.998); expedientes con
líneas 306 → ~373. De esos 67, **solo 21 tienen baja** declarada en un
documento legible: sin leer también las adjudicaciones escaneadas, dos
tercios de esas líneas saldrían sin precio adjudicado.

### Qué haría falta

La vía que ya prevé CONTEXTO.md sección 15: rasterizar la página y pasarla a
un modelo con visión. Nada de OCR tradicional (no hay `tesseract` en la
imagen; `pypdfium2` para rasterizar ya está instalado).

1. **Interfaz de modelo con imagen** (invariante 2: intercambiable, mañana un
   modelo autoalojado con visión). Hoy `ModelProvider.completar` solo acepta
   texto.
2. **Localizar las páginas del cuadro**: clasificar cada página escaneada a
   baja resolución ("¿hay un cuadro de artículos con precios?").
3. **Transcribir** las páginas del cuadro con salida estructurada (código de
   precio, matrícula, descripción, unidad, cantidad, precio y las cabeceras
   "LOTE N"), cacheado por hash del documento + página.
4. **Encajarlo en la cascada**: las filas transcritas entran por el mismo
   `construir_linea_catalogo`/`guardar_lineas_catalogo`, con página y
   transcripción como traza, y **marcadas para revisión** (ver calidad).
5. **La baja de las adjudicaciones escaneadas**, si se quiere precio
   adjudicado para los 46 que no la tienen.
6. Verificación contra los 67 expedientes.

**Choca con una regla escrita**: CONTEXTO.md sección 6 ("el modelo se llama
para traducir una cabecera nunca vista, para nada más"). Esto sería leer
datos con el modelo, así que es una decisión de alcance, no un arreglo.

### Coste

**Piloto real** (una página densa escaneada de `6.16/28510.0161`, 21 filas,
renderizada a 1.191×1.685, `claude-haiku-4-5`, el modelo configurado): 9,4 s,
1.639 tokens de entrada y 1.749 de salida. Matrículas (de 8 cifras, formato
antiguo real), referencias, normas y los 21 precios, correctos; **un dígito
mal** en una medida de la descripción ("M22X265" leído "M22X266").

Con los precios de la API (Haiku 4.5: 1 $ / 5 $ por millón de tokens de
entrada/salida; Sonnet 5: 2 $ / 10 $; la API por lotes, a mitad de precio):

| Paso | Volumen | Haiku 4.5 | Sonnet 5 |
|---|---|---|---|
| Clasificar páginas (estimado, ~700 tokens/página) | 5.298 páginas | ~4 $ | ~8 $ |
| Transcribir cuadros (medido: ~0,010 $/página Haiku) | ~150 páginas | ~1,5 $ | ~3 $ |
| **Total, una vez** | | **~6 $** | **~11 $** |

Tiempo de proceso: ~25 min para transcribir, ~3 h para clasificar en serie
(o asíncrono por lotes). Es un coste de una sola vez: la caché por hash
impide repetirlo y los documentos nuevos (2020 en adelante) traen texto.

**Desarrollo**: del orden de 2-3 sesiones como las de este proyecto (interfaz
y transcripción con caché; integración en la cascada con lotes y trazas;
verificación contra los 67), +1 si se quiere también la baja de las
adjudicaciones escaneadas.

**Riesgo principal**: la calidad. Una cifra mal leída en un precio no se
detecta sola (el piloto acertó los 21 precios, pero es una página). Por eso
las líneas deberían entrar marcadas como "leídas de imagen", visibles en la
cola de revisión.
