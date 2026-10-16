"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import NavLinks from "./nav-links";
import { type Perfil, ProveedorPerfil } from "./perfil";
import { API_URL_NAVEGADOR } from "./sesion-cliente";

// Pantallas sin barra de navegación: la de entrada, y la de cambio de
// contraseña mientras es obligatoria (todavía no se puede ir a ningún sitio).
const SIN_MARCO = new Set(["/entrar"]);

type Sesion = { usuario: string; debe_cambiar_contrasena: boolean; perfil: Perfil };

export default function Marco({ children }: { children: React.ReactNode }) {
  const pathname = usePathname() ?? "";
  const [sesion, setSesion] = useState<Sesion | null>(null);

  useEffect(() => {
    if (SIN_MARCO.has(pathname)) return;
    fetch(`${API_URL_NAVEGADOR}/auth/sesion`, { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then(setSesion)
      .catch(() => setSesion(null));
  }, [pathname]);

  // En la de cambio, hasta saber si es obligatorio no se pinta la barra: si
  // lo es, enseñarla un instante invitaría a pulsar enlaces que no llevan.
  const cambioPorConfirmar = pathname === "/cambiar-contrasena" && sesion === null;
  if (SIN_MARCO.has(pathname) || cambioPorConfirmar || sesion?.debe_cambiar_contrasena) {
    return <div className="acceso-fondo">{children}</div>;
  }

  async function salir() {
    await fetch(`${API_URL_NAVEGADOR}/auth/salir`, { method: "POST" }).catch(() => null);
    window.location.assign("/entrar");
  }

  return (
    <>
      <nav className="app-nav">
        <span className="app-brand">
          ADIF
          <small>Catálogo de materiales</small>
        </span>
        <NavLinks />
        <span className="nav-usuario">
          {sesion && (
            <span className="nav-usuario-nombre">
              {sesion.usuario}
              {sesion.perfil === "consulta" && <span className="nav-usuario-perfil"> · solo consulta</span>}
            </span>
          )}
          <Link href="/cambiar-contrasena" className={`nav-link${pathname === "/cambiar-contrasena" ? " active" : ""}`}>
            Contraseña
          </Link>
          <button type="button" className="nav-link nav-salir" onClick={salir}>
            Salir
          </button>
        </span>
      </nav>
      <div className="app-body">
        <ProveedorPerfil value={sesion?.perfil ?? null}>{children}</ProveedorPerfil>
      </div>
    </>
  );
}
