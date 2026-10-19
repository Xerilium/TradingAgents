"""Bounded broker receipts and official reconciliation preflight; no portfolio accounting."""
import asyncio
import copy
import json
from datetime import datetime, timedelta
from decimal import Decimal
from urllib.parse import urlencode

from .alpaca_reports import timestamp, execution_id


async def collect_history(lifecycle, account, until, prior=None):
    start = (datetime.fromisoformat(prior["through"].replace("Z", "+00:00")) - timedelta(seconds=1)).isoformat() if prior else account.get("created_at")
    if not start:
        raise ValueError("Account creation time is missing; complete fill-history provenance is unavailable")
    rows, references, token, previous = dict(prior["activities"]) if prior else {}, [], None, None
    while True:
        query = dict(after=start, until=until, direction="asc", page_size=100)
        if token:
            query["page_token"] = token
        result = await asyncio.to_thread(lifecycle.transport.read_receipt, "/v2/account/activities?" + urlencode(query))
        references.append(lifecycle.receipt("native-recovery", "Alpaca account activities page",
            {"query": query, "raw_response": result["raw"].decode(), "received_at": result["received_at"]}))
        page = result["data"]
        if not isinstance(page, list) or len(page) > 100:
            raise ValueError("Invalid account-activity page")
        for row in page:
            identity = row.get("id")
            if not identity or identity in rows and rows[identity] != row:
                raise ValueError("Missing or conflicting account-activity identity")
            if row.get("activity_type") == "FILL":
                instant = timestamp(row.get("transaction_time"))
                if not timestamp(start) <= instant <= timestamp(until) or previous is not None and instant < previous:
                    raise ValueError("Fill page ordering or requested time boundary differs")
                previous = instant
            rows[identity] = row
        if len(page) < 100:
            break
        if page[-1]["id"] == token:
            raise ValueError("Account-activity cursor did not advance")
        token = page[-1]["id"]
    fills = [copy.deepcopy(row) for row in rows.values() if row.get("activity_type") == "FILL"]
    fees = {}
    for row in rows.values():
        identity = row.get("execution_id") or row.get("trade_id")
        if row.get("activity_type") != "FILL" and identity and row.get("commission") is not None:
            identity = execution_id(identity)
            fee = {"amount": row["commission"], "currency": row.get("currency"), "activity_id": row["id"],
                   "execution_id": identity, "order_id": row.get("order_id")}
            if identity in fees and fees[identity] != fee:
                raise ValueError("Conflicting explicitly linked commission sources")
            fees[identity] = fee
    changed = prior is None or rows != prior["activities"]
    pages = (prior["pages"] if prior else []) + (references if changed else [])
    evidence = lifecycle.receipt("native-recovery", "Complete activity history provenance",
        {"from": prior["from"] if prior else start, "through": until, "pages": pages,
         "activity_ids": sorted(rows)}) if changed else prior["evidence"]
    history = {"complete": True, "from": prior["from"] if prior else start, "through": until,
               "records": len(rows), "pages": pages, "boundary_pages": references, "evidence": evidence, "activities": rows,
               "limits": {"page_size": 100}}
    return fills, fees, history


def report_signature(report):
    from nautilus_trader.core.uuid import UUID4
    from nautilus_trader.model.identifiers import Identifier
    from nautilus_trader.model.objects import Money, Price, Quantity
    def scalar(value):
        if isinstance(value, (Decimal, UUID4, Identifier, Money, Price, Quantity)):
            return {"native_type": type(value).__name__, "value": str(value)}
        if isinstance(value, datetime):
            return value.isoformat()
        if hasattr(value, "name"):
            return {"enum": type(value).__name__, "value": value.name}
        raise TypeError("Unsupported native report representation")
    return json.dumps({**vars(report), "report_id": report.id, "ts_init": report.ts_init},
                      default=scalar, sort_keys=True, allow_nan=False)


def copy_mass(mass, excluded=()):
    copied = type(mass)(mass.client_id, mass.account_id, mass.venue, mass.id, mass.ts_init)
    copied.add_order_reports([report for key, report in mass.order_reports.items() if str(key) not in excluded])
    copied.add_fill_reports([report for key, reports in mass.fill_reports.items() if str(key) not in excluded for report in reports])
    copied.add_position_reports([report for reports in mass.position_reports.values() for report in reports])
    return copied


def require_unchanged_adjustment(mass, cache, *, select_closed_history=False):
    from nautilus_trader.live.reconciliation import adjust_fills_for_partial_window
    instruments = [cache.instrument(identity) for identity in mass.position_reports]
    if any(item is None for item in instruments):
        raise ValueError("Position lifecycle instrument is unavailable")
    # The pinned helper only reads these immutable report objects through to_pyo3().
    original = copy_mass(mass)
    excluded = set()
    for instrument, (orders, fills) in adjust_fills_for_partial_window(original, instruments).items():
        expected_orders = {str(key): report_signature(value) for key, value in mass.order_reports.items() if value.instrument_id == instrument}
        actual_orders = {str(key): report_signature(value) for key, value in orders.items()}
        expected_fills = {str(key): [report_signature(value) for value in values] for key, values in mass.fill_reports.items()
                          if values and values[0].instrument_id == instrument}
        actual_fills = {str(key): [report_signature(value) for value in values] for key, values in fills.items() if values}
        if select_closed_history:
            if (any(key not in expected_orders or value != expected_orders[key] for key, value in actual_orders.items())
                    or any(key not in expected_fills or value != expected_fills[key] for key, value in actual_fills.items())
                    or set(actual_fills).difference(actual_orders)):
                raise ValueError("Official lifecycle selection would fabricate or modify a fill/order; recovery withheld")
            if any(report.is_open for key, report in mass.order_reports.items() if str(key) in expected_orders and str(key) not in actual_orders):
                raise ValueError("Official lifecycle selection would omit an active order")
            excluded.update(key for key in expected_orders if key not in actual_orders)
        elif list(expected_orders) != list(actual_orders) or expected_orders != actual_orders or expected_fills != actual_fills:
            raise ValueError("Official partial-window adjustment would create, replace, omit or reorder real reports; full position lifecycle is unresolved")
    if excluded:
        selected = copy_mass(mass, excluded)
        require_unchanged_adjustment(selected, cache)
        return selected, sorted(excluded)
    if select_closed_history:
        require_unchanged_adjustment(mass, cache)
    return mass, []
