/**
 * Monthly grouped bar chart of signed CO₂ benefit per interconnection.
 *
 * Positive = imports avoided domestic emissions (lower-carbon neighbour);
 * negative = imports increased consumption-based emissions.
 *
 * Mirrors ``plot_co2_benefit_monthly`` from the matplotlib layer.
 */
import type { Data } from "plotly.js";
import { Plot } from "./Plot";
import { baseLayout, plotlyConfig } from "./plotlyConfig";

interface Co2BenefitMonthlyProps {
  names: string[];
  /** Shape (n_runs, n_links, 12), tons. */
  monthlyCo2Tons: number[][][];
}

const MONTH_LABELS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

const LINK_COLORS = [
  "#1565C0", "#F57F17", "#2E7D32", "#6A1B9A", "#C62828",
  "#00838F", "#5D4037", "#8E24AA",
];

export function Co2BenefitMonthly({
  names,
  monthlyCo2Tons,
}: Co2BenefitMonthlyProps) {
  if (!monthlyCo2Tons.length || !names.length) return null;
  const nRuns = monthlyCo2Tons.length;

  // Mean across runs for each (link, month), in kt
  const meanPerLinkMonth = names.map((_, li) => {
    const months = Array(12).fill(0);
    for (let r = 0; r < nRuns; r++) {
      for (let m = 0; m < 12; m++) {
        months[m] += monthlyCo2Tons[r][li][m];
      }
    }
    return months.map((v) => v / nRuns / 1e3);
  });

  const traces: Data[] = names.map((name, li) => ({
    type: "bar",
    name,
    x: MONTH_LABELS,
    y: meanPerLinkMonth[li],
    marker: { color: LINK_COLORS[li % LINK_COLORS.length] },
    hovertemplate: `${name}<br>%{x}: %{y:+.0f} kt<extra></extra>`,
  }));

  return (
    <Plot
      data={traces}
      layout={{
        ...baseLayout(),
        height: 320,
        barmode: "group",
        xaxis: { ...baseLayout().xaxis, title: { text: "Month" } },
        yaxis: {
          ...baseLayout().yaxis,
          title: { text: "CO₂ benefit (kt)" },
          zeroline: true,
          zerolinecolor: "rgba(150,150,150,0.5)",
          zerolinewidth: 1,
        },
      }}
      config={plotlyConfig}
      style={{ width: "100%" }}
      useResizeHandler
    />
  );
}
