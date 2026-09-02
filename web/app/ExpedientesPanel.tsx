"use client";

import { useEffect, useState } from "react";

export type Expediente = {
  id: number;
  codigo_expediente: string;
  codigo_matriz: string | null;
  importe_licitacion: string | null;
  importe_adjudicacion: string | null;
  baja_global: string | null;
  estado: string;
  error: string | null;
};

const ETIQUETA_ESTADO: Record<string, string> = {
  pendiente: "Pendiente",
  descargando: "Descargando",
  descargado: "Descargado",
  extrayendo: "Extrayendo",
  pendiente_revision: "Pendiente de revisión",
  completado: "Completado",
  fallido: "Fallido",
};

const COLOR_ESTADO: Record<string, string> = {
  pendiente: "#6b7280",
  descargando: "#2563eb",
  descargado: "#2563eb",
  extrayendo: "#2563eb",
  pendiente_revision: "#b45309",
  completado: "#15803d",
  fallido: "#b91c1c",
};

const INTERVALO_SONDEO_MS = 3000;

function formatearPorcentaje(valor: string | null): string {
  if (valor === null) return "—";
  return `${(Number(valor) * 100).toFixed(2)}%`;
}

function formatearImporte(valor: string | null): string {
  if (valor === null) return "—";
  return `${Number(valor).toLocaleString("es-ES", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €`;
}

export default function ExpedientesPanel({
  inicial,
  apiUrl,
}: {
  inicial: Expediente[];
  apiUrl: string;
}) {
  const [expedientes, setExpedientes] = useState<Expediente[]>(inicial);
  const [errorConexion, setErrorConexion] = useState<string | null>(null);
  const [codigoNuevo, setCodigoNuevo] = useState("");
  const [matrizNuevo, setMatrizNuevo] = useState("");
  const [creando, setCreando] = useState(false);
  const [lanzando, setLanzando] = useState<number | null>(null);

  async function recargar() {
    try {
      const res = await fetch(`${apiUrl}/expedientes`, { cache: "no-store" });
      if (!res.ok) throw new Error(`la API respondió ${res.status}`);
      const datos = await res.json();
      setExpedientes(datos);
      setErrorConexion(null);
    } catch (e) {
      setErrorConexion(e instanceof Error ? e.message : String(e));
    }
  }

  useEffect(() => {
    const id = setInterval(recargar, INTERVALO_SONDEO_MS);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function crearExpediente(e: React.FormEvent) {
    e.preventDefault();
    if (!codigoNuevo.trim()) return;
    setCreando(true);
    try {
      const res = await fetch(`${apiUrl}/expedientes`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          codigo_expediente: codigoNuevo.trim(),
          codigo_matriz: matrizNuevo.trim() || null,
        }),
      });
      if (!res.ok) throw new Error(`la API respondió ${res.status}`);
      setCodigoNuevo("");
      setMatrizNuevo("");
      await recargar();
    } catch (e) {
      setErrorConexion(e instanceof Error ? e.message : String(e));
    } finally {
      setCreando(false);
    }
  }

  async function lanzarDescarga(id: number) {
    setLanzando(id);
    try {
      const res = await fetch(`${apiUrl}/expedientes/${id}/descargar`, { method: "POST" });
      if (!res.ok) throw new Error(`la API respondió ${res.status}`);
      await recargar();
    } catch (e) {
      setErrorConexion(e instanceof Error ? e.message : String(e));
    } finally {
      setLanzando(null);
    }
  }

  async function lanzarExtraccion(id: number) {
    setLanzando(id);
    try {
      const res = await fetch(`${apiUrl}/expedientes/${id}/extraer`, { method: "POST" });
      if (!res.ok) throw new Error(`la API respondió ${res.status}`);
      await recargar();
    } catch (e) {
      setErrorConexion(e instanceof Error ? e.message : String(e));
    } finally {
      setLanzando(null);
    }
  }

  return (
    <div>
      <form onSubmit={crearExpediente} style={{ display: "flex", gap: "0.5rem", marginBottom: "1.5rem", flexWrap: "wrap" }}>
        <input
          value={codigoNuevo}
          onChange={(e) => setCodigoNuevo(e.target.value)}
          placeholder="Código de expediente (6.24/28510.0088)"
          style={{ padding: "0.4rem", minWidth: "16rem" }}
        />
        <input
          value={matrizNuevo}
          onChange={(e) => setMatrizNuevo(e.target.value)}
          placeholder="Código matriz (opcional)"
          style={{ padding: "0.4rem", minWidth: "14rem" }}
        />
        <button type="submit" disabled={creando} style={{ padding: "0.4rem 0.8rem" }}>
          {creando ? "Añadiendo..." : "Añadir expediente"}
        </button>
      </form>

      {errorConexion && (
        <p style={{ color: "crimson" }}>Error al conectar con la API ({apiUrl}): {errorConexion}</p>
      )}

      <table style={{ borderCollapse: "collapse", width: "100%" }}>
        <thead>
          <tr style={{ textAlign: "left", borderBottom: "2px solid #ccc" }}>
            <th style={{ padding: "0.4rem" }}>Expediente</th>
            <th style={{ padding: "0.4rem" }}>Matriz</th>
            <th style={{ padding: "0.4rem" }}>Estado</th>
            <th style={{ padding: "0.4rem" }}>Licitación</th>
            <th style={{ padding: "0.4rem" }}>Adjudicación</th>
            <th style={{ padding: "0.4rem" }}>Baja</th>
            <th style={{ padding: "0.4rem" }}>Acciones</th>
          </tr>
        </thead>
        <tbody>
          {expedientes.map((exp) => {
            const enCurso = exp.estado === "descargando" || exp.estado === "extrayendo";
            return (
              <tr key={exp.id} style={{ borderBottom: "1px solid #eee" }}>
                <td style={{ padding: "0.4rem" }}>{exp.codigo_expediente}</td>
                <td style={{ padding: "0.4rem" }}>{exp.codigo_matriz ?? "—"}</td>
                <td style={{ padding: "0.4rem" }}>
                  <span
                    style={{
                      color: COLOR_ESTADO[exp.estado] ?? "#000",
                      fontWeight: 600,
                    }}
                  >
                    {ETIQUETA_ESTADO[exp.estado] ?? exp.estado}
                  </span>
                  {exp.error && (
                    <div style={{ fontSize: "0.8rem", color: "#b91c1c", marginTop: "0.2rem" }}>{exp.error}</div>
                  )}
                </td>
                <td style={{ padding: "0.4rem" }}>{formatearImporte(exp.importe_licitacion)}</td>
                <td style={{ padding: "0.4rem" }}>{formatearImporte(exp.importe_adjudicacion)}</td>
                <td style={{ padding: "0.4rem" }}>{formatearPorcentaje(exp.baja_global)}</td>
                <td style={{ padding: "0.4rem" }}>
                  <button
                    onClick={() => lanzarDescarga(exp.id)}
                    disabled={enCurso || lanzando === exp.id}
                    style={{ padding: "0.3rem 0.6rem", marginRight: "0.4rem" }}
                  >
                    Descargar
                  </button>
                  <button
                    onClick={() => lanzarExtraccion(exp.id)}
                    disabled={enCurso || lanzando === exp.id}
                    style={{ padding: "0.3rem 0.6rem" }}
                  >
                    Extraer
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {expedientes.length === 0 && <p>Sin expedientes todavía.</p>}
    </div>
  );
}
