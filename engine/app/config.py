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

    # Orígenes permitidos para CORS (lista separada por comas): la API es la
    # única frontera con datos (CLAUDE.md sección 9.1), y el navegador del
    # cliente llama a esta dirección directamente desde fuera de la red de
    # Docker — sin cabeceras CORS, el navegador bloquea la respuesta aunque
    # la petición llegue bien (a diferencia de un servidor a servidor, que no
    # las necesita). Por defecto, el puerto donde corre "web" en local.
    cors_allowed_origins: str = "http://localhost:3000"

    # Cruce con el Excel de códigos (CLAUDE.md sección 7): ruta al
    # `Expedientes.xlsx` de referencia (columnas `Nº Interno`, `Nº
    # Expediente`, `MATRIZ`). Vacío por defecto: sin esta variable, el
    # sistema sigue funcionando pero ningún expediente cruza (CLAUDE.md
    # sección 7, "si no cruza, se deja vacío y se marca" — aplica igual si
    # el propio fichero no está disponible).
    codigos_proyecto_path: Optional[str] = None

    # Recuperación de trabajos huérfanos (CLAUDE.md sección 17, pendiente):
    # un trabajo `en_proceso` cuyo `bloqueado_en` supera este umbral se
    # reclama como si el worker que lo tenía hubiera desaparecido (contenedor
    # caído, dockerd reiniciado a mitad de ejecución). Varias veces el
    # timeout de navegación del scraping, que es el trabajo más largo hoy.
    worker_orphan_threshold_seconds: float = 300.0

    # Mapeo de cabecera (CLAUDE.md sección 6): única etapa de la cascada que
    # llama al modelo. La clave nunca se hardcodea, viene del entorno.
    # Haiku por defecto: la tarea es traducir una cabecera de tabla a un
    # diccionario de 6 claves, no razonamiento — Opus devolvía hasta 535
    # tokens de salida para esa misma tarea (CLAUDE.md sección 17.2).
    # Configurable por ANTHROPIC_MODEL para volver a un modelo mayor si una
    # cabecera concreta lo necesita.
    anthropic_api_key: Optional[str] = None
    anthropic_model: str = "claude-haiku-4-5"
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

    # Bloque 2, descubrimiento por sindicación (CLAUDE.md sección 24): ZIP
    # mensual de "licitacionesPerfilesContratanteCompleto3" bajo la
    # sindicación 643, verificado real en la sesión de mantenimiento
    # automático (agosto 2024 y la sesión previa de CLAUDE.md 17.1, mayo
    # 2025). Configurable para poder apuntar a un espejo o a un doble en
    # tests, nunca hardcodeado en el código de descubrimiento.
    sindicacion_base_url: str = "https://contrataciondelestado.es/sindicacion/sindicacion_643"
    # Departamentos de ADIF que el descubrimiento da de alta solos (CLAUDE.md
    # sección 24): "28510" es el único que usan los 45 expedientes del
    # corpus y todo lo documentado hasta ahora — el motor de extracción está
    # pensado para su patrón (cuadro de precios + baja única por lote), no
    # para la obra civil de otros departamentos ni de "ADIF Alta Velocidad".
    # Lista separada por comas; añadir un departamento nuevo es cambiar esta
    # variable, nunca tocar código.
    sindicacion_departamentos_adif: str = "28510"


settings = Settings()
