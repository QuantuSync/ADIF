// Sesión 2026-10-14: todas las llamadas del navegador a la API llevan la
// cookie de sesión (`credentials: "include"`; en local la web y la API son
// orígenes distintos, :3000 y :8000). Se hace una sola vez, envolviendo
// `fetch`, en vez de tocar cada llamada de cada panel.
//
// Dos cosas más, también aquí para que valgan en todas las pantallas:
// - Una petición que sale sin que el usuario haya tocado nada en el último
//   minuto (el sondeo automático de los paneles) va marcada con `X-Sondeo`,
//   y la API no la cuenta como actividad: si no, una pestaña olvidada
//   abierta mantendría la sesión viva para siempre.
// - Un 401 (sesión caducada) lleva a la pantalla de entrada, y el 403 del
//   cambio de contraseña obligatorio, a la de cambio.

export const API_URL_NAVEGADOR = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const SIN_INTERACCION_MS = 60_000;

let ultimaInteraccion = Date.now();
let redirigiendo = false;

function irA(destino: string) {
  if (redirigiendo) return;
  redirigiendo = true;
  window.location.assign(destino);
}

function urlDe(input: RequestInfo | URL): string {
  if (typeof input === "string") return input;
  if (input instanceof URL) return input.href;
  return input.url;
}

type VentanaConMarca = Window & { __adifSesion?: boolean };

if (typeof window !== "undefined" && !(window as VentanaConMarca).__adifSesion) {
  (window as VentanaConMarca).__adifSesion = true;
  for (const evento of ["pointerdown", "keydown", "wheel", "touchstart"]) {
    window.addEventListener(evento, () => (ultimaInteraccion = Date.now()), { passive: true, capture: true });
  }
  const fetchOriginal = window.fetch.bind(window);
  window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = urlDe(input);
    if (!url.startsWith(API_URL_NAVEGADOR)) return fetchOriginal(input, init);
    const cabeceras = new Headers(init?.headers ?? (input instanceof Request ? input.headers : undefined));
    if (Date.now() - ultimaInteraccion > SIN_INTERACCION_MS) cabeceras.set("X-Sondeo", "1");
    const respuesta = await fetchOriginal(input, { ...init, headers: cabeceras, credentials: "include" });
    if (respuesta.status === 401 && !url.startsWith(`${API_URL_NAVEGADOR}/auth/entrar`)) {
      const aqui = window.location.pathname + window.location.search;
      irA(aqui === "/" ? "/entrar" : `/entrar?siguiente=${encodeURIComponent(aqui)}`);
    } else if (respuesta.status === 403 && window.location.pathname !== "/cambiar-contrasena") {
      const cuerpo = await respuesta.clone().json().catch(() => null);
      if (cuerpo?.detail === "cambio_contrasena_obligatorio") irA("/cambiar-contrasena");
    }
    return respuesta;
  };
}
