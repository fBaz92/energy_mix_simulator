/**
 * Daily curtailment area plot across the year.
 *
 * Curtailment is an extensive quantity (energy), so we plot daily sums
 * in p.u.·quarter-hours (equivalent to p.u.·hours × 0.25). The seasonal
 * pattern highlights spring/summer inertia-driven curtailment spikes in
 * high-renewable scenarios.
 */
import { useSimulationTimeseries } from "@/api/simulations";
import { Plot } from "./Plot";
import { baseLayout, plotlyConfig } from "./plotlyConfig";
import { monthTicks, toDailySum } from "./timeseriesUtils";

interface CurtailmentTimeseriesProps {
  simulationId: number;
  run: number;
}

export function CurtailmentTimeseries({
  simulationId,
  run,
}: CurtailmentTimeseriesProps) {
  const { data, isLoading, error } = useSimulationTimeseries(
    simulationId,
    run,
    ["curtailment"],
  );

  if (isLoading) {
    return (
      <div className="text-sm text-muted-foreground text-center py-8">
        Loading curtailment…
      </div>
    );
  }
  if (error || !data?.series.curtailment) {
    return (
      <div className="text-sm text-muted-foreground text-center py-8">
        Curtailment time-series unavailable.
      </div>
    );
  }

  // Daily sum in p.u.·quarter-hours. Multiplied by 0.25 to express in
  // p.u.·hours, a more intuitive unit (and directly comparable to the
  // ``total_curtailment`` scalar in the MC summary).
  const daily = toDailySum(data.series.curtailment).map((v) => v * 0.25);
  const ticks = monthTicks();
  const x = Array.from({ length: daily.length }, (_, i) => i);

  return (
    <Plot
      data={[
        {
          type: "scatter",
          mode: "lines",
          x,
          y: daily,
          fill: "tozeroy",
          line: { color: "#ef4444", width: 1 },
          fillcolor: "rgba(239,68,68,0.2)",
          hovertemplate:
            "Day %{x}<br>%{y:.3f} p.u.·h curtailed<extra></extra>",
        },
      ]}
      layout={{
        ...baseLayout(),
        height: 260,
        xaxis: {
          ...baseLayout().xaxis,
          tickvals: ticks.tickvals,
          ticktext: ticks.ticktext,
          range: [0, daily.length - 1],
        },
        yaxis: {
          ...baseLayout().yaxis,
          title: { text: "p.u.·h / day" },
          rangemode: "tozero",
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
