# Estados de carga y error en la web (sesión 2026-09-06)

## El problema

Las cuatro pantallas (`/`, `/catalogo`, `/revision`, `/mantenimiento`) confundían
tres situaciones distintas en una sola:

1. La API todavía no ha respondido nunca (carga inicial, o la API está
   arrancando/reintentando la conexión a la base de datos).
2. La API no responde tras varios intentos seguidos (corte real).
3. La API respondió y confirmó que no hay datos.

Antes del arreglo, mientras no había respuesta confirmada, cada panel ya
mostraba su estado inicial (`[]`, `null`) como si fuera un dato real: el
recuento en cero, la tabla vacía y el texto "Sin expedientes todavía" /
"Sin casos pendientes de revisión" / "Sin ejecuciones todavía" aparecían
*a la vez* que, tras el tercer fallo seguido, el banner "Error al conectar
con la API". Un cliente viendo eso podía pensar razonablemente que se
habían borrado los datos.

## El arreglo

`useReintentoConexion` (`web/app/useReintentoConexion.ts`) ya llevaba el
umbral de 3 fallos seguidos para decidir cuándo avisar de un corte real
(regla 2). Se le añadió un tercer valor, `confirmado`: pasa a `true` la
primera vez que una petición tiene éxito y no vuelve a `false` nunca
(una petición fallida posterior solo dispara el banner de error, no borra
lo ya confirmado). De ahí se deriva `cargando = !confirmado && !error`.

Cada panel usa esas dos señales para elegir una de tres vistas, nunca una
mezcla:

- **`cargando`** → un único mensaje ("Cargando expedientes…", "Cargando
  catálogo…", etc.), sin cifras, sin tabla vacía.
- **`error`** (umbral cumplido, `confirmado` sigue en `false`) → solo el
  banner de aviso, nada de recuento ni de "sin datos todavía".
- **`confirmado`** → el contenido real, incluidos los ceros legítimos si
  la API confirmó que no hay nada.

Si la conexión se corta *después* de haber confirmado datos alguna vez, el
panel sigue enseñando el último dato bueno conocido y añade el banner de
error encima -- no vuelve a la pantalla de "cargando", porque ese dato
sigue siendo el último confirmado, no una cifra inventada.

`ExpedientesPanel` es el único caso con una carga inicial en el servidor
(`web/app/page.tsx`): si ese `fetch` del servidor tiene éxito, pasa
`inicialConfirmado=true` al panel para que arranque ya confirmado en el
primer render del cliente, sin pasar por un "Cargando…" espurio.

## Verificación en vivo

Verificado contra el stack real (`docker compose`), aprovechando un
reinicio real y repetido de los cuatro contenedores durante la sesión
(entorno con la inestabilidad de `dockerd`/WSL ya documentada en
`docs/tolerancia-reinicios-dockerd.md` -- no provocada por este cambio).
Con Playwright contra las cuatro pantallas a la vez, capturando el texto
de la página cada 2 s durante un ciclo completo de caída y recuperación:

- Los primeros ~6-16 s tras cada reinicio: cada pantalla dice solo
  "Cargando…" -- ninguna cifra, ninguna tabla vacía.
- Tras el umbral de 3 fallos seguidos: solo el banner "Error al conectar
  con la API" -- sin "0 expedientes", sin "Sin expedientes todavía".
- En cuanto la API responde: datos reales de golpe (58 expedientes, 3.007
  líneas de catálogo, casos de revisión, frecuencia de mantenimiento) --
  nunca un cero intermedio.
- Un segundo corte, ya con datos confirmados: el banner reaparece junto a
  los últimos datos buenos (no un "cargando" ni un cero) -- comportamiento
  correcto, no la contradicción original.

Ningún recuento en cero se mostró sin una respuesta confirmada de la API
en ningún momento de la prueba.

## Hallazgo relacionado: CORS solo cubría un origen (sesión 2026-09-06, más tarde)

Aviso real del cliente: las cuatro pantallas cargaban bien (navegación
normal, sin CORS de por medio) pero cada `fetch()` a la API fallaba con
"Failed to fetch" **desde el navegador de Windows**, mientras `curl` desde
dentro del stack respondía sin problema -- la pista correcta que dio el
cliente para diagnosticar esto: un contraste entre cliente HTTP simple
(curl, no aplica CORS) y navegador real (si aplica CORS).

Confirmado en vivo con `curl -H "Origin: ..." -X OPTIONS`: con
`CORS_ALLOWED_ORIGINS=http://localhost:3000` (el único valor configurado),
una petición con `Origin: http://127.0.0.1:3000` recibía un `400` sin
cabecera `Access-Control-Allow-Origin` -- CORS compara el origen exacto
(esquema+host+puerto), y `localhost` y `127.0.0.1` son dos orígenes
distintos para el navegador aunque resuelvan al mismo sitio. Quien abriera
la web por la dirección no cubierta veía la página cargar (la navegación no
pasa por CORS) y cada llamada a la API fallar con un "Failed to fetch"
genérico, indistinguible a simple vista de la API estando caída.

Arreglado: `cors_allowed_origins` (`engine/app/config.py`), el valor por
defecto de `docker-compose.yml` y `.env.example` cubren ahora los dos
orígenes (`http://localhost:3000,http://127.0.0.1:3000`) de fábrica.
Verificado desde un navegador Windows real (Chromium vía Playwright, no
`curl`) contra las dos direcciones: los cuatro endpoints
(`/expedientes`, `/catalogo`, `/revision`, `/mantenimiento/estado`)
responden `200` con datos reales desde ambos orígenes.

**Nota del entorno, no del código**: durante esta verificación, `dockerd`
se reinició solo varias veces en una ventana de pocos minutos (más seguido
de lo habitual) -- síntoma ya documentado en
`docs/diagnostico-caidas-dockerd.md`, no una regresión de este arreglo.
Cada reinicio deja una ventana de unos segundos en la que cualquier
petición (curl o navegador) falla por igual mientras los contenedores
vuelven a arrancar; distinto del fallo de CORS, que era permanente para el
origen no cubierto, reinicios aparte.

## Segundo hallazgo, el que de verdad explicaba "sigue fallando" (mismo día)

El arreglo de arriba (cubrir los dos orígenes) era real pero no bastaba: el
cliente lo confirmó abriendo `http://localhost:3000` -- el origen que **sí**
estaba cubierto -- y las cuatro pantallas seguían fallando con
"Failed to fetch" en el navegador. La pista fue suya: contrastar `curl`
(nunca aplica CORS) contra un navegador real con la consola y la pestaña de
red abiertas.

Reproducido con Chromium real (Playwright, no `curl`) contra
`http://localhost:3000`: la consola mostraba, de forma intermitente,

```
Access to fetch at 'http://localhost:8000/expedientes' from origin
'http://localhost:3000' has been blocked by CORS policy: No
'Access-Control-Allow-Origin' header is present on the requested resource.
```

**con el origen exacto ya cubierto** -- descartando de raíz un problema de
configuración de orígenes. La causa real: un corte transitorio de conexión
a la base de datos (el mismo `dockerd`/WSL reiniciándose a mitad de
sesión, `docs/diagnostico-caidas-dockerd.md`) hace que `get_db()` propague
`sqlalchemy.exc.OperationalError` sin capturar. Starlette añade su propio
`ServerErrorMiddleware` **fuera** de los middlewares registrados con
`add_middleware` -- incluido `CORSMiddleware` -- para atrapar justo las
excepciones no capturadas: una respuesta generada ahí nunca pasa por
`CORSMiddleware`, así que nunca lleva `Access-Control-Allow-Origin`. El
navegador no puede distinguir eso de un origen mal configurado y lo
reporta como bloqueo de CORS -- un error de infraestructura transitorio
disfrazado de error de configuración permanente.

Reproducido de forma determinista (sin depender de pillar un reinicio real
de `dockerd` por casualidad): `docker network disconnect adif_default
adif-postgres-1` mientras la API seguía arriba. Antes del arreglo, `curl`
con cabecera `Origin` recibía **"Empty reply from server"** (la conexión se
cortaba sin ninguna respuesta) contra ese mismo escenario.

Arreglado en `engine/app/main.py`: un `@app.exception_handler(OperationalError)`
devuelve un `503` explícito, JSON, con la cabecera CORS ya puesta (un
manejador de excepción registrado en la propia `app` intercepta ANTES de
`ServerErrorMiddleware`, dentro de `CORSMiddleware`). Verificado con el
mismo `docker network disconnect`: la respuesta pasó a ser
`503 Service Unavailable` con `access-control-allow-origin` presente. De
paso, ese `503` es exactamente lo que `useReintentoConexion` (bloque de
arriba) ya sabe interpretar como "corte transitorio, reintentar", en vez de
un "Failed to fetch" opaco.

**Verificación final, las cuatro pantallas, navegador real**: con el
arreglo desplegado, Chromium (Playwright) contra `http://localhost:3000`
cargó datos reales en las cuatro pantallas en una misma pasada: 58
expedientes en "/", 3001 líneas en "/catalogo", los casos reales de
"/revision", y el histórico real de "/mantenimiento" (frecuencia,
ejecuciones, resúmenes de ciclo).

**Nota aparte, no resuelta por este arreglo**: durante esta sesión se
observó que `dockerd` se reiniciaba con una cadencia mucho más alta de lo
habitual (cada 20-60 s en vez de cada varios minutos). Se probó
desactivando la tarea programada `ADIF-WSL-Docker-Watchdog` como
hipótesis -- los reinicios continuaron igual sin ella activa, así que no es
la causa (la tarea se reactivó tal cual estaba). Sigue sin identificarse
por qué la cadencia fue tan alta justo en esta sesión; el mecanismo de
fondo (reanudación de modo de espera moderno) ya está documentado en
`docs/diagnostico-caidas-dockerd.md`. Con los dos arreglos de esta sesión,
cada reinicio real ahora se ve en el navegador como una reconexión breve
(3-9 s, bloque de arriba) en vez de un error de CORS permanente.
