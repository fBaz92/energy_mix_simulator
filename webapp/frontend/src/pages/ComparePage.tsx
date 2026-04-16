/**
 * Compare page placeholder (Phase 6).
 * Will allow selecting 2-4 simulations for side-by-side analysis.
 */
import { Card, CardContent } from "@/components/ui/card";

export function ComparePage() {
  return (
    <div className="p-8 space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Compare</h1>
        <p className="text-sm text-muted-foreground">
          Compare multiple simulations side-by-side.
        </p>
      </div>
      <Card>
        <CardContent className="py-12 text-center">
          <p className="text-sm text-muted-foreground italic">
            Coming in Phase 6.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
