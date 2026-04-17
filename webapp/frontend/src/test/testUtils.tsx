/**
 * Shared test helpers. Wraps components in QueryClientProvider +
 * MemoryRouter so they can use TanStack Query hooks and react-router
 * navigation inside tests.
 */
import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { render, type RenderOptions } from "@testing-library/react";

export function makeClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0, staleTime: 0 },
      mutations: { retry: false },
    },
  });
}

interface Providers {
  client?: QueryClient;
  initialEntries?: string[];
}

export function renderWithProviders(
  ui: ReactNode,
  { client = makeClient(), initialEntries = ["/"] }: Providers = {},
  options?: RenderOptions
) {
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={initialEntries}>{ui}</MemoryRouter>
    </QueryClientProvider>,
    options
  );
}
