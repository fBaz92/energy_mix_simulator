/**
 * Top-N country bar chart of annual PM2.5-attributable deaths.
 *
 * Year is selectable via a slider; aggregates (regions, income groups)
 * are hidden by default but a toggle surfaces them. PM2.5 data covers
 * all ambient sources, not only fossil fuels — the intro copy on the
 * page clarifies this.
 */
import { useMemo, useState } from "react";
import { Plot } from "./Plot";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { baseLayout, plotlyConfig } from "./plotlyConfig";
import type { Pm25DeathsRow } from "@/types/api";

interface Pm25DeathsByCountryProps {
  rows: Pm25DeathsRow[];
}

export function Pm25DeathsByCountry({ rows }: Pm25DeathsByCountryProps) {
  const availableYears = useMemo(
    () => Array.from(new Set(rows.map((r) => r.year))).sort((a, b) => a - b),
    [rows]
  );
  const [year, setYear] = useState<number | null>(null);
  const [includeAggregates, setIncludeAggregates] = useState(false);

  const effectiveYear = year ?? availableYears[availableYears.length - 1];

  const data = useMemo(() => {
    if (!effectiveYear) return [];
    return rows
      .filter((r) => r.year === effectiveYear)
      .filter((r) => includeAggregates || !r.is_aggregate)
      .sort((a, b) => b.deaths - a.deaths)
      .slice(0, 20);
  }, [rows, effectiveYear, includeAggregates]);

  if (!rows.length) {
    return (
      <div className="text-sm text-muted-foreground text-center py-8">
        Dataset loading...
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-4 text-xs">
        <div className="flex items-center gap-2 flex-1 min-w-[240px]">
          <Label className="whitespace-nowrap" htmlFor="year-slider">
            Year: <span className="font-bold">{effectiveYear}</span>
          </Label>
          <input
            id="year-slider"
            type="range"
            min={availableYears[0]}
            max={availableYears[availableYears.length - 1]}
            step={1}
            value={effectiveYear ?? availableYears[0]}
            onChange={(e) => setYear(parseInt(e.target.value, 10))}
            className="flex-1 accent-primary"
          />
        </div>
        <div className="flex items-center gap-2">
          <Switch
            id="aggregates"
            checked={includeAggregates}
            onCheckedChange={setIncludeAggregates}
          />
          <Label htmlFor="aggregates">Show regional aggregates</Label>
        </div>
      </div>
      <Plot
        data={[
          {
            type: "bar",
            orientation: "h",
            x: data.map((r) => r.deaths),
            y: data.map((r) => r.country),
            marker: { color: "#b91c1c" },
            text: data.map((r) =>
              r.deaths >= 100000
                ? `${(r.deaths / 1000).toFixed(0)}k`
                : r.deaths.toFixed(0)
            ),
            textposition: "outside",
            hovertemplate:
              "<b>%{y}</b><br>%{x:,.0f} deaths / year<extra></extra>",
          },
        ]}
        layout={{
          ...baseLayout(),
          height: 480,
          xaxis: {
            ...baseLayout().xaxis,
            title: { text: "Annual deaths from ambient PM2.5" },
          },
          yaxis: {
            ...baseLayout().yaxis,
            automargin: true,
            categoryorder: "total ascending",
          },
          margin: { l: 120, r: 60, t: 20, b: 50 },
        }}
        config={plotlyConfig}
        style={{ width: "100%" }}
        useResizeHandler
      />
    </div>
  );
}
