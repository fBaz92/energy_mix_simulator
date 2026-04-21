/**
 * Smoke test for the Data Analysis page.
 *
 * Mocks every dataset endpoint with fake payloads and asserts each
 * major section renders its headline text. Guards against route /
 * import regressions — the page has eight sections and eight
 * different hooks, one broken import would take the whole page down
 * silently without this.
 */
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { Route, Routes } from "react-router-dom";
import { DataAnalysisPage } from "./DataAnalysisPage";
import { renderWithProviders } from "@/test/testUtils";
import { api } from "@/api/client";

function fakeRemoteEnvelope(slug: string, rows: unknown[]) {
  return {
    meta: {
      slug,
      title: slug,
      source_url: "https://example.org/" + slug,
      license: "CC-BY 4.0",
      attribution: "Test source",
      fetched_at: "2026-04-20T00:00:00+00:00",
      is_stale: false,
      notes: "Test notes",
      kind: "remote",
    },
    rows,
    payload: null,
  };
}

function fakeStaticEnvelope(slug: string, rows: unknown[] | null,
                             payload: unknown | null = null) {
  return {
    meta: {
      slug,
      title: slug,
      source_url: "",
      license: "Curated",
      attribution: "Test curation",
      fetched_at: "2026-04-20T00:00:00+00:00",
      is_stale: false,
      notes: "",
      kind: "static",
    },
    rows,
    payload,
  };
}

const RESPONSES: Record<string, () => unknown> = {
  "/api/datasets/deaths_per_twh": () =>
    fakeRemoteEnvelope("deaths_per_twh", [
      { source: "Coal", year: 2021, deaths_per_twh: 24.6 },
      { source: "Gas", year: 2021, deaths_per_twh: 2.8 },
    ]),
  "/api/datasets/carbon_intensity_country": () =>
    fakeRemoteEnvelope("carbon_intensity_country", [
      { country: "Italy", code: "ITA", year: 2020, gco2_kwh: 258, is_aggregate: false },
      { country: "Italy", code: "ITA", year: 2021, gco2_kwh: 240, is_aggregate: false },
    ]),
  "/api/datasets/pm25_deaths_country": () =>
    fakeRemoteEnvelope("pm25_deaths_country", [
      { country: "Italy", code: "ITA", year: 2019, deaths: 26000, is_aggregate: false },
    ]),
  "/api/datasets/lifecycle_carbon": () =>
    fakeStaticEnvelope("lifecycle_carbon", [
      {
        source: "Coal",
        median_gco2eq_kwh: 820,
        p5_gco2eq_kwh: 740,
        p95_gco2eq_kwh: 910,
        notes: "",
        reference: "",
      },
    ]),
  "/api/datasets/land_use": () =>
    fakeStaticEnvelope("land_use", [
      {
        source: "Nuclear",
        median_m2_per_mwh: 0.1,
        p5_m2_per_mwh: 0.05,
        p95_m2_per_mwh: 0.31,
      },
    ]),
  "/api/datasets/accidents": () =>
    fakeStaticEnvelope("accidents", [
      {
        id: "banqiao-1975",
        name: "Banqiao and Shimantan dam failures",
        year: 1975,
        country: "China",
        source_type: "Hydro",
        direct_deaths: 26000,
        estimated_deaths_low: 85000,
        estimated_deaths_high: 240000,
        short_description: "Typhoon Nina.",
        references: ["https://example.org/banqiao"],
      },
    ]),
  "/api/datasets/fossil_pollution_deaths": () =>
    fakeStaticEnvelope("fossil_pollution_deaths", null, {
      headline: {
        global_annual_deaths_from_fossil_pm25: {
          vohra_2021_central: 8700000,
          lelieveld_2019_central: 3610000,
          burnett_2018_central: 3450000,
        },
        commentary: "",
      },
      by_source: [
        {
          source: "Coal",
          annual_global_deaths_vohra_2021: 3900000,
          share_of_fossil_total_pct: 45,
          notes: "",
          reference: "",
        },
      ],
      by_region: [],
      historical_famous_events: [],
    }),
  "/api/datasets/nuclear_waste": () =>
    fakeStaticEnvelope("nuclear_waste", null, {
      headline: {
        spent_fuel_per_mwh_electrical_g: 3.3,
        hlw_per_mwh_after_reprocessing_g: 0.3,
        llw_and_ilw_per_mwh_g: 80,
        coal_ash_per_mwh_kg: 90,
        coal_ash_comparison_note: "Coal ash contains more heavy metals.",
      },
      categories: [
        {
          category: "HLW",
          full_name: "High Level Waste",
          share_of_waste_volume_pct: 3,
          share_of_waste_radioactivity_pct: 95,
          typical_contents: "Spent fuel",
          disposal: "Deep repository",
          hazard_lifetime_years: 250000,
        },
      ],
      global_stockpile_2023: {
        spent_fuel_in_storage_tonnes_hm: 400000,
        spent_fuel_in_dry_cask_tonnes_hm: 120000,
        spent_fuel_in_pool_tonnes_hm: 260000,
        annual_production_tonnes_hm_per_year: 12000,
        notes: "",
      },
      size_comparison: {
        description: "Fits in a football field.",
        hlw_volume_m3_cumulative_worldwide: 400000,
        coal_ash_volume_m3_annual_worldwide: 800000000,
        ratio: "2000x",
      },
      deep_geological_repositories: [
        {
          name: "Onkalo",
          country: "Finland",
          status: "Operating",
          host_rock: "Granite",
          depth_m: 440,
          planned_capacity_tonnes_hm: 6500,
          operator: "Posiva",
        },
      ],
      reprocessing_status: {
        description: "",
        countries_operating: [],
        "countries_with_once-through_only": [],
        proliferation_concern: "",
      },
      references: [],
    }),
};

describe("DataAnalysisPage", () => {
  beforeEach(() => {
    vi.spyOn(api, "get").mockImplementation(async (url: string) => {
      const factory = RESPONSES[url];
      if (factory) return { data: factory() } as never;
      throw new Error("unexpected url: " + url);
    });
  });

  afterEach(() => vi.restoreAllMocks());

  it("renders all eight sections", async () => {
    renderWithProviders(
      <Routes>
        <Route path="/" element={<DataAnalysisPage />} />
      </Routes>
    );

    // Static headers render synchronously — start with those.
    expect(
      screen.getByRole("heading", { name: /data analysis/i, level: 1 })
    ).toBeInTheDocument();

    // The section titles the user needs to recognise.
    expect(
      screen.getByRole("heading", {
        name: /carbon intensity per source/i,
      })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", {
        name: /deaths per unit of energy produced/i,
      })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /major energy accidents/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /hydroelectric disasters/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", {
        name: /air pollution deaths from fossil fuels/i,
      })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /land use per unit of energy/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /nuclear waste management/i })
    ).toBeInTheDocument();

    // Once fossil fuel data loads, the Vohra headline text should appear.
    await waitFor(() =>
      expect(screen.getByText(/8\.7M/i)).toBeInTheDocument()
    );
  });
});
