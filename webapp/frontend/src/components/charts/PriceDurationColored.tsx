/**
 * Price duration curve coloured by the technology that set the price.
 *
 * This is the "killer chart" of the price-setter tracking feature:
 * prices are sorted high-to-low along the x-axis (share of the year)
 * and each quarter-hour carries its own colour marking which tech was
 * the price-setter at that moment. The resulting stacked-area figure
 * makes it visually obvious which technology rules the expensive hours
 * (usually gas or imports) vs. the cheap off-peak hours (usually
 * nuclear, hydro, solar).
 *
 * Implementation notes:
 * - Fetches ``marginal_price`` and ``price_setter_idx`` lazily for the
 *   selected run from the backend Parquet endpoint.
 * - Uses the ``gen_types`` metadata to collapse all virtual import
 *   links into a single ``'import'`` bucket — matching the convention
 *   used by the MC-level aggregates displayed in
 *   :mod:`PriceSetterPie` and :mod:`PriceSetterHeatmap`.
 * - Builds one stacked-area trace per technology so Plotly's native
 *   legend + hover works out of the box.
 */
import { useMemo } from "react";
import { useSimulationTimeseries } from "@/api/simulations";
import { Plot } from "./Plot";
import { baseLayout, colorFor, plotlyConfig } from "./plotlyConfig";

interface PriceDurationColoredProps {
  simulationId: number;
  run: number;
}

export function PriceDurationColored({
  simulationId,
  run,
}: PriceDurationColoredProps) {
  const { data, isLoading, error } = useSimulationTimeseries(
    simulationId,
    run,
    ["marginal_price", "price_setter_idx"],
  );

  const plotData = useMemo(() => {
    if (!data) return null;
    const prices = data.series.marginal_price;
    const setterIdx = data.series.price_setter_idx;
    if (!prices || !setterIdx) return null;

    // Map unit index → technology label. Virtual imports collapse into
    // the ``'import'`` bucket. The sentinel ``-1`` (unserved energy)
    // becomes a distinct ``'unserved'`` bucket.
    const labelFor = (idx: number): string => {
      if (idx < 0) return "unserved";
      const gt = data.gen_types[idx];
      if (gt === "import") return "import";
      return data.gen_names[idx] ?? `unit_${idx}`;
    };

    const n = prices.length;
    if (n === 0) return null;

    // Sort indices by decreasing price.
    const sortedIdx = Array.from({ length: n }, (_, i) => i).sort(
      (a, b) => prices[b] - prices[a],
    );

    // For a stacked area "one bucket fills one time slot" rendering,
    // build one trace per tech. Each trace has y = price at that slot
    // if this tech was the setter, NaN otherwise. Plotly will stack
    // them vertically — since only one tech is non-NaN per x, this is
    // equivalent to a coloured fill under the single curve without
    // duplicating the data.
    const byTech: Record<string, { x: number[]; y: number[] }> = {};
    for (let k = 0; k < n; k++) {
      const origIdx = sortedIdx[k];
      const tech = labelFor(setterIdx[origIdx]);
      if (!(tech in byTech)) byTech[tech] = { x: [], y: [] };
      byTech[tech].x.push(k);
      byTech[tech].y.push(prices[origIdx]);
    }

    // Sort techs by contribution (count of points) descending so the
    // most-common price-setter anchors the legend.
    const orderedTechs = Object.keys(byTech).sort(
      (a, b) => byTech[b].x.length - byTech[a].x.length,
    );

    return {
      traces: orderedTechs.map((tech) => ({
        type: "scattergl" as const,
        mode: "markers" as const,
        x: byTech[tech].x,
        y: byTech[tech].y,
        marker: {
          color: tech === "unserved" ? "#6b7280" : colorFor(tech),
          size: 2,
        },
        name: `${tech} (${((byTech[tech].x.length / n) * 100).toFixed(1)}%)`,
        hovertemplate: `<b>${tech}</b><br>Hour %{x}<br>%{y:.1f} EUR/MWh<extra></extra>`,
      })),
      nPoints: n,
    };
  }, [data]);

  if (isLoading) {
    return (
      <div className="text-sm text-muted-foreground text-center py-8">
        Loading price-setter duration curve…
      </div>
    );
  }
  if (error || !plotData) {
    return (
      <div className="text-sm text-muted-foreground text-center py-8">
        Duration curve data unavailable.
      </div>
    );
  }

  return (
    <Plot
      data={plotData.traces}
      layout={{
        ...baseLayout(),
        height: 320,
        xaxis: {
          ...baseLayout().xaxis,
          title: { text: "Sorted quarter-hour (most expensive → cheapest)" },
          range: [0, plotData.nPoints - 1],
        },
        yaxis: {
          ...baseLayout().yaxis,
          title: { text: "Marginal price (EUR/MWh)" },
        },
        legend: {
          orientation: "h",
          y: -0.2,
          itemsizing: "constant",
        },
        margin: { l: 60, r: 20, t: 20, b: 60 },
      }}
      config={plotlyConfig}
      style={{ width: "100%" }}
      useResizeHandler
    />
  );
}
