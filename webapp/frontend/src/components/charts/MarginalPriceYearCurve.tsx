/**
 * Full-year marginal price curve for a single MC run.
 *
 * The raw quarter-hour series (35 040 points) would render but is slow
 * to interact with, so the trace is downsampled to daily means (365
 * points). The shape remains faithful — intra-day noise averages out
 * and the seasonal envelope (winter peaks, summer solar dips) is what
 * the user typically wants to see here.
 */
import { useSimulationTimeseries } from "@/api/simulations";
import { Plot } from "./Plot";
import { baseLayout, plotlyConfig } from "./plotlyConfig";
import { monthTicks, toDailyMean } from "./timeseriesUtils";

interface MarginalPriceYearCurveProps {
  simulationId: number;
  run: number;
}

export function MarginalPriceYearCurve({
  simulationId,
  run,
}: MarginalPriceYearCurveProps) {
  const { data, isLoading, error } = useSimulationTimeseries(
    simulationId,
    run,
    ["marginal_price"],
  );

  if (isLoading) {
    return (
      <div className="text-sm text-muted-foreground text-center py-8">
        Loading time-series…
      </div>
    );
  }
  if (error || !data?.series.marginal_price) {
    return (
      <div className="text-sm text-muted-foreground text-center py-8">
        Time-series unavailable for this simulation.
      </div>
    );
  }

  const daily = toDailyMean(data.series.marginal_price);
  const ticks = monthTicks();
  const x = Array.from({ length: daily.length }, (_, i) => i);

  return (
    <Plot
      data={[
        {
          type: "scattergl",
          mode: "lines",
          x,
          y: daily,
          line: { color: "#0f172a", width: 1.5 },
          hovertemplate:
            "Day %{x}<br>%{y:.1f} EUR/MWh (daily mean)<extra></extra>",
          name: "Daily mean",
        },
      ]}
      layout={{
        ...baseLayout(),
        height: 300,
        xaxis: {
          ...baseLayout().xaxis,
          tickvals: ticks.tickvals,
          ticktext: ticks.ticktext,
          range: [0, daily.length - 1],
        },
        yaxis: {
          ...baseLayout().yaxis,
          title: { text: "EUR / MWh" },
        },
        showlegend: false,
        margin: { l: 60, r: 20, t: 20, b: 40 },
      }}
      config={plotlyConfig}
      style={{ width: "100%" }}
      useResizeHandler
    />
  );
}
