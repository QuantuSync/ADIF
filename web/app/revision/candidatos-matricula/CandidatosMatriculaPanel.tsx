"use client";

import { useEffect, useState } from "react";
import { useReintentoConexion } from "../../useReintentoConexion";

type CandidatoMatricula = {
  matricula_candidata: string;
  denominacion_maestro: string | null;
  similitud: string;
  exacto: boolean;
};

type LineaCandidatosMatricula = {
  linea_id: number;
  expediente_id: number;
  codigo_expediente: string;
  identificador_lote: string | null;
  codigo_precio: string | null;
  descripcion: string;
  candidatos: CandidatoMatricula[];
};

type RespuestaCola = {
  total: number;
  pagina: number;
  tamano_pagina: number;
  lineas: LineaCandidatosMatricula[];
};

type ResumenCalculo = {
  lineas_sin_matricula: number;
  lineas_con_candidato: number;
  lineas_sin_candidato: number;
  candidatos_generados: number;
};

const TAMANO_PAGINA = 50;
// Debounce del filtro por expediente: sin esto, cada pulsación relanza la
// consulta -- con 2.000+ líneas de por medio, teclear "6.24/28510" a ritmo
// normal dispararía seis peticiones antes de terminar.
const DEBOUNCE_FILTRO_MS = 400;

function formatearSimilitud(valor: string): string {
  return `${(Number(valor) * 100).toFixed(1)} %`;
}

export default function CandidatosMatriculaPanel({ apiUrl }: { apiUrl: string }) {
  const [lineas, setLineas] = useState<LineaCandidatosMatricula[]>([]);
  const [total, setTotal] = useState(0);
  const [pagina, setPagina] = useState(1);
  const [filtroInput, setFiltroInput] = useState("");
  const [filtro, setFiltro] = useState("");
  const { error, confirmado, cargando, registrarExito, registrarFallo } = useReintentoConexion();
  // Por línea, qué acción está en curso (deshabilita sus propios botones sin
  // congelar el resto de la cola) o qué panel de nota está abierto.
  const [enCurso, setEnCurso] = useState<Set<number>>(new Set());
  const [notaAbiertaEn, setNotaAbiertaEn] = useState<number | null>(null);
  const [textoNota, setTextoNota] = useState("");
  const [avisoAccion, setAvisoAccion] = useState<string | null>(null);

  // Resumen de la última vez que se calculó la cola -- informativo, para que
  // quien revisa sepa cuántas quedan sin candidato del todo (nunca aparecen
  // aquí, esta pantalla solo lista las que sí tienen alguno).
  const [resumen, setResumen] = useState<ResumenCalculo | null>(null);
  const [calculando, setCalculando] = useState(false);

  useEffect(() => {
    const id = setTimeout(() => {
      setFiltro(filtroInput.trim());
      setPagina(1);
    }, DEBOUNCE_FILTRO_MS);
    return () => clearTimeout(id);
  }, [filtroInput]);

  async function cargar() {
    try {
      const params = new URLSearchParams({ pagina: String(pagina), tamano_pagina: String(TAMANO_PAGINA) });
      if (filtro) params.set("codigo_expediente", filtro);
      const res = await fetch(`${apiUrl}/revision/candidatos-matricula?${params.toString()}`, { cache: "no-store" });
      if (!res.ok) throw new Error(`la API respondió ${res.status}`);
      const datos: RespuestaCola = await res.json();
      setLineas(datos.lineas);
      setTotal(datos.total);
      registrarExito();
    } catch (e) {
      registrarFallo(e instanceof Error ? e.message : String(e));
    }
  }

  useEffect(() => {
    cargar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pagina, filtro]);

  function marcarEnCurso(lineaId: number, activo: boolean) {
    setEnCurso((actual) => {
      const siguiente = new Set(actual);
      if (activo) siguiente.add(lineaId);
      else siguiente.delete(lineaId);
      return siguiente;
    });
  }

  // Aceptar es de un clic a propósito (encargo explícito: "son 2.000
  // líneas") -- ni confirmación ni formulario intermedio. Quita la línea de
  // la lista en cuanto la API confirma, sin esperar al siguiente sondeo, para
  // que despachar la cola se sienta inmediato.
  async function aceptar(linea: LineaCandidatosMatricula, candidato: CandidatoMatricula) {
    setAvisoAccion(null);
    marcarEnCurso(linea.linea_id, true);
    try {
      const res = await fetch(`${apiUrl}/revision/candidatos-matricula/${linea.linea_id}/aceptar`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ matricula_candidata: candidato.matricula_candidata }),
      });
      if (!res.ok) {
        const detalle = await res.json().catch(() => null);
        throw new Error(detalle?.detail ?? `la API respondió ${res.status}`);
      }
      setLineas((actual) => actual.filter((l) => l.linea_id !== linea.linea_id));
      setTotal((t) => Math.max(0, t - 1));
    } catch (e) {
      setAvisoAccion(e instanceof Error ? e.message : String(e));
    } finally {
      marcarEnCurso(linea.linea_id, false);
    }
  }

  async function rechazar(linea: LineaCandidatosMatricula) {
    setAvisoAccion(null);
    marcarEnCurso(linea.linea_id, true);
    try {
      const res = await fetch(`${apiUrl}/revision/candidatos-matricula/${linea.linea_id}/rechazar`, {
        method: "POST",
      });
      if (!res.ok) throw new Error(`la API respondió ${res.status}`);
      setLineas((actual) => actual.filter((l) => l.linea_id !== linea.linea_id));
      setTotal((t) => Math.max(0, t - 1));
    } catch (e) {
      setAvisoAccion(e instanceof Error ? e.message : String(e));
    } finally {
      marcarEnCurso(linea.linea_id, false);
    }
  }

  function abrirNota(lineaId: number) {
    setAvisoAccion(null);
    setNotaAbiertaEn(notaAbiertaEn === lineaId ? null : lineaId);
    setTextoNota("");
  }

  async function guardarNota(linea: LineaCandidatosMatricula) {
    if (!textoNota.trim()) {
      setAvisoAccion("La nota es obligatoria.");
      return;
    }
    marcarEnCurso(linea.linea_id, true);
    try {
      const res = await fetch(`${apiUrl}/revision/candidatos-matricula/${linea.linea_id}/pendiente`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nota: textoNota.trim() }),
      });
      if (!res.ok) throw new Error(`la API respondió ${res.status}`);
      setNotaAbiertaEn(null);
      // La línea sigue en la cola (dejar nota no decide nada) -- solo se
      // cierra el panel, sin quitarla de la lista.
    } catch (e) {
      setAvisoAccion(e instanceof Error ? e.message : String(e));
    } finally {
      marcarEnCurso(linea.linea_id, false);
    }
  }

  async function recalcularCola() {
    setCalculando(true);
    setAvisoAccion(null);
    try {
      const res = await fetch(`${apiUrl}/mantenimiento/candidatos-matricula/calcular`, { method: "POST" });
      if (!res.ok) throw new Error(`la API respondió ${res.status}`);
      const datos: ResumenCalculo = await res.json();
      setResumen(datos);
      setPagina(1);
      await cargar();
    } catch (e) {
      setAvisoAccion(e instanceof Error ? e.message : String(e));
    } finally {
      setCalculando(false);
    }
  }

  const totalPaginas = Math.max(1, Math.ceil(total / TAMANO_PAGINA));

  return (
    <div>
      <div className="card" style={{ marginBottom: "1.5rem" }}>
        <p className="section-label">Recalcular la cola</p>
        <p className="muted" style={{ marginTop: 0 }}>
          Compara cada línea sin matrícula contra el maestro de materiales de SAP y repuebla la lista de abajo entera.
          Vuelve a lanzarlo tras recargar el maestro o tras un reproceso que cambie qué líneas tienen matrícula.
        </p>
        <div className="button-row">
          <button onClick={recalcularCola} disabled={calculando} className="btn btn-secondary">
            {calculando ? "Calculando…" : "Recalcular candidatos"}
          </button>
        </div>
        {resumen && (
          <p className="muted" style={{ marginTop: "0.9rem" }}>
            Última pasada: {resumen.lineas_sin_matricula} líneas sin matrícula → {resumen.lineas_con_candidato} con al
            menos un candidato, {resumen.lineas_sin_candidato} sin ninguno ({resumen.candidatos_generados} candidatos
            generados en total).
          </p>
        )}
      </div>

      <div className="candidato-toolbar">
        <label className="field">
          <span className="field-label">Filtrar por expediente</span>
          <input
            className="input"
            placeholder="p. ej. 6.24/28510.0088"
            value={filtroInput}
            onChange={(e) => setFiltroInput(e.target.value)}
          />
        </label>
        <span className="muted">
          {total} línea{total === 1 ? "" : "s"} en la cola{filtro ? ` para "${filtro}"` : ""}
        </span>
      </div>

      {cargando && <p className="muted">Cargando cola de candidatos…</p>}
      {error && <p className="error-banner">{error}</p>}
      {avisoAccion && <p className="error-banner">{avisoAccion}</p>}
      {confirmado && lineas.length === 0 && !error && (
        <p className="empty-state">
          {filtro
            ? `Sin líneas pendientes de revisar para "${filtro}".`
            : "Sin líneas pendientes en la cola de candidatos de matrícula."}
        </p>
      )}

      {lineas.map((linea) => (
        <div key={linea.linea_id} className="card candidato-card">
          <div>
            <div className="candidato-cabecera">
              <span className="mono muted" style={{ fontSize: "0.85rem" }}>
                {linea.codigo_expediente}
                {linea.identificador_lote ? ` · Lote ${linea.identificador_lote}` : ""}
                {linea.codigo_precio ? ` · ${linea.codigo_precio}` : ""}
              </span>
            </div>
            <p className="section-label">Descripción del pliego</p>
            <p className="candidato-pliego">{linea.descripcion}</p>
          </div>

          <div>
            <p className="section-label">Candidatos del maestro de materiales ({linea.candidatos.length})</p>
            <div className="candidato-lista">
              {linea.candidatos.map((c) => (
                <div
                  key={c.matricula_candidata}
                  className={`candidato-fila${c.exacto ? " candidato-fila--exacto" : ""}`}
                >
                  <div>
                    {c.exacto && <span className="candidato-badge-exacto">Coincidencia exacta</span>}
                    <div className="candidato-denominacion">{c.denominacion_maestro ?? "—"}</div>
                    <span className="candidato-matricula">{c.matricula_candidata}</span>
                  </div>
                  <span className="candidato-similitud">{formatearSimilitud(c.similitud)}</span>
                  <button
                    onClick={() => aceptar(linea, c)}
                    disabled={enCurso.has(linea.linea_id)}
                    className="btn btn-primary btn-sm"
                  >
                    Aceptar
                  </button>
                </div>
              ))}
            </div>

            <div className="candidato-acciones-linea">
              <button
                onClick={() => rechazar(linea)}
                disabled={enCurso.has(linea.linea_id)}
                className="btn btn-secondary btn-sm"
              >
                Ninguno es correcto
              </button>
              <button
                onClick={() => abrirNota(linea.linea_id)}
                disabled={enCurso.has(linea.linea_id)}
                className="btn btn-ghost btn-sm"
              >
                Dejar nota
              </button>
            </div>

            {notaAbiertaEn === linea.linea_id && (
              <div className="candidato-nota-panel">
                <label>
                  <span className="field-label">Nota</span>
                  <textarea
                    className="input"
                    rows={2}
                    value={textoNota}
                    onChange={(e) => setTextoNota(e.target.value)}
                    placeholder="Qué hace falta consultar antes de decidir"
                  />
                </label>
                <div className="button-row" style={{ marginTop: "0.6rem" }}>
                  <button onClick={() => setNotaAbiertaEn(null)} className="btn btn-secondary btn-sm">
                    Cancelar
                  </button>
                  <button
                    onClick={() => guardarNota(linea)}
                    disabled={enCurso.has(linea.linea_id)}
                    className="btn btn-primary btn-sm"
                  >
                    Guardar nota
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      ))}

      {total > TAMANO_PAGINA && (
        <div style={{ display: "flex", gap: "0.75rem", alignItems: "center", marginTop: "1.5rem" }}>
          <button
            onClick={() => setPagina((p) => Math.max(1, p - 1))}
            disabled={pagina <= 1}
            className="btn btn-secondary btn-sm"
          >
            ← Anterior
          </button>
          <span className="muted">
            Página {pagina} de {totalPaginas} ({total} en total)
          </span>
          <button
            onClick={() => setPagina((p) => Math.min(totalPaginas, p + 1))}
            disabled={pagina >= totalPaginas}
            className="btn btn-secondary btn-sm"
          >
            Siguiente →
          </button>
        </div>
      )}
    </div>
  );
}
