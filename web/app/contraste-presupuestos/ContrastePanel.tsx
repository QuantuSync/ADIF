"use client";

import { useEffect, useMemo, useState } from "react";

import { useReintentoConexion } from "../useReintentoConexion";

// Bloque 1, sesión 2026-09-21: la hoja "Contraste de presupuestos" del Excel
// como pantalla, para quienes gestionan expedientes y presupuestos. Mismo
// criterio que la vista de Conciliación: la API devuelve todas las filas de una
// vez con su recuento por Resultado (el recuento es siempre el del total, no el
// del filtro), el filtro es instantáneo en el cliente y la vista no se sondea.

type FilaContraste = {
  codigo_expediente: string;
  lote: string;
  presupuesto_publicado: string;
  tipo_cifra: string;
  cifra_comparada: string;
  documento: string | null;
  pagina: number | null;
  suma_lineas: string;
  diferencia: string;
  diferencia_relativa: string | null;
  lineas: number;
  lineas_sin_cantidad: number;
  resultado: string;
  explicacion: string;
};

type Respuesta = {
  total: number;
  resultados: { resultado: string; lotes: number; significado: string }[];
  filas: FilaContraste[];
  fuera_total: number;
  fuera: { motivo: string; lotes: number }[];
};

const euros = new Intl.NumberFormat("es-ES", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

function importe(valor: string | null): string {
  if (valor === null) return "—";
  const n = Number(valor);
  return Number.isNaN(n) ? valor : `${euros.format(n)} €`;
}

function porcentaje(valor: string | null): string {
  if (valor === null) return "—";
  const n = Number(valor);
  if (Number.isNaN(n)) return valor;
  return `${(n * 100).toLocaleString("es-ES", { minimumFractionDigits: 4, maximumFractionDigits: 4 })} %`;
}

function claseResultado(resultado: string): string {
  if (resultado.startsWith("Cuadra")) return "status status-ok";
  return "status status-attn";
}

export default function ContrastePanel({ apiUrl }: { apiUrl: string }) {
  const [datos, setDatos] = useState<Respuesta | null>(null);
  const [resultado, setResultado] = useState<string | null>(null);
  const [expediente, setExpediente] = useState("");
  const [cargando, setCargando] = useState(true);
  const [recarga, setRecarga] = useState(0);
  const { error, confirmado, registrarExito, registrarFallo } = useReintentoConexion();

  useEffect(() => {
    setCargando(true);
    fetch(`${apiUrl}/contraste-presupuestos`, { cache: "no-store" })
      .then((res) => {
        if (!res.ok) throw new Error(`la API respondió ${res.status}`);
        return res.json();
      })
      .then((json: Respuesta) => {
        setDatos(json);
        registrarExito();
      })
      .catch((e) => registrarFallo(e instanceof Error ? e.message : String(e)))
      .finally(() => setCargando(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiUrl, recarga]);

  const filas = useMemo(() => {
    if (!datos) return [];
    const texto = expediente.trim().toLowerCase();
    return datos.filas.filter(
      (f) =>
        (resultado === null || f.resultado === resultado) &&
        (texto === "" || f.codigo_expediente.toLowerCase().includes(texto))
    );
  }, [datos, resultado, expediente]);

  return (
    <div>
      {error && (
        <div className="error-banner">
          No se pudo leer el contraste de presupuestos: {error}.{" "}
          <button className="btn btn-sm btn-ghost" onClick={() => setRecarga((r) => r + 1)}>
            Reintentar
          </button>
        </div>
      )}

      {!confirmado && !error && <p className="muted">Leyendo el contraste de presupuestos…</p>}

      {datos && (
        <>
          <div className="search-panel">
            <div className="search-primary field field-primary">
              <label className="field-label" htmlFor="contraste-buscar">
                Buscar expediente
              </label>
              <span className="field-hint">Por código</span>
              <input
                id="contraste-buscar"
                className="input input-hero"
                value={expediente}
                onChange={(e) => setExpediente(e.target.value)}
                placeholder="6.20/28510.0054"
              />
            </div>
            <div className="search-secondary">
              <div className="field" style={{ gridColumn: "1 / -1" }}>
                <label className="field-label">Resultado</label>
                <span className="field-hint">
                  {datos.total} lotes contrastados · {datos.fuera_total} lotes con filas en el
                  catálogo que no entran (ver abajo por qué)
                </span>
                <div className="filtro-estado-grupo">
                  <button
                    className={`filtro-estado${resultado === null ? " active" : ""}`}
                    onClick={() => setResultado(null)}
                  >
                    Todos <span className="mono">{datos.total}</span>
                  </button>
                  {datos.resultados.map((r) => (
                    <button
                      key={r.resultado}
                      className={`filtro-estado${resultado === r.resultado ? " active" : ""}`}
                      onClick={() => setResultado(r.resultado)}
                      title={r.significado || r.resultado}
                      disabled={r.lotes === 0}
                    >
                      {r.resultado} <span className="mono">{r.lotes}</span>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>

          <details className="muted">
            <summary>Qué significa cada resultado</summary>
            <ul>
              {datos.resultados.map((r) => (
                <li key={r.resultado}>
                  <strong>{r.resultado}</strong>: {r.significado}
                </li>
              ))}
            </ul>
          </details>

          <p className="muted">
            {filas.length === datos.total
              ? `${datos.total} lotes`
              : `${filas.length} de ${datos.total} lotes`}
            {cargando ? " · actualizando…" : ""}
          </p>

          <div className="table-scroll">
            <table className="table">
              <thead>
                <tr>
                  <th>Código de expediente</th>
                  <th>Lote</th>
                  <th className="num">Presupuesto publicado</th>
                  <th>Qué cifra es</th>
                  <th className="num">Cifra con la que se compara</th>
                  <th>Documento</th>
                  <th className="num">Pág.</th>
                  <th className="num">Suma de sus líneas</th>
                  <th className="num">Diferencia</th>
                  <th className="num">Diferencia (%)</th>
                  <th className="num">Líneas</th>
                  <th className="num">Sin cantidad</th>
                  <th>Resultado</th>
                  <th>Explicación</th>
                </tr>
              </thead>
              <tbody>
                {filas.map((f) => (
                  <tr key={`${f.codigo_expediente}-${f.lote}`} className="row-accent">
                    <td className="mono">{f.codigo_expediente}</td>
                    <td className="mono">{f.lote}</td>
                    <td className="num mono">{importe(f.presupuesto_publicado)}</td>
                    <td className="descripcion">
                      <span title={f.tipo_cifra}>{f.tipo_cifra}</span>
                    </td>
                    <td className="num mono">{importe(f.cifra_comparada)}</td>
                    <td className="descripcion">
                      <span title={f.documento ?? undefined}>{f.documento ?? "—"}</span>
                    </td>
                    <td className="num mono">{f.pagina ?? "—"}</td>
                    <td className="num mono">{importe(f.suma_lineas)}</td>
                    <td className="num mono">{importe(f.diferencia)}</td>
                    <td className="num mono">{porcentaje(f.diferencia_relativa)}</td>
                    <td className="num mono">{f.lineas}</td>
                    <td className="num mono">{f.lineas_sin_cantidad > 0 ? f.lineas_sin_cantidad : ""}</td>
                    <td>
                      <span className={claseResultado(f.resultado)}>{f.resultado}</span>
                    </td>
                    <td className="descripcion">
                      <span title={f.explicacion}>{f.explicacion}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {filas.length === 0 && (
            <p className="empty-state">Ningún lote con ese resultado y esa búsqueda.</p>
          )}

          {/* Los lotes que no entran, y por qué: sin esto, un lote ausente de
              la tabla no se distingue de uno que el sistema no conoce. */}
          <div className="card">
            <p className="section-label">Lotes con filas en el catálogo que no entran en el contraste</p>
            <ul className="muted">
              {datos.fuera.map((m) => (
                <li key={m.motivo}>
                  <span className="mono">{m.lotes}</span> · {m.motivo}
                </li>
              ))}
            </ul>
            <p className="muted">
              Qué cifra es cada presupuesto lo dice la etiqueta con la que se publicó; si no lo dice,
              la fila lo avisa. Esta comprobación no cambia ningún dato del catálogo.
            </p>
          </div>
        </>
      )}
    </div>
  );
}
