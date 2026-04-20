/**
 * Sweep detail page — poll the status and render the result chart
 * once the grid completes.
 *
 * Uses :mod:`Sweep1DCurve` for ``sweep_type === '1d'`` and
 * :mod:`Sweep2DHeatmap` otherwise. While the sweep is pending or
 * running, a progress bar is shown.
 */
import { Link, useParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { useSweep, useSweepResults } from "@/api/sweeps";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ChartCard } from "@/components/charts/ChartCard";
import { Sweep1DCurve } from "@/components/charts/Sweep1DCurve";
import { Sweep2DHeatmap } from "@/components/charts/Sweep2DHeatmap";

export function SweepDetailPage() {
  const { id } = useParams<{ id: string }>();
  const sweepId = id ? parseInt(id) : null;

  const { data: sweep, isLoading, error } = useSweep(sweepId);
  const { data: results } = useSweepResults(
    sweep?.status === "completed" ? sweepId : null,
  );

  if (isLoading) {
    return <div className="p-8 text-sm text-muted-foreground">Loading…</div>;
  }
  if (error || !sweep) {
    return (
      <div className="p-8 space-y-4 max-w-2xl">
        <Button asChild variant="ghost" size="sm">
          <Link to="/sweeps">
            <ArrowLeft className="h-4 w-4 mr-1" />
            Back to sweeps
          </Link>
        </Button>
        <Card>
          <CardContent className="py-12 text-center space-y-2">
            <p className="text-sm text-destructive font-medium">
              Sweep not found
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-8 space-y-6">
      <div>
        <Button asChild variant="ghost" size="sm" className="-ml-2 mb-2">
          <Link to="/sweeps">
            <ArrowLeft className="h-4 w-4 mr-1" />
            Back to sweeps
          </Link>
        </Button>
        <h1 className="text-2xl font-bold tracking-tight">{sweep.name}</h1>
        <p className="text-sm text-muted-foreground">
          {sweep.scenario_name} · {sweep.sweep_type.toUpperCase()} sweep ·{" "}
          {sweep.parameter_a}
          {sweep.sweep_type === "2d" && sweep.parameter_b
            ? ` × ${sweep.parameter_b}`
            : ""}{" "}
          · {sweep.progress_total} grid points × {sweep.n_runs_per_point} MC
          runs each
        </p>
      </div>

      {(sweep.status === "pending" || sweep.status === "running") && (
        <Card>
          <CardContent className="py-6 space-y-2">
            <p className="text-sm">
              Sweep is <strong>{sweep.status}</strong>…
            </p>
            <div className="text-xs text-muted-foreground">
              {sweep.progress_current} / {sweep.progress_total} grid points
              completed
            </div>
            <div className="h-2 bg-muted rounded-full overflow-hidden">
              <div
                className="h-full bg-blue-500 transition-all"
                style={{
                  width: `${(sweep.progress_current / Math.max(sweep.progress_total, 1)) * 100}%`,
                }}
              />
            </div>
          </CardContent>
        </Card>
      )}

      {sweep.status === "failed" && (
        <Card>
          <CardContent className="py-6 space-y-2">
            <p className="text-sm text-destructive font-medium">
              Sweep failed
            </p>
            {sweep.error_message && (
              <pre className="text-xs text-destructive bg-destructive/10 p-2 rounded overflow-x-auto max-h-64">
                {sweep.error_message}
              </pre>
            )}
          </CardContent>
        </Card>
      )}

      {sweep.status === "completed" && results && (
        <ChartCard
          title={sweep.sweep_type === "1d" ? "Sensitivity curve" : "Sensitivity heatmap"}
          description={
            sweep.sweep_type === "1d"
              ? "Metric vs parameter A across grid points"
              : "Metric heatmap over parameter A × B"
          }
        >
          {sweep.sweep_type === "1d" ? (
            <Sweep1DCurve results={results} />
          ) : (
            <Sweep2DHeatmap results={results} />
          )}
        </ChartCard>
      )}
    </div>
  );
}
