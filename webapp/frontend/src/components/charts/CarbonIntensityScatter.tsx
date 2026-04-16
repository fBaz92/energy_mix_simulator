/**
 * Scatter plot of carbon intensity vs average price across MC runs.
 *
 * Each point is one MC year. Reveals correlations between price and
 * emissions (e.g. high gas price runs tend to have higher CO2 if
 * coal picks up the slack).
 */
import Plot from "react-plotly.js";
import { baseLayout, plotlyConfig } from "./plotlyConfig";

interface CarbonIntensityScatterProps {
  avgPrice: number[];
  carbonIntensity: number[];
}

export function CarbonIntensityScatter({
  avgPrice,
  carbonIntensity,
}: CarbonIntensityScatterProps) {
  return (
    <Plot
      data={[
        {
          type: "scatter",
          mode: "markers",
          x: avgPrice,
          y: carbonIntensity,
          marker: {
            color: "#8b5cf6",
            size: 8,
            opacity: 0.7,
            line: { width: 1, color: "#6d28d9" },
          },
          hovertemplate:
            "price: %{x:.1f} EUR/MWh<br>CI: %{y:.0f} gCO₂/kWh<extra></extra>",
        },
      ]}
      layout={{
        ...baseLayout(),
        height: 280,
        xaxis: {
          ...baseLayout().xaxis,
          title: { text: "Avg price (EUR/MWh)" },
        },
        yaxis: {
          ...baseLayout().yaxis,
          title: { text: "Carbon intensity (gCO₂/kWh)" },
        },
      }}
      config={plotlyConfig}
      style={{ width: "100%" }}
      useResizeHandler
    />
  );
}
