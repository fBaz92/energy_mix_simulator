/**
 * Overlaid histograms of avg price for multiple simulations.
 * Used on the Compare page to visualise how the price distribution
 * shifts across scenarios (lower = better mix).
 */
import type { Data } from "plotly.js";
import { Plot } from "./Plot";
import { baseLayout, plotlyConfig } from "./plotlyConfig";

interface Series {
  label: string;
  values: number[];
  color: string;
}

interface PriceDistributionCompareProps {
  series: Series[];
}

export function PriceDistributionCompare({
  series,
}: PriceDistributionCompareProps) {
  const traces: Data[] = series.map((s) => ({
    type: "histogram",
    x: s.values,
    name: s.label,
    opacity: 0.55,
    marker: { color: s.color },
    nbinsx: Math.min(
      20,
      Math.max(5, Math.round(s.values.length / 2))
    ),
  }) as Data);

  return (
    <Plot
      data={traces}
      layout={{
        ...baseLayout(),
        height: 340,
        barmode: "overlay",
        xaxis: {
          ...baseLayout().xaxis,
          title: { text: "EUR/MWh" },
        },
        yaxis: {
          ...baseLayout().yaxis,
          title: { text: "MC runs" },
        },
      }}
      config={plotlyConfig}
      style={{ width: "100%" }}
      useResizeHandler
    />
  );
}
