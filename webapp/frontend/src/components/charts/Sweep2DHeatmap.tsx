/**
 * 2D sweep heatmap with a selectable metric.
 *
 * Reshapes the row-major ``points`` list from the sweep result into a
 * ``len(values_a) × len(values_b)`` matrix and renders it as a Plotly
 * heatmap. The metric selector lets the user flip between price,
 * carbon intensity, inertia, and curtailment without re-fetching.
 */
import { useState } from "react";
import { Plot } from "./Plot";
import { baseLayout, plotlyConfig } from "./plotlyConfig";
import type { SweepFullResult } from "@/types/api";

type Metric =
  | "avg_price_mean"
  | "carbon_intensity_mean"
  | "avg_inertia_mean"
  | "curtailment_mean";

const METRIC_LABELS: Record<Metric, { label: string; unit: string }> = {
  avg_price_mean: { label: "Average price", unit: "EUR/MWh" },
  carbon_intensity_mean: {
    label: "Carbon intensity",
    unit: "gCO₂/kWh",
  },
  avg_inertia_mean: { label: "System inertia", unit: "s" },
  curtailment_mean: {
    label: "Curtailment",
    unit: "p.u.·qh",
  },
};

interface Sweep2DHeatmapProps {
  results: SweepFullResult;
}

export function Sweep2DHeatmap({ results }: Sweep2DHeatmapProps) {
  const [metric, setMetric] = useState<Metric>("avg_price_mean");

  const nA = results.values_a.length;
  const nB = results.values_b?.length ?? 0;

  if (nB === 0 || !results.values_b) {
    return (
      <div className="text-sm text-muted-foreground text-center py-8">
        2D heatmap requires values_b.
      </div>
    );
  }

  // Reshape row-major: point k = (a = k // nB, b = k % nB).
  const z: number[][] = Array.from({ length: nA }, () => new Array(nB).fill(0));
  for (let i = 0; i < results.points.length; i++) {
    const row = Math.floor(i / nB);
    const col = i % nB;
    z[row][col] = results.points[i][metric];
  }

  const mLabel = METRIC_LABELS[metric];

  return (
    <div>
      <div className="mb-3 flex items-center gap-2 text-sm">
        <label htmlFor="sweep2d-metric" className="text-muted-foreground">
          Metric:
        </label>
        <select
          id="sweep2d-metric"
          value={metric}
          onChange={(e) => setMetric(e.target.value as Metric)}
          className="rounded border border-border bg-background px-2 py-1"
        >
          {(Object.keys(METRIC_LABELS) as Metric[]).map((k) => (
            <option key={k} value={k}>
              {METRIC_LABELS[k].label}
            </option>
          ))}
        </select>
      </div>
      <Plot
        data={[
          {
            type: "heatmap",
            z,
            x: results.values_b,
            y: results.values_a,
            colorscale: "Viridis",
            colorbar: { title: { text: mLabel.unit } },
            hovertemplate:
              `${results.parameter_a} = %{y}<br>` +
              `${results.parameter_b} = %{x}<br>` +
              `${mLabel.label}: %{z:.2f} ${mLabel.unit}<extra></extra>`,
          },
        ]}
        layout={{
          ...baseLayout(),
          height: 380,
          xaxis: {
            ...baseLayout().xaxis,
            title: { text: results.parameter_b ?? "" },
          },
          yaxis: {
            ...baseLayout().yaxis,
            title: { text: results.parameter_a },
          },
          margin: { l: 80, r: 80, t: 20, b: 60 },
        }}
        config={plotlyConfig}
        style={{ width: "100%" }}
        useResizeHandler
      />
    </div>
  );
}
