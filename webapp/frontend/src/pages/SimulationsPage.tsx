/**
 * Simulations list page.
 * Shows all past and in-progress simulations with summary stats.
 * Click to navigate to the results page.
 */
import { Link } from "react-router-dom";
import { Trash2 } from "lucide-react";
import { useSimulations, useDeleteSimulation } from "@/api/simulations";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

function statusBadge(status: string) {
  const base = "px-2 py-0.5 rounded-full text-xs font-medium";
  switch (status) {
    case "completed":
      return `${base} bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400`;
    case "running":
      return `${base} bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400`;
    case "pending":
      return `${base} bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400`;
    case "failed":
      return `${base} bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400`;
    default:
      return `${base} bg-muted text-muted-foreground`;
  }
}

export function SimulationsPage() {
  const { data: sims, isLoading } = useSimulations();
  const deleteMutation = useDeleteSimulation();

  const handleDelete = (id: number) => {
    if (confirm("Delete this simulation and its results?")) {
      deleteMutation.mutate(id);
    }
  };

  return (
    <div className="p-8 space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Simulations</h1>
        <p className="text-sm text-muted-foreground">
          All Monte Carlo simulation runs, past and current.
        </p>
      </div>

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading...</p>
      ) : sims && sims.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-sm text-muted-foreground">
              No simulations yet. Launch one from the Scenarios page.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {sims?.map((s) => (
            <Card key={s.id}>
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between">
                  <div>
                    <CardTitle className="text-base flex items-center gap-3">
                      {s.scenario_name || `Simulation #${s.id}`}
                      <span className={statusBadge(s.status)}>{s.status}</span>
                    </CardTitle>
                    <CardDescription>
                      {s.n_runs} MC runs · started{" "}
                      {s.started_at
                        ? new Date(s.started_at).toLocaleString()
                        : "—"}
                    </CardDescription>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      size="icon"
                      variant="ghost"
                      onClick={() => handleDelete(s.id)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                    <Button asChild size="sm" variant="outline">
                      <Link
                        to={
                          s.status === "completed"
                            ? `/results/${s.id}`
                            : `/simulations/${s.id}`
                        }
                      >
                        Open
                      </Link>
                    </Button>
                  </div>
                </div>
              </CardHeader>
              {s.status === "completed" && (
                <CardContent className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                  <div>
                    <div className="text-muted-foreground text-xs">
                      Avg price
                    </div>
                    <div className="font-semibold">
                      {s.avg_price_mean?.toFixed(1)} ± {s.avg_price_std?.toFixed(1)}{" "}
                      <span className="text-xs text-muted-foreground">
                        EUR/MWh
                      </span>
                    </div>
                  </div>
                  <div>
                    <div className="text-muted-foreground text-xs">
                      Emissions
                    </div>
                    <div className="font-semibold">
                      {s.total_emissions_mean_mt?.toFixed(1)}{" "}
                      <span className="text-xs text-muted-foreground">Mt/y</span>
                    </div>
                  </div>
                  <div>
                    <div className="text-muted-foreground text-xs">
                      CO₂ intensity
                    </div>
                    <div className="font-semibold">
                      {s.carbon_intensity_mean?.toFixed(0)}{" "}
                      <span className="text-xs text-muted-foreground">
                        gCO₂/kWh
                      </span>
                    </div>
                  </div>
                  <div>
                    <div className="text-muted-foreground text-xs">
                      Mean inertia
                    </div>
                    <div className="font-semibold">
                      {s.mean_inertia?.toFixed(2)}{" "}
                      <span className="text-xs text-muted-foreground">s</span>
                    </div>
                  </div>
                </CardContent>
              )}
              {s.status === "failed" && s.error_message && (
                <CardContent>
                  <pre className="text-xs text-destructive bg-destructive/10 p-2 rounded overflow-x-auto max-h-32">
                    {s.error_message.split("\n").slice(-5).join("\n")}
                  </pre>
                </CardContent>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
