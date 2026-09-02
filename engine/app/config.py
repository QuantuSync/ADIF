from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # "model_cache_dir" empieza por "model_", el prefijo que pydantic
    # reserva para su propia API (model_config, model_fields...). Sin esto,
    # arranca con un UserWarning en cada proceso que importa app.config.
    model_config = {"protected_namespaces": ()}

    database_url: str = "postgresql+psycopg://adif:adif@postgres:5432/adif"
    document_storage_path: str = "/data/documentos"
    worker_poll_interval_seconds: float = 3.0

    # Recuperación de trabajos huérfanos (CLAUDE.md sección 17, pendiente):
    # un trabajo `en_proceso` cuyo `bloqueado_en` supera este umbral se
    # reclama como si el worker que lo tenía hubiera desaparecido (contenedor
    # caído, dockerd reiniciado a mitad de ejecución). Varias veces el
    # timeout de navegación del scraping, que es el trabajo más largo hoy.
    worker_orphan_threshold_seconds: float = 300.0

    # Mapeo de cabecera (CLAUDE.md sección 6): única etapa de la cascada que
    # llama al modelo. La clave nunca se hardcodea, viene del entorno.
    anthropic_api_key: Optional[str] = None
    anthropic_model: str = "claude-opus-5"
    # Solo necesario si ANTHROPIC_API_KEY es una clave ligada a identidad
    # (creada en la consola bajo un usuario, no una API key clásica de
    # workspace): la API la exige en la cabecera `anthropic-workspace-id` de
    # cada petición. Ver docstring de AnthropicModelProvider.
    anthropic_workspace_id: Optional[str] = None

    # Caché en disco de `CachedModelProvider` (interfaces/model_provider.py):
    # solo para desarrollo local, nunca para producción — evita pagar la
    # misma cabecera dos veces mientras se itera contra la API real. Vacío
    # por defecto: sin esta variable, el worker llama a Anthropic directo,
    # sin decorador de caché de disco (la caché persistente de firma en
    # `cache_mapeo_cabecera` sigue activa siempre, es otra cosa).
    model_cache_dir: Optional[str] = None

    # Scraping PCSP. Siempre headless (el contenedor no tiene ventana);
    # ver engine/app/scraping/pcsp.py sección "hallazgos headless".
    scraping_navigation_timeout_ms: int = 70000
    scraping_ui_timeout_ms: int = 35000
    scraping_contract_max_keep: int = 2
    scraping_require_contract_qr_csv_hint: bool = True


settings = Settings()
