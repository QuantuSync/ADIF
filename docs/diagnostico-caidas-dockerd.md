# Diagnóstico: caídas de `dockerd` en WSL2

Sesión de diagnóstico puro (2026-09-06). No se ha tocado el motor ni la
interfaz, ni se ha cambiado ninguna configuración — solo lectura de logs.
Metodología: `journalctl` dentro de WSL (Ubuntu-24.04, con acceso de
lectura vía grupo `adm`, sin `sudo`), Visor de sucesos de Windows vía
`Get-WinEvent`, `.wslconfig`, `wsl.exe --status`, `systemctl show docker`,
`dmesg`, `free -h`.

## Resumen ejecutivo

Hay dos mecanismos de caída completamente distintos, y solo uno seguía
activo en el momento del diagnóstico:

1. **Causa 1 (ya corregida, verificada activa):** `vmIdleTimeout` por
   defecto (60 s) suspendía la VM de WSL2 sin actividad. El arreglo
   (`vmIdleTimeout=-1` en `.wslconfig`) sigue aplicado y sigue siendo
   efectivo.
2. **Causa 2 (nueva, caracterizada, no corregida):** el modo de ahorro de
   energía **Modo de espera moderno (S0ix, "Red conectada")** de Windows
   provoca, al reanudarse, una reinicialización forzada del *init* de la
   distro WSL (systemd, y con él `dockerd` y todos los contenedores) sin
   que se reinicie la VM ni el kernel. Ocurrió 2 veces en las ~84 horas
   posteriores al arreglo de la causa 1, ambas la misma mañana
   (2026-09-03), ninguna desde entonces.

Memoria, hibernación clásica (S3), Windows Update y actualizaciones de WSL
quedan descartados con evidencia (detalle abajo). No hay ninguna caída de
`dockerd` en solitario (sin caída de toda la distro) en todo el historial
disponible del journal.

---

## Reconstrucción del historial

`journalctl --list-boots` es la fuente más fiable porque el `boot_id` lo
genera el kernel (UUID aleatorio en cada arranque real), no algo que WSL o
systemd puedan falsear.

- **17 arranques de kernel** en el histórico disponible del journal
  (persiste desde 2026-08-12).
- **Cluster de 9 arranques cortísimos** el 2026-09-02 entre las 16:04 y
  las 17:22 (cada uno de 1 a 10 minutos) — esto es la causa 1, la VM
  muriendo por `vmIdleTimeout` cada vez que pasaba un minuto sin actividad.
  El mismo patrón, más disperso, se ve desde el 12 de agosto y durante toda
  la mañana del 2 de septiembre (11:45–16:58): decenas de arranques de
  minutos de duración.
- **Un único arranque de kernel desde las 17:22:22 del 2026-09-02 hasta
  ahora** (`boot_id dca8a721...`, cuatro días sin interrupción). Esto
  confirma que el arreglo de `vmIdleTimeout` corta de raíz el problema
  original: cero arranques de kernel provocados por inactividad desde que
  se aplicó.

### El evento que sigue ocurriendo dentro de ese único arranque

Buscando la firma completa del suceso (```journalctl | grep "The system
will power off now"```, que aparece justo antes de que systemd empiece a
parar servicios) contra **todo** el histórico, se cuentan 54
apariciones. Deduplicadas por marca de tiempo:

- Todas menos dos caen dentro del cluster de la causa 1 (2026-09-02,
  11:45–22:18) — es el mismo suceso, era el síntoma con el que se
  diagnosticó `vmIdleTimeout` la primera vez.
- **Solo dos ocurren después del arreglo**, ambas el 2026-09-03: **09:12:39**
  y **10:13:24**. Ninguna más en las siguientes ~84 horas hasta el momento
  del diagnóstico (2026-09-06 09:46).

Para las dos de después del arreglo, se comprobó el `_BOOT_ID` justo antes
y justo después de cada una: **es el mismo** (`dca8a721...`). No hubo
reinicio de la VM ni del kernel — lo que ocurre es que el *init* de la
distro (systemd, PID 1 dentro de Ubuntu-24.04) recibe algo equivalente a
una señal ACPI de apagado, ejecuta un apagado limpio de todos sus
servicios (incluido `docker.service`, con `SIGTERM` normal, forzando a los
10 s los contenedores que no responden), y ~15 segundos después WSL
reinicia ese mismo init desde cero — sin que la VM subyacente se haya
movido. El registro justo antes de cada suceso siempre trae la misma firma:

```
Exception:
unknown: Operation canceled @p9io.cpp:258 (AcceptAsync)
systemd-logind[...]: The system will power off now!
systemd-logind[...]: System is powering down.
```

`p9io.cpp` es la capa de interoperabilidad 9P de WSL (la que expone
`/mnt/c/...`). Su excepción justo en el instante del apagado es la pista
de que el disparador viene del lado de la VM/host, no de dentro de Linux.

### Qué precede al suceso de las 09:12:39

En los cinco minutos previos (09:08:00–09:12:23) el journal registra
`systemd-resolved: Clock change detected. Flushing caches.` **repetido
cada 30–70 segundos** — el reloj de la VM saltando una y otra vez. Eso
es la firma de una VM que se está pausando y reanudando en ráfagas cortas
a nivel de hipervisor, no de un proceso que se cuelga dentro de Linux.

Ese mismo suceso empieza **4 minutos después** de que el portátil saliera
del modo de espera moderno por apertura de tapa
(`Microsoft-Windows-Kernel-Power`, id 507, "saliendo del modo de espera
moderno, motivo: Lid", 09:08:05). No hay una reanudación limpia entre esa
hora y la medianoche siguiente — la máquina permanece despierta hasta las
22:45. El segundo suceso, a las 10:13:24, ocurre ~65 minutos después, sin
ningún evento de suspensión/reanudación de Windows registrado entre medias
(comprobado con `Get-WinEvent` sobre `Microsoft-Windows-Kernel-Power` para
todo el día 3 de septiembre) — es decir, es una réplica tardía del mismo
episodio de reanudación fallida, no un segundo disparador independiente.

---

## Sospechas descartadas, con evidencia

| Sospecha | Resultado | Evidencia |
|---|---|---|
| Windows suspende/hiberna la máquina entera y se lleva la VM | **Descartado como causa directa de las dos caídas de después del arreglo** | El sistema usa Modo de espera moderno (S0, "Red conectada"), no S3 clásico. Inicio rápido está deshabilitado por directiva (`powercfg /a`), así que tampoco es un factor. No hay ningún evento `Kernel-Power` 506/507 exactamente en las dos ventanas de caída — lo que sí hay es una reanudación 4 min antes de la primera, y el reloj de la VM saltando repetidamente justo antes de ambas, consistente con micro-pausas de energía del Modo de espera moderno que no siempre generan un evento 506/507 completo. |
| Límite de memoria de WSL agotado por los contenedores en un reproceso | **Descartado** | `.wslconfig` asigna 24 GB a la VM. En reposo el uso real es 2,6 GiB. El pico de memoria más alto documentado de `docker.service` en un reproceso completo (sección "Rendimiento de `6.23/28510.0051`" de `CONTEXTO.md`) fue 2,9 GiB. Margen amplísimo — no hay presión de memoria posible con la carga actual. |
| `dockerd` muere por falta de memoria (OOM) | **Descartado** | `dmesg` no tiene ni una entrada de `oom-killer` en todo el historial disponible. Ninguna de las caídas encontradas es un OOM. |
| Actualizaciones automáticas de WSL o de Windows reiniciando la VM | **Descartado** | El paquete `MicrosoftCorporationII.WindowsSubsystemForLinux` no se ha modificado desde 2026-07-05. Windows Update instaló solo firmas de Defender y apps de la Store ese día, ninguna cerca de los dos sucesos y ninguna que exija reinicio. No hay tarea programada ni evento de AppX relacionado con WSL en esas ventanas. |
| `.wslconfig` no se aplicó de verdad / dejó de aplicarse | **Descartado** | El fichero (`C:\Users\LUCAS\.wslconfig`) contiene `vmIdleTimeout=-1` ahora mismo, y el propio historial de arranques lo confirma: el cluster de arranques cortos termina exactamente donde arranca el único boot largo de 4 días. Si el ajuste se hubiera dejado de aplicar, el patrón de arranques de 1-10 min habría continuado — y no lo hizo. |
| `dockerd` se cuelga o muere en solitario (sin que caiga toda la distro) | **Descartado como mecanismo independiente** | `journalctl -u docker` no tiene ni un "Main process exited"/"Failed with result"/segfault/panic en todo el historial. Todas las interrupciones de `docker.service` encontradas son la consecuencia de la distro entera recibiendo la señal de apagado, nunca `dockerd` cayendo por su cuenta. |

**Ruido que no es la causa, verificado:** los mensajes `healthcheck failed
fatally: ... only one connection allowed` que aparecen muy a menudo en el
journal de `docker` (varias veces por hora) son de un healthcheck de
sesión de `containerd`/buildkit, no de un fallo de `dockerd`. `docker.service`
lleva activo sin interrupción desde el 2026-09-03 10:13:40 pese a esos
mensajes — no le impiden seguir funcionando, y no deben confundirse con
las caídas reales.

---

## Estado actual de recursos (verificado)

```
memory=24GB / processors=16 / swap=8GB   (.wslconfig)
free -h dentro de WSL:  23Gi total, 2.6Gi usados, 20Gi disponibles
docker.service MemoryPeak: 2.7 GiB (pico histórico de esta sesión de VM)
```

Sin margen de preocupación para el día de la demo. Esto no es el
cuello de botella.

---

## Qué falta hoy (comprobado, no supuesto)

- `docker.service` **ya** tiene `Restart=always` y está `enabled` — si
  la distro está corriendo y `dockerd` muriera por su cuenta, ya se
  reiniciaría solo. Esta parte del punto 5 del encargo ya está resuelta,
  sin que nadie la haya configurado a propósito (es el valor de fábrica
  del paquete `docker.io`/`docker-ce` de Ubuntu).
- Lo que **no** existe: nada arranca la distro de WSL automáticamente al
  iniciar sesión en Windows. Hoy WSL (y por tanto `dockerd`, aunque esté
  `enabled`) solo se pone en marcha cuando algo la invoca explícitamente
  (abrir una terminal, VS Code conectándose, etc.). No hay tarea
  programada ni acceso directo en la carpeta de inicio que lance
  `wsl.exe`. Esto confirma el punto de partida del encargo: "hoy hay que
  levantarlo a mano".

---

## Solución propuesta y coste

**Para el día de la demo, en orden de coste:**

1. **Impedir que Windows entre en modo de espera mientras dure la demo**
   (cambiar el plan de energía a "nunca" suspender con el equipo
   enchufado). Coste: cero — es un ajuste de energía, no de WSL ni de
   Docker, revertible en un clic, y elimina de raíz el disparador de la
   causa 2 porque la VM nunca se pausa. Contrapartida: hay que
   acordarse de mantener el portátil enchufado (con "nunca suspender"
   activo y sin corriente se agotaría la batería sin que el usuario lo
   note).
2. **Más duradero, para el uso diario post-demo:** identificar y
   desactivar el origen de reanudación con motivo `16777220` (visible
   repetidas veces en `Microsoft-Windows-Kernel-Power`, típicamente un
   adaptador de red con "reactivación por LAN/paquete mágico" armado) vía
   `powercfg -devicequery wake_armed` / `powercfg -deviceenablewake`.
   Coste: bajo, pero solo neutraliza ese disparador concreto — el modo de
   espera moderno seguiría activo para todo lo demás, y la fragilidad de
   WSL2 al reanudarse de él podría reaparecer por otra vía (p. ej. la
   tapa).
3. **Si ninguna de las dos convence:** no depender de este portátil el
   día de la demo — correr el stack en una máquina que no entre en
   suspensión (otra máquina siempre encendida, una VM en la nube, o
   simplemente este mismo portátil con la opción 1 aplicada). No hace
   falta abandonar WSL2 como plataforma: el problema no es WSL2 en sí,
   es la interacción entre el modo de espera moderno de Windows y la
   reanudación de la VM ligera de WSL2. Con la opción 1 aplicada, WSL2
   es una base perfectamente válida para la demo.

**Salvaguarda pedida (independiente de la causa):** crear una tarea
programada de Windows (Programador de tareas), para el usuario actual,
que ejecute `wsl.exe -d Ubuntu-24.04 -- true` (o equivalente) al iniciar
sesión — esto arranca la distro (y con ella, por estar `enabled`,
`docker.service`) sin intervención manual. `Restart=always` ya cubre la
parte de "que se reinicie solo si muere" una vez la distro está arriba.
Coste: una tarea programada, reversible, con alcance solo al usuario
actual — **no se ha creado todavía**, a la espera de confirmación (ver
nota más abajo).

---

## Acciones aplicadas en esta sesión (con confirmación del usuario)

Tras el diagnóstico, se aplicaron y verificaron las dos acciones
propuestas. Detalle de comandos, valores previos y cómo revertir cada una:
`README.md`, sección "Segunda causa de caída: reanudación del modo de
espera moderno de Windows". Resumen:

1. **Cierre de tapa en corriente → no hace nada** (antes suspendía).
   Comprobado con `powercfg /query`: la suspensión por inactividad en
   corriente ya estaba en "Nunca" (`0x00000000`), así que no era el
   disparador — el disparador real que sí estaba activo era la acción de
   cierre de tapa, confirmada por los propios eventos `Kernel-Power` con
   `motivo: Lid`.
2. **Tarea programada `ADIF-WSL-Docker-Autostart`**, solo para el usuario
   actual: arranca WSL y `docker.service` al iniciar sesión. Verificada
   en caliente en esta misma sesión: se terminó la distro
   (`wsl --terminate Ubuntu-24.04`, quedó `Stopped`), se disparó la tarea
   manualmente (`Start-ScheduledTask`), y la distro volvió a `Running`
   con `docker.service active` sin ninguna intervención manual adicional.
   **No se pudo verificar con un reinicio real de sesión/equipo** — se
   evitó deliberadamente porque habría cortado esta misma sesión de
   diagnóstico; la simulación de arriba (terminar + disparar la tarea) es
   equivalente en la práctica, ya que es exactamente la secuencia que
   ejecuta Windows al iniciar sesión.

**Hueco que ninguna de las dos cubre:** `docker-compose.yml` no define
`restart:` en ningún servicio, así que los contenedores de ADIF en sí
(no `dockerd`) no se recuperan solos tras una caída — hace falta
`docker compose up -d` de nuevo. Sin tocar el motor esta sesión, queda
anotado como pendiente para una sesión de código si se quiere cerrar del
todo el punto 5 del encargo original.

## Cuándo NO debería volver a ocurrir la causa 2

El mecanismo completo depende de una reanudación real desde suspensión —
tanto la caída de las 09:12:39 (cuatro minutos después de un evento de
reanudación por tapa) como la de las 10:13:24 (réplica tardía del mismo
episodio, sin una reanudación nueva de por medio) ocurrieron dentro de la
misma mañana en la que el portátil había estado suspendido y se reanudó.
**Si el día de la demo el portátil se mantiene enchufado y despierto sin
suspenderse en ningún momento — que es justo lo que fuerzan los dos
cambios aplicados arriba —, no hay reanudación que dispare esta causa.**
No se ha vuelto a observar ni una sola vez en los cuatro días transcurridos
entre el arreglo original y este diagnóstico, ventana en la que el equipo
sí se suspendió y reanudó varias veces por otros motivos (madrugadas,
cierres de tapa) sin volver a producir el suceso — así que ni siquiera es
un 100% de correlación observada, pero es el único patrón consistente con
la evidencia y el que mantener el equipo despierto elimina por completo.

---

## Causa 2: cerrada de raíz (sesión 2026-09-07) — y una causa 3 nueva, distinta, encontrada al verificarlo

El usuario desactivó el Modo de espera moderno a nivel de firmware
(`PlatformAoAcOverride = 0` en el registro, fuera del alcance de este
repositorio — requiere privilegios de administrador de Windows) y
reinició el equipo. Confirmado con `powercfg /a`: el sistema ya solo
ofrece **Modo de espera (S3)** e **Hibernar** — el S0ix que causaba la
causa 2 ya no existe como estado posible. Revertir: `README.md`.

**Verificación de que la causa 2 en sí ya no puede dispararse:** en toda
la ventana de esta sesión (más de 20 minutos de sondeo activo) no hubo
**ni un solo evento `Kernel-Power`** en el registro de sucesos de Windows
— ni suspensión, ni reanudación, ni cambio de tapa, ni cambio de fuente de
energía salvo los del propio arranque. El mecanismo que investigaba este
documento (reanudación de S0ix forzando un reinicio del *init* de la
distro) no tiene ningún evento de reanudación del que dispararse. Causa 2:
**cerrada**, con evidencia, no solo con la ausencia teórica del estado de
energía.

### Pero el stack se seguía cayendo — mucho más seguido que antes

Con la tarea `ADIF-WSL-Docker-Autostart` disparada con éxito al iniciar
sesión (confirmado, `LastTaskResult 0`, 16s después del arranque), el
navegador seguía dando `ERR_CONNECTION_REFUSED` media hora después. Cuatro
sondas sucesivas desde Windows (`Invoke-WebRequest` a `http://localhost:3000/`
cada 3s, sin tocar WSL durante la medición, mismo método que la sección 6
de `docs/tolerancia-reinicios-dockerd.md`) aislaron la causa:

| Sonda | Configuración | Resultado |
|---|---|---|
| 1 | `ADIF-WSL-Docker-Watchdog` activo (cada 1 min), 11 min | **12 cortes, ~40s cada uno, uno por minuto** |
| 2 | Watchdog desactivado, 4 min | 1 corte — **no se recuperó en todo el tramo** |
| 3 | Watchdog desactivado, arranque limpio inmediatamente antes, 2:30 min | Igual: cae a los 14s de desactivarlo y no vuelve |
| 4 | Watchdog desactivado, con una sesión `wsl.exe` **persistente** conectada (`wsl.exe -d Ubuntu-24.04 -- sleep 200`, sin relación con Docker) | **0 cortes, 0 fallos en 170s** |

`journalctl` dentro de WSL, durante una de las ventanas de corte de la
sonda 1, confirma el mecanismo exacto:

```
Sep 07 09:33:29 Lucas unknown: WSL (2 - init-systemd(Ubuntu-24.04)) ERROR:
InitTerminateInstanceInternal:2763: systemctl poweroff did not terminate
the instance in 10000 ms, calling reboot(RB_POWER_OFF)
```

Ese mensaje aparece, en cada ciclo, entre 25 y 30 segundos después de que
el único cliente `wsl.exe` conectado en ese momento (la propia tarea
`ADIF-WSL-Docker-Watchdog`, que se conecta, ejecuta `systemctl start
docker` y se desconecta — patrón de un solo tiro, sin esperar) se
desconecta. **`WSL apaga sola la instancia entera en cuanto no queda
ningún cliente conectado**, sin relación ninguna con el modo de espera
moderno (no hay reanudación de por medio: `journalctl --list-boots` no
muestra ningún arranque de kernel nuevo en toda la ventana — es la
instancia de WSL derribando y relanzando su propio *init*, no la VM
reiniciándose) y **pese a `systemd=true` en `/etc/wsl.conf` y
`vmIdleTimeout=-1` en `.wslconfig`**, que en teoría debían bastar para
mantenerla viva de forma persistente. Es un mecanismo de WSL (build
2.7.10.0 de esta máquina) distinto y no documentado en la sección de
arriba, que esta sesión no había visto porque en las sesiones anteriores
siempre había alguna otra actividad de WSL (una terminal abierta, VS Code
conectado) manteniendo un cliente adjunto casi todo el tiempo — con la
máquina recién reiniciada y solo el Watchdog tocando WSL, cada
desconexión del Watchdog deja una ventana de ~25-30s sin ningún cliente,
tiempo de sobra para que se dispare.

Cada vez que esto ocurre, derriba el *init* entero — no solo `dockerd` —
así que los cuatro contenedores mueren a la fuerza (`Container failed to
exit within 10s of signal 15 - using the force`, visible en el log de
`dockerd` en cada ciclo) y se reconstruyen desde cero al arrancar de
nuevo, **incluida `postgres`**, cuando el siguiente disparo del Watchdog
(un minuto después) reconecta y relanza la instancia. El propio Watchdog,
pensado como red de seguridad para la causa 2, era sin darse cuenta el
mecanismo que mantenía vivo el sistema frente a esta causa 3 — pero al
precio de un derribo completo del stack cada minuto.

### El arreglo: una sesión persistente, no una reconexión periódica

La sonda 4 señala la solución directamente: si nunca se desconecta ningún
cliente, WSL no tiene ventana en la que apagar la instancia. Sustituida
`ADIF-WSL-Docker-Watchdog` (reconexión de un solo tiro cada minuto) por
**`ADIF-WSL-Docker-Keepalive`**: una tarea programada al iniciar sesión
que ejecuta, oculta (mismo patrón `wscript.exe` + `.vbs` de siempre, ver
sección 5 de `docs/tolerancia-reinicios-dockerd.md`), un bucle que
mantiene un único `wsl.exe` conectado sin parar:

```vbscript
Do
    objShell.Run "wsl.exe -d Ubuntu-24.04 -u root -- bash -c ""systemctl start docker; exec sleep infinity""", 0, True
    WScript.Sleep 2000
Loop
```

`exec sleep infinity` nunca termina por sí solo, así que la sesión queda
conectada indefinidamente; si `wsl.exe` muriera de verdad (un fallo real,
no el autoapagado por inactividad, que ya no puede darse con un cliente
siempre conectado), el bucle reconecta a los 2s. `systemctl start docker`
se repite en cada reconexión, idempotente, por si acaso. Detalle de la
tarea programada y cómo revertirla: `README.md`.

**Verificación final:** sonda de 16 minutos (960s, sondeo cada 3s, 307
sondeos) con `ADIF-WSL-Docker-Keepalive` activo y
`ADIF-WSL-Docker-Watchdog` ya retirado — **0 sondeos fallidos, 0 cortes**.
Contraste directo con la sonda 1 de la tabla de arriba, misma metodología:
12 cortes de ~40s en 11 minutos con el Watchdog periódico, 0 cortes en 16
minutos con la sesión permanente.

### Causa 2 vs. causa 3 — qué cierra cada cosa

- **Causa 2 (Modo de espera moderno, reanudación real):** cerrada por el
  cambio de registro del usuario, `PlatformAoAcOverride = 0` — fuera de
  este repositorio, ver revertir en `README.md`. Nada en el motor ni en la
  infraestructura del proyecto la cierra por sí sola; dependía de una
  máquina con ese firmware desactivado.
- **Causa 3 (autoapagado de la instancia de WSL sin cliente conectado):**
  cerrada por `ADIF-WSL-Docker-Keepalive`, dentro del alcance de este
  repositorio (tarea programada de Windows, igual que las otras, no
  código del motor). Sigue sin identificarse la causa raíz exacta dentro
  de WSL (¿un cambio de comportamiento entre versiones de WSL, un ajuste
  de `.wslconfig` más específico que `vmIdleTimeout` que la haría
  innecesaria? No investigado esta sesión) — el arreglo aplicado es un
  mitigante que la evidencia (sonda 4) confirma que funciona, no una
  corrección de WSL en sí, que está fuera del alcance de este
  repositorio.
