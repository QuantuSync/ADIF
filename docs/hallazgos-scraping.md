# Hallazgos de scraping

Registro histórico movido desde `CLAUDE.md` (split de sesión 2026-09-05).
Ver `CLAUDE.md` para el contexto vivo del proyecto.

---

## 17. Hallazgos de scraping (cierre del punto 2 del orden de trabajo)

Verificado en vivo, headless, contra la Plataforma real y dentro del contenedor
Linux del worker (no solo en un script suelto). Ver `engine/app/scraping/pcsp.py`.

- **El WAF distingue por tipo de URL, no rechaza toda descarga fuera del
  navegador sin más.** Matizado en la sesión de sindicación (2026-09-02, ver
  `docs/hallazgos-sindicacion.md`, sección 17.1): las URLs capturadas del evento `download` dentro de la sesión
  de navegador (estado JSF) sí requieren el motor de render — un cliente HTTP
  aparte, incluso replicando cabeceras de un navegador real, es rechazado. Pero
  las URLs `docAccCmpnt` con `DocumentIdParam` que trae el XML de sindicación
  se descargaron con cliente HTTP plano (`curl -k`, sin cookies ni cabeceras de
  navegador) sin problema: dos URIs reales probadas, HTTP 200 y PDF correcto en
  ambas. Pendiente: no se ha probado con volumen, así que no se descarta
  limitación de tasa. **La conclusión práctica se mantiene: la automatización
  de navegador sigue siendo necesaria, porque el problema no es la descarga —
  esa parte puede que ya esté resuelta para las URLs de sindicación — sino el
  descubrimiento del documento, y la sindicación no lo cubre de forma fiable
  (ver `docs/hallazgos-sindicacion.md`, sección 17.1).**
- Los identificadores JSF del formulario de búsqueda y los selectores
  `GetDocumentByIdServlet` y `docAccCmpnt` siguen siendo válidos a fecha de esta
  sesión (2026-09-02).
- El camino de abrir la tarjeta "Licitaciones" antes de que aparezca el input de
  búsqueda se toma siempre en headless, no es un caso excepcional.
- La ruta de almacenamiento de cada documento va por hash de contenido, nunca
  por índice (`CONTRATO_1.pdf`, `CONTRATO_2.pdf`...), para que reprocesar un
  expediente y encontrar contenido distinto en el mismo hueco no pise el fichero
  que una fila de `documentos` anterior sigue referenciando por su hash.
- **`dockerd` no arranca solo en WSL**, y no solo al abrir la distro: durante
  esta misma sesión el contenedor del stack completo se cayó dos veces sin
  intervención (`docker compose ps` mostraba los cuatro servicios "Exited" y
  `dockerd` con un `Active: ... since` de segundos antes) con apenas minutos de
  diferencia. Los volúmenes con nombre (Postgres, documentos) sobreviven a esos
  reinicios; los trabajos de la cola que estaban `en_proceso` en ese momento se
  quedan huérfanos (bloqueados por un contenedor que ya no existe) y no se
  vuelven a recoger solos — hay que resetear su `estado` a `pendiente` a mano.
  Antes de dar por caído el worker, comprobar siempre `systemctl status docker`
  en la distro.
- **Un mismo procedimiento puede tener dos documentos de adjudicación válidos
  a la vez**: la Propuesta de Adjudicación (plantilla LC.27, firma el
  Presidente de la Mesa de Contratación) y, más tarde, la Resolución de
  Adjudicación (firma el órgano de contratación). Verificado con el
  expediente `6.24/28510.0008`: la Resolución cita explícitamente a la
  Propuesta ("de acuerdo con la Propuesta... de 29 de mayo de 2024") y ambas
  declaran los mismos importes y la misma baja (54,00% en este caso). **El
  motor debe tratarlas como el mismo hecho, no como datos en conflicto, y
  preferir la Resolución cuando existan las dos** — es el acto posterior y
  definitivo del mismo procedimiento.
- **Pendiente: recuperación de trabajos huérfanos.** Hoy un trabajo puede
  quedarse en `en_proceso` bloqueado por un worker que ya no existe (contenedor
  caído, `dockerd` reiniciado a mitad de ejecución — ver más arriba) y nada lo
  recoge de nuevo: `tomar_siguiente_trabajo` solo mira `estado = pendiente`, así
  que ese trabajo se pierde hasta que alguien lo resetea a mano. Solución
  prevista, sin implementar todavía: usar `bloqueado_en` (ya existe en el
  modelo) como marca de tiempo de bloqueo, y que el worker, antes de pedir un
  trabajo nuevo, reclame como `pendiente` cualquier trabajo `en_proceso` cuyo
  `bloqueado_en` supere un umbral razonable (p. ej. varias veces el timeout de
  navegación del scraping), respetando `intentos`/`max_intentos` igual que un
  fallo normal.

---

## 17.4 Estabilidad de `dockerd` en WSL: `vmIdleTimeout` (sesión 2026-09-02)

Ajuste de máquina, no de proyecto — documentado también en el `README.md`
raíz porque afecta a cualquiera que desarrolle en este equipo, no solo a
este repositorio.

- **Causa encontrada de las caídas de `dockerd` de la sección 17 (nueve en
  una sola sesión):** el `vmIdleTimeout` de WSL2 (por defecto 60000 ms) —
  la VM ligera de WSL se suspende sola sin ningún comando `wsl` ni proceso
  adjunto activo durante ese tiempo, y se lleva `dockerd` con ella. No es un
  fallo de Docker ni de la distro: es el comportamiento por defecto de WSL2
  documentado para ese ajuste.
- **Corregido con `vmIdleTimeout=-1` en `C:\Users\<usuario>\.wslconfig`**
  (fuera del repositorio, uno por máquina — ver README). Aplicado con
  `wsl --shutdown` seguido de un arranque limpio; **verificado que aguanta**
  dejando la VM sin ningún comando `wsl` activo durante 90 segundos seguidos
  (por encima del umbral por defecto de 60 s que causaba la caída) y
  comprobando después que `docker.service` seguía con el mismo `Active:
  ... since` de antes de la espera, sin reinicio.
- **Matizado en la sesión de catálogo (2026-09-02, sección 18 de
  `docs/hallazgos-extraccion.md`): la caída volvió a pasar con
  `vmIdleTimeout=-1` ya aplicado**, varias veces en la
  misma sesión (`journalctl -u docker` mostró `Processing signal
  'terminated'` seguido de `Stopping docker.service` cada ~50-90 s mientras
  había comandos `docker compose` activos, con la distro WSL en estado
  `Running` todo el tiempo — no es el mismo síntoma que la suspensión de VM
  documentada arriba). Causa real sin confirmar todavía. Mitigación que
  funcionó en la práctica: mantener un `docker compose up` en primer plano
  (sin `-d`) corriendo en una shell de fondo mientras se opera el stack
  desde otra — reduce la frecuencia de caídas pero no las elimina del todo.
  **No dar por cerrado el hallazgo de `vmIdleTimeout` de arriba como
  solución completa.**
