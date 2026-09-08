"""Estado explícito para distinguir "no he mirado / no hay dato" (`None`)
de "he mirado, encontré algo, pero determiné que no puedo atribuirlo con
confianza a este expediente" (`INVALIDADO`) -- sesión de medición del
alcance "Nº Lote: NNN" (2026-09-08,
docs/sesion-2026-09-08-auditoria-automatica.md).

Motivo real: `None` nunca pisa un valor ya guardado (`guardar_lineas_
catalogo`, la asignación de `lote.adjudicatario`...) -- correcto cuando de
verdad no se ha mirado esa fuente, o esta pasada no la trae. Pero cuando la
extracción SÍ mira un documento multi-lote y determina explícitamente que
el bloque no se puede atribuir con confianza (`app.extraccion.lotes_pcsp`,
`app.extraccion.baja`), un `None` corriente dejaba sobrevivir el valor de
una pasada anterior igual de equivocada -- el caso real que motiva esto:
12 de los 14 expedientes de "balasto" seguían mostrando el adjudicatario de
un lote hermano después de corregir la extracción, porque nadie le decía a
la asignación que ese hueco no era "no lo sé", era "sé que esto no es
fiable, bórralo".

Un solo símbolo compartido (no una instancia por campo): comprobar `valor is
INVALIDADO` es más barato y más claro que comparar contra una clase nueva
en cada sitio, y garantiza que todo el código de la cascada reconoce el
mismo símbolo."""
from __future__ import annotations


class _Invalidado:
    __slots__ = ()

    def __repr__(self) -> str:
        return "INVALIDADO"

    def __bool__(self) -> bool:
        # Se comporta como "falsy" en `if valor:` -- igual que `None` en las
        # comprobaciones existentes que ya tratan cualquier valor vacío como
        # "no hay nada que guardar". Lo que lo distingue de `None` es la
        # identidad (`is INVALIDADO`), no la verdad booleana.
        return False


INVALIDADO = _Invalidado()
