/**
 * Vitest setup file — runs before every test.
 * Extends Jest's ``expect`` with Testing Library matchers (toBeInTheDocument, etc.).
 */
import "@testing-library/jest-dom/vitest";

// jsdom does not implement ResizeObserver, which Radix UI primitives
// (Slider, Tabs trigger width measurement, etc.) need. Provide a shim
// that immediately reports a non-zero size so Radix's position math
// (e.g. "calc(X% + Y px)" on Slider thumbs) doesn't divide by zero.
if (typeof globalThis.ResizeObserver === "undefined") {
  class ResizeObserverStub {
    private cb: (entries: unknown[]) => void;
    constructor(cb: (entries: unknown[]) => void) {
      this.cb = cb;
    }
    observe(target: Element) {
      // Report a reasonable layout box so Radix doesn't produce NaN.
      queueMicrotask(() => {
        this.cb([
          {
            target,
            contentRect: {
              width: 200,
              height: 20,
              x: 0,
              y: 0,
              top: 0,
              left: 0,
              right: 200,
              bottom: 20,
            },
            borderBoxSize: [{ inlineSize: 200, blockSize: 20 }],
            contentBoxSize: [{ inlineSize: 200, blockSize: 20 }],
            devicePixelContentBoxSize: [{ inlineSize: 200, blockSize: 20 }],
          },
        ]);
      });
    }
    unobserve() {}
    disconnect() {}
  }
  (globalThis as { ResizeObserver?: unknown }).ResizeObserver =
    ResizeObserverStub;
}

// jsdom returns 0 for every layout measurement, which makes Radix's
// Slider thumb position collapse to ``calc(NaN% + 0px)``. Report a
// reasonable bounding box so the CSS parser can consume the output.
if (typeof Element !== "undefined") {
  const original = Element.prototype.getBoundingClientRect;
  Element.prototype.getBoundingClientRect = function () {
    const result = original.call(this) as DOMRect;
    if (result.width === 0 && result.height === 0) {
      return {
        width: 200,
        height: 20,
        x: 0,
        y: 0,
        top: 0,
        left: 0,
        right: 200,
        bottom: 20,
        toJSON() {
          return {};
        },
      } as DOMRect;
    }
    return result;
  };
}
