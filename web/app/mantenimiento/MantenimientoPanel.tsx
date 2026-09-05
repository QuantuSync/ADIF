"use client";

import { useEffect, useState } from "react";

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

const INTERVALO_SONDEO_MS = 4000;

function formatearFecha(iso: string): string {
  return new Date(iso).toLocaleString("es-ES");
}

// Segundos legibles como "cada 7 días" / "cada 30 minutos" en vez de un
// número de segundos crudo -- lo que de verdad va a configurar quien opere
// el sistema (CLAUDE.md bloque 3, punto 1: "configurable en frecuencia").
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
          {String(descubrimiento.expedientes_filtrados)} tras el filtro de departamento,{" "}
          {String(descubrimiento.expedientes_con_cambio_estado)} con cambio de estado
        </div>
      )}
      {Boolean(descubrimiento?.error) && (
        <div className="status-note">sindicación falló: {String(descubrimiento!.error)}</div>
      )}
    </div>
  );
}

export default function MantenimientoPanel({ apiUrl }: { apiUrl: string }) {
  const [estado, setEstado] = useState<EstadoMantenimiento | null>(null);
  const [historial, setHistorial] = useState<Trabajo[]>([]);
  const [errorConexion, setErrorConexion] = useState<string | null>(null);
  const [lanzando, setLanzando] = useState(false);

  async function recargar() {
    try {
      const [resEstado, resHistorial] = await Promise.all([
        fetch(`${apiUrl}/mantenimiento/estado`, { cache: "no-store" }),
        fetch(`${apiUrl}/mantenimiento/historial`, { cache: "no-store" }),
      ]);
      if (!resEstado.ok) throw new Error(`la API respondió ${resEstado.status}`);
      if (!resHistorial.ok) throw new Error(`la API respondió ${resHistorial.status}`);
      setEstado(await resEstado.json());
      setHistorial(await resHistorial.json());
      setErrorConexion(null);
    } catch (e) {
      setErrorConexion(e instanceof Error ? e.message : String(e));
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
      setErrorConexion(e instanceof Error ? e.message : String(e));
    } finally {
      setLanzando(false);
    }
  }

  return (
    <div>
      {errorConexion && (
        <p className="error-banner">
          Error al conectar con la API ({apiUrl}): {errorConexion}
        </p>
      )}

      <div className="card" style={{ marginBottom: "1.5rem" }}>
        <p className="section-label">Ejecución programada</p>
        {estado ? (
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
        ) : (
          <p className="muted">Cargando…</p>
        )}
        {estado?.ultima_ejecucion && (
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
                  <td>{trabajo.estado === "pendiente" || trabajo.estado === "en_proceso" ? "" : formatearFecha(trabajo.updated_at)}</td>
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
    </div>
  );
}
