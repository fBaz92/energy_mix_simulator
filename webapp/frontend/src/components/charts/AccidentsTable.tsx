/**
 * Sortable tabular view of the curated accidents list.
 *
 * No shadcn table primitive is available in this project, so we inline
 * a Tailwind-styled table. Sort state is local; clicking a header
 * toggles between ascending / descending. The reference links open in
 * a new tab.
 */
import { useMemo, useState } from "react";
import { ArrowDown, ArrowUp, ExternalLink } from "lucide-react";
import { cn } from "@/lib/utils";
import type { AccidentRow } from "@/types/api";

type SortKey = "year" | "direct_deaths" | "estimated_deaths_high" | "name";

interface AccidentsTableProps {
  rows: AccidentRow[];
  /** Optional filter by source_type (used by HydroDisastersBar's "see table" link). */
  filterSource?: string;
}

export function AccidentsTable({ rows, filterSource }: AccidentsTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>("estimated_deaths_high");
  const [sortAsc, setSortAsc] = useState(false);

  const view = useMemo(() => {
    const filtered = filterSource
      ? rows.filter((r) => r.source_type === filterSource)
      : rows;
    return [...filtered].sort((a, b) => {
      const va = a[sortKey];
      const vb = b[sortKey];
      if (typeof va === "string" && typeof vb === "string") {
        return sortAsc ? va.localeCompare(vb) : vb.localeCompare(va);
      }
      const na = Number(va ?? 0);
      const nb = Number(vb ?? 0);
      return sortAsc ? na - nb : nb - na;
    });
  }, [rows, filterSource, sortKey, sortAsc]);

  function toggle(key: SortKey) {
    if (key === sortKey) setSortAsc((p) => !p);
    else {
      setSortKey(key);
      setSortAsc(false);
    }
  }

  if (!rows.length) {
    return (
      <div className="text-sm text-muted-foreground text-center py-8">
        Loading accidents...
      </div>
    );
  }

  return (
    <div className="overflow-x-auto text-xs">
      <table className="w-full border-collapse">
        <thead>
          <tr className="border-b bg-muted/40">
            <SortableHeader
              label="Name"
              active={sortKey === "name"}
              asc={sortAsc}
              onClick={() => toggle("name")}
            />
            <SortableHeader
              label="Year"
              active={sortKey === "year"}
              asc={sortAsc}
              onClick={() => toggle("year")}
              align="right"
            />
            <th className="px-2 py-1.5 text-left font-medium">Country</th>
            <th className="px-2 py-1.5 text-left font-medium">Type</th>
            <SortableHeader
              label="Direct deaths"
              active={sortKey === "direct_deaths"}
              asc={sortAsc}
              onClick={() => toggle("direct_deaths")}
              align="right"
            />
            <SortableHeader
              label="Est. high"
              active={sortKey === "estimated_deaths_high"}
              asc={sortAsc}
              onClick={() => toggle("estimated_deaths_high")}
              align="right"
            />
            <th className="px-2 py-1.5 text-left font-medium">Description</th>
            <th className="px-2 py-1.5 text-left font-medium">Ref.</th>
          </tr>
        </thead>
        <tbody>
          {view.map((r) => (
            <tr key={r.id} className="border-b hover:bg-muted/20 align-top">
              <td className="px-2 py-1.5 font-medium">{r.name}</td>
              <td className="px-2 py-1.5 text-right tabular-nums">{r.year}</td>
              <td className="px-2 py-1.5">{r.country}</td>
              <td className="px-2 py-1.5">
                <SourceTypeBadge type={r.source_type} />
              </td>
              <td className="px-2 py-1.5 text-right tabular-nums">
                {r.direct_deaths.toLocaleString()}
              </td>
              <td className="px-2 py-1.5 text-right tabular-nums">
                {r.estimated_deaths_high.toLocaleString()}
              </td>
              <td className="px-2 py-1.5 max-w-lg text-muted-foreground">
                {r.short_description}
              </td>
              <td className="px-2 py-1.5">
                {r.references.map((url, i) => (
                  <a
                    key={url}
                    href={url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-0.5 text-blue-600 hover:underline mr-1"
                    title={url}
                  >
                    [{i + 1}]<ExternalLink className="h-2.5 w-2.5" />
                  </a>
                ))}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SortableHeader({
  label,
  active,
  asc,
  onClick,
  align = "left",
}: {
  label: string;
  active: boolean;
  asc: boolean;
  onClick: () => void;
  align?: "left" | "right";
}) {
  return (
    <th
      className={cn(
        "px-2 py-1.5 font-medium cursor-pointer select-none",
        align === "right" ? "text-right" : "text-left"
      )}
      onClick={onClick}
    >
      <span className="inline-flex items-center gap-1">
        {label}
        {active &&
          (asc ? (
            <ArrowUp className="h-3 w-3" />
          ) : (
            <ArrowDown className="h-3 w-3" />
          ))}
      </span>
    </th>
  );
}

function SourceTypeBadge({ type }: { type: string }) {
  const colors: Record<string, string> = {
    Hydro: "bg-cyan-100 text-cyan-900",
    Nuclear: "bg-purple-100 text-purple-900",
    Coal: "bg-stone-200 text-stone-900",
    "Oil & Gas": "bg-orange-100 text-orange-900",
  };
  return (
    <span
      className={cn(
        "inline-block rounded px-1.5 py-0.5 text-[10px] font-medium whitespace-nowrap",
        colors[type] ?? "bg-muted text-foreground"
      )}
    >
      {type}
    </span>
  );
}
