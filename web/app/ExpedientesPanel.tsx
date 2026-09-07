"use client";

import { useEffect, useState } from "react";
import { DatoVacio, EstadoTexto, accentClaseEstado, formatearImporte, formatearPorcentaje } from "./ui";
import { interpretarMotivos } from "./motivos";
import { useReintentoConexion } from "./useReintentoConexion";

// Un expediente todavía en curso (no ha terminado de descargar/extraer)
// puede no tener importe/baja por simple falta de tiempo, no porque el
// sistema no lo encontrara — distinto de un expediente ya resuelto que se
// quedó sin ese dato de verdad (CONTEXTO.md bloque 3).
const ESTADOS_EN_CURSO = ["pendiente", "descargando", "descargado", "extrayendo", "esperando_matriz"];

const LARGO_MOTIVO_LISTA = 88;

// El motivo técnico acumulado (varios documentos, varias páginas, "; "
// entre cada uno) puede llegar a cientos de caracteres — volcado tal cual
// rompía la altura de la fila (mismo problema que las descripciones largas
// del catálogo). Aquí solo cabe un resumen: el primer motivo, en lenguaje
// llano, recortado — el detalle completo vive en la cola de revisión.
function ResumenMotivo({ error }: { error: string | null }) {
  if (!error) return null;
  const primerMotivo = interpretarMotivos(error)[0];
  if (!primerMotivo) return null;
  const texto =
    primerMotivo.texto.length > LARGO_MOTIVO_LISTA
      ? `${primerMotivo.texto.slice(0, LARGO_MOTIVO_LISTA)}…`
      : primerMotivo.texto;
  return (
    <span className="status-note status-note-tight" title={primerMotivo.texto}>
      {texto}
    </span>
  );
}

export type Lote = {
  id: number;
  identificador_lote: string;
  baja_lote: string | null;
  importe_licitacion: string | null;
  importe_adjudicacion: string | null;
  adjudicatario: string | null;
  // Segunda familia de baja (CONTEXTO.md sección 16, docs/identidad-
  // expediente.md sección 28): "indexado_por_pedido" explica por qué
  // `baja_lote` es null a propósito -- ese modelo fija la baja en cada
  // pedido futuro contra el Acuerdo Marco, nunca en la licitación. Se
  // propaga también a los lotes de los pedidos heredados (sesión de
  // descubrimiento inverso): sin esto, un pedido de esta familia se leía
  // como un fallo de extracción.
  modelo_precio: "fijo" | "indexado_por_pedido";
  coeficiente_transformacion: string | null;
};

// Resumen ligero de un pedido derivado, en la lista `pedidos` de su matriz
// (sesión de descubrimiento inverso, punto 2: "la matriz con sus precios de
// referencia y sus pedidos con la baja de cada uno").
export type PedidoResumen = {
  id: number;
  codigo_expediente: string;
  nombre_proyecto: string | null;
  estado: string;
  baja_global: string | null;
  importe_adjudicacion: string | null;
};

export type Expediente = {
  id: number;
  codigo_expediente: string;
  codigo_matriz: string | null;
  nombre_proyecto: string | null;
  importe_licitacion: string | null;
  importe_adjudicacion: string | null;
  baja_global: string | null;
  // CONTEXTO.md, encargo de la sesión de multi-lote: cuando hay varios lotes
  // con baja distinta, `baja_global` es null a propósito y este campo lo
  // explica — nunca se muestra un "—" mudo que parezca un fallo.
  baja_variable_por_lote: boolean | null;
  // True cuando el Anuncio PCSP propio y la columna MATRIZ del Excel de
  // códigos declaran una matriz distinta entre sí (CONTEXTO.md sección 7): un
  // `codigo_matriz` vacío con esto en `true` es un conflicto sin resolver,
  // no un expediente que simplemente no depende de un acuerdo marco.
  matriz_conflicto: boolean | null;
  lotes: Lote[];
  estado: string;
  error: string | null;
  // Descubrimiento inverso (sesión de descubrimiento inverso): pedidos ya
  // enlazados a este expediente como acuerdo marco. Vacío en la inmensa
  // mayoría de expedientes, que no son matriz de nadie.
  pedidos: PedidoResumen[];
  aviso_descubrimiento_pedidos: string | null;
};

const INTERVALO_SONDEO_MS = 3000;

// Encargo de esta sesión: con 53 expedientes ya incómodo de repasar a ojo, y
// el sistema pensado para descubrirlos solo (serán cientos), hace falta
// filtrar por estado y buscar por código o nombre — separado a propósito del
// formulario "Añadir expediente" (mismo aspecto de campo+botón, riesgo real
// de que alguien dé de alta un expediente creyendo que está buscando uno).
type FiltroEstado = "todos" | "completado" | "revision" | "sin_publicar";

function coincideEstado(exp: Expediente, filtro: FiltroEstado): boolean {
  if (filtro === "todos") return true;
  if (filtro === "completado") return exp.estado === "completado";
  if (filtro === "revision") return exp.estado === "pendiente_revision" || exp.estado === "fallido";
  return exp.estado === "sin_publicar";
}

function coincideBusqueda(exp: Expediente, busqueda: string): boolean {
  const q = busqueda.trim().toLowerCase();
  if (!q) return true;
  return (
    exp.codigo_expediente.toLowerCase().includes(q) ||
    (exp.nombre_proyecto ?? "").toLowerCase().includes(q)
  );
}

// El hallazgo central del proyecto (CONTEXTO.md sección 4): en el modelo de
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

// Matriz vacía: la inmensa mayoría de los expedientes no son un pedido
// derivado de un acuerdo marco, así que no declaran matriz — "no aplica",
// definitivo. Solo cuando el propio sistema ya detectó un conflicto entre
// el Anuncio PCSP y el Excel de códigos (CONTEXTO.md sección 7) el hueco es
// en realidad un "no consta" sin resolver, no una ausencia estructural.
function celdaMatriz(expediente: Expediente) {
  if (expediente.codigo_matriz) return expediente.codigo_matriz;
  if (expediente.matriz_conflicto) {
    return (
      <DatoVacio
        motivo="no-consta"
        titulo="El Anuncio PCSP propio y el Excel de códigos declaran una matriz distinta entre sí — el sistema no elige una en silencio, hay que confirmarla a mano."
      />
    );
  }
  return (
    <DatoVacio motivo="na" titulo="Este expediente no es un pedido derivado de un acuerdo marco — no tiene matriz que declarar." />
  );
}

// Importe vacío: mientras el expediente sigue en curso (descargando o
// extrayendo todavía) es simple falta de tiempo, no un hueco definitivo —
// distinto de un expediente ya resuelto (completado o en revisión) que se
// quedó sin este dato de verdad.
function celdaImporte(expediente: Expediente, valor: string | null) {
  const texto = formatearImporte(valor);
  if (texto) return texto;
  if (ESTADOS_EN_CURSO.includes(expediente.estado)) {
    return <DatoVacio motivo="pendiente" titulo="El expediente todavía se está procesando." />;
  }
  return <DatoVacio motivo="no-consta" titulo="No se pudo determinar este importe en los documentos de este expediente." />;
}

// Segunda familia de baja (CONTEXTO.md sección 16): el modelo indexado por
// pedido no tiene baja única de lote que extraer -- ni de la licitación ni,
// para un pedido heredado, de la matriz (docs/identidad-expediente.md
// sección 28). Sin esto, un `baja_lote` vacío se leía como el mismo fallo
// que "no consta" (encargo de esta sesión, ajuste 4).
function esModeloIndexado(lotes: Lote[]): boolean {
  return lotes.length >= 1 && lotes.every((l) => l.modelo_precio === "indexado_por_pedido");
}

function NotaModeloIndexado() {
  return (
    <span
      className="status-note status-note-tight"
      title="Acuerdo marco de precio indexado por pedido: la baja se fija pedido a pedido en el futuro, junto con un índice de actualización de precios (Kt) — no existe todavía en ningún documento de la licitación, no es un dato que el sistema no haya encontrado."
    >
      Baja indexada por pedido
    </span>
  );
}

// Baja vacía (fuera del caso "varía por lote", que ya se explica solo):
// mismo criterio pendiente/no consta que el resto de importes.
function celdaBajaTexto(expediente: Expediente) {
  const texto = formatearPorcentaje(expediente.baja_global);
  if (texto) return <strong>{texto}</strong>;
  if (esModeloIndexado(expediente.lotes)) return <NotaModeloIndexado />;
  if (ESTADOS_EN_CURSO.includes(expediente.estado)) {
    return <DatoVacio motivo="pendiente" titulo="El expediente todavía se está procesando." />;
  }
  return <DatoVacio motivo="no-consta" titulo="No se pudo determinar la baja de este expediente en sus documentos." />;
}

function CeldaBaja({ expediente }: { expediente: Expediente }) {
  const cuerpo =
    expediente.lotes.length <= 1 ? (
      celdaBajaTexto(expediente)
    ) : !expediente.baja_variable_por_lote ? (
      <details>
        <summary className="chip" style={{ display: "inline-flex" }}>
          {celdaBajaTexto(expediente)}
        </summary>
        <TablaLotes lotes={expediente.lotes} estadoExpediente={expediente.estado} />
      </details>
    ) : (
      <details>
        <summary className="chip" style={{ display: "inline-flex" }}>
          <strong className="status-attn">Varía por lote</strong>
        </summary>
        <TablaLotes lotes={expediente.lotes} estadoExpediente={expediente.estado} />
      </details>
    );

  return (
    <>
      {cuerpo}
      {esCasoPreciosUnitarios(expediente) && (
        <span
          className="status-note status-note-tight"
          title="El importe de licitación y el de adjudicación coinciden: es el modelo de baja única sobre precios unitarios (CONTEXTO.md sección 4), no un error de extracción."
        >
          Importe fijo, baja en precios unitarios
        </span>
      )}
    </>
  );
}

// Mismo criterio pendiente/no consta de arriba, a nivel de lote: un lote
// hereda el estado general del expediente (no se procesa por separado).
function celdaLote(estadoExpediente: string, valor: string | null, formatear: (v: string | null) => string) {
  const texto = formatear(valor);
  if (texto) return texto;
  if (ESTADOS_EN_CURSO.includes(estadoExpediente)) {
    return <DatoVacio motivo="pendiente" titulo="El expediente todavía se está procesando." />;
  }
  return <DatoVacio motivo="no-consta" titulo="No se pudo determinar este dato para este lote en los documentos del expediente." />;
}

function celdaBajaLote(lote: Lote, estadoExpediente: string) {
  if (lote.baja_lote === null && lote.modelo_precio === "indexado_por_pedido") {
    return <NotaModeloIndexado />;
  }
  return celdaLote(estadoExpediente, lote.baja_lote, formatearPorcentaje);
}

// Punto 2 del encargo de descubrimiento inverso: "que la web los presente
// juntos: el acuerdo marco con sus precios de referencia y sus pedidos con
// la baja de cada uno". El acuerdo marco (con sus precios) ya es la propia
// fila de la tabla principal -- esto añade, debajo de su código, la lista
// plegable de pedidos ya enlazados y el botón para buscar más.
function CeldaPedidos({
  expediente,
  buscando,
  onBuscar,
}: {
  expediente: Expediente;
  buscando: boolean;
  onBuscar: () => void;
}) {
  if (expediente.pedidos.length === 0 && !expediente.aviso_descubrimiento_pedidos) return null;
  return (
    <div style={{ marginTop: "0.35rem", fontWeight: 400 }}>
      {expediente.pedidos.length > 0 ? (
        <details>
          <summary className="chip" style={{ display: "inline-flex" }}>
            {expediente.pedidos.length} pedido{expediente.pedidos.length === 1 ? "" : "s"}
          </summary>
          <table className="table" style={{ marginTop: "0.5rem", width: "auto", fontSize: "0.85rem" }}>
            <thead>
              <tr>
                <th>Pedido</th>
                <th>Estado</th>
                <th className="num">Baja</th>
                <th className="num">Adjudicación</th>
              </tr>
            </thead>
            <tbody>
              {expediente.pedidos.map((p) => (
                <tr key={p.id}>
                  <td className="mono">{p.codigo_expediente}</td>
                  <td>
                    <EstadoTexto estado={p.estado} />
                  </td>
                  <td className="num">{formatearPorcentaje(p.baja_global) || "—"}</td>
                  <td className="num">{formatearImporte(p.importe_adjudicacion) || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <button type="button" onClick={onBuscar} disabled={buscando} className="btn btn-ghost btn-sm" style={{ marginTop: "0.4rem" }}>
            {buscando ? "Buscando…" : "Buscar más pedidos"}
          </button>
        </details>
      ) : (
        <span className="status-note status-note-tight" title={expediente.aviso_descubrimiento_pedidos ?? undefined}>
          {expediente.aviso_descubrimiento_pedidos}
        </span>
      )}
    </div>
  );
}

function TablaLotes({ lotes, estadoExpediente }: { lotes: Lote[]; estadoExpediente: string }) {
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
            <td className="num">{celdaBajaLote(lote, estadoExpediente)}</td>
            <td className="num">{celdaLote(estadoExpediente, lote.importe_licitacion, formatearImporte)}</td>
            <td className="num">{celdaLote(estadoExpediente, lote.importe_adjudicacion, formatearImporte)}</td>
            <td>
              {lote.adjudicatario ?? (
                <DatoVacio motivo="no-consta" titulo="El documento de adjudicación no declara el adjudicatario de este lote." />
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function ExpedientesPanel({
  inicial,
  inicialConfirmado,
  apiUrl,
}: {
  inicial: Expediente[];
  inicialConfirmado: boolean;
  apiUrl: string;
}) {
  const [expedientes, setExpedientes] = useState<Expediente[]>(inicial);
  // Conexión (sondeo pasivo, cada pocos segundos): un fallo puntual no se
  // muestra hasta que se repite varias veces seguidas -- ver
  // `useReintentoConexion`. Distinto de `errorAccion`: una acción directa
  // del usuario (crear, descargar, extraer) sí avisa al primer fallo.
  const { error: errorConexion, confirmado, cargando, registrarExito, registrarFallo } =
    useReintentoConexion(inicialConfirmado);
  const [errorAccion, setErrorAccion] = useState<string | null>(null);
  const [codigoNuevo, setCodigoNuevo] = useState("");
  const [matrizNuevo, setMatrizNuevo] = useState("");
  const [creando, setCreando] = useState(false);
  const [lanzando, setLanzando] = useState<number | null>(null);
  const [buscandoPedidos, setBuscandoPedidos] = useState<number | null>(null);
  const [busqueda, setBusqueda] = useState("");
  const [filtroEstado, setFiltroEstado] = useState<FiltroEstado>("todos");

  async function recargar() {
    try {
      const res = await fetch(`${apiUrl}/expedientes`, { cache: "no-store" });
      if (!res.ok) throw new Error(`la API respondió ${res.status}`);
      const datos = await res.json();
      setExpedientes(datos);
      registrarExito();
    } catch (e) {
      registrarFallo(e instanceof Error ? e.message : String(e));
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
      setErrorAccion(e instanceof Error ? e.message : String(e));
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
      setErrorAccion(e instanceof Error ? e.message : String(e));
    } finally {
      setLanzando(null);
    }
  }

  // Descubrimiento inverso (sesión de descubrimiento inverso, punto 2):
  // botón manual sobre una matriz concreta, mismo trabajo que la ejecución
  // programada semanal (app.extraccion.descubrimiento_matriz).
  async function lanzarDescubrimientoPedidos(id: number) {
    setBuscandoPedidos(id);
    try {
      const res = await fetch(`${apiUrl}/mantenimiento/descubrimiento-pedidos/ejecutar`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ matriz_expediente_id: id }),
      });
      if (!res.ok) throw new Error(`la API respondió ${res.status}`);
      await recargar();
    } catch (e) {
      setErrorAccion(e instanceof Error ? e.message : String(e));
    } finally {
      setBuscandoPedidos(null);
    }
  }

  async function lanzarExtraccion(id: number) {
    setLanzando(id);
    try {
      const res = await fetch(`${apiUrl}/expedientes/${id}/extraer`, { method: "POST" });
      if (!res.ok) throw new Error(`la API respondió ${res.status}`);
      await recargar();
    } catch (e) {
      setErrorAccion(e instanceof Error ? e.message : String(e));
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

  // Encargo de esta sesión: un expediente `sin_publicar` no es lo mismo que
  // uno pendiente — está verificado que no existe en la Plataforma, así que
  // no hay licitación/adjudicación/baja que mostrar ni descarga/extracción
  // que lanzar. Antes vivían mezclados en la tabla principal, con las
  // mismas nueve columnas que un expediente real (la mayoría vacías) y los
  // mismos dos botones activos — casi un tercio de las 53 filas de esta
  // base para expedientes que no van a completarse nunca. Se separan en un
  // grupo aparte, plegado por defecto.
  const filtrados = expedientes.filter(
    (e) => coincideEstado(e, filtroEstado) && coincideBusqueda(e, busqueda)
  );
  const normales = filtrados.filter((e) => e.estado !== "sin_publicar");
  const noPublicados = filtrados.filter((e) => e.estado === "sin_publicar");
  const hayFiltroActivo = filtroEstado !== "todos" || busqueda.trim() !== "";

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

      {/* Estados de carga y error (CONTEXTO.md, bloque de estados de carga y
          error, sesión 2026-09-06): mientras no hay respuesta confirmada de
          la API, no se enseña ningún recuento -- ni siquiera cero -- para
          que un corte de conexión no se lea como que se han borrado los
          expedientes. */}
      {cargando && <p className="muted" style={{ marginBottom: "1.25rem" }}>Cargando expedientes…</p>}
      {errorConexion && (
        <p className="error-banner">
          Error al conectar con la API ({apiUrl}): {errorConexion}
        </p>
      )}
      {errorAccion && <p className="error-banner">{errorAccion}</p>}

      {confirmado && (
        <>
          <p className="muted" style={{ marginBottom: "1.25rem" }}>
            {expedientes.length} expediente{expedientes.length === 1 ? "" : "s"} · {resumen.completado} completado
            {resumen.completado === 1 ? "" : "s"} · {resumen.revision} en revisión · {resumen.sinPublicar} no publicado
            {resumen.sinPublicar === 1 ? "" : "s"}
            {resumen.enCurso > 0 && ` · ${resumen.enCurso} en curso`}
          </p>

          <div className="buscador-expedientes">
            <input
              className="input"
              value={busqueda}
              onChange={(e) => setBusqueda(e.target.value)}
              placeholder="Buscar por código o nombre de proyecto…"
              aria-label="Buscar expedientes"
            />
            <div className="filtro-estado-grupo" role="group" aria-label="Filtrar por estado">
              {(
                [
                  ["todos", "Todos"],
                  ["completado", "Completado"],
                  ["revision", "En revisión"],
                  ["sin_publicar", "No publicado"],
                ] as [FiltroEstado, string][]
              ).map(([valor, etiqueta]) => (
                <button
                  key={valor}
                  type="button"
                  onClick={() => setFiltroEstado(valor)}
                  className={`filtro-estado${filtroEstado === valor ? " active" : ""}`}
                >
                  {etiqueta}
                </button>
              ))}
            </div>
          </div>

          {hayFiltroActivo && (
            <p className="muted" style={{ marginBottom: "1.25rem", fontSize: "0.88rem" }}>
              {filtrados.length} resultado{filtrados.length === 1 ? "" : "s"} con este filtro.
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
                {normales.map((exp) => {
              const enCurso = exp.estado === "descargando" || exp.estado === "extrayendo";
              // No reprocesar por accidente un expediente ya completado
              // (encargo de la sesión de pulido): hay que borrarlo y crearlo
              // de nuevo si de verdad hace falta relanzarlo.
              const completado = exp.estado === "completado";
              return (
                <tr key={exp.id} className={`row-accent ${accentClaseEstado(exp.estado)}`}>
                  <td style={{ fontWeight: 600 }}>
                    {exp.codigo_expediente}
                    <CeldaPedidos
                      expediente={exp}
                      buscando={buscandoPedidos === exp.id}
                      onBuscar={() => lanzarDescubrimientoPedidos(exp.id)}
                    />
                  </td>
                  <td>{celdaMatriz(exp)}</td>
                  <td>
                    <EstadoTexto estado={exp.estado} />
                    <ResumenMotivo error={exp.error} />
                  </td>
                  <td className="num">{celdaImporte(exp, exp.importe_licitacion)}</td>
                  <td className="num">{celdaImporte(exp, exp.importe_adjudicacion)}</td>
                  <td className="num">
                    <CeldaBaja expediente={exp} />
                  </td>
                  <td>
                    {/* En línea (encargo de esta sesión): con los `sin_publicar`
                        ya fuera de esta tabla, dos btn-sm uno junto al otro caben
                        a 1280px con un hueco ajustado — 0.5rem desbordaba la
                        tabla por ~2px (medido con Playwright), 0.35rem no. */}
                    <div style={{ display: "flex", flexDirection: "row", gap: "0.35rem" }}>
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
          {expedientes.length > 0 && filtrados.length === 0 && (
            <p className="muted" style={{ marginTop: "1rem" }}>Ningún expediente coincide con este filtro.</p>
          )}

          {/* Grupo aparte, plegado por defecto (encargo de esta sesión): un
              expediente `sin_publicar` está verificado que no existe en la
              Plataforma (CONTEXTO.md sección 22) — no hay licitación, adjudicación
              ni baja que mostrar, ni descarga o extracción que tenga sentido
              lanzar por defecto. Una fila de una sola línea, sin las columnas
              vacías de la tabla principal. */}
          {noPublicados.length > 0 && (
            <details className="grupo-no-publicados">
              <summary className="chip">
                {noPublicados.length} expediente{noPublicados.length === 1 ? "" : "s"} no publicado
                {noPublicados.length === 1 ? "" : "s"}
              </summary>
              <ul className="lista-no-publicados">
                {noPublicados.map((exp) => (
                  <li key={exp.id} className="fila-no-publicado">
                    <span className="mono">{exp.codigo_expediente}</span>
                    <EstadoTexto estado={exp.estado} />
                    <button
                      onClick={() => lanzarDescarga(exp.id)}
                      disabled={lanzando === exp.id}
                      title="Ya se comprobó que no está en la Plataforma — reintentar solo tiene sentido si ha podido publicarse desde entonces"
                      className="btn btn-ghost btn-sm"
                    >
                      Reintentar
                    </button>
                  </li>
                ))}
              </ul>
            </details>
          )}
        </>
      )}
    </div>
  );
}
