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
    # única frontera con datos (CONTEXTO.md sección 9.1), y el navegador del
    # cliente llama a esta dirección directamente desde fuera de la red de
    # Docker — sin cabeceras CORS, el navegador bloquea la respuesta aunque
    # la petición llegue bien (a diferencia de un servidor a servidor, que no
    # las necesita). Por defecto, el puerto donde corre "web" en local.
    #
    # Los dos orígenes (sesión de diagnóstico "Failed to fetch", 2026-09-06):
    # CORS compara el origen EXACTO (esquema+host+puerto), y "localhost" y
    # "127.0.0.1" son dos orígenes distintos para el navegador aunque
    # resuelvan al mismo sitio. Verificado en vivo: con un único origen
    # configurado, un navegador abierto en el otro veía la página cargar
    # bien (la navegación no pasa por CORS) pero cada fetch() a la API
    # fallaba con "Failed to fetch" sin más detalle -- indistinguible a
    # simple vista de la API estando caída. Cubrir los dos por defecto evita
    # que cuál de las dos formas escriba alguien en la barra de direcciones
    # decida si la web funciona.
    cors_allowed_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Cruce con el Excel de códigos (CONTEXTO.md sección 7): ruta al
    # `Expedientes.xlsx` de referencia (columnas `Nº Interno`, `Nº
    # Expediente`, `MATRIZ`). Vacío por defecto: sin esta variable, el
    # sistema sigue funcionando pero ningún expediente cruza (CONTEXTO.md
    # sección 7, "si no cruza, se deja vacío y se marca" — aplica igual si
    # el propio fichero no está disponible).
    codigos_proyecto_path: Optional[str] = None

    # Recuperación de trabajos huérfanos (CONTEXTO.md sección 17, pendiente):
    # un trabajo `en_proceso` cuyo `bloqueado_en` supera este umbral se
    # reclama como si el worker que lo tenía hubiera desaparecido (contenedor
    # caído, dockerd reiniciado a mitad de ejecución). Varias veces el
    # timeout de navegación del scraping, que es el trabajo más largo hoy.
    worker_orphan_threshold_seconds: float = 300.0

    # Mapeo de cabecera (CONTEXTO.md sección 6): única etapa de la cascada que
    # llama al modelo. La clave nunca se hardcodea, viene del entorno.
    # Modelo pequeño por defecto: la tarea es traducir una cabecera de tabla
    # a un diccionario de 6 claves, no razonamiento — un modelo mayor
    # probado en la misma tarea devolvía hasta 535 tokens de salida sin
    # necesitarlo (CONTEXTO.md sección 17.2). El identificador de modelo se
    # configura por MODEL_ID, sin valor por defecto en el repositorio
    # (depende del proveedor de modelo elegido en cada despliegue) —
    # requerido para que APIModelProvider pueda arrancar.
    model_api_key: Optional[str] = None
    model_id: Optional[str] = None
    # Solo necesario si MODEL_API_KEY es una clave ligada a identidad
    # (creada en la consola bajo un usuario, no una API key clásica de
    # workspace): la API de este proveedor la exige en una cabecera propia
    # de cada petición. Ver docstring de APIModelProvider.
    model_workspace_id: Optional[str] = None

    # Caché en disco de `CachedModelProvider` (interfaces/model_provider.py):
    # solo para desarrollo local, nunca para producción — evita pagar la
    # misma cabecera dos veces mientras se itera contra la API real. Vacío
    # por defecto: sin esta variable, el worker llama a la API del proveedor
    # directo, sin decorador de caché de disco (la caché persistente de
    # firma en `cache_mapeo_cabecera` sigue activa siempre, es otra cosa).
    model_cache_dir: Optional[str] = None

    # Scraping PCSP. Siempre headless (el contenedor no tiene ventana);
    # ver engine/app/scraping/pcsp.py sección "hallazgos headless".
    scraping_navigation_timeout_ms: int = 70000
    scraping_ui_timeout_ms: int = 35000
    scraping_contract_max_keep: int = 2
    scraping_require_contract_qr_csv_hint: bool = True

    # Bloque 2, descubrimiento por sindicación (CONTEXTO.md sección 24): ZIP
    # mensual de "licitacionesPerfilesContratanteCompleto3" bajo la
    # sindicación 643, verificado real en la sesión de mantenimiento
    # automático (agosto 2024 y la sesión previa de CONTEXTO.md 17.1, mayo
    # 2025). Configurable para poder apuntar a un espejo o a un doble en
    # tests, nunca hardcodeado en el código de descubrimiento.
    sindicacion_base_url: str = "https://contrataciondelestado.es/sindicacion/sindicacion_643"
    # Departamentos de ADIF que el descubrimiento da de alta solos (CONTEXTO.md
    # sección 24): "28510" es el único que usan los 45 expedientes del
    # corpus y todo lo documentado hasta ahora — el motor de extracción está
    # pensado para su patrón (cuadro de precios + baja única por lote), no
    # para la obra civil de otros departamentos ni de "ADIF Alta Velocidad".
    # Lista separada por comas; añadir un departamento nuevo es cambiar esta
    # variable, nunca tocar código.
    sindicacion_departamentos_adif: str = "28510"

    # Bloque 3, ejecución programada (CONTEXTO.md sección 25): cada cuánto se
    # lanza el ciclo completo de mantenimiento solo, sin intervención.
    # Semanal por defecto -- el ciclo puede tardar minutos u horas si hay
    # trabajo real que hacer (secciones 23 y 24), así que no tiene sentido
    # un intervalo corto por defecto. `mantenimiento_programado_activo` en
    # `false` desactiva el disparo automático sin tocar código (el botón
    # manual, `POST /mantenimiento/ejecutar`, sigue funcionando igual).
    mantenimiento_intervalo_segundos: float = 7 * 24 * 3600.0
    mantenimiento_programado_activo: bool = True

    # Copias de seguridad automáticas (bloque de copias de seguridad,
    # sesión 2026-09-06): antes no había ninguna periódica, solo volcados
    # puntuales a mano antes de cada limpieza -- con un entorno que se
    # reinicia solo varias veces al día (docs/diagnostico-caidas-dockerd.md),
    # perder el volumen de la base de datos se llevaría el catálogo entero
    # sin ningún respaldo. Diaria por defecto, mismo mecanismo que
    # `mantenimiento_intervalo_segundos` (bloque 3): el propio bucle del
    # worker decide cuándo toca, sin un quinto proceso ni cron del sistema
    # operativo. `backup_dir` apunta a un volumen de Docker propio, distinto
    # del de PostgreSQL (docker-compose.yml), para que perder el volumen de
    # datos no se lleve las copias por delante.
    backup_dir: str = "/backups"
    backup_intervalo_segundos: float = 24 * 3600.0
    backup_activo: bool = True
    # Copias que se conservan (la más reciente cuenta como una) antes de
    # borrar las más antiguas -- sin esto, una copia diaria sin límite
    # acaba llenando el disco. 14 por defecto: dos semanas de histórico.
    backup_retencion: int = 14
    backup_timeout_segundos: float = 900.0

    # Descubrimiento inverso matriz -> pedidos (sesión de descubrimiento
    # inverso, app.extraccion.descubrimiento_matriz): abre una ficha real por
    # candidato nuevo -- con 92 candidatos reales para un solo adjudicatario
    # en la muestra de esta sesión, es caro. Semanal por defecto, mismo
    # razonamiento que `mantenimiento_intervalo_segundos`: los pedidos nuevos
    # de un acuerdo marco aparecen cada semanas, no cada hora, y la caché de
    # `candidatos_acuerdo_marco` ya evita reabrir lo ya comprobado aunque el
    # intervalo fuera más corto.
    descubrimiento_pedidos_intervalo_segundos: float = 7 * 24 * 3600.0
    descubrimiento_pedidos_activo: bool = True


settings = Settings()
