/**
 * Cross-border flow summary: grouped bars per link (gross import/export, net)
 * with overlaid foreign price and NTC saturation lines on a secondary axis.
 *
 * Mirrors ``plot_interconnection_flows_summary`` from the matplotlib layer.
 */
import Plot from "react-plotly.js";
import type { Data } from "plotly.js";
import { baseLayout, plotlyConfig } from "./plotlyConfig";

interface InterconnectionFlowsProps {
  names: string[];
  /** Shape (n_runs, n_links). */
  importGrossTwh: number[][];
  exportGrossTwh: number[][];
  netImportTwh: number[][];
  foreignPriceMean: number[][];
  ntcImportSaturationPct: number[][];
}

function meanCol(matrix: number[][], col: number): number {
  if (matrix.length === 0) return 0;
  let s = 0;
  for (const row of matrix) s += row[col];
  return s / matrix.length;
}

function stdCol(matrix: number[][], col: number): number {
  if (matrix.length === 0) return 0;
  const m = meanCol(matrix, col);
  let s = 0;
  for (const row of matrix) {
    const d = row[col] - m;
    s += d * d;
  }
  return Math.sqrt(s / matrix.length);
}

export function InterconnectionFlows({
  names,
  importGrossTwh,
  exportGrossTwh,
  netImportTwh,
  foreignPriceMean,
  ntcImportSaturationPct,
}: InterconnectionFlowsProps) {
  const imp = names.map((_, i) => meanCol(importGrossTwh, i));
  const exp = names.map((_, i) => meanCol(exportGrossTwh, i));
  const net = names.map((_, i) => meanCol(netImportTwh, i));
  const netStd = names.map((_, i) => stdCol(netImportTwh, i));
  const fprice = names.map((_, i) => meanCol(foreignPriceMean, i));
  const sat = names.map((_, i) => meanCol(ntcImportSaturationPct, i));

  const traces: Data[] = [
    {
      type: "bar",
      name: "Gross import",
      x: names,
      y: imp,
      marker: { color: "#2E7D32" },
    },
    {
      type: "bar",
      name: "Gross export",
      x: names,
      y: exp,
      marker: { color: "#C62828" },
    },
    {
      type: "bar",
      name: "Net import ± σ",
      x: names,
      y: net,
      error_y: { type: "data", array: netStd, visible: true },
      marker: { color: "#1565C0" },
    },
    {
      type: "scatter",
      mode: "lines+markers",
      name: "Foreign price (EUR/MWh)",
      x: names,
      y: fprice,
      line: { color: "#F57F17", dash: "dash" },
      marker: { symbol: "diamond", size: 9 },
      yaxis: "y2",
    },
    {
      type: "scatter",
      mode: "lines+markers",
      name: "NTC saturation (%)",
      x: names,
      y: sat,
      line: { color: "#6A1B9A", dash: "dot" },
      marker: { symbol: "square", size: 9 },
      yaxis: "y2",
    },
  ];

  return (
    <Plot
      data={traces}
      layout={{
        ...baseLayout(),
        height: 360,
        barmode: "group",
        xaxis: { ...baseLayout().xaxis, title: { text: "Interconnection" } },
        yaxis: {
          ...baseLayout().yaxis,
          title: { text: "Energy (TWh/yr)" },
        },
        yaxis2: {
          overlaying: "y",
          side: "right",
          title: { text: "Foreign price / NTC sat (%)" },
          gridcolor: "rgba(0,0,0,0)",
        },
        legend: { orientation: "h", y: -0.2 },
      }}
      config={plotlyConfig}
      style={{ width: "100%" }}
      useResizeHandler
    />
  );
}
