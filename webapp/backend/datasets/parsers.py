"""Pure functions that parse OWID CSV bytes into typed row dicts.

Each parser accepts raw bytes (as returned by ``httpx``) and returns a
list of dicts shaped for the frontend. Parsers are deliberately simple
and stateless so they can be unit-tested against checked-in fixtures
without any network or database dependency.

No ``pandas`` — the largest dataset (country-year carbon intensity) is
~160 KB / ~10 k rows, trivially iterable with ``csv.DictReader``.
Avoiding pandas also keeps the backend container image small.

Canonical source labels
-----------------------

OWID death-rates-per-TWh uses "Hydropower" while the rest of this app
labels it "Hydro". The :data:`CANONICAL_SOURCE_LABELS` mapping rewrites
labels at parse time so bars line up visually with the rest of the UI
(notably :class:`GenerationMixPie`).
"""

from __future__ import annotations

import csv
import io
from typing import Callable


CANONICAL_SOURCE_LABELS: dict[str, str] = {
    "Hydropower": "Hydro",
    "Brown coal": "Lignite",
    # Identity entries kept for documentation; no rewrite needed:
    "Coal": "Coal",
    "Gas": "Gas",
    "Oil": "Oil",
    "Biomass": "Biomass",
    "Nuclear": "Nuclear",
    "Solar": "Solar",
    "Wind": "Wind",
}


def _canon(label: str) -> str:
    """Apply the canonical source rewrite if one is configured.

    Args:
        label: Raw source label from the upstream CSV.

    Returns:
        Canonical label used throughout the rest of the webapp.
    """
    return CANONICAL_SOURCE_LABELS.get(label, label)


def _decode(raw: bytes) -> csv.DictReader:
    """Decode UTF-8 CSV bytes and return a ``DictReader``.

    Args:
        raw: Raw response body from ``httpx`` (``response.content``).

    Returns:
        ``csv.DictReader`` positioned at the first data row.
    """
    text = raw.decode("utf-8-sig")  # tolerate BOM
    return csv.DictReader(io.StringIO(text))


# ---------------------------------------------------------------------------
# Parsers — one per DatasetSpec.parser_name
# ---------------------------------------------------------------------------

def parse_deaths_per_twh(raw: bytes) -> list[dict]:
    """Parse the 'death-rates-from-energy-production-per-twh' CSV.

    Expected upstream columns::

        Entity, Year, Deaths per terawatt-hour of energy production

    The dataset has one row per source (~8 rows) and a single point in
    time. We keep the year alongside the value so the UI can show it in
    the caption.

    Args:
        raw: Raw CSV bytes.

    Returns:
        List of dicts ``{source, deaths_per_twh, year}`` sorted by
        ``deaths_per_twh`` descending (coal / oil at the top, solar /
        nuclear / wind at the bottom) — saves the frontend a sort.
    """
    reader = _decode(raw)
    rows: list[dict] = []
    for r in reader:
        rows.append({
            "source": _canon(r["Entity"]),
            "year": int(r["Year"]),
            "deaths_per_twh": float(
                r["Deaths per terawatt-hour of energy production"]),
        })
    rows.sort(key=lambda x: x["deaths_per_twh"], reverse=True)
    return rows


def parse_carbon_intensity_country(raw: bytes) -> list[dict]:
    """Parse the 'carbon-intensity-electricity' country-year CSV.

    Expected upstream columns::

        Entity, Code, Year, Carbon intensity of electricity per kWh

    Some rows have an empty ``Code`` (aggregates like "ASEAN (Ember)");
    we retain them but mark them as ``is_aggregate=true`` so the
    frontend can filter them out of per-country views.

    Args:
        raw: Raw CSV bytes.

    Returns:
        List of dicts ``{country, code, year, gco2_kwh, is_aggregate}``
        sorted by (country, year). The frontend applies a country
        multiselect on top.
    """
    reader = _decode(raw)
    rows: list[dict] = []
    for r in reader:
        code = (r.get("Code") or "").strip()
        try:
            value = float(r["Carbon intensity of electricity per kWh"])
        except (ValueError, KeyError):
            continue
        rows.append({
            "country": r["Entity"],
            "code": code or None,
            "year": int(r["Year"]),
            "gco2_kwh": value,
            "is_aggregate": not code,
        })
    rows.sort(key=lambda x: (x["country"], x["year"]))
    return rows


def parse_pm25_deaths(raw: bytes) -> list[dict]:
    """Parse the 'absolute-deaths-ambient-PM2.5' country-year CSV.

    Expected upstream columns (State of Global Air release)::

        Entity, Code, Year, Absolute deaths from ambient PM2.5 air
            pollution- State of Global Air

    The column name has a hyphen without a space and can include
    special characters — we look it up by positional header scan rather
    than a hard-coded string to survive minor upstream renames.

    Args:
        raw: Raw CSV bytes.

    Returns:
        List of dicts ``{country, code, year, deaths, is_aggregate}``
        sorted by (country, year).
    """
    reader = _decode(raw)
    # Find the value column — it's the only one not in the fixed set.
    fixed = {"Entity", "Code", "Year"}
    value_col = next(
        (f for f in reader.fieldnames or [] if f not in fixed), None)
    if value_col is None:
        raise ValueError("PM2.5 dataset: could not locate value column "
                         f"(fieldnames={reader.fieldnames})")
    rows: list[dict] = []
    for r in reader:
        code = (r.get("Code") or "").strip()
        try:
            deaths = float(r[value_col])
        except (ValueError, KeyError):
            continue
        rows.append({
            "country": r["Entity"],
            "code": code or None,
            "year": int(r["Year"]),
            "deaths": deaths,
            "is_aggregate": not code,
        })
    rows.sort(key=lambda x: (x["country"], x["year"]))
    return rows


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

PARSERS: dict[str, Callable[[bytes], list[dict]]] = {
    "parse_deaths_per_twh": parse_deaths_per_twh,
    "parse_carbon_intensity_country": parse_carbon_intensity_country,
    "parse_pm25_deaths": parse_pm25_deaths,
}


def get_parser(name: str) -> Callable[[bytes], list[dict]]:
    """Look up a parser by name, raising a clear error if missing.

    Args:
        name: Value of :attr:`DatasetSpec.parser_name`.

    Returns:
        The parser function.

    Raises:
        KeyError: If ``name`` is not in :data:`PARSERS`.
    """
    try:
        return PARSERS[name]
    except KeyError:
        raise KeyError(
            f"No parser named '{name}'. Known parsers: {sorted(PARSERS)}"
        ) from None
