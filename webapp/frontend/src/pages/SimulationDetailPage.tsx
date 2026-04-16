/**
 * Simulation detail / progress page.
 *
 * Shown immediately after launching a simulation. Polls the status
 * endpoint every 500ms until completion, then shows summary stats
 * and a link to the results dashboard (Phase 4).
 */
import { Link, useParams } from "react-router-dom";
import { useSimulation } from "@/api/simulations";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function SimulationDetailPage() {
  const { id } = useParams<{ id: string }>();
  const simId = id ? parseInt(id) : null;
  const { data: sim, isLoading } = useSimulation(simId);

  if (isLoading || !sim) {
    return <div className="p-8">Loading simulation...</div>;
  }

  const isRunning = sim.status === "pending" || sim.status === "running";
  const progressPct = Math.round(sim.progress * 100);

  return (
    <div className="p-8 space-y-6 max-w-4xl">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">
          {sim.scenario_name || `Simulation #${sim.id}`}
        </h1>
        <p className="text-sm text-muted-foreground">
          Status: <span className="font-medium">{sim.status}</span> · {sim.n_runs}{" "}
          MC runs
        </p>
      </div>

      {/* Progress bar while running */}
      {isRunning && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Running simulation</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <div className="w-full bg-muted rounded-full h-2 overflow-hidden">
              <div
                className="bg-primary h-full transition-all duration-200"
                style={{ width: `${progressPct}%` }}
              />
            </div>
            <p className="text-sm text-muted-foreground">
              {progressPct}% complete
            </p>
          </CardContent>
        </Card>
      )}

      {/* Failed state */}
      {sim.status === "failed" && (
        <Card className="border-destructive">
          <CardHeader>
            <CardTitle className="text-base text-destructive">
              Simulation failed
            </CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="text-xs bg-destructive/10 p-3 rounded overflow-x-auto max-h-64">
              {sim.error_message}
            </pre>
          </CardContent>
        </Card>
      )}

      {/* Summary stats when completed */}
      {sim.status === "completed" && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card>
            <CardContent className="pt-6">
              <div className="text-xs text-muted-foreground">
                Average price
              </div>
              <div className="text-2xl font-bold mt-1">
                {sim.avg_price_mean?.toFixed(1)}
              </div>
              <div className="text-xs text-muted-foreground">
                ± {sim.avg_price_std?.toFixed(1)} EUR/MWh
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-xs text-muted-foreground">Total CO₂</div>
              <div className="text-2xl font-bold mt-1">
                {sim.total_emissions_mean_mt?.toFixed(1)}
              </div>
              <div className="text-xs text-muted-foreground">Mt/year</div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-xs text-muted-foreground">
                Carbon intensity
              </div>
              <div className="text-2xl font-bold mt-1">
                {sim.carbon_intensity_mean?.toFixed(0)}
              </div>
              <div className="text-xs text-muted-foreground">gCO₂/kWh</div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-xs text-muted-foreground">
                Mean inertia
              </div>
              <div className="text-2xl font-bold mt-1">
                {sim.mean_inertia?.toFixed(2)}
              </div>
              <div className="text-xs text-muted-foreground">seconds</div>
            </CardContent>
          </Card>
        </div>
      )}

      {sim.status === "completed" && (
        <Button asChild>
          <Link to={`/results/${sim.id}`}>Open full results dashboard →</Link>
        </Button>
      )}
    </div>
  );
}
