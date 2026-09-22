# Informe de cierre del proyecto ADIF

Fecha: 22/09/2026. Estado del repositorio: commit `a144bbb` (rama `main`).

Sesión de solo lectura: para este informe no se ha cambiado código ni base de
datos, ni se han lanzado reprocesos ni descargas. Las consultas a la base se
hicieron en modo `default_transaction_read_only=on`, y las pruebas corrieron
en un contenedor desechable sin red y con SQLite en memoria.

**Cómo leer las cifras.** Cada cifra lleva su procedencia:

- **(medido)**: sale del repositorio, de la base de datos de producción, del
  Excel entregado o de una ejecución hecha hoy.
- **(doc.)**: la cifra está escrita en un documento de `docs/` o en
  `CONTEXTO.md`, que se cita. No se ha vuelto a medir.
- **(estimado)**: es un cálculo con un criterio que se explica al lado. No es
  una medida.

## Índice

1. Arquitectura
2. Tamaño del sistema
3. Cifras del catálogo y del corpus
4. Historia del trabajo
5. Horas
6. Dificultades del origen de los datos
7. Estado de cierre

---

## 1. Arquitectura

### 1.1 Servicios y contenedores

Hay cuatro servicios en `docker-compose.yml` (medido) y ningún proceso más:
la regla está en `CONTEXTO.md` §10, "cuatro, ni uno más". Los cuatro llevan
`restart: unless-stopped`.

| Servicio | Imagen | Qué hace | Cómo se comunica |
|---|---|---|---|
| `postgres` | `postgres:16-alpine` | Guarda el estado, el catálogo, las trazas, las cachés y la cola de trabajos. | Puerto 5432. Volumen `postgres_data`. |
| `api` | `./engine` (Python 3.12) | FastAPI con uvicorn. Es la única frontera con los datos y los ficheros. Al arrancar espera a la base (`app.esperar_bd`) y aplica las migraciones (`alembic upgrade head`). | HTTP, puerto 8000. SQL contra `postgres`. Monta el volumen `documentos`. |
| `worker` | la misma imagen que `api` | Consume la cola: descarga de la Plataforma con Chromium headless (Playwright), extracción, reconocimiento óptico, ciclo de mantenimiento, copias de seguridad, auditoría. Es el único proceso que llama al modelo. | SQL contra `postgres`. Volúmenes `documentos` y `copias_seguridad_bd` (`/backups`), y `engine/.cache_modelo_dev` como caché de disco del modelo. Sale a Internet: Plataforma, sindicación y API del modelo. |
| `web` | `./web` (Node 20) | Next.js. Cliente ligero. | Solo HTTP hacia la API: `NEXT_PUBLIC_API_URL` desde el navegador y `API_URL` desde el servidor. Nunca toca la base ni un PDF (invariante 1, `CONTEXTO.md` §9). |

Los ficheros de entrada que envía ADIF entran en los contenedores `api` y
`worker` montados desde `Ejemplo/Input`, mediante `docker-compose.override.yml`,
que no está versionado. Son el Excel de códigos, dos volcados de SAP, el
listado de estados, el desglose de traviesas, el maestro de materiales y el
listado de expedientes en ejecución.

Entorno de ejecución (medido, `README.md` y `docs/diagnostico-caidas-dockerd.md`):
Docker Engine dentro de WSL2 (Ubuntu-24.04) en un portátil con Windows 11.
Los contenedores se construyen siempre desde `/mnt/c/dev/ADIF`, que es el
invariante 11.

### 1.2 Tecnologías y bibliotecas

Versiones medidas dentro de la imagen `adif-worker`, que es la misma que usa
`api` (`pip freeze`), y en `web/package.json`:

| Tecnología | Versión | Para qué |
|---|---|---|
| Python | 3.12.14 | Motor, API y worker |
| FastAPI / uvicorn | 0.115.0 / 0.30.6 | API HTTP |
| SQLAlchemy / Alembic | 2.0.35 / 1.13.2 | Modelo de datos y migraciones |
| psycopg | 3.2.3 | Controlador de PostgreSQL |
| pydantic / pydantic-settings | 2.9.2 / 2.5.2 | Esquemas de la API y configuración por variables de entorno |
| Playwright (Chromium) | 1.62.0 | Navegación headless por la Plataforma de Contratación |
| pdfplumber / pdfminer.six | 0.11.10 / 20260107 | Texto y tablas de los PDF (etapas 1 a 4 de la cascada) |
| pypdfium2 | 5.13.0 | Rasterizar las páginas escaneadas para el reconocimiento óptico |
| PyPDF2 | 3.0.1 | Componer un PDF con capa de texto a partir de lo reconocido (`app.extraccion.ocr_pdf`) |
| anthropic (SDK) | 0.84.0 | Implementación de la interfaz `ModelProvider` (`app/interfaces/model_provider.py`) |
| openpyxl | 3.1.5 | Exportar el Excel y leer los ficheros de entrada de ADIF |
| httpx | 0.28.1 | Cliente HTTP (sindicación y pruebas) |
| pytest | 8.3.3 | Pruebas |
| PostgreSQL | 16 (servidor) / 17.11 (cliente `pg_dump`) | Base de datos y copias de seguridad |
| Node.js | 20.20.2 | Ejecutar la web |
| Next.js / React | 14.2.15 / 18.3.1 | Web |
| TypeScript | 5.6.2 | Web |

Modelos configurados (medido en `.env` y en la base):

- `MODEL_ID=claude-haiku-4-5`: mapeo de cabeceras, código del material y
  reconocimiento óptico.
- `claude-opus-5`: solo en la relectura a mano de páginas concretas, en 5
  trabajos `ocr_relectura`.

### 1.3 Módulos del motor

`engine/app` tiene 95 ficheros en git, de los que 88 tienen código (medido).
La responsabilidad de cada módulo en una línea sale de su propia cabecera
de documentación.

**Núcleo y API**

| Módulo | Responsabilidad |
|---|---|
| `main.py` | Crea la app FastAPI, CORS, y convierte una caída de la base en un 503 con cabecera CORS. |
| `config.py` | Toda la configuración por variables de entorno. |
| `db.py`, `models.py`, `schemas.py` | Conexión, 17 tablas ORM y esquemas de la API. |
| `auth.py` | Costura de autenticación: hoy devuelve un usuario ficticio (invariante 7). |
| `queue.py` | Cola de trabajos en PostgreSQL con `SELECT … FOR UPDATE SKIP LOCKED`; reclama huérfanos a los 300 s. |
| `worker.py` | Bucle del worker: toma trabajos, los despacha por tipo y lanza lo programado. |
| `esperar_bd.py` | Espera a la base antes de migrar o arrancar (tolerancia a reinicios de `dockerd`). |
| `routers/*` (9) | Endpoints: `health`, `expedientes`, `trabajos`, `catalogo`, `conciliacion`, `contraste_presupuestos`, `revision`, `documentos`, `mantenimiento`. |
| `interfaces/document_storage.py` | Interfaz de almacenamiento de documentos (hoy disco local). |
| `interfaces/model_provider.py` | Interfaz del modelo intercambiable, con implementación de API, nula y con caché en disco. |

**Catálogo, exportación y hojas del Excel**

| Módulo | Responsabilidad |
|---|---|
| `catalogo.py` | Construye, fusiona, guarda, poda y recalcula las líneas del catálogo; es el módulo más grande (3.687 líneas de fichero). |
| `catalogo_consulta.py` | Lectura del catálogo con filtros, búsqueda por matrícula y trazabilidad; la única consulta que usan la web y el Excel. |
| `celdas_vacias.py` | Motivo de cada celda vacía: no aplica, no consta o pendiente. |
| `exportacion.py` | Genera el Excel entregable y comprueba que "Conciliación" cuadra con "Materiales". |
| `conciliacion.py` | Hoja "Conciliación": una fila por expediente publicado, con su Situación. |
| `contraste_presupuestos.py` | Hoja "Contraste de presupuestos": suma de cada lote contra su presupuesto publicado, con su causa. |
| `presupuestos_adif.py` | Hoja "Presupuestos ADIF", solo si llega un listado con presupuesto. |
| `exclusion.py` | Listas de exclusión por código, departamento, código interno o palabras del título. |
| `criterio_expediente.py` | Criterio del cliente de qué código es "nuestro" (contiene 28510). |
| `catalogo_antiguo.py` | Cruce con el catálogo antiguo de ADIF, preparado para cuando llegue. |
| `ingesta_local.py` | Segunda vía de entrada: documentos desde una carpeta local. |

**Extracción (`app/extraccion`, 45 módulos)**

| Módulo | Responsabilidad |
|---|---|
| `orquestador.py` | Encadena la cascada sobre todos los documentos de un expediente (trabajo `extraer_expediente`). |
| `texto.py` | Texto de cada página, con caché por hash de documento. |
| `clasificador.py` | Etapa 1: plantilla del documento por marcadores de texto. |
| `campos_pcsp.py`, `campos_lc27.py` | Etapa 2: campos de etiqueta fija del Anuncio PCSP y de la Propuesta LC.27. |
| `baja.py`, `precios_unitarios.py`, `modelo_precio_indexado.py` | Baja declarada en texto; caso de precios unitarios; segunda familia de precio indexado por pedido. |
| `lotes.py`, `lotes_pcsp.py`, `lote_declarado.py`, `lote_tabla.py` | Estructura multilote, bloques «Nº Lote» del anuncio, lote declarado en el título, y a qué lote pertenece cada tabla (etapa 3.5). |
| `identidad_expediente.py`, `herencia_matriz.py`, `descubrimiento_matriz.py` | Identidad del expediente desde su documento, herencia del acuerdo marco y búsqueda inversa de pedidos. |
| `localizador.py` | Etapa 3: páginas candidatas a cuadro de precios. |
| `tabla.py`, `fila_sobre_la_tabla.py`, `filas_repetidas.py`, `partida_alzada_del_lote.py` | Etapa 4: extraer el cuadro con `pdfplumber` y recuperar las filas que la tabla pierde. |
| `firma_cabecera.py`, `firma_estructural.py`, `mapeo_cabecera.py` | Etapa 5: firma de cabecera, caché y mapeo cabecera → esquema (reglas primero, modelo como último recurso). |
| `pipeline_anejo.py` | Etapas 3 a 6 sobre un documento completo. |
| `normalizacion.py`, `unidad_medida.py`, `codigo_material.py`, `referencia_como_descripcion.py`, `glifos_cid.py`, `invalidado.py`, `traza.py` | Etapa 6: números en formato español, unidades, código del material, cifras en glifos, estado `INVALIDADO` y trazas sin duplicar. |
| `presupuesto_lote.py` | Presupuesto de licitación de cada lote leído de los documentos. |
| `ocr.py`, `ocr_pdf.py`, `ocr_relectura.py` | Reconocimiento óptico de escaneados y relectura de páginas concretas. |
| `cruce_codigos.py`, `estado_sap.py`, `estados_adif.py`, `en_ejecucion_adif.py`, `sap_desglose.py`, `maestro_materiales.py`, `vigentes_remanente.py`, `candidatos_matricula.py` | Cruce y carga de los ficheros de entrada de ADIF. |

**Obtención de datos (`app/scraping`, `app/sindicacion`)**

| Módulo | Responsabilidad |
|---|---|
| `scraping/pcsp.py` | Scraper de la Plataforma: búsqueda por MATRIZ con caída a Nº Expediente y descarga de documentos. |
| `scraping/job.py` | Trabajo de cola que descarga y registra expediente y documentos. |
| `scraping/limitador.py` | Espaciado mínimo entre peticiones a la Plataforma. |
| `scraping/descubrimiento_busqueda.py` | Descubrimiento por el buscador de la Plataforma (fragmento `28510`). |
| `sindicacion/cliente.py`, `atom_parser.py`, `descubrimiento.py`, `contraste.py` | Descarga y parseo de los boletines de sindicación, alta de expedientes y contraste de importes. |

**Mantenimiento (`app/mantenimiento`)**

| Módulo | Responsabilidad |
|---|---|
| `ciclo.py` | Ciclo de mantenimiento: descubrir, descargar, extraer y auditar. |
| `frescura.py` | Decide qué hay que descargar o reextraer y cuándo se vuelve a buscar un `sin_publicar`. |
| `programacion.py` | Lanza los trabajos programados desde el bucle del worker. |
| `auditoria.py` | Auditoría automática del catálogo: solo detecta, nunca corrige. |
| `copia_seguridad.py` | `pg_dump` con retención. |
| `reconstruccion.py` | Reconstrucción del catálogo desde cero en una base aparte. |
