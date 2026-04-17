/**
 * Regression test for the "Loading..." forever bug on invalid simulation IDs.
 *
 * Before the fix, useSimulation's `data` stayed undefined forever on a 404,
 * and the page showed "Loading..." indefinitely because the guard was
 * `if (!sim)` instead of distinguishing between loading and error states.
 */
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { Route, Routes } from "react-router-dom";
import { ResultsPage } from "./ResultsPage";
import { renderWithProviders } from "@/test/testUtils";
import { api } from "@/api/client";

function route() {
  return (
    <Routes>
      <Route path="/results/:id" element={<ResultsPage />} />
    </Routes>
  );
}

describe("ResultsPage — missing simulation", () => {
  beforeEach(() => {
    vi.spyOn(api, "get").mockImplementation(async (url: string) => {
      // Simulate the backend returning 404 for a non-existent sim
      if (url.startsWith("/api/simulations/9999")) {
        const error = new Error("Request failed with status code 404") as Error & {
          response?: unknown;
        };
        error.response = { status: 404, data: { detail: "not found" } };
        throw error;
      }
      throw new Error("unexpected url: " + url);
    });
  });

  afterEach(() => vi.restoreAllMocks());

  it("shows a not-found error instead of Loading… forever", async () => {
    renderWithProviders(route(), { initialEntries: ["/results/9999"] });

    await waitFor(() =>
      expect(screen.getByText(/simulation not found/i)).toBeInTheDocument()
    );

    expect(screen.getByText(/#9999 does not exist/i)).toBeInTheDocument();
    expect(screen.queryByText(/loading\.\.\./i)).not.toBeInTheDocument();
  });
});
