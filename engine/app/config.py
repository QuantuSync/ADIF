from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://adif:adif@postgres:5432/adif"
    document_storage_path: str = "/data/documentos"
    worker_poll_interval_seconds: float = 3.0

    # Mapeo de cabecera (CLAUDE.md sección 6): única etapa de la cascada que
    # llama al modelo. La clave nunca se hardcodea, viene del entorno.
    anthropic_api_key: Optional[str] = None
    anthropic_model: str = "claude-opus-5"

    # Scraping PCSP. Siempre headless (el contenedor no tiene ventana);
    # ver engine/app/scraping/pcsp.py sección "hallazgos headless".
    scraping_navigation_timeout_ms: int = 70000
    scraping_ui_timeout_ms: int = 35000
    scraping_contract_max_keep: int = 2
    scraping_require_contract_qr_csv_hint: bool = True


settings = Settings()
