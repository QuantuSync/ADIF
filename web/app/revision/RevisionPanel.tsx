"use client";

import { useEffect, useState } from "react";

type ExpedienteResumen = {
  id: number;
  codigo_expediente: string;
  codigo_matriz: string | null;
  nombre_proyecto: string | null;
  importe_licitacion: string | null;
  importe_adjudicacion: string | null;
  baja_global: string | null;
  estado: string;
  error: string | null;
};

type Documento = {
  id: number;
  tipo_documento: string;
  nombre_archivo: string;
  paginas: number | null;
};

type LineaCatalogo = {
  id: number;
  codigo_precio: string | null;
  matricula: string | null;
  descripcion: string;
  cantidad: string | null;
  precio_unitario: string | null;
  precio_adjudicado: string | null;
  estado_revision: string;
  documento_origen_id: number | null;
  documento_origen_nombre: string | null;
  pagina: number | null;
};

type DetalleRevision = {
  expediente: ExpedienteResumen;
  documentos: Documento[];
  lineas: LineaCatalogo[];
};

const inputEstilo: React.CSSProperties = {
  padding: "0.4rem 0.5rem",
  fontSize: "0.95rem",
  border: "1px solid #9ca3af",
  borderRadius: "4px",
  width: "9rem",
};

export default function RevisionPanel({ apiUrl }: { apiUrl: string }) {
  const [lista, setLista] = useState<ExpedienteResumen[]>([]);
  const [seleccionId, setSeleccionId] = useState<number | null>(null);
  const [detalle, setDetalle] = useState<DetalleRevision | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [guardando, setGuardando] = useState(false);
  const [correccion, setCorreccion] = useState({
    importe_licitacion: "",
    importe_adjudicacion: "",
    baja_global: "",
    codigo_matriz: "",
  });

  async function cargarLista() {
    try {
      const res = await fetch(`${apiUrl}/revision`, { cache: "no-store" });
      if (!res.ok) throw new Error(`la API respondió ${res.status}`);
      setLista(await res.json());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function cargarDetalle(id: number) {
    try {
      const res = await fetch(`${apiUrl}/expedientes/${id}/revision`, { cache: "no-store" });
      if (!res.ok) throw new Error(`la API respondió ${res.status}`);
      const datos: DetalleRevision = await res.json();
      setDetalle(datos);
      setCorreccion({
        importe_licitacion: datos.expediente.importe_licitacion ?? "",
        importe_adjudicacion: datos.expediente.importe_adjudicacion ?? "",
        baja_global: datos.expediente.baja_global ?? "",
        codigo_matriz: datos.expediente.codigo_matriz ?? "",
      });
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  useEffect(() => {
    cargarLista();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (seleccionId !== null) cargarDetalle(seleccionId);
    else setDetalle(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seleccionId]);

  async function confirmarExpediente(conCorreccion: boolean) {
    if (seleccionId === null) return;
    setGuardando(true);
    try {
      const cuerpo = conCorreccion
        ? {
            importe_licitacion: correccion.importe_licitacion || null,
            importe_adjudicacion: correccion.importe_adjudicacion || null,
            baja_global: correccion.baja_global || null,
            codigo_matriz: correccion.codigo_matriz || null,
          }
        : null;
      const res = await fetch(`${apiUrl}/expedientes/${seleccionId}/revision/confirmar`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(cuerpo),
      });
      if (!res.ok) throw new Error(`la API respondió ${res.status}`);
      setSeleccionId(null);
      await cargarLista();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setGuardando(false);
    }
  }

  async function confirmarLinea(lineaId: number) {
    await fetch(`${apiUrl}/catalogo/lineas/${lineaId}/confirmar`, { method: "POST" });
    if (seleccionId !== null) await cargarDetalle(seleccionId);
  }

  return (
    <div style={{ display: "flex", gap: "2rem", alignItems: "flex-start" }}>
      <div style={{ minWidth: "20rem" }}>
        {error && <p style={{ color: "crimson" }}>{error}</p>}
        {lista.length === 0 && <p style={{ color: "#374151" }}>Sin casos pendientes de revisión.</p>}
        <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
          {lista.map((exp) => (
            <li key={exp.id}>
              <button
                onClick={() => setSeleccionId(exp.id)}
                style={{
                  display: "block",
                  width: "100%",
                  textAlign: "left",
                  padding: "0.75rem",
                  marginBottom: "0.5rem",
                  border: seleccionId === exp.id ? "2px solid #111827" : "1px solid #d1d5db",
                  borderRadius: "6px",
                  background: seleccionId === exp.id ? "#eff6ff" : "#fff",
                  cursor: "pointer",
                  fontSize: "1rem",
                }}
              >
                <strong>{exp.codigo_expediente}</strong>
                <div style={{ fontSize: "0.9rem", color: "#b45309", marginTop: "0.2rem" }}>{exp.error}</div>
              </button>
            </li>
          ))}
        </ul>
      </div>

      {detalle && (
        <div style={{ flex: 1, fontSize: "1.05rem" }}>
          <h2 style={{ fontSize: "1.3rem" }}>{detalle.expediente.codigo_expediente}</h2>
          <p style={{ color: "#b45309" }}>
            <strong>Motivo:</strong> {detalle.expediente.error}
          </p>

          <h3 style={{ fontSize: "1.1rem" }}>Documentos</h3>
          <ul>
            {detalle.documentos.map((doc) => (
              <li key={doc.id}>
                <a href={`${apiUrl}/documentos/${doc.id}/archivo`} target="_blank" rel="noreferrer">
                  {doc.nombre_archivo}
                </a>{" "}
                <span style={{ color: "#6b7280" }}>({doc.tipo_documento})</span>
              </li>
            ))}
            {detalle.documentos.length === 0 && <li style={{ color: "#6b7280" }}>Sin documentos descargados.</li>}
          </ul>

          <h3 style={{ fontSize: "1.1rem" }}>Corregir datos del expediente</h3>
          <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap", marginBottom: "0.75rem" }}>
            <label>
              Importe licitación
              <br />
              <input
                style={inputEstilo}
                value={correccion.importe_licitacion}
                onChange={(e) => setCorreccion({ ...correccion, importe_licitacion: e.target.value })}
              />
            </label>
            <label>
              Importe adjudicación
              <br />
              <input
                style={inputEstilo}
                value={correccion.importe_adjudicacion}
                onChange={(e) => setCorreccion({ ...correccion, importe_adjudicacion: e.target.value })}
              />
            </label>
            <label>
              Baja (0-1)
              <br />
              <input
                style={inputEstilo}
                value={correccion.baja_global}
                onChange={(e) => setCorreccion({ ...correccion, baja_global: e.target.value })}
              />
            </label>
            <label>
              Código matriz
              <br />
              <input
                style={inputEstilo}
                value={correccion.codigo_matriz}
                onChange={(e) => setCorreccion({ ...correccion, codigo_matriz: e.target.value })}
              />
            </label>
          </div>
          <div style={{ display: "flex", gap: "0.75rem", marginBottom: "1.5rem" }}>
            <button
              onClick={() => confirmarExpediente(false)}
              disabled={guardando}
              style={{ padding: "0.5rem 1rem", fontSize: "1rem" }}
            >
              Confirmar tal cual
            </button>
            <button
              onClick={() => confirmarExpediente(true)}
              disabled={guardando}
              style={{ padding: "0.5rem 1rem", fontSize: "1rem", fontWeight: 700 }}
            >
              Guardar corrección y confirmar
            </button>
          </div>

          <h3 style={{ fontSize: "1.1rem" }}>Líneas de catálogo ({detalle.lineas.length})</h3>
          <table style={{ borderCollapse: "collapse", width: "100%", fontSize: "0.95rem" }}>
            <thead>
              <tr style={{ textAlign: "left", borderBottom: "2px solid #111827" }}>
                <th style={{ padding: "0.4rem" }}>Código</th>
                <th style={{ padding: "0.4rem" }}>Matrícula</th>
                <th style={{ padding: "0.4rem" }}>Descripción</th>
                <th style={{ padding: "0.4rem" }}>Precio unitario</th>
                <th style={{ padding: "0.4rem" }}>Estado</th>
                <th style={{ padding: "0.4rem" }} />
              </tr>
            </thead>
            <tbody>
              {detalle.lineas.map((linea) => (
                <tr key={linea.id} style={{ borderBottom: "1px solid #e5e7eb" }}>
                  <td style={{ padding: "0.4rem" }}>{linea.codigo_precio ?? "—"}</td>
                  <td style={{ padding: "0.4rem" }}>{linea.matricula ?? "—"}</td>
                  <td style={{ padding: "0.4rem" }}>{linea.descripcion}</td>
                  <td style={{ padding: "0.4rem" }}>{linea.precio_unitario ?? "—"}</td>
                  <td style={{ padding: "0.4rem" }}>{linea.estado_revision}</td>
                  <td style={{ padding: "0.4rem" }}>
                    {linea.estado_revision !== "confirmado" && (
                      <button onClick={() => confirmarLinea(linea.id)} style={{ padding: "0.2rem 0.5rem" }}>
                        Confirmar línea
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
