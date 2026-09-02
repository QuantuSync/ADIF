"""Conjunto fijo de prueba para la cascada de extracción.

CLAUDE.md sección 13: "No metas los 187 PDFs en el repo. Deja un conjunto fijo
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

# Anuncio PCSP (formulario estándar, CLAUDE.md sección 3): "Anuncio de
# adjudicación" con la sección "Licitación basada en el acuerdo marco" que
# trae la MATRIZ.
ANUNCIO_PCSP_CON_MATRIZ = FIXTURES_DIR / "2.18_04703.0019_ADJUDICACION_1.pdf"

# Anuncio PCSP de un procedimiento directo (Negociado sin publicidad), sin
# acuerdo marco de por medio: no trae MATRIZ.
ANUNCIO_PCSP_SIN_MATRIZ = FIXTURES_DIR / "6.24_28510.0193_ADJUDICACION_1.pdf"

# Propuesta LC.27. Caso central del proyecto (CLAUDE.md sección 4): licitación
# y adjudicación son ambas 138.000,00 €, baja declarada del 54,00 %. La
# fórmula ingenua (1 - adjudicado/licitación) da 0 %.
PROPUESTA_LC27_PRECIOS_UNITARIOS = FIXTURES_DIR / "6.24_28510.0008_ADJUDICACION_1.pdf"

# Propuesta LC.27 con adjudicación a una UTE de 3 empresas y baja del 0,50 %
# sobre una licitación de 1.000.000,00 € (mismo importe en licitación y
# adjudicación: segundo caso real de precios unitarios).
PROPUESTA_LC27_UTE = FIXTURES_DIR / "6.24_28510.0088_ADJUDICACION_1.pdf"

# Resolución de Adjudicación (plantilla L9_AF.01-FE, distinta de LC.27; ver
# CLAUDE.md sección 17). Tercer caso real de precios unitarios: 800.000,00 €
# en licitación y adjudicación, baja declarada del 4,50 %.
RESOLUCION_ADJUDICACION = FIXTURES_DIR / "6.24_28510.0124_ADJUDICACION_1.pdf"

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
# repetida dentro del mismo documento. CLAUDE.md sección 3: "11 variantes
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
