/**
 * Compare page: select 2-4 completed simulations and view them side-by-side.
 *
 * Shows:
 * - A multi-select list of completed simulations.
 * - A summary table with the key metrics per simulation.
 * - Overlaid price distribution histogram.
 * - Stacked emissions-by-tech comparison bar.
 */
import { useMemo, useState } from "react";
import { Check } from "lucide-react";
import { useSimulations, useSimulationResultsBatch } from "@/api/simulations";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ChartCard } from "@/components/charts/ChartCard";
import { PriceDistributionCompare } from "@/components/charts/PriceDistributionCompare";
import { EmissionsCompare } from "@/components/charts/EmissionsCompare";
import { cn } from "@/lib/utils";
import type { SimulationSummary } from "@/types/api";

const COMPARE_COLORS = [
  "#3b82f6",
  "#f97316",
  "#10b981",
  "#ef4444",
];
const MAX_SELECTED = 4;

function numOrDash(v: number | null | undefined, digits = 1): string {
  return typeof v === "number" ? v.toFixed(digits) : "—";
}

export function ComparePage() {
  const { data: sims } = useSimulations();
  const [selected, setSelected] = useState<number[]>([]);

  const completedSims: SimulationSummary[] = useMemo(
    () => (sims ?? []).filter((s) => s.status === "completed"),
    [sims]
  );

  const toggleSelect = (id: number) => {
    setSelected((prev) => {
      if (prev.includes(id)) return prev.filter((x) => x !== id);
      if (prev.length >= MAX_SELECTED) return prev;
      return [...prev, id];
    });
  };

  const resultQueries = useSimulationResultsBatch(selected);
  const loadingCount = resultQueries.filter((q) => q.isLoading).length;
  const allReady =
    selected.length >= 2 && resultQueries.every((q) => q.data !== undefined);

  const selectedSims = selected
    .map((id) => completedSims.find((s) => s.id === id))
    .filter((s): s is SimulationSummary => s !== undefined);

  return (
    <div className="p-8 space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Compare</h1>
        <p className="text-sm text-muted-foreground">
          Select 2–{MAX_SELECTED} completed simulations to compare side-by-side.
        </p>
      </div>

      {/* Selection list */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">
            Completed simulations ({completedSims.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          {completedSims.length === 0 ? (
            <p className="text-sm text-muted-foreground italic">
              No completed simulations yet.
            </p>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
              {completedSims.map((s) => {
                const idx = selected.indexOf(s.id);
                const isSelected = idx !== -1;
                const canAdd =
                  !isSelected && selected.length < MAX_SELECTED;
                return (
                  <button
                    key={s.id}
                    onClick={() => toggleSelect(s.id)}
                    disabled={!isSelected && !canAdd}
                    className={cn(
                      "text-left p-3 rounded-md border transition-colors relative",
                      isSelected
                        ? "border-primary bg-accent"
                        : canAdd
                        ? "border-border hover:bg-accent/50"
                        : "border-border opacity-50 cursor-not-allowed"
                    )}
                  >
                    {isSelected && (
                      <div
                        className="absolute top-2 right-2 h-2 w-2 rounded-full"
                        style={{ backgroundColor: COMPARE_COLORS[idx] }}
                      />
                    )}
                    <div className="flex items-center gap-2">
                      {isSelected && (
                        <Check className="h-3.5 w-3.5 text-primary" />
                      )}
                      <span className="text-sm font-medium truncate">
                        {s.scenario_name}
                      </span>
                    </div>
                    <div className="text-xs text-muted-foreground mt-1">
                      {s.n_runs} runs · {numOrDash(s.avg_price_mean)} EUR/MWh
                    </div>
                  </button>
                );
              })}
            </div>
          )}
          {selected.length > 0 && (
            <div className="mt-3 flex items-center justify-between">
              <p className="text-xs text-muted-foreground">
                {selected.length} selected
                {selected.length === 1 && " (need at least 2)"}
              </p>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setSelected([])}
              >
                Clear
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Summary table */}
      {selected.length >= 2 && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Summary</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left">
                    <th className="py-2 pr-4 font-medium">Metric</th>
                    {selectedSims.map((s, i) => (
                      <th key={s.id} className="py-2 pr-4 font-medium">
                        <span
                          className="inline-block h-2 w-2 rounded-full mr-2"
                          style={{ backgroundColor: COMPARE_COLORS[i] }}
                        />
                        {s.scenario_name}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  <tr className="border-b">
                    <td className="py-2 pr-4 text-muted-foreground">
                      Avg price (EUR/MWh)
                    </td>
                    {selectedSims.map((s) => (
                      <td key={s.id} className="py-2 pr-4 font-mono">
                        {numOrDash(s.avg_price_mean)}{" "}
                        <span className="text-muted-foreground text-xs">
                          ± {numOrDash(s.avg_price_std)}
                        </span>
                      </td>
                    ))}
                  </tr>
                  <tr className="border-b">
                    <td className="py-2 pr-4 text-muted-foreground">
                      Total CO₂ (Mt/yr)
                    </td>
                    {selectedSims.map((s) => (
                      <td key={s.id} className="py-2 pr-4 font-mono">
                        {numOrDash(s.total_emissions_mean_mt)}
                      </td>
                    ))}
                  </tr>
                  <tr className="border-b">
                    <td className="py-2 pr-4 text-muted-foreground">
                      Carbon intensity (gCO₂/kWh)
                    </td>
                    {selectedSims.map((s) => (
                      <td key={s.id} className="py-2 pr-4 font-mono">
                        {numOrDash(s.carbon_intensity_mean, 0)}
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <td className="py-2 pr-4 text-muted-foreground">
                      Mean inertia (s)
                    </td>
                    {selectedSims.map((s) => (
                      <td key={s.id} className="py-2 pr-4 font-mono">
                        {numOrDash(s.mean_inertia, 2)}
                      </td>
                    ))}
                  </tr>
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Charts */}
      {loadingCount > 0 && (
        <p className="text-sm text-muted-foreground">
          Loading {loadingCount} result{loadingCount > 1 ? "s" : ""}...
        </p>
      )}
      {allReady && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <ChartCard
            title="Price distribution"
            description="Overlaid histograms across MC runs"
          >
            <PriceDistributionCompare
              series={selectedSims.map((s, i) => ({
                label: s.scenario_name,
                values: resultQueries[i].data?.avg_price ?? [],
                color: COMPARE_COLORS[i],
              }))}
            />
          </ChartCard>

          <ChartCard
            title="Emissions by technology"
            description="Stacked mean emissions per scenario"
          >
            <EmissionsCompare
              series={selectedSims.map((s, i) => ({
                label: s.scenario_name,
                emissionsByTech:
                  resultQueries[i].data?.emissions_by_tech ?? {},
              }))}
            />
          </ChartCard>
        </div>
      )}
    </div>
  );
}
