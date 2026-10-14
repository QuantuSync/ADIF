"use client";

import { FormEvent, useState } from "react";
import { API_URL_NAVEGADOR } from "../sesion-cliente";

// Solo rutas de esta misma web: un `siguiente` que apunte fuera ("//otro.sitio",
// "https://...") convertiría la pantalla de entrada en un redirector abierto.
function destinoSeguro(siguiente: string | null): string {
  return siguiente && siguiente.startsWith("/") && !siguiente.startsWith("//") ? siguiente : "/";
}

export default function Entrar() {
  const [usuario, setUsuario] = useState("");
  const [contrasena, setContrasena] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  async function enviar(e: FormEvent) {
    e.preventDefault();
    setEnviando(true);
    setError(null);
    try {
      const res = await fetch(`${API_URL_NAVEGADOR}/auth/entrar`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ usuario, contrasena }),
      });
      const cuerpo = await res.json().catch(() => null);
      if (!res.ok) {
        setError(cuerpo?.detail ?? `No se ha podido entrar (${res.status}).`);
        setEnviando(false);
        return;
      }
      const siguiente = new URLSearchParams(window.location.search).get("siguiente");
      window.location.assign(cuerpo?.debe_cambiar_contrasena ? "/cambiar-contrasena" : destinoSeguro(siguiente));
    } catch {
      setError("No hay conexión con el servidor. Vuelve a intentarlo en unos segundos.");
      setEnviando(false);
    }
  }

  return (
    <div className="acceso">
      <p className="acceso-marca">
        ADIF <span>Catálogo de materiales</span>
      </p>
      <h1 className="acceso-titulo">Entrar</h1>
      <form onSubmit={enviar} className="acceso-form">
        <label className="field">
          <span className="field-label">Usuario</span>
          <input
            className="input"
            name="usuario"
            autoComplete="username"
            autoCapitalize="none"
            spellCheck={false}
            required
            autoFocus
            value={usuario}
            onChange={(e) => setUsuario(e.target.value)}
          />
        </label>
        <label className="field">
          <span className="field-label">Contraseña</span>
          <input
            className="input"
            name="contrasena"
            type="password"
            autoComplete="current-password"
            required
            value={contrasena}
            onChange={(e) => setContrasena(e.target.value)}
          />
        </label>
        {error && (
          <p className="acceso-error" role="alert">
            {error}
          </p>
        )}
        <button type="submit" className="btn acceso-boton" disabled={enviando}>
          {enviando ? "Entrando…" : "Entrar"}
        </button>
      </form>
      <p className="acceso-nota">La sesión se cierra sola tras un rato sin actividad.</p>
    </div>
  );
}
