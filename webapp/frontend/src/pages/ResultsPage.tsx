/**
 * Results dashboard for a completed simulation.
 *
 * Layout: summary stat cards at the top, then a responsive grid of Plotly
 * charts. Fetches both the lightweight SimulationSummary (for stats + status
 * check) and the heavy SimulationFullResult (for chart data).
 */
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import {
  useSimulation,
  useSimulationResults,
  useTimeseriesMetadata,
} from "@/api/simulations";
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
import { PriceSetterPie } from "@/components/charts/PriceSetterPie";
import { PriceSetterHeatmap } from "@/components/charts/PriceSetterHeatmap";
import { MarginalPriceYearCurve } from "@/components/charts/MarginalPriceYearCurve";
import { DispatchStack } from "@/components/charts/DispatchStack";
import { CurtailmentTimeseries } from "@/components/charts/CurtailmentTimeseries";
import { InertiaTimeseries } from "@/components/charts/InertiaTimeseries";
import { SocDailyProfile } from "@/components/charts/SocDailyProfile";
import { ForeignPriceTimeseries } from "@/components/charts/ForeignPriceTimeseries";
import { PriceDurationColored } from "@/components/charts/PriceDurationColored";

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

  // Selected MC run for the time-series section. Starts at 0 and is
  // bounded to ``n_runs - 1`` once the metadata is loaded.
  const [selectedRun, setSelectedRun] = useState(0);

  const {
    data: sim,
    isLoading: simLoading,
    error: simError,
  } = useSimulation(simId);
  const { data: results, isLoading: resultsLoading } =
    useSimulationResults(sim?.status === "completed" ? simId : null);
  const { data: scenario } = useScenario(sim?.scenario_id ?? null);
  const { data: tsMeta } = useTimeseriesMetadata(
    sim?.status === "completed" ? simId : null,
  );

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

          <ChartCard
            title="Price-setter by technology"
            description="Share of year each technology set the marginal price"
          >
            <PriceSetterPie
              pctByTech={results.price_setter_pct_by_tech}
            />
          </ChartCard>

          <ChartCard
            title="Price-setter pattern"
            description="% of hours each tech sets the price by month × hour-of-day"
          >
            <PriceSetterHeatmap
              byMonthHour={results.price_setter_by_month_hour}
            />
          </ChartCard>
        </div>
      )}

      {/* Time-series section — available when the Parquet payload is present */}
      {results && simId !== null && tsMeta && (
        <div className="space-y-4 pt-4">
          <div className="border-t pt-4 flex items-end justify-between gap-4 flex-wrap">
            <div>
              <h2 className="text-xl font-bold tracking-tight">
                Time-series (quarter-hour)
              </h2>
              <p className="text-sm text-muted-foreground">
                Intra-year detail for a single MC run. {tsMeta.n_runs} runs available.
              </p>
            </div>
            <div className="flex items-center gap-2 text-sm">
              <label htmlFor="run-selector" className="text-muted-foreground">
                MC run:
              </label>
              <select
                id="run-selector"
                value={selectedRun}
                onChange={(e) => setSelectedRun(parseInt(e.target.value, 10))}
                className="rounded border border-border bg-background px-2 py-1"
              >
                {Array.from({ length: tsMeta.n_runs }, (_, i) => (
                  <option key={i} value={i}>
                    Run {i}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <ChartCard
              title="Marginal price across the year"
              description="Daily-mean system marginal price"
              className="md:col-span-2"
            >
              <MarginalPriceYearCurve simulationId={simId} run={selectedRun} />
            </ChartCard>

            <ChartCard
              title="Dispatch stack"
              description="Per-generator power on a selected day (p.u.)"
              className="md:col-span-2"
            >
              <DispatchStack
                simulationId={simId}
                run={selectedRun}
                availableSeries={tsMeta.available}
              />
            </ChartCard>

            <ChartCard
              title="Price-setter duration curve"
              description="Sorted prices coloured by the tech that set them"
              className="md:col-span-2"
            >
              <PriceDurationColored
                simulationId={simId}
                run={selectedRun}
              />
            </ChartCard>

            <ChartCard
              title="Curtailment"
              description="Daily sum of curtailed energy (p.u.·h)"
            >
              <CurtailmentTimeseries simulationId={simId} run={selectedRun} />
            </ChartCard>

            <ChartCard
              title="System inertia"
              description="Daily mean H_system (with 3.5 s floor)"
            >
              <InertiaTimeseries simulationId={simId} run={selectedRun} />
            </ChartCard>

            {tsMeta.storage_names.length > 0 && (
              <ChartCard
                title="Battery SOC profile"
                description="Hourly-mean SOC across day-of-year × hour-of-day"
                className="md:col-span-2"
              >
                <SocDailyProfile
                  simulationId={simId}
                  run={selectedRun}
                  storageNames={tsMeta.storage_names}
                />
              </ChartCard>
            )}

            {tsMeta.interconnection_names.length > 0 && (
              <ChartCard
                title="Foreign prices"
                description="Daily-mean wholesale price per interconnection"
                className="md:col-span-2"
              >
                <ForeignPriceTimeseries
                  simulationId={simId}
                  run={selectedRun}
                  interconnectionNames={tsMeta.interconnection_names}
                />
              </ChartCard>
            )}
          </div>
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
