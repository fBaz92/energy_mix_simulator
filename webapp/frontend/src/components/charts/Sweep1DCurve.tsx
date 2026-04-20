/**
 * 1D sweep line chart with a selectable metric.
 *
 * Plots one point per grid value with a shaded ±1σ error band (only
 * meaningful for the price metric — other metrics collapse to a
 * single line since the sweep runner does not record their std).
 */
import { useState } from "react";
import type { Data } from "plotly.js";
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

interface Sweep1DCurveProps {
  results: SweepFullResult;
}

export function Sweep1DCurve({ results }: Sweep1DCurveProps) {
  const [metric, setMetric] = useState<Metric>("avg_price_mean");

  const x = results.points.map((p) => p.a);
  const y = results.points.map((p) => p[metric]);
  const stdUpper =
    metric === "avg_price_mean"
      ? results.points.map((p) => p.avg_price_mean + p.avg_price_std)
      : null;
  const stdLower =
    metric === "avg_price_mean"
      ? results.points.map((p) => p.avg_price_mean - p.avg_price_std)
      : null;

  const mLabel = METRIC_LABELS[metric];

  const traces: Data[] = [
    {
      type: "scatter",
      mode: "lines+markers",
      x,
      y,
      line: { color: "#0f172a", width: 2 },
      marker: { color: "#0f172a", size: 8 },
      name: "mean",
      hovertemplate: `${results.parameter_a} = %{x:.2f}<br>%{y:.2f} ${mLabel.unit}<extra></extra>`,
    },
  ];
  if (stdUpper && stdLower) {
    traces.unshift({
      type: "scatter",
      mode: "lines",
      x: [...x, ...[...x].reverse()],
      y: [...stdUpper, ...[...stdLower].reverse()],
      fill: "toself",
      fillcolor: "rgba(15,23,42,0.15)",
      line: { color: "rgba(0,0,0,0)" },
      hoverinfo: "skip",
      showlegend: false,
      name: "±1σ",
    });
  }

  return (
    <div>
      <div className="mb-3 flex items-center gap-2 text-sm">
        <label htmlFor="sweep1d-metric" className="text-muted-foreground">
          Metric:
        </label>
        <select
          id="sweep1d-metric"
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
        data={traces}
        layout={{
          ...baseLayout(),
          height: 340,
          xaxis: {
            ...baseLayout().xaxis,
            title: { text: results.parameter_a },
          },
          yaxis: {
            ...baseLayout().yaxis,
            title: { text: `${mLabel.label} (${mLabel.unit})` },
          },
          showlegend: false,
          margin: { l: 70, r: 20, t: 20, b: 50 },
        }}
        config={plotlyConfig}
        style={{ width: "100%" }}
        useResizeHandler
      />
    </div>
  );
}
