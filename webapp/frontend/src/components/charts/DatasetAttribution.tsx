/**
 * Small attribution + freshness footer rendered under dataset charts.
 *
 * Surfaces the licence, attribution text, and fetch timestamp from the
 * DatasetMeta returned by the backend. For remote datasets with a
 * stale cache (upstream fetch failed) the footer shows a warning
 * badge so users know they're reading a snapshot.
 */
import { AlertTriangle, ExternalLink } from "lucide-react";
import type { DatasetMeta } from "@/types/api";

export function DatasetAttribution({ meta }: { meta: DatasetMeta | undefined }) {
  if (!meta) return null;
  const fetched = meta.fetched_at
    ? new Date(meta.fetched_at).toLocaleDateString()
    : null;
  return (
    <div className="text-[11px] text-muted-foreground leading-snug pt-2 border-t mt-2 space-y-1">
      {meta.is_stale && (
        <div className="flex items-center gap-1 text-amber-600 font-medium">
          <AlertTriangle className="h-3 w-3" />
          Stale cache — most recent upstream refresh failed.
        </div>
      )}
      <div>
        <span className="font-medium">Source:</span> {meta.attribution}
        {meta.source_url && (
          <>
            {" "}
            <a
              href={meta.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-0.5 underline decoration-dotted hover:text-foreground"
            >
              link <ExternalLink className="h-2.5 w-2.5" />
            </a>
          </>
        )}
        {fetched && <span className="ml-1">· fetched {fetched}</span>}
      </div>
    </div>
  );
}
