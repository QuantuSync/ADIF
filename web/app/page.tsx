import ExpedientesPanel, { Expediente } from "./ExpedientesPanel";

export default async function Home() {
  // API_URL: red interna de contenedores, para el fetch inicial en el
  // servidor (Next corriendo dentro de docker-compose). NEXT_PUBLIC_API_URL:
  // variable expuesta al navegador, que no resuelve nombres de contenedor —
  // ver CONTEXTO.md sección 13, "la dirección de la API en la web es una
  // variable de entorno".
  const apiUrlServidor = process.env.API_URL ?? "http://localhost:8000";
  const apiUrlNavegador = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

  // Tolerancia a reinicios de dockerd (sesión 2026-09-06): antes, un fallo
  // en este fetch inicial del servidor dejaba la página parada en un
  // banner de error estático para siempre -- `ExpedientesPanel`, que sí
  // sondea la API sola cada pocos segundos y se recupera cuando vuelve,
  // nunca llegaba a montarse. Ahora se monta siempre, con `[]` si el fetch
  // inicial falló: su propio sondeo se encarga de rellenarlo en cuanto la
  // API responda, sin que nadie recargue la página.
  let expedientes: Expediente[] = [];
  try {
    const res = await fetch(`${apiUrlServidor}/expedientes`, { cache: "no-store" });
    if (!res.ok) throw new Error(`la API respondió ${res.status}`);
    expedientes = await res.json();
  } catch {
    expedientes = [];
  }

  return (
    <main>
      <h1 className="page-title">Expedientes</h1>
      <p className="page-subtitle">Descarga, extracción y estado de cada expediente del catálogo.</p>
      <ExpedientesPanel inicial={expedientes} apiUrl={apiUrlNavegador} />
    </main>
  );
}
