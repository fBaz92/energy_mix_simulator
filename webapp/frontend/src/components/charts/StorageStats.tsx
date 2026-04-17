/**
 * Per-storage-unit summary cards: annual revenue, equivalent cycles,
 * and energy cycled. Shown as a set of mini stat cards rather than
 * a chart, since each metric is a single scalar per unit.
 */
import { Card, CardContent } from "@/components/ui/card";

interface StorageStatsProps {
  names: string[];
  /** Shape (n_runs, n_storage). */
  revenueEur: number[][];
  equivalentCycles: number[][];
  avgSoc: number[][];
  energyCycledMwh: number[][];
}

function colMean(matrix: number[][], col: number): number {
  if (matrix.length === 0) return 0;
  let s = 0;
  for (const row of matrix) s += row[col];
  return s / matrix.length;
}

function colStd(matrix: number[][], col: number): number {
  if (matrix.length === 0) return 0;
  const m = colMean(matrix, col);
  let s = 0;
  for (const row of matrix) {
    const d = row[col] - m;
    s += d * d;
  }
  return Math.sqrt(s / matrix.length);
}

export function StorageStats({
  names,
  revenueEur,
  equivalentCycles,
  avgSoc,
  energyCycledMwh,
}: StorageStatsProps) {
  return (
    <div className="space-y-4">
      {names.map((name, ui) => {
        const revMean = colMean(revenueEur, ui) / 1e6;
        const revStd = colStd(revenueEur, ui) / 1e6;
        const cycMean = colMean(equivalentCycles, ui);
        const socMean = colMean(avgSoc, ui);
        const energyMean = colMean(energyCycledMwh, ui) / 1e3;

        return (
          <div key={name} className="space-y-2">
            <h4 className="text-sm font-semibold">{name}</h4>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              <Card>
                <CardContent className="pt-4 pb-4">
                  <div className="text-xs text-muted-foreground">Revenue</div>
                  <div className="text-lg font-bold">
                    {revMean >= 0 ? "+" : ""}
                    {revMean.toFixed(1)}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    ± {revStd.toFixed(1)} M€/yr
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="pt-4 pb-4">
                  <div className="text-xs text-muted-foreground">
                    Equiv. cycles
                  </div>
                  <div className="text-lg font-bold">{cycMean.toFixed(0)}</div>
                  <div className="text-xs text-muted-foreground">per year</div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="pt-4 pb-4">
                  <div className="text-xs text-muted-foreground">Avg SOC</div>
                  <div className="text-lg font-bold">{socMean.toFixed(2)}</div>
                  <div className="text-xs text-muted-foreground">fraction</div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="pt-4 pb-4">
                  <div className="text-xs text-muted-foreground">
                    Energy cycled
                  </div>
                  <div className="text-lg font-bold">
                    {energyMean.toFixed(1)}
                  </div>
                  <div className="text-xs text-muted-foreground">GWh/yr</div>
                </CardContent>
              </Card>
            </div>
          </div>
        );
      })}
    </div>
  );
}
