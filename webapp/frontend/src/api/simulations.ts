/**
 * TanStack Query hooks for the simulations API.
 *
 * The poll hook (useSimulation) auto-refetches every 500ms while the
 * simulation is pending or running, and stops polling once it completes.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import type {
  SimulationFullResult,
  SimulationSummary,
} from "@/types/api";

const SIMULATIONS_KEY = ["simulations"] as const;

/** Fetch the list of all simulations. */
export function useSimulations() {
  return useQuery({
    queryKey: SIMULATIONS_KEY,
    queryFn: async (): Promise<SimulationSummary[]> => {
      const res = await api.get<SimulationSummary[]>("/api/simulations");
      return res.data;
    },
  });
}

/**
 * Poll a single simulation. Refetches every 500ms while status is
 * pending or running, stops once completed or failed.
 */
export function useSimulation(id: number | null) {
  return useQuery({
    queryKey: ["simulation", id],
    enabled: id !== null,
    refetchInterval: (q) => {
      const data = q.state.data as SimulationSummary | undefined;
      if (!data) return 500;
      if (data.status === "pending" || data.status === "running") return 500;
      return false;
    },
    queryFn: async (): Promise<SimulationSummary> => {
      const res = await api.get<SimulationSummary>(`/api/simulations/${id}`);
      return res.data;
    },
  });
}

/** Fetch the full MC result arrays for a completed simulation. */
export function useSimulationResults(id: number | null) {
  return useQuery({
    queryKey: ["simulation-results", id],
    enabled: id !== null,
    staleTime: Infinity, // Results are immutable
    queryFn: async (): Promise<SimulationFullResult> => {
      const res = await api.get<SimulationFullResult>(
        `/api/simulations/${id}/results`
      );
      return res.data;
    },
  });
}

/** Launch a new simulation for a scenario. */
export function useLaunchSimulation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (scenarioId: number): Promise<SimulationSummary> => {
      const res = await api.post<SimulationSummary>("/api/simulations", {
        scenario_id: scenarioId,
      });
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: SIMULATIONS_KEY });
    },
  });
}

/** Delete a simulation and its results. */
export function useDeleteSimulation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number): Promise<void> => {
      await api.delete(`/api/simulations/${id}`);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: SIMULATIONS_KEY });
    },
  });
}
