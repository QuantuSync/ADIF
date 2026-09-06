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
 * "transitorio, se está reintentando solo" a "corte real, avisar".
 *
 * `confirmado` (CONTEXTO.md, bloque de estados de carga y error, sesión
 * 2026-09-06): true solo tras al menos una respuesta real de la API. Antes
 * de eso, ningún panel debe enseñar un recuento -- ni siquiera cero -- ni un
 * "sin resultados": un array vacío por falta de respuesta no distingue de un
 * array vacío confirmado, y mostrar ceros en ese hueco se leía como datos
 * perdidos. `inicialConfirmado` deja que la home (con su propio fetch en el
 * servidor) arranque ya confirmada cuando ese fetch sí tuvo éxito, en vez de
 * pasar por un "cargando" espurio en el primer render del cliente. */
export function useReintentoConexion(inicialConfirmado = false) {
  const [error, setError] = useState<string | null>(null);
  const [confirmado, setConfirmado] = useState(inicialConfirmado);
  const fallosSeguidos = useRef(0);

  const registrarExito = useCallback(() => {
    fallosSeguidos.current = 0;
    setError(null);
    setConfirmado(true);
  }, []);

  const registrarFallo = useCallback((mensaje: string) => {
    fallosSeguidos.current += 1;
    if (fallosSeguidos.current >= UMBRAL_FALLOS_CONSECUTIVOS) {
      setError(mensaje);
    }
  }, []);

  // Cargando o reconectando (regla 1): todavía no hay respuesta confirmada
  // ni se ha cumplido el umbral de fallos seguidos para avisar de un corte
  // real (regla 2) -- ninguna de las dos cosas todavía, se sigue esperando.
  const cargando = !confirmado && !error;

  return { error, confirmado, cargando, registrarExito, registrarFallo };
}
