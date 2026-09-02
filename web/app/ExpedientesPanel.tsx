"use client";

import { useEffect, useState } from "react";

export type Lote = {
  id: number;
  identificador_lote: string;
  baja_lote: string | null;
  importe_licitacion: string | null;
  importe_adjudicacion: string | null;
  adjudicatario: string | null;
};

export type Expediente = {
  id: number;
  codigo_expediente: string;
  codigo_matriz: string | null;
  importe_licitacion: string | null;
  importe_adjudicacion: string | null;
  baja_global: string | null;
  // CLAUDE.md, encargo de la sesión de multi-lote: cuando hay varios lotes
  // con baja distinta, `baja_global` es null a propósito y este campo lo
  // explica — nunca se muestra un "—" mudo que parezca un fallo.
  baja_variable_por_lote: boolean | null;
  lotes: Lote[];
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

// Un expediente con lotes de baja distinta no tiene una baja única (CLAUDE.md,
// encargo de la sesión de multi-lote): nunca se muestra un valor inventado
// ni un vacío mudo — si varía por lote, lo dice explícitamente y despliega
// el detalle por lote.
function CeldaBaja({ expediente }: { expediente: Expediente }) {
  if (expediente.lotes.length <= 1) {
    return <>{formatearPorcentaje(expediente.baja_global)}</>;
  }
  if (!expediente.baja_variable_por_lote) {
    // Varios lotes pero comparten la misma baja: se muestra igual que si
    // fuera una sola, con el detalle disponible por si hace falta.
    return (
      <details>
        <summary style={{ cursor: "pointer" }}>{formatearPorcentaje(expediente.baja_global)}</summary>
        <TablaLotes lotes={expediente.lotes} />
      </details>
    );
  }
  return (
    <details>
      <summary style={{ cursor: "pointer", color: "#b45309", fontWeight: 600 }}>Varía por lote</summary>
      <TablaLotes lotes={expediente.lotes} />
    </details>
  );
}

function TablaLotes({ lotes }: { lotes: Lote[] }) {
  return (
    <table style={{ marginTop: "0.4rem", fontSize: "0.85rem", borderCollapse: "collapse" }}>
      <thead>
        <tr>
          <th style={{ textAlign: "left", padding: "0.2rem 0.5rem 0.2rem 0" }}>Lote</th>
          <th style={{ textAlign: "left", padding: "0.2rem 0.5rem" }}>Baja</th>
          <th style={{ textAlign: "left", padding: "0.2rem 0.5rem" }}>Licitación</th>
          <th style={{ textAlign: "left", padding: "0.2rem 0.5rem" }}>Adjudicación</th>
          <th style={{ textAlign: "left", padding: "0.2rem 0.5rem" }}>Adjudicatario</th>
        </tr>
      </thead>
      <tbody>
        {lotes.map((lote) => (
          <tr key={lote.id}>
            <td style={{ padding: "0.2rem 0.5rem 0.2rem 0" }}>{lote.identificador_lote}</td>
            <td style={{ padding: "0.2rem 0.5rem" }}>{formatearPorcentaje(lote.baja_lote)}</td>
            <td style={{ padding: "0.2rem 0.5rem" }}>{formatearImporte(lote.importe_licitacion)}</td>
            <td style={{ padding: "0.2rem 0.5rem" }}>{formatearImporte(lote.importe_adjudicacion)}</td>
            <td style={{ padding: "0.2rem 0.5rem" }}>{lote.adjudicatario ?? "—"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
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
            // No reprocesar por accidente un expediente ya completado
            // (encargo de la sesión de pulido): hay que borrarlo y crearlo
            // de nuevo si de verdad hace falta relanzarlo.
            const completado = exp.estado === "completado";
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
                <td style={{ padding: "0.4rem" }}>
                  <CeldaBaja expediente={exp} />
                </td>
                <td style={{ padding: "0.4rem" }}>
                  <button
                    onClick={() => lanzarDescarga(exp.id)}
                    disabled={enCurso || completado || lanzando === exp.id}
                    title={completado ? "Ya está completado — no se puede relanzar desde aquí" : undefined}
                    style={{ padding: "0.3rem 0.6rem", marginRight: "0.4rem" }}
                  >
                    Descargar
                  </button>
                  <button
                    onClick={() => lanzarExtraccion(exp.id)}
                    disabled={enCurso || completado || lanzando === exp.id}
                    title={completado ? "Ya está completado — no se puede relanzar desde aquí" : undefined}
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
