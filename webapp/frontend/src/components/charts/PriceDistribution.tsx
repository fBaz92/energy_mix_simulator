/**
 * Histogram of the average electricity price across MC runs.
 *
 * Shows the uncertainty/spread induced by stochastic fuel prices, weather,
 * and load noise. A vertical line marks the mean.
 */
import Plot from "react-plotly.js";
import type { Data } from "plotly.js";
import { baseLayout, plotlyConfig } from "./plotlyConfig";

interface PriceDistributionProps {
  avgPrice: number[];
}

export function PriceDistribution({ avgPrice }: PriceDistributionProps) {
  const mean = avgPrice.reduce((a, b) => a + b, 0) / avgPrice.length;

  const trace: Data = {
    type: "histogram",
    x: avgPrice,
    name: "Annual price",
    marker: { color: "#3b82f6", opacity: 0.7 },
    nbinsx: Math.min(20, Math.max(5, Math.round(avgPrice.length / 2))),
  } as Data;

  return (
    <Plot
      data={[trace]}
      layout={{
        ...baseLayout(),
        height: 320,
        xaxis: {
          ...baseLayout().xaxis,
          title: { text: "EUR/MWh" },
        },
        yaxis: {
          ...baseLayout().yaxis,
          title: { text: "MC runs" },
        },
        shapes: [
          {
            type: "line",
            x0: mean,
            x1: mean,
            yref: "paper",
            y0: 0,
            y1: 1,
            line: { color: "#ef4444", width: 2, dash: "dash" },
          },
        ],
        annotations: [
          {
            x: mean,
            yref: "paper",
            y: 1.02,
            text: `μ = ${mean.toFixed(1)}`,
            showarrow: false,
            font: { color: "#ef4444", size: 11 },
          },
        ],
      }}
      config={plotlyConfig}
      style={{ width: "100%" }}
      useResizeHandler
    />
  );
}
