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
| Límite de memoria de WSL agotado por los contenedores en un reproceso | **Descartado** | `.wslconfig` asigna 24 GB a la VM. En reposo el uso real es 2,6 GiB. El pico de memoria más alto documentado de `docker.service` en un reproceso completo (sección "Rendimiento de `6.23/28510.0051`" de `CLAUDE.md`) fue 2,9 GiB. Margen amplísimo — no hay presión de memoria posible con la carga actual. |
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
