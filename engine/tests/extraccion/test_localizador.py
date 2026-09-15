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


# Sesión 2026-09-14: continuación con descripciones largas en prosa técnica
# (forma real de `6.21/28510.0109_ANEJO_7bfc92005f43e68e.pdf` p.24: dos filas
# por página, 30 líneas de descripción cada una) -- densidad de párrafo, muy
# por debajo de `UMBRAL_DENSIDAD_CONTINUACION`, pero con identificadores de
# fila.
_PAGINA_CONTINUACION_PROSA = (
    "Corazón de punta móvil para desvío o semiescape de radio a izquierdas o derechas con\n"
    "inclinación de rodadura, dotado de punta y contrapunta de perfil bajo asimétrico con talón\n"
    "forjado, prolongaciones en el lado anterior y acero de grado soldable. Incluye cuna de acero\n"
    "17.000 P-71 Cruzamiento al manganeso con patas de liebre de perfil simétrico 11 190.772,\n"
    "de alma gruesa y antenas anteriores con prolongaciones y acero de grado soldable.\n"
) * 2 + "17.000 P-72 Cruzamiento taladros, tornillería y todos los elementos necesarios 11 161.096,\n"


def test_continuacion_con_prosa_tecnica_entra_por_identificadores_de_fila():
    from app.extraccion.localizador import UMBRAL_DENSIDAD_CONTINUACION, _densidad_numerica

    assert _densidad_numerica(_PAGINA_CONTINUACION_PROSA) < UMBRAL_DENSIDAD_CONTINUACION
    paginas = [
        PaginaTexto(numero=1, texto=_PAGINA_CON_TABLA),
        PaginaTexto(numero=2, texto=_PAGINA_CONTINUACION_PROSA),
        PaginaTexto(numero=3, texto=_PAGINA_CONTINUACION_PROSA),
    ]
    resultado = localizar_paginas_candidatas(paginas)
    assert [c.numero for c in resultado.candidatas] == [1, 2, 3]
    assert all(c.continuacion for c in resultado.candidatas[1:])


def test_prosa_sin_identificadores_tras_una_tabla_no_es_continuacion():
    prosa_con_cifras = (
        "El plazo de garantía de los suministros será de 24 meses, a contar desde la fecha de\n"
        "recepción, y el importe máximo de 1.250,00 € por pedido se revisará cada 12 meses.\n"
    ) * 4
    paginas = [
        PaginaTexto(numero=1, texto=_PAGINA_CON_TABLA),
        PaginaTexto(numero=2, texto=prosa_con_cifras),
    ]
    assert [c.numero for c in localizar_paginas_candidatas(paginas).candidatas] == [1]


# Forma real de `6.21/28510.0016_ANEJO_e40fc4e4546ec90b.pdf` p.13: cabecera
# en fuente sin mapa Unicode (ningún marcador legible), filas con matrícula e
# importe.
_PAGINA_CABECERA_ILEGIBLE = (
    "(cid:69)(cid:465)(cid:3)(cid:68)(cid:4)(cid:100) (cid:90)(cid:28)(cid:38)(cid:856)\n"
    "03PAI-\n642190360 RT58 ALMOHADILLA PARA AISLADORES 100 1,53 €\n032-01\n"
    "03PAI-\n642190370 RT70 ALMOHADILLA PARA AISLADORES 30 18,29 €\n033-01\n"
    "01PAT-\n642530150 L5a PASADOR PARA MORDAZA DE ATIRANTADO 200 0,86 €\n023-01\n"
)


def test_arranque_de_tabla_sin_cabecera_legible_entra_por_filas_de_datos():
    paginas = [
        PaginaTexto(numero=1, texto=_PAGINA_PROSA),
        PaginaTexto(numero=2, texto=_PAGINA_CABECERA_ILEGIBLE),
        PaginaTexto(numero=3, texto=_PAGINA_CONTINUACION_PROSA),
    ]
    resultado = localizar_paginas_candidatas(paginas)
    assert [c.numero for c in resultado.candidatas] == [2, 3]
    assert resultado.candidatas[0].sin_cabecera_legible is True
    assert resultado.candidatas[1].continuacion is True


def test_menos_de_tres_filas_de_datos_sin_cabecera_no_bastan():
    dos_filas = "642190360 RT58 ALMOHADILLA 100 1,53 €\n642190370 RT70 ALMOHADILLA 30 18,29 €\n" + _PAGINA_PROSA
    resultado = localizar_paginas_candidatas([PaginaTexto(numero=1, texto=dos_filas)])
    assert resultado.candidatas == []


def test_identificador_de_fila_admite_sufijo_en_mayuscula_y_matricula_con_puntos():
    from app.extraccion.localizador import _identificadores_fila

    assert _identificadores_fila("GAV 1500 P-39B Contraaguja 1,4 4.292,05") == 1
    assert _identificadores_fila("PAV 1500 P-41 A Aguja 1,7 8.783,64") == 1
    assert _identificadores_fila("643.910.630 G51 GUARDACABOS 1000 0,40 €") == 1
    # `4.26/28510.0020_ANEJO_8f2a33dd634a5454.pdf` p.40: "Cod0013".
    assert _identificadores_fila("Cod0013 Ud. JUEGO DE TIMONERÍA DE MANDO Y 1262,94") == 1
    # "P1" suelto (sin guion) aparece en prosa ("tipo P o P1 de radio 1500"):
    # no cuenta como prueba de fila.
    assert _identificadores_fila("desvío polivalente tipo P o P1 de radio 1500") == 0


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


def test_tabla_con_cabecera_mat_abreviada_se_abre():
    # `6.21/28510.0041_ANEJO_637638edb5567514.pdf` p.3 (el mismo texto que la
    # p.113 de su Contrato): "Mat." por "Matrícula", "Designación" y
    # "Medición estimada" -- solo el grupo "precio" era reconocible, y con dos
    # filas no llega a `MIN_FILAS_DATO_SIN_CABECERA`.
    texto = (
        "2 LISTADO DE MATERIALES A SUMINISTRAR\n"
        "Medición Precio\n"
        "Mat. Designación IMPORTE\n"
        "estimada unitario\n"
        "601061018 CARRIL 60E1 R350 SIN TALADRAR 18 M 2211,67 m 49,39 € 109.238,72 €\n"
        "601061036 CARRIL 60E1 R350 SIN TALADRAR 36 M 7.800 m 50,10 € 390.761,28 €\n"
        "PARTIDA ALZADA A JUSTIFICAR PARA IMPREVISTOS 50.000,00 €\n"
    )
    resultado = localizar_paginas_candidatas([PaginaTexto(numero=3, texto=texto)])

    assert [c.numero for c in resultado.candidatas] == [3]
    assert "matricula" in resultado.candidatas[0].grupos_marcadores


def test_cuadro_pequeno_entre_prosa_entra_por_sus_filas_aunque_baje_de_la_densidad():
    # `6.20/28510.0080_CONTRATO` p.106 (densidad 0,023): el cuadro de precios
    # de balasto entre dos párrafos largos. El P-4 (m3 x km, 0,12 €) solo
    # está en esta página.
    texto = (
        "resolución del mismo o acordar la continuidad de su ejecución con imposición de nuevas\n"
        "penalidades.\n"
        "5. Adif tendrá las mismas facultades a que se refieren los apartados anteriores respecto al\n"
        "incumplimiento por parte del contratista de los plazos parciales, cuando la demora en el\n"
        "cumplimiento de aquellos haga presumir razonablemente la imposibilidad de cumplir el\n"
        "plazo total.\n"
        "9. PRECIOS UNITARIOS Y PRESUPUESTO DE LICITACION.\n"
        "A continuación se detalla la composición de los precios unitarios:\n"
        "CUADRO DE PRECIOS\n"
        "Ref. ud Denominación Precio\n"
        "m3 de balasto producido según especificaciones del Pliego de\n"
        "Prescripciones Técnicas, incluso preparación de las eras de\n"
        "P-1 m3 12,40 €\n"
        "almacenamiento en cantera, acopio del material en cantera y\n"
        "vigilancia de acopios.\n"
        "P-2 m3 M3 de balasto transportado al punto de carga ofertado 9,60 €\n"
        "Carga y enrasado del balasto transportado en las tolvas en los puntos\n"
        "P-3 m3 1,08 €\n"
        "de carga.\n"
        "m3 x km de balasto transportado a los puntos de carga que figuran en\n"
        "P-4 m3xkm 0,12 € el pliego diferente al ofertado\n"
        "P-5 1 Partida alzada a justificar de acondicionamiento de puntos de carga 50.000 €\n"
        "Los precios llevan incluido los gastos generales y el beneficio industrial.\n"
        "Los precios unitarios que figuran en el presente pliego se consideran como límite superior para\n"
        "que las ofertas puedan ser admitidas.\n"
        "Si durante la gestión del contrato fuera preciso realizar suministros en puntos distintos a los\n"
        "recogidos en el presente pliego, se abonarán tomando como referencia los precios ofertados\n"
        "por el licitador, variando unicamente la distancia entre la cantera ofertada y el nuevo punto de\n"
        "suministro.\n"
        "El licitador deberá presentar su oferta cumplimentando la totalidad de los precios unitarios del\n"
        "presupuesto,. salvo la del precio unitario de la partida alzada (P5), que no admite baja alguna,\n"
        "debiendo ser el mismo de la licitación (50.000 €).\n"
        "La partida alzada está destinada a las actuaciones requeridas para el acondicionamiento inicial\n"
        "de los cargaderos. Las actuaciones para el mantenimiento de los mismos en condiciones\n"
        "adecuadas están incluidas en el precio del balasto suministrado.\n"
        "El licitador deberá incluir declaración jurada de la distancia existente entre la cantera con la\n"
        "que se presenta a esta licitación y el punto de carga ofertado, incluyendo un mapa con el cálculo\n"
        "de la distancia.\n"
    )
    from app.extraccion.localizador import UMBRAL_DENSIDAD_NUMERICA, _densidad_numerica

    assert _densidad_numerica(texto) < UMBRAL_DENSIDAD_NUMERICA
    resultado = localizar_paginas_candidatas([PaginaTexto(numero=106, texto=texto)])
    assert [c.numero for c in resultado.candidatas] == [106]


def test_prosa_por_debajo_de_la_densidad_sin_filas_de_datos_sigue_fuera():
    resultado = localizar_paginas_candidatas([PaginaTexto(numero=1, texto=_PAGINA_PROSA)])
    assert resultado.candidatas == []


def test_cuadro_de_un_articulo_en_pagina_de_prosa_es_candidata():
    # Sesión 2026-09-15 (`3.24/28510.0132`): densidad 0,023, sin
    # identificadores de fila; la línea "Concepto Unidades Importe" es la
    # cabecera del cuadro.
    paginas = extraer_texto(fx.PPT_RESISTENCIA_PATRON_0132)
    resultado = localizar_paginas_candidatas(paginas)

    assert [c.numero for c in resultado.candidatas] == [1]


def test_prosa_que_nombra_precio_y_cantidad_en_lineas_distintas_no_es_candidata():
    from app.extraccion.texto import PaginaTexto

    paginas = [PaginaTexto(numero=1, texto=(
        "El adjudicatario tiene derecho al abono con arreglo al precio convenido.\n"
        "La descripción del suministro figura en el apartado 3.\n"
        "Las cantidades son estimadas.\n"
    ))]

    assert localizar_paginas_candidatas(paginas).candidatas == []
