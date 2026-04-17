/**
 * Monthly price distribution as box plots (one box per month).
 *
 * Each box shows the spread of the monthly average price across MC runs,
 * highlighting seasonal patterns (e.g. winter peak, summer solar dip).
 */
import { Plot } from "./Plot";
import { baseLayout, plotlyConfig } from "./plotlyConfig";

interface MonthlyPriceBoxplotProps {
  /** Shape (n_runs, 12). */
  monthlyPrices: number[][];
}

const MONTH_LABELS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

export function MonthlyPriceBoxplot({
  monthlyPrices,
}: MonthlyPriceBoxplotProps) {
  if (!monthlyPrices.length) return null;

  // Build one trace per month by transposing the matrix
  const traces = MONTH_LABELS.map((label, m) => ({
    type: "box" as const,
    y: monthlyPrices.map((row) => row[m]),
    name: label,
    marker: { color: "#3b82f6" },
    boxmean: true as const,
  }));

  return (
    <Plot
      data={traces}
      layout={{
        ...baseLayout(),
        height: 320,
        showlegend: false,
        xaxis: {
          ...baseLayout().xaxis,
          title: { text: "Month" },
        },
        yaxis: {
          ...baseLayout().yaxis,
          title: { text: "EUR/MWh" },
        },
      }}
      config={plotlyConfig}
      style={{ width: "100%" }}
      useResizeHandler
    />
  );
}
