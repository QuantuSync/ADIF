type Expediente = {
  id: number;
  codigo_expediente: string;
  estado: string;
};

export default async function Home() {
  const apiUrl = process.env.API_URL ?? "http://localhost:8000";
  let expedientes: Expediente[] = [];
  let error: string | null = null;

  try {
    const res = await fetch(`${apiUrl}/expedientes`, { cache: "no-store" });
    if (!res.ok) {
      throw new Error(`la API respondio ${res.status}`);
    }
    expedientes = await res.json();
  } catch (e) {
    error = e instanceof Error ? e.message : String(e);
  }

  return (
    <main style={{ fontFamily: "sans-serif", padding: "2rem" }}>
      <h1>ADIF - Catalogo de materiales</h1>
      <p>API: {apiUrl}</p>
      {error ? (
        <p style={{ color: "crimson" }}>Error al conectar con la API: {error}</p>
      ) : (
        <>
          <p>Expedientes en base de datos: {expedientes.length}</p>
          <ul>
            {expedientes.map((e) => (
              <li key={e.id}>
                {e.codigo_expediente} — {e.estado}
              </li>
            ))}
          </ul>
        </>
      )}
    </main>
  );
}
