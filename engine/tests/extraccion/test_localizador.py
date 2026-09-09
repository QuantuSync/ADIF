from app.extraccion.localizador import localizar_paginas_candidatas
from app.extraccion.texto import extraer_texto
from tests import fixtures as fx


def test_anejo_guantes_localiza_solo_la_pagina_del_cuadro_de_precios():
    # El resto del documento es el Pliego de Prescripciones Técnicas
    # completo (CONTEXTO.md sección 3): el localizador no debe dejarse
    # engañar por el nombre "_ANEJO_1.pdf".
    paginas = extraer_texto(fx.ANEJO_PRECIOS_GUANTES)
    resultado = localizar_paginas_candidatas(paginas)

    assert [c.numero for c in resultado.candidatas] == [11]
    assert resultado.total_paginas == 12


def test_anejo_guantes_descarta_la_mayoria_de_paginas():
    paginas = extraer_texto(fx.ANEJO_PRECIOS_GUANTES)
    resultado = localizar_paginas_candidatas(paginas)
    # 1 de 12 candidata: 91,7% descartado, del mismo orden que el 83%
    # medido sobre el corpus completo (CONTEXTO.md sección 3).
    assert resultado.porcentaje_descartado > 0.9


def test_anejo_traviesas_localiza_las_tres_paginas_con_tabla_de_precios():
    # Este fixture trae, dentro del mismo PDF, dos anejos distintos: el
    # cuadro de precios "normal" (páginas 18-19) y un segundo cuadro dentro
    # del Anejo 2 "Criterios técnicos" (página 23) que repite los mismos
    # códigos con una columna distinta. Las dos son páginas de cuadro de
    # precios real y las dos deben localizarse, aunque ninguna mencione
    # "matrícula" (esta tabla no tiene esa columna en absoluto).
    paginas = extraer_texto(fx.ANEJO_PRECIOS_TRAVIESAS)
    resultado = localizar_paginas_candidatas(paginas)

    assert [c.numero for c in resultado.candidatas] == [18, 19, 23]
    assert resultado.total_paginas == 26


def test_anejo_traviesas_descarta_la_mayoria_de_paginas():
    paginas = extraer_texto(fx.ANEJO_PRECIOS_TRAVIESAS)
    resultado = localizar_paginas_candidatas(paginas)
    assert resultado.porcentaje_descartado > 0.85


def test_pagina_vacia_nunca_es_candidata():
    from app.extraccion.texto import PaginaTexto

    resultado = localizar_paginas_candidatas([PaginaTexto(numero=1, texto="")])
    assert resultado.candidatas == []


def test_pagina_con_prosa_larga_y_tabla_corta_sigue_siendo_candidata():
    # Sesión de expedientes sin publicar: 6.24/28510.0187_ANEJO_1.pdf página
    # 11 tiene un cuadro de precios real (2 líneas, "P01"/"P02") diluido por
    # un párrafo largo de prosa introductoria — densidad 0,0253, por debajo
    # del umbral antiguo (0,04). Bajado a 0,025 (medido contra el corpus
    # real completo antes de decidirlo, ver docstring del módulo) para no
    # perder esta página.
    paginas = extraer_texto(fx.ANEJO_PRECIOS_CODIGO_P_DOS_DIGITOS)
    resultado = localizar_paginas_candidatas(paginas)
    assert [c.numero for c in resultado.candidatas] == [1]


def test_parrafo_que_solo_menciona_precio_no_es_candidato():
    # Un párrafo de pliego puede mencionar "precio" de pasada sin ser una
    # tabla: un solo grupo de marcador, por muchas veces que aparezca, no
    # basta (CONTEXTO.md sección 3: localizar por contenido real de tabla, no
    # por una palabra suelta).
    from app.extraccion.texto import PaginaTexto

    texto = "El precio ofertado deberá respetar el precio máximo de licitación en todo momento." * 5
    resultado = localizar_paginas_candidatas([PaginaTexto(numero=1, texto=texto)])
    assert resultado.candidatas == []


# Bloque 5, cambios del cliente tras revisar el catálogo (sesión 2026-09-09):
# páginas de continuación de un cuadro de precios de varias páginas, que no
# repiten ninguna palabra de cabecera -- verificado contra
# `6.20/28510.0047_ANEJO_abd69efbdd39b552.pdf`, 42 páginas reales así.
from app.extraccion.texto import PaginaTexto  # noqa: E402

_PAGINA_CON_TABLA = (
    "MATRICULA DESIGNACION PLANO PRECIO CANTIDAD 610840051 BULON ARTICULACION 5,82 1 " * 4
)  # cabecera real + datos: marcadores y densidad numérica altos a propósito
_PAGINA_SOLO_DATOS = "610840051 BULON ARTICULACION 213-27-67 5,82 1 " * 8  # solo dígitos y texto, sin marcador
_PAGINA_PROSA = (
    "El presente pliego regula las condiciones generales del contrato administrativo "
    "y las obligaciones de las partes intervinientes en el procedimiento."
) * 3


def test_pagina_sin_marcadores_hereda_candidatura_de_la_anterior():
    paginas = [
        PaginaTexto(numero=1, texto=_PAGINA_CON_TABLA),
        PaginaTexto(numero=2, texto=_PAGINA_SOLO_DATOS),
    ]
    resultado = localizar_paginas_candidatas(paginas)

    numeros = [c.numero for c in resultado.candidatas]
    assert numeros == [1, 2]
    candidata_2 = next(c for c in resultado.candidatas if c.numero == 2)
    assert candidata_2.continuacion is True
    assert candidata_2.grupos_marcadores == frozenset()
    candidata_1 = next(c for c in resultado.candidatas if c.numero == 1)
    assert candidata_1.continuacion is False


def test_cadena_de_continuacion_se_corta_al_llegar_a_densidad_baja():
    paginas = [
        PaginaTexto(numero=1, texto=_PAGINA_CON_TABLA),
        PaginaTexto(numero=2, texto=_PAGINA_SOLO_DATOS),
        PaginaTexto(numero=3, texto=_PAGINA_PROSA),  # densidad baja: corta la cadena
        PaginaTexto(numero=4, texto=_PAGINA_SOLO_DATOS),  # ya no hereda de nadie
    ]
    resultado = localizar_paginas_candidatas(paginas)

    assert [c.numero for c in resultado.candidatas] == [1, 2]


def test_pagina_sin_marcadores_no_candidata_si_la_anterior_tampoco_lo_era():
    # Contraste: sin ninguna página candidata antes, la densidad sola no
    # basta -- evita que un documento sin ningún cuadro de precios real
    # empiece a aceptar páginas de pura casualidad numérica.
    paginas = [
        PaginaTexto(numero=1, texto=_PAGINA_PROSA),
        PaginaTexto(numero=2, texto=_PAGINA_SOLO_DATOS),
    ]
    resultado = localizar_paginas_candidatas(paginas)

    assert resultado.candidatas == []
