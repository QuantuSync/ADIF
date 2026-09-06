import CatalogoPanel from "./CatalogoPanel";

export default function PaginaCatalogo() {
  // CONTEXTO.md sección 9.1: la web solo llama a la API por HTTP, nunca toca
  // la base de datos ni un PDF directamente — por eso esta página server no
  // hace fetch inicial (a diferencia de "/"), todo el filtrado vive en el
  // cliente contra la API.
  const apiUrlNavegador = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  return (
    <main>
      <h1 className="page-title">Catálogo de materiales</h1>
      <p className="page-subtitle">Un catálogo único, acumulativo, para todos los expedientes.</p>
      <CatalogoPanel apiUrl={apiUrlNavegador} />
    </main>
  );
}
