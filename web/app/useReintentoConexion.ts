"use client";

import { useCallback, useRef, useState } from "react";

// Encargo de la sesión de tolerancia a reinicios de dockerd (2026-09-06):
// un corte de conexión de un par de segundos (el caso real de esta sesión)
// no debe encender un banner rojo si el siguiente sondeo automático ya lo
// resuelve solo -- eso es lo que ya reintenta cada panel (sondeo periódico
// o reintento tras fallo). Solo tras varios fallos SEGUIDOS se considera un
// corte real que vale la pena interrumpir al usuario con él.
const UMBRAL_FALLOS_CONSECUTIVOS = 3;

/** Política común de cuándo mostrar el aviso de conexión. Cada panel sigue
 * dueño de su propio sondeo/reintento (distintos endpoints, distintos
 * intervalos) -- esto solo decide si un fallo puntual ya pasó de
 * "transitorio, se está reintentando solo" a "corte real, avisar". */
export function useReintentoConexion() {
  const [error, setError] = useState<string | null>(null);
  const fallosSeguidos = useRef(0);

  const registrarExito = useCallback(() => {
    fallosSeguidos.current = 0;
    setError(null);
  }, []);

  const registrarFallo = useCallback((mensaje: string) => {
    fallosSeguidos.current += 1;
    if (fallosSeguidos.current >= UMBRAL_FALLOS_CONSECUTIVOS) {
      setError(mensaje);
    }
  }, []);

  return { error, registrarExito, registrarFallo };
}
