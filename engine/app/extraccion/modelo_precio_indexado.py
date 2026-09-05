"""Segunda familia de baja (CLAUDE.md sección 16, "Pendiente de resolver";
propuesta completa en docs/identidad-expediente.md sección 28): al menos 3
expedientes reales del corpus (`6.23/28510.0018`, `6.23/28510.0102`,
`6.25/28510.0016`, los tres Acuerdos Marco de suministro de carril nuevo)
fijan el precio de cada pedido futuro con

    P(t) = Precio_ofertado × Kt × Coeficiente_de_baja

en vez de una baja porcentual única de lote. `Kt` (índices IPRI de energía y
acero, publicados por el INE) y el "Coeficiente de baja" no están en ningún
documento de la licitación: los fija ADIF pedido a pedido, en el futuro,
contra el acuerdo marco ya adjudicado. `baja_lote`/`precio_adjudicado` deben
quedar `None` para este modelo -- no falta un dato que buscar mejor, el dato
no existe todavía.

Lo único de la fórmula que sí está fijado en la licitación es el
"coeficiente de transformación" (1,276 en los tres casos verificados), que se
aplica a los precios de referencia del PPT para obtener el precio ofertado
-- se extrae aquí porque es un dato real y estático, a diferencia de `Kt` y
del Coeficiente de baja.

Deliberadamente NO se extraen los pesos de `Kt` (0,26/0,33/0,41) ni los
grupos IPRI de energía/acero (encargo explícito de la sesión de trabajo
pendiente real, 2026-09-05): sin caso de uso real hoy que los consuma, y el
propio Kt es incalculable sin consultar al INE en el momento del pedido, algo
fuera del alcance de una extracción de PDF."""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from app.extraccion.normalizacion import parsear_numero_es
from app.extraccion.texto import PaginaTexto

# Frase ancla, idéntica en los tres documentos reales verificados (Contrato y
# Anejo/Pliego de los tres expedientes): "Coeficiente de baja: Ofertado por
# el licitador para cada pedido, debe de ser un valor menor o igual a 1."
# Suficientemente específica para no disparar con nada ajeno a este modelo.
_MARCADOR_RE = re.compile(
    r"Coeficiente de baja:\s*Ofertado por el licitador para cada pedido",
    re.IGNORECASE,
)

# "con un coeficiente de transformación para el P-1 de 1,276" (Adjudicación,
# Contrato) -- tolera el espacio suelto real visto en `6.25/28510.0016`
# ("de 1, 276", separación de miles rota por la extracción del PDF).
_COEFICIENTE_TRANSFORMACION_RE = re.compile(
    r"coeficiente de transformaci[oó]n(?:\s+ofertado)?\s+para el P-1 de\s*([\d]+(?:\s*[.,]\s*\d+)?)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ModeloPrecioIndexadoDetectado:
    coeficiente_transformacion: Optional[Decimal]
    pagina: int
    fragmento: str


def detectar_modelo_precio_indexado(paginas: list[PaginaTexto]) -> Optional[ModeloPrecioIndexadoDetectado]:
    """Primera página que trae el marcador de la fórmula de esta segunda
    familia. El coeficiente de transformación puede estar en una página
    distinta de la del marcador (los tres reales lo repiten cerca, pero no
    hay garantía) -- se busca en el documento entero, no solo en esa
    página."""
    pagina_marcador: Optional[PaginaTexto] = None
    for pagina in paginas:
        if _MARCADOR_RE.search(pagina.texto):
            pagina_marcador = pagina
            break
    if pagina_marcador is None:
        return None

    coeficiente: Optional[Decimal] = None
    for pagina in paginas:
        m = _COEFICIENTE_TRANSFORMACION_RE.search(pagina.texto)
        if m:
            coeficiente = parsear_numero_es(m.group(1))
            break

    return ModeloPrecioIndexadoDetectado(
        coeficiente_transformacion=coeficiente,
        pagina=pagina_marcador.numero,
        fragmento=_MARCADOR_RE.search(pagina_marcador.texto).group(0).strip(),
    )
