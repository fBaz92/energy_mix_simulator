"""Catalog of external and curated datasets served by the webapp.

Two kinds of specs live here:

- :class:`DatasetSpec` — datasets fetched over HTTP from Our World in
  Data (CC-BY 4.0). Values change slowly (annual cadence), so the
  default TTL is 7 days and refresh is triggered lazily on read or
  explicitly via ``POST /api/datasets/{slug}/refresh``. The parser is a
  pure function that maps raw CSV bytes to a list of row dicts shaped
  for the frontend.

- :class:`StaticDatasetSpec` — hand-curated JSON committed under
  ``webapp/backend/data/``. Used when a clean upstream dataset does not
  exist (accidents list, nuclear waste scheda) or when upstream
  distribution is legally restricted (IHME GBD source-split pollution
  deaths are 403 on OWID, so we inline published figures with proper
  citations).

The two slug namespaces are distinct; the router first looks in
``DATASET_SPECS`` and falls back to ``STATIC_DATASET_SPECS``.

URL verification status (2026-04):
    - deaths_per_twh: 200 OK (verified)
    - carbon_intensity_country: 200 OK (verified)
    - pm25_deaths_country: 200 OK (verified, State of Global Air)

Other historically-named OWID slugs (lifecycle carbon, land-use per
energy, fossil-fuel-attributable pollution deaths) either 404 or are
marked non-redistributable by OWID. Their values live in
``webapp/backend/data/*.json`` with upstream references.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class DatasetSpec:
    """Specification for a remote (HTTP-fetched) dataset.

    Attributes:
        slug: Stable identifier used as the SQLite primary key and the
            URL path segment (``/api/datasets/{slug}``).
        title: Human-readable label shown in the UI catalog.
        source_url: Canonical CSV endpoint. Appending or changing
            query-string parameters should be avoided once the slug is
            pinned — the frontend caches responses.
        license: Short licence tag (``"CC-BY 4.0"``).
        attribution: One-line credit string rendered under each chart.
        parser_name: Name of the parser function in
            :mod:`webapp.backend.datasets.parsers` — looked up at call
            time so :class:`DatasetSpec` stays importable without
            pulling parser dependencies at module load.
        refresh_ttl_hours: Seconds-to-live for the cache row. After
            this age, the next ``GET`` re-fetches upstream (unless
            offline, in which case the stale row is served with
            ``is_stale=true``).
        notes: Caveat text surfaced in the UI "Notes" accordion under
            the chart. Plain prose, no markdown rendering.
    """

    slug: str
    title: str
    source_url: str
    license: str
    attribution: str
    parser_name: str
    refresh_ttl_hours: int = 168  # one week
    notes: str = ""


@dataclass(frozen=True)
class StaticDatasetSpec:
    """Specification for a curated JSON file committed to the repo.

    Attributes:
        slug: URL path segment.
        title: Human-readable label.
        filename: Basename under ``webapp/backend/data/`` (e.g.
            ``"accidents.json"``).
        attribution: Free-form citation string.
        notes: Caveat text shown in the UI.
    """

    slug: str
    title: str
    filename: str
    attribution: str
    notes: str = ""


# ---------------------------------------------------------------------------
# Remote datasets (Our World in Data, CC-BY 4.0)
# ---------------------------------------------------------------------------

_OWID_ATTRIBUTION = (
    "Our World in Data — licensed CC-BY 4.0. "
    "Fetched live from ourworldindata.org."
)


DATASET_SPECS: dict[str, DatasetSpec] = {
    "deaths_per_twh": DatasetSpec(
        slug="deaths_per_twh",
        title="Death rates per unit of energy production",
        source_url=(
            "https://ourworldindata.org/grapher/"
            "death-rates-from-energy-production-per-twh.csv"
        ),
        license="CC-BY 4.0",
        attribution=_OWID_ATTRIBUTION + " Based on Markandya & Wilkinson "
                    "(Lancet 2007) + Sovacool et al. (2016).",
        parser_name="parse_deaths_per_twh",
        notes=(
            "Global averages, single-point estimates (2021). The nuclear "
            "figure uses the lower Chernobyl-fatality estimate (WHO/IAEA "
            "~4,000 latent cancers); alternative estimates (TORCH, "
            "Greenpeace) are 10-100x higher. The hydropower figure is "
            "dominated by the 1975 Banqiao dam failure in China "
            "(~171,000 deaths); excluding Banqiao drops it by >10x."
        ),
    ),
    "carbon_intensity_country": DatasetSpec(
        slug="carbon_intensity_country",
        title="Operational carbon intensity of electricity (country-year)",
        source_url=(
            "https://ourworldindata.org/grapher/"
            "carbon-intensity-electricity.csv"
        ),
        license="CC-BY 4.0",
        attribution=_OWID_ATTRIBUTION + " Based on Ember + Energy Institute "
                    "Statistical Review of World Energy.",
        parser_name="parse_carbon_intensity_country",
        notes=(
            "OPERATIONAL intensity (gCO2/kWh at the point of generation), "
            "not lifecycle. Combustion emissions only — does not include "
            "embodied CO2 in plant construction, fuel extraction, or "
            "decommissioning. For lifecycle emissions by source, see the "
            "'Lifecycle carbon per source' section (IPCC AR6 values)."
        ),
    ),
    "pm25_deaths_country": DatasetSpec(
        slug="pm25_deaths_country",
        title="Deaths from ambient PM2.5 air pollution (country-year)",
        source_url=(
            "https://ourworldindata.org/grapher/"
            "absolute-number-of-deaths-from-ambient-particulate"
            "-air-pollution.csv"
        ),
        license="CC-BY 4.0",
        attribution=_OWID_ATTRIBUTION + " Source: Health Effects Institute, "
                    "State of Global Air.",
        parser_name="parse_pm25_deaths",
        notes=(
            "Total deaths from ambient (outdoor) PM2.5, all sources "
            "combined. Fossil-fuel combustion is the dominant contributor "
            "in most countries but the GBD methodology does not attribute "
            "deaths to specific sectors in this table. For the "
            "fossil-fuel-only split, see the 'Fossil-fuel pollution deaths' "
            "section (Vohra 2021, Lelieveld 2019 figures). PM2.5 is only "
            "one pathway; NO2 and O3 add ~40%% on top."
        ),
    ),
}


# ---------------------------------------------------------------------------
# Curated (static) datasets committed to the repo
# ---------------------------------------------------------------------------

STATIC_DATASET_SPECS: dict[str, StaticDatasetSpec] = {
    "lifecycle_carbon": StaticDatasetSpec(
        slug="lifecycle_carbon",
        title="Lifecycle carbon intensity per source (IPCC AR6)",
        filename="lifecycle_carbon.json",
        attribution=(
            "IPCC AR6 WGIII Annex III (2022); ranges reflect the 5th to "
            "95th percentile of the harmonized literature."
        ),
        notes=(
            "Lifecycle gCO2eq/kWh, cradle-to-grave: includes manufacturing, "
            "fuel extraction, construction, operation, decommissioning. "
            "Wide ranges for solar/wind reflect different grid carbon "
            "intensities during manufacturing. Nuclear range spans PWR/BWR "
            "designs and different uranium ore grades."
        ),
    ),
    "land_use": StaticDatasetSpec(
        slug="land_use",
        title="Land footprint per TWh (van Zalk & Behrens 2018)",
        filename="land_use.json",
        attribution=(
            "van Zalk & Behrens, Energy Policy 2018; additional figures "
            "from Our World in Data analysis."
        ),
        notes=(
            "Median land use in m2 per MWh (converted to km2/TWh). Does "
            "NOT include upstream mining footprint (uranium, lithium, "
            "coal), nor transmission right-of-way. For solar and wind the "
            "'direct' footprint (panels / turbine bases) is a small "
            "fraction of the 'total' project area."
        ),
    ),
    "fossil_pollution_deaths": StaticDatasetSpec(
        slug="fossil_pollution_deaths",
        title="Deaths from fossil-fuel air pollution (Vohra 2021)",
        filename="fossil_pollution_deaths.json",
        attribution=(
            "Vohra et al., Environmental Research 2021; Lelieveld et al., "
            "European Heart Journal 2019. IHME GBD source-split data is "
            "not redistributable by OWID (API 403) so figures are "
            "inlined here from the peer-reviewed publications."
        ),
        notes=(
            "All figures are annual global deaths attributable to PM2.5 "
            "from fossil-fuel combustion. Vohra (GEOS-Chem chemical "
            "transport model + GBD exposure-response) is the highest "
            "estimate; Lelieveld and Burnett use different exposure "
            "functions and give 3-5M. Coal is the single largest source. "
            "Does NOT include NOx/SO2/O3 pathways."
        ),
    ),
    "accidents": StaticDatasetSpec(
        slug="accidents",
        title="Major energy accidents",
        filename="accidents.json",
        attribution=(
            "Curated from Wikipedia, Sovacool (2016) and IAEA INES. "
            "Hydro figures from official government reports where "
            "available; otherwise Si & Qian (2008) for Banqiao and local "
            "inquiry reports for Vajont, Teton, Machchhu."
        ),
        notes=(
            "Hydro dam failures dominate direct fatalities in absolute "
            "terms — Banqiao/Shimantan 1975 alone killed more people "
            "than all commercial nuclear accidents in history combined. "
            "Nuclear 'deaths' are direct + estimated latent cancer "
            "mortality; ranges reflect the wide spread between WHO and "
            "alternative estimates."
        ),
    ),
    "nuclear_waste": StaticDatasetSpec(
        slug="nuclear_waste",
        title="Nuclear waste: volumes, categories, and repositories",
        filename="nuclear_waste.json",
        attribution=(
            "World Nuclear Association 'Radioactive Waste Management' "
            "(2024 update); IAEA NEWMDB; OECD NEA."
        ),
        notes=(
            "HLW (high-level waste) is spent fuel and reprocessing "
            "residues; LLW/VLLW is contaminated PPE, tools, building "
            "rubble. The three categories differ by 6+ orders of "
            "magnitude in radioactivity per unit volume — conflating "
            "them is the single most common mistake in public discourse."
        ),
    ),
}
