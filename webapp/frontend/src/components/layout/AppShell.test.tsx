/**
 * Navigation tests for the AppShell sidebar.
 *
 * Checks that the three sidebar links exist, point at the correct paths,
 * and that clicking them routes to those paths (the "se clicco sul menu
 * a fianco non cambia la pagina" bug).
 */
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  MemoryRouter,
  Route,
  Routes,
  useLocation,
} from "react-router-dom";
import { AppShell } from "./AppShell";

/**
 * Probe component that exposes the current pathname in the DOM so tests
 * can assert that navigation actually occurred.
 */
function LocationProbe() {
  const loc = useLocation();
  return <div data-testid="location">{loc.pathname}</div>;
}

function renderShell(initialPath = "/scenarios") {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route element={<AppShell />}>
          <Route path="/scenarios" element={<LocationProbe />} />
          <Route path="/simulations" element={<LocationProbe />} />
          <Route path="/compare" element={<LocationProbe />} />
          <Route path="/results/:id" element={<LocationProbe />} />
        </Route>
      </Routes>
    </MemoryRouter>
  );
}

describe("AppShell navigation", () => {
  it("renders the three primary nav links", () => {
    renderShell();
    expect(screen.getByRole("link", { name: /scenarios/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /simulations/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /compare/i })).toBeInTheDocument();
  });

  it("navigates to /simulations when the Simulations link is clicked", async () => {
    const user = userEvent.setup();
    renderShell("/scenarios");

    await user.click(screen.getByRole("link", { name: /simulations/i }));

    expect(screen.getByTestId("location")).toHaveTextContent("/simulations");
  });

  it("navigates to /compare from a deep route like /results/:id", async () => {
    // Regression: sidebar was reported as not changing the page when
    // starting from /results/X (which had just thrown a render error).
    const user = userEvent.setup();
    renderShell("/results/42");

    await user.click(screen.getByRole("link", { name: /compare/i }));

    expect(screen.getByTestId("location")).toHaveTextContent("/compare");
  });
});
