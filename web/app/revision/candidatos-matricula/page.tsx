import CandidatosMatriculaPanel from "./CandidatosMatriculaPanel";

export default function PaginaCandidatosMatricula() {
  const apiUrlNavegador = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  return (
    <main>
      <h1 className="page-title">Candidatos de matrícula</h1>
      <p className="page-subtitle">
        Líneas del catálogo sin matrícula con al menos una coincidencia en el maestro de materiales de SAP — el
        sistema nunca la asigna solo, cada una espera una decisión aquí.
      </p>
      <CandidatosMatriculaPanel apiUrl={apiUrlNavegador} />
    </main>
  );
}
