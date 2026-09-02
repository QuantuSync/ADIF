"use client";

import { useEffect, useState } from "react";

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

function formatearImporte(valor: string | null): string {
  if (valor === null) return "—";
  return Number(valor).toLocaleString("es-ES", { minimumFractionDigits: 2, maximumFractionDigits: 4 });
}

const inputEstilo: React.CSSProperties = {
  padding: "0.5rem 0.6rem",
  fontSize: "1rem",
  border: "1px solid #9ca3af",
  borderRadius: "4px",
};

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
      {/* Búsqueda por matrícula: la pregunta que ADIF realmente tiene — cómo
          evoluciona el precio de un material a través de todos los
          expedientes — así que va primera y más grande. */}
      <div style={{ marginBottom: "1.25rem" }}>
        <label style={{ display: "block", fontSize: "1.15rem", fontWeight: 700, marginBottom: "0.4rem" }}>
          Buscar por matrícula (todos los expedientes)
        </label>
        <input
          value={matricula}
          onChange={(e) => actualizarFiltro(setMatricula)(e.target.value)}
          placeholder="697500900"
          style={{ ...inputEstilo, fontSize: "1.2rem", padding: "0.6rem 0.8rem", minWidth: "20rem" }}
        />
      </div>

      <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap", marginBottom: "1rem" }}>
        <input
          value={expediente}
          onChange={(e) => actualizarFiltro(setExpediente)(e.target.value)}
          placeholder="Filtrar por expediente"
          style={{ ...inputEstilo, minWidth: "14rem" }}
        />
        <input
          value={lote}
          onChange={(e) => actualizarFiltro(setLote)(e.target.value)}
          placeholder="Lote"
          style={{ ...inputEstilo, minWidth: "8rem" }}
        />
        <input
          value={q}
          onChange={(e) => actualizarFiltro(setQ)(e.target.value)}
          placeholder="Buscar en descripción / código"
          style={{ ...inputEstilo, minWidth: "16rem" }}
        />
        <a
          href={`${apiUrl}/catalogo/exportar.xlsx`}
          style={{
            padding: "0.5rem 1rem",
            background: "#111827",
            color: "#fff",
            textDecoration: "none",
            borderRadius: "4px",
            fontWeight: 600,
            fontSize: "1rem",
            alignSelf: "center",
          }}
        >
          Exportar Excel
        </a>
      </div>

      {error && <p style={{ color: "crimson", fontSize: "1.05rem" }}>Error al conectar con la API: {error}</p>}
      {cargando && <p style={{ color: "#6b7280" }}>Cargando…</p>}

      {datos && (
        <>
          <p style={{ color: "#374151", fontSize: "1rem" }}>{datos.total} línea(s) de catálogo</p>
          <div style={{ overflowX: "auto" }}>
            <table style={{ borderCollapse: "collapse", width: "100%", fontSize: "1rem" }}>
              <thead>
                <tr style={{ textAlign: "left", borderBottom: "2px solid #111827" }}>
                  <th style={{ padding: "0.5rem" }}>Expediente</th>
                  <th style={{ padding: "0.5rem" }}>Lote</th>
                  <th style={{ padding: "0.5rem" }}>Matrícula</th>
                  <th style={{ padding: "0.5rem" }}>Código</th>
                  <th style={{ padding: "0.5rem" }}>Descripción</th>
                  <th style={{ padding: "0.5rem" }}>Cantidad</th>
                  <th style={{ padding: "0.5rem" }}>Precio unitario</th>
                  <th style={{ padding: "0.5rem" }}>Precio adjudicado</th>
                  <th style={{ padding: "0.5rem" }}>Revisión</th>
                </tr>
              </thead>
              <tbody>
                {datos.lineas.map((linea) => (
                  <tr
                    key={linea.id}
                    onClick={() => setSeleccion(linea)}
                    style={{
                      borderBottom: "1px solid #e5e7eb",
                      cursor: "pointer",
                      background: seleccion?.id === linea.id ? "#eff6ff" : undefined,
                    }}
                  >
                    <td style={{ padding: "0.5rem" }}>{linea.codigo_expediente}</td>
                    <td style={{ padding: "0.5rem" }}>{linea.identificador_lote}</td>
                    <td style={{ padding: "0.5rem", fontWeight: 600 }}>{linea.matricula ?? "—"}</td>
                    <td style={{ padding: "0.5rem" }}>{linea.codigo_precio ?? "—"}</td>
                    <td style={{ padding: "0.5rem" }}>{linea.descripcion}</td>
                    <td style={{ padding: "0.5rem" }}>{linea.cantidad ?? "—"}</td>
                    <td style={{ padding: "0.5rem" }}>{formatearImporte(linea.precio_unitario)}</td>
                    <td style={{ padding: "0.5rem" }}>{formatearImporte(linea.precio_adjudicado)}</td>
                    <td style={{ padding: "0.5rem" }}>{linea.estado_revision}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {datos.lineas.length === 0 && <p>Sin resultados para estos filtros.</p>}

          <div style={{ display: "flex", gap: "0.75rem", alignItems: "center", marginTop: "1rem" }}>
            <button
              onClick={() => setPagina((p) => Math.max(1, p - 1))}
              disabled={pagina <= 1}
              style={{ padding: "0.4rem 0.8rem", fontSize: "1rem" }}
            >
              ← Anterior
            </button>
            <span>
              Página {pagina} de {totalPaginas}
            </span>
            <button
              onClick={() => setPagina((p) => Math.min(totalPaginas, p + 1))}
              disabled={pagina >= totalPaginas}
              style={{ padding: "0.4rem 0.8rem", fontSize: "1rem" }}
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
        <div
          style={{
            marginTop: "1.5rem",
            padding: "1.25rem",
            border: "2px solid #111827",
            borderRadius: "8px",
            fontSize: "1.05rem",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
            <h2 style={{ fontSize: "1.3rem", margin: 0 }}>
              Trazabilidad — {seleccion.codigo_precio ?? seleccion.matricula ?? `línea ${seleccion.id}`}
            </h2>
            <button onClick={() => setSeleccion(null)} style={{ padding: "0.3rem 0.7rem" }}>
              Cerrar
            </button>
          </div>
          <p>
            <strong>Expediente:</strong> {seleccion.codigo_expediente}
            {seleccion.codigo_matriz && <> · <strong>Matriz:</strong> {seleccion.codigo_matriz}</>}
            {seleccion.nombre_proyecto && (
              <>
                <br />
                <strong>Proyecto:</strong> {seleccion.nombre_proyecto}
              </>
            )}
          </p>
          <p>
            <strong>Código interno:</strong> {seleccion.codigo_interno ?? "sin cruzar con el Excel de códigos"}
          </p>
          <p>
            <strong>Precio unitario:</strong> {formatearImporte(seleccion.precio_unitario)} €{" "}
            {seleccion.baja_lote && (
              <>
                × (1 − {(Number(seleccion.baja_lote) * 100).toFixed(2)}%) ={" "}
                <strong>{formatearImporte(seleccion.precio_adjudicado)} €</strong>
              </>
            )}
          </p>
          <p>
            <strong>Documento origen:</strong>{" "}
            {seleccion.documento_origen_id ? (
              <a
                href={`${apiUrl}/documentos/${seleccion.documento_origen_id}/archivo`}
                target="_blank"
                rel="noreferrer"
              >
                {seleccion.documento_origen_nombre ?? `documento ${seleccion.documento_origen_id}`}
              </a>
            ) : (
              "—"
            )}
            {seleccion.pagina && <> · página {seleccion.pagina}</>}
          </p>
          {seleccion.fragmento && (
            <p>
              <strong>Fragmento extraído:</strong>
              <br />
              <code
                style={{
                  display: "block",
                  background: "#f3f4f6",
                  padding: "0.6rem",
                  borderRadius: "4px",
                  whiteSpace: "pre-wrap",
                  fontSize: "0.95rem",
                }}
              >
                {seleccion.fragmento}
              </code>
            </p>
          )}
          {seleccion.comentarios && (
            <p>
              <strong>Comentarios:</strong> {seleccion.comentarios}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
