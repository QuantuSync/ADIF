"""Conjunto fijo de prueba para la cascada de extracción.

CONTEXTO.md sección 13: "No metas los 187 PDFs en el repo. Deja un conjunto fijo
de prueba [...] Trabaja siempre contra esos." Copiados de Ejemplo/Input/ (que
no está en el repo, ver .gitignore) el 2026-09-02. Cada fichero conserva su
nombre original de la Plataforma para no romper la trazabilidad hacia el
expediente de origen.

6.24_28510.0008_CONTRATO_1_p1.pdf es un recorte a una sola página del
contrato real (Ejemplo/Input/6.24_28510.0008_CONTRATO_1.pdf, 5 MB / 3
páginas): la página 1 sola trae partes, importe y baja; el resto del
documento son anexos firmados sin datos nuevos para el catálogo.
"""
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / "pdfs"

# Anuncio PCSP (formulario estándar, CONTEXTO.md sección 3): "Anuncio de
# adjudicación" con la sección "Licitación basada en el acuerdo marco" que
# trae la MATRIZ.
ANUNCIO_PCSP_CON_MATRIZ = FIXTURES_DIR / "2.18_04703.0019_ADJUDICACION_1.pdf"

# Anuncio PCSP de un procedimiento directo (Negociado sin publicidad), sin
# acuerdo marco de por medio: no trae MATRIZ.
ANUNCIO_PCSP_SIN_MATRIZ = FIXTURES_DIR / "6.24_28510.0193_ADJUDICACION_1.pdf"

# Propuesta LC.27. Caso central del proyecto (CONTEXTO.md sección 4): licitación
# y adjudicación son ambas 138.000,00 €, baja declarada del 54,00 %. La
# fórmula ingenua (1 - adjudicado/licitación) da 0 %.
PROPUESTA_LC27_PRECIOS_UNITARIOS = FIXTURES_DIR / "6.24_28510.0008_ADJUDICACION_1.pdf"

# Propuesta LC.27 con adjudicación a una UTE de 3 empresas y baja del 0,50 %
# sobre una licitación de 1.000.000,00 € (mismo importe en licitación y
# adjudicación: segundo caso real de precios unitarios).
PROPUESTA_LC27_UTE = FIXTURES_DIR / "6.24_28510.0088_ADJUDICACION_1.pdf"

# Resolución de Adjudicación (plantilla L9_AF.01-FE, distinta de LC.27; ver
# CONTEXTO.md sección 17). Tercer caso real de precios unitarios: 800.000,00 €
# en licitación y adjudicación, baja declarada del 4,50 %.
RESOLUCION_ADJUDICACION = FIXTURES_DIR / "6.24_28510.0124_ADJUDICACION_1.pdf"

# Propuesta LC.27, camino de lote único, matriz de carril real
# (6.23/28510.0102): redacción real distinta de PROPUESTA_LC27_PRECIOS_UNITARIOS
# para el adjudicatario -- "...S.A.– NIF:" con guion en vez de la palabra
# "con" delante de NIF/CIF (docs/descubrimiento-inverso-matriz-pedidos.md
# sección 7). Recorte a la página 1 (Ejemplo/Input/6.23_28510.0102_
# ADJUDICACION_1.pdf, la página 2 solo trae el bloque de firmantes).
PROPUESTA_LC27_ADJUDICATARIO_SIN_CON = FIXTURES_DIR / "6.23_28510.0102_ADJUDICACION_1_p1.pdf"

# Contrato (plantilla L9_AF.06, "PARTES CONTRATANTES"). Mismo expediente que
# PROPUESTA_LC27_PRECIOS_UNITARIOS: la baja del 54,00 % declarada aquí debe
# coincidir con la de la propuesta.
CONTRATO_PRECIOS_UNITARIOS = FIXTURES_DIR / "6.24_28510.0008_CONTRATO_1_p1.pdf"

# Anejo de precios unitarios (en realidad el Pliego de Prescripciones
# Técnicas completo: el anejo de precios es una sección suya, no un fichero
# aparte — ver docstring de app.extraccion.clasificador). Cabecera de tabla:
# "Nº MATRÍCULA DESCRIPCIÓN ... CANTIDADES ESTIMADAS ... CÓDIGO ... PRECIO
# UNITARIO DE REFERENCIA".
ANEJO_PRECIOS_GUANTES = FIXTURES_DIR / "6.24_28510.0008_ANEJO_1.pdf"

# Igual que el anterior pero con cabecera de tabla distinta ("CÓDIGO ...
# CANTIDADES ... UNIDAD ... PRECIO DE ..."), y con varias tablas de cabecera
# repetida dentro del mismo documento. CONTEXTO.md sección 3: "11 variantes
# distintas en solo 7 documentos".
ANEJO_PRECIOS_TRAVIESAS = FIXTURES_DIR / "6.24_28510.0088_ANEJO_1.pdf"

# Expediente multi-lote real (encargo de la sesión de extracción por lote):
# Resolución de Adjudicación (plantilla L9_AF.01-FE) de "SUMINISTRO DE
# BALASTO... 6 LOTES", con solo LOTE 1 (7,13 %) y LOTE 3 (1,18 %) adjudicados
# — los otros cuatro lotes del expediente no llegaron a esta resolución. Es
# el caso que destapó que el motor se quedaba con la primera baja del texto
# y la presentaba como la del expediente entero.
RESOLUCION_MULTI_LOTE = FIXTURES_DIR / "6.25_28510.0027_ADJUDICACION_1.pdf"

# Pliego del mismo expediente (en realidad el nombre "ANEJO_1" es el Pliego
# de Prescripciones Técnicas completo, igual que ANEJO_PRECIOS_GUANTES): su
# Anejo Nº1 trae un cuadro de precios unitarios por lote, con los mismos
# códigos P-1..P-6 repetidos en cada uno de los 6 lotes (LOTE 1 a LOTE 6),
# cada tabla precedida por su propia cabecera "LOTE N" — el caso real que
# ejercita la asociación tabla->lote por posición (app.extraccion.lote_tabla).
ANEJO_PRECIOS_BALASTO_MULTI_LOTE = FIXTURES_DIR / "6.25_28510.0027_ANEJO_1.pdf"

# Sesión de arreglos pequeños (2026-09-03, docs/analisis-corpus.md hallazgo
# 4): 3ª plantilla de propuesta ("L9_CM.32-FE", Dirección Técnica en vez de
# Mesa de Contratación), baja declarada del 20,00 %. Su propia página 1 cita
# de pasada "el determinado en Pliego de Cláusulas Administrativas
# Particulares del contrato" (índice 1662 del texto normalizado): antes de
# la regla propia de esta plantilla, esa mención bastaba para clasificar el
# documento como `pliego` en vez de `propuesta_dt` — el caso real que
# destapó el falso positivo, no solo la plantilla sin clasificar.
PROPUESTA_DT_CON_FALSO_POSITIVO_PLIEGO = FIXTURES_DIR / "6.23_28510.0104_ADJUDICACION_1.pdf"

# Mismo formato, expediente 6.24/28510.0047, baja declarada del 0,13 %. Sin
# la mención de pasada al pliego: antes de la regla propia caía en `otro`,
# no en el falso positivo — los dos casos reales de la misma plantilla.
PROPUESTA_DT_SIN_FALSO_POSITIVO = FIXTURES_DIR / "6.24_28510.0047_ADJUDICACION_1.pdf"

# docs/analisis-corpus.md hallazgo 2: cuadro de precios real (carriles) cuyo
# código viene con el guion tipográfico Unicode U+2010 ("P‐01".."P‐13"), no
# el guion ASCII — página 12 (índice 11) del documento. Antes del arreglo,
# `_es_fila_de_datos` no reconocía ninguna fila como fila de datos y
# `extraer_tablas_pagina` descartaba la tabla entera como espuria.
ANEJO_PRECIOS_CARRILES_GUION_UNICODE = FIXTURES_DIR / "6.23_28510.0018_ANEJO_1.pdf"

# Sesión de expedientes sin publicar (2026-09-03, docs/analisis-corpus.md
# hallazgo 6): "otros formatos de código de precio", recortes de una sola
# página de documentos reales (el documento completo no hace falta para
# probar el filtro de fila de datos de `app.extraccion.tabla`).

# Código sin separador, un dígito ("P1", "P2") — cupones de carril,
# 6.24/28510.0047.
ANEJO_PRECIOS_CODIGO_P_SIN_GUION = FIXTURES_DIR / "6.24_28510.0047_ANEJO_1_p18.pdf"

# Código sin separador, dos dígitos ("P01", "P02") — tapas de canaleta,
# 6.24/28510.0187. Cabecera "CODIFICACIÓN DEL PRECIO", no "CÓDIGO DE
# PRECIO": no coincide con ningún alias determinista de `codigo_precio`
# (a propósito — ver test_mapeo_cabecera.py), así que en producción esta
# cabecera cae al modelo, no al mapeo determinista.
ANEJO_PRECIOS_CODIGO_P_DOS_DIGITOS = FIXTURES_DIR / "6.24_28510.0187_ANEJO_1_p11.pdf"

# Código con prefijo "PN" ("PN001".."PN018") — señalización vertical,
# 6.24/28510.0180. Misma cabecera "CODIFICACIÓN DEL PRECIO" que el anterior.
ANEJO_PRECIOS_CODIGO_PN = FIXTURES_DIR / "6.24_28510.0180_ANEJO_1_p18.pdf"

# Código de lote+tipo ("L01-T01".."L03-T13") y partida alzada numerada
# ("PA-01", "PA-02") en la misma tabla — traviesas, 6.24/28510.0094. Recorte
# de 2 páginas (112-113) del Contrato real (2,8 MB / 118+ páginas): el cuadro
# de precios es una sección interna suya, igual que los "*_ANEJO_N.pdf" de
# CONTEXTO.md sección 3.
ANEJO_PRECIOS_LOTE_TIPO_Y_PARTIDA_ALZADA = FIXTURES_DIR / "6.24_28510.0094_CONTRATO_1_p112-113.pdf"

# Tabla sin ninguna columna de código: la matrícula de 9 dígitos es el único
# identificador de fila — hilo de contacto, 6.20/28510.0136.
TABLA_PRECIOS_SOLO_MATRICULA = FIXTURES_DIR / "6.20_28510.0136_ANEJO_3_p3.pdf"

# Sexto formato de código de precio, bloque 3 de la sesión de expedientes en
# revisión por trabajo pendiente real (2026-09-07): prefijo "Cod" + 4 dígitos
# ("Cod0001".."Cod0305") — instalaciones de seguridad, 4.26/28510.0020.
# Página 39 (índice 38) del `ANEJO_1.pdf` real. Antes del arreglo,
# `_es_fila_de_datos` no reconocía ninguna fila y la tabla entera (13 filas
# limpias, cabecera "Código"/"DESCRIPCION"/"PRECIO") se descartaba como
# espuria — el expediente entero quedaba sin ninguna línea de catálogo pese a
# tener la tabla intacta.
ANEJO_PRECIOS_CODIGO_COD = FIXTURES_DIR / "4.26_28510.0020_ANEJO_1_p39.pdf"

# Sesión de identidad de lote (CONTEXTO.md sección 27): expedientes multi-lote
# reales cuya redacción del bloque de adjudicación por lote NO coincide con
# la de RESOLUCION_MULTI_LOTE ("En el LOTE N.") -- catalogados antes de
# generalizar `app.extraccion.lotes` contra las 15 variantes reales del
# corpus, no contra una sola.

# "4 LOTES", solo LOTE 1 en este documento (BASE DE MANTENIMIENTO DE MORA,
# expediente propio 6.23/28510.0073): la cabecera declara "EXPEDIENTE
# PRINCIPAL Nº" + "LOTE 1: ... EXPEDIENTE Nº X", pero el cuerpo nunca repite
# "LOTE N" -- antes de esta sesión, este caso caía al lote implícito único
# (`LOTE_UNICO`) y su baja/importe de UN lote de 4 quedaban etiquetados como
# los del expediente entero.
PROPUESTA_LC27_UN_LOTE_DE_VARIOS = FIXTURES_DIR / "6.23_28510.0066_ADJUDICACION_1.pdf"

# "3 LOTES", los tres con su propio bloque de adjudicación en el mismo
# documento ("- LOTE N: <desc>. EXPEDIENTE Nº X: <empresa>, con NIF: Y, con
# una baja económica del Z% ..."), con el bloque del LOTE 2 partido entre la
# página 0 (importe) y la página 1 (baja) -- ejercita el ventaneo por "LOTE
# N" sobre las páginas concatenadas, no una sola.
PROPUESTA_LC27_TRES_LOTES_BAJA_ENTRE_PAGINAS = FIXTURES_DIR / "6.24_28510.0117_ADJUDICACION_1.pdf"

# "7 LOTES" pero el LOTE 5 no aparece en ningún sitio del documento (ni en
# la cabecera ni en el cuerpo) -- desierto o anulado, sin verificar cuál
# (CONTEXTO.md sección 27): la numeración real tiene huecos y
# `lotes_totales_declarados` (7) nunca se usa para generar el lote que
# falta, solo para contar cuántos de los 7 sí se conocen (6).
RESOLUCION_LOTES_CON_HUECO = FIXTURES_DIR / "6.25_28510.0028_ADJUDICACION_1.pdf"

# "3 LOTES", los tres con su propio bloque numerado ("1º.-/2º.-/3º.-") en el
# mismo documento. Etiqueta el expediente principal como "Nº EXPEDIENTE
# MATRIZ" -- la trampa de vocabulario del docstring de `app.extraccion.lotes`:
# la palabra "matriz" aquí no tiene ninguna relación con acuerdo marco, es
# solo cómo esta Propuesta LC.27 concreta llama a "expediente que agrupa los
# lotes". Documento real que verifica que `codigo_principal_declarado` nunca
# se escribe en `expediente.codigo_matriz`.
PROPUESTA_LC27_NUMERADA_CON_ETIQUETA_MATRIZ = FIXTURES_DIR / "6.24_28510.0094_ADJUDICACION_1.pdf"

# Anuncio PCSP ("Anuncio de adjudicación") de una licitación de "2 lotes" y
# campo estructurado "Nº de Lotes: 2" -- el caso más peligroso de la sesión
# de identidad de lote: 6.23/28510.0139 no trae ninguna Propuesta LC.27 ni
# Resolución de la que sacar el desglose por lote, así que antes de esta
# sesión figuraba `completado` sin haber identificado ni un solo lote de
# los 2 que el propio documento confirma que existen.
ANUNCIO_PCSP_DOS_LOTES_SIN_DESGLOSE = FIXTURES_DIR / "6.23_28510.0139_ADJUDICACION_1.pdf"

# El único documento escaneado confirmado del corpus real (186 de 187
# documentos tienen capa de texto, CONTEXTO.md sección 3): recorte de 1 página
# del anejo de 100 páginas real (`6.20/28510.0136_ANEJO_2.pdf`) — cada página
# es una imagen a página completa, sin ningún carácter de texto ni con
# `pdfplumber` ni con `pypdf`.
DOCUMENTO_ESCANEADO_SIN_TEXTO = FIXTURES_DIR / "6.20_28510.0136_ANEJO_2_p1.pdf"

# Herencia de lote entre páginas de continuación (sesión de verificación del
# Excel, 2026-09-08, aprobado por el cliente): 5 páginas reales de
# `6.22/28510.0156_ANEJO_1.pdf` (repuestos genéricos de vía, 2 lotes) — p.15,
# 16, 25, 26 y 27 del documento original, en ese orden. p.15 y p.26 traen la
# cláusula de "urgencia mutua" que menciona los dos lotes en la misma frase
# (Parte A: se resuelve por posición gramatical, "Lote N:" vs "del lote M");
# p.16, 25 y 27 no traen ningún rastro de "LOTE" (Parte B: elegibles para
# heredar el lote de la tabla anterior). Verificado contra el documento real
# completo antes de implementar nada: el bloque de Lote 2 (p.26-36 del
# original) es una copia íntegra del cuadro de precios de Lote 1 (p.15-25),
# mismos códigos/descripciones/precios desplazados 11 páginas — la
# transición interna semicambios→cruzamientos es el orden del propio
# catálogo, no un cambio de lote sin marcar.
ANEJO_HERENCIA_LOTE_0156 = FIXTURES_DIR / "6.22_28510.0156_ANEJO_herencia_lote_p15-16_25-27.pdf"

# Sesión 2026-09-14 (revisión del cliente sobre el Excel): 3 páginas reales
# de `6.21/28510.0109_ANEJO_7bfc92005f43e68e.pdf` (criterios técnicos de
# repuestos de aparatos de vía, 5 lotes) -- p.3, 4 y 5 del original. p.3 trae
# la cabecera real ("TIPOLOGÍA APARATO | CÓDIGO DEL ELEMENTO | REPUESTO |
# DESCRIPCIÓN | ...") con P-11/P-12; p.4 y p.5 son continuación sin cabecera
# (P-13..P-22), con descripciones de 20-40 líneas de prosa técnica por fila:
# densidad numérica ~0,10, por debajo del umbral de continuación antiguo, así
# que antes de esta sesión esas dos páginas nunca se abrían.
ANEJO_REPUESTO_CONTINUACION_0109 = FIXTURES_DIR / "6.21_28510.0109_ANEJO_repuesto_continuacion_p3-5.pdf"

# Misma sesión: 2 páginas reales de `6.21/28510.0016_ANEJO_e40fc4e4546ec90b.pdf`
# (tornillería, Lote 2 "Anclajes de seguridad") -- p.19 y p.20 del original.
# La cabecera de la tabla está en una fuente sin mapa Unicode: `pdfplumber`
# devuelve "(cid:69)(cid:465)..." en vez de "Nº MATRÍCULA", "REF. ADIF",
# "DESCRIPCIÓN", "PLANO DE REFERENCIA", "CANTIDADES...", "PRECIO". 25
# anclajes con matrícula (13 + 12) más una partida alzada al final de la
# p.20.
ANEJO_CABECERA_ILEGIBLE_0016 = FIXTURES_DIR / "6.21_28510.0016_ANEJO_cabecera_ilegible_p19-20.pdf"

# Misma sesión, continuación (identidad de lote en expedientes hermanos):
# recortes a la página 1 de documentos reales. La página 1 de cada Contrato
# trae "Contrato nº", el "LOTE N" que es y la baja; la de cada adjudicación,
# la cabecera del lote y el RESUELVE.
#
# Tornillería (`6.20/28510.0115`, 2 lotes; `0015` es el LOTE 1 y `0016` el
# LOTE 2): la única Resolución es la del LOTE 2 ("LOTE 2 - ANCLAJES DE
# SEGURIDAD. EXPEDIENTE Nº: 6.21/28510.0016" en la cabecera) y su RESUELVE
# lo llama "LOTE 1: ANCLAJES DE SEGURIDAD. EXPEDIENTE Nº: 6.21/28510.0016"
# -- errata del documento. Los recortes de sus dos Contratos pesan 220-280
# KB; los tests usan el texto literal de su cabecera en su lugar.
RESOLUCION_LOTE2_ERRATA_LOTE1_0016 = FIXTURES_DIR / "6.21_28510.0016_ADJUDICACION_1_p1.pdf"

# Tornillos y tirafondos (`6.22/28510.0033`, 2 lotes; `0057` LOTE 1 NORTE,
# `0058` LOTE 2 SUR). La descripción de cada lote nombra al otro ("... POR
# EL ADJUDICATARIO DEL LOTE1, NORTE"), y la Resolución del LOTE 2 copia en
# su RESUELVE "LOTE 1 ... EXPEDIENTE Nº 6.22/28510.0057" con la empresa y la
# baja del LOTE 2 (TECNOLOGÍA SEÑALÉTICA, 0,50 %). CONTRATO_1: 0058, LOTE 2,
# 0,50 %; CONTRATO_2: 0057, LOTE 1, INDUSTRIAS LANEKO, 10,50 %.
RESOLUCION_REFERENCIA_CRUZADA_0058 = FIXTURES_DIR / "6.22_28510.0058_ADJUDICACION_1_p1.pdf"
CONTRATO_LOTE2_0058 = FIXTURES_DIR / "6.22_28510.0058_CONTRATO_1_p1.pdf"
CONTRATO_LOTE1_0057 = FIXTURES_DIR / "6.22_28510.0058_CONTRATO_2_p1.pdf"
# Sesión 2026-09-15: las dos primeras páginas de los mismos Contratos. La
# p.2 trae su importe: "Ascendiendo el importe de licitación del lote N a
# 2.400.000,00 € (IVA excluido)" y "CUARTO. El importe del contrato es de:
# - Base imponible ... 2.400.000,00 €".
CONTRATO_LOTE2_0058_CON_IMPORTE = FIXTURES_DIR / "6.22_28510.0058_CONTRATO_1_p1-2.pdf"
CONTRATO_LOTE1_0057_CON_IMPORTE = FIXTURES_DIR / "6.22_28510.0058_CONTRATO_2_p1-2.pdf"

# Repuestos de vía (`6.22/28510.0122`, 2 lotes; `0155` LOTE 1, `0156` LOTE
# 2): la Propuesta del LOTE 2 es el único documento de lotes, y el LOTE 1
# solo aparece en la referencia cruzada de la descripción del LOTE 2.
# CONTRATO_1: 0156, LOTE 2, 24,99 %; CONTRATO_2: 0155, LOTE 1, 24,90 %.
PROPUESTA_REFERENCIA_CRUZADA_0156 = FIXTURES_DIR / "6.22_28510.0156_ADJUDICACION_1_p1.pdf"

# Auditoría de las huérfanas recuperadas (misma sesión): 6 páginas reales de
# `4.26/28510.0020_ANEJO_8f2a33dd634a5454.pdf` (2 lotes) -- p.14, 15, 16,
# 17, 18 y 39 del original, en ese orden. p.14: "LOTE 1: SUBDIRECCIÓN DE
# OPERACIONES ESTE" dentro de la caja de la tabla (filas de título). p.15:
# continuación del LOTE 1; debajo de la tabla, "LOTE 2: SUBDIRECCIÓN DE
# OPERACIONES NORESTE", que abre la tabla de la p.16. p.17: continuación
# del LOTE 2, y debajo "TOTAL DE AMBOS LOTES: LOTE 1 ... LOTE 2 ...". p.18:
# prosa, sin tabla. p.39: cuadro de precios de la partida alzada, común a
# los dos lotes, sin ningún rastro de "LOTE" en su página.
ANEJO_LOTE_EN_TITULO_Y_COLA_0020 = FIXTURES_DIR / "4.26_28510.0020_ANEJO_1_lote_en_titulo_y_cola_p14-18_39.pdf"
CONTRATO_LOTE2_0156 = FIXTURES_DIR / "6.22_28510.0156_CONTRATO_1_p1.pdf"
CONTRATO_LOTE1_0155 = FIXTURES_DIR / "6.22_28510.0156_CONTRATO_2_p1.pdf"

# Sesión 2026-09-14, tercera parte. Aparatos de vía de ancho mixto o métrico
# (`6.23/28510.0051`, 2 lotes; `0060` LOTE 1, `0061` LOTE 2). Su Propuesta
# solo nombra el LOTE 1 (`0060`, 25,31 %); sus dos Contratos dicen LOTE 1 ->
# `0060` (25,31 %) y LOTE 2 -> `0061` (25,10 %). Del ANEJO_1, p.14, 38, 55 y
# 56 del original: p.14 abre "Lote 1: ANCHO MIXTO"; p.38 cierra el LOTE 1 y
# abre "Lote 2: ANCHO METRICO"; p.55-56, el anejo de criterios técnicos
# ("materiales a suministrar en el expediente “... 2 LOTES”"), con su propia
# numeración de códigos.
PROPUESTA_SOLO_LOTE1_0051 = FIXTURES_DIR / "6.23_28510.0051_ADJUDICACION_1_p1-2.pdf"
CONTRATO_LOTE1_0060 = FIXTURES_DIR / "6.23_28510.0051_CONTRATO_1_p1.pdf"
CONTRATO_LOTE2_0061 = FIXTURES_DIR / "6.23_28510.0051_CONTRATO_2_p1.pdf"
ANEJO_LOTES_Y_CRITERIOS_0051 = FIXTURES_DIR / "6.23_28510.0051_ANEJO_1_lotes_y_criterios_p14_38_55_56.pdf"

# El Contrato del LOTE 1 de `6.22/28510.0122` trae el pliego entero; el
# localizador no abre las páginas de sus cuadros salvo sueltas. p.116 del
# original: "LLote 1: SEMICAMBIOS..." (negrita simulada), sin tabla que
# abrir; p.122: tabla del LOTE 1 sin cabecera; p.127: "LLote 2:
# CRUZAMIENTOS..."; p.133: tabla del LOTE 2 sin cabecera.
CONTRATO_LOTE1_PLIEGO_0155 = FIXTURES_DIR / "6.22_28510.0156_CONTRATO_2_pliego_p116_122_127_133.pdf"

# Aparatos de vía, 5 lotes (`6.21/28510.0109`; `0112` LOTE 4, `0113` LOTE 5):
# sin documento de lotes, solo sus Contratos. CONTRATO_1: `0113`, LOTE 5,
# 3,00 %; CONTRATO_2: `0112`, LOTE 4, 18,30 %. Del ANEJO_1, p.18, 19, 42, 43
# y 49 del original: p.18 abre "Lote 1. Semicambios..." sin tabla; p.19,
# tabla del LOTE 1 sin cabecera; p.42, "Lote 4. Corazones..." y su tabla;
# p.43, su continuación; p.49, "Lote 5. Pequeño material".
CONTRATO_LOTE5_0113 = FIXTURES_DIR / "6.21_28510.0112_CONTRATO_1_p1.pdf"
CONTRATO_LOTE4_0112 = FIXTURES_DIR / "6.21_28510.0112_CONTRATO_2_p1.pdf"
ANEJO_LOTE4_0112 = FIXTURES_DIR / "6.21_28510.0109_ANEJO_1_lote4_p18_19_42_43_49.pdf"
# Sesión 2026-09-15: las dos primeras páginas del Contrato de `0112`; la p.2
# trae "El importe del contrato es de: - Base imponible ... 710.000,00 €".
CONTRATO_LOTE4_0112_CON_IMPORTE = FIXTURES_DIR / "6.21_28510.0112_CONTRATO_2_p1-2.pdf"

# Sesión 2026-09-15. Balasto, 6 lotes (`6.22/28510.0012`; `0016` es el LOTE
# 6). ANEJO_1, p.21 del original: tabla del LOTE 5 y, debajo, "LOTE 6: RAM
# NORTE" (P-1 65.000 m3 a 14,20 €, P-2 64.000 a 16,50 €, P-3 65.000 a 1,10 €,
# P-4 100.000 m3xkm a 0,12 €). Con los ajustes por defecto, `pdfplumber`
# pierde la primera columna de la tabla del LOTE 6 (ver
# `app.extraccion.tabla._AJUSTES_SEGUNDO_INTENTO`).
ANEJO_LOTES_5_Y_6_BALASTO_0016 = FIXTURES_DIR / "6.22_28510.0012_ANEJO_1_lotes5_6_p21.pdf"
