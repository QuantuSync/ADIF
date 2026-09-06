import MantenimientoPanel from "./MantenimientoPanel";

export default function PaginaMantenimiento() {
  // CONTEXTO.md sección 9.1: la web solo llama a la API por HTTP — sin fetch
  // inicial en el servidor, igual que /catalogo.
  const apiUrlNavegador = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  return (
    <main>
      <h1 className="page-title">Mantenimiento</h1>
      <p className="page-subtitle">
        Descubrir expedientes nuevos, descargar y extraer lo que falte — solo, o a mano.
      </p>
      <MantenimientoPanel apiUrl={apiUrlNavegador} />
    </main>
  );
}
