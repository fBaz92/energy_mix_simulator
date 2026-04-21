/**
 * Top-level application shell: sidebar nav + main content area.
 * Renders the active route via react-router Outlet.
 */
import { NavLink, Outlet } from "react-router-dom";
import {
  BookOpen,
  Database,
  FlaskConical,
  GitCompare,
  LayoutDashboard,
  TrendingUp,
  Zap,
} from "lucide-react";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { to: "/scenarios", label: "Scenarios", icon: FlaskConical },
  { to: "/simulations", label: "Simulations", icon: LayoutDashboard },
  { to: "/sweeps", label: "Sweeps", icon: TrendingUp },
  { to: "/compare", label: "Compare", icon: GitCompare },
  { to: "/data-analysis", label: "Data Analysis", icon: Database },
  { to: "/wiki", label: "Wiki", icon: BookOpen },
] as const;

export function AppShell() {
  return (
    <div className="min-h-screen flex bg-background text-foreground">
      {/* Sidebar */}
      <aside className="w-60 border-r bg-card flex flex-col">
        <div className="h-14 flex items-center gap-2 px-4 border-b">
          <Zap className="h-5 w-5 text-primary" />
          <span className="font-semibold tracking-tight">Energy Mix Sim</span>
        </div>
        <nav className="flex-1 p-2 space-y-1">
          {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-accent text-accent-foreground"
                    : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                )
              }
            >
              <Icon className="h-4 w-4" />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="p-3 border-t text-xs text-muted-foreground">
          Monte Carlo simulator for electricity mix analysis
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}
