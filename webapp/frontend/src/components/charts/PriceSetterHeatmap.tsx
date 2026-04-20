/**
 * Heatmap of price-setter share across calendar month × hour-of-day.
 *
 * Visualises the seasonal/daily pattern of who sets the marginal price.
 * A tech selector lets the user flip between technologies — solar will
 * typically dominate midday hours in summer, gas the evening peak and
 * winter nights, imports the shoulder hours.
 *
 * Data contract: ``price_setter_by_month_hour[tech]`` has shape
 * ``(n_runs, 12, 24)`` and contains the number of hours that unit set
 * the price for each (month, hour-of-day) cell. We average across runs
 * and normalise by the cell width (≈ 30.4 h per (month, hour) cell) to
 * expose a probability-of-being-price-setter in that cell.
 */
import { useMemo, useState } from "react";
import { Plot } from "./Plot";
import { baseLayout, plotlyConfig } from "./plotlyConfig";

interface PriceSetterHeatmapProps {
  /**
   * price_setter_by_month_hour: ``{tech: [run][month 0..11][hour 0..23]}``.
   * Values are hours/year the tech set the price in that cell.
   */
  byMonthHour: Record<string, number[][][]>;
}

const MONTHS = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
];

// Average hours per (month, hour-of-day) cell across a non-leap year:
// month_days[m] / 12 summed ≈ 30.4 days per month on average, 1 h per cell.
const HOURS_PER_MONTH = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];

export function PriceSetterHeatmap({ byMonthHour }: PriceSetterHeatmapProps) {
  const techs = useMemo(
    () =>
      Object.keys(byMonthHour)
        .filter((t) => {
          const runs = byMonthHour[t];
          if (!runs || runs.length === 0) return false;
          // Exclude techs that never set the price.
          let sum = 0;
          for (const r of runs)
            for (const m of r) for (const h of m) sum += h;
          return sum > 0.01;
        })
        .sort(),
    [byMonthHour],
  );

  const [selectedTech, setSelectedTech] = useState<string>(techs[0] ?? "");

  if (techs.length === 0) {
    return (
      <div className="text-sm text-muted-foreground text-center py-8">
        No price-setter data available.
      </div>
    );
  }

  // Ensure selected tech is valid after techs list changes.
  const tech = techs.includes(selectedTech) ? selectedTech : techs[0];

  // Average across runs → (12, 24) of hours, then convert to probability
  // by dividing by the cell width (days-in-month, since 1 hour/day/month).
  const runs = byMonthHour[tech];
  const nRuns = runs.length;
  const z: number[][] = [];
  for (let m = 0; m < 12; m++) {
    const row: number[] = [];
    for (let h = 0; h < 24; h++) {
      let s = 0;
      for (let r = 0; r < nRuns; r++) s += runs[r][m][h];
      const meanHours = s / nRuns;
      // Fraction of hours in that (month, hour) cell where this tech set
      // the price. Each cell has ``HOURS_PER_MONTH[m]`` hours of that
      // hour-of-day across the year.
      row.push((meanHours / HOURS_PER_MONTH[m]) * 100);
    }
    z.push(row);
  }

  return (
    <div>
      <div className="mb-3 flex items-center gap-2 text-sm">
        <label htmlFor="ps-heatmap-tech" className="text-muted-foreground">
          Technology:
        </label>
        <select
          id="ps-heatmap-tech"
          value={tech}
          onChange={(e) => setSelectedTech(e.target.value)}
          className="rounded border border-border bg-background px-2 py-1"
        >
          {techs.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </div>
      <Plot
        data={[
          {
            type: "heatmap",
            z,
            x: Array.from({ length: 24 }, (_, i) => i),
            y: MONTHS,
            colorscale: "YlOrRd",
            zmin: 0,
            zmax: 100,
            colorbar: { title: { text: "% of hours" }, ticksuffix: "%" },
            hovertemplate:
              "<b>%{y}</b> at %{x}:00<br>%{z:.1f}% price-setter<extra></extra>",
          },
        ]}
        layout={{
          ...baseLayout(),
          height: 340,
          xaxis: {
            ...baseLayout().xaxis,
            title: { text: "Hour of day" },
            dtick: 2,
          },
          yaxis: {
            ...baseLayout().yaxis,
            autorange: "reversed",
          },
          margin: { l: 60, r: 80, t: 20, b: 50 },
        }}
        config={plotlyConfig}
        style={{ width: "100%" }}
        useResizeHandler
      />
    </div>
  );
}
