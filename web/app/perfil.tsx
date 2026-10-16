"use client";

import { createContext, useContext } from "react";

// Sesión 2026-10-16: dos perfiles. Un usuario de consulta ve todas las
// pantallas y exporta, y nada más. Aquí solo se decide qué se enseña: quien
// manda es la API, que responde 403 a cualquier petición que escriba
// (`engine/app/auth.py`, `get_usuario_con_permiso`).
//
// Mientras no se sabe el perfil (la sesión se pide al cargar), se trata como
// consulta: es mejor que los botones aparezcan un instante tarde que
// enseñarlos a quien no los puede usar.
export type Perfil = "escritura" | "consulta";

const PerfilContexto = createContext<Perfil | null>(null);

export const ProveedorPerfil = PerfilContexto.Provider;

export function usePuedeEscribir(): boolean {
  return useContext(PerfilContexto) === "escritura";
}
