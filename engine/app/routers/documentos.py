from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from app.auth import Usuario, get_current_user
from app.config import settings
from app.db import get_db
from app.interfaces.document_storage import LocalDiskStorage
from app.models import Documento
from sqlalchemy.orm import Session

router = APIRouter()

# Misma instancia de almacenamiento que el worker (app/worker.py), detrás de
# la interfaz de la sección 9.3: la API sirve el PDF, nunca lo toca la web
# directamente (CLAUDE.md sección 9.1).
_storage = LocalDiskStorage(settings.document_storage_path)


@router.get("/documentos/{documento_id}/archivo")
def descargar_documento(
    documento_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """CLAUDE.md sección 9.1: "la web nunca toca un PDF [...] solo llama a
    la API por HTTP" — este es el único sitio por el que la web puede mostrar
    "el documento al lado" en trazabilidad (punto 2) y en la cola de
    revisión (punto 3)."""
    documento = db.get(Documento, documento_id)
    if documento is None:
        raise HTTPException(status_code=404, detail="documento no encontrado")
    contenido = _storage.recuperar(documento.ruta_almacenamiento)
    return Response(
        content=contenido,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{documento.nombre_archivo}"'},
    )
