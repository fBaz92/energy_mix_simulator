/**
 * TanStack Query hooks for the sweeps API.
 *
 * Mirrors the ergonomics of :mod:`api/simulations` so the two
 * resources feel consistent to the UI: a list hook, a polling hook
 * (auto-refreshes every 500 ms while the sweep is running), an
 * on-demand results hook, plus launch / delete mutations.
 */
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { api } from "@/api/client";
import type {
  SweepCreate,
  SweepFullResult,
  SweepOut,
} from "@/types/api";

const SWEEPS_KEY = ["sweeps"] as const;

/** Fetch the list of all sweeps. */
export function useSweeps() {
  return useQuery({
    queryKey: SWEEPS_KEY,
    queryFn: async (): Promise<SweepOut[]> => {
      const res = await api.get<SweepOut[]>("/api/sweeps");
      return res.data;
    },
  });
}

/**
 * Poll a single sweep. Refetches every 500 ms while the sweep is
 * pending or running, stops once completed / failed.
 */
export function useSweep(id: number | null) {
  return useQuery({
    queryKey: ["sweep", id],
    enabled: id !== null,
    refetchInterval: (q) => {
      const data = q.state.data as SweepOut | undefined;
      if (!data) return 500;
      if (data.status === "pending" || data.status === "running") return 500;
      return false;
    },
    queryFn: async (): Promise<SweepOut> => {
      const res = await api.get<SweepOut>(`/api/sweeps/${id}`);
      return res.data;
    },
  });
}

/** Fetch the full grid-point list of a completed sweep. */
export function useSweepResults(id: number | null) {
  return useQuery({
    queryKey: ["sweep-results", id],
    enabled: id !== null,
    staleTime: Infinity,
    queryFn: async (): Promise<SweepFullResult> => {
      const res = await api.get<SweepFullResult>(
        `/api/sweeps/${id}/results`,
      );
      return res.data;
    },
  });
}

/** Launch a new sweep. */
export function useLaunchSweep() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: SweepCreate): Promise<SweepOut> => {
      const res = await api.post<SweepOut>("/api/sweeps", body);
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: SWEEPS_KEY });
    },
  });
}

/** Delete a sweep. */
export function useDeleteSweep() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number): Promise<void> => {
      await api.delete(`/api/sweeps/${id}`);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: SWEEPS_KEY });
    },
  });
}
