import "./globals.css";
import NavLinks from "./nav-links";

export const metadata = {
  title: "ADIF - Catálogo de materiales",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
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
