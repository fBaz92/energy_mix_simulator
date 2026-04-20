/**
 * Stacked-area dispatch for a single day.
 *
 * Shows the quarter-hour dispatch of every generator on a user-selected
 * day, stacked on top of the load so the user can see who contributed
 * what. Day-level granularity avoids the 35 040-point Plotly
 * performance cliff while preserving intra-day dynamics (peak ramp-up,
 * solar midday dip, evening gas peaker).
 *
 * Data contract: one ``power_<tech>`` column per generator present in
 * the Parquet file. We ask the API for all of them via
 * ``available.filter(startsWith('power_'))`` so the chart self-adapts
 * to scenarios with extra generators (e.g. coal enabled) without code
 * changes.
 */
import { useMemo, useState } from "react";
import { useSimulationTimeseries } from "@/api/simulations";
import { Plot } from "./Plot";
import { baseLayout, colorFor, plotlyConfig } from "./plotlyConfig";
import { dayHourLabels, sliceDay } from "./timeseriesUtils";

interface DispatchStackProps {
  simulationId: number;
  run: number;
  /** Mix of generators (used to enumerate series to fetch). */
  availableSeries: string[] | undefined;
}

export function DispatchStack({
  simulationId,
  run,
  availableSeries,
}: DispatchStackProps) {
  // Day selector — default to a mid-January day for a winter view, but
  // the user is free to scrub through the year.
  const [day, setDay] = useState(15);

  // Enumerate ``power_*`` columns available in the file.
  const powerSeries = useMemo(
    () =>
      (availableSeries ?? [])
        .filter((s) => s.startsWith("power_"))
        .sort(),
    [availableSeries],
  );

  const { data, isLoading, error } = useSimulationTimeseries(
    simulationId,
    run,
    powerSeries,
  );

  if (!availableSeries) {
    return (
      <div className="text-sm text-muted-foreground text-center py-8">
        Loading column list…
      </div>
    );
  }
  if (powerSeries.length === 0) {
    return (
      <div className="text-sm text-muted-foreground text-center py-8">
        No per-generator dispatch columns in this simulation.
      </div>
    );
  }
  if (isLoading) {
    return (
      <div className="text-sm text-muted-foreground text-center py-8">
        Loading dispatch…
      </div>
    );
  }
  if (error || !data?.series) {
    return (
      <div className="text-sm text-muted-foreground text-center py-8">
        Dispatch data unavailable for this simulation.
      </div>
    );
  }

  const xLabels = dayHourLabels();
  const traces = powerSeries.map((colName) => {
    const values = data.series[colName] ?? [];
    const tech = colName.replace(/^power_/, "");
    return {
      type: "scatter" as const,
      mode: "lines" as const,
      x: xLabels,
      y: sliceDay(values, day),
      stackgroup: "one",
      name: tech,
      line: { width: 0.5, color: colorFor(tech) },
      fillcolor: colorFor(tech),
      hovertemplate: `<b>${tech}</b><br>%{x}<br>%{y:.3f} p.u.<extra></extra>`,
    };
  });

  return (
    <div>
      <div className="mb-3 flex items-center gap-2 text-sm">
        <label htmlFor="dispatch-day" className="text-muted-foreground">
          Day of year:
        </label>
        <input
          id="dispatch-day"
          type="range"
          min={0}
          max={364}
          value={day}
          onChange={(e) => setDay(parseInt(e.target.value, 10))}
          className="flex-1"
        />
        <span className="tabular-nums text-xs w-12 text-right">{day + 1}</span>
      </div>
      <Plot
        data={traces}
        layout={{
          ...baseLayout(),
          height: 320,
          xaxis: {
            ...baseLayout().xaxis,
            title: { text: "Hour of day" },
            tickmode: "array",
            tickvals: [0, 24, 48, 72, 95].map((i) => xLabels[i]),
            ticktext: ["00:00", "06:00", "12:00", "18:00", "23:45"],
          },
          yaxis: {
            ...baseLayout().yaxis,
            title: { text: "Dispatch (p.u.)" },
          },
          legend: {
            orientation: "h",
            y: -0.2,
          },
          margin: { l: 60, r: 20, t: 20, b: 60 },
        }}
        config={plotlyConfig}
        style={{ width: "100%" }}
        useResizeHandler
      />
    </div>
  );
}
