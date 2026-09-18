"""Cifras que salen como identificadores de glifo (`(cid:1005)`) en vez de
dígitos, y cómo descodificarlas sin adivinar (bloque 2, sesión 2026-09-18,
tercera parte).

**El problema.** Un PDF cuya fuente no trae tabla `ToUnicode` no dice qué
carácter es cada glifo; `pdfplumber` devuelve entonces el identificador crudo
del glifo. Una celda de precio real del corpus
(`6.26/28510.0064`, ANEJO_1 p.25, "11,97 €") sale así:

```
(cid:1005)(cid:1005),(cid:1013)(cid:1011)(cid:1004)(cid:1004) €
```

Hasta hoy eso era el final del camino: `parsear_numero_es` lo rechaza a
propósito (los dígitos del propio identificador parecen dígitos válidos y
colarlos daría un "precio" de veinte cifras) y la línea va a revisión.

**Por qué se puede descodificar sin adivinar.** En una fuente así los diez
dígitos son diez glifos consecutivos, así que el mapa es una traslación:
`cid -> cid - desplazamiento`. El desplazamiento no se supone: se acota con
los propios identificadores de la fila (todos tienen que caer en 0-9, lo que
deja un rango muy corto de candidatos) y **se confirma con la aritmética de
la fila**, que es una comprobación que se valida a sí misma:

```
cantidad × precio unitario = importe total
30.000 × 11,97 = 359.100,00   ✓ el documento trae ese mismo 359.100,00
```

Si la cuenta no sale, no hay descodificación: la fila se queda como estaba y
va a revisión. Nunca se escribe un número que el propio documento no confirme.

**Qué NO hace este módulo.** No compara descripciones y no tiene ninguna tabla
de desplazamientos "conocidos" que aplicar a ciegas. Dos filas del mismo
documento pueden salir una verificada y la otra a revisión, y eso es correcto.

**Segunda vía, para las tablas sin columna de totales** (bloque 5, sesión
2026-09-18, quinta parte): `confirmar_con_precio_conocido`, al final del
módulo. Sigue sin copiarse ningún precio de ninguna parte -- el número que se
escribe es el de los glifos de la propia celda; lo único que aporta otra fila
es confirmar el desplazamiento, que es justo lo que a una tabla sin totales le
falta. Ver el comentario largo que la precede.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Optional

from app.extraccion.normalizacion import parsear_numero_es

_TOKEN_CID = re.compile(r"\(cid:(\d+)\)")

# Cuánto puede separarse el importe recalculado del que trae el documento para
# seguir considerándose el mismo número. No es una tolerancia de "parecido":
# el documento redondea el total a dos decimales y el precio unitario puede
# traer cuatro (`13,5000`), así que el producto exacto y el total impreso
# pueden diferir en el último céntimo. Más que eso ya no es redondeo.
_TOLERANCIA_IMPORTE = Decimal("0.01")


def tiene_glifos_cid(texto: Optional[str]) -> bool:
    return bool(texto) and _TOKEN_CID.search(texto) is not None


def _ids_cid(texto: str) -> list[int]:
    return [int(m.group(1)) for m in _TOKEN_CID.finditer(texto)]


def desplazamientos_posibles(textos: list[Optional[str]]) -> list[int]:
    """Los desplazamientos con los que TODOS los identificadores de glifo de
    estas celdas caen en 0-9. Con los diez dígitos presentes solo queda uno;
    con menos dígitos distintos pueden quedar varios, y entonces decide la
    aritmética (`descodificar_fila`)."""
    ids = [i for texto in textos if texto for i in _ids_cid(texto)]
    if not ids:
        return []
    menor, mayor = min(ids), max(ids)
    if mayor - menor > 9:
        return []  # más de diez glifos distintos: no son solo dígitos
    return list(range(mayor - 9, menor + 1))


def descodificar(texto: str, desplazamiento: int) -> str:
    """Sustituye cada `(cid:N)` por el dígito `N - desplazamiento`. El
    llamador ya ha comprobado que todos caen en 0-9."""
    return _TOKEN_CID.sub(lambda m: str(int(m.group(1)) - desplazamiento), texto)


def _numero(texto: Optional[str]) -> Optional[Decimal]:
    if not texto:
        return None
    try:
        return parsear_numero_es(texto)
    except (ValueError, InvalidOperation, ArithmeticError):
        return None


@dataclass(frozen=True)
class FilaDescodificada:
    """`celdas` son las de la fila con los glifos ya sustituidos por dígitos.
    `desplazamiento` es el que lo consiguió, y `comprobacion` la cuenta que lo
    demuestra, en texto, para que quede en el motivo de la línea y se pueda
    rehacer a mano."""

    celdas: list[Optional[str]]
    desplazamiento: int
    comprobacion: str


def descodificar_fila(
    celdas: list[Optional[str]],
    indice_cantidad: Optional[int],
    indice_precio: Optional[int],
) -> Optional[FilaDescodificada]:
    """Descodifica la fila entera si —y solo si— algún desplazamiento hace que
    el precio unitario **cuadre con la aritmética de la propia fila**: existen
    en ella otras dos celdas, una cantidad y un importe, tales que
    `cantidad × precio = importe`.

    La única celda anclada al mapeo de cabecera es la del precio: es la que se
    va a guardar. La cantidad y el importe se buscan entre las demás celdas de
    la fila, sin exigir que estén en su columna nominal, porque en este tipo de
    tabla la fila suele venir desplazada por una columna fantasma (la cantidad
    "30.000" cae en la columna anterior a la que la cabecera llama CANTIDADES;
    `app.catalogo._recuperar_columna_fantasma` ya lo recupera después). **No es
    buscar "algo parecido"**: la prueba es la multiplicación, que o sale o no
    sale, y los dos valores que la sostienen se descartan después -- solo se
    guarda el precio.

    `indice_cantidad` se usa como preferencia para que la comprobación se lea
    con la cantidad de la columna correcta cuando sí está ahí.

    Devuelve `None` si no hay glifos, si no hay ningún desplazamiento posible,
    si la cuenta no sale con ninguno, o si sale con dos desplazamientos
    distintos (ambigüedad: no se elige)."""
    if indice_precio is None:
        return None
    if not any(tiene_glifos_cid(c) for c in celdas):
        return None

    validos: list[FilaDescodificada] = []
    for desplazamiento in desplazamientos_posibles(celdas):
        decodificadas = [
            descodificar(c, desplazamiento) if c and tiene_glifos_cid(c) else c for c in celdas
        ]
        precio = _numero(_en(decodificadas, indice_precio))
        if precio is None or precio <= 0:
            continue
        prueba = _buscar_prueba(decodificadas, precio, indice_precio, indice_cantidad)
        if prueba is None:
            continue
        cantidad, importe = prueba
        validos.append(
            FilaDescodificada(
                celdas=decodificadas,
                desplazamiento=desplazamiento,
                comprobacion=(
                    f"{_es(cantidad)} × {_es(precio)} = {_es(importe)}, que es el importe que trae la "
                    f"propia fila"
                ),
            )
        )
        if len(validos) > 1:
            return None  # dos lecturas distintas cuadran: no se elige ninguna
    return validos[0] if len(validos) == 1 else None


def _en(celdas: list[Optional[str]], indice: Optional[int]) -> Optional[str]:
    if indice is None:
        return None
    return celdas[indice] if 0 <= indice < len(celdas) else None


def _buscar_prueba(
    celdas: list[Optional[str]],
    precio: Decimal,
    indice_precio: int,
    indice_cantidad: Optional[int],
) -> Optional[tuple[Decimal, Decimal]]:
    """`(cantidad, importe)` de la fila que demuestran el precio, o `None`. Se
    prueba primero con la cantidad de su columna nominal; si no está o no
    cuadra, con cualquier otra celda numérica de la fila."""
    numeros = {
        indice: valor
        for indice, celda in enumerate(celdas)
        if indice != indice_precio and (valor := _numero(celda)) is not None and valor > 0
    }
    orden = sorted(numeros, key=lambda i: (i != indice_cantidad, i))
    for i in orden:
        esperado = numeros[i] * precio
        for j in numeros:
            if j == i:
                continue
            if abs(numeros[j] - esperado) <= _TOLERANCIA_IMPORTE:
                return numeros[i], numeros[j]
    return None


def _es(valor: Decimal) -> str:
    """Formato español, para que la comprobación se lea igual que el documento."""
    texto = f"{valor.normalize():f}"
    if "." in texto:
        entero, _, decimales = texto.partition(".")
    else:
        entero, decimales = texto, ""
    miles = f"{int(entero):,}".replace(",", ".")
    return f"{miles},{decimales}" if decimales else miles


# ---------------------------------------------------------------------------
# Segunda vía de comprobación: el precio del mismo código en otro lote
# ---------------------------------------------------------------------------
# Bloque 5, sesión 2026-09-18 (quinta parte). Hay cuadros de precios que no
# publican columna de totales -- la tabla del LOTE 3 de `6.26/28510.0064` es
# el caso real que lo motiva --, así que la aritmética de la propia fila
# (`descodificar_fila`, arriba) no tiene con qué comprobar nada y la celda se
# queda sin descodificar.
#
# **Lo que NO se hace aquí, y es lo importante.** No se copia el precio de
# otra fila. El número que se escribe sigue siendo el de los glifos de ESTA
# celda; lo único que aporta la otra fila es **confirmar cuál es el
# desplazamiento**, que es justo lo que a esta fila le falta por no tener
# totales. Se exige que un único desplazamiento de los posibles produzca un
# número que ya esté verificado para el MISMO código de precio en otro lote
# del mismo cuadro: si dos desplazamientos distintos dan cada uno un precio
# conocido, o si ninguno lo da, no se escribe nada y la fila se queda como
# estaba.
#
# Consecuencia medida en `6.26/28510.0064`: los cinco conceptos cuyo precio es
# el mismo en los seis lotes (P-1, P-3, P-4, P-5, P-6) se resuelven; P-2, el
# transporte, que vale distinto en cada lote, no se resuelve con ninguno de
# sus dos desplazamientos posibles y se queda a revisión. Es el resultado
# correcto: un precio que varía por lote no se puede confirmar con el de otro.


@dataclass(frozen=True)
class PrecioConfirmado:
    """El precio que sale de descodificar la celda con el desplazamiento que
    confirmó otra fila, y el valor de referencia que lo confirmó."""

    precio: Decimal
    desplazamiento: int
    referencia: Decimal


def confirmar_con_precio_conocido(
    texto_precio: Optional[str], precios_conocidos: set[Decimal]
) -> Optional[PrecioConfirmado]:
    """Descodifica una celda de precio en glifos usando como prueba que el
    resultado coincida con un precio ya verificado.

    Devuelve `None` si la celda no trae glifos, si no hay desplazamiento
    posible, si ninguno da un precio de `precios_conocidos`, o si más de uno
    lo da (ambigüedad: no se elige)."""
    if not tiene_glifos_cid(texto_precio) or not precios_conocidos:
        return None
    assert texto_precio is not None
    validos: list[PrecioConfirmado] = []
    for desplazamiento in desplazamientos_posibles([texto_precio]):
        precio = _numero(descodificar(texto_precio, desplazamiento))
        if precio is None or precio <= 0:
            continue
        for conocido in precios_conocidos:
            if precio == conocido:
                validos.append(PrecioConfirmado(precio, desplazamiento, conocido))
                break
        if len(validos) > 1:
            return None
    return validos[0] if len(validos) == 1 else None
