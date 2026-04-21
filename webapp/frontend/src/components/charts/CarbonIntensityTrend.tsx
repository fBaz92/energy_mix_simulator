/**
 * Multi-country line chart of operational carbon intensity over time.
 *
 * Defaults surface a representative set (Italy + neighbours + polluters
 * + world) that tells a clear story about grid decarbonisation. Users
 * can add/remove countries via the multi-select.
 */
import { useMemo, useState } from "react";
import { Plot } from "./Plot";
import { baseLayout, plotlyConfig } from "./plotlyConfig";
import type { CarbonIntensityCountryRow } from "@/types/api";

const DEFAULT_COUNTRIES = [
  "Italy",
  "France",
  "Germany",
  "Poland",
  "United Kingdom",
  "World",
] as const;

const COUNTRY_COLORS = [
  "#0ea5e9",
  "#a855f7",
  "#ef4444",
  "#78716c",
  "#eab308",
  "#64748b",
  "#10b981",
  "#ec4899",
];

interface CarbonIntensityTrendProps {
  rows: CarbonIntensityCountryRow[];
}

export function CarbonIntensityTrend({ rows }: CarbonIntensityTrendProps) {
  const available = useMemo(
    () => Array.from(new Set(rows.map((r) => r.country))).sort(),
    [rows]
  );
  const [selected, setSelected] = useState<string[]>(() =>
    DEFAULT_COUNTRIES.filter((c) => available.includes(c))
  );

  const traces = useMemo(
    () =>
      selected.map((country, i) => {
        const series = rows
          .filter((r) => r.country === country)
          .sort((a, b) => a.year - b.year);
        return {
          type: "scatter" as const,
          mode: "lines" as const,
          name: country,
          x: series.map((r) => r.year),
          y: series.map((r) => r.gco2_kwh),
          line: { color: COUNTRY_COLORS[i % COUNTRY_COLORS.length], width: 2 },
          hovertemplate: `<b>${country}</b><br>%{x}: %{y:.0f} gCO₂/kWh<extra></extra>`,
        };
      }),
    [rows, selected]
  );

  function toggle(country: string) {
    setSelected((prev) =>
      prev.includes(country) ? prev.filter((c) => c !== country) : [...prev, country]
    );
  }

  if (!rows.length) {
    return (
      <div className="text-sm text-muted-foreground text-center py-8">
        Dataset loading...
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <Plot
        data={traces}
        layout={{
          ...baseLayout(),
          height: 340,
          xaxis: { ...baseLayout().xaxis, title: { text: "Year" } },
          yaxis: {
            ...baseLayout().yaxis,
            title: { text: "gCO₂ / kWh (operational)" },
          },
          margin: { l: 70, r: 20, t: 20, b: 50 },
        }}
        config={plotlyConfig}
        style={{ width: "100%" }}
        useResizeHandler
      />
      <CountrySelector
        available={available}
        selected={selected}
        onToggle={toggle}
      />
    </div>
  );
}

function CountrySelector({
  available,
  selected,
  onToggle,
}: {
  available: string[];
  selected: string[];
  onToggle: (c: string) => void;
}) {
  const [query, setQuery] = useState("");
  const filtered = query
    ? available.filter((c) => c.toLowerCase().includes(query.toLowerCase()))
    : available.slice(0, 30);
  return (
    <div className="space-y-2">
      <input
        type="search"
        placeholder="Search countries..."
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        className="w-full rounded border border-border bg-background px-2 py-1 text-xs"
      />
      <div className="flex flex-wrap gap-1 max-h-32 overflow-y-auto">
        {selected.map((c) => (
          <button
            key={c}
            onClick={() => onToggle(c)}
            className="rounded bg-primary text-primary-foreground px-2 py-0.5 text-[11px] hover:opacity-80"
          >
            {c} ×
          </button>
        ))}
        {filtered
          .filter((c) => !selected.includes(c))
          .slice(0, 30)
          .map((c) => (
            <button
              key={c}
              onClick={() => onToggle(c)}
              className="rounded border bg-background px-2 py-0.5 text-[11px] hover:bg-accent"
            >
              + {c}
            </button>
          ))}
      </div>
    </div>
  );
}
