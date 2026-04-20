/**
 * Pie chart of the share of the year each technology set the marginal
 * electricity price.
 *
 * The "price-setter" at a given quarter-hour is the unit with the highest
 * SRMC among those dispatched — i.e. the one whose cost the system is
 * willing to pay to serve the last MWh of demand. Aggregated across the
 * year and MC runs, this answers the question "who sets the price on
 * average?". Technologies that never clear are omitted.
 */
import { Plot } from "./Plot";
import { colorFor, plotlyConfig } from "./plotlyConfig";

interface PriceSetterPieProps {
  /** price_setter_pct_by_tech: {tech: [per_run_fraction_in_0..1]}. */
  pctByTech: Record<string, number[]>;
}

export function PriceSetterPie({ pctByTech }: PriceSetterPieProps) {
  const rows = Object.entries(pctByTech)
    .map(([tech, vals]) => ({
      tech,
      mean_pct:
        vals.length > 0 ? (vals.reduce((a, b) => a + b, 0) / vals.length) * 100 : 0,
    }))
    .filter((r) => r.mean_pct > 0.01)
    .sort((a, b) => b.mean_pct - a.mean_pct);

  if (rows.length === 0) {
    return (
      <div className="text-sm text-muted-foreground text-center py-8">
        No price-setter data available.
      </div>
    );
  }

  return (
    <Plot
      data={[
        {
          type: "pie",
          labels: rows.map((r) => r.tech),
          values: rows.map((r) => r.mean_pct),
          marker: { colors: rows.map((r) => colorFor(r.tech)) },
          hole: 0.5,
          textinfo: "label+percent",
          hovertemplate:
            "<b>%{label}</b><br>%{value:.1f}% of year<extra></extra>",
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
