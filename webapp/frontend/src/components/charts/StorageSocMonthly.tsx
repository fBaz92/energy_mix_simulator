/**
 * Monthly average SOC per storage unit, grouped bars.
 *
 * Reveals seasonal patterns (e.g. higher SOC in shoulder months when price
 * spreads are largest). Mirrors ``plot_storage_soc_monthly``.
 */
import Plot from "react-plotly.js";
import type { Data } from "plotly.js";
import { baseLayout, plotlyConfig } from "./plotlyConfig";

interface StorageSocMonthlyProps {
  names: string[];
  /** Shape (n_runs, n_storage, 12). */
  monthlyAvgSoc: number[][][];
}

const MONTH_LABELS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

const UNIT_COLORS = ["#8B5CF6", "#06B6D4", "#F59E0B", "#EC4899"];

export function StorageSocMonthly({
  names,
  monthlyAvgSoc,
}: StorageSocMonthlyProps) {
  if (!monthlyAvgSoc.length || !names.length) return null;
  const nRuns = monthlyAvgSoc.length;

  // Mean across runs for each (unit, month)
  const meanPerUnitMonth = names.map((_, ui) => {
    const months = Array(12).fill(0);
    for (let r = 0; r < nRuns; r++) {
      for (let m = 0; m < 12; m++) {
        months[m] += monthlyAvgSoc[r][ui][m];
      }
    }
    return months.map((v) => v / nRuns);
  });

  const traces: Data[] = names.map((name, ui) => ({
    type: "bar",
    name,
    x: MONTH_LABELS,
    y: meanPerUnitMonth[ui],
    marker: { color: UNIT_COLORS[ui % UNIT_COLORS.length] },
    hovertemplate: `${name}<br>%{x}: SOC %{y:.2f}<extra></extra>`,
  }));

  return (
    <Plot
      data={traces}
      layout={{
        ...baseLayout(),
        height: 300,
        barmode: "group",
        xaxis: { ...baseLayout().xaxis, title: { text: "Month" } },
        yaxis: {
          ...baseLayout().yaxis,
          title: { text: "Average SOC (fraction)" },
          range: [0, 1],
        },
      }}
      config={plotlyConfig}
      style={{ width: "100%" }}
      useResizeHandler
    />
  );
}
