// Kit compartido por las cuatro pantallas (CLAUDE.md; rediseño visual
// 2026-09-03): formateadores y el componente de estado, para no repetir la
// misma regla de formato ni la misma distinción tipográfica en cada panel.
// Los estados se distinguen por tipografía y color reservado a lo urgente
// (CLAUDE.md, encargo de esta sesión) — no hay badges ni iconos decorativos.

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

// "ok": resuelto. "attn": exige revisión humana — el único caso que usa el
// color de acento. "faint": fuera de alcance, deliberadamente atenuado.
// "muted": en curso, sin urgencia todavía.
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
  if (valor === null) return "—";
  return `${(Number(valor) * 100).toFixed(2)} %`;
}

export function formatearImporte(valor: string | number | null): string {
  if (valor === null) return "—";
  return `${Number(valor).toLocaleString("es-ES", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })} €`;
}

export function formatearNumero(valor: string | number | null, maxDecimales = 4): string {
  if (valor === null) return "—";
  return Number(valor).toLocaleString("es-ES", { maximumFractionDigits: maxDecimales });
}
