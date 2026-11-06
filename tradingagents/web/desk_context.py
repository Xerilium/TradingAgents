"""Read-only desk views for local clients that do not need settings or order details."""

from copy import deepcopy

from .config import DeskConfig
from .investor import DEFAULT as INVESTOR_DEFAULT


class ContextUnavailable(LookupError):
    """The requested retained record is unavailable."""


def _fields(record, names):
    return {name: record.get(name) for name in names.split()}


def research(desk, *, symbol=None, report=None, offset="0", limit="25"):
    store = desk.store
    if symbol is not None:
        symbol = DeskConfig.symbols([symbol])[0]
        if offset != "0" or limit != "25":
            raise ValueError("Pagination applies to the research list only.")
    elif report is not None:
        raise ValueError("A report requires a symbol.")
    offset, limit = int(offset), int(limit)
    if offset < 0 or not 1 <= limit <= 100:
        raise ValueError("Use a nonnegative offset and a limit from 1 to 100.")

    def summary(run_id, result):
        item = store.result_summary(result)
        gaps = item.get("coverage_gaps")
        return {"run_id": run_id, **_fields(item, "symbol status rating trade_date revision completion_gaps report_keys"),
                "coverage_gap_count": len(gaps) if gaps is not None else None}

    with store.lock:
        latest = {result["symbol"]: (run["id"], result)
                  for run in store.data["runs"] for result in run.get("results", [])}
        if symbol is not None:
            if symbol not in latest:
                raise ContextUnavailable("No retained research for this symbol.")
            run_id, result = latest[symbol]
            item = summary(run_id, result)
            if report is not None:
                if report not in item["report_keys"]:
                    raise ContextUnavailable("This report is unavailable in the latest result. Read the result to list its reports.")
                item.update(report_key=report, report=deepcopy(result["reports"][report]))
            return item

        end = offset + limit
        return {"results": [summary(*latest[key]) for key in sorted(latest)[offset:end]],
                "total": len(latest), "next_offset": end if end < len(latest) else None}


def portfolio(desk):
    runtime = desk.runtime.state()
    connected = runtime["status"] == "connected"
    account = runtime.get("account") if connected else None
    reconciliation = runtime.get("reconciliation", {})
    observed = runtime.get("broker_observation", {})
    positions_complete = bool(account and account.get("id") and reconciliation.get("status") == "reconciled"
                              and observed.get("positions_complete") is True)
    policy = desk.store.database.read("investor", INVESTOR_DEFAULT)["data"]["policy"]
    funds = desk.fund_plan_status(runtime, policy)
    rebalance = desk.spy_rebalance.status(runtime)
    return {
        "engine": runtime["status"],
        "account_observed_at": runtime.get("account_at"),
        "account": _fields(account, "currency cash equity buying_power") if account else None,
        "reconciliation": _fields(reconciliation, "status gaps"),
        "positions_complete": positions_complete,
        "positions": [_fields(position, "symbol asset_class side qty qty_available avg_entry_price current_price market_value unrealized_pl import_error")
                      for position in runtime.get("positions", [])],
        "fund_plan": _fields(funds, "budget budget_error"),
        "spy_rebalance": _fields(rebalance, "enabled in_progress run"),
    }


def quote(desk, *, symbol):
    symbol = DeskConfig.symbols([symbol])[0]
    runtime = desk.runtime.state()
    return {"symbol": symbol, **desk._market_quotes(runtime, [symbol])[symbol]}
