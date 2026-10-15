# Sesión 2026-10-14 — Acceso, modelo de IA configurable y preparación del despliegue

El proyecto se entrega desplegado en una máquina de Azure ya creada (Ubuntu
24.04, 4 vCPU, 16 GB, 256 GB, `adif-catalogo-ineco.spaincentral.cloudapp.azure.com`,
443 abierto). Esta sesión deja el sistema listo para ese despliegue, sin
desplegar. No se ha reprocesado nada ni se han tocado datos del catálogo.

Commits: `89ce22f` (acceso), `ed6060a` (modelo de IA), `94e635f` (despliegue).

## Bloque 1 — Acceso con usuario y contraseña

**Qué hay.**

- Tablas `usuarios`, `sesiones_usuario` y `registro_accesos` (migración 0044).
- Contraseña en **argon2id** (`argon2-cffi`). Nunca en claro; la prueba lo
  comprueba sobre el hash guardado.
- Sesión por **cookie `HttpOnly`, `SameSite=Lax`**, `Secure` en producción. En
  la base se guarda el SHA-256 del token. Se eligió cookie y no cabecera porque
  el Excel y los PDF se descargan por enlace normal del navegador, que no lleva
  cabeceras propias.
- Caducidad: 30 minutos sin actividad, 12 horas como máximo. Las pantallas
  sondean la API solas cada pocos segundos; para que una pestaña olvidada no
  mantenga la sesión viva, la web marca con `X-Sondeo` toda petición que sale
  sin que el usuario haya tocado nada en el último minuto, y la API no la cuenta
  como actividad.
- Primera entrada (y tras un reinicio de contraseña): 403
  `cambio_contrasena_obligatorio` en cualquier ruta con datos hasta cambiarla.
  Pantalla `/cambiar-contrasena` también accesible cuando se quiera, desde la
  barra. Cambiarla cierra las demás sesiones del usuario.
- Consola: `python -m app.usuarios crear | reiniciar | desactivar | activar |
  listar | accesos`. `crear` y `reiniciar` generan una contraseña temporal; no
  se pasa ninguna contraseña por la línea de órdenes.
- Registro: entrada, salida, fallo, bloqueado y cambio de contraseña, con
  usuario tecleado, momento, dirección y navegador.
- Límite de intentos contado sobre el propio registro (sin estado en memoria):
  5 fallos por usuario o 20 por dirección en 15 minutos bloquean 15 minutos,
  incluso con la contraseña correcta. Usuario inexistente y contraseña mala
  responden igual, y tardan lo mismo (verificación contra un hash señuelo).
- `/docs` y `/openapi.json` apagados por defecto (`API_DOCUMENTACION_ACTIVA`).

**Cómo queda protegida toda la API.** `get_current_user` (la costura de
CONTEXTO.md 9.7) se pone en `app.main` a cada router entero. Sin sesión, solo
responden `/health`, `/auth/entrar` y `/auth/salir`. `tests/test_acceso.py`
recorre **todas** las rutas registradas (más de 50, la exportación incluida) y
exige 401 a cada una; una ruta nueva sin protección rompe esa prueba. Las
pruebas de pantallas entran con un usuario de prueba (`conftest.py`), salvo
las marcadas `acceso_real`.

**Web.** `middleware.ts` pregunta a la API por la red interna y manda a
`/entrar?siguiente=...` sin sesión (o a `/cambiar-contrasena`). La redirección
se arma con `Host` y `X-Forwarded-Proto` porque detrás de Caddy la URL que ve
Next es la interna (y Next exige Location absoluta: una relativa da 500). Si la
API está caída, el middleware deja pasar: sin API no hay datos, y cada
pantalla ya sabe avisar y reintentar. `sesion-cliente.ts` envuelve `fetch` una
sola vez (cookie, `X-Sondeo`, 401 a la entrada) en vez de tocar las 35
llamadas de los paneles. La carga inicial de la portada, hecha desde el
servidor de Next, reenvía la cookie a mano.

**Diseño.** Blanco, negro y grises, la tipografía de siempre (Archivo, Public
Sans), botón negro, un formulario y nada más. La barra de navegación gana el
nombre del usuario, "Contraseña" y "Salir"; para que siga cabiendo a 1440 px
se quita el subtítulo de la marca por debajo de 1560 px, y en pantallas
estrechas la barra se desplaza en horizontal.

**Verificado** con Playwright a 360, 390, 412 y 1440 px: redirección a la
entrada, error con contraseña mala, primera entrada al cambio obligatorio,
cambio, datos, vuelta a la página pedida, salir. Sin cookie, la API da 401 en
datos, exportación y documentos.

## Bloque 2 — El modelo de IA, configurable

**`MODEL_PROVEEDOR`**: `anthropic` (el de siempre, por defecto) u `openai`,
una implementación nueva del protocolo de chat de OpenAI
(`OpenAICompatibleModelProvider`) por HTTP directo con `httpx`, sin SDK. Es la
vía para el servicio de IA del cliente (`MODEL_ENDPOINT`, su clave y el nombre
del despliegue en `MODEL_ID`; `MODEL_API_VERSION` solo para el formato antiguo
por despliegue), y vale igual para un modelo autoalojado. Se nombra por el
protocolo y no por el proveedor por la regla 9.5 de CONTEXTO.md: Azure solo
aparece en la configuración de ejemplo y en la guía. La clave va en
`Authorization: Bearer` y en `api-key`; cada servicio lee la suya. Salida
estructurada con `response_format: json_schema` y `strict: false` (el modo
estricto exige todas las claves como obligatorias y los esquemas de la cascada
no se escribieron así). Las páginas escaneadas van como `image_url` en base64.

**Sin clave** el sistema arranca, consulta y exporta. El worker lo dice al
arrancar; la pantalla de Mantenimiento lo enseña (`GET /mantenimiento/modelo-ia`,
que dice proveedor y modelo, nunca la clave); y un expediente con un escaneado
nuevo queda en revisión con el motivo "no hay modelo de IA configurado para
leer escaneados nuevos (MODEL_API_KEY vacía)" en vez del de antes, que lo
presentaba como fuera de alcance. Una cabecera nunca vista da un error que dice
lo mismo.

**Nada de lo leído se vuelve a leer.** Dos cambios en la caché de
reconocimiento óptico:

1. Antes, una lectura solo valía si la había hecho el mismo `MODEL_ID`;
   cambiar al servicio del cliente habría vuelto a leer (y pagar) los ~140
   escaneados. Ahora vale con cualquier modelo; `modelo` queda como constancia
   de quién la hizo. Para mejorar páginas concretas sigue la relectura.
2. Antes, sin proveedor no se miraba la caché: reprocesar un expediente sin
   clave habría perdido las líneas de sus escaneados ya leídos. Ahora se usa
   lo cacheado (`leer_documento_en_cache`).

**Pruebas** (`tests/test_modelo_ia.py`, sin red): la petición del protocolo
(dirección, cabeceras, esquema, imagen, versión), respuesta cortada que no se
reintenta, clave mala que deja la página pendiente, elección por
configuración, y de punta a punta sobre un escaneado de 4 páginas con cada
vía (cliente falso del SDK en una, transporte falso de `httpx` en otra);
cambiar de proveedor no hace ninguna llamada y deja las mismas líneas; sin
clave, lo leído sale de la caché y lo nuevo queda en revisión con su motivo.

**Hallazgo de paso.** El ciclo semanal programado se lanzó solo hoy a las 13:46
UTC (antes de empezar la sesión) y una extracción falló con `invalid
x-api-key`: la clave de `.env` local no es válida. No se ha tocado.

## Bloque 3 — Preparar el despliegue

Todo en `deploy/`:

- `docker-compose.prod.yml`: postgres, api, worker y web sin ningún puerto
  publicado, y `entrada` (Caddy 2.8) con el 80 y el 443. API con
  `--proxy-headers` para que el registro de accesos vea la dirección real.
  Documentos, copias y ficheros de entrada en `/srv/adif` de la máquina.
- `Caddyfile`: certificado automático para `DOMINIO`, redirección del 80 al
  443 (la hace Caddy solo), web en `/`, API en `/api`, cabeceras de seguridad.
  El navegador ve un solo origen.
- `env.produccion.ejemplo`: todas las variables, sin secretos.
- `instalar.sh`: Docker oficial, actualizaciones de seguridad automáticas,
  registros acotados, carpetas, `.env` con contraseña de base aleatoria,
  construcción, arranque, restauración si hay datos en `traspaso/`, y unidad
  de systemd. Repetible; sirve también para actualizar.
- `restaurar-datos.sh`: base con el `pg_restore` del propio PostgreSQL 16,
  documentos desde un tar, y vacía usuarios, sesiones y registro de accesos
  de la máquina de origen.
- `adif.service`: arranque de todo al encender la máquina.
- Copias: las del worker de siempre (diarias, 14), ahora en `/srv/adif/copias`.

**Hallazgo que habría bloqueado el despliegue: las migraciones no se podían
aplicar sobre una base vacía.** Alembic las ejecutaba todas en una sola
transacción, y la 0031 usa `sin_publicar`, un valor de enum que añade la 0010;
PostgreSQL no deja usar un valor nuevo de enum antes de confirmar la
transacción que lo crea. La base local se fue migrando poco a poco y nunca lo
vio. Arreglado con `transaction_per_migration=True` en `migrations/env.py`.

**Segundo hallazgo**: las copias automáticas las hace el `pg_dump` 17 de la
imagen del motor, y el `pg_restore` 16 del contenedor de PostgreSQL no puede
leerlas. Por eso el traspaso se hace con el `pg_dump` del contenedor de
PostgreSQL, y la guía restaura las copias automáticas con el `pg_restore` del
motor.

**Probado de verdad en local**, con la pila de producción bajo otro nombre de
proyecto (`adifprueba`), `DOMINIO=localhost` y datos en una carpeta temporal:
migración desde cero hasta la 0044; restauración del volcado y los documentos
reales en 30 s (614 expedientes, 40.164 líneas, igual que el origen); el 80
redirige al 443; sin sesión 401 en datos, Excel y documentos; cookie con
`Secure`; solo `entrada` publica puertos; Caddy no se fía de un
`X-Forwarded-For` inventado; primera entrada al cambio obligatorio y catálogo
con datos en Chromium a 390 y 1440 px; Excel completo (1,9 MB) a través de
Caddy en 128 s; worker sin clave arrancando y diciéndolo; copia de seguridad
de 45 MB en la carpeta de la máquina. La pila de prueba se desmontó después.

**Sin probar**: `instalar.sh` entero (instala paquetes y servicios del
sistema, no se ejecutó en esta máquina; sus pasos de Docker sí, uno a uno); el
certificado real de Let's Encrypt (necesita el dominio); el arranque tras un
reinicio real; y la restauración de una copia automática con el comando de la
guía en la pila de producción.

## Qué hay que subir

| | Tamaño |
|---|---|
| Documentos descargados (`documentos.tar`, 1.651 ficheros) | 1,9 GB |
| Copia de la base (`adif.dump`, `pg_dump -Fc`) | 44 MB |

## Pendiente

- Abrir el puerto 80 en el grupo de seguridad de Azure (hoy solo está el 443;
  sin el 80 no funciona la redirección).
- Subir los datos y ejecutar `instalar.sh` (pasos en `docs/guia-de-operacion.md`).
- Clave, dirección y despliegue del servicio de IA del cliente. Para leer
  escaneados el despliegue tiene que admitir imágenes.
- La clave de `.env` local no vale (`invalid x-api-key`).
- En local quedan los usuarios `lucas` (temporal, a cambiar en la primera
  entrada) y `verificacion` (desactivado). No viajan a producción: la
  restauración vacía los usuarios.
