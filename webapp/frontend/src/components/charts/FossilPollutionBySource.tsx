/**
 * Horizontal bar of fossil-fuel-attributable deaths by fuel category
 * (Vohra 2021). Complementary to the country-level PM2.5 chart —
 * this one breaks down the source side: coal vs. gas vs. oil vs.
 * "other fossil + secondary".
 */
import { Plot } from "./Plot";
import { baseLayout, plotlyConfig } from "./plotlyConfig";
import type { FossilPollutionPayload } from "@/types/api";

interface FossilPollutionBySourceProps {
  payload: FossilPollutionPayload | undefined;
}

const COLORS: Record<string, string> = {
  Coal: "#44403c",
  Gas: "#94a3b8",
  Oil: "#ea580c",
  "Other fossil + secondary": "#7c3aed",
};

export function FossilPollutionBySource({
  payload,
}: FossilPollutionBySourceProps) {
  if (!payload) {
    return (
      <div className="text-sm text-muted-foreground text-center py-8">
        Loading...
      </div>
    );
  }
  const rows = [...payload.by_source].sort(
    (a, b) =>
      a.annual_global_deaths_vohra_2021 - b.annual_global_deaths_vohra_2021
  );

  return (
    <Plot
      data={[
        {
          type: "bar",
          orientation: "h",
          x: rows.map((r) => r.annual_global_deaths_vohra_2021),
          y: rows.map((r) => r.source),
          marker: { color: rows.map((r) => COLORS[r.source] ?? "#64748b") },
          text: rows.map(
            (r) =>
              `${(r.annual_global_deaths_vohra_2021 / 1e6).toFixed(2)}M (${r.share_of_fossil_total_pct}%)`
          ),
          textposition: "outside",
          hovertemplate:
            "<b>%{y}</b><br>%{x:,.0f} deaths/year<br>%{customdata}% of fossil total<extra></extra>",
          customdata: rows.map((r) => r.share_of_fossil_total_pct),
        },
      ]}
      layout={{
        ...baseLayout(),
        height: 280,
        xaxis: {
          ...baseLayout().xaxis,
          title: { text: "Annual global deaths (Vohra et al. 2021)" },
        },
        yaxis: { ...baseLayout().yaxis, automargin: true },
        margin: { l: 200, r: 100, t: 20, b: 50 },
      }}
      config={plotlyConfig}
      style={{ width: "100%" }}
      useResizeHandler
    />
  );
}
