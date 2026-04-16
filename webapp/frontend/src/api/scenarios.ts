/**
 * TanStack Query hooks and mutation helpers for the scenarios API.
 *
 * Uses the shared axios client (@/api/client). Queries are cached
 * under typed query keys for automatic refetch/invalidation.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import type {
  DefaultsResponse,
  ScenarioCreate,
  ScenarioListItem,
  ScenarioResponse,
} from "@/types/api";

const SCENARIOS_KEY = ["scenarios"] as const;

/** Fetch the full list of saved scenarios. */
export function useScenarios() {
  return useQuery({
    queryKey: SCENARIOS_KEY,
    queryFn: async (): Promise<ScenarioListItem[]> => {
      const res = await api.get<ScenarioListItem[]>("/api/scenarios");
      return res.data;
    },
  });
}

/** Fetch a single scenario by ID with its full config. */
export function useScenario(id: number | null) {
  return useQuery({
    queryKey: ["scenario", id],
    enabled: id !== null,
    queryFn: async (): Promise<ScenarioResponse> => {
      const res = await api.get<ScenarioResponse>(`/api/scenarios/${id}`);
      return res.data;
    },
  });
}

/** Fetch default config values from the backend. */
export function useDefaults() {
  return useQuery({
    queryKey: ["defaults"],
    staleTime: Infinity, // Defaults never change
    queryFn: async (): Promise<DefaultsResponse> => {
      const res = await api.get<DefaultsResponse>("/api/scenarios/defaults");
      return res.data;
    },
  });
}

/** Create a new scenario. Invalidates the scenarios list on success. */
export function useCreateScenario() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: ScenarioCreate): Promise<ScenarioResponse> => {
      const res = await api.post<ScenarioResponse>("/api/scenarios", body);
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: SCENARIOS_KEY });
    },
  });
}

/** Update an existing scenario. Invalidates list and individual scenario. */
export function useUpdateScenario() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      id,
      body,
    }: {
      id: number;
      body: ScenarioCreate;
    }): Promise<ScenarioResponse> => {
      const res = await api.put<ScenarioResponse>(
        `/api/scenarios/${id}`,
        body
      );
      return res.data;
    },
    onSuccess: (_, { id }) => {
      qc.invalidateQueries({ queryKey: SCENARIOS_KEY });
      qc.invalidateQueries({ queryKey: ["scenario", id] });
    },
  });
}

/** Delete a scenario. Invalidates the list. */
export function useDeleteScenario() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number): Promise<void> => {
      await api.delete(`/api/scenarios/${id}`);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: SCENARIOS_KEY });
    },
  });
}
