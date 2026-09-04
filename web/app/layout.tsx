import "./globals.css";
import NavLinks from "./nav-links";

export const metadata = {
  title: "ADIF - Catálogo de materiales",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;600;700;800&family=Public+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap"
        />
      </head>
      <body>
        <nav className="app-nav">
          <span className="app-brand">
            ADIF
            <small>Catálogo de materiales</small>
          </span>
          <NavLinks />
        </nav>
        <div className="app-body">{children}</div>
      </body>
    </html>
  );
}
