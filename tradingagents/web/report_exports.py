"""Decimal-preserving scoped CSV exports from existing observations and saved reports."""

import csv
import io
import json
import re

from .investor import decimal
from .recovery import references


def guard(value):
    list(references(value))
    if re.search(r"(?i)bearer\s+\S+|sk-(?:proj-)?[A-Za-z0-9_-]{16,}|-----BEGIN [A-Z ]*PRIVATE KEY|(?:api[_ -]?key|secret[_ -]?key|password)\s*[=:]\s*\S+", json.dumps(value)):
        raise ValueError("Selected export may contain a credential; export stopped")


def csv_export(kind, rows, context):
    guard({"rows": rows, "context": context})
    fields = list(dict.fromkeys(["scope", "account_id", "source_at", "period_start", "period_end"] + list(context) + [key for row in rows for key in row]))
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        safe = {}
        for key, value in {**context, **row}.items():
            value = "Unavailable" if value is None else json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)
            if value.startswith(("=", "+", "-", "@")) and decimal(value) is None:
                value = "'" + value
            safe[key] = value
        writer.writerow(safe)
    return {"csv": output.getvalue(), "filename": "tradingagents-" + kind + ".csv", "context": context}
