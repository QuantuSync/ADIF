"use client";

import { useEffect, useState } from "react";
import { DatoVacio } from "../ui";
import { useReintentoConexion } from "../useReintentoConexion";

type Trabajo = {
  id: number;
  tipo: string;
  estado: string;
  intentos: number;
  max_intentos: number;
  payload: Record<string, unknown> | null;
  resultado: Record<string, unknown> | null;
  error: string | null;
  created_at: string;
  updated_at: string;
};

type EstadoMantenimiento = {
  ultima_ejecucion: Trabajo | null;
  en_curso: boolean;
  proxima_ejecucion: string;
  intervalo_segundos: number;
  programado_activo: boolean;
};

// BLOQUE 1, sesión de auditoría automática (2026-09-08): forma de cada
// entrada de `resultado.hallazgos` de un trabajo `auditoria_catalogo`
// (`app.mantenimiento.auditoria.Hallazgo.to_dict`).
type HallazgoAuditoria = {
  categoria: string;
  gravedad: "error" | "aviso";
  mensaje: string;
  expedientes: string[];
  total_afectados: number | null;
  detalle: Record<string, unknown> | null;
};

const INTERVALO_SONDEO_MS = 4000;

function formatearFecha(iso: string): string {
  return new Date(iso).toLocaleString("es-ES");
}

// Segundos legibles como "cada 7 días" / "cada 30 minutos" en vez de un
// número de segundos crudo -- lo que de verdad va a configurar quien opere
// el sistema (CONTEXTO.md bloque 3, punto 1: "configurable en frecuencia").
function formatearIntervalo(segundos: number): string {
  if (segundos >= 86400) return `cada ${(segundos / 86400).toFixed(segundos % 86400 === 0 ? 0 : 1)} día(s)`;
  if (segundos >= 3600) return `cada ${(segundos / 3600).toFixed(segundos % 3600 === 0 ? 0 : 1)} hora(s)`;
  if (segundos >= 60) return `cada ${(segundos / 60).toFixed(segundos % 60 === 0 ? 0 : 1)} minuto(s)`;
  return `cada ${segundos.toFixed(0)} s`;
}

function disparadoPor(trabajo: Trabajo): string {
  const valor = trabajo.payload?.disparado_por;
  return valor === "programado" ? "Programado" : valor === "manual" ? "Manual" : "";
}

// No hay ninguna vía de código que produzca esta marca (comprobado: no
// aparece en ningún .py) — es texto que alguien escribe a mano en la base
// de datos para desatascar un trabajo durante desarrollo, nunca un fallo
// real del sistema. Encargo de la sesión de pulido de 1280px: que no se
// lea como un fallo real de extracción/scraping.
function esInterrupcionManual(trabajo: Trabajo): boolean {
  return trabajo.estado === "fallido" && !!trabajo.error?.toLowerCase().includes("abortado manualmente");
}

function ResumenCiclo({ resultado }: { resultado: Record<string, unknown> | null }) {
  if (!resultado) return null;
  const descubrimiento = resultado.descubrimiento as Record<string, unknown> | null | undefined;
  return (
    <div style={{ fontSize: "0.85rem" }}>
      <div>
        {String(resultado.nuevos_descubiertos ?? 0)} nuevo(s) · {String(resultado.descargas_lanzadas ?? 0)} descarga(s) ·{" "}
        {String(resultado.extracciones_lanzadas ?? 0)} extracción(es) · {String(resultado.trabajos_drenados ?? 0)} trabajo(s)
        drenado(s) · {Number(resultado.duracion_segundos ?? 0).toFixed(1)} s
      </div>
      {descubrimiento && !descubrimiento.error && (
        <div className="muted">
          sindicación {String(descubrimiento.periodo)}: {String(descubrimiento.expedientes_adif_total)} de ADIF,{" "}
          {String(descubrimiento.expedientes_filtrados)} con el departamento en el código,{" "}
          {String(descubrimiento.expedientes_con_cambio_estado)} con cambio de estado
        </div>
      )}
      {Boolean(descubrimiento?.error) && (
        <div className="status-note">sindicación falló: {String(descubrimiento!.error)}</div>
      )}
    </div>
  );
}

// BLOQUE 1, sesión de auditoría automática (2026-09-08): un hallazgo por
// fila, con su gravedad y los expedientes afectados (recortada por el
// backend a `_LIMITE_EXPEDIENTES`; `total_afectados` es siempre la cifra
// real aunque la lista venga más corta). "No corrige nada por su cuenta,
// solo detecta y avisa" -- esta pantalla es exactamente ese aviso.
function FilaHallazgo({ hallazgo }: { hallazgo: HallazgoAuditoria }) {
  const masExpedientes = (hallazgo.total_afectados ?? hallazgo.expedientes.length) - hallazgo.expedientes.length;
  return (
    <li style={{ marginBottom: "0.6rem" }}>
      <span className={`status ${hallazgo.gravedad === "error" ? "status-attn" : ""}`}>
        {hallazgo.gravedad === "error" ? "Error" : "Aviso"}
      </span>{" "}
      <strong>{hallazgo.categoria}</strong>
      <div style={{ margin: "0.2rem 0 0" }}>{hallazgo.mensaje}</div>
      {hallazgo.expedientes.length > 0 && (
        <div className="muted" style={{ marginTop: "0.2rem" }}>
          Expedientes: {hallazgo.expedientes.join(", ")}
          {masExpedientes > 0 ? ` (+${masExpedientes} más)` : ""}
        </div>
      )}
    </li>
  );
}

// Bloque 6, sesión de comparación documento-vs-listado interno: forma de
// `resultado` de un trabajo `ingesta_local`
// (`app.ingesta_local.ResumenIngestaLocal.to_dict`).
type ResumenIngestaLocal = {
  configurado: boolean;
  carpetas_leidas: number;
  carpetas_sin_codigo_reconocible: number;
  expedientes_nuevos: number;
  expedientes_existentes: number;
  documentos_nuevos: number;
  documentos_ya_conocidos: number;
  enlaces_nuevos: number;
  documentos_codigo_declarado_distinto: number;
  expedientes_reencolados: number;
};

// Sin programación propia (a diferencia de la auditoría, que se encola sola
// al final de cada ciclo): el cliente avisa cuando su macro deja ficheros
// nuevos en la carpeta, así que esto es solo un botón manual y su último
// resultado -- no hace falta la forma completa de `EstadoMantenimiento`
// (frecuencia, próxima ejecución) que no aplica aquí.
function PanelIngestaLocal({
  ultimaEjecucion, onLanzar, lanzando,
}: {
  ultimaEjecucion: Trabajo | null;
  onLanzar: () => void;
  lanzando: boolean;
}) {
  const resultado = (ultimaEjecucion?.resultado ?? null) as ResumenIngestaLocal | null;
  return (
    <div className="card" style={{ marginBottom: "1.5rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "1rem" }}>
        <div>
          <p className="section-label" style={{ margin: 0 }}>Ingesta manual de documentos</p>
          <p className="muted" style={{ margin: "0.3rem 0 0" }}>
            Expedientes vigentes en el SAP del cliente que no están publicados en la Plataforma, aportados en una
            carpeta local.
          </p>
        </div>
        <button
          onClick={onLanzar}
          disabled={lanzando || ultimaEjecucion?.estado === "en_proceso" || ultimaEjecucion?.estado === "pendiente"}
          className="btn btn-secondary"
        >
          {lanzando ? "Lanzando…" : "Ejecutar ahora"}
        </button>
      </div>
      {!ultimaEjecucion ? (
        <p className="muted" style={{ marginTop: "0.8rem" }}>Todavía no se ha ejecutado nunca.</p>
      ) : ultimaEjecucion.estado !== "completado" ? (
        <div style={{ marginTop: "0.8rem" }}>
          <span className={`status ${ultimaEjecucion.estado === "fallido" ? "status-attn" : ""}`}>
            {ultimaEjecucion.estado === "fallido" ? "La última ejecución falló" : ultimaEjecucion.estado}
          </span>
          {ultimaEjecucion.error && <p style={{ margin: "0.35rem 0 0" }}>{ultimaEjecucion.error}</p>}
        </div>
      ) : !resultado?.configurado ? (
        <p className="muted" style={{ marginTop: "0.8rem" }}>
          No hay ninguna ruta configurada (<code>INGESTA_LOCAL_PATH</code>) -- no hace nada.
        </p>
      ) : (
        <div className="muted" style={{ marginTop: "0.8rem", fontSize: "0.85rem" }}>
          {formatearFecha(ultimaEjecucion.created_at)} · {resultado.carpetas_leidas} carpeta(s) leída(s) ·{" "}
          {resultado.expedientes_nuevos} expediente(s) nuevo(s), {resultado.expedientes_existentes} ya
          conocido(s) · {resultado.documentos_nuevos} documento(s) nuevo(s), {resultado.enlaces_nuevos} enlace(s)
          nuevo(s)
          {resultado.carpetas_sin_codigo_reconocible > 0 && (
            <div>
              <span className="status status-attn">
                {resultado.carpetas_sin_codigo_reconocible} carpeta(s) sin código de expediente reconocible
              </span>
            </div>
          )}
          {resultado.documentos_codigo_declarado_distinto > 0 && (
            <div>
              <span className="status status-attn">
                {resultado.documentos_codigo_declarado_distinto} documento(s) cuyo código propio no coincide con
                su carpeta -- sin enlazar, ver el expediente correspondiente
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function PanelAuditoria({ estado }: { estado: EstadoMantenimiento | null }) {
  if (!estado) return null;
  const trabajo = estado.ultima_ejecucion;
  if (!trabajo) {
    return (
      <div className="card" style={{ marginBottom: "1.5rem" }}>
        <p className="section-label">Auditoría automática del catálogo</p>
        <p className="muted">
          Todavía no ha corrido ninguna — se lanza sola al terminar cada ciclo de mantenimiento.
        </p>
      </div>
    );
  }
  if (trabajo.estado !== "completado") {
    return (
      <div className="card" style={{ marginBottom: "1.5rem" }}>
        <p className="section-label">Auditoría automática del catálogo</p>
        <p>
          <span className="status status-attn">La última ejecución no terminó bien</span>
        </p>
        {trabajo.error && <p style={{ margin: "0.35rem 0 0" }}>{trabajo.error}</p>}
      </div>
    );
  }
  const resultado = trabajo.resultado ?? {};
  const hallazgos = (resultado.hallazgos as HallazgoAuditoria[] | undefined) ?? [];
  const totalErrores = Number(resultado.total_errores ?? 0);
  const totalAvisos = Number(resultado.total_avisos ?? 0);
  return (
    <div className="card" style={{ marginBottom: "1.5rem" }}>
      <p className="section-label">Auditoría automática del catálogo</p>
      <div className="muted" style={{ marginBottom: "0.6rem" }}>
        Última ejecución: {formatearFecha(trabajo.created_at)} · {String(resultado.total_lineas ?? 0)} línea(s) de{" "}
        {String(resultado.total_expedientes ?? 0)} expediente(s) revisadas -- solo detecta y avisa, nunca corrige nada
        por su cuenta.
      </div>
      {hallazgos.length === 0 ? (
        <p>
          <span className="status status-ok">Sin hallazgos</span>
        </p>
      ) : (
        <>
          <p style={{ marginBottom: "0.5rem" }}>
            <span className={`status ${totalErrores > 0 ? "status-attn" : ""}`}>{totalErrores} error(es)</span>{" "}
            <span className="status">{totalAvisos} aviso(s)</span>
          </p>
          <ul style={{ paddingLeft: "1.1rem", margin: 0 }}>
            {hallazgos.map((h, i) => (
              <FilaHallazgo key={`${h.categoria}-${i}`} hallazgo={h} />
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

export default function MantenimientoPanel({ apiUrl }: { apiUrl: string }) {
  const [estado, setEstado] = useState<EstadoMantenimiento | null>(null);
  const [historial, setHistorial] = useState<Trabajo[]>([]);
  const [estadoAuditoria, setEstadoAuditoria] = useState<EstadoMantenimiento | null>(null);
  const [ultimaIngesta, setUltimaIngesta] = useState<Trabajo | null>(null);
  // Conexión (sondeo pasivo): gateado, igual que en el resto de paneles.
  // `errorAccion` es de "lanzar ahora" -- una acción directa, avisa ya.
  const { error: errorConexion, confirmado, cargando, registrarExito, registrarFallo } = useReintentoConexion();
  const [errorAccion, setErrorAccion] = useState<string | null>(null);
  const [lanzando, setLanzando] = useState(false);
  const [lanzandoIngesta, setLanzandoIngesta] = useState(false);

  async function recargar() {
    try {
      const [resEstado, resHistorial, resAuditoria, resIngesta] = await Promise.all([
        fetch(`${apiUrl}/mantenimiento/estado`, { cache: "no-store" }),
        fetch(`${apiUrl}/mantenimiento/historial`, { cache: "no-store" }),
        fetch(`${apiUrl}/mantenimiento/auditoria/estado`, { cache: "no-store" }),
        fetch(`${apiUrl}/mantenimiento/ingesta-local/historial?limite=1`, { cache: "no-store" }),
      ]);
      if (!resEstado.ok) throw new Error(`la API respondió ${resEstado.status}`);
      if (!resHistorial.ok) throw new Error(`la API respondió ${resHistorial.status}`);
      if (!resAuditoria.ok) throw new Error(`la API respondió ${resAuditoria.status}`);
      if (!resIngesta.ok) throw new Error(`la API respondió ${resIngesta.status}`);
      setEstado(await resEstado.json());
      setHistorial(await resHistorial.json());
      setEstadoAuditoria(await resAuditoria.json());
      const historialIngesta: Trabajo[] = await resIngesta.json();
      setUltimaIngesta(historialIngesta[0] ?? null);
      registrarExito();
    } catch (e) {
      registrarFallo(e instanceof Error ? e.message : String(e));
    }
  }

  async function lanzarIngestaLocal() {
    setLanzandoIngesta(true);
    try {
      const res = await fetch(`${apiUrl}/mantenimiento/ingesta-local/ejecutar`, { method: "POST" });
      if (!res.ok) throw new Error(`la API respondió ${res.status}`);
      await recargar();
    } catch (e) {
      setErrorAccion(e instanceof Error ? e.message : String(e));
    } finally {
      setLanzandoIngesta(false);
    }
  }

  useEffect(() => {
    recargar();
    const id = setInterval(recargar, INTERVALO_SONDEO_MS);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function lanzarAhora() {
    setLanzando(true);
    try {
      const res = await fetch(`${apiUrl}/mantenimiento/ejecutar`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      if (!res.ok) throw new Error(`la API respondió ${res.status}`);
      await recargar();
    } catch (e) {
      setErrorAccion(e instanceof Error ? e.message : String(e));
    } finally {
      setLanzando(false);
    }
  }

  return (
    <div>
      {/* Estados de carga y error (CONTEXTO.md, bloque de estados de carga y
          error, sesión 2026-09-06): sin respuesta confirmada de la API
          todavía, ni el panel de estado ni el histórico se enseñan -- antes
          `estado` a `null` ya decía "Cargando…" arriba, pero el histórico
          vacío decía "Sin ejecuciones todavía" a la vez que este banner de
          error, un mensaje contradictorio. */}
      {cargando && <p className="muted">Cargando estado de mantenimiento…</p>}
      {errorConexion && (
        <p className="error-banner">
          Error al conectar con la API ({apiUrl}): {errorConexion}
        </p>
      )}
      {errorAccion && <p className="error-banner">{errorAccion}</p>}

      {confirmado && estado && (
        <>
          <div className="card" style={{ marginBottom: "1.5rem" }}>
            <p className="section-label">Ejecución programada</p>
            <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center" }}>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "2rem", alignItems: "flex-start", flex: "1 1 auto" }}>
                <div>
                  <div className="muted">Frecuencia</div>
                  <strong>
                    {estado.programado_activo ? formatearIntervalo(estado.intervalo_segundos) : "desactivada"}
                  </strong>
                </div>
                <div>
                  <div className="muted">Última ejecución</div>
                  <strong>
                    {estado.ultima_ejecucion ? formatearFecha(estado.ultima_ejecucion.created_at) : "nunca"}
                  </strong>
                  {estado.ultima_ejecucion && (
                    <span className="status-note status-note-inline"> {disparadoPor(estado.ultima_ejecucion)}</span>
                  )}
                </div>
                <div>
                  <div className="muted">Próxima ejecución</div>
                  <strong>
                    {estado.en_curso ? (
                      <span className="status status-attn">en curso ahora mismo</span>
                    ) : (
                      formatearFecha(estado.proxima_ejecucion)
                    )}
                  </strong>
                </div>
              </div>
              <button
                onClick={lanzarAhora}
                disabled={lanzando || estado.en_curso}
                className="btn btn-primary"
                style={{ marginLeft: "2rem" }}
              >
                {lanzando ? "Lanzando…" : "Lanzar ciclo ahora"}
              </button>
            </div>
            {estado.ultima_ejecucion && (
              <>
                <div className="hr" />
                {estado.ultima_ejecucion.estado === "fallido" ? (
                  esInterrupcionManual(estado.ultima_ejecucion) ? (
                    // Distinto de un fallo real (encargo de la sesión de pulido
                    // de 1280px): tono neutro, sin el acento de atención — es
                    // ruido de una sesión de diagnóstico, no un problema del
                    // sistema que alguien tenga que mirar.
                    <div>
                      <span className="status status-faint">Interrumpida manualmente</span>
                      <p className="muted" style={{ margin: "0.35rem 0 0" }}>
                        Se detuvo a mano durante una sesión de diagnóstico — no es un fallo real del motor de
                        mantenimiento. Puede lanzarse un ciclo nuevo cuando convenga.
                      </p>
                    </div>
                  ) : (
                    <div>
                      <span className="status status-attn">La última ejecución falló</span>
                      <p style={{ margin: "0.35rem 0 0" }}>{estado.ultima_ejecucion.error}</p>
                    </div>
                  )
                ) : (
                  <>
                    <p className="muted" style={{ marginBottom: "0.4rem" }}>
                      Qué encontró la última ejecución
                    </p>
                    <ResumenCiclo resultado={estado.ultima_ejecucion.resultado} />
                  </>
                )}
              </>
            )}
          </div>

          <PanelAuditoria estado={estadoAuditoria} />

          <PanelIngestaLocal ultimaEjecucion={ultimaIngesta} onLanzar={lanzarIngestaLocal} lanzando={lanzandoIngesta} />

          <p className="section-label">Histórico</p>
          <div className="table-scroll">
            <table className="table">
              <thead>
                <tr>
                  <th className="num">#</th>
                  <th>Origen</th>
                  <th>Estado</th>
                  <th>Lanzado</th>
                  <th>Terminado</th>
                  <th>Resumen</th>
                </tr>
              </thead>
              <tbody>
                {historial.map((trabajo) => {
                  const interrumpido = esInterrupcionManual(trabajo);
                  return (
                    <tr
                      key={trabajo.id}
                      className={trabajo.error && !interrumpido ? "row-accent row-accent-attn" : "row-accent"}
                    >
                      <td className="num">{trabajo.id}</td>
                      <td>{disparadoPor(trabajo)}</td>
                      <td>
                        <span
                          className={`status ${
                            trabajo.estado === "completado"
                              ? "status-ok"
                              : interrumpido
                              ? "status-faint"
                              : trabajo.estado === "fallido"
                              ? "status-attn"
                              : ""
                          }`}
                        >
                          {interrumpido ? "Interrumpido" : trabajo.estado}
                        </span>
                      </td>
                      <td>{formatearFecha(trabajo.created_at)}</td>
                      <td>
                        {trabajo.estado === "pendiente" || trabajo.estado === "en_proceso" ? (
                          <DatoVacio motivo="pendiente" titulo="Todavía no ha terminado." />
                        ) : (
                          formatearFecha(trabajo.updated_at)
                        )}
                      </td>
                      <td>
                        <ResumenCiclo resultado={trabajo.resultado} />
                        {trabajo.error && (
                          <div className="status-note" title={interrumpido ? trabajo.error ?? undefined : undefined}>
                            {interrumpido ? "Interrumpida manualmente para diagnóstico — no es un fallo real." : trabajo.error}
                          </div>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {historial.length === 0 && <p className="muted" style={{ marginTop: "1rem" }}>Sin ejecuciones todavía.</p>}
        </>
      )}
    </div>
  );
}
