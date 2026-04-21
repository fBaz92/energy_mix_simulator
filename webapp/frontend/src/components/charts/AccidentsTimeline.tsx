/**
 * Scatter timeline of major energy accidents.
 *
 * X-axis: year. Y-axis: source_type (Hydro, Nuclear, Coal, Oil & Gas).
 * Marker size encodes log10(estimated_deaths_high) so Banqiao is
 * visually distinct from Three Mile Island without crushing the
 * small-incident markers into invisibility.
 */
import { useMemo } from "react";
import { Plot } from "./Plot";
import { baseLayout, plotlyConfig } from "./plotlyConfig";
import type { AccidentRow } from "@/types/api";

const SOURCE_TYPE_COLORS: Record<string, string> = {
  Hydro: "#06b6d4",
  Nuclear: "#a855f7",
  Coal: "#44403c",
  "Oil & Gas": "#ea580c",
};

interface AccidentsTimelineProps {
  rows: AccidentRow[];
}

export function AccidentsTimeline({ rows }: AccidentsTimelineProps) {
  const traces = useMemo(() => {
    const bySourceType = new Map<string, AccidentRow[]>();
    for (const r of rows) {
      const arr = bySourceType.get(r.source_type) ?? [];
      arr.push(r);
      bySourceType.set(r.source_type, arr);
    }
    return Array.from(bySourceType.entries()).map(([sourceType, items]) => ({
      type: "scatter" as const,
      mode: "markers" as const,
      name: sourceType,
      x: items.map((r) => r.year),
      y: items.map(() => sourceType),
      marker: {
        size: items.map((r) =>
          Math.max(8, 6 + 5 * Math.log10(Math.max(1, r.estimated_deaths_high)))
        ),
        color: SOURCE_TYPE_COLORS[sourceType] ?? "#64748b",
        opacity: 0.75,
        line: { color: "#1e293b", width: 0.8 },
      },
      hovertemplate:
        "<b>%{customdata[0]}</b> (%{x})<br>" +
        "Country: %{customdata[1]}<br>" +
        "Est. deaths: %{customdata[2]}-%{customdata[3]}" +
        "<extra></extra>",
      customdata: items.map((r) => [
        r.name,
        r.country,
        r.estimated_deaths_low,
        r.estimated_deaths_high,
      ]),
    }));
  }, [rows]);

  if (!rows.length) {
    return (
      <div className="text-sm text-muted-foreground text-center py-8">
        Dataset loading...
      </div>
    );
  }

  return (
    <Plot
      data={traces}
      layout={{
        ...baseLayout(),
        height: 340,
        xaxis: {
          ...baseLayout().xaxis,
          title: { text: "Year" },
        },
        yaxis: {
          ...baseLayout().yaxis,
          automargin: true,
          categoryorder: "array",
          categoryarray: ["Hydro", "Nuclear", "Coal", "Oil & Gas"],
        },
        margin: { l: 100, r: 20, t: 20, b: 50 },
        showlegend: true,
      }}
      config={plotlyConfig}
      style={{ width: "100%" }}
      useResizeHandler
    />
  );
}
