"use client";

import { FormEvent, useEffect, useState } from "react";
import { API_URL_NAVEGADOR } from "../sesion-cliente";

// Mismo mínimo que `contrasena_longitud_minima` en engine/app/config.py. La
// API es quien lo exige; aquí solo se avisa antes de enviar.
const LONGITUD_MINIMA = 12;

export default function CambiarContrasena() {
  const [obligatorio, setObligatorio] = useState(false);
  const [usuario, setUsuario] = useState("");
  const [actual, setActual] = useState("");
  const [nueva, setNueva] = useState("");
  const [repetida, setRepetida] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [hecho, setHecho] = useState(false);
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    fetch(`${API_URL_NAVEGADOR}/auth/sesion`, { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then((s) => {
        setObligatorio(Boolean(s?.debe_cambiar_contrasena));
        setUsuario(s?.usuario ?? "");
      })
      .catch(() => null);
  }, []);

  async function enviar(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (nueva.length < LONGITUD_MINIMA) {
      setError(`La contraseña nueva tiene que tener al menos ${LONGITUD_MINIMA} caracteres.`);
      return;
    }
    if (nueva !== repetida) {
      setError("Las dos contraseñas nuevas no coinciden.");
      return;
    }
    setEnviando(true);
    try {
      const res = await fetch(`${API_URL_NAVEGADOR}/auth/cambiar-contrasena`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ actual, nueva }),
      });
      const cuerpo = await res.json().catch(() => null);
      if (!res.ok) {
        setError(cuerpo?.detail ?? `No se ha podido cambiar (${res.status}).`);
        return;
      }
      if (obligatorio) {
        window.location.assign("/");
        return;
      }
      setHecho(true);
      setActual("");
      setNueva("");
      setRepetida("");
    } catch {
      setError("No hay conexión con el servidor. Vuelve a intentarlo en unos segundos.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className={obligatorio ? "acceso" : "acceso acceso--en-pagina"}>
      {obligatorio && (
        <p className="acceso-marca">
          ADIF <span>Catálogo de materiales</span>
        </p>
      )}
      <h1 className="acceso-titulo">Cambiar contraseña</h1>
      {obligatorio && (
        <p className="acceso-aviso">
          Es tu primera entrada o te han dado una contraseña temporal. Elige una nueva para continuar.
        </p>
      )}
      <form onSubmit={enviar} className="acceso-form">
        {/* Para que el gestor de contraseñas del navegador sepa de qué usuario es. */}
        <input type="text" name="usuario" autoComplete="username" value={usuario} readOnly hidden />
        <label className="field">
          <span className="field-label">Contraseña actual</span>
          <input
            className="input"
            type="password"
            autoComplete="current-password"
            required
            value={actual}
            onChange={(e) => setActual(e.target.value)}
          />
        </label>
        <label className="field">
          <span className="field-label">Contraseña nueva</span>
          <input
            className="input"
            type="password"
            autoComplete="new-password"
            required
            minLength={LONGITUD_MINIMA}
            value={nueva}
            onChange={(e) => setNueva(e.target.value)}
          />
          <span className="acceso-ayuda">Al menos {LONGITUD_MINIMA} caracteres. Una frase corta vale.</span>
        </label>
        <label className="field">
          <span className="field-label">Repite la contraseña nueva</span>
          <input
            className="input"
            type="password"
            autoComplete="new-password"
            required
            value={repetida}
            onChange={(e) => setRepetida(e.target.value)}
          />
        </label>
        {error && (
          <p className="acceso-error" role="alert">
            {error}
          </p>
        )}
        {hecho && (
          <p className="acceso-ok" role="status">
            Contraseña cambiada. Las demás sesiones abiertas con tu usuario se han cerrado.
          </p>
        )}
        <button type="submit" className="btn acceso-boton" disabled={enviando}>
          {enviando ? "Guardando…" : "Cambiar contraseña"}
        </button>
      </form>
    </div>
  );
}
