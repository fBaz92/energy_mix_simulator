/**
 * Daily-mean system inertia across the year, with the 3.5 s H_MIN floor.
 *
 * When the inertia fix activates (Phase 2 of dispatch), the trace
 * jumps up to at least ``H_MIN_SECONDS``. Dips below that line indicate
 * timesteps where no synchronous generator was available to fix the
 * constraint — a red flag for a high-renewable scenario that would
 * require batteries (synthetic inertia) or demand response.
 */
import { useSimulationTimeseries } from "@/api/simulations";
import { Plot } from "./Plot";
import { baseLayout, plotlyConfig } from "./plotlyConfig";
import { monthTicks, toDailyMean } from "./timeseriesUtils";

const H_MIN_SECONDS = 3.5;

interface InertiaTimeseriesProps {
  simulationId: number;
  run: number;
}

export function InertiaTimeseries({
  simulationId,
  run,
}: InertiaTimeseriesProps) {
  const { data, isLoading, error } = useSimulationTimeseries(
    simulationId,
    run,
    ["h_system"],
  );

  if (isLoading) {
    return (
      <div className="text-sm text-muted-foreground text-center py-8">
        Loading inertia…
      </div>
    );
  }
  if (error || !data?.series.h_system) {
    return (
      <div className="text-sm text-muted-foreground text-center py-8">
        Inertia time-series unavailable.
      </div>
    );
  }

  const daily = toDailyMean(data.series.h_system);
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
          line: { color: "#7c3aed", width: 1.5 },
          hovertemplate: "Day %{x}<br>H = %{y:.2f} s<extra></extra>",
          name: "H_system",
        },
        {
          type: "scatter",
          mode: "lines",
          x: [0, daily.length - 1],
          y: [H_MIN_SECONDS, H_MIN_SECONDS],
          line: { color: "#ef4444", dash: "dash", width: 1 },
          hoverinfo: "skip",
          name: "H_min = 3.5 s",
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
          title: { text: "Inertia (s)" },
        },
        showlegend: true,
        legend: { orientation: "h", y: -0.2 },
        margin: { l: 60, r: 20, t: 20, b: 60 },
      }}
      config={plotlyConfig}
      style={{ width: "100%" }}
      useResizeHandler
    />
  );
}
