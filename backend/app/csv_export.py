"""CSV serialization for the admin raw-data export.

Column order and names are fixed by the research contract in CLAUDE.md. JSON
columns are emitted as compact JSON strings.
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Iterable, Iterator

# Exact column order required by the export contract.
CSV_COLUMNS: list[str] = [
    "run_id",
    "timestamp",
    "timestep",
    "firm_id",
    "agent_type",
    "info_visibility",
    "regulation_mode",
    "coordination_mode",
    "price",
    "baseline_cost",
    "units_sold",
    "revenue",
    "profit",
    "market_avg_price",
    "market_price_std",
    "collusion_indicator",
    "consumer_surplus",
    "regulatory_penalty",
    "observed_competitor_prices",
    "agent_internal_state",
    "agent_decision_reasoning",
    "event_notes",
]

JSON_COLUMNS = {
    "observed_competitor_prices",
    "agent_internal_state",
}


def _format_value(column: str, value: object) -> str:
    if value is None:
        return ""
    if column in JSON_COLUMNS:
        # Stored as jsonb -> comes back as dict/list; emit compact JSON string.
        if isinstance(value, (dict, list)):
            return json.dumps(value, separators=(",", ":"))
        return str(value)
    return value if isinstance(value, str) else str(value)


def iter_csv(rows: Iterable[dict]) -> Iterator[str]:
    """Yield CSV text chunks (header first) for streaming responses."""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_COLUMNS, extrasaction="ignore")

    writer.writeheader()
    yield _drain(buffer)

    for row in rows:
        formatted = {col: _format_value(col, row.get(col)) for col in CSV_COLUMNS}
        writer.writerow(formatted)
        yield _drain(buffer)


def _drain(buffer: io.StringIO) -> str:
    text = buffer.getvalue()
    buffer.seek(0)
    buffer.truncate(0)
    return text
