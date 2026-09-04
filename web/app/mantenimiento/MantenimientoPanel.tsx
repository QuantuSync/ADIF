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
  return valor === "programado" ? "Programado" : valor === "manual" ? "Manual" : "—";
}

function ResumenCiclo({ resultado }: { resultado: Record<string, unknown> | null }) {
  if (!resultado) return <span className="muted">—</span>;
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
          <div style={{ display: "flex", flexWrap: "wrap", gap: "2rem", alignItems: "center" }}>
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
                <span className="status-note"> {disparadoPor(estado.ultima_ejecucion)}</span>
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
            <button onClick={lanzarAhora} disabled={lanzando || estado.en_curso} className="btn btn-primary">
              {lanzando ? "Lanzando…" : "Lanzar ciclo ahora"}
            </button>
          </div>
        ) : (
          <p className="muted">Cargando…</p>
        )}
        {estado?.ultima_ejecucion && (
          <>
            <div className="hr" />
            <p className="muted" style={{ marginBottom: "0.4rem" }}>
              Qué encontró la última ejecución
            </p>
            <ResumenCiclo resultado={estado.ultima_ejecucion.resultado} />
            {estado.ultima_ejecucion.error && (
              <p className="status-note" style={{ marginTop: "0.4rem" }}>
                {estado.ultima_ejecucion.error}
              </p>
            )}
          </>
        )}
      </div>

      <p className="section-label">Histórico</p>
      <div className="table-scroll">
        <table className="table">
          <thead>
            <tr>
              <th>#</th>
              <th>Origen</th>
              <th>Estado</th>
              <th>Lanzado</th>
              <th>Terminado</th>
              <th>Resumen</th>
            </tr>
          </thead>
          <tbody>
            {historial.map((trabajo) => (
              <tr key={trabajo.id} className={trabajo.error ? "row-accent row-accent-attn" : "row-accent"}>
                <td>{trabajo.id}</td>
                <td>{disparadoPor(trabajo)}</td>
                <td>
                  <span className={`status ${trabajo.estado === "completado" ? "status-ok" : trabajo.estado === "fallido" ? "status-attn" : ""}`}>
                    {trabajo.estado}
                  </span>
                </td>
                <td>{formatearFecha(trabajo.created_at)}</td>
                <td>{trabajo.estado === "pendiente" || trabajo.estado === "en_proceso" ? "—" : formatearFecha(trabajo.updated_at)}</td>
                <td>
                  <ResumenCiclo resultado={trabajo.resultado} />
                  {trabajo.error && <div className="status-note">{trabajo.error}</div>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {historial.length === 0 && <p className="muted" style={{ marginTop: "1rem" }}>Sin ejecuciones todavía.</p>}
    </div>
  );
}
