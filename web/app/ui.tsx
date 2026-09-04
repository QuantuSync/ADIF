"use client";

// Kit compartido por las cuatro pantallas (CLAUDE.md; rediseño visual
// 2026-09-04): formateadores y los componentes de estado y descripción, para
// no repetir la misma regla de formato ni la misma distinción tipográfica en
// cada panel. Los estados se distinguen por tipografía, peso y un punto de
// estado — nunca por una insignia de color. Un valor ausente se deja en
// blanco: un guion suelto es ruido visual, no información.

import { useState } from "react";

export type EstadoExpediente =
  | "pendiente"
  | "descargando"
  | "descargado"
  | "extrayendo"
  | "esperando_matriz"
  | "pendiente_revision"
  | "completado"
  | "fallido"
  | "sin_publicar";

export const ETIQUETA_ESTADO: Record<string, string> = {
  pendiente: "Pendiente",
  descargando: "Descargando",
  descargado: "Descargado",
  extrayendo: "Extrayendo",
  esperando_matriz: "Esperando matriz",
  pendiente_revision: "Pendiente de revisión",
  completado: "Completado",
  fallido: "Fallido",
  sin_publicar: "No publicado",
};

// "ok": resuelto — el único estado que usa el acento (es, de verdad, una
// buena noticia). "attn": exige revisión humana — tinta, no color, para no
// competir con el acento. "faint": fuera de alcance, deliberadamente
// atenuado. "muted": en curso, sin urgencia todavía.
type NivelEstado = "ok" | "attn" | "faint" | "muted";

const NIVEL_ESTADO: Record<string, NivelEstado> = {
  completado: "ok",
  pendiente_revision: "attn",
  fallido: "attn",
  sin_publicar: "faint",
  pendiente: "muted",
  descargando: "muted",
  descargado: "muted",
  extrayendo: "muted",
  esperando_matriz: "muted",
};

const CLASE_NIVEL: Record<NivelEstado, string> = {
  ok: "status-ok",
  attn: "status-attn",
  faint: "status-faint",
  muted: "",
};

export function EstadoTexto({ estado }: { estado: string }) {
  const nivel = NIVEL_ESTADO[estado] ?? "muted";
  return (
    <span className={`status ${CLASE_NIVEL[nivel]}`}>{ETIQUETA_ESTADO[estado] ?? estado}</span>
  );
}

export function accentClaseEstado(estado: string): string {
  return (NIVEL_ESTADO[estado] ?? "muted") === "attn" ? "row-accent-attn" : "";
}

export function formatearPorcentaje(valor: string | number | null): string {
  if (valor === null) return "";
  return `${(Number(valor) * 100).toFixed(2)} %`;
}

export function formatearImporte(valor: string | number | null): string {
  if (valor === null) return "";
  return `${Number(valor).toLocaleString("es-ES", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })} €`;
}

export function formatearNumero(valor: string | number | null, maxDecimales = 4): string {
  if (valor === null) return "";
  return Number(valor).toLocaleString("es-ES", { maximumFractionDigits: maxDecimales });
}

const LARGO_TRUNCADO = 64;

// Descripción de línea de catálogo: trunca a una sola línea para no romper
// la altura de la fila, con un control explícito para ver el texto entero.
// stopPropagation evita disparar la selección de fila (trazabilidad) al
// pulsar el propio control.
export function DescripcionCelda({ texto }: { texto: string }) {
  const [expandida, setExpandida] = useState(false);
  const esLarga = texto.length > LARGO_TRUNCADO;
  return (
    <div className={`descripcion${expandida ? " descripcion-expandida" : ""}`}>
      <span>{texto}</span>
      {esLarga && (
        <button
          type="button"
          className="descripcion-toggle"
          onClick={(e) => {
            e.stopPropagation();
            setExpandida((v) => !v);
          }}
        >
          {expandida ? "ver menos" : "ver completo"}
        </button>
      )}
    </div>
  );
}
