/**
 * Monthly stacked bar chart of cross-border economic benefit (congestion rent)
 * broken down by interconnection.
 *
 * Mirrors ``plot_economic_benefit_monthly`` from the matplotlib layer.
 * Values are mean across MC runs, expressed in M€/month.
 */
import type { Data } from "plotly.js";
import { Plot } from "./Plot";
import { baseLayout, plotlyConfig } from "./plotlyConfig";

interface EconomicBenefitMonthlyProps {
  names: string[];
  /** Shape (n_runs, n_links, 12), EUR. */
  monthlyBenefitEur: number[][][];
}

const MONTH_LABELS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

const LINK_COLORS = [
  "#1565C0", "#F57F17", "#2E7D32", "#6A1B9A", "#C62828",
  "#00838F", "#5D4037", "#8E24AA",
];

export function EconomicBenefitMonthly({
  names,
  monthlyBenefitEur,
}: EconomicBenefitMonthlyProps) {
  if (!monthlyBenefitEur.length || !names.length) return null;
  const nRuns = monthlyBenefitEur.length;

  // Mean across runs for each (link, month)
  // Shape after reduction: (n_links, 12), in M€/month
  const meanPerLinkMonth = names.map((_, li) => {
    const months = Array(12).fill(0);
    for (let r = 0; r < nRuns; r++) {
      for (let m = 0; m < 12; m++) {
        months[m] += monthlyBenefitEur[r][li][m];
      }
    }
    return months.map((v) => v / nRuns / 1e6);
  });

  const traces: Data[] = names.map((name, li) => ({
    type: "bar",
    name,
    x: MONTH_LABELS,
    y: meanPerLinkMonth[li],
    marker: { color: LINK_COLORS[li % LINK_COLORS.length] },
    hovertemplate: `${name}<br>%{x}: %{y:.1f} M€<extra></extra>`,
  }));

  return (
    <Plot
      data={traces}
      layout={{
        ...baseLayout(),
        height: 320,
        barmode: "stack",
        xaxis: { ...baseLayout().xaxis, title: { text: "Month" } },
        yaxis: {
          ...baseLayout().yaxis,
          title: { text: "Economic benefit (M€)" },
        },
      }}
      config={plotlyConfig}
      style={{ width: "100%" }}
      useResizeHandler
    />
  );
}
