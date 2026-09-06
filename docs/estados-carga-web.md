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
