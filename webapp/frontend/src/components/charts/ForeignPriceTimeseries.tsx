/**
 * Multi-line plot of foreign wholesale prices across interconnections.
 *
 * Aggregated to daily means (365 points per line). Helps judge price
 * convergence between domestic and foreign markets — a proxy for
 * whether the interconnection is effectively coupling the two systems
 * or whether congestion keeps them decoupled.
 */
import { useMemo } from "react";
import { useSimulationTimeseries } from "@/api/simulations";
import { Plot } from "./Plot";
import { baseLayout, plotlyConfig } from "./plotlyConfig";
import { monthTicks, toDailyMean } from "./timeseriesUtils";

const LINE_COLORS = [
  "#0ea5e9",
  "#f97316",
  "#10b981",
  "#ef4444",
  "#8b5cf6",
  "#eab308",
];

interface ForeignPriceTimeseriesProps {
  simulationId: number;
  run: number;
  interconnectionNames: string[];
}

export function ForeignPriceTimeseries({
  simulationId,
  run,
  interconnectionNames,
}: ForeignPriceTimeseriesProps) {
  const seriesNames = useMemo(
    () => interconnectionNames.map((n) => `foreign_price_${n}`),
    [interconnectionNames],
  );

  const { data, isLoading, error } = useSimulationTimeseries(
    simulationId,
    run,
    seriesNames,
  );

  if (interconnectionNames.length === 0) {
    return (
      <div className="text-sm text-muted-foreground text-center py-8">
        No interconnections in this simulation.
      </div>
    );
  }
  if (isLoading) {
    return (
      <div className="text-sm text-muted-foreground text-center py-8">
        Loading foreign prices…
      </div>
    );
  }
  if (error || !data?.series) {
    return (
      <div className="text-sm text-muted-foreground text-center py-8">
        Foreign price time-series unavailable.
      </div>
    );
  }

  const ticks = monthTicks();
  const traces = interconnectionNames
    .map((name, i) => {
      const col = `foreign_price_${name}`;
      const raw = data.series[col];
      if (!raw) return null;
      const daily = toDailyMean(raw);
      return {
        type: "scatter" as const,
        mode: "lines" as const,
        x: Array.from({ length: daily.length }, (_, d) => d),
        y: daily,
        line: { color: LINE_COLORS[i % LINE_COLORS.length], width: 1.5 },
        name,
        hovertemplate: `<b>${name}</b><br>Day %{x}<br>%{y:.1f} EUR/MWh<extra></extra>`,
      };
    })
    .filter((t): t is NonNullable<typeof t> => t !== null);

  return (
    <Plot
      data={traces}
      layout={{
        ...baseLayout(),
        height: 300,
        xaxis: {
          ...baseLayout().xaxis,
          tickvals: ticks.tickvals,
          ticktext: ticks.ticktext,
          range: [0, 365],
        },
        yaxis: {
          ...baseLayout().yaxis,
          title: { text: "Foreign price (EUR/MWh)" },
        },
        legend: { orientation: "h", y: -0.2 },
        margin: { l: 60, r: 20, t: 20, b: 60 },
      }}
      config={plotlyConfig}
      style={{ width: "100%" }}
      useResizeHandler
    />
  );
}
