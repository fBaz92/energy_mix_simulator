/**
 * Horizontal bar chart of lifecycle carbon intensity (gCO2eq/kWh) per
 * source, with p5-p95 error bars from IPCC AR6.
 *
 * The ranges communicate the real uncertainty in LCA values — hydro
 * spans three orders of magnitude because tropical reservoirs emit
 * methane, while nuclear and wind are tightly clustered at the low
 * end. The bar chart alone would hide that insight.
 */
import { Plot } from "./Plot";
import { baseLayout, colorFor, plotlyConfig } from "./plotlyConfig";
import type { LifecycleCarbonRow } from "@/types/api";

interface LifecycleCarbonBarProps {
  rows: LifecycleCarbonRow[];
}

export function LifecycleCarbonBar({ rows }: LifecycleCarbonBarProps) {
  if (!rows.length) {
    return (
      <div className="text-sm text-muted-foreground text-center py-8">
        Dataset loading...
      </div>
    );
  }
  // Sort by median ascending so clean sources are at the bottom,
  // dirty ones at the top — matches reading order of a y-axis.
  const data = [...rows].sort(
    (a, b) => a.median_gco2eq_kwh - b.median_gco2eq_kwh
  );

  return (
    <Plot
      data={[
        {
          type: "bar",
          orientation: "h",
          x: data.map((r) => r.median_gco2eq_kwh),
          y: data.map((r) => r.source),
          error_x: {
            type: "data",
            symmetric: false,
            array: data.map((r) => r.p95_gco2eq_kwh - r.median_gco2eq_kwh),
            arrayminus: data.map(
              (r) => r.median_gco2eq_kwh - r.p5_gco2eq_kwh
            ),
            thickness: 1.4,
            width: 5,
            color: "#64748b",
          },
          marker: {
            color: data.map((r) => colorFor(r.source.toLowerCase())),
          },
          hovertemplate:
            "<b>%{y}</b><br>Median: %{x} gCO2eq/kWh<br>Range (p5-p95): %{customdata[0]}-%{customdata[1]}<extra></extra>",
          customdata: data.map((r) => [r.p5_gco2eq_kwh, r.p95_gco2eq_kwh]),
        },
      ]}
      layout={{
        ...baseLayout(),
        height: 420,
        xaxis: {
          ...baseLayout().xaxis,
          title: { text: "gCO₂eq / kWh (log)" },
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
