# Tolerancia a reinicios de `dockerd`

Sesión 2026-09-06, continuación directa de `docs/diagnostico-caidas-dockerd.md`.
Ese documento diagnosticó **por qué** `dockerd` se reinicia (Modo de espera
moderno de Windows reinicializando el *init* de WSL) y cerró con una
salvedad explícita: *"`docker-compose.yml` no define `restart:` en ningún
servicio... los contenedores de ADIF en sí no se recuperan solos tras una
caída"*. Esa parte ya se cerró en una sesión posterior (`restart:
unless-stopped` en los cuatro servicios). Esta sesión ataca lo que quedaba:
**cuando los contenedores sí se recuperan solos, ¿lo hacen limpiamente, sin
tirar la aplicación abajo por el camino?** La respuesta, verificada en vivo
contra el error real reportado por el cliente (`Error 500 en la API`), era
que no del todo.

**Decisión explícita del cliente para esta sesión**: no se cambia de
máquina para la demo. La inestabilidad de fondo (Modo de espera moderno)
sigue sin resolverse — requiere privilegios de administrador de Windows que
esta sesión no tiene — pero todo lo que sí depende del código de este
repositorio se hace tolerante a que seguirá ocurriendo.

---

## 1. Causa raíz del error 500: `depends_on` no cubre la restauración de `dockerd`

`docker-compose.yml` ya declaraba `depends_on: postgres: condition:
service_healthy` para `api`. Verificado que esto **no** protege contra el
caso real: esa condición solo la evalúa el orquestador de `docker compose`
en un `up` explícito. Cuando `dockerd` se reinicia por su cuenta (la causa
ya diagnosticada) y restaura los contenedores con `restart: unless-stopped`,
cada uno arranca por separado, sin pasar por Compose ni por su orden de
dependencias — `api` y `worker` podían intentar conectar a `postgres`
mientras la red del stack todavía se estaba recreando, y su primer intento
fallaba con:

```
sqlalchemy.exc.OperationalError: (psycopg.OperationalError) [Errno -2] Name or service not known
```

Antes de esta sesión, ese fallo no se atrapaba en ningún sitio: reventaba
`alembic upgrade head` (api) o la primera consulta del bucle (worker),
matando el proceso entero — el contenedor volvía a arrancar desde cero por
`restart: unless-stopped`, y mientras tanto cualquier petición real (el
"Error 500" reportado) caía en la ventana muerta.

## 2. Arreglo: `app.esperar_bd`

Nuevo módulo (`engine/app/esperar_bd.py`): reintenta una conexión mínima
(`SELECT 1`) hasta 40 veces con 3s de espera entre intentos (2 minutos de
margen, generoso frente a los pocos segundos reales que tarda `postgres` en
aceptar conexiones tras un reinicio) antes de devolver `True`/`False` — nunca
lanza. Invocado como paso previo en `docker-compose.yml`:

```yaml
api:
  command: sh -c "python -m app.esperar_bd && alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"
worker:
  command: sh -c "python -m app.esperar_bd && python -m app.worker"
```

`pool_pre_ping=True` del motor de `app.db` no serviría aquí: solo revalida
conexiones ya abiertas del pool, no ayuda en el primer intento cuando el DNS
del contenedor `postgres` ni siquiera resuelve todavía.

Tests (`engine/tests/test_esperar_bd.py`): conecta a la primera sin dormir,
reintenta hasta conectar (motor falso que falla N veces y luego conecta de
verdad contra SQLite en memoria), agota los intentos y devuelve `False` sin
lanzar.

## 3. Segundo fallo real, encontrado verificando en vivo (no solo con tests)

El encargo pedía verificar contra el stack real, no solo con la suite de
tests — y verificando así apareció un segundo fallo que ningún test unitario
había cubierto: `app.esperar_bd` valida conectividad **una vez**, al
arrancar. Un reinicio real de `dockerd` puede dejar la red del stack
recreándose todavía **varios segundos después** de esa comprobación exitosa
— reproducido en vivo, forzando reinicios de `dockerd` mientras el worker
corría:

```
2026-09-06 17:54:08 worker arrancado, sondeando cada 3.0s
Traceback (most recent call last):
  ...
  File "/app/app/worker.py", line 163, in bucle_principal
    reclamados = reclamar_trabajos_huerfanos(db, ...)
  ...
sqlalchemy.exc.OperationalError: (psycopg.OperationalError) [Errno -2] Name or service not known
```

`esperar_bd` había conectado correctamente; la siguiente consulta, ya
dentro de `bucle_principal()`, se topó con el mismo DNS que había vuelto a
fallar. Esa consulta (`reclamar_trabajos_huerfanos`, `tomar_siguiente_trabajo`,
`verificar_y_lanzar_ciclo_programado`) no es la de un trabajo concreto — esas
ya aíslan sus propios fallos en `app.queue.ejecutar_trabajo` (`except
Exception`, marca el trabajo `fallido` y sigue) — es la propia
"contabilidad" del bucle, sin ningún `try` alrededor. La excepción salía de
`bucle_principal()` entera, mataba el proceso, y `restart: unless-stopped`
reiniciaba el contenedor desde cero — perdiendo el reintento que
`esperar_bd` ya había hecho, y repitiendo el ciclo.

**Arreglo** (`engine/app/worker.py`): el cuerpo de cada vuelta se extrajo a
`_vuelta_bucle_principal(db)` (testable sin depender de un `while True`), y
`bucle_principal` atrapa `OperationalError` a su alrededor: registra un aviso
y reintenta en la siguiente vuelta (el mismo `sleep` de siempre), en vez de
morir. `engine/tests/test_worker.py`,
`test_bucle_principal_no_muere_por_un_fallo_de_conexion_transitorio`: una
vuelta falla por conexión, la siguiente se ejecuta igualmente (si hubiera
matado el proceso, no habría segunda vuelta que contar).

La API no necesitaba el mismo arreglo: un fallo transitorio durante una
petición ya aislada por FastAPI/`get_db()` produce un 500 para *esa*
petición, no mata el proceso (`uvicorn` sigue sirviendo las siguientes
peticiones sin problema, verificado en los logs reales) — el problema ahí
no es "el proceso muere", es "el navegador se queda con un error visible
sin reintentar", que es exactamente el punto 4.

## 4. La web: dejaba de reintentar en cuanto fallaba una vez

Dos problemas reales, verificados leyendo el código de `web/app/`, no solo
la sensación de "la web no carga":

- **`web/app/page.tsx` (Home, "/") se quedaba parada para siempre.** Es un
  Server Component (`async function Home()`) que hace un `fetch` en el
  servidor una vez por petición. Si fallaba, renderizaba un banner de error
  estático y **nunca montaba `ExpedientesPanel`** — el componente que sí
  sondea la API cada 3s y se recupera solo. Sin `ExpedientesPanel` montado,
  no había ningún reintento posible sin recargar la página a mano.
  Corregido: ahora siempre monta `ExpedientesPanel` (con `inicial: []` si el
  fetch del servidor falló) — su propio sondeo lo rellena en cuanto la API
  responde.
- **Ningún panel distinguía "corte de un par de segundos que ya se
  resolvió solo" de "corte real"**: el primer fallo de sondeo ya encendía
  un banner rojo, aunque el siguiente sondeo (2-4s después, según el panel)
  lo resolviera solo. Nuevo hook compartido,
  `web/app/useReintentoConexion.ts`: no muestra el banner hasta 3 fallos
  **seguidos** del sondeo pasivo — una acción directa del usuario (crear,
  descargar, extraer, confirmar) sigue avisando al primer fallo, eso no
  cambia. Aplicado a los cuatro paneles (`ExpedientesPanel`, `CatalogoPanel`,
  `RevisionPanel`, `MantenimientoPanel`).
- **`CatalogoPanel` y `RevisionPanel` no reintentaban en absoluto tras un
  fallo** (`CatalogoPanel` solo volvía a pedir datos si el usuario cambiaba
  un filtro; `RevisionPanel` cargaba la lista una sola vez al montar).
  `CatalogoPanel` ahora reintenta automáticamente 3s después de cualquier
  fallo (sin interferir con el sondeo por cambio de filtro);
  `RevisionPanel` pasa de "una vez al montar" a sondeo periódico cada 3s,
  igual que `ExpedientesPanel`.

Build de producción verificado sin errores de tipos ni de compilación
(`npm run build`, `✓ Compiled successfully`, `Linting and checking validity
of types`).

## 5. Ventana de consola visible en las tareas programadas

`ADIF-WSL-Docker-Autostart` (creada en la sesión de diagnóstico) y
`ADIF-WSL-Docker-Watchdog` (creada más tarde en la sesión de unificación del
árbol de construcción) invocaban `wsl.exe` directamente como acción de la
tarea — `wsl.exe` siempre abre una consola visible, aunque la tarea se
ejecute en segundo plano. Corregido: ambas apuntan ahora a
`C:\Users\LUCAS\AppData\Local\ADIF\run-hidden.vbs`, que lanza el mismo
comando (`wsl.exe -d Ubuntu-24.04 -u root -- systemctl start docker`) vía
`WScript.Shell.Run(..., 0, False)` — el `0` es la clave: ventana oculta.
Verificado disparando ambas tareas manualmente, sin ventana, `LastTaskResult
= 0`.

## 6. Verificación: forzando reinicios reales de `dockerd`, no solo tests

El encargo pedía tirar el stack de golpe, levantarlo, y repetirlo varias
veces — comprobado con `systemctl restart docker` / `stop` + `start`
forzados, y además con la propia inestabilidad ambiental del entorno
(Modo de espera moderno, sigue activa, sin resolver) disparándose sola
docenas de veces más durante esta sesión. Los dos sirven como evidencia,
la segunda incluso más honesta por no ser un caso preparado:

- **Ejecuciones repetidas y observadas en vivo**: contenedores operativos
  en 8-14s desde `systemctl restart docker`, sin `docker compose up` manual
  de por medio (`restart: unless-stopped` + `esperar_bd` + la restauración
  de contenedores de `dockerd`).
- **Docenas de ciclos reales adicionales** (la inestabilidad ambiental
  siguió disparándose sola durante la verificación): revisado el log
  completo del worker tras desplegar el arreglo — **cero trazas sin
  atrapar** (`grep -c Traceback` → `0`), solo avisos limpios ("fallo de
  conexión a la base de datos en esta vuelta, se reintenta") seguidos de
  recuperación normal. Antes del arreglo, la misma inestabilidad producía
  una traza completa de Python cada vez.
- **Con la web "abierta"** (sondeada repetidamente desde Windows, sin tocar
  WSL, para no contaminar la medida): capturado un corte real
  (`SIN_RESPUESTA`) seguido de recuperación limpia en la siguiente petición
  (~3,5s después), sostenida sin ninguna interrupción durante los
  siguientes 90s+ de sondeo — sin recargar nada a mano. Dado que "/" es una
  ruta dinámica (`ƒ Dynamic` en el build de Next.js, se re-renderiza en
  cada petición, nunca cacheada), cada petición del sondeo ejercita de
  verdad el mismo camino que corregía el punto 4.1: si el fetch del
  servidor hubiera fallado en alguna de esas peticiones, antes se habría
  visto el banner de error estático; después de la sesión no se vio
  ninguno.
- **No verificado con un navegador real persistente** (Playwright, sí
  disponible en las imágenes del proyecto): la evidencia de arriba prueba
  el arreglo del punto 4.1 (la ruta ya no se queda parada) con peticiones
  frescas repetidas, pero no observa directamente el estado de React de una
  misma pestaña reconectando sola vía `setInterval` — ese mecanismo es el
  mismo patrón ya usado en `MantenimientoPanel` desde antes de esta sesión,
  no código nuevo sin precedente, pero queda anotado como la comprobación
  más rigurosa pendiente si se quiere cerrar del todo antes de la demo.

## 7. Lo que sigue sin resolver, a propósito

La causa de fondo (Modo de espera moderno reiniciando WSL) no se toca en
esta sesión — sigue siendo el mismo diagnóstico y las mismas limitaciones de
`docs/diagnostico-caidas-dockerd.md` (requiere privilegios de administrador
de Windows). Lo que cambia es que, cuando ocurre — y ocurrirá, se observó
decenas de veces solo durante esta sesión —, el sistema ya no lo nota como
un usuario: se recupera solo, sin tracebacks, sin que la web se quede
mostrando un error rojo permanente ni que nadie tenga que recargar nada a
mano.
