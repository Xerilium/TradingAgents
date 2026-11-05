"""Human-authored portfolios, independent of research and broker accounts."""

import re
from decimal import Decimal, InvalidOperation
from uuid import uuid4

DEFAULT = {"portfolios": []}


def state(store):
    record = store.database.read("manual_portfolios", DEFAULT)
    portfolios = [{**item, "revision": item.get("revision", 1)} for item in record["data"]["portfolios"]]
    return {"revision": record["revision"], "portfolios": portfolios,
            "universe": list(store.data["config"]["universe"])}


def save(store, request, weights=None):
    if request.get("action") != "save" or not isinstance(request.get("portfolio"), dict):
        raise ValueError("Choose a portfolio to save")
    source = request["portfolio"]
    name = source.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Enter a portfolio name")
    rows = source.get("allocations")
    if not isinstance(rows, list) or not rows or len(rows) > 1000:
        raise ValueError("Choose between 1 and 1000 allocations")
    try:
        capital = Decimal(str(source["capital_usd"]))
        cash = Decimal(str(source["cash_weight"]))
        allocations, seen = [], set()
        for row in rows:
            symbol = row["symbol"].strip().upper()
            weight = Decimal(str(row["weight"]))
            if not re.fullmatch(r"[A-Z0-9][A-Z0-9.\-]{0,19}", symbol) or symbol in seen or not weight.is_finite() or not 0 <= weight <= 1:
                raise ValueError("Invalid or duplicate symbol or weight")
            seen.add(symbol)
            allocations.append({"symbol": symbol, "weight": str(weight), **({"cusip": str(row["cusip"])} if row.get("cusip") else {}),
                                **({"historical_symbol": str(row["historical_symbol"])} if row.get("historical_symbol") else {})})
        if not capital.is_finite() or capital <= 0 or not cash.is_finite() or not 0 <= cash <= 1 or sum((Decimal(row["weight"]) for row in allocations), cash) != 1:
            raise ValueError("Capital must be positive and allocations plus cash must total 100%")
    except (KeyError, TypeError, AttributeError, InvalidOperation) as error:
        raise ValueError("Invalid portfolio capital, cash or allocations") from error
    identity = source.get("id") or str(uuid4())
    if not isinstance(identity, str) or not identity.strip():
        raise ValueError("Invalid portfolio id")
    portfolio = {"id": identity, "name": name.strip(), "capital_usd": str(capital),
                 "allocations": allocations, "cash_weight": str(cash)}
    if source.get("weight_source") is not None:
        claim = source["weight_source"]
        if not isinstance(claim, dict) or weights is None:
            raise ValueError("Invalid index weight source")
        snapshot = weights.state(as_of=claim.get("as_of")).get("snapshot")
        if not snapshot or claim.get("id") != snapshot["id"] or claim.get("source_sha256") != snapshot["source_sha256"]:
            raise ValueError("Index snapshot is unavailable or changed")
        expected = {row["symbol"]: (Decimal(row["weight"]), row.get("cusip") or None, row.get("historical_symbol") or None) for row in snapshot["entries"]}
        actual = {row["symbol"]: (Decimal(row["weight"]), row.get("cusip") or None, row.get("historical_symbol") or None) for row in allocations}
        if actual != expected:
            raise ValueError("Edited allocations do not match the selected index snapshot; clear its source")
        portfolio["weight_source"] = {key: snapshot[key] for key in ("id", "as_of", "source_sha256", "provider")}
    def change(data):
        previous = next((item for item in data["portfolios"] if item["id"] == identity), None)
        portfolio["revision"] = previous.get("revision", 1) + 1 if previous else 1
        data["portfolios"] = [item for item in data["portfolios"] if item["id"] != identity] + [portfolio]
    record = store.database.update("manual_portfolios", request.get("expected_revision"), change, DEFAULT)
    return {"revision": record["revision"], "portfolios": record["data"]["portfolios"],
            "universe": list(store.data["config"]["universe"]), "portfolio": portfolio}


def model(store, identity, revision):
    record = store.database.read("manual_portfolios", DEFAULT)
    portfolio = next((item for item in record["data"]["portfolios"] if item["id"] == identity), None)
    if portfolio is None:
        raise ValueError("Choose a saved portfolio")
    current_revision = portfolio.get("revision", 1)
    if type(revision) is not int or revision != current_revision:
        from .app_database import StoreConflict
        raise StoreConflict(current_revision)
    return {"id": portfolio["id"], "name": portfolio["name"], "portfolio_revision": revision,
            "inputs": [{"symbol": row["symbol"], **({"cusip": row["cusip"]} if row.get("cusip") else {}),
                        **({"historical_symbol": row["historical_symbol"]} if row.get("historical_symbol") else {})} for row in portfolio["allocations"]],
            "result": {"capital": portfolio["capital_usd"], "target_cash_weight": portfolio["cash_weight"],
                       "allocations": portfolio["allocations"]}, "weight_source": portfolio.get("weight_source")}
