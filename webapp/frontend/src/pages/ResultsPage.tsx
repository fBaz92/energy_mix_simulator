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
import { InterconnectionFlows } from "@/components/charts/InterconnectionFlows";
import { ImportExportHours } from "@/components/charts/ImportExportHours";
import { EconomicBenefitMonthly } from "@/components/charts/EconomicBenefitMonthly";
import { Co2BenefitMonthly } from "@/components/charts/Co2BenefitMonthly";
import { StorageSocMonthly } from "@/components/charts/StorageSocMonthly";
import { StorageStats } from "@/components/charts/StorageStats";

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

  const {
    data: sim,
    isLoading: simLoading,
    error: simError,
  } = useSimulation(simId);
  const { data: results, isLoading: resultsLoading } =
    useSimulationResults(sim?.status === "completed" ? simId : null);
  const { data: scenario } = useScenario(sim?.scenario_id ?? null);

  if (simLoading) {
    return <div className="p-8 text-sm text-muted-foreground">Loading...</div>;
  }

  if (simError || !sim) {
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
            <p className="text-sm text-destructive font-medium">
              Simulation not found
            </p>
            <p className="text-xs text-muted-foreground">
              Simulation #{simId} does not exist or has been deleted.
            </p>
          </CardContent>
        </Card>
      </div>
    );
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

      {/* Interconnection section — shown only when links are enabled */}
      {results && results.interconnection_names.length > 0 && (
        <div className="space-y-4 pt-4">
          <div className="border-t pt-4">
            <h2 className="text-xl font-bold tracking-tight">
              Cross-border exchanges
            </h2>
            <p className="text-sm text-muted-foreground">
              {results.interconnection_names.length} interconnections active
            </p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <ChartCard
              title="Flow summary"
              description="Gross import / export / net, with foreign price and NTC saturation"
              className="md:col-span-2"
            >
              <InterconnectionFlows
                names={results.interconnection_names}
                importGrossTwh={results.import_gross_twh}
                exportGrossTwh={results.export_gross_twh}
                netImportTwh={results.net_import_twh}
                foreignPriceMean={results.foreign_price_mean}
                ntcImportSaturationPct={results.ntc_import_saturation_pct}
              />
            </ChartCard>
            <ChartCard
              title="Import / export hours"
              description="Time each link spends in each flow state"
            >
              <ImportExportHours
                names={results.interconnection_names}
                importHours={results.import_hours}
                exportHours={results.export_hours}
              />
            </ChartCard>
            <ChartCard
              title="Economic benefit"
              description="Monthly congestion-rent contribution per link"
            >
              <EconomicBenefitMonthly
                names={results.interconnection_names}
                monthlyBenefitEur={results.economic_benefit_monthly_eur}
              />
            </ChartCard>
            <ChartCard
              title="CO₂ benefit"
              description="Monthly signed CO₂ impact per link (+ = avoided)"
              className="md:col-span-2"
            >
              <Co2BenefitMonthly
                names={results.interconnection_names}
                monthlyCo2Tons={results.co2_benefit_monthly_tons}
              />
            </ChartCard>
          </div>
        </div>
      )}

      {/* Storage section — shown only when storage units are enabled */}
      {results && results.storage_names.length > 0 && (
        <div className="space-y-4 pt-4">
          <div className="border-t pt-4">
            <h2 className="text-xl font-bold tracking-tight">
              Battery storage
            </h2>
            <p className="text-sm text-muted-foreground">
              {results.storage_names.length} storage unit
              {results.storage_names.length > 1 ? "s" : ""} active
            </p>
          </div>
          <ChartCard title="Per-unit statistics">
            <StorageStats
              names={results.storage_names}
              revenueEur={results.storage_revenue_eur}
              equivalentCycles={results.storage_equivalent_cycles}
              avgSoc={results.storage_avg_soc}
              energyCycledMwh={results.storage_energy_cycled_mwh}
            />
          </ChartCard>
          <ChartCard
            title="Monthly average SOC"
            description="Seasonal pattern of state-of-charge"
          >
            <StorageSocMonthly
              names={results.storage_names}
              monthlyAvgSoc={results.storage_monthly_avg_soc}
            />
          </ChartCard>
        </div>
      )}
    </div>
  );
}
