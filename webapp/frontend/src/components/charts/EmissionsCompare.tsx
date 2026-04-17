/**
 * Grouped bar chart comparing per-technology CO₂ emissions across simulations.
 */
import Plot from "react-plotly.js";
import type { Data } from "plotly.js";
import { baseLayout, colorFor, plotlyConfig } from "./plotlyConfig";

interface SimSeries {
  label: string;
  /** emissions_by_tech: {tech: [per_run_tons]}. */
  emissionsByTech: Record<string, number[]>;
}

export function EmissionsCompare({ series }: { series: SimSeries[] }) {
  // Collect all techs across all series
  const allTechs = new Set<string>();
  series.forEach((s) =>
    Object.keys(s.emissionsByTech).forEach((t) => allTechs.add(t))
  );
  const techs = Array.from(allTechs).filter((t) => {
    const maxAcrossSeries = Math.max(
      ...series.map((s) => {
        const vals = s.emissionsByTech[t] ?? [];
        return vals.length
          ? vals.reduce((a, b) => a + b, 0) / vals.length / 1e6
          : 0;
      })
    );
    return maxAcrossSeries > 0.01;
  });

  const traces: Data[] = techs.map((tech) => ({
    type: "bar",
    name: tech,
    x: series.map((s) => s.label),
    y: series.map((s) => {
      const vals = s.emissionsByTech[tech] ?? [];
      return vals.length
        ? vals.reduce((a, b) => a + b, 0) / vals.length / 1e6
        : 0;
    }),
    marker: { color: colorFor(tech) },
    hovertemplate: `${tech}<br>%{x}: %{y:.2f} Mt/yr<extra></extra>`,
  }));

  return (
    <Plot
      data={traces}
      layout={{
        ...baseLayout(),
        height: 340,
        barmode: "stack",
        xaxis: { ...baseLayout().xaxis, title: { text: "Scenario" } },
        yaxis: {
          ...baseLayout().yaxis,
          title: { text: "Mt CO₂ / year" },
        },
      }}
      config={plotlyConfig}
      style={{ width: "100%" }}
      useResizeHandler
    />
  );
}
