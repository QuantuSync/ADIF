"use client";

import { useEffect, useMemo, useState } from "react";

import { useReintentoConexion } from "../useReintentoConexion";

// Bloque 5, sesión 2026-09-19 (quinta parte): la hoja "Conciliación" del Excel
// como pantalla. Contesta la pregunta que el cliente hace de verdad -- "¿de
// cuáles de mis expedientes no tenemos precios, y por qué?" -- y hasta ahora
// solo se podía mirar abriendo el Excel.
//
// La API (`GET /conciliacion`) devuelve las 534 filas de una vez, con su
// recuento por Situación: son pocas, el filtro es instantáneo en el cliente y
// así el recuento de la cabecera siempre es el del total, no el del filtro.
// No se sondea periódicamente (a diferencia de las otras cuatro pantallas):
// esto solo cambia cuando corre un ciclo, y recorrer el catálogo entero para
// contar no es algo que deba repetirse cada tres segundos.

type FilaConciliacion = {
  codigo_expediente: string;
  titulo: string | null;
  organo_contratacion: string | null;
  estado_plataforma: string | null;
  estado_adif: string | null;
  documentos_descargados: number;
  documentos_reconocimiento_optico: number;
  lineas_en_catalogo: number;
  baja: string;
  situacion: string;
  motivo: string;
};

type RecuentoSituacion = { situacion: string; expedientes: number };

type Registro = {
  departamentos: string[];
  periodos_sindicacion: string[];
  sindicacion_actualizado_hasta: string | null;
  busqueda_ejecutada_en: string | null;
  busqueda_fragmentos: string[];
  busqueda_codigos_encontrados: number | null;
  expedientes_publicados: number;
  expedientes_no_publicados: number;
  expedientes_en_ficha_de_otro: number;
};

type Respuesta = {
  total: number;
  total_lineas: number;
  situaciones: RecuentoSituacion[];
  filas: FilaConciliacion[];
  registro: Registro;
};

// El motor escribe el valor y, entre paréntesis, de dónde sale o por qué no
// consta ("Adjudicada (lo prueba su Resolución...)", "no consta (este
// expediente se conoce por la búsqueda directa...)"). En el Excel la celda es
// ancha y eso se lee bien; en una tabla de once columnas convierte cada fila
// en un párrafo. Aquí se muestra el valor y la explicación va al `title`:
// sigue estando, a un puntero de distancia, sin romper la tabla.
function partirExplicacion(texto: string | null): { valor: string; detalle: string | null } {
  if (!texto) return { valor: "", detalle: null };
  const abre = texto.indexOf(" (");
  if (abre < 0 || !texto.endsWith(")")) return { valor: texto, detalle: null };
  const valor = texto.slice(0, abre);
  return { valor: valor === "no consta" ? "No consta" : valor, detalle: texto.slice(abre + 2, -1) };
}

function CeldaEstado({ texto }: { texto: string | null }) {
  const { valor, detalle } = partirExplicacion(texto);
  if (!valor) return <span className="dato-vacio dato-vacio--no-consta">—</span>;
  const esAusencia = valor === "No consta";
  return (
    <span className={esAusencia ? "dato-vacio dato-vacio--no-consta" : undefined} title={detalle ?? undefined}>
      {valor}
      {detalle && <span className="status-note-inline"> ⓘ</span>}
    </span>
  );
}

function fecha(valor: string | null): string {
  if (!valor) return "—";
  const d = new Date(valor);
  return Number.isNaN(d.getTime()) ? valor : d.toLocaleDateString("es-ES");
}

export default function ConciliacionPanel({ apiUrl }: { apiUrl: string }) {
  const [datos, setDatos] = useState<Respuesta | null>(null);
  const [situacion, setSituacion] = useState<string | null>(null);
  const [expediente, setExpediente] = useState("");
  const [cargando, setCargando] = useState(true);
  const [recarga, setRecarga] = useState(0);
  const { error, confirmado, registrarExito, registrarFallo } = useReintentoConexion();

  useEffect(() => {
    setCargando(true);
    fetch(`${apiUrl}/conciliacion`, { cache: "no-store" })
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
        (situacion === null || f.situacion === situacion) &&
        (texto === "" ||
          f.codigo_expediente.toLowerCase().includes(texto) ||
          (f.titulo ?? "").toLowerCase().includes(texto))
    );
  }, [datos, situacion, expediente]);

  return (
    <div>
      {error && (
        <div className="error-banner">
          No se pudo leer la conciliación: {error}.{" "}
          <button className="btn btn-sm btn-ghost" onClick={() => setRecarga((r) => r + 1)}>
            Reintentar
          </button>
        </div>
      )}

      {!confirmado && !error && <p className="muted">Leyendo la conciliación…</p>}

      {datos && (
        <>
          <div className="search-panel">
            <div className="search-primary field field-primary">
              <label className="field-label" htmlFor="conc-buscar">
                Buscar expediente
              </label>
              <span className="field-hint">Por código o por título</span>
              <input
                id="conc-buscar"
                className="input input-hero"
                value={expediente}
                onChange={(e) => setExpediente(e.target.value)}
                placeholder="6.24/28510.0088"
              />
            </div>
            <div className="search-secondary">
              <div className="field" style={{ gridColumn: "1 / -1" }}>
                <label className="field-label">Situación</label>
                <span className="field-hint">
                  {datos.total} expedientes · {datos.total_lineas.toLocaleString("es-ES")} filas en
                  el catálogo entregado
                </span>
                <div className="filtro-estado-grupo">
                  <button
                    className={`filtro-estado${situacion === null ? " active" : ""}`}
                    onClick={() => setSituacion(null)}
                  >
                    Todas <span className="mono">{datos.total}</span>
                  </button>
                  {datos.situaciones.map((s) => (
                    <button
                      key={s.situacion}
                      className={`filtro-estado${situacion === s.situacion ? " active" : ""}`}
                      onClick={() => setSituacion(s.situacion)}
                      title={s.situacion}
                      disabled={s.expedientes === 0}
                    >
                      {s.situacion} <span className="mono">{s.expedientes}</span>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>

          <p className="muted">
            {filas.length === datos.total
              ? `${datos.total} expedientes`
              : `${filas.length} de ${datos.total} expedientes`}
            {cargando ? " · actualizando…" : ""}
          </p>

          <div className="table-scroll">
            <table className="table">
              <thead>
                <tr>
                  <th>Código de expediente</th>
                  <th>Título</th>
                  <th>Órgano de contratación</th>
                  <th>Estado publicado en la Plataforma</th>
                  <th>Estado según ADIF</th>
                  <th className="num">Docs.</th>
                  <th className="num">Docs. leídos por imagen</th>
                  <th className="num">Líneas que aporta</th>
                  <th>Baja y de dónde sale</th>
                  <th>Situación</th>
                  <th>Motivo</th>
                </tr>
              </thead>
              <tbody>
                {filas.map((f) => (
                  <tr key={f.codigo_expediente} className="row-accent">
                    <td className="mono">{f.codigo_expediente}</td>
                    <td className="descripcion">
                      <span title={f.titulo ?? undefined}>{f.titulo ?? "—"}</span>
                    </td>
                    <td>
                      <CeldaEstado texto={f.organo_contratacion} />
                    </td>
                    <td>
                      <CeldaEstado texto={f.estado_plataforma} />
                    </td>
                    <td>
                      <CeldaEstado texto={f.estado_adif} />
                    </td>
                    <td className="num mono">{f.documentos_descargados}</td>
                    <td className="num mono">
                      {f.documentos_reconocimiento_optico > 0 ? f.documentos_reconocimiento_optico : ""}
                    </td>
                    <td className="num mono">
                      {f.lineas_en_catalogo > 0 ? (
                        f.lineas_en_catalogo.toLocaleString("es-ES")
                      ) : (
                        <span className="dato-vacio dato-vacio--no-consta">0</span>
                      )}
                    </td>
                    <td>
                      <CeldaEstado texto={f.baja} />
                    </td>
                    <td>
                      {f.situacion === "Aporta líneas" ? (
                        <span className="status status-ok">{f.situacion}</span>
                      ) : (
                        <span className="status status-attn">{f.situacion}</span>
                      )}
                    </td>
                    <td className="descripcion">
                      <span title={f.motivo}>{f.motivo}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {filas.length === 0 && (
            <p className="empty-state">Ningún expediente con esa situación y esa búsqueda.</p>
          )}

          {/* De qué fecha es el registro de lo publicado: el mismo texto que
              el Resumen del Excel. Una cifra de cobertura sin decir de cuándo
              es no sirve para decidir nada. */}
          <div className="card">
            <p className="section-label">De cuándo es este registro</p>
            <p className="muted">
              Departamentos: <span className="mono">{datos.registro.departamentos.join(", ")}</span>.{" "}
              {datos.registro.periodos_sindicacion.length} boletines de sindicación, el más reciente
              con datos de {fecha(datos.registro.sindicacion_actualizado_hasta)}. Última búsqueda
              directa en la Plataforma el {fecha(datos.registro.busqueda_ejecutada_en)} con{" "}
              <span className="mono">{datos.registro.busqueda_fragmentos.join(", ") || "—"}</span>,{" "}
              {datos.registro.busqueda_codigos_encontrados ?? "—"} expedientes devueltos.
            </p>
            <p className="muted">
              {datos.registro.expedientes_publicados} constan publicados,{" "}
              {datos.registro.expedientes_no_publicados} no aparecen al buscarlos por su número, y{" "}
              {datos.registro.expedientes_en_ficha_de_otro} de esos sí tienen sus documentos
              publicados dentro de la ficha de otro expediente.
            </p>
          </div>
        </>
      )}
    </div>
  );
}
