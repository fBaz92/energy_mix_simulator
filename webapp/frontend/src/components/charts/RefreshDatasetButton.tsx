/**
 * Inline refresh control for a remote dataset.
 *
 * Triggers POST /api/datasets/{slug}/refresh and shows a loading
 * spinner while the request is in flight. Static datasets hide the
 * button entirely — there is nothing to refresh from.
 */
import { Loader2, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useRefreshDataset } from "@/api/datasets";

interface RefreshDatasetButtonProps {
  slug: string;
  /** Kind of the dataset — ``"static"`` hides the button. */
  kind: "remote" | "static";
}

export function RefreshDatasetButton({
  slug,
  kind,
}: RefreshDatasetButtonProps) {
  const mutation = useRefreshDataset();
  if (kind !== "remote") return null;
  return (
    <Button
      variant="ghost"
      size="sm"
      disabled={mutation.isPending}
      onClick={() => mutation.mutate(slug)}
      className="h-7 px-2 text-xs"
      title="Re-fetch from upstream (Our World in Data)"
    >
      {mutation.isPending ? (
        <Loader2 className="h-3 w-3 animate-spin" />
      ) : (
        <RefreshCw className="h-3 w-3" />
      )}
      <span className="ml-1">Refresh</span>
    </Button>
  );
}
