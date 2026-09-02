import ExpedientesPanel, { Expediente } from "./ExpedientesPanel";

export default async function Home() {
  // API_URL: red interna de contenedores, para el fetch inicial en el
  // servidor (Next corriendo dentro de docker-compose). NEXT_PUBLIC_API_URL:
  // variable expuesta al navegador, que no resuelve nombres de contenedor —
  // ver CLAUDE.md sección 13, "la dirección de la API en la web es una
  // variable de entorno".
  const apiUrlServidor = process.env.API_URL ?? "http://localhost:8000";
  const apiUrlNavegador = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

  let expedientes: Expediente[] = [];
  let error: string | null = null;
  try {
    const res = await fetch(`${apiUrlServidor}/expedientes`, { cache: "no-store" });
    if (!res.ok) throw new Error(`la API respondió ${res.status}`);
    expedientes = await res.json();
  } catch (e) {
    error = e instanceof Error ? e.message : String(e);
  }

  return (
    <main>
      <h1 style={{ fontSize: "1.7rem" }}>Expedientes</h1>
      {error ? (
        <p style={{ color: "crimson" }}>Error al conectar con la API: {error}</p>
      ) : (
        <ExpedientesPanel inicial={expedientes} apiUrl={apiUrlNavegador} />
      )}
    </main>
  );
}
