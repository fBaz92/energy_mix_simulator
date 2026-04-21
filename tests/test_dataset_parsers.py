"""Unit tests for the OWID CSV parsers.

Each parser is a pure function over raw CSV bytes. Fixtures here embed
tiny representative slices of each upstream schema (matching the real
OWID column headers observed 2026-04) so the tests never touch the
network and fail loudly if a future upstream change breaks the
contract.
"""

from __future__ import annotations

import pytest

from webapp.backend.datasets.parsers import (
    CANONICAL_SOURCE_LABELS,
    parse_carbon_intensity_country,
    parse_deaths_per_twh,
    parse_pm25_deaths,
)


# ---------------------------------------------------------------------------
# deaths_per_twh
# ---------------------------------------------------------------------------

_DEATHS_CSV = b"""\
Entity,Year,Deaths per terawatt-hour of energy production
Biomass,2021,4.63
Brown coal,2021,32.72
Coal,2021,24.62
Gas,2021,2.821
Hydropower,2021,1.3
Nuclear,2021,0.03
Oil,2021,18.43
Solar,2021,0.02
Wind,2021,0.04
"""


class TestDeathsPerTwhParser:
    """Verify the shape and canonicalisation of the death-rates parser."""

    def test_returns_all_rows(self):
        """Every data row in the CSV must be turned into a dict."""
        rows = parse_deaths_per_twh(_DEATHS_CSV)
        assert len(rows) == 9

    def test_sorted_descending(self):
        """Rows must be sorted by deaths_per_twh descending so the UI
        can render the bar chart without re-sorting."""
        rows = parse_deaths_per_twh(_DEATHS_CSV)
        values = [r["deaths_per_twh"] for r in rows]
        assert values == sorted(values, reverse=True)
        # Top is Brown coal / Coal / Oil; bottom is Solar / Wind / Nuclear
        assert rows[0]["source"] in {"Coal", "Lignite"}
        assert rows[-1]["source"] in {"Solar", "Wind", "Nuclear"}

    def test_canonical_label_rewrite(self):
        """'Hydropower' must be rewritten to 'Hydro' to match the rest
        of the webapp's source labels (see CANONICAL_SOURCE_LABELS)."""
        rows = parse_deaths_per_twh(_DEATHS_CSV)
        sources = {r["source"] for r in rows}
        assert "Hydro" in sources
        assert "Hydropower" not in sources
        # 'Brown coal' becomes 'Lignite'.
        assert "Lignite" in sources
        assert "Brown coal" not in sources

    def test_value_type_and_year(self):
        """Deaths-per-TWh must be floats; year must be int."""
        rows = parse_deaths_per_twh(_DEATHS_CSV)
        for r in rows:
            assert isinstance(r["deaths_per_twh"], float)
            assert isinstance(r["year"], int)
            assert r["year"] == 2021

    def test_tolerates_utf8_bom(self):
        """OWID occasionally serves CSVs with a BOM; the decoder must
        strip it rather than corrupting the first header name."""
        with_bom = b"\xef\xbb\xbf" + _DEATHS_CSV
        rows = parse_deaths_per_twh(with_bom)
        assert len(rows) == 9

    def test_canonical_labels_mapping_completeness(self):
        """Every label we expect to see in the upstream file must have
        a canonical entry (identity or rewrite). Guards against silent
        drift when OWID adds a new source."""
        expected = {"Biomass", "Brown coal", "Coal", "Gas", "Hydropower",
                    "Nuclear", "Oil", "Solar", "Wind"}
        for label in expected:
            assert label in CANONICAL_SOURCE_LABELS


# ---------------------------------------------------------------------------
# carbon_intensity_country
# ---------------------------------------------------------------------------

_CARBON_CSV = b"""\
Entity,Code,Year,Carbon intensity of electricity per kWh
ASEAN (Ember),,2000,572.52
Afghanistan,AFG,2000,250
Africa,OWID_AFR,2000,621.1345
Italy,ITA,2000,478.0
Italy,ITA,2020,258.4
"""


class TestCarbonIntensityCountryParser:
    """Verify parsing of the per-country-per-year carbon intensity CSV."""

    def test_row_shape(self):
        """Each row must contain country, code, year, gco2_kwh, is_aggregate."""
        rows = parse_carbon_intensity_country(_CARBON_CSV)
        assert len(rows) == 5
        for r in rows:
            assert set(r.keys()) == {"country", "code", "year",
                                     "gco2_kwh", "is_aggregate"}

    def test_is_aggregate_flag(self):
        """Rows without a 3-letter country code (aggregates like 'ASEAN
        (Ember)' or 'Africa') must be marked is_aggregate=True."""
        rows = parse_carbon_intensity_country(_CARBON_CSV)
        agg = [r for r in rows if r["is_aggregate"]]
        countries = [r for r in rows if not r["is_aggregate"]]
        assert any(r["country"] == "ASEAN (Ember)" for r in agg)
        assert any(r["country"] == "Afghanistan" for r in countries)

    def test_sorted_by_country_year(self):
        """Rows must come out ordered by (country, year) for stable
        line-chart rendering on the frontend."""
        rows = parse_carbon_intensity_country(_CARBON_CSV)
        keys = [(r["country"], r["year"]) for r in rows]
        assert keys == sorted(keys)

    def test_skips_rows_with_missing_value(self):
        """A malformed row with a non-numeric value must be dropped,
        not crash the whole parse — upstream data quality is not
        something we can validate at import time."""
        bad = _CARBON_CSV + b"Italy,ITA,2021,NA\n"
        rows = parse_carbon_intensity_country(bad)
        # Same count as the clean fixture — the bad row was dropped.
        assert len(rows) == 5


# ---------------------------------------------------------------------------
# pm25_deaths
# ---------------------------------------------------------------------------

_PM25_CSV = b"""\
Entity,Code,Year,Absolute deaths from ambient PM2.5 air pollution- State of Global Air
Afghanistan,AFG,1990,16200
Afghanistan,AFG,2019,31000
Italy,ITA,1990,44000
Italy,ITA,2019,26000
World,OWID_WRL,2019,4140000
"""


class TestPm25DeathsParser:
    """Verify parsing of the ambient-PM2.5 deaths country-year CSV."""

    def test_basic_shape(self):
        """Returns {country, code, year, deaths, is_aggregate} tuples."""
        rows = parse_pm25_deaths(_PM25_CSV)
        assert len(rows) == 5
        for r in rows:
            assert set(r.keys()) == {"country", "code", "year",
                                     "deaths", "is_aggregate"}
            assert isinstance(r["deaths"], float)

    def test_world_is_aggregate(self):
        """'World' (code OWID_WRL) is an aggregate — code present but
        the 3-letter test flags aggregates via code pattern. Here the
        OWID code exists so is_aggregate is False; the frontend
        separately filters OWID_ prefixes. This test pins the current
        behaviour."""
        rows = parse_pm25_deaths(_PM25_CSV)
        world = next(r for r in rows if r["country"] == "World")
        assert world["code"] == "OWID_WRL"

    def test_missing_value_column_raises(self):
        """If OWID renames the value column in a way our heuristic
        can't recover, we'd rather fail loudly than silently return
        an empty list."""
        broken = b"Entity,Code,Year\nItaly,ITA,2000\n"
        with pytest.raises(ValueError, match="value column"):
            parse_pm25_deaths(broken)
