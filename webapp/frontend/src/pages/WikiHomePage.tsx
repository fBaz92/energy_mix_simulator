import { Navigate } from "react-router-dom";
import { getFirstDoc } from "@/wiki/loader";

export function WikiHomePage() {
  const first = getFirstDoc();
  if (first) {
    return <Navigate to={`/wiki/${first.slug}`} replace />;
  }
  return (
    <div className="px-6 py-10 max-w-3xl">
      <h2 className="text-xl font-semibold mb-2">Wiki vuota</h2>
      <p className="text-sm text-muted-foreground">
        Aggiungi file <code>.md</code> in{" "}
        <code>src/wiki/content/</code> per popolare questa sezione.
      </p>
    </div>
  );
}
