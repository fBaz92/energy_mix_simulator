/**
 * TanStack Query hooks for the simulations API.
 *
 * The poll hook (useSimulation) auto-refetches every 500ms while the
 * simulation is pending or running, and stops polling once it completes.
 */
import {
  useMutation,
  useQueries,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { api } from "@/api/client";
import type {
  SimulationFullResult,
  SimulationSummary,
  TimeseriesResponse,
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

/**
 * Fetch full results for multiple simulations in parallel.
 * Used by the Compare page to load 2-4 simulations side-by-side.
 */
export function useSimulationResultsBatch(ids: number[]) {
  return useQueries({
    queries: ids.map((id) => ({
      queryKey: ["simulation-results", id],
      staleTime: Infinity,
      queryFn: async (): Promise<SimulationFullResult> => {
        const res = await api.get<SimulationFullResult>(
          `/api/simulations/${id}/results`
        );
        return res.data;
      },
    })),
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

/**
 * Fetch only the time-series metadata (available columns, gen names,
 * gen types, storage/IC names, total run count) for a simulation.
 *
 * Uses the same endpoint as :func:`useSimulationTimeseries` but with
 * an empty ``series`` parameter so the backend skips the heavy Parquet
 * read. Cached forever — the Parquet file is immutable per simulation.
 */
export function useTimeseriesMetadata(simulationId: number | null) {
  return useQuery({
    queryKey: ["simulation-timeseries-meta", simulationId],
    enabled: simulationId !== null,
    staleTime: Infinity,
    queryFn: async (): Promise<TimeseriesResponse> => {
      const res = await api.get<TimeseriesResponse>(
        `/api/simulations/${simulationId}/timeseries`,
        { params: { run: 0, series: "" } },
      );
      return res.data;
    },
  });
}

/**
 * Lazy-load per-run quarter-hour time-series for a completed simulation.
 *
 * Requests one run at a time to keep the payload bounded. Pass an empty
 * ``series`` array (or ``null`` for ``simulationId``) to disable the
 * query — the ``available`` field in the response lists all columns
 * stored in the Parquet file, which is useful for deciding which
 * charts can be rendered for the current scenario.
 *
 * Results are immutable within a simulation, so they cache indefinitely
 * (``staleTime: Infinity``).
 */
export function useSimulationTimeseries(
  simulationId: number | null,
  run: number,
  series: string[],
) {
  const seriesKey = [...series].sort().join(",");
  return useQuery({
    queryKey: ["simulation-timeseries", simulationId, run, seriesKey],
    enabled: simulationId !== null && series.length > 0,
    staleTime: Infinity,
    queryFn: async (): Promise<TimeseriesResponse> => {
      const res = await api.get<TimeseriesResponse>(
        `/api/simulations/${simulationId}/timeseries`,
        { params: { run, series: series.join(",") } },
      );
      return res.data;
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
