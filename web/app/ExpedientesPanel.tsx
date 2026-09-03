"use client";

import { useEffect, useState } from "react";
import { EstadoTexto, accentClaseEstado, formatearImporte, formatearPorcentaje } from "./ui";

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

const INTERVALO_SONDEO_MS = 3000;

// El hallazgo central del proyecto (CLAUDE.md sección 4): en el modelo de
// "baja única por lote", licitación y adjudicación son a menudo el mismo
// importe (el presupuesto es un techo de gasto, no cambia) y la baja real
// vive solo en el porcentaje declarado. Sin esta nota, esa fila se lee como
// un error ("¿por qué no ha bajado nada?") en vez de como el comportamiento
// esperado.
function esCasoPreciosUnitarios(exp: Expediente): boolean {
  if (exp.importe_licitacion === null || exp.importe_adjudicacion === null) return false;
  if (Number(exp.importe_licitacion) !== Number(exp.importe_adjudicacion)) return false;
  const baja = exp.baja_global !== null ? Number(exp.baja_global) : null;
  return (baja !== null && baja > 0) || exp.baja_variable_por_lote === true;
}

function CeldaBaja({ expediente }: { expediente: Expediente }) {
  const cuerpo =
    expediente.lotes.length <= 1 ? (
      <strong>{formatearPorcentaje(expediente.baja_global)}</strong>
    ) : !expediente.baja_variable_por_lote ? (
      <details>
        <summary className="chip" style={{ display: "inline-flex" }}>
          <strong>{formatearPorcentaje(expediente.baja_global)}</strong>
        </summary>
        <TablaLotes lotes={expediente.lotes} />
      </details>
    ) : (
      <details>
        <summary className="chip" style={{ display: "inline-flex" }}>
          <strong className="status-attn">Varía por lote</strong>
        </summary>
        <TablaLotes lotes={expediente.lotes} />
      </details>
    );

  return (
    <>
      {cuerpo}
      {esCasoPreciosUnitarios(expediente) && (
        <span
          className="status-note"
          title="El importe de licitación y el de adjudicación coinciden: es el modelo de baja única sobre precios unitarios (CLAUDE.md sección 4), no un error de extracción."
        >
          Importe fijo, baja en precios unitarios
        </span>
      )}
    </>
  );
}

function TablaLotes({ lotes }: { lotes: Lote[] }) {
  return (
    <table className="table" style={{ marginTop: "0.5rem", width: "auto", fontSize: "0.85rem" }}>
      <thead>
        <tr>
          <th>Lote</th>
          <th className="num">Baja</th>
          <th className="num">Licitación</th>
          <th className="num">Adjudicación</th>
          <th>Adjudicatario</th>
        </tr>
      </thead>
      <tbody>
        {lotes.map((lote) => (
          <tr key={lote.id}>
            <td>{lote.identificador_lote}</td>
            <td className="num">{formatearPorcentaje(lote.baja_lote)}</td>
            <td className="num">{formatearImporte(lote.importe_licitacion)}</td>
            <td className="num">{formatearImporte(lote.importe_adjudicacion)}</td>
            <td>{lote.adjudicatario ?? "—"}</td>
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

  const resumen = {
    completado: expedientes.filter((e) => e.estado === "completado").length,
    revision: expedientes.filter((e) => e.estado === "pendiente_revision" || e.estado === "fallido").length,
    sinPublicar: expedientes.filter((e) => e.estado === "sin_publicar").length,
    enCurso: expedientes.filter((e) =>
      ["pendiente", "descargando", "descargado", "extrayendo", "esperando_matriz"].includes(e.estado)
    ).length,
  };

  return (
    <div>
      <div className="card" style={{ marginBottom: "1.5rem" }}>
        <p className="section-label">Añadir expediente</p>
        <form onSubmit={crearExpediente} style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap", alignItems: "end" }}>
          <div style={{ minWidth: "16rem" }}>
            <label className="field-label" htmlFor="codigo-nuevo">
              Código de expediente
            </label>
            <input
              id="codigo-nuevo"
              className="input"
              value={codigoNuevo}
              onChange={(e) => setCodigoNuevo(e.target.value)}
              placeholder="6.24/28510.0088"
            />
          </div>
          <div style={{ minWidth: "14rem" }}>
            <label className="field-label" htmlFor="matriz-nuevo">
              Código matriz (opcional)
            </label>
            <input
              id="matriz-nuevo"
              className="input"
              value={matrizNuevo}
              onChange={(e) => setMatrizNuevo(e.target.value)}
              placeholder="2.18/04703.0019"
            />
          </div>
          <button type="submit" disabled={creando} className="btn btn-primary">
            {creando ? "Añadiendo…" : "Añadir expediente"}
          </button>
        </form>
      </div>

      <p className="muted" style={{ marginBottom: "1.75rem" }}>
        {expedientes.length} expediente{expedientes.length === 1 ? "" : "s"} · {resumen.completado} completado
        {resumen.completado === 1 ? "" : "s"} · {resumen.revision} en revisión · {resumen.sinPublicar} no publicado
        {resumen.sinPublicar === 1 ? "" : "s"}
        {resumen.enCurso > 0 && ` · ${resumen.enCurso} en curso`}
      </p>

      {errorConexion && (
        <p className="error-banner">
          Error al conectar con la API ({apiUrl}): {errorConexion}
        </p>
      )}

      <div className="table-scroll">
        <table className="table">
          <thead>
            <tr>
              <th>Expediente</th>
              <th>Matriz</th>
              <th>Estado</th>
              <th className="num">Licitación</th>
              <th className="num">Adjudicación</th>
              <th className="num">Baja</th>
              <th>Acciones</th>
            </tr>
          </thead>
          <tbody>
            {expedientes.map((exp) => {
              const enCurso = exp.estado === "descargando" || exp.estado === "extrayendo";
              // No reprocesar por accidente un expediente ya completado
              // (encargo de la sesión de pulido): hay que borrarlo y crearlo
              // de nuevo si de verdad hace falta relanzarlo.
              const completado = exp.estado === "completado";
              const noPublicado = exp.estado === "sin_publicar";
              return (
                <tr
                  key={exp.id}
                  className={`row-accent ${accentClaseEstado(exp.estado)}${noPublicado ? " row-muted" : ""}`}
                >
                  <td style={{ fontWeight: 600 }}>{exp.codigo_expediente}</td>
                  <td>{exp.codigo_matriz ?? "—"}</td>
                  <td>
                    <EstadoTexto estado={exp.estado} />
                    {exp.error && !noPublicado && <span className="status-note">{exp.error}</span>}
                  </td>
                  <td className="num">{formatearImporte(exp.importe_licitacion)}</td>
                  <td className="num">{formatearImporte(exp.importe_adjudicacion)}</td>
                  <td className="num">
                    <CeldaBaja expediente={exp} />
                  </td>
                  <td>
                    <div style={{ display: "flex", gap: "0.4rem" }}>
                      <button
                        onClick={() => lanzarDescarga(exp.id)}
                        disabled={enCurso || completado || lanzando === exp.id}
                        title={completado ? "Ya está completado — no se puede relanzar desde aquí" : undefined}
                        className="btn btn-secondary btn-sm"
                      >
                        Descargar
                      </button>
                      <button
                        onClick={() => lanzarExtraccion(exp.id)}
                        disabled={enCurso || completado || lanzando === exp.id}
                        title={completado ? "Ya está completado — no se puede relanzar desde aquí" : undefined}
                        className="btn btn-secondary btn-sm"
                      >
                        Extraer
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {expedientes.length === 0 && <p className="muted" style={{ marginTop: "1rem" }}>Sin expedientes todavía.</p>}
    </div>
  );
}
