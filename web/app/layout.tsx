import Link from "next/link";

export const metadata = {
  title: "ADIF - Catalogo de materiales",
};

const estiloEnlace: React.CSSProperties = {
  color: "#111827",
  textDecoration: "none",
  fontSize: "1.1rem",
  fontWeight: 600,
  padding: "0.3rem 0",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <body
        style={{
          fontFamily: "system-ui, -apple-system, Segoe UI, sans-serif",
          fontSize: "17px",
          color: "#111827",
          background: "#fff",
          margin: 0,
        }}
      >
        <nav
          style={{
            display: "flex",
            gap: "1.75rem",
            padding: "1rem 2rem",
            borderBottom: "2px solid #111827",
            alignItems: "baseline",
          }}
        >
          <span style={{ fontSize: "1.25rem", fontWeight: 800, marginRight: "0.5rem" }}>
            ADIF · Catálogo
          </span>
          <Link href="/" style={estiloEnlace}>
            Expedientes
          </Link>
          <Link href="/catalogo" style={estiloEnlace}>
            Catálogo
          </Link>
          <Link href="/revision" style={estiloEnlace}>
            Cola de revisión
          </Link>
        </nav>
        <div style={{ padding: "1.5rem 2rem" }}>{children}</div>
      </body>
    </html>
  );
}
