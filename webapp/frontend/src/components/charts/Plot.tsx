/**
 * Plot wrapper that handles the CJS/ESM interop for react-plotly.js.
 *
 * react-plotly.js is a CommonJS-only package. Under Vite with code-splitting,
 * the default import can come back as the module object instead of the
 * component itself (causing "Element type is invalid" runtime errors).
 *
 * We import via the factory and pass it the pre-bundled browser build
 * (``plotly.js/dist/plotly.min.js``). The pre-bundled distribution avoids
 * Node-only dependencies (``buffer``, ``stream``, ``assert``) that the
 * raw source of plotly.js pulls in for image export features.
 */
import createPlotlyComponent from "react-plotly.js/factory";
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-ignore — the dist file ships with no TypeScript types
import Plotly from "plotly.js/dist/plotly.min.js";

export const Plot = createPlotlyComponent(Plotly);
