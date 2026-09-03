// Kit compartido por las cuatro pantallas (CLAUDE.md, sesión de diseño de
// interfaz): iconos, badges de estado y formateadores, para no repetir la
// misma paleta y las mismas reglas de formato en cada panel.

type IconProps = { className?: string };

function svgProps(className?: string) {
  return {
    className,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 2,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
  };
}

export function IconCheckCircle({ className }: IconProps) {
  return (
    <svg {...svgProps(className)}>
      <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
      <path d="M22 4 12 14.01l-3-3" />
    </svg>
  );
}

export function IconAlertTriangle({ className }: IconProps) {
  return (
    <svg {...svgProps(className)}>
      <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z" />
      <path d="M12 9v4" />
      <path d="M12 17h.01" />
    </svg>
  );
}

export function IconInfo({ className }: IconProps) {
  return (
    <svg {...svgProps(className)}>
      <circle cx="12" cy="12" r="10" />
      <path d="M12 16v-4" />
      <path d="M12 8h.01" />
    </svg>
  );
}

export function IconBan({ className }: IconProps) {
  return (
    <svg {...svgProps(className)}>
      <circle cx="12" cy="12" r="10" />
      <path d="m4.9 4.9 14.2 14.2" />
    </svg>
  );
}

export function IconClock({ className }: IconProps) {
  return (
    <svg {...svgProps(className)}>
      <circle cx="12" cy="12" r="10" />
      <path d="M12 6v6l4 2" />
    </svg>
  );
}

export function IconSearch({ className }: IconProps) {
  return (
    <svg {...svgProps(className)}>
      <circle cx="11" cy="11" r="8" />
      <path d="m21 21-4.3-4.3" />
    </svg>
  );
}

export function IconFile({ className }: IconProps) {
  return (
    <svg {...svgProps(className)}>
      <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2Z" />
      <path d="M14 2v6h6" />
    </svg>
  );
}

export function IconExternal({ className }: IconProps) {
  return (
    <svg {...svgProps(className)}>
      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
      <path d="M15 3h6v6" />
      <path d="M10 14 21 3" />
    </svg>
  );
}

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

type EstadoVisual = {
  badge: "green" | "amber" | "slate" | "blue" | "red";
  accent: "green" | "amber" | "slate" | "blue";
  Icon: (p: IconProps) => JSX.Element;
};

const VISUAL_ESTADO: Record<string, EstadoVisual> = {
  completado: { badge: "green", accent: "green", Icon: IconCheckCircle },
  pendiente_revision: { badge: "amber", accent: "amber", Icon: IconAlertTriangle },
  sin_publicar: { badge: "slate", accent: "slate", Icon: IconBan },
  fallido: { badge: "red", accent: "amber", Icon: IconAlertTriangle },
  pendiente: { badge: "slate", accent: "slate", Icon: IconClock },
  descargando: { badge: "blue", accent: "blue", Icon: IconClock },
  descargado: { badge: "blue", accent: "blue", Icon: IconClock },
  extrayendo: { badge: "blue", accent: "blue", Icon: IconClock },
  esperando_matriz: { badge: "blue", accent: "blue", Icon: IconClock },
};

export function EstadoBadge({ estado }: { estado: string }) {
  const visual = VISUAL_ESTADO[estado] ?? VISUAL_ESTADO.pendiente;
  const Icon = visual.Icon;
  return (
    <span className={`badge badge-${visual.badge}`}>
      <Icon />
      {ETIQUETA_ESTADO[estado] ?? estado}
    </span>
  );
}

export function accentClaseEstado(estado: string): string {
  const visual = VISUAL_ESTADO[estado] ?? VISUAL_ESTADO.pendiente;
  return `row-accent-${visual.accent}`;
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
