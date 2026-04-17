/**
 * Plot wrapper that handles the CJS/ESM interop for react-plotly.js.
 *
 * Background: react-plotly.js is a CommonJS-only package. Under Vite the
 * module shape can end up double-wrapped — ``{default: {default: fn}}`` —
 * because ``react-plotly.js/factory`` is a sub-path that is not auto-
 * converted to ESM the same way top-level packages are. Direct default
 * imports then fail at runtime with "createPlotlyComponent is not a
 * function".
 *
 * Strategy: namespace-import the factory and probe up to two ``.default``
 * levels to find the callable. This is robust against both the
 * ``{default: fn}`` and ``{default: {default: fn}}`` shapes. The
 * pre-bundled ``plotly.js/dist/plotly.min.js`` is used instead of the raw
 * source to avoid Node-only deps (``buffer``, ``stream``, ``assert``).
 */
import * as factoryModule from "react-plotly.js/factory";
// @ts-expect-error — the dist file ships with no TypeScript types
import * as plotlyModule from "plotly.js/dist/plotly.min.js";

type Factory = (plotly: unknown) => React.ComponentType<Record<string, unknown>>;

function unwrapDefault<T = unknown>(mod: unknown): T {
  // Walk up to two levels of ``.default`` wrapping, stop as soon as we
  // hit a callable (factory) or a non-object (the plotly bundle root).
  let current: unknown = mod;
  for (let depth = 0; depth < 3; depth++) {
    if (typeof current === "function") return current as T;
    if (
      current &&
      typeof current === "object" &&
      "default" in current
    ) {
      current = (current as { default: unknown }).default;
      continue;
    }
    break;
  }
  return current as T;
}

const createPlotlyComponent = unwrapDefault<Factory>(factoryModule);

if (typeof createPlotlyComponent !== "function") {
  throw new Error(
    "Plot.tsx: react-plotly.js/factory did not expose a callable factory. " +
      "Inspect the module namespace shape in the browser devtools."
  );
}

const Plotly = unwrapDefault(plotlyModule);

export const Plot = createPlotlyComponent(Plotly);
