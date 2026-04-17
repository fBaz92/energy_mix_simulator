/**
 * Horizontal stacked bar: hours per year each link spends importing,
 * exporting, or idle (8760 - import - export).
 *
 * Mirrors ``plot_import_export_hours`` from the matplotlib layer.
 */
import Plot from "react-plotly.js";
import type { Data } from "plotly.js";
import { baseLayout, plotlyConfig } from "./plotlyConfig";

interface ImportExportHoursProps {
  names: string[];
  /** Shape (n_runs, n_links). */
  importHours: number[][];
  exportHours: number[][];
}

function meanCol(matrix: number[][], col: number): number {
  if (matrix.length === 0) return 0;
  let s = 0;
  for (const row of matrix) s += row[col];
  return s / matrix.length;
}

const HOURS_PER_YEAR = 8760;

export function ImportExportHours({
  names,
  importHours,
  exportHours,
}: ImportExportHoursProps) {
  const imp = names.map((_, i) => meanCol(importHours, i));
  const exp = names.map((_, i) => meanCol(exportHours, i));
  const idle = names.map((_, i) => Math.max(0, HOURS_PER_YEAR - imp[i] - exp[i]));

  const traces: Data[] = [
    {
      type: "bar",
      orientation: "h",
      name: "Importing",
      x: imp,
      y: names,
      marker: { color: "#2E7D32" },
      hovertemplate: "%{y}: %{x:.0f} h<extra>Importing</extra>",
    },
    {
      type: "bar",
      orientation: "h",
      name: "Exporting",
      x: exp,
      y: names,
      marker: { color: "#C62828" },
      hovertemplate: "%{y}: %{x:.0f} h<extra>Exporting</extra>",
    },
    {
      type: "bar",
      orientation: "h",
      name: "Idle",
      x: idle,
      y: names,
      marker: { color: "#CFD8DC" },
      hovertemplate: "%{y}: %{x:.0f} h<extra>Idle</extra>",
    },
  ];

  return (
    <Plot
      data={traces}
      layout={{
        ...baseLayout(),
        height: Math.max(220, 60 * names.length + 100),
        barmode: "stack",
        xaxis: {
          ...baseLayout().xaxis,
          title: { text: "Hours / year" },
          range: [0, HOURS_PER_YEAR],
        },
        yaxis: { ...baseLayout().yaxis, automargin: true },
        margin: { l: 80, r: 20, t: 20, b: 60 },
      }}
      config={plotlyConfig}
      style={{ width: "100%" }}
      useResizeHandler
    />
  );
}
