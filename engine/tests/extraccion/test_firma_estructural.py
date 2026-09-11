from app.extraccion.firma_estructural import calcular_firma_estructural, clasificar_columnas


def test_firma_estructural_distingue_columna_fantasma_desplazada():
    # Caso real, Bloque 3 (`6.22/28510.0126_ANEJO_57694f5d5dacb236.pdf`): la
    # tabla con cabecera real de la p.15 trae una columna fantasma vacía
    # justo antes de la descripción; las tablas sin cabecera de las p.19/20
    # no la traen, así que la descripción cae un índice antes -- las dos
    # formas tienen 8 columnas, pero NUNCA deben compartir firma estructural
    # (heredar el mapeo de la primera a la segunda desplazaría descripcion
    # sobre la columna de unidad).
    filas_p15 = [
        ["P-001", "611150110", "", "DS-B1-54-320/230-0,11-CR-D", "UD.", "1", "", "122.624,14 €"],
        ["P-002", "611150111", "", "DS-B1-54-320/230-0,11-CR-I", "UD.", "1", "", "107.297,32 €"],
        ["P-003", "611150098", "", "DS-B1-54-320/417-0,09-CR-D", "UD.", "1", "", "116.745,94 €"],
    ]
    filas_p19 = [
        ["P-142", "612050110", "ES-C-54-250-0,11-CR-D-3808", "UD.", "0", "", "224.251,50 €", ""],
        ["P-143", "612050111", "ES-C-54-250-0,11-CR-I-3808", "UD.", "0", "", "224.251,50 €", ""],
        ["P-144", "612050113", "ES-C-54-250-0,11-CR-I-3742", "UD.", "0", "", "224.251,50 €", ""],
    ]
    assert calcular_firma_estructural(filas_p15) != calcular_firma_estructural(filas_p19)


def test_firma_estructural_misma_forma_da_misma_firma():
    # Dos tablas sin cabecera reales del mismo documento (p.19 y p.20), misma
    # forma de verdad: deben compartir firma para que se pueda reutilizar el
    # mapeo sin llamar otra vez al modelo. Caso real, `6.22/28510.0126` p.20:
    # de 44 filas, solo UNA trae un valor suelto en la columna 5 (normalmente
    # vacía) -- no debe cambiar el tipo de la columna entera (umbral de
    # relleno mínimo, `_UMBRAL_RELLENO_MINIMO`).
    filas_p19 = [
        ["P-142", "612050110", "ES-C-54-250-0,11-CR-D-3808", "UD.", "0", "", "224.251,50 €", ""],
    ] * 10
    filas_p20 = [
        ["P-186", "616060110", "ESH-P1-60-250-0,11-CR-D-TC-3808", "UD.", "0", "", "305.071,32 €", ""],
    ] * 9 + [
        ["P-188", "616060090", "ESH-P1-60-318-0,09-CR-D-TC-3808", "UD.", "0", "358.669,23 €", "341.594,98 €", ""],
    ]
    assert calcular_firma_estructural(filas_p19) == calcular_firma_estructural(filas_p20)


def test_firma_estructural_distinto_numero_columnas_nunca_coincide():
    filas_a = [["P-1", "611150110", "Descripción larga de verdad", "12,50 €"]]
    filas_b = [["P-1", "611150110", "Descripción larga de verdad", "UD.", "12,50 €"]]
    assert calcular_firma_estructural(filas_a) != calcular_firma_estructural(filas_b)


def test_firma_estructural_vacia_sin_filas():
    assert calcular_firma_estructural([]) == (0, ())


# --- Bloque 3, sesión 2026-09-11: dos categorías nuevas, verificadas contra
# las 33 filas reales de `ANEJO_abd69efbdd39b552.pdf` p.35 (trío 0042/0046/
# 0047) -- ver `app.extraccion.mapeo_cabecera.derivar_mapeo_por_contenido`.


def test_clasificar_columnas_distingue_referencia_normativa_de_descripcion():
    filas = [
        ["612260110", "SCV-C-60-ID-318", "P16.0785.02", "03.361.130.2", "15.377,63 €"],
        ["612260115", "SCV-C-60-II-318", "P16.0785.24", "03.361.130.2", "15.468,40 €"],
        ["615260093", "SCI-P-60-II-318", "P16.3589.05 SIMETRICO", "03.361.130.2", "15.561,96 €"],
        ["619350615", "CZI-AG-3HD-B1-54-0,11-R", "P16.2316.00 (S)", "03.361.140.1", "15.571,69 €"],
    ]
    tipos = clasificar_columnas(filas)
    assert tipos == ["matricula", "texto_unico", "referencia_alfanumerica", "referencia_normativa", "precio"]


def test_clasificar_columnas_no_confunde_codigo_precio_real_con_referencia():
    # "P-001" (código de precio real, con guion) nunca debe clasificarse
    # como "referencia_alfanumerica" (que exige el dígito pegado a la letra,
    # sin guion) -- si lo hiciera, `derivar_mapeo_por_contenido` no podría
    # distinguir un código de precio real de una referencia de plano.
    filas = [["P-001", "BRIDA", "3,50 €"], ["P-002", "PLACA", "7,20 €"]]
    tipos = clasificar_columnas(filas)
    assert tipos[0] == "codigo_repetido"
