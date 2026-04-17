/**
 * Horizontal bar chart of CO₂ emissions by technology.
 *
 * Shows the mean annual emissions (Mt) per technology across MC runs.
 * Only technologies with non-zero emissions are displayed.
 */
import { Plot } from "./Plot";
import { baseLayout, colorFor, plotlyConfig } from "./plotlyConfig";

interface EmissionsBreakdownProps {
  /** emissions_by_tech: {tech: [per_run_tons]}. */
  emissionsByTech: Record<string, number[]>;
}

export function EmissionsBreakdown({
  emissionsByTech,
}: EmissionsBreakdownProps) {
  // Compute per-tech means in Mt, filter zero-emission techs
  const rows = Object.entries(emissionsByTech)
    .map(([tech, vals]) => ({
      tech,
      mean_mt: vals.reduce((a, b) => a + b, 0) / vals.length / 1e6,
    }))
    .filter((r) => r.mean_mt > 0.01)
    .sort((a, b) => b.mean_mt - a.mean_mt);

  if (rows.length === 0) {
    return (
      <div className="text-sm text-muted-foreground text-center py-8">
        No CO₂ emissions in this scenario (fully decarbonized).
      </div>
    );
  }

  return (
    <Plot
      data={[
        {
          type: "bar",
          orientation: "h",
          x: rows.map((r) => r.mean_mt),
          y: rows.map((r) => r.tech),
          marker: {
            color: rows.map((r) => colorFor(r.tech)),
          },
          text: rows.map((r) => `${r.mean_mt.toFixed(1)} Mt`),
          textposition: "outside",
          hovertemplate: "<b>%{y}</b><br>%{x:.2f} Mt/year<extra></extra>",
        },
      ]}
      layout={{
        ...baseLayout(),
        height: 280,
        xaxis: {
          ...baseLayout().xaxis,
          title: { text: "Mt CO₂ / year" },
        },
        yaxis: {
          ...baseLayout().yaxis,
          automargin: true,
        },
        margin: { l: 100, r: 60, t: 20, b: 50 },
      }}
      config={plotlyConfig}
      style={{ width: "100%" }}
      useResizeHandler
    />
  );
}
