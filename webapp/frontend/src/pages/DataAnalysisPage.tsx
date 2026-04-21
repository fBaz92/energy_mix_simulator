/**
 * Data Analysis page — external dataset dashboard.
 *
 * Layout follows the same scroll-with-border-t pattern as ResultsPage
 * so the narrative flow is preserved. Eight sections in this order:
 * 1. Carbon intensity per source (lifecycle, IPCC AR6)
 * 2. Carbon intensity over time (operational, country-year, Ember)
 * 3. Deaths per TWh by source (OWID)
 * 4. Major accidents timeline + table
 * 5. Hydro disasters deep-dive (user priority)
 * 6. Fossil-fuel air pollution deaths (Vohra 2021 by source + Pm25 country data)
 * 7. Land use per TWh (van Zalk 2018)
 * 8. Nuclear waste scheda (volumes, categories, repositories)
 */
import { AlertCircle } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { ChartCard } from "@/components/charts/ChartCard";
import { DatasetAttribution } from "@/components/charts/DatasetAttribution";
import { RefreshDatasetButton } from "@/components/charts/RefreshDatasetButton";
import { LifecycleCarbonBar } from "@/components/charts/LifecycleCarbonBar";
import { CarbonIntensityTrend } from "@/components/charts/CarbonIntensityTrend";
import { DeathsPerTwhBar } from "@/components/charts/DeathsPerTwhBar";
import { AccidentsTimeline } from "@/components/charts/AccidentsTimeline";
import { AccidentsTable } from "@/components/charts/AccidentsTable";
import { HydroDisastersBar } from "@/components/charts/HydroDisastersBar";
import { Pm25DeathsByCountry } from "@/components/charts/Pm25DeathsByCountry";
import { FossilPollutionBySource } from "@/components/charts/FossilPollutionBySource";
import { LandUseBar } from "@/components/charts/LandUseBar";
import { NuclearWasteCard } from "@/components/charts/NuclearWasteCard";
import {
  useAccidents,
  useCarbonIntensityCountry,
  useDeathsPerTwh,
  useFossilPollution,
  useLandUse,
  useLifecycleCarbon,
  useNuclearWaste,
  usePm25Deaths,
} from "@/api/datasets";

export function DataAnalysisPage() {
  const lifecycle = useLifecycleCarbon();
  const carbonTrend = useCarbonIntensityCountry();
  const deaths = useDeathsPerTwh();
  const accidents = useAccidents();
  const pm25 = usePm25Deaths();
  const fossil = useFossilPollution();
  const landUse = useLandUse();
  const nuclearWaste = useNuclearWaste();

  return (
    <div className="p-8 space-y-6 max-w-[1400px]">
      <header className="space-y-2">
        <h1 className="text-2xl font-bold tracking-tight">Data Analysis</h1>
        <p className="text-sm text-muted-foreground max-w-3xl">
          Real-world reference metrics for energy sources: lifecycle carbon
          intensity, mortality per TWh produced, major historical accidents,
          pollution-attributable deaths, land footprint, and nuclear waste
          volumes. Most remote datasets are pulled automatically from Our
          World in Data (CC-BY 4.0) and cached for one week; use each
          section's "Refresh" button to force an immediate re-fetch.
        </p>
      </header>

      {/* ==================== Section 1: Lifecycle carbon ==================== */}
      <section className="space-y-3 pt-2">
        <SectionHeader
          title="Carbon intensity per source (lifecycle)"
          subtitle="Cradle-to-grave CO₂eq per kWh by technology — IPCC AR6"
        />
        <ChartCard
          title={lifecycle.meta?.title ?? "Lifecycle carbon intensity"}
          description="Bars show median; whiskers span IPCC AR6 p5-p95. Log x-axis."
        >
          <div className="flex justify-end mb-2">
            <RefreshDatasetButton slug="lifecycle_carbon" kind="static" />
          </div>
          <LifecycleCarbonBar rows={lifecycle.rows} />
          {lifecycle.meta?.notes && <NotesBlock text={lifecycle.meta.notes} />}
          <DatasetAttribution meta={lifecycle.meta} />
        </ChartCard>
      </section>

      {/* ==================== Section 2: Carbon intensity trend ==================== */}
      <section className="space-y-3 pt-4 border-t">
        <SectionHeader
          title="Carbon intensity over time (operational)"
          subtitle="Per-country trend, Ember + Energy Institute"
        />
        <ChartCard
          title={carbonTrend.meta?.title ?? "Carbon intensity per country-year"}
          description="Operational CO₂ intensity at generation, not lifecycle. Select or search countries below the chart."
        >
          <div className="flex justify-end mb-2">
            <RefreshDatasetButton
              slug="carbon_intensity_country"
              kind="remote"
            />
          </div>
          {carbonTrend.isError ? (
            <ErrorBlock message="Could not load carbon intensity dataset." />
          ) : (
            <CarbonIntensityTrend rows={carbonTrend.rows} />
          )}
          {carbonTrend.meta?.notes && (
            <NotesBlock text={carbonTrend.meta.notes} />
          )}
          <DatasetAttribution meta={carbonTrend.meta} />
        </ChartCard>
      </section>

      {/* ==================== Section 3: Deaths per TWh ==================== */}
      <section className="space-y-3 pt-4 border-t">
        <SectionHeader
          title="Deaths per unit of energy produced"
          subtitle="Safety comparison across sources (Our World in Data)"
        />
        <ChartCard
          title={deaths.meta?.title ?? "Deaths per TWh"}
          description="Global averages, 2021. Log x-axis because range spans >1000x."
        >
          <div className="flex justify-end mb-2">
            <RefreshDatasetButton slug="deaths_per_twh" kind="remote" />
          </div>
          {deaths.isError ? (
            <ErrorBlock message="Could not load death rates dataset." />
          ) : (
            <DeathsPerTwhBar rows={deaths.rows} />
          )}
          {deaths.meta?.notes && <NotesBlock text={deaths.meta.notes} />}
          <DatasetAttribution meta={deaths.meta} />
        </ChartCard>
      </section>

      {/* ==================== Section 4: Accidents ==================== */}
      <section className="space-y-3 pt-4 border-t">
        <SectionHeader
          title="Major energy accidents"
          subtitle="Curated list of the deadliest incidents across sources"
        />
        <div className="grid grid-cols-1 gap-4">
          <ChartCard
            title="Timeline of major accidents"
            description="Marker size ∝ log(estimated deaths). Hover for details."
          >
            <AccidentsTimeline rows={accidents.rows} />
          </ChartCard>
          <ChartCard
            title="All accidents (sortable)"
            description="Click column headers to sort. Click reference numbers to open source."
          >
            <AccidentsTable rows={accidents.rows} />
            <DatasetAttribution meta={accidents.meta} />
          </ChartCard>
        </div>
      </section>

      {/* ==================== Section 5: Hydro deep-dive ==================== */}
      <section className="space-y-3 pt-4 border-t">
        <SectionHeader
          title="Hydroelectric disasters: top 10 by death toll"
          subtitle="User-requested focus — hydro dam failures dominate absolute fatality counts"
        />
        <Card>
          <CardContent className="pt-6 space-y-4">
            <p className="text-sm text-muted-foreground max-w-3xl">
              Dam failures are by far the deadliest energy accidents by
              absolute body count. <b>Banqiao 1975</b> alone killed more
              people than <em>all other civil energy accidents combined</em>.
              Despite this, hydropower's per-TWh death rate sits well below
              coal and oil because it also produces an enormous amount of
              energy — but the failure mode is catastrophic when it happens.
            </p>
            <HydroDisastersBar rows={accidents.rows} hydroOnly={true} />
            <div className="pt-2">
              <h3 className="text-sm font-semibold mb-2">
                Hydroelectric accidents only
              </h3>
              <AccidentsTable rows={accidents.rows} filterSource="Hydro" />
            </div>
          </CardContent>
        </Card>
      </section>

      {/* ==================== Section 6: Air pollution from fossil fuels ==================== */}
      <section className="space-y-3 pt-4 border-t">
        <SectionHeader
          title="Air pollution deaths from fossil fuels"
          subtitle="Not CO₂ — actual combustion-product pollution (PM2.5, NOx, SO₂)"
        />
        <Card>
          <CardContent className="pt-6 space-y-4 text-sm">
            {fossil.payload ? (
              <p className="text-muted-foreground max-w-3xl">
                The three most-cited estimates for annual global deaths from
                fossil-fuel PM2.5 differ by 2.5x because of different exposure
                models. Vohra et al. 2021 (GEOS-Chem): ≈
                <b> {(fossil.payload.headline.global_annual_deaths_from_fossil_pm25.vohra_2021_central / 1e6).toFixed(1)}M</b>
                /year. Lelieveld 2019: ≈
                <b> {(fossil.payload.headline.global_annual_deaths_from_fossil_pm25.lelieveld_2019_central / 1e6).toFixed(1)}M</b>
                . Burnett 2018: ≈
                <b> {(fossil.payload.headline.global_annual_deaths_from_fossil_pm25.burnett_2018_central / 1e6).toFixed(1)}M</b>
                . All agree coal is the single largest contributor.
              </p>
            ) : null}
          </CardContent>
        </Card>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <ChartCard
            title="Deaths by fossil-fuel category"
            description="Annual global deaths attributable to PM2.5 — Vohra et al. 2021"
          >
            <FossilPollutionBySource payload={fossil.payload} />
            <DatasetAttribution meta={fossil.meta} />
          </ChartCard>
          <ChartCard
            title="Total ambient PM2.5 deaths by country"
            description="All sources combined (fossil fuels are the dominant share worldwide). Use slider to pick a year."
          >
            <div className="flex justify-end mb-2">
              <RefreshDatasetButton slug="pm25_deaths_country" kind="remote" />
            </div>
            {pm25.isError ? (
              <ErrorBlock message="Could not load PM2.5 deaths dataset." />
            ) : (
              <Pm25DeathsByCountry rows={pm25.rows} />
            )}
            {pm25.meta?.notes && <NotesBlock text={pm25.meta.notes} />}
            <DatasetAttribution meta={pm25.meta} />
          </ChartCard>
        </div>
      </section>

      {/* ==================== Section 7: Land use ==================== */}
      <section className="space-y-3 pt-4 border-t">
        <SectionHeader
          title="Land use per unit of energy"
          subtitle="Footprint (m² per MWh) — van Zalk & Behrens 2018"
        />
        <ChartCard
          title={landUse.meta?.title ?? "Land use per TWh"}
          description="Median with p5-p95 whiskers. Log scale; biomass is ~4 orders of magnitude above nuclear."
        >
          <LandUseBar rows={landUse.rows} />
          {landUse.meta?.notes && <NotesBlock text={landUse.meta.notes} />}
          <DatasetAttribution meta={landUse.meta} />
        </ChartCard>
      </section>

      {/* ==================== Section 8: Nuclear waste ==================== */}
      <section className="space-y-3 pt-4 border-t">
        <SectionHeader
          title="Nuclear waste management"
          subtitle="Volumes, categories (VLLW/LLW/ILW/HLW), and deep geological repositories"
        />
        <Card>
          <CardContent className="pt-6">
            <NuclearWasteCard payload={nuclearWaste.payload} />
            {nuclearWaste.meta?.notes && (
              <NotesBlock text={nuclearWaste.meta.notes} />
            )}
            <DatasetAttribution meta={nuclearWaste.meta} />
          </CardContent>
        </Card>
      </section>
    </div>
  );
}

// ----------------------------- helpers ---------------------------------

function SectionHeader({
  title,
  subtitle,
}: {
  title: string;
  subtitle: string;
}) {
  return (
    <div>
      <h2 className="text-xl font-bold tracking-tight">{title}</h2>
      <p className="text-sm text-muted-foreground">{subtitle}</p>
    </div>
  );
}

function NotesBlock({ text }: { text: string }) {
  return (
    <details className="text-[11px] text-muted-foreground mt-2 border-t pt-2">
      <summary className="cursor-pointer font-medium hover:text-foreground">
        Notes &amp; caveats
      </summary>
      <p className="mt-1 leading-snug whitespace-pre-wrap">{text}</p>
    </details>
  );
}

function ErrorBlock({ message }: { message: string }) {
  return (
    <div className="flex items-center gap-2 text-sm text-destructive py-8 justify-center">
      <AlertCircle className="h-4 w-4" />
      <span>{message}</span>
    </div>
  );
}
