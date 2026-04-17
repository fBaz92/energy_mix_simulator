/**
 * Regression tests for the Plot wrapper.
 *
 * These protect against the CJS/ESM interop issues we hit twice with
 * react-plotly.js under Vite code-splitting:
 * - "Element type is invalid ... got: object" (default export wrapped)
 * - "createPlotlyComponent is not a function" (factory default wrapped)
 *
 * The tests check that Plot is a callable React component (function or
 * class), not an object or undefined.
 */
import { describe, expect, it } from "vitest";
import { Plot } from "./Plot";

describe("Plot wrapper", () => {
  it("is a valid React component (function or class)", () => {
    expect(Plot).toBeDefined();
    expect(typeof Plot).toBe("function");
  });

  it("is not a module-shaped object", () => {
    // Common CJS/ESM interop bug: Plot ends up as { default: Component }
    // instead of the component itself. Guard against that shape.
    expect(Plot).not.toHaveProperty("default");
    expect(Plot).not.toHaveProperty("__esModule");
  });
});
