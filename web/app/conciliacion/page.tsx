import ConciliacionPanel from "./ConciliacionPanel";

export default function PaginaConciliacion() {
  // CONTEXTO.md sección 9.1: la web solo llama a la API por HTTP.
  const apiUrlNavegador = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  return (
    <main>
      <h1 className="page-title">Conciliación con la Plataforma</h1>
      <p className="page-subtitle">
        Una fila por expediente del departamento que consta publicado en la Plataforma, aporte
        líneas al catálogo o no, con su situación y su motivo. Las mismas cifras que la hoja
        &quot;Conciliación&quot; del Excel.
      </p>
      <ConciliacionPanel apiUrl={apiUrlNavegador} />
    </main>
  );
}
