"use client";

import { useEffect, useState } from "react";
import { DescripcionCelda, formatearImporte, formatearNumero, formatearPorcentaje } from "../ui";

type LineaCatalogo = {
  id: number;
  lote_id: number;
  expediente_id: number;
  codigo_expediente: string;
  codigo_matriz: string | null;
  nombre_proyecto: string | null;
  codigo_interno: string | null;
  codigos_cruzados: boolean | null;
  identificador_lote: string;
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
  documento_origen_id: number | null;
  documento_origen_nombre: string | null;
  pagina: number | null;
  fragmento: string | null;
};

type RespuestaCatalogo = {
  total: number;
  pagina: number;
  tamano_pagina: number;
  lineas: LineaCatalogo[];
};

const TAMANO_PAGINA = 25;

export default function CatalogoPanel({ apiUrl }: { apiUrl: string }) {
  const [matricula, setMatricula] = useState("");
  const [expediente, setExpediente] = useState("");
  const [lote, setLote] = useState("");
  const [q, setQ] = useState("");
  const [pagina, setPagina] = useState(1);
  const [datos, setDatos] = useState<RespuestaCatalogo | null>(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [seleccion, setSeleccion] = useState<LineaCatalogo | null>(null);

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
          setError(null);
        })
        .catch((e) => setError(e instanceof Error ? e.message : String(e)))
        .finally(() => setCargando(false));
    }, 300);
    return () => clearTimeout(id);
  }, [apiUrl, matricula, expediente, lote, q, pagina]);

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
                {datos.lineas.map((linea) => (
                  <tr
                    key={linea.id}
                    onClick={() => setSeleccion(linea)}
                    className={`clickable${seleccion?.id === linea.id ? " selected" : ""}`}
                  >
                    <td>{linea.codigo_expediente}</td>
                    <td>{linea.identificador_lote}</td>
                    <td style={{ fontWeight: 700 }} className="mono">
                      {linea.matricula ?? ""}
                    </td>
                    <td className="mono">{linea.codigo_precio ?? ""}</td>
                    <td>
                      <DescripcionCelda texto={linea.descripcion} />
                    </td>
                    <td className="num">{formatearNumero(linea.cantidad, 2)}</td>
                    <td className="num">{formatearNumero(linea.precio_unitario)}</td>
                    <td className="num">{formatearNumero(linea.precio_adjudicado)}</td>
                    <td>
                      <span className={linea.estado_revision === "confirmado" ? "status status-ok" : "status"}>
                        {linea.estado_revision === "confirmado" ? "Confirmado" : "Sin confirmar"}
                      </span>
                    </td>
                  </tr>
                ))}
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

      {/* Trazabilidad (CLAUDE.md, encargo de esta sesión, punto 2): de qué
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
