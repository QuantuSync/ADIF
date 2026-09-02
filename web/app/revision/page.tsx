import RevisionPanel from "./RevisionPanel";

export default function PaginaRevision() {
  const apiUrlNavegador = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  return (
    <main>
      <h1 style={{ fontSize: "1.7rem" }}>Cola de revisión</h1>
      <RevisionPanel apiUrl={apiUrlNavegador} />
    </main>
  );
}
