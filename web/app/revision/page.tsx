import RevisionPanel from "./RevisionPanel";

export default function PaginaRevision() {
  const apiUrlNavegador = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  return (
    <main>
      <h1 className="page-title">Cola de revisión</h1>
      <p className="page-subtitle">Casos que no cuadran solos: el documento al lado, para confirmar o corregir.</p>
      <RevisionPanel apiUrl={apiUrlNavegador} />
    </main>
  );
}
