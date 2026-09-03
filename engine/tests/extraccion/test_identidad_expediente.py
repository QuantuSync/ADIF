"""CLAUDE.md sección 20, encargo de la sesión de corrección de identidad: el
código de un expediente es el que declara su propio Anuncio PCSP en "Número
de Expediente", nunca el término de búsqueda con el que se registró. Cubre
`corregir_identidad_expediente` de forma aislada (con el fixture real que
destapó el hallazgo, `ANUNCIO_PCSP_CON_MATRIZ`) y un caso de extremo a
extremo: el mismo escenario de los 8 expedientes reales mal etiquetados del
corpus, vía `ejecutar_extraccion_expediente`."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.extraccion.clasificador import clasificar
from app.extraccion.identidad_expediente import corregir_identidad_expediente
from app.extraccion.orquestador import ejecutar_extraccion_expediente
from app.extraccion.texto import extraer_texto
from app.interfaces.document_storage import DocumentStorage
from app.models import Documento, EstadoExpediente, Expediente, TipoDocumento, TrazaOrigen
from tests import fixtures as fx


class _StorageDirecta(DocumentStorage):
    def guardar(self, nombre: str, contenido: bytes) -> str:
        raise NotImplementedError

    def recuperar(self, ruta: str) -> bytes:
        return Path(ruta).read_bytes()

    def listar(self, prefijo: str = "") -> list[str]:
        raise NotImplementedError


def _item_anuncio_pcsp(db_session, expediente_id, ruta: Path, nombre: str):
    """Un `_Documento` de orquestador es duck-typed aquí (`.tipo`, `.paginas`,
    `.documento.id`) para no depender de la dataclass privada del módulo."""
    documento = Documento(
        expediente_id=expediente_id, tipo_documento=TipoDocumento.anuncio_pcsp,
        hash=f"hash-{nombre}", nombre_archivo=nombre, ruta_almacenamiento=str(ruta),
    )
    db_session.add(documento)
    db_session.commit()
    paginas = extraer_texto(ruta)
    assert clasificar(paginas).tipo == TipoDocumento.anuncio_pcsp
    return SimpleNamespace(documento=documento, tipo=TipoDocumento.anuncio_pcsp, paginas=paginas)


# --- corregir_identidad_expediente, aislada ------------------------------


def test_sin_anuncio_pcsp_no_hace_nada(db_session):
    expediente = Expediente(codigo_expediente="6.24/28510.0008")
    db_session.add(expediente)
    db_session.commit()

    motivo = corregir_identidad_expediente(db_session, expediente, [])

    assert motivo is None
    assert expediente.codigo_expediente == "6.24/28510.0008"


def test_codigo_ya_correcto_es_no_op(db_session):
    # El caso normal (37 de los 45 expedientes reales): el propio código de
    # búsqueda ya es el real, así que corregir no cambia nada ni escribe traza.
    expediente = Expediente(codigo_expediente="6.24/28510.0103")
    db_session.add(expediente)
    db_session.commit()
    item = _item_anuncio_pcsp(db_session, expediente.id, fx.ANUNCIO_PCSP_CON_MATRIZ, "ADJUDICACION_1.pdf")

    motivo = corregir_identidad_expediente(db_session, expediente, [item])

    assert motivo is None
    assert expediente.codigo_expediente == "6.24/28510.0103"
    assert expediente.codigo_matriz is None
    assert db_session.query(TrazaOrigen).count() == 0


def test_codigo_registrado_con_el_de_la_matriz_se_corrige(db_session):
    # Caso real de los 8 expedientes mal etiquetados (CLAUDE.md sección 20):
    # la fila se registró con el código de su MATRIZ (el término con el que
    # se buscó), no con el suyo propio.
    expediente = Expediente(codigo_expediente="2.18/04703.0019")
    db_session.add(expediente)
    db_session.commit()
    item = _item_anuncio_pcsp(db_session, expediente.id, fx.ANUNCIO_PCSP_CON_MATRIZ, "ADJUDICACION_1.pdf")

    motivo = corregir_identidad_expediente(db_session, expediente, [item])

    assert motivo is None
    assert expediente.codigo_expediente == "6.24/28510.0103"
    # El código con el que estaba registrado pasa a ser su matriz.
    assert expediente.codigo_matriz == "2.18/04703.0019"
    assert expediente.matriz_conflicto is not True

    traza = db_session.query(TrazaOrigen).filter_by(entidad_tipo="expediente", campo="codigo_expediente").one()
    assert traza.entidad_id == expediente.id
    assert traza.documento_id == item.documento.id
    assert traza.valor_extraido == "6.24/28510.0103"


def test_no_pisa_una_matriz_ya_declarada_distinta_marca_conflicto(db_session):
    expediente = Expediente(codigo_expediente="2.18/04703.0019", codigo_matriz="OTRA/MATRIZ.0001")
    db_session.add(expediente)
    db_session.commit()
    item = _item_anuncio_pcsp(db_session, expediente.id, fx.ANUNCIO_PCSP_CON_MATRIZ, "ADJUDICACION_1.pdf")

    corregir_identidad_expediente(db_session, expediente, [item])

    assert expediente.codigo_expediente == "6.24/28510.0103"
    assert expediente.codigo_matriz == "OTRA/MATRIZ.0001"
    assert expediente.matriz_conflicto is True


def test_codigo_real_ya_usado_por_otra_fila_no_se_fusiona(db_session):
    otra = Expediente(codigo_expediente="6.24/28510.0103")
    db_session.add(otra)
    expediente = Expediente(codigo_expediente="2.18/04703.0019")
    db_session.add(expediente)
    db_session.commit()
    item = _item_anuncio_pcsp(db_session, expediente.id, fx.ANUNCIO_PCSP_CON_MATRIZ, "ADJUDICACION_1.pdf")

    motivo = corregir_identidad_expediente(db_session, expediente, [item])

    assert motivo is not None
    assert "6.24/28510.0103" in motivo
    # No se tocó la identidad: fusionar dos filas es una decisión manual.
    assert expediente.codigo_expediente == "2.18/04703.0019"


def test_anuncios_que_discrepan_van_a_revision_sin_corregir(db_session):
    expediente = Expediente(codigo_expediente="X")
    db_session.add(expediente)
    db_session.commit()
    item_1 = _item_anuncio_pcsp(db_session, expediente.id, fx.ANUNCIO_PCSP_CON_MATRIZ, "a.pdf")
    item_2 = _item_anuncio_pcsp(db_session, expediente.id, fx.ANUNCIO_PCSP_SIN_MATRIZ, "b.pdf")

    motivo = corregir_identidad_expediente(db_session, expediente, [item_1, item_2])

    assert motivo is not None
    assert "6.24/28510.0103" in motivo and "6.24/28510.0193" in motivo
    assert expediente.codigo_expediente == "X"


# --- extremo a extremo, con el fixture real ------------------------------


def test_pedido_mal_etiquetado_se_renombra_y_deja_de_formar_ciclo(db_session):
    """Antes del arreglo, esta fila (registrada con el código de su matriz,
    igual que los 8 expedientes reales del corpus) se quedaba en
    `pendiente_revision` con "forma un ciclo": `_forma_ciclo` veía
    `codigo_matriz == codigo_expediente` y cortaba, porque la matriz
    declarada en el propio Anuncio PCSP es una autorreferencia mientras la
    fila siga mal etiquetada. Con la identidad corregida antes de resolver
    la matriz, deja de ser un ciclo real y pasa a `esperando_matriz`."""
    pedido = Expediente(codigo_expediente="2.18/04703.0019")
    db_session.add(pedido)
    db_session.commit()
    db_session.add(Documento(
        expediente_id=pedido.id, tipo_documento=TipoDocumento.otro,
        hash="h-pedido", nombre_archivo="ADJUDICACION_1.pdf",
        ruta_almacenamiento=str(fx.ANUNCIO_PCSP_CON_MATRIZ),
    ))
    db_session.commit()
    trabajo = SimpleNamespace(expediente_id=pedido.id)

    resultado = ejecutar_extraccion_expediente(db_session, _StorageDirecta(), trabajo, model_provider=None)

    db_session.refresh(pedido)
    assert pedido.codigo_expediente == "6.24/28510.0103"
    assert pedido.codigo_matriz == "2.18/04703.0019"
    assert pedido.estado == EstadoExpediente.esperando_matriz
    assert resultado["expediente"] == "6.24/28510.0103"

    matriz = db_session.query(Expediente).filter_by(codigo_expediente="2.18/04703.0019").one()
    assert pedido.matriz_expediente_id == matriz.id
