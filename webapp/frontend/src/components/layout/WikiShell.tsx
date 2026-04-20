import { NavLink, Outlet } from "react-router-dom";
import { wikiIndex } from "@/wiki/loader";
import { cn } from "@/lib/utils";

export function WikiShell() {
  return (
    <div className="flex flex-col h-full">
      <header className="border-b bg-card">
        <div className="px-6 pt-4 pb-2">
          <h1 className="text-lg font-semibold tracking-tight">Wiki</h1>
          <p className="text-xs text-muted-foreground">
            Teoria, modelli e scelte di progettazione del simulatore
          </p>
        </div>
        <nav className="px-6 pb-3 flex flex-wrap gap-x-6 gap-y-2 text-sm">
          {wikiIndex.map((cat) => (
            <div key={cat.name} className="flex items-baseline gap-3">
              <span className="text-xs uppercase tracking-wider text-muted-foreground font-medium">
                {cat.name}
              </span>
              <div className="flex flex-wrap gap-1">
                {cat.docs.map((doc) => (
                  <NavLink
                    key={doc.slug}
                    to={`/wiki/${doc.slug}`}
                    className={({ isActive }) =>
                      cn(
                        "rounded-md px-2 py-1 text-sm transition-colors",
                        isActive
                          ? "bg-accent text-accent-foreground font-medium"
                          : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                      )
                    }
                  >
                    {doc.title}
                  </NavLink>
                ))}
              </div>
            </div>
          ))}
        </nav>
      </header>
      <div className="flex-1 overflow-auto">
        <Outlet />
      </div>
    </div>
  );
}
