"use client";

import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import { DatoVacio, DescripcionCelda, esPartidaAlzada, formatearNumero } from "../ui";
import { interpretarMotivoLinea, interpretarMotivos } from "../motivos";
import { useReintentoConexion } from "../useReintentoConexion";

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

// Bloque 4, sesión de huérfanos de banda vacía (2026-09-07): la línea YA
// resuelta (con lote) del mismo expediente con la que una huérfana coincide
// en matrícula/descripción/precio — señal informativa, nunca calculada por
// el sistema como duplicado real (ver docstring de
// `app.catalogo.buscar_posible_duplicado_huerfana`: un precio de referencia
// puede coincidir legítimamente entre lotes distintos sin ser la misma fila).
type PosibleDuplicado = {
  linea_id: number;
  identificador_lote: string;
  codigo_precio: string | null;
  matricula: string | null;
  descripcion: string;
  precio_unitario: string | null;
};

type LineaCatalogo = {
  id: number;
  lote_id: number | null;
  codigo_precio: string | null;
  matricula: string | null;
  descripcion: string;
  cantidad: string | null;
  precio_unitario: string | null;
  unidad_medida: string | null;
  precio_adjudicado: string | null;
  estado_revision: string;
  motivo_revision: string | null;
  comentarios: string | null;
  documento_origen_id: number | null;
  documento_origen_nombre: string | null;
  pagina: number | null;
  posible_duplicado_de: PosibleDuplicado | null;
};

// Las tres salidas de una línea que hoy solo se podía confirmar (CONTEXTO.md
// bloque 2): corregir el dato a mano, descartarla del catálogo con motivo, o
// dejarla pendiente con una nota para consultar. Cada una abre su propio
// panel bajo la fila -- nunca más de uno a la vez, para no competir con la
// tabla por atención.
type TipoAccionLinea = "corregir" | "descartar" | "pendiente";

const ETIQUETA_ESTADO_LINEA: Record<string, string> = {
  sin_revisar: "Sin confirmar",
  confirmado: "Confirmado",
  corregido: "Corregido",
  descartado: "Descartado",
  pendiente: "Pendiente de consulta",
};

// Ninguna celda vacía sin explicación (CONTEXTO.md bloque 3) -- mismo criterio
// y mismo componente que CatalogoPanel, aplicado a las dos columnas que
// pueden quedar vacías en esta tabla.
function celdaCodigoPrecio(linea: LineaCatalogo) {
  if (linea.codigo_precio) return linea.codigo_precio;
  return (
    <DatoVacio
      motivo="no-consta"
      titulo={
        linea.motivo_revision ??
        "El cuadro de precios de origen no trae un código de línea distinto para esta fila."
      }
    />
  );
}

function celdaPrecioUnitario(linea: LineaCatalogo) {
  const texto = formatearNumero(linea.precio_unitario);
  if (texto) return texto;
  return (
    <DatoVacio
      motivo="no-consta"
      titulo={linea.motivo_revision ?? "No se pudo interpretar el precio unitario de esta línea en el documento de origen."}
    />
  );
}

// Unidad de medida (CONTEXTO.md, encargo de esta sesión): sin ella, un
// precio unitario no se entiende por sí solo (0,142 solo tiene sentido
// sabiendo que es por tonelada-kilómetro) -- mismo criterio na/no-consta
// que el resto de columnas.
function celdaUnidadMedida(linea: LineaCatalogo) {
  if (linea.unidad_medida) return linea.unidad_medida;
  if (esPartidaAlzada(linea.descripcion)) {
    return (
      <DatoVacio
        motivo="na"
        titulo="Partida alzada: es una reserva presupuestaria, no un artículo de almacén — no lleva este dato salvo que el documento le dé una unidad propia."
      />
    );
  }
  return (
    <DatoVacio motivo="no-consta" titulo="El cuadro de precios de origen no trae unidad de medida para esta línea." />
  );
}

function celdaMatricula(linea: LineaCatalogo) {
  if (linea.matricula) return linea.matricula;
  if (esPartidaAlzada(linea.descripcion)) {
    return (
      <DatoVacio
        motivo="na"
        titulo="Partida alzada: es una reserva presupuestaria, no un artículo de almacén — no lleva este dato."
      />
    );
  }
  return (
    <DatoVacio
      motivo="no-consta"
      titulo="El cuadro de precios de origen no trae matrícula para esta línea (pasa en aproximadamente un tercio del catálogo)."
    />
  );
}

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

const INTERVALO_SONDEO_MS = 3000;

export default function RevisionPanel({ apiUrl }: { apiUrl: string }) {
  const [lista, setLista] = useState<ExpedienteResumen[]>([]);
  const [seleccionId, setSeleccionId] = useState<number | null>(null);
  const [detalle, setDetalle] = useState<DetalleRevision | null>(null);
  const [documentoActivo, setDocumentoActivo] = useState<number | null>(null);
  // Conexión (sondeo pasivo de la lista, cada pocos segundos): gateado por
  // `useReintentoConexion`, igual que en ExpedientesPanel/CatalogoPanel.
  // `errorDetalle` es distinto: carga del detalle seleccionado o confirmar
  // un expediente son acciones puntuales, avisan al primer fallo.
  const { error, confirmado, cargando: sinConfirmar, registrarExito, registrarFallo } = useReintentoConexion();
  const [errorDetalle, setErrorDetalle] = useState<string | null>(null);
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
      registrarExito();
    } catch (e) {
      registrarFallo(e instanceof Error ? e.message : String(e));
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
      setErrorDetalle(null);
    } catch (e) {
      setErrorDetalle(e instanceof Error ? e.message : String(e));
    }
  }

  useEffect(() => {
    // Tolerancia a reinicios de dockerd (sesión 2026-09-06): antes, la lista
    // solo se cargaba una vez al montar -- un fallo puntual la dejaba vacía
    // para siempre, sin reintentar. Sondeo periódico, igual que
    // ExpedientesPanel: se recupera sola en cuanto la API vuelve.
    cargarLista();
    const id = setInterval(cargarLista, INTERVALO_SONDEO_MS);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // El punto principal del rediseño (CONTEXTO.md, encargo de la sesión de
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
      setErrorDetalle(e instanceof Error ? e.message : String(e));
    } finally {
      setGuardando(false);
    }
  }

  async function confirmarLinea(lineaId: number) {
    await fetch(`${apiUrl}/catalogo/lineas/${lineaId}/confirmar`, { method: "POST" });
    if (seleccionId !== null) await cargarDetalle(seleccionId);
  }

  // Bloque 4 (2026-09-07): la única acción de un clic específica de la señal
  // de "posible duplicado" — descartar. "Confirmar como distinta" reutiliza
  // el botón "Confirmar" de siempre (`confirmarLinea`), porque es la misma
  // decisión que ya existía: esta línea es material real del catálogo. El
  // motivo queda anclado a la línea con la que coincidía, para que quede
  // trazado por qué se descartó, no solo que se descartó.
  async function descartarComoDuplicado(linea: LineaCatalogo) {
    const d = linea.posible_duplicado_de;
    if (!d) return;
    const referencia = d.codigo_precio ?? d.matricula ?? "misma descripción y precio";
    const motivo = `Descartada por coincidir con la línea ${d.linea_id} del LOTE ${d.identificador_lote} (${referencia}, ${
      formatearNumero(d.precio_unitario) || "—"
    } €) — confirmado como duplicado desde la señal de la cola de revisión.`;
    await fetch(`${apiUrl}/catalogo/lineas/${linea.id}/descartar`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ motivo }),
    });
    if (seleccionId !== null) await cargarDetalle(seleccionId);
  }

  // Panel de acción abierto bajo una fila de línea (corregir/descartar/
  // pendiente): como mucho uno a la vez, con su propio formulario.
  const [panelAccion, setPanelAccion] = useState<{ lineaId: number; tipo: TipoAccionLinea } | null>(null);
  const [formCorreccion, setFormCorreccion] = useState({
    matricula: "", cantidad: "", precio_unitario: "", comentarios: "",
  });
  const [textoMotivo, setTextoMotivo] = useState("");
  const [guardandoAccion, setGuardandoAccion] = useState(false);
  const [errorAccion, setErrorAccion] = useState<string | null>(null);

  function abrirAccionLinea(linea: LineaCatalogo, tipo: TipoAccionLinea) {
    setErrorAccion(null);
    if (panelAccion?.lineaId === linea.id && panelAccion.tipo === tipo) {
      setPanelAccion(null);
      return;
    }
    setPanelAccion({ lineaId: linea.id, tipo });
    setTextoMotivo("");
    if (tipo === "corregir") {
      setFormCorreccion({
        matricula: linea.matricula ?? "",
        cantidad: linea.cantidad ?? "",
        precio_unitario: linea.precio_unitario ?? "",
        comentarios: linea.comentarios ?? "",
      });
    }
  }

  async function guardarCorreccionLinea(lineaId: number) {
    setGuardandoAccion(true);
    setErrorAccion(null);
    try {
      const cuerpo: Record<string, string> = {};
      if (formCorreccion.matricula) cuerpo.matricula = formCorreccion.matricula;
      if (formCorreccion.cantidad) cuerpo.cantidad = formCorreccion.cantidad;
      if (formCorreccion.precio_unitario) cuerpo.precio_unitario = formCorreccion.precio_unitario;
      if (formCorreccion.comentarios) cuerpo.comentarios = formCorreccion.comentarios;
      const res = await fetch(`${apiUrl}/catalogo/lineas/${lineaId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(cuerpo),
      });
      if (!res.ok) throw new Error(`la API respondió ${res.status}`);
      setPanelAccion(null);
      if (seleccionId !== null) await cargarDetalle(seleccionId);
    } catch (e) {
      setErrorAccion(e instanceof Error ? e.message : String(e));
    } finally {
      setGuardandoAccion(false);
    }
  }

  async function guardarAccionConTexto(lineaId: number, tipo: "descartar" | "pendiente") {
    if (!textoMotivo.trim()) {
      setErrorAccion(tipo === "descartar" ? "El motivo es obligatorio." : "La nota es obligatoria.");
      return;
    }
    setGuardandoAccion(true);
    setErrorAccion(null);
    try {
      const campo = tipo === "descartar" ? "motivo" : "nota";
      const res = await fetch(`${apiUrl}/catalogo/lineas/${lineaId}/${tipo}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ [campo]: textoMotivo.trim() }),
      });
      if (!res.ok) throw new Error(`la API respondió ${res.status}`);
      setPanelAccion(null);
      if (seleccionId !== null) await cargarDetalle(seleccionId);
    } catch (e) {
      setErrorAccion(e instanceof Error ? e.message : String(e));
    } finally {
      setGuardandoAccion(false);
    }
  }

  const motivos = useMemo(() => interpretarMotivos(detalle?.expediente.error), [detalle]);

  // La tabla de líneas vive en `.table-scroll--panel` (scroll horizontal
  // propio, no el de la página — CONTEXTO.md, comentario de esa clase en
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
        {/* Estados de carga y error (CONTEXTO.md, bloque de estados de carga
            y error, sesión 2026-09-06): sin respuesta confirmada de la API
            todavía, no se dice "sin casos pendientes" -- eso solo es cierto
            una vez confirmado, no por simple falta de respuesta. */}
        {sinConfirmar && <p className="muted">Cargando cola de revisión…</p>}
        {error && <p className="error-banner">{error}</p>}
        {errorDetalle && <p className="error-banner">{errorDetalle}</p>}
        {confirmado && lista.length === 0 && !error && <p className="empty-state">Sin casos pendientes de revisión.</p>}
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
                        <th>Unidad</th>
                        <th>Estado</th>
                        <th>Aviso</th>
                        <th />
                      </tr>
                    </thead>
                    <tbody>
                      {detalle.lineas.map((linea) => {
                        const aviso = interpretarMotivoLinea(linea.motivo_revision);
                        const panelAbierto = panelAccion?.lineaId === linea.id ? panelAccion.tipo : null;
                        const esFinal = linea.estado_revision === "confirmado" || linea.estado_revision === "descartado";
                        return (
                          <Fragment key={linea.id}>
                            <tr>
                              <td className="mono">{celdaCodigoPrecio(linea)}</td>
                              <td className="mono">{celdaMatricula(linea)}</td>
                              <td>
                                <DescripcionCelda texto={linea.descripcion} />
                              </td>
                              <td className="num">{celdaPrecioUnitario(linea)}</td>
                              <td>{celdaUnidadMedida(linea)}</td>
                              <td>
                                <span
                                  className={linea.estado_revision === "confirmado" ? "status status-ok" : "status"}
                                >
                                  {ETIQUETA_ESTADO_LINEA[linea.estado_revision] ?? linea.estado_revision}
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
                                {linea.comentarios && (
                                  <span className="status-note" title={linea.comentarios}>
                                    {linea.comentarios.length > 80
                                      ? `${linea.comentarios.slice(0, 80)}…`
                                      : linea.comentarios}
                                  </span>
                                )}
                              </td>
                              <td>
                                <div className="button-row">
                                  {linea.estado_revision !== "confirmado" && (
                                    <button onClick={() => confirmarLinea(linea.id)} className="btn btn-ghost btn-sm">
                                      Confirmar
                                    </button>
                                  )}
                                  {!esFinal && (
                                    <>
                                      <button
                                        onClick={() => abrirAccionLinea(linea, "corregir")}
                                        className="btn btn-ghost btn-sm"
                                      >
                                        Corregir
                                      </button>
                                      <button
                                        onClick={() => abrirAccionLinea(linea, "pendiente")}
                                        className="btn btn-ghost btn-sm"
                                      >
                                        Pendiente
                                      </button>
                                      <button
                                        onClick={() => abrirAccionLinea(linea, "descartar")}
                                        className="btn btn-ghost btn-sm"
                                      >
                                        Descartar
                                      </button>
                                    </>
                                  )}
                                </div>
                              </td>
                            </tr>
                            {linea.posible_duplicado_de && !esFinal && (
                              <tr>
                                <td colSpan={8} className="linea-accion-panel duplicado-panel">
                                  <p className="duplicado-titulo">
                                    Posible duplicado: coincide en matrícula/descripción/precio con una línea ya
                                    resuelta de este mismo expediente. No es una decisión del sistema — puede ser el
                                    mismo material repetido en el documento, o un precio de referencia que
                                    legítimamente se repite entre lotes distintos (pasa en licitaciones reales).
                                    Compara y decide:
                                  </p>
                                  <div className="duplicado-comparacion">
                                    <div>
                                      <span className="duplicado-label">Esta línea (sin lote)</span>
                                      <span className="mono">{linea.codigo_precio ?? linea.matricula ?? "—"}</span>
                                      <div>{linea.descripcion}</div>
                                      <div className="num">{formatearNumero(linea.precio_unitario) || "—"} €</div>
                                    </div>
                                    <div>
                                      <span className="duplicado-label">
                                        Ya resuelta — LOTE {linea.posible_duplicado_de.identificador_lote}
                                      </span>
                                      <span className="mono">
                                        {linea.posible_duplicado_de.codigo_precio ??
                                          linea.posible_duplicado_de.matricula ??
                                          "—"}
                                      </span>
                                      <div>{linea.posible_duplicado_de.descripcion}</div>
                                      <div className="num">
                                        {formatearNumero(linea.posible_duplicado_de.precio_unitario) || "—"} €
                                      </div>
                                    </div>
                                  </div>
                                  <div className="button-row" style={{ marginTop: "0.75rem" }}>
                                    <button onClick={() => confirmarLinea(linea.id)} className="btn btn-secondary btn-sm">
                                      Confirmar como línea distinta
                                    </button>
                                    <button
                                      onClick={() => descartarComoDuplicado(linea)}
                                      className="btn btn-primary btn-sm"
                                    >
                                      Descartar como duplicado
                                    </button>
                                  </div>
                                </td>
                              </tr>
                            )}
                            {panelAbierto && (
                              <tr>
                                <td colSpan={8} className="linea-accion-panel">
                                  {panelAbierto === "corregir" && (
                                    <div className="field-grid">
                                      <label>
                                        <span className="field-label">Matrícula</span>
                                        <input
                                          className="input"
                                          value={formCorreccion.matricula}
                                          onChange={(e) =>
                                            setFormCorreccion({ ...formCorreccion, matricula: e.target.value })
                                          }
                                        />
                                      </label>
                                      <label>
                                        <span className="field-label">Cantidad</span>
                                        <input
                                          className="input"
                                          value={formCorreccion.cantidad}
                                          onChange={(e) =>
                                            setFormCorreccion({ ...formCorreccion, cantidad: e.target.value })
                                          }
                                        />
                                      </label>
                                      <label>
                                        <span className="field-label">Precio unitario</span>
                                        <input
                                          className="input"
                                          value={formCorreccion.precio_unitario}
                                          onChange={(e) =>
                                            setFormCorreccion({ ...formCorreccion, precio_unitario: e.target.value })
                                          }
                                        />
                                      </label>
                                      <label style={{ gridColumn: "1 / -1" }}>
                                        <span className="field-label">Comentarios</span>
                                        <textarea
                                          className="input"
                                          rows={2}
                                          value={formCorreccion.comentarios}
                                          onChange={(e) =>
                                            setFormCorreccion({ ...formCorreccion, comentarios: e.target.value })
                                          }
                                        />
                                      </label>
                                    </div>
                                  )}
                                  {(panelAbierto === "descartar" || panelAbierto === "pendiente") && (
                                    <label>
                                      <span className="field-label">
                                        {panelAbierto === "descartar" ? "Motivo del descarte" : "Nota"}
                                      </span>
                                      <textarea
                                        className="input"
                                        rows={2}
                                        value={textoMotivo}
                                        onChange={(e) => setTextoMotivo(e.target.value)}
                                        placeholder={
                                          panelAbierto === "descartar"
                                            ? "Por qué esta línea no es material real o no se puede determinar"
                                            : "Qué hace falta consultar antes de decidir"
                                        }
                                      />
                                    </label>
                                  )}
                                  {errorAccion && <p className="error-banner">{errorAccion}</p>}
                                  <div className="button-row" style={{ marginTop: "0.75rem" }}>
                                    <button
                                      onClick={() => setPanelAccion(null)}
                                      disabled={guardandoAccion}
                                      className="btn btn-secondary btn-sm"
                                    >
                                      Cancelar
                                    </button>
                                    <button
                                      onClick={() =>
                                        panelAbierto === "corregir"
                                          ? guardarCorreccionLinea(linea.id)
                                          : guardarAccionConTexto(linea.id, panelAbierto)
                                      }
                                      disabled={guardandoAccion}
                                      className="btn btn-primary btn-sm"
                                    >
                                      {panelAbierto === "corregir" && "Guardar corrección"}
                                      {panelAbierto === "descartar" && "Descartar línea"}
                                      {panelAbierto === "pendiente" && "Dejar pendiente"}
                                    </button>
                                  </div>
                                </td>
                              </tr>
                            )}
                          </Fragment>
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
