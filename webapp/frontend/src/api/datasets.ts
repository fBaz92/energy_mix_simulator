/**
 * TanStack Query hooks for the Data Analysis section.
 *
 * Each dataset is exposed as a dedicated typed hook so call sites get
 * narrow row types instead of ``unknown[]``. The shared ``useDataset``
 * helper centralises the fetch/cache wiring so adding a new dataset
 * is a one-liner on top of a backend DatasetSpec registration.
 *
 * All datasets use a long ``staleTime`` (1 hour) because they refresh
 * on the server side with a weekly TTL — the client doesn't need to
 * keep polling.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import type {
  AccidentRow,
  CarbonIntensityCountryRow,
  DatasetIndexEntry,
  DatasetResponse,
  DeathsPerTwhRow,
  FossilPollutionPayload,
  LandUseRow,
  LifecycleCarbonRow,
  NuclearWastePayload,
  Pm25DeathsRow,
} from "@/types/api";

const DATASETS_KEY = ["datasets"] as const;
const ONE_HOUR_MS = 60 * 60 * 1000;

/** Catalog of available datasets (remote + static). */
export function useDatasetCatalog() {
  return useQuery({
    queryKey: DATASETS_KEY,
    staleTime: ONE_HOUR_MS,
    queryFn: async (): Promise<DatasetIndexEntry[]> => {
      const res = await api.get<DatasetIndexEntry[]>("/api/datasets");
      return res.data;
    },
  });
}

/**
 * Low-level generic fetcher shared by every dataset hook.
 *
 * @param slug dataset slug (matches backend DatasetSpec.slug)
 * @returns TanStack Query result for the full DatasetResponse envelope.
 */
function useDataset(slug: string) {
  return useQuery({
    queryKey: ["dataset", slug],
    staleTime: ONE_HOUR_MS,
    queryFn: async (): Promise<DatasetResponse> => {
      const res = await api.get<DatasetResponse>(
        `/api/datasets/${slug}`
      );
      return res.data;
    },
  });
}

/** Deaths per TWh by energy source (OWID). */
export function useDeathsPerTwh() {
  const q = useDataset("deaths_per_twh");
  return {
    ...q,
    rows: (q.data?.rows ?? []) as unknown as DeathsPerTwhRow[],
    meta: q.data?.meta,
  };
}

/** Operational carbon intensity of electricity (country-year, Ember). */
export function useCarbonIntensityCountry() {
  const q = useDataset("carbon_intensity_country");
  return {
    ...q,
    rows: (q.data?.rows ?? []) as unknown as CarbonIntensityCountryRow[],
    meta: q.data?.meta,
  };
}

/** PM2.5 deaths (country-year, State of Global Air). */
export function usePm25Deaths() {
  const q = useDataset("pm25_deaths_country");
  return {
    ...q,
    rows: (q.data?.rows ?? []) as unknown as Pm25DeathsRow[],
    meta: q.data?.meta,
  };
}

/** Lifecycle carbon intensity per source (IPCC AR6, curated). */
export function useLifecycleCarbon() {
  const q = useDataset("lifecycle_carbon");
  return {
    ...q,
    rows: (q.data?.rows ?? []) as unknown as LifecycleCarbonRow[],
    meta: q.data?.meta,
  };
}

/** Land use per TWh (van Zalk & Behrens 2018, curated). */
export function useLandUse() {
  const q = useDataset("land_use");
  return {
    ...q,
    rows: (q.data?.rows ?? []) as unknown as LandUseRow[],
    meta: q.data?.meta,
  };
}

/** Major energy accidents (curated). */
export function useAccidents() {
  const q = useDataset("accidents");
  return {
    ...q,
    rows: (q.data?.rows ?? []) as unknown as AccidentRow[],
    meta: q.data?.meta,
  };
}

/** Fossil-fuel air-pollution deaths breakdown (Vohra 2021, curated). */
export function useFossilPollution() {
  const q = useDataset("fossil_pollution_deaths");
  return {
    ...q,
    payload: q.data?.payload as FossilPollutionPayload | undefined,
    meta: q.data?.meta,
  };
}

/** Nuclear waste scheda (volumes, categories, repositories; curated). */
export function useNuclearWaste() {
  const q = useDataset("nuclear_waste");
  return {
    ...q,
    payload: q.data?.payload as NuclearWastePayload | undefined,
    meta: q.data?.meta,
  };
}

/**
 * Mutation that forces an upstream re-fetch for a remote dataset.
 *
 * On success the per-dataset query is invalidated so the UI re-renders
 * with the fresh payload. Static datasets cannot be refreshed — the
 * backend returns 400 and TanStack Query surfaces the error.
 */
export function useRefreshDataset() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (slug: string): Promise<DatasetResponse> => {
      const res = await api.post<DatasetResponse>(
        `/api/datasets/${slug}/refresh`
      );
      return res.data;
    },
    onSuccess: (_data, slug) => {
      qc.invalidateQueries({ queryKey: ["dataset", slug] });
      qc.invalidateQueries({ queryKey: DATASETS_KEY });
    },
  });
}
