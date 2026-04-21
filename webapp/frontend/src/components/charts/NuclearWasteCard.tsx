/**
 * Informational card layout for the nuclear waste scheda.
 *
 * Mixes numeric highlights, a WLLW / LLW / ILW / HLW breakdown table,
 * a stacked bar chart of volume-vs-radioactivity share (which makes
 * the ~95% / ~3% inversion visually obvious), and a list of the deep
 * geological repositories that actually exist.
 */
import { Plot } from "./Plot";
import { baseLayout, plotlyConfig } from "./plotlyConfig";
import type { NuclearWastePayload } from "@/types/api";

const CATEGORY_COLORS: Record<string, string> = {
  VLLW: "#a7f3d0",
  LLW: "#6ee7b7",
  ILW: "#fbbf24",
  HLW: "#b91c1c",
};

interface NuclearWasteCardProps {
  payload: NuclearWastePayload | undefined;
}

export function NuclearWasteCard({ payload }: NuclearWasteCardProps) {
  if (!payload) {
    return (
      <div className="text-sm text-muted-foreground text-center py-8">
        Loading nuclear waste data...
      </div>
    );
  }

  const { headline, categories, global_stockpile_2023, size_comparison,
          deep_geological_repositories } = payload;

  return (
    <div className="space-y-6">
      {/* Headline stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
        <HeadlineStat
          label="Spent fuel per MWh"
          value={`${headline.spent_fuel_per_mwh_electrical_g} g`}
          sub="LWR, electrical output"
        />
        <HeadlineStat
          label="Coal ash per MWh"
          value={`${headline.coal_ash_per_mwh_kg} kg`}
          sub={`${Math.round((headline.coal_ash_per_mwh_kg * 1000) / headline.spent_fuel_per_mwh_electrical_g)}x more by mass`}
        />
        <HeadlineStat
          label="HLW cumulative world"
          value={`${(global_stockpile_2023.spent_fuel_in_storage_tonnes_hm / 1000).toFixed(0)} kt`}
          sub="Tonnes heavy metal since 1950s"
        />
        <HeadlineStat
          label="Annual production"
          value={`${(global_stockpile_2023.annual_production_tonnes_hm_per_year / 1000).toFixed(1)} kt/yr`}
          sub="Tonnes HM per year"
        />
      </div>

      {/* Volume vs radioactivity */}
      <div className="space-y-1">
        <h3 className="text-sm font-semibold">Volume vs. radioactivity</h3>
        <p className="text-xs text-muted-foreground">
          The four waste categories differ by 6+ orders of magnitude in
          radioactivity per unit volume. HLW is only ~3% of the volume
          but ~95% of the radioactivity — conflating categories is the
          most common mistake in public discourse.
        </p>
        <Plot
          data={[
            {
              type: "bar",
              name: "Volume share",
              x: categories.map((c) => c.category),
              y: categories.map((c) => c.share_of_waste_volume_pct),
              marker: {
                color: categories.map(
                  (c) => CATEGORY_COLORS[c.category] ?? "#64748b"
                ),
              },
              hovertemplate: "<b>%{x}</b><br>%{y}% of volume<extra></extra>",
            },
            {
              type: "bar",
              name: "Radioactivity share",
              x: categories.map((c) => c.category),
              y: categories.map((c) => c.share_of_waste_radioactivity_pct),
              marker: {
                color: categories.map(
                  (c) => CATEGORY_COLORS[c.category] ?? "#64748b"
                ),
                opacity: 0.6,
                pattern: { shape: "/" },
              },
              hovertemplate:
                "<b>%{x}</b><br>%{y}% of radioactivity<extra></extra>",
            },
          ]}
          layout={{
            ...baseLayout(),
            height: 260,
            barmode: "group",
            yaxis: {
              ...baseLayout().yaxis,
              title: { text: "% of total (log)" },
              type: "log",
            },
            margin: { l: 70, r: 20, t: 20, b: 50 },
          }}
          config={plotlyConfig}
          style={{ width: "100%" }}
          useResizeHandler
        />
      </div>

      {/* Category table */}
      <div className="overflow-x-auto text-xs">
        <table className="w-full border-collapse">
          <thead>
            <tr className="border-b bg-muted/40 text-left">
              <th className="px-2 py-1.5 font-medium">Category</th>
              <th className="px-2 py-1.5 font-medium">Contents</th>
              <th className="px-2 py-1.5 font-medium">Disposal</th>
              <th className="px-2 py-1.5 font-medium text-right">
                Hazard lifetime
              </th>
            </tr>
          </thead>
          <tbody>
            {categories.map((c) => (
              <tr key={c.category} className="border-b align-top">
                <td className="px-2 py-1.5">
                  <div className="font-medium">{c.category}</div>
                  <div className="text-muted-foreground">{c.full_name}</div>
                </td>
                <td className="px-2 py-1.5 text-muted-foreground">
                  {c.typical_contents}
                </td>
                <td className="px-2 py-1.5 text-muted-foreground">
                  {c.disposal}
                </td>
                <td className="px-2 py-1.5 text-right tabular-nums">
                  {c.hazard_lifetime_years.toLocaleString()} yr
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Size comparison */}
      <div className="rounded-md border bg-muted/30 p-3 text-sm">
        <div className="font-semibold mb-1">Physical scale</div>
        <p className="text-muted-foreground">{size_comparison.description}</p>
      </div>

      {/* Repositories */}
      <div className="space-y-2">
        <h3 className="text-sm font-semibold">Deep geological repositories</h3>
        <div className="grid md:grid-cols-2 gap-2">
          {deep_geological_repositories.map((repo) => (
            <div
              key={repo.name}
              className="rounded-md border p-3 text-xs space-y-1"
            >
              <div className="flex justify-between gap-2">
                <span className="font-semibold">{repo.name}</span>
                <span className="text-muted-foreground">{repo.country}</span>
              </div>
              <div className="text-muted-foreground">{repo.status}</div>
              <div className="flex gap-3 text-muted-foreground">
                <span>Host rock: {repo.host_rock}</span>
                <span>Depth: {repo.depth_m} m</span>
              </div>
              {repo.notes && (
                <div className="text-muted-foreground">{repo.notes}</div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Coal comparison note */}
      <div className="rounded-md border border-amber-200 bg-amber-50/50 p-3 text-xs text-amber-900">
        <span className="font-semibold">Note on coal ash comparison:</span>{" "}
        {headline.coal_ash_comparison_note}
      </div>
    </div>
  );
}

function HeadlineStat({
  label,
  value,
  sub,
}: {
  label: string;
  value: string;
  sub: string;
}) {
  return (
    <div className="rounded-md border p-3">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="text-xl font-bold tracking-tight mt-0.5">{value}</div>
      <div className="text-[10px] text-muted-foreground">{sub}</div>
    </div>
  );
}
