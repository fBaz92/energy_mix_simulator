/**
 * Heatmap of battery state-of-charge across day-of-year × hour-of-day.
 *
 * Collapses the 35 040-point SOC trace into a 365 × 24 matrix by
 * averaging over the 4 quarter-hours of each hour. Typical read: the
 * daily cycle appears as a horizontal band pattern (discharge in
 * evening, recharge overnight); seasonal drift appears as vertical
 * colour shifts. Works for any single storage unit — a dropdown lets
 * the user flip between units when the scenario has more than one.
 */
import { useMemo, useState } from "react";
import { useSimulationTimeseries } from "@/api/simulations";
import { Plot } from "./Plot";
import { baseLayout, plotlyConfig } from "./plotlyConfig";
import { QH_PER_HOUR } from "./timeseriesUtils";

interface SocDailyProfileProps {
  simulationId: number;
  run: number;
  /** Names of storage units in the simulation. */
  storageNames: string[];
}

export function SocDailyProfile({
  simulationId,
  run,
  storageNames,
}: SocDailyProfileProps) {
  const [selectedUnit, setSelectedUnit] = useState<string>(
    storageNames[0] ?? "",
  );

  const unit = storageNames.includes(selectedUnit)
    ? selectedUnit
    : storageNames[0] ?? "";

  const seriesName = useMemo(
    () => (unit ? [`storage_soc_${unit}`] : []),
    [unit],
  );

  const { data, isLoading, error } = useSimulationTimeseries(
    simulationId,
    run,
    seriesName,
  );

  if (storageNames.length === 0) {
    return (
      <div className="text-sm text-muted-foreground text-center py-8">
        No storage units in this simulation.
      </div>
    );
  }
  if (isLoading) {
    return (
      <div className="text-sm text-muted-foreground text-center py-8">
        Loading SOC profile…
      </div>
    );
  }
  const raw = data?.series[seriesName[0] ?? ""];
  if (error || !raw) {
    return (
      <div className="text-sm text-muted-foreground text-center py-8">
        SOC data unavailable for {unit}.
      </div>
    );
  }

  // Reshape 35040 qh → (365 days, 24 hours of hourly mean).
  const nDays = 365;
  const z: number[][] = Array.from({ length: 24 }, () =>
    new Array(nDays).fill(0),
  );
  for (let d = 0; d < nDays; d++) {
    for (let h = 0; h < 24; h++) {
      let s = 0;
      for (let q = 0; q < QH_PER_HOUR; q++) {
        s += raw[d * 96 + h * QH_PER_HOUR + q] ?? 0;
      }
      z[h][d] = s / QH_PER_HOUR;
    }
  }

  return (
    <div>
      {storageNames.length > 1 && (
        <div className="mb-3 flex items-center gap-2 text-sm">
          <label htmlFor="soc-unit" className="text-muted-foreground">
            Unit:
          </label>
          <select
            id="soc-unit"
            value={unit}
            onChange={(e) => setSelectedUnit(e.target.value)}
            className="rounded border border-border bg-background px-2 py-1"
          >
            {storageNames.map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </div>
      )}
      <Plot
        data={[
          {
            type: "heatmap",
            z,
            x: Array.from({ length: nDays }, (_, i) => i),
            y: Array.from({ length: 24 }, (_, i) => i),
            colorscale: "Viridis",
            zmin: 0,
            zmax: 1,
            colorbar: { title: { text: "SOC" } },
            hovertemplate:
              "Day %{x}, Hour %{y}:00<br>SOC = %{z:.2f}<extra></extra>",
          },
        ]}
        layout={{
          ...baseLayout(),
          height: 320,
          xaxis: {
            ...baseLayout().xaxis,
            title: { text: "Day of year" },
          },
          yaxis: {
            ...baseLayout().yaxis,
            title: { text: "Hour of day" },
            dtick: 3,
          },
          margin: { l: 60, r: 80, t: 20, b: 40 },
        }}
        config={plotlyConfig}
        style={{ width: "100%" }}
        useResizeHandler
      />
    </div>
  );
}
