import hashlib


def calcular_clave_linea(codigo_precio, matricula, descripcion, orden_aparicion):
    """Clave no nula para una línea de catálogo dentro de un lote.
    Prioridad: codigo_precio > matricula > hash(descripcion + orden de aparición).
    Los nulos de Postgres no colisionan en un UNIQUE, así que la clave nunca
    puede ser nula si se quiere que el constraint detecte duplicados."""
    if codigo_precio:
        return codigo_precio.strip()
    if matricula:
        return matricula.strip()
    base = f"{descripcion.strip()}|{orden_aparicion}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()
