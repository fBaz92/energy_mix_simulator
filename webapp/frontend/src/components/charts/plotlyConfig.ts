/**
 * Shared Plotly configuration and layout defaults.
 *
 * Centralizes chart styling so all dashboard charts share a consistent
 * look and feel. The color palette is tuned for energy mix visualisations
 * (gas = gray, solar = yellow, wind = blue, nuclear = purple, coal = dark,
 * hydro = cyan).
 */
import type { Config, Layout } from "plotly.js";

/** Shared Plotly config: disable watermark, hide mode bar by default. */
export const plotlyConfig: Partial<Config> = {
  displayModeBar: false,
  responsive: true,
};

/** Shared layout defaults (fonts, margins, transparent background). */
export function baseLayout(): Partial<Layout> {
  return {
    autosize: true,
    margin: { l: 60, r: 20, t: 30, b: 50 },
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    font: {
      family:
        "ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, sans-serif",
      size: 12,
      color: "#52525b",
    },
    xaxis: {
      gridcolor: "rgba(150,150,150,0.15)",
      zerolinecolor: "rgba(150,150,150,0.3)",
    },
    yaxis: {
      gridcolor: "rgba(150,150,150,0.15)",
      zerolinecolor: "rgba(150,150,150,0.3)",
    },
    legend: {
      orientation: "h",
      y: -0.2,
    },
  };
}

/** Technology color palette for consistent styling across charts. */
export const TECH_COLORS: Record<string, string> = {
  gas: "#94a3b8",
  solar: "#f59e0b",
  wind: "#3b82f6",
  nuclear: "#a855f7",
  coal: "#44403c",
  hydro_mustrun: "#06b6d4",
  hydro: "#06b6d4",
  import: "#10b981",
};

export function colorFor(tech: string): string {
  return TECH_COLORS[tech] ?? "#64748b";
}
