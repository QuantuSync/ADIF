"""Orden del catálogo (bloque 3, sesión 2026-09-18).

El desempate por `expediente + lote + orden_aparicion` no es un orden total:
`orden_aparicion` es la posición de la fila dentro de SU tabla, así que dos
documentos del mismo expediente y lote pueden dar el mismo valor, y entonces
el motor de base de datos devuelve las filas empatadas en el orden que
quiera. Efecto real medido: tres parejas de filas contiguas intercambiaban
posición entre dos exportaciones idénticas. `LineaCatalogo.id` cierra el
orden."""
from decimal import Decimal

from sqlalchemy.dialects import postgresql

from app.catalogo_consulta import consultar_catalogo
from app.models import Expediente, LineaCatalogo, Lote


def _sembrar_empate(db_session) -> Expediente:
    expediente = Expediente(codigo_expediente="6.21/28510.0109")
    db_session.add(expediente)
    db_session.commit()
    lote = Lote(expediente_id=expediente.id, identificador_lote="1")
    db_session.add(lote)
    db_session.commit()
    # Cuatro líneas de DOS documentos distintos con el mismo
    # `orden_aparicion`: el empate que dejaba el orden a merced del motor.
    for i, clave in enumerate(("A-1", "B-1", "A-2", "B-2")):
        db_session.add(LineaCatalogo(
            expediente_id=expediente.id, lote_id=lote.id, clave_linea=clave,
            codigo_precio=clave, orden_aparicion=i % 2, descripcion=f"PIEZA {clave}",
            precio_unitario=Decimal("1.00"),
        ))
    db_session.commit()
    return expediente


def test_las_lineas_empatadas_salen_siempre_en_el_mismo_orden(db_session):
    _sembrar_empate(db_session)
    primera = [l.id for l, *_ in consultar_catalogo(db_session, tamano_pagina=50).filas]
    segunda = [l.id for l, *_ in consultar_catalogo(db_session, tamano_pagina=50).filas]
    assert primera == segunda
    # Y dentro de cada grupo de empate, por `id` ascendente.
    por_orden: dict[int, list[int]] = {}
    for linea, *_ in consultar_catalogo(db_session, tamano_pagina=50).filas:
        por_orden.setdefault(linea.orden_aparicion, []).append(linea.id)
    for ids in por_orden.values():
        assert ids == sorted(ids)


def test_el_id_es_el_ultimo_desempate_de_la_consulta(db_session):
    """La comprobación de arriba pasaría por casualidad si el motor
    devolviera las filas empatadas en orden de inserción. Esta fija el
    criterio donde vive: el `ORDER BY` termina en `lineas_catalogo.id`."""
    _sembrar_empate(db_session)
    consultas: list[str] = []
    original = db_session.execute

    def espia(stmt, *args, **kwargs):
        consultas.append(str(stmt.compile(dialect=postgresql.dialect())))
        return original(stmt, *args, **kwargs)

    db_session.execute = espia
    try:
        consultar_catalogo(db_session, tamano_pagina=50)
    finally:
        db_session.execute = original

    listados = [c for c in consultas if "ORDER BY" in c]
    assert listados, "la consulta del listado tiene que llevar ORDER BY"
    for consulta in listados:
        assert consulta.rstrip().split("ORDER BY")[-1].split("\n")[0].strip().endswith("lineas_catalogo.id")


def test_el_orden_alfabetico_tambien_cierra_por_id(db_session):
    _sembrar_empate(db_session)
    primera = [l.id for l, *_ in consultar_catalogo(db_session, orden="alfabetico", tamano_pagina=50).filas]
    segunda = [l.id for l, *_ in consultar_catalogo(db_session, orden="alfabetico", tamano_pagina=50).filas]
    assert primera == segunda
    # `orden_aparicion` manda antes que el `id`: primero las dos de
    # `orden_aparicion` 0 y luego las dos de 1, cada pareja por `id`.
    assert primera == [1, 3, 2, 4]
