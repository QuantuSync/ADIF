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
