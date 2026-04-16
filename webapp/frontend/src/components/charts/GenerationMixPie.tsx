/**
 * Pie chart of installed capacity by technology.
 *
 * Uses the scenario's mix_config (capacity_gw per tech) rather than
 * dispatched energy, since we don't track hourly energy per tech in
 * the MC aggregate. This gives a quick overview of the mix structure.
 */
import Plot from "react-plotly.js";
import { colorFor, plotlyConfig } from "./plotlyConfig";
import type { GeneratorParams } from "@/types/api";

interface GenerationMixPieProps {
  mixConfig: Record<string, GeneratorParams>;
}

export function GenerationMixPie({ mixConfig }: GenerationMixPieProps) {
  const entries = Object.entries(mixConfig)
    .filter(([, p]) => p.capacity_gw > 0.01)
    .sort((a, b) => b[1].capacity_gw - a[1].capacity_gw);

  if (entries.length === 0) {
    return (
      <div className="text-sm text-muted-foreground text-center py-8">
        No installed capacity.
      </div>
    );
  }

  const labels = entries.map(([tech]) => tech);
  const values = entries.map(([, p]) => p.capacity_gw);
  const colors = labels.map(colorFor);

  return (
    <Plot
      data={[
        {
          type: "pie",
          labels,
          values,
          marker: { colors },
          hole: 0.5,
          textinfo: "label+percent",
          hovertemplate:
            "<b>%{label}</b><br>%{value:.1f} GW (%{percent})<extra></extra>",
        },
      ]}
      layout={{
        height: 320,
        paper_bgcolor: "rgba(0,0,0,0)",
        plot_bgcolor: "rgba(0,0,0,0)",
        margin: { l: 20, r: 20, t: 20, b: 20 },
        showlegend: false,
        font: { size: 12 },
      }}
      config={plotlyConfig}
      style={{ width: "100%" }}
      useResizeHandler
    />
  );
}
