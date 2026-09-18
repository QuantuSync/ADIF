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

    # Bloque 1, sesión del Excel de ejecución SAP (2026-09-07): fuente de
    # entrada permanente para `estado_contrato_sap` (CONTEXTO.md,
    # app.extraccion.estado_sap), igual de mecánica que `codigos_proyecto_path`
    # de arriba -- una ruta montada por bind-mount, vacía por defecto (sin
    # ella, `POST /mantenimiento/estado-sap/cargar` no tiene nada que leer).
    estado_sap_path: Optional[str] = None

    # Bloque 1, sesión 2026-09-18 (continuación): listado de estados de
    # contratación que ADIF envió el 18/09/2026 (358 expedientes del 28510),
    # sacado por ellos de una transacción de SAP y autorizado expresamente
    # (`app.extraccion.estados_adif`, ver su docstring para la procedencia).
    # Mismo mecanismo que las rutas de arriba -- una ruta montada por
    # bind-mount, vacía por defecto. Fuente de contraste y de relleno de
    # columnas: NUNCA decide si un expediente está publicado.
    estados_adif_path: Optional[str] = None

    # Bloque 6, cambios del cliente tras revisar el catálogo: desglose de
    # SAP con las matrículas concretas de cada contrato (app.extraccion.
    # sap_desglose) -- mismo mecanismo que las dos rutas de arriba. Solo lo
    # lee la API (POST /mantenimiento/sap-desglose/cargar).
    sap_desglose_path: Optional[str] = None

    # Bloque 4, sesión 2026-09-09: maestro de materiales de SAP (app.
    # extraccion.maestro_materiales) -- documento de referencia de ADIF, NO
    # derivado de pliegos ni contratos, con matrícula y unidad de medida de
    # cada material. Mismo mecanismo que las rutas de arriba. Todavía no
    # facilitado por el cliente: sin esta variable, `POST /mantenimiento/
    # maestro-materiales/cargar` no tiene nada que leer y `completar-unidades`
    # no completa nada -- ninguno de los dos rompe el resto del sistema.
    maestro_materiales_path: Optional[str] = None

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

    # Reconocimiento óptico de documentos escaneados (sesión 2026-09-17,
    # `app.extraccion.ocr`): "escaneados" (por defecto) lee con el modelo con
    # visión solo los documentos sin capa de texto; "desactivado" lo apaga.
    # Nunca se aplica a un documento que ya trae texto.
    ocr_modo: str = "escaneados"
    # Páginas leídas a la vez dentro de un documento.
    ocr_paralelismo: int = 4
    # Un documento escaneado más largo que esto no se lee entero (una ficha
    # técnica de 670 páginas en el corpus real): solo sus primeras páginas,
    # para clasificarlo, y queda anotado.
    ocr_max_paginas: int = 150

    # Scraping PCSP. Siempre headless (el contenedor no tiene ventana);
    # ver engine/app/scraping/pcsp.py sección "hallazgos headless".
    scraping_navigation_timeout_ms: int = 70000
    scraping_ui_timeout_ms: int = 35000
    scraping_contract_max_keep: int = 2
    scraping_require_contract_qr_csv_hint: bool = True
    # Sesión de límite de tasa (2026-09-07): espaciado mínimo entre
    # peticiones reales de scraping (`descargar_expediente`) -- 454
    # descargas seguidas sin ninguna pausa entre sí, en esta misma sesión,
    # coincidieron con un patrón de bloqueo/timeout bajo carga en la
    # Plataforma real. Ver `app.scraping.limitador.esperar_turno`.
    scraping_separacion_minima_segundos: float = 5.0

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

    # Descubrimiento por búsqueda directa en la Plataforma (sesión
    # 2026-09-16, `app.scraping.descubrimiento_busqueda`): la sindicación
    # cubre lo que ha tenido un evento de contratación en el mes -- en la
    # práctica, lo ya adjudicado -- y deja fuera lo que sigue en licitación
    # o pendiente de resolver. El buscador de la Plataforma sí lo lista.
    # Lista de fragmentos de código separados por comas, con coincidencia
    # POR SUBCADENA (el campo "Nº de expediente" del buscador funciona así):
    # "28510" trae todo expediente que contenga esos dígitos, en cualquier
    # estado y de cualquier año, que es literalmente el criterio del cliente
    # (CONTEXTO.md sección 16). Vacía = usar `sindicacion_departamentos_adif`,
    # para no mantener dos listas de "qué es nuestro" que puedan divergir.
    # Un fragmento más fino ("6.26/28510") sirve para acotar una pasada
    # concreta desde el payload del trabajo, sin tocar la configuración.
    busqueda_fragmentos: str = ""
    # Desactiva el descubrimiento por búsqueda dentro del ciclo de
    # mantenimiento sin tocar código, igual que
    # `mantenimiento_programado_activo` para el ciclo entero. No hay
    # intervalo propio: corre dentro de cada ciclo (semanal por defecto),
    # junto al descubrimiento por sindicación.
    busqueda_descubrimiento_activo: bool = True

    # Bloque 3, ejecución programada (CONTEXTO.md sección 25): cada cuánto se
    # lanza el ciclo completo de mantenimiento solo, sin intervención.
    # Semanal por defecto -- el ciclo puede tardar minutos u horas si hay
    # trabajo real que hacer (secciones 23 y 24), así que no tiene sentido
    # un intervalo corto por defecto. `mantenimiento_programado_activo` en
    # `false` desactiva el disparo automático sin tocar código (el botón
    # manual, `POST /mantenimiento/ejecutar`, sigue funcionando igual).
    mantenimiento_intervalo_segundos: float = 7 * 24 * 3600.0
    mantenimiento_programado_activo: bool = True
    # Sesión 2026-09-15: un `sin_publicar` ya confirmado con la lógica de
    # búsqueda vigente se vuelve a buscar pasado este plazo (dos semanas: con
    # el ciclo semanal, en ciclos alternos). Un negativo sin confirmar no
    # espera ningún plazo. Tope de búsquedas por ciclo (~40 s cada una en la
    # Plataforma real), empezando por los más antiguos; los que no caben
    # quedan para el ciclo siguiente.
    sin_publicar_reintento_dias: float = 14.0
    sin_publicar_reintentos_por_ciclo: int = 50
    # Sesión 2026-09-18 (tercera parte): el plazo de arriba es el de un
    # expediente viejo. Uno del año en curso (o del anterior) es un
    # procedimiento vivo que puede publicarse cualquier semana --
    # `6.26/28510.0057` y `0083` se buscaron el 16/09, no estaban, y el 18/09
    # ya estaban publicados: con catorce días se habrían encontrado el 30/09,
    # doce días tarde. Para esos el plazo es corto, así que el ciclo semanal
    # los vuelve a buscar SIEMPRE. Para uno de 2014, que lleva una década sin
    # publicarse, catorce días sigue siendo lo razonable: cada búsqueda evitada
    # cuenta contra una Plataforma lenta y frágil (CONTEXTO.md sección 14).
    # `sin_publicar_anios_recientes` es la distancia en años, contra el año
    # que va en el propio código del expediente; 0 lo dejaría solo en el año
    # en curso.
    sin_publicar_reintento_dias_recientes: float = 3.0
    sin_publicar_anios_recientes: int = 1

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

    # Bloque 5, cambios del cliente tras revisar el catálogo: lista de
    # exclusión de expedientes que no son del equipo del cliente -- sin
    # ella, el cliente los quitaba a mano de cada exportación y volvían a
    # aparecer en la siguiente. Mismo mecanismo que `codigos_proyecto_path`/
    # `estado_sap_path` de arriba (ruta a un fichero de entrada, montada por
    # bind-mount, vacía por defecto): un fichero de texto plano, no una base
    # de datos ni un endpoint de escritura, para que ADIF pueda mantenerlo
    # sin tocar código ni pedir un despliegue (`app.exclusion` para el
    # formato exacto). Vacío por defecto: sin esta variable, no se excluye
    # ningún expediente.
    exclusion_expedientes_path: Optional[str] = None

    # Bloque 3, sesión de comparación documento-vs-listado interno: filtro
    # por palabras del título del contrato -- el cliente quiere poder
    # excluir de la vista (Excel + web) contratos que no son material
    # (arrendamientos, gestión de residuos...) sin dejar de descargarlos ni
    # de guardarlos. Mismo mecanismo que `exclusion_expedientes_path`
    # (`app.exclusion`, fichero de texto plano montado por bind-mount,
    # una palabra o frase por línea): mantenible sin tocar código. Vacío
    # por defecto: sin esta variable, no se excluye ningún título.
    exclusion_palabras_titulo_path: Optional[str] = None

    # Bloque 6, sesión de comparación documento-vs-listado interno: segunda
    # vía de ingesta (`app.ingesta_local`), para expedientes vigentes en el
    # SAP del cliente que no están publicados en la Plataforma -- una macro
    # propia deja los PDF en esta ruta (montada por bind-mount, mismo
    # mecanismo que `codigos_proyecto_path` y el resto de fuentes de
    # entrada), una subcarpeta por expediente (ver docstring del módulo y
    # docs/ingesta-manual-convencion-carpetas.md, pensado para enviárselo al
    # cliente). Vacío por defecto: sin esta variable, la ingesta no hace
    # nada.
    ingesta_local_path: Optional[str] = None


settings = Settings()
