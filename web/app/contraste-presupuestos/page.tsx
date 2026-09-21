import ContrastePanel from "./ContrastePanel";

export default function PaginaContrastePresupuestos() {
  // CONTEXTO.md sección 9.1: la web solo llama a la API por HTTP.
  const apiUrlNavegador = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  return (
    <main>
      <h1 className="page-title">Contraste de presupuestos</h1>
      <p className="page-subtitle">
        Una fila por lote: la suma de cantidad × precio de sus filas del catálogo contra el
        presupuesto de licitación que se publica para ese lote, siempre con la cifra equivalente.
        Las mismas cifras que la hoja &quot;Contraste de presupuestos&quot; del Excel.
      </p>
      <ContrastePanel apiUrl={apiUrlNavegador} />
    </main>
  );
}
