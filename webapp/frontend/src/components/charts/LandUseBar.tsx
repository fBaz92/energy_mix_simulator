/**
 * Horizontal bar chart of land use per TWh by source, with p5-p95
 * error bars (van Zalk & Behrens 2018).
 *
 * Log-scale x-axis because the range spans 4 orders of magnitude —
 * nuclear at ~0.1 m2/MWh vs. biomass at ~600 m2/MWh.
 */
import { Plot } from "./Plot";
import { baseLayout, colorFor, plotlyConfig } from "./plotlyConfig";
import type { LandUseRow } from "@/types/api";

interface LandUseBarProps {
  rows: LandUseRow[];
}

export function LandUseBar({ rows }: LandUseBarProps) {
  if (!rows.length) {
    return (
      <div className="text-sm text-muted-foreground text-center py-8">
        Dataset loading...
      </div>
    );
  }
  const data = [...rows].sort(
    (a, b) => a.median_m2_per_mwh - b.median_m2_per_mwh
  );
  return (
    <Plot
      data={[
        {
          type: "bar",
          orientation: "h",
          x: data.map((r) => r.median_m2_per_mwh),
          y: data.map((r) => r.source),
          error_x: {
            type: "data",
            symmetric: false,
            array: data.map((r) => r.p95_m2_per_mwh - r.median_m2_per_mwh),
            arrayminus: data.map(
              (r) => r.median_m2_per_mwh - r.p5_m2_per_mwh
            ),
            thickness: 1.4,
            width: 5,
            color: "#64748b",
          },
          marker: {
            color: data.map((r) => colorFor(r.source.toLowerCase())),
          },
          hovertemplate:
            "<b>%{y}</b><br>%{x:.2f} m²/MWh (p5-p95: %{customdata[0]}-%{customdata[1]})<extra></extra>",
          customdata: data.map((r) => [r.p5_m2_per_mwh, r.p95_m2_per_mwh]),
        },
      ]}
      layout={{
        ...baseLayout(),
        height: 320,
        xaxis: {
          ...baseLayout().xaxis,
          title: { text: "m² / MWh (log)" },
          type: "log",
        },
        yaxis: { ...baseLayout().yaxis, automargin: true },
        margin: { l: 110, r: 40, t: 20, b: 50 },
      }}
      config={plotlyConfig}
      style={{ width: "100%" }}
      useResizeHandler
    />
  );
}
