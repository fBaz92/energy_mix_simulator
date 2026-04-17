/**
 * Root application component.
 *
 * Wraps the router in:
 * - QueryClientProvider for TanStack Query.
 * - React Router for page navigation.
 * - ErrorBoundary around each route to avoid white-screen crashes.
 *
 * Pages that use Plotly (Results, Compare) are lazy-loaded so the Plotly
 * bundle (~4.5 MB) only downloads when the user actually needs a chart.
 * Suspense shows a PageSkeleton during the load.
 */
import { lazy, Suspense } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
} from "react-router-dom";
import { AppShell } from "@/components/layout/AppShell";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { PageSkeleton } from "@/components/PageSkeleton";
import { ScenariosPage } from "@/pages/ScenariosPage";
import { SimulationsPage } from "@/pages/SimulationsPage";
import { SimulationDetailPage } from "@/pages/SimulationDetailPage";

// Code-split: Plotly ships with ResultsPage and ComparePage only.
const ResultsPage = lazy(() =>
  import("@/pages/ResultsPage").then((m) => ({ default: m.ResultsPage }))
);
const ComparePage = lazy(() =>
  import("@/pages/ComparePage").then((m) => ({ default: m.ComparePage }))
);

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<Navigate to="/scenarios" replace />} />
            <Route
              path="/scenarios"
              element={
                <ErrorBoundary>
                  <ScenariosPage />
                </ErrorBoundary>
              }
            />
            <Route
              path="/simulations"
              element={
                <ErrorBoundary>
                  <SimulationsPage />
                </ErrorBoundary>
              }
            />
            <Route
              path="/simulations/:id"
              element={
                <ErrorBoundary>
                  <SimulationDetailPage />
                </ErrorBoundary>
              }
            />
            <Route
              path="/results/:id"
              element={
                <ErrorBoundary>
                  <Suspense fallback={<PageSkeleton />}>
                    <ResultsPage />
                  </Suspense>
                </ErrorBoundary>
              }
            />
            <Route
              path="/compare"
              element={
                <ErrorBoundary>
                  <Suspense fallback={<PageSkeleton />}>
                    <ComparePage />
                  </Suspense>
                </ErrorBoundary>
              }
            />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
