"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { DescripcionCelda, formatearNumero } from "../ui";
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
      <div className="reason-kind">{esContradiccion ? "Dato contradictorio" : "Límite del sistema"}</div>
      <div style={{ flex: 1 }}>
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

  // El punto principal del rediseño (CLAUDE.md, encargo de la sesión de
  // pulido de 1280px): el documento y el formulario al lado de la lista,
  // no detrás de un clic. Sin esto, la pantalla se abría con dos tercios en
  // blanco hasta que alguien seleccionaba un caso a mano.
  useEffect(() => {
    if (seleccionId === null && lista.length > 0) setSeleccionId(lista[0].id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lista]);

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

  // La tabla de líneas vive en `.table-scroll--panel` (scroll horizontal
  // propio, no el de la página — CLAUDE.md, comentario de esa clase en
  // globals.css: comparte columna con el visor de PDF, que no puede
  // desplazarse). Dos defectos de esta sesión, encargo del cliente:
  //
  // 1. Al cambiar de expediente seleccionado, React reutiliza el mismo
  //    contenedor <div> (no cambia de posición en el árbol), así que
  //    conservaba el scroll horizontal del caso anterior — el nuevo caso
  //    "arrancaba desplazado" con la primera columna ya fuera de vista.
  //    Se resetea a 0 cada vez que cambia el expediente seleccionado.
  // 2. La barra de scroll nativa de ese contenedor queda al final de sus
  //    filas (puede haber más de 40), inalcanzable sin bajar antes del
  //    todo. Una segunda barra arriba, sincronizada con la de abajo, la
  //    hace accesible sin bajar — el ancho real de la tabla se mide tras
  //    cada carga de líneas para que ambas compartan el mismo scrollWidth.
  const scrollTablaRef = useRef<HTMLDivElement | null>(null);
  const scrollSuperiorRef = useRef<HTMLDivElement | null>(null);
  const tablaLineasRef = useRef<HTMLTableElement | null>(null);
  const sincronizandoRef = useRef<"superior" | "tabla" | null>(null);
  const [anchoTablaLineas, setAnchoTablaLineas] = useState(0);

  useEffect(() => {
    if (scrollTablaRef.current) scrollTablaRef.current.scrollLeft = 0;
    if (scrollSuperiorRef.current) scrollSuperiorRef.current.scrollLeft = 0;
  }, [seleccionId]);

  useEffect(() => {
    setAnchoTablaLineas(tablaLineasRef.current?.scrollWidth ?? 0);
  }, [detalle?.lineas]);

  function sincronizarDesde(origen: "superior" | "tabla", scrollLeft: number) {
    if (sincronizandoRef.current === origen) {
      sincronizandoRef.current = null;
      return;
    }
    const destino = origen === "superior" ? scrollTablaRef.current : scrollSuperiorRef.current;
    if (destino) {
      sincronizandoRef.current = origen === "superior" ? "tabla" : "superior";
      destino.scrollLeft = scrollLeft;
    }
  }

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
                {exp.nombre_proyecto && (
                  <span className="hint proyecto" title={exp.nombre_proyecto}>
                    {exp.nombre_proyecto}
                  </span>
                )}
                {primerMotivo && (
                  <span className="hint" style={{ display: "block", marginTop: "0.35rem" }}>
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
          <h2 className="detail-title" style={{ fontSize: "1.6rem", margin: "0 0 0.25rem" }}>
            {detalle.expediente.codigo_expediente}
          </h2>
          {detalle.expediente.nombre_proyecto && <p className="muted" style={{ margin: "0 0 1.5rem" }}>{detalle.expediente.nombre_proyecto}</p>}

          <div style={{ marginBottom: "2.5rem" }}>
            <p className="section-label">Por qué está en revisión</p>
            {motivos.length === 0 && <p className="muted">Sin motivo registrado.</p>}
            {motivos.map((m, i) => (
              <ReasonCard key={i} categoria={m.categoria} texto={m.texto} tecnico={m.tecnico} />
            ))}
          </div>

          <div className="revision-detail-grid">
            {/* minWidth 0: por defecto un hijo de grid no encoge por debajo
                del ancho mínimo de su contenido (aquí, la tabla de líneas) —
                sin esto, esa tabla empujaba la columna entera fuera de la
                pista de 1fr y desbordaba la página (encargo de la sesión de
                pulido de 1280px). */}
            <div style={{ minWidth: 0 }}>
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
                <>
                  <div
                    className="table-scroll-superior"
                    ref={scrollSuperiorRef}
                    onScroll={(e) => sincronizarDesde("superior", e.currentTarget.scrollLeft)}
                  >
                    <div style={{ width: anchoTablaLineas, height: 1 }} />
                  </div>
                  <div
                    className="table-scroll table-scroll--panel"
                    ref={scrollTablaRef}
                    onScroll={(e) => sincronizarDesde("tabla", e.currentTarget.scrollLeft)}
                  >
                  <table className="table" ref={tablaLineasRef}>
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
                            <td className="mono">{linea.codigo_precio ?? ""}</td>
                            <td className="mono">{linea.matricula ?? ""}</td>
                            <td>
                              <DescripcionCelda texto={linea.descripcion} />
                            </td>
                            <td className="num">{formatearNumero(linea.precio_unitario)}</td>
                            <td>
                              <span className={linea.estado_revision === "confirmado" ? "status status-ok" : "status"}>
                                {linea.estado_revision === "confirmado" ? "Confirmado" : "Sin confirmar"}
                              </span>
                            </td>
                            <td className="col-aviso">
                              {aviso && (
                                <span
                                  className={aviso.categoria === "contradiccion" ? "status-note status-attn" : "status-note"}
                                >
                                  {aviso.texto}
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
                </>
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
