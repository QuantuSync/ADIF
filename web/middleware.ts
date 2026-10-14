import { NextRequest, NextResponse } from "next/server";

// Sesión 2026-10-14: ninguna pantalla se sirve sin sesión válida. La sesión
// la emite y la valida la API (engine/app/auth.py); aquí solo se pregunta a la
// API, por la red interna, si la cookie que trae el navegador sigue valiendo.
// Los datos nunca dependen de esto -- la API rechaza por su cuenta cualquier
// petición sin sesión --, pero así nadie ve una pantalla vacía en vez de la
// de entrada.
const API_URL = process.env.API_URL ?? "http://localhost:8000";
// Mismo nombre que `sesion_cookie_nombre` en engine/app/config.py.
const COOKIE_SESION = "adif_sesion";
const PANTALLA_ENTRADA = "/entrar";
const PANTALLA_CAMBIO = "/cambiar-contrasena";

// La dirección pública se arma con las cabeceras que manda el servidor de
// entrada (`Host` intacto y `X-Forwarded-Proto`), no con `req.url`: detrás
// de él, la URL que ve Next es la interna. Next exige una Location absoluta.
function redirigir(req: NextRequest, destino: string) {
  const host = req.headers.get("x-forwarded-host") ?? req.headers.get("host") ?? req.nextUrl.host;
  const protocolo = req.headers.get("x-forwarded-proto") ?? req.nextUrl.protocol.replace(":", "");
  return NextResponse.redirect(`${protocolo}://${host}${destino}`, 307);
}

export async function middleware(req: NextRequest) {
  const { pathname, search } = req.nextUrl;
  if (pathname === PANTALLA_ENTRADA) return NextResponse.next();

  const aEntrar = () =>
    redirigir(
      req,
      pathname === "/" ? PANTALLA_ENTRADA : `${PANTALLA_ENTRADA}?siguiente=${encodeURIComponent(pathname + search)}`
    );
  const token = req.cookies.get(COOKIE_SESION)?.value;
  if (!token) return aEntrar();

  let respuesta: Response;
  try {
    respuesta = await fetch(`${API_URL}/auth/sesion`, {
      headers: { cookie: `${COOKIE_SESION}=${token}` },
      cache: "no-store",
    });
  } catch {
    // API caída (p. ej. reinicio de dockerd): se deja pasar. Sin API no hay
    // datos que enseñar, y cada pantalla ya sabe avisar del corte y
    // reintentar sola (useReintentoConexion).
    return NextResponse.next();
  }
  if (respuesta.status === 401) return aEntrar();
  if (respuesta.ok) {
    const sesion = (await respuesta.json()) as { debe_cambiar_contrasena?: boolean };
    if (sesion.debe_cambiar_contrasena && pathname !== PANTALLA_CAMBIO) return redirigir(req, PANTALLA_CAMBIO);
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/|favicon.ico).*)"],
};
