/**
 * Horizontal bar of deaths per TWh by energy source (OWID).
 *
 * The backend parser already sorts rows descending, so we render as-is.
 * Log-scale x-axis is necessary because the range spans >1000x — coal
 * at ~25 deaths/TWh vs. solar/wind at ~0.02.
 */
import { Plot } from "./Plot";
import { baseLayout, colorFor, plotlyConfig } from "./plotlyConfig";
import type { DeathsPerTwhRow } from "@/types/api";

interface DeathsPerTwhBarProps {
  rows: DeathsPerTwhRow[];
}

export function DeathsPerTwhBar({ rows }: DeathsPerTwhBarProps) {
  if (!rows.length) {
    return (
      <div className="text-sm text-muted-foreground text-center py-8">
        Dataset loading...
      </div>
    );
  }
  const data = [...rows].sort((a, b) => a.deaths_per_twh - b.deaths_per_twh);
  return (
    <Plot
      data={[
        {
          type: "bar",
          orientation: "h",
          x: data.map((r) => r.deaths_per_twh),
          y: data.map((r) => r.source),
          marker: {
            color: data.map((r) => colorFor(r.source.toLowerCase())),
          },
          text: data.map((r) => r.deaths_per_twh.toFixed(2)),
          textposition: "outside",
          hovertemplate:
            "<b>%{y}</b><br>%{x:.3f} deaths/TWh<extra></extra>",
        },
      ]}
      layout={{
        ...baseLayout(),
        height: 320,
        xaxis: {
          ...baseLayout().xaxis,
          title: { text: "Deaths per TWh (log scale)" },
          type: "log",
        },
        yaxis: { ...baseLayout().yaxis, automargin: true },
        margin: { l: 90, r: 60, t: 20, b: 50 },
      }}
      config={plotlyConfig}
      style={{ width: "100%" }}
      useResizeHandler
    />
  );
}
