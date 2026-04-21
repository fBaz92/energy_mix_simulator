/**
 * Top-N hydro-disaster bar chart.
 *
 * User requirement: hydroelectric dam failures are the deadliest energy
 * accidents by absolute count and deserve their own focused visual.
 * Horizontal bars with the estimated-deaths-high value; Banqiao
 * dominates and is left visually intact rather than clipped.
 */
import { useMemo } from "react";
import { Plot } from "./Plot";
import { baseLayout, plotlyConfig } from "./plotlyConfig";
import type { AccidentRow } from "@/types/api";

interface HydroDisastersBarProps {
  rows: AccidentRow[];
  /** Include only hydro accidents; default ``true``. */
  hydroOnly?: boolean;
}

export function HydroDisastersBar({
  rows,
  hydroOnly = true,
}: HydroDisastersBarProps) {
  const data = useMemo(() => {
    const filtered = hydroOnly
      ? rows.filter((r) => r.source_type === "Hydro")
      : rows;
    return [...filtered]
      .sort((a, b) => a.estimated_deaths_high - b.estimated_deaths_high)
      .slice(-10);
  }, [rows, hydroOnly]);

  if (!data.length) {
    return (
      <div className="text-sm text-muted-foreground text-center py-8">
        Loading...
      </div>
    );
  }

  return (
    <Plot
      data={[
        {
          type: "bar",
          orientation: "h",
          x: data.map((r) => r.estimated_deaths_high),
          y: data.map((r) => `${r.name} (${r.year})`),
          marker: { color: "#06b6d4" },
          text: data.map((r) =>
            r.estimated_deaths_high >= 1000
              ? `${(r.estimated_deaths_high / 1000).toFixed(1)}k`
              : r.estimated_deaths_high.toString()
          ),
          textposition: "outside",
          hovertemplate:
            "<b>%{y}</b><br>Country: %{customdata[0]}<br>Direct: %{customdata[1]}<br>Estimated high: %{x:,}<extra></extra>",
          customdata: data.map((r) => [r.country, r.direct_deaths]),
        },
      ]}
      layout={{
        ...baseLayout(),
        height: 380,
        xaxis: {
          ...baseLayout().xaxis,
          title: { text: "Estimated upper-bound deaths (log)" },
          type: "log",
        },
        yaxis: { ...baseLayout().yaxis, automargin: true },
        margin: { l: 260, r: 60, t: 20, b: 50 },
      }}
      config={plotlyConfig}
      style={{ width: "100%" }}
      useResizeHandler
    />
  );
}
