/**
 * Results dashboard for a completed simulation.
 *
 * Layout: summary stat cards at the top, then a responsive grid of Plotly
 * charts. Fetches both the lightweight SimulationSummary (for stats + status
 * check) and the heavy SimulationFullResult (for chart data).
 */
import { Link, useParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { useSimulation, useSimulationResults } from "@/api/simulations";
import { useScenario } from "@/api/scenarios";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ChartCard } from "@/components/charts/ChartCard";
import { PriceDistribution } from "@/components/charts/PriceDistribution";
import { MonthlyPriceBoxplot } from "@/components/charts/MonthlyPriceBoxplot";
import { EmissionsBreakdown } from "@/components/charts/EmissionsBreakdown";
import { GenerationMixPie } from "@/components/charts/GenerationMixPie";
import { CarbonIntensityScatter } from "@/components/charts/CarbonIntensityScatter";
import { InertiaDistribution } from "@/components/charts/InertiaDistribution";

function StatCard({
  label,
  value,
  unit,
  sub,
}: {
  label: string;
  value: string;
  unit: string;
  sub?: string;
}) {
  return (
    <Card>
      <CardContent className="pt-6">
        <div className="text-xs text-muted-foreground">{label}</div>
        <div className="text-2xl font-bold mt-1 tracking-tight">{value}</div>
        <div className="text-xs text-muted-foreground">
          {unit}
          {sub && <span className="ml-1 italic">({sub})</span>}
        </div>
      </CardContent>
    </Card>
  );
}

export function ResultsPage() {
  const { id } = useParams<{ id: string }>();
  const simId = id ? parseInt(id) : null;

  const { data: sim } = useSimulation(simId);
  const { data: results, isLoading: resultsLoading } =
    useSimulationResults(sim?.status === "completed" ? simId : null);
  const { data: scenario } = useScenario(sim?.scenario_id ?? null);

  if (!sim) {
    return <div className="p-8 text-sm text-muted-foreground">Loading...</div>;
  }

  if (sim.status !== "completed") {
    return (
      <div className="p-8 space-y-4 max-w-2xl">
        <Button asChild variant="ghost" size="sm">
          <Link to="/simulations">
            <ArrowLeft className="h-4 w-4 mr-1" />
            Back to simulations
          </Link>
        </Button>
        <Card>
          <CardContent className="py-12 text-center space-y-2">
            <p className="text-sm text-muted-foreground">
              Simulation is <strong>{sim.status}</strong>.
            </p>
            <p className="text-xs text-muted-foreground">
              Results will be available once the simulation completes.
            </p>
            <Button asChild variant="outline" size="sm" className="mt-4">
              <Link to={`/simulations/${sim.id}`}>View progress</Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-8 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <Button asChild variant="ghost" size="sm" className="-ml-2 mb-2">
            <Link to="/simulations">
              <ArrowLeft className="h-4 w-4 mr-1" />
              Back to simulations
            </Link>
          </Button>
          <h1 className="text-2xl font-bold tracking-tight">
            {sim.scenario_name}
          </h1>
          <p className="text-sm text-muted-foreground">
            {sim.n_runs} MC runs · completed{" "}
            {sim.completed_at
              ? new Date(sim.completed_at).toLocaleString()
              : "—"}
          </p>
        </div>
      </div>

      {/* Summary stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          label="Average price"
          value={sim.avg_price_mean?.toFixed(1) ?? "—"}
          unit="EUR/MWh"
          sub={`± ${sim.avg_price_std?.toFixed(1) ?? "—"}`}
        />
        <StatCard
          label="Total CO₂"
          value={sim.total_emissions_mean_mt?.toFixed(1) ?? "—"}
          unit="Mt / year"
        />
        <StatCard
          label="Carbon intensity"
          value={sim.carbon_intensity_mean?.toFixed(0) ?? "—"}
          unit="gCO₂ / kWh"
        />
        <StatCard
          label="Mean inertia"
          value={sim.mean_inertia?.toFixed(2) ?? "—"}
          unit="seconds"
        />
      </div>

      {/* Charts */}
      {resultsLoading || !results ? (
        <p className="text-sm text-muted-foreground">Loading chart data...</p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <ChartCard
            title="Price distribution"
            description="Annual electricity price across MC runs"
          >
            <PriceDistribution avgPrice={results.avg_price} />
          </ChartCard>

          <ChartCard
            title="Monthly prices"
            description="Distribution of monthly averages across runs"
          >
            <MonthlyPriceBoxplot monthlyPrices={results.monthly_prices} />
          </ChartCard>

          <ChartCard
            title="Emissions by technology"
            description="Mean annual CO₂ per technology"
          >
            <EmissionsBreakdown
              emissionsByTech={results.emissions_by_tech}
            />
          </ChartCard>

          {scenario && (
            <ChartCard
              title="Installed capacity"
              description="Generation mix by technology (GW)"
            >
              <GenerationMixPie mixConfig={scenario.config.mix_config} />
            </ChartCard>
          )}

          <ChartCard
            title="Price vs carbon intensity"
            description="Each point is one MC run"
          >
            <CarbonIntensityScatter
              avgPrice={results.avg_price}
              carbonIntensity={results.carbon_intensity}
            />
          </ChartCard>

          <ChartCard
            title="System inertia"
            description="Distribution across MC runs (H_min = 3.5s)"
          >
            <InertiaDistribution avgInertia={results.avg_inertia} />
          </ChartCard>
        </div>
      )}
    </div>
  );
}
