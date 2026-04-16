/**
 * Root application component.
 *
 * Wraps the router in:
 * - QueryClientProvider for TanStack Query.
 * - React Router for page navigation.
 *
 * Routes:
 *   /                 -> redirect to /scenarios
 *   /scenarios        -> ScenariosPage
 *   /simulations      -> SimulationsPage
 *   /simulations/:id  -> SimulationDetailPage
 *   /compare          -> ComparePage
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
} from "react-router-dom";
import { AppShell } from "@/components/layout/AppShell";
import { ScenariosPage } from "@/pages/ScenariosPage";
import { SimulationsPage } from "@/pages/SimulationsPage";
import { SimulationDetailPage } from "@/pages/SimulationDetailPage";
import { ComparePage } from "@/pages/ComparePage";

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
            <Route path="/scenarios" element={<ScenariosPage />} />
            <Route path="/simulations" element={<SimulationsPage />} />
            <Route
              path="/simulations/:id"
              element={<SimulationDetailPage />}
            />
            <Route path="/compare" element={<ComparePage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
