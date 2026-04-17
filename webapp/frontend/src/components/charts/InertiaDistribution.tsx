/**
 * Distribution of mean system inertia across MC runs.
 *
 * A vertical line marks the H_MIN threshold (3.5 s). Runs below this
 * line indicate potential stability issues — but since the dispatch
 * engine enforces the constraint, all values should be comfortably above.
 */
import type { Data } from "plotly.js";
import { Plot } from "./Plot";
import { baseLayout, plotlyConfig } from "./plotlyConfig";

interface InertiaDistributionProps {
  avgInertia: number[];
}

const H_MIN = 3.5;

export function InertiaDistribution({ avgInertia }: InertiaDistributionProps) {
  const trace: Data = {
    type: "histogram",
    x: avgInertia,
    marker: { color: "#10b981", opacity: 0.7 },
    nbinsx: Math.min(20, Math.max(5, Math.round(avgInertia.length / 2))),
  } as Data;

  return (
    <Plot
      data={[trace]}
      layout={{
        ...baseLayout(),
        height: 280,
        xaxis: {
          ...baseLayout().xaxis,
          title: { text: "Mean inertia H (seconds)" },
        },
        yaxis: {
          ...baseLayout().yaxis,
          title: { text: "MC runs" },
        },
        shapes: [
          {
            type: "line",
            x0: H_MIN,
            x1: H_MIN,
            yref: "paper",
            y0: 0,
            y1: 1,
            line: { color: "#ef4444", width: 2, dash: "dash" },
          },
        ],
        annotations: [
          {
            x: H_MIN,
            yref: "paper",
            y: 1.02,
            text: `H_min = ${H_MIN}s`,
            showarrow: false,
            font: { color: "#ef4444", size: 11 },
          },
        ],
      }}
      config={plotlyConfig}
      style={{ width: "100%" }}
      useResizeHandler
    />
  );
}
