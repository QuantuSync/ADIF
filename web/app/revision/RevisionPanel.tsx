"use client";

import { useEffect, useMemo, useState } from "react";
import { formatearNumero, IconAlertTriangle, IconInfo } from "../ui";
import { interpretarMotivoLinea, interpretarMotivos } from "../motivos";

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
  motivo_revision: string | null;
  documento_origen_id: number | null;
  documento_origen_nombre: string | null;
  pagina: number | null;
};

type DetalleRevision = {
  expediente: ExpedienteResumen;
  documentos: Documento[];
  lineas: LineaCatalogo[];
};

const ETIQUETA_TIPO_DOCUMENTO: Record<string, string> = {
  anuncio_pcsp: "Anuncio PCSP",
  propuesta_lc27: "Propuesta de adjudicación",
  propuesta_dt: "Propuesta (Dirección Técnica)",
  resolucion_adjudicacion: "Resolución de adjudicación",
  contrato: "Contrato",
  anejo: "Anejo",
  pliego: "Pliego",
  otro: "Otro documento",
};

function ReasonCard({ categoria, texto, tecnico }: { categoria: "contradiccion" | "limitacion"; texto: string; tecnico: string }) {
  const esContradiccion = categoria === "contradiccion";
  return (
    <div className={`reason-card reason-card--${categoria}`}>
      <span className="icon">{esContradiccion ? <IconAlertTriangle /> : <IconInfo />}</span>
      <div style={{ flex: 1 }}>
        <div className="reason-kind">{esContradiccion ? "Dato contradictorio en el documento" : "Límite del sistema"}</div>
        <div className="reason-text">{texto}</div>
        {tecnico !== texto && (
          <details className="reason-tech">
            <summary>Ver mensaje técnico</summary>
            <code>{tecnico}</code>
          </details>
        )}
      </div>
    </div>
  );
}

export default function RevisionPanel({ apiUrl }: { apiUrl: string }) {
  const [lista, setLista] = useState<ExpedienteResumen[]>([]);
  const [seleccionId, setSeleccionId] = useState<number | null>(null);
  const [detalle, setDetalle] = useState<DetalleRevision | null>(null);
  const [documentoActivo, setDocumentoActivo] = useState<number | null>(null);
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
      setDocumentoActivo(datos.documentos[0]?.id ?? null);
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

  const motivos = useMemo(() => interpretarMotivos(detalle?.expediente.error), [detalle]);

  return (
    <div className="revision-layout">
      <div>
        {error && <p className="error-banner">{error}</p>}
        {lista.length === 0 && !error && <p className="empty-state">Sin casos pendientes de revisión.</p>}
        <div className="revision-list">
          {lista.map((exp) => {
            const primerMotivo = interpretarMotivos(exp.error)[0];
            return (
              <button
                key={exp.id}
                onClick={() => setSeleccionId(exp.id)}
                className={`revision-item${seleccionId === exp.id ? " active" : ""}`}
              >
                <span className="code">{exp.codigo_expediente}</span>
                {exp.nombre_proyecto && <span className="hint">{exp.nombre_proyecto}</span>}
                {primerMotivo && (
                  <span className="hint" style={{ display: "block", marginTop: "0.3rem", color: "var(--slate-700)" }}>
                    {primerMotivo.texto.length > 110 ? `${primerMotivo.texto.slice(0, 110)}…` : primerMotivo.texto}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {detalle && (
        <div>
          <h2 style={{ fontSize: "1.35rem", color: "var(--navy-800)", margin: "0 0 0.15rem" }}>
            {detalle.expediente.codigo_expediente}
          </h2>
          {detalle.expediente.nombre_proyecto && <p className="muted" style={{ margin: "0 0 1rem" }}>{detalle.expediente.nombre_proyecto}</p>}

          <div style={{ marginBottom: "1.5rem" }}>
            <p className="section-label">Por qué está en revisión</p>
            {motivos.length === 0 && <p className="muted">Sin motivo registrado.</p>}
            {motivos.map((m, i) => (
              <ReasonCard key={i} categoria={m.categoria} texto={m.texto} tecnico={m.tecnico} />
            ))}
          </div>

          <div className="revision-detail-grid">
            <div>
              <div className="card" style={{ marginBottom: "1.25rem" }}>
                <p className="section-label">Corregir datos del expediente</p>
                <div className="field-grid">
                  <label>
                    <span className="field-label">Importe licitación</span>
                    <input
                      className="input"
                      value={correccion.importe_licitacion}
                      onChange={(e) => setCorreccion({ ...correccion, importe_licitacion: e.target.value })}
                    />
                  </label>
                  <label>
                    <span className="field-label">Importe adjudicación</span>
                    <input
                      className="input"
                      value={correccion.importe_adjudicacion}
                      onChange={(e) => setCorreccion({ ...correccion, importe_adjudicacion: e.target.value })}
                    />
                  </label>
                  <label>
                    <span className="field-label">Baja (0-1)</span>
                    <input
                      className="input"
                      value={correccion.baja_global}
                      onChange={(e) => setCorreccion({ ...correccion, baja_global: e.target.value })}
                    />
                  </label>
                  <label>
                    <span className="field-label">Código matriz</span>
                    <input
                      className="input"
                      value={correccion.codigo_matriz}
                      onChange={(e) => setCorreccion({ ...correccion, codigo_matriz: e.target.value })}
                    />
                  </label>
                </div>
                <div className="button-row" style={{ marginTop: "1rem" }}>
                  <button onClick={() => confirmarExpediente(false)} disabled={guardando} className="btn btn-secondary">
                    Confirmar tal cual
                  </button>
                  <button onClick={() => confirmarExpediente(true)} disabled={guardando} className="btn btn-primary">
                    Guardar corrección y confirmar
                  </button>
                </div>
              </div>

              <p className="section-label">Líneas de catálogo ({detalle.lineas.length})</p>
              {detalle.lineas.length === 0 ? (
                <p className="empty-state">
                  Este expediente todavía no tiene ninguna línea de catálogo — no hay tabla de precios que mostrar.
                </p>
              ) : (
                <div className="table-scroll">
                  <table className="table">
                    <thead>
                      <tr>
                        <th>Código</th>
                        <th>Matrícula</th>
                        <th>Descripción</th>
                        <th className="num">Precio unitario</th>
                        <th>Estado</th>
                        <th>Aviso</th>
                        <th />
                      </tr>
                    </thead>
                    <tbody>
                      {detalle.lineas.map((linea) => {
                        const aviso = interpretarMotivoLinea(linea.motivo_revision);
                        return (
                          <tr key={linea.id}>
                            <td className="mono">{linea.codigo_precio ?? "—"}</td>
                            <td className="mono">{linea.matricula ?? "—"}</td>
                            <td>{linea.descripcion}</td>
                            <td className="num">{formatearNumero(linea.precio_unitario)}</td>
                            <td>
                              <span className={`badge ${linea.estado_revision === "confirmado" ? "badge-green" : "badge-slate"}`}>
                                {linea.estado_revision}
                              </span>
                            </td>
                            <td style={{ maxWidth: "18rem" }}>
                              {aviso && (
                                <span
                                  className={`badge ${aviso.categoria === "contradiccion" ? "badge-amber" : "badge-slate"}`}
                                  title={aviso.texto}
                                >
                                  {aviso.categoria === "contradiccion" ? <IconAlertTriangle /> : <IconInfo />}
                                  {aviso.texto.length > 60 ? `${aviso.texto.slice(0, 60)}…` : aviso.texto}
                                </span>
                              )}
                            </td>
                            <td>
                              {linea.estado_revision !== "confirmado" && (
                                <button onClick={() => confirmarLinea(linea.id)} className="btn btn-ghost btn-sm">
                                  Confirmar línea
                                </button>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            <div>
              <p className="section-label">Documento</p>
              {detalle.documentos.length === 0 ? (
                <p className="empty-state">Sin documentos descargados.</p>
              ) : (
                <>
                  <div className="pdf-tabs">
                    {detalle.documentos.map((doc) => (
                      <button
                        key={doc.id}
                        onClick={() => setDocumentoActivo(doc.id)}
                        className={`pdf-tab${documentoActivo === doc.id ? " active" : ""}`}
                        title={doc.nombre_archivo}
                      >
                        {ETIQUETA_TIPO_DOCUMENTO[doc.tipo_documento] ?? doc.tipo_documento}
                      </button>
                    ))}
                  </div>
                  <div className="pdf-frame-wrap">
                    {documentoActivo ? (
                      <iframe
                        key={documentoActivo}
                        src={`${apiUrl}/documentos/${documentoActivo}/archivo`}
                        className="pdf-frame"
                        title="Documento"
                      />
                    ) : (
                      <div className="pdf-empty">Selecciona un documento para verlo aquí.</div>
                    )}
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
