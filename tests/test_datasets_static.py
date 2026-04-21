"""Schema validation for curated JSON datasets committed to the repo.

These tests catch drift during manual editing of the JSON files: a
missing field, a mistyped key, a malformed number. They do not check
editorial accuracy (that's a job for code review) but they guarantee
the files load cleanly and expose the shape the frontend consumes.
"""

from __future__ import annotations

import json

import pytest

from webapp.backend.datasets.sources import STATIC_DATASET_SPECS
from webapp.backend.datasets.static_data import (
    get_static_dataset,
    get_static_dataset_path,
)


# ---------------------------------------------------------------------------
# Every static slug must exist on disk and load as JSON.
# ---------------------------------------------------------------------------

class TestStaticFilesPresent:
    """All registered static slugs must be backed by a readable file."""

    @pytest.mark.parametrize("slug", list(STATIC_DATASET_SPECS.keys()))
    def test_file_exists_and_parses(self, slug):
        """The JSON file for every slug must exist and decode cleanly."""
        path = get_static_dataset_path(slug)
        assert path.exists(), f"Missing file for static slug '{slug}': {path}"
        # Round-trip to confirm it's valid JSON.
        with path.open("r", encoding="utf-8") as fh:
            json.load(fh)

    @pytest.mark.parametrize("slug", list(STATIC_DATASET_SPECS.keys()))
    def test_loader_envelope(self, slug):
        """``get_static_dataset`` wraps list payloads in ``{"rows": ...}``
        and dict payloads in ``{"payload": ...}``. Tests each slug's
        current envelope so a regression in the wrapper is caught."""
        envelope = get_static_dataset(slug)
        assert ("rows" in envelope) ^ ("payload" in envelope), (
            f"{slug} envelope must have exactly one of rows/payload, "
            f"got {list(envelope.keys())}")


# ---------------------------------------------------------------------------
# Per-slug schema checks
# ---------------------------------------------------------------------------

class TestLifecycleCarbonSchema:
    """Lifecycle carbon JSON: list of sources with IPCC ranges."""

    def test_rows_are_well_formed(self):
        """Each row needs source + median/p5/p95 + notes + reference."""
        rows = get_static_dataset("lifecycle_carbon")["rows"]
        assert len(rows) >= 8
        required = {"source", "median_gco2eq_kwh",
                    "p5_gco2eq_kwh", "p95_gco2eq_kwh",
                    "notes", "reference"}
        for r in rows:
            assert required <= set(r.keys()), (
                f"Row missing keys: {required - set(r.keys())}")
            assert r["p5_gco2eq_kwh"] <= r["median_gco2eq_kwh"]
            assert r["median_gco2eq_kwh"] <= r["p95_gco2eq_kwh"]

    def test_contains_core_sources(self):
        """Must include the main energy sources our simulator models."""
        rows = get_static_dataset("lifecycle_carbon")["rows"]
        sources = {r["source"] for r in rows}
        for core in {"Coal", "Gas", "Solar", "Wind", "Hydro", "Nuclear"}:
            assert core in sources


class TestLandUseSchema:
    """Land use JSON: list of sources with m2/MWh ranges."""

    def test_rows_are_well_formed(self):
        rows = get_static_dataset("land_use")["rows"]
        assert len(rows) >= 6
        required = {"source", "median_m2_per_mwh",
                    "p5_m2_per_mwh", "p95_m2_per_mwh"}
        for r in rows:
            assert required <= set(r.keys())
            assert r["p5_m2_per_mwh"] <= r["median_m2_per_mwh"]
            assert r["median_m2_per_mwh"] <= r["p95_m2_per_mwh"]


class TestFossilPollutionSchema:
    """Fossil-fuel pollution deaths JSON: headline + by_source breakdown."""

    def test_headline_structure(self):
        data = get_static_dataset("fossil_pollution_deaths")["payload"]
        head = data["headline"]
        vals = head["global_annual_deaths_from_fossil_pm25"]
        # Vohra > Lelieveld > Burnett (confirms our orientation).
        assert vals["vohra_2021_central"] > vals["lelieveld_2019_central"]

    def test_by_source_adds_up_roughly(self):
        """Share_of_fossil_total_pct values should sum to 100 ±5."""
        data = get_static_dataset("fossil_pollution_deaths")["payload"]
        total = sum(r["share_of_fossil_total_pct"] for r in data["by_source"])
        assert 95 <= total <= 105


class TestAccidentsSchema:
    """Accidents JSON: at least 20 entries, hydro-heavy, required fields."""

    def test_minimum_count(self):
        rows = get_static_dataset("accidents")["rows"]
        assert len(rows) >= 20

    def test_required_fields(self):
        """Every accident entry must carry these fields so the UI can
        render table + timeline without defensive null checks."""
        rows = get_static_dataset("accidents")["rows"]
        required = {"id", "name", "year", "country", "source_type",
                    "direct_deaths", "estimated_deaths_low",
                    "estimated_deaths_high", "short_description",
                    "references"}
        for r in rows:
            missing = required - set(r.keys())
            assert not missing, f"{r.get('id')} missing: {missing}"
            assert isinstance(r["references"], list)
            assert len(r["references"]) >= 1

    def test_ids_are_unique(self):
        """IDs serve as stable URL fragments and React keys."""
        rows = get_static_dataset("accidents")["rows"]
        ids = [r["id"] for r in rows]
        assert len(ids) == len(set(ids))

    def test_hydro_is_dominant_category(self):
        """User requirement: hydro must be the largest category in the
        curated list, since hydroelectric dam failures produced by far
        the highest absolute death counts in history."""
        rows = get_static_dataset("accidents")["rows"]
        counts: dict[str, int] = {}
        for r in rows:
            counts[r["source_type"]] = counts.get(r["source_type"], 0) + 1
        assert counts.get("Hydro", 0) >= 8
        # No other category should have more hydro entries.
        assert counts["Hydro"] == max(counts.values())

    def test_banqiao_is_deadliest(self):
        """Sanity: Banqiao's upper estimate must be the highest in the
        list by a wide margin — if a curator edits it below another
        entry by mistake, the UI's 'deadliest' narrative breaks."""
        rows = get_static_dataset("accidents")["rows"]
        banqiao = next(r for r in rows if r["id"] == "banqiao-1975")
        top = max(r["estimated_deaths_high"] for r in rows)
        assert banqiao["estimated_deaths_high"] == top
        assert banqiao["estimated_deaths_high"] >= 100000


class TestNuclearWasteSchema:
    """Nuclear waste JSON: headline + categories + stockpile + repositories."""

    def test_structure(self):
        data = get_static_dataset("nuclear_waste")["payload"]
        for key in ("headline", "categories", "global_stockpile_2023",
                    "deep_geological_repositories", "references"):
            assert key in data

    def test_four_waste_categories(self):
        data = get_static_dataset("nuclear_waste")["payload"]
        cats = {c["category"] for c in data["categories"]}
        assert cats == {"VLLW", "LLW", "ILW", "HLW"}

    def test_category_shares_sum_to_100(self):
        """Volume shares across VLLW/LLW/ILW/HLW sum to 100 ±5."""
        data = get_static_dataset("nuclear_waste")["payload"]
        total = sum(c["share_of_waste_volume_pct"] for c in data["categories"])
        assert 95 <= total <= 105

    def test_repositories_have_names(self):
        data = get_static_dataset("nuclear_waste")["payload"]
        names = [r["name"] for r in data["deep_geological_repositories"]]
        assert "Onkalo (Olkiluoto)" in names
        # Every entry has a status string.
        for repo in data["deep_geological_repositories"]:
            assert repo.get("status")
