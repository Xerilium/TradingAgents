"""Account-bound, authored paper fund reserves; no transfer or trading authority."""

import hashlib
import json
import re
from datetime import UTC, datetime
from decimal import Decimal

from .investor import decimal

RECORD = "fund_plans"
DEFAULT = {"schema_version": 1, "plans": {}}
PAPER = "https://paper-api.alpaca.markets"
FIELDS = ("monthly_net_withdrawal_usd", "reserve_months", "tax_provision_usd", "trading_cushion_usd")


def account_key(account_id):
    if not isinstance(account_id, str) or not re.fullmatch(r"[A-Za-z0-9-]{1,128}", account_id):
        raise ValueError("A valid observed paper account identity is required.")
    return PAPER + "|" + account_id


def amount(value, field):
    if value is None:
        return None
    if not isinstance(value, str) or not re.fullmatch(r"\d{1,12}(?:\.\d{1,2})?", value):
        raise ValueError(f"{field}: Enter a nonnegative decimal with at most two decimal places, or leave it unknown.")
    result = Decimal(value)
    maximum = Decimal("1200") if field == "reserve_months" else Decimal("100000000000")
    if result > maximum:
        raise ValueError(f"{field}: The value exceeds the supported limit.")
    return format(result.normalize(), "f")


def validate(data):
    if not isinstance(data, dict) or set(data) != {"schema_version", "plans"} or type(data["schema_version"]) is not int or data["schema_version"] != 1 or not isinstance(data["plans"], dict) or len(data["plans"]) > 1000:
        raise ValueError("Invalid fund plans record.")
    for key, plan in data["plans"].items():
        if not isinstance(plan, dict) or set(plan) != {"account_id", "endpoint", "currency", "revision", "status", "updated_at", *FIELDS}:
            raise ValueError("Invalid fund plan fields.")
        if (key != account_key(plan["account_id"]) or plan["endpoint"] != PAPER or plan["currency"] != "USD"
                or type(plan["revision"]) is not int or not 1 <= plan["revision"] <= 1000000000
                or not isinstance(plan["status"], str) or plan["status"] not in {"active", "inactive"}):
            raise ValueError("Invalid fund plan identity, revision, or status.")
        try:
            timestamp = datetime.fromisoformat(plan["updated_at"])
            if timestamp.tzinfo is None or timestamp.utcoffset() is None:
                raise ValueError
        except (TypeError, ValueError):
            raise ValueError("Invalid fund plan update time.") from None
        for field in FIELDS:
            if amount(plan[field], field) != plan[field]:
                raise ValueError("Fund plan decimal values must be canonical.")
    return data


def binding(data, account_id):
    validate(data)
    plan = data["plans"].get(account_key(account_id))
    encoded = json.dumps(plan, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return {"revision": plan["revision"] if plan else 0, "sha256": hashlib.sha256(encoded).hexdigest()}


def save(data, request, account_id):
    validate(data)
    allowed = {"action", "account_id", "expected_revision", "fund_plans_revision", "plan_revision", "status", *FIELDS}
    if set(request) != allowed:
        raise ValueError("Supply only the required fund-plan fields and revisions.")
    key = account_key(account_id)
    old = data["plans"].get(key)
    if type(request.get("plan_revision")) is not int or request["plan_revision"] != (old["revision"] if old else 0):
        raise ValueError("The account fund plan changed. Reload it before saving.")
    if not isinstance(request.get("status"), str) or request["status"] not in {"active", "inactive"} or any(field not in request for field in FIELDS):
        raise ValueError("Choose plan status and provide each reserve term, using null for unknown values.")
    values = {field: amount(request[field], field) for field in FIELDS}
    if old and old["status"] == request["status"] and all(old[field] == values[field] for field in FIELDS):
        return False
    data["plans"][key] = {"account_id": account_id, "endpoint": PAPER, "currency": "USD",
                          "revision": (old["revision"] if old else 0) + 1, "status": request["status"],
                          "updated_at": datetime.now(UTC).isoformat(), **values}
    validate(data)
    return True


def budget(plan, runtime, policy, *, commitments_clear=True):
    account = runtime.get("account") or {}
    cash, equity = decimal(account.get("cash")), decimal(account.get("equity"))
    if cash is None or cash < 0 or equity is None or equity <= 0:
        raise ValueError("Nonnegative observed cash and positive account equity are required.")
    rule = policy["rules"].get("cash_reserve_pct", {})
    percent = decimal(rule.get("value")) if rule.get("state") == "enabled" else Decimal(0)
    if percent is None or not 0 <= percent <= 100:
        raise ValueError("The cash reserve rule is unavailable.")
    floor = equity * percent / 100
    active = plan is not None and plan["status"] == "active"
    if active and any(plan[field] is None for field in FIELDS):
        raise ValueError("The active fund plan has unknown reserve terms.")
    spending = Decimal(plan[FIELDS[0]]) * Decimal(plan[FIELDS[1]]) if active else Decimal(0)
    authored = spending + Decimal(plan[FIELDS[2]]) + Decimal(plan[FIELDS[3]]) if active else Decimal(0)
    reserve = max(authored, floor)
    sleeve = max(Decimal(0), equity - reserve)
    return {"spending_reserve_usd": str(spending) if active else None, "authored_reserve_usd": str(authored) if active else None,
            "policy_floor_usd": str(floor), "required_reserve_usd": str(reserve),
            "cash_usd": str(cash), "equity_usd": str(equity), "shortfall_usd": str(max(Decimal(0), reserve - cash)),
            "investable_sleeve_usd": str(sleeve),
            "spendable_cash_usd": str(max(Decimal(0), cash - reserve)) if commitments_clear else None,
            "spendable_cash_error": None if commitments_clear else "Working or unknown order commitments prevent calculating spendable cash.",
            "account_at": runtime.get("account_at"),
            "account_observation_started_at": runtime.get("account_observation_started_at"),
            "active": active}
