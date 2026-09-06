"use client";

import { useEffect, useState } from "react";
import { useReintentoConexion } from "../useReintentoConexion";
import {
  DatoVacio,
  DescripcionCelda,
  esPartidaAlzada,
  formatearImporte,
  formatearNumero,
  formatearPorcentaje,
} from "../ui";

type LineaCatalogo = {
  id: number;
  lote_id: number | null;
  expediente_id: number;
  codigo_expediente: string;
  codigo_matriz: string | null;
  nombre_proyecto: string | null;
  codigo_interno: string | null;
  codigos_cruzados: boolean | null;
  // Huérfana (CONTEXTO.md sección 2): la tabla de origen no se pudo asociar a
  // un lote sin ambigüedad. Existe y se puede revisar, pero no cuelga de
  // ningún lote -- `null`, no una cadena vacía.
  identificador_lote: string | null;
  codigo_precio: string | null;
  matricula: string | null;
  descripcion: string;
  codigo_material: string | null;
  cantidad: string | null;
  precio_unitario: string | null;
  unidad_medida: string | null;
  baja_lote: string | null;
  precio_adjudicado: string | null;
  comentarios: string | null;
  estado_revision: string;
  motivo_revision: string | null;
  documento_origen_id: number | null;
  documento_origen_nombre: string | null;
  pagina: number | null;
  fragmento: string | null;
};

// Encargo de esta sesión: "sin confirmar" es el estado por defecto de las
// 3.018 líneas, así que repetirlo en cada fila es ruido, no información —
// mismo principio que ya sigue `ui.tsx` ("un valor ausente se deja en
// blanco"). La columna solo habla cuando hay algo que decir: una línea ya
// confirmada/corregida (buena noticia, acento) o una que trae un motivo de
// revisión real (exige atención humana) — cualquier otra cosa, en blanco.
function celdaRevision(linea: LineaCatalogo) {
  if (linea.estado_revision === "confirmado" || linea.estado_revision === "corregido") {
    return <span className="status status-ok">{linea.estado_revision === "confirmado" ? "Confirmado" : "Corregido"}</span>;
  }
  if (linea.estado_revision === "descartado") {
    return <span className="status status-faint">Descartado</span>;
  }
  if (linea.motivo_revision) {
    return (
      <span className="status status-attn" title={linea.motivo_revision}>
        Revisar
      </span>
    );
  }
  return null;
}

// Fila que de verdad exige atención humana (mismo criterio que la etiqueta
// "Revisar" de arriba) — encargo de esta sesión: con 4.195 líneas, la
// etiqueta sola en la última columna se pierde al recorrer la tabla. El
// acento al margen (mismo patrón que Expedientes) la hace visible sin
// necesidad de llegar hasta esa columna.
function necesitaRevision(linea: LineaCatalogo): boolean {
  return (
    linea.estado_revision !== "confirmado" &&
    linea.estado_revision !== "corregido" &&
    linea.estado_revision !== "descartado" &&
    Boolean(linea.motivo_revision)
  );
}

// Matrícula vacía (CONTEXTO.md sección 2 y encargo de esta sesión): distingue
// "no aplica" (partida alzada — reserva presupuestaria, no un artículo de
// almacén, hueco correcto y definitivo) de "no existe en el documento" (el
// cuadro de precios de origen no la traía en ~1/3 de las líneas, tampoco
// hay nada que recuperar) — hoy ambas se veían igual de "en blanco" que un
// dato realmente pendiente.
function celdaConCausaDeVacio(valor: string | null, esPartida: boolean, tituloNoConsta: string) {
  if (valor) return valor;
  if (esPartida) {
    return (
      <DatoVacio
        motivo="na"
        titulo="Partida alzada: es una reserva presupuestaria, no un artículo de almacén — no lleva este dato."
      />
    );
  }
  return <DatoVacio motivo="no-consta" titulo={tituloNoConsta} />;
}

// Precio adjudicado = precio unitario × (1 − baja de lote) — CONTEXTO.md
// sección 4. Cuando falta, casi siempre es porque el expediente todavía no
// tiene baja de lote declarada, no porque el sistema no supiera calcularlo:
// distinto de un simple hueco, se resuelve solo en cuanto llegue ese dato.
function celdaPrecioAdjudicado(linea: LineaCatalogo) {
  const texto = formatearNumero(linea.precio_adjudicado);
  if (texto) return texto;
  if (linea.precio_unitario && !linea.baja_lote) {
    return (
      <DatoVacio
        motivo="pendiente"
        titulo="El expediente todavía no tiene baja de lote declarada. En cuanto se registre, se calcula solo."
      />
    );
  }
  return "";
}

// Lote vacío (huérfana, CONTEXTO.md sección 2): la tabla de origen no se pudo
// asociar a un único lote sin ambigüedad -- `linea.motivo_revision` ya trae
// el detalle exacto (banda vacía, varias cabeceras LOTE N en la misma
// franja...); esta celda solo señala que el hueco tiene una causa conocida
// y remite a él, en vez de dejarlo en blanco como si fuera un dato
// cualquiera sin extraer.
function celdaLote(linea: LineaCatalogo) {
  if (linea.identificador_lote) return linea.identificador_lote;
  return (
    <DatoVacio
      motivo="no-consta"
      titulo={
        linea.motivo_revision ??
        "No se pudo asociar esta línea a un único lote sin ambigüedad (ver el motivo de revisión del expediente)."
      }
    />
  );
}

// Código de precio vacío: el cuadro de precios de origen no trae un
// identificador de línea distinto para esta fila (CONTEXTO.md sección 2, la
// matrícula es la única clave alternativa cuando falta). Definitivo, nada
// que recuperar -- distinto de un valor descartado por formato irreconocible
// (eso ya lleva su propio `motivo_revision`, con el valor bruto).
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

// Cantidad vacía: verificado contra el corpus real (bloque 3, sesión
// 2026-09-06, docs/inventario-celdas-vacias.md) que la mayoría de los casos
// son catálogos de acuerdo marco de muchos lotes que fijan solo el precio
// unitario, sin comprometer una cantidad hasta el pedido futuro concreto --
// no un hueco de extracción. Un caso real donde el número sí estaba en el
// documento y no se leía (columna fantasma en la cabecera) ya se corrige en
// el motor (`app.catalogo._recuperar_cantidad_columna_fantasma`), no aquí.
function celdaCantidad(linea: LineaCatalogo) {
  const texto = formatearNumero(linea.cantidad, 2);
  if (texto) return texto;
  return (
    <DatoVacio
      motivo="no-consta"
      titulo="El cuadro de precios de origen no fija una cantidad para esta línea (frecuente en catálogos de acuerdo marco de muchos lotes, donde la cantidad se decide pedido a pedido)."
    />
  );
}

// Precio unitario vacío: siempre un hueco real de extracción (a diferencia
// de cantidad, ningún cuadro de precios licita sin precio) -- verificado
// contra el corpus real que casi todos los casos ya se recuperan solos en
// el motor (`app.catalogo._recuperar_precio_columna_fantasma`); lo que
// queda es la minoría genuina sin precio interpretable, con su propio
// motivo_revision.
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

type RespuestaCatalogo = {
  total: number;
  pagina: number;
  tamano_pagina: number;
  lineas: LineaCatalogo[];
};

const TAMANO_PAGINA = 25;
const REINTENTO_MS = 3000;

export default function CatalogoPanel({ apiUrl }: { apiUrl: string }) {
  const [matricula, setMatricula] = useState("");
  const [expediente, setExpediente] = useState("");
  const [lote, setLote] = useState("");
  const [q, setQ] = useState("");
  const [pagina, setPagina] = useState(1);
  const [datos, setDatos] = useState<RespuestaCatalogo | null>(null);
  const [cargando, setCargando] = useState(false);
  const { error, registrarExito, registrarFallo } = useReintentoConexion();
  const [seleccion, setSeleccion] = useState<LineaCatalogo | null>(null);
  // Tolerancia a reinicios de dockerd (sesión 2026-09-06): antes, esta
  // página solo volvía a pedir datos cuando el usuario cambiaba un filtro
  // -- un fallo puntual se quedaba así para siempre, sin reintentar solo.
  // `reintento` no cambia ningún filtro; solo fuerza que el efecto de abajo
  // se repita cuando la petición anterior falló.
  const [reintento, setReintento] = useState(0);

  useEffect(() => {
    const id = setTimeout(() => {
      setCargando(true);
      const params = new URLSearchParams({ pagina: String(pagina), tamano_pagina: String(TAMANO_PAGINA) });
      if (matricula.trim()) params.set("matricula", matricula.trim());
      if (expediente.trim()) params.set("expediente", expediente.trim());
      if (lote.trim()) params.set("lote", lote.trim());
      if (q.trim()) params.set("q", q.trim());

      fetch(`${apiUrl}/catalogo?${params.toString()}`, { cache: "no-store" })
        .then((res) => {
          if (!res.ok) throw new Error(`la API respondió ${res.status}`);
          return res.json();
        })
        .then((json: RespuestaCatalogo) => {
          setDatos(json);
          registrarExito();
        })
        .catch((e) => {
          registrarFallo(e instanceof Error ? e.message : String(e));
          setTimeout(() => setReintento((r) => r + 1), REINTENTO_MS);
        })
        .finally(() => setCargando(false));
    }, 300);
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiUrl, matricula, expediente, lote, q, pagina, reintento]);

  // Cualquier cambio de filtro vuelve a la página 1 — si no, se puede quedar
  // mirando una página vacía de un resultado mucho más corto.
  function actualizarFiltro(setter: (v: string) => void) {
    return (v: string) => {
      setter(v);
      setPagina(1);
    };
  }

  const totalPaginas = datos ? Math.max(1, Math.ceil(datos.total / TAMANO_PAGINA)) : 1;

  return (
    <div>
      {/* Búsqueda unificada: un solo bloque. La matrícula es la pregunta que
          ADIF realmente tiene — cómo evoluciona el precio de un material a
          través de todos los expedientes — así que ocupa la fila principal,
          con su etiqueta siempre encima del campo. Los otros tres filtros
          conviven en la misma tarjeta, no en una zona aparte. */}
      <div className="search-panel">
        <div className="search-primary field field-primary">
          <label className="field-label" htmlFor="buscar-matricula">
            Buscar por matrícula
          </label>
          <span className="field-hint">En todos los expedientes del catálogo</span>
          <input
            id="buscar-matricula"
            value={matricula}
            onChange={(e) => actualizarFiltro(setMatricula)(e.target.value)}
            placeholder="p. ej. 697500900"
            className="input input-hero"
          />
        </div>

        <div className="search-secondary">
          <div className="field">
            <label className="field-label" htmlFor="filtro-expediente">
              Expediente
            </label>
            <input
              id="filtro-expediente"
              value={expediente}
              onChange={(e) => actualizarFiltro(setExpediente)(e.target.value)}
              placeholder="6.24/28510.0088"
              className="input"
            />
          </div>
          <div className="field">
            <label className="field-label" htmlFor="filtro-lote">
              Lote
            </label>
            <input
              id="filtro-lote"
              value={lote}
              onChange={(e) => actualizarFiltro(setLote)(e.target.value)}
              placeholder="LOTE 1"
              className="input"
            />
          </div>
          <div className="field">
            <label className="field-label" htmlFor="filtro-texto">
              Descripción o código
            </label>
            <input
              id="filtro-texto"
              value={q}
              onChange={(e) => actualizarFiltro(setQ)(e.target.value)}
              placeholder="brida, P-014…"
              className="input"
            />
          </div>
          <div className="field field-action">
            <a href={`${apiUrl}/catalogo/exportar.xlsx`} className="btn btn-primary">
              Exportar Excel
            </a>
          </div>
        </div>
      </div>

      {error && <p className="error-banner">Error al conectar con la API: {error}</p>}

      {datos && (
        <>
          <p className="muted" style={{ marginBottom: "0.6rem" }}>
            {cargando ? "Cargando…" : `${datos.total} línea(s) de catálogo`}
          </p>
          <div className="table-scroll">
            <table className="table">
              <thead>
                <tr>
                  <th>Expediente</th>
                  <th>Lote</th>
                  <th>Matrícula</th>
                  <th>Código</th>
                  <th>Descripción</th>
                  <th className="num">Cantidad</th>
                  <th className="num">Precio unitario</th>
                  <th className="num">Precio adjudicado</th>
                  <th>Revisión</th>
                </tr>
              </thead>
              <tbody>
                {datos.lineas.map((linea) => {
                  const partida = esPartidaAlzada(linea.descripcion);
                  return (
                    <tr
                      key={linea.id}
                      onClick={() => setSeleccion(linea)}
                      className={`clickable row-accent${necesitaRevision(linea) ? " row-accent-attn" : ""}${
                        seleccion?.id === linea.id ? " selected" : ""
                      }`}
                    >
                      <td>{linea.codigo_expediente}</td>
                      <td>{celdaLote(linea)}</td>
                      <td style={linea.matricula ? { fontWeight: 700 } : undefined} className="mono">
                        {celdaConCausaDeVacio(
                          linea.matricula,
                          partida,
                          "El cuadro de precios de origen no trae matrícula para esta línea (pasa en aproximadamente un tercio del catálogo)."
                        )}
                      </td>
                      <td className="mono">{celdaCodigoPrecio(linea)}</td>
                      <td>
                        <DescripcionCelda texto={linea.descripcion} />
                      </td>
                      <td className="num">{celdaCantidad(linea)}</td>
                      <td className="num">{celdaPrecioUnitario(linea)}</td>
                      <td className="num">{celdaPrecioAdjudicado(linea)}</td>
                      <td>{celdaRevision(linea)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {datos.lineas.length === 0 && <p className="empty-state">Sin resultados para estos filtros.</p>}

          <div style={{ display: "flex", gap: "0.75rem", alignItems: "center", marginTop: "1rem" }}>
            <button
              onClick={() => setPagina((p) => Math.max(1, p - 1))}
              disabled={pagina <= 1}
              className="btn btn-secondary btn-sm"
            >
              ← Anterior
            </button>
            <span className="muted">
              Página {pagina} de {totalPaginas}
            </span>
            <button
              onClick={() => setPagina((p) => Math.min(totalPaginas, p + 1))}
              disabled={pagina >= totalPaginas}
              className="btn btn-secondary btn-sm"
            >
              Siguiente →
            </button>
          </div>
        </>
      )}

      {/* Trazabilidad (CONTEXTO.md, encargo de esta sesión, punto 2): de qué
          documento, página y fragmento sale cada cifra — es lo que la
          versión hecha con Copilot no puede ofrecer. */}
      {seleccion && (
        <div className="trace-panel" style={{ marginTop: "2.5rem" }}>
          <div className="trace-header">
            <h2>Trazabilidad — {seleccion.codigo_precio ?? seleccion.matricula ?? `línea ${seleccion.id}`}</h2>
            <button onClick={() => setSeleccion(null)} className="btn btn-ghost btn-sm">
              Cerrar
            </button>
          </div>
          <div className="trace-body">
            <div className="trace-row">
              <dl className="trace-field">
                <dt>Expediente</dt>
                <dd>{seleccion.codigo_expediente}</dd>
              </dl>
              {seleccion.codigo_matriz && (
                <dl className="trace-field">
                  <dt>Matriz</dt>
                  <dd>{seleccion.codigo_matriz}</dd>
                </dl>
              )}
              <dl className="trace-field">
                <dt>Código interno</dt>
                <dd>{seleccion.codigo_interno ?? "sin cruzar con el Excel de códigos"}</dd>
              </dl>
              {seleccion.nombre_proyecto && (
                <dl className="trace-field" style={{ flex: "1 1 100%" }}>
                  <dt>Proyecto</dt>
                  <dd>{seleccion.nombre_proyecto}</dd>
                </dl>
              )}
            </div>

            <div>
              <p className="section-label">Precio y baja</p>
              {seleccion.baja_lote ? (
                <div className="formula">
                  <span>{formatearImporte(seleccion.precio_unitario)}</span>
                  <span className="op">×</span>
                  <span>(1 − {formatearPorcentaje(seleccion.baja_lote)})</span>
                  <span className="op">=</span>
                  <span className="result">{formatearImporte(seleccion.precio_adjudicado)}</span>
                </div>
              ) : (
                <div className="formula">
                  <span>{formatearImporte(seleccion.precio_unitario)}</span>
                  <span className="op muted">— sin baja de lote todavía</span>
                </div>
              )}
            </div>

            <div>
              <p className="section-label">Origen documental</p>
              {seleccion.documento_origen_id ? (
                <a
                  href={`${apiUrl}/documentos/${seleccion.documento_origen_id}/archivo`}
                  target="_blank"
                  rel="noreferrer"
                  className="btn btn-secondary btn-sm"
                >
                  {seleccion.documento_origen_nombre ?? `documento ${seleccion.documento_origen_id}`}
                  {seleccion.pagina && ` · página ${seleccion.pagina}`}
                </a>
              ) : (
                <span className="muted">Sin documento de origen registrado.</span>
              )}
              {seleccion.fragmento && <code className="fragment" style={{ marginTop: "0.75rem" }}>{seleccion.fragmento}</code>}
            </div>

            {seleccion.comentarios && (
              <div>
                <p className="section-label">Comentarios</p>
                <p style={{ margin: 0 }}>{seleccion.comentarios}</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
