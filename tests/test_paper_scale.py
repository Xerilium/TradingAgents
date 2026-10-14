"""Large-universe and summary/detail contracts, without models or broker writes."""

from __future__ import annotations

import copy
import json

import pytest
from pydantic import ValidationError

from tests.test_paper_service import BrokerFake, ScriptedGraph
from tradingagents.web.config import DeskConfig
from tradingagents.web.service import DeskService

SYMBOLS = [f"S{i:03}" for i in range(500)]


@pytest.fixture
def desk(tmp_path):
    broker = BrokerFake()
    service = DeskService(tmp_path, broker, ScriptedGraph)
    service.save_config({"name": "500-stock test fixture", "universe": SYMBOLS})
    yield service, broker
    service.close()


def test_universe_accepts_500_and_normalizes_class_symbols():
    config = DeskConfig(universe=[*SYMBOLS, " brk.b ", "S000"])
    assert len(config.universe) == 501
    assert config.universe[-1] == "BRK.B"
    with pytest.raises(ValidationError):
        DeskConfig(universe=[f"S{i}" for i in range(1001)])
    with pytest.raises(ValidationError, match="whitespace"):
        DeskConfig(name="   ")


def test_refresh_batches_all_500_snapshots_and_does_not_fetch_all_charts(desk):
    service, broker = desk
    state = service.refresh()
    requests = [args["symbols"].split(",") for _, command, args in broker.calls
                if command == "get_stock_snapshot"]
    assert len(requests) == 5
    assert all(len(batch) == 100 for batch in requests)
    assert sorted(s for batch in requests for s in batch) == SYMBOLS
    assert set(state["quotes"]) == set(SYMBOLS)
    assert not any(command == "get_stock_bars" for _, command, _ in broker.calls)
    assert state["errors"] == []
    assert broker.submitted == []


def test_failed_quote_batch_preserves_other_batches_and_keeps_execution_blocked(desk):
    service, broker = desk
    execute = broker.execute

    def partial(domain, command, parameters):
        if command == "get_stock_snapshot" and parameters["symbols"].startswith("S100"):
            raise RuntimeError("This snapshot batch is unavailable.")
        return execute(domain, command, parameters)

    broker.execute = partial
    state = service.refresh()
    assert len(state["quotes"]) == 400
    assert "S000" in state["quotes"] and "S499" in state["quotes"]
    error = next(e for e in state["errors"] if e["source"] == "quotes")
    assert error["symbols"] == SYMBOLS[100:200]
    with pytest.raises(ValueError, match="complete broker data"):
        service._book()
    assert broker.submitted == []


def test_chart_loads_one_allowed_symbol_caches_and_returns_independent_data(desk):
    service, broker = desk
    execute = broker.execute

    def chart_data(domain, command, parameters):
        if command == "get_stock_bars":
            broker.calls.append((domain, command, copy.deepcopy(parameters)))
            return {"bars": {parameters["symbols"]: [{"o": 100, "h": 102, "l": 99, "c": 101}]}}
        return execute(domain, command, parameters)

    broker.execute = chart_data
    first = service.chart("S499")
    assert first["symbol"] == "S499" and first["bars"][0]["c"] == 101
    first["bars"][0]["c"] = 0
    assert service.chart("S499")["bars"][0]["c"] == 101
    requests = [args for _, command, args in broker.calls if command == "get_stock_bars"]
    assert len(requests) == 1 and requests[0]["symbols"] == "S499"
    with pytest.raises(ValueError, match="universe"):
        service.chart("NOTINLIST")
    assert len(broker.calls) == 1


def test_compact_poll_does_not_copy_reports_or_raw_laya_and_details_are_available(desk):
    service, _ = desk
    results = [{"symbol": s, "status": "completed", "rating": "Hold", "trade_date": "2026-10-13",
                "revision": 5, "elapsed_seconds": 100,
                "reports": {"market_report": "Large source report " * 500},
                "laya": {"contract": {"grade": "ask_human", "summary": "Review required"},
                         "auto_execute": False, "raw": "raw model data " * 500}}
               for s in SYMBOLS]
    with service.store.lock:
        service.store.data["runs"] = [{"id": "scale-run", "symbols": SYMBOLS,
            "status": "completed", "config": service.store.data["config"],
            "results": results, "events": [{"message": f"event {i}"} for i in range(500)]}]
    compact = service.state(compact=True)
    full = service.state()
    assert len(json.dumps(compact)) < 250_000
    assert len(json.dumps(full)) > len(json.dumps(compact)) * 20
    run = compact["runs"][0]
    assert run["counts"]["completed"] == 500 and run["counts"]["queued"] == 0
    assert len(run["events"]) == 40 and run["event_count"] == 500
    assert "reports" not in run["results"][499]
    assert run["results"][499]["report_keys"] == ["market_report"]
    assert "raw" not in run["results"][499]["laya"]
    assert compact["research"]["S499"]["laya"]["grade"] == "ask_human"
    detail = service.run_detail("scale-run", "S499")
    assert detail == results[499]
    detail["reports"]["market_report"] = "changed"
    assert service.run_detail("scale-run", "S499")["reports"]["market_report"] != "changed"
    assert len(service.run_detail("scale-run")["results"]) == 500


def test_compact_state_keeps_selected_older_run_reachable(desk):
    service, _ = desk
    with service.store.lock:
        service.store.data["runs"] = [
            {"id": key, "symbols": [symbol], "status": "completed", "config": {},
             "results": [{"symbol": symbol, "status": "completed", "reports": {}}]}
            for key, symbol in (("new", "S000"), ("old", "S499"))
        ]
    runs = service.state(compact=True, run_id="old")["runs"]
    assert runs[0]["results"] == []
    assert runs[1]["results"][0]["symbol"] == "S499"
    assert service.run_detail("old", "S499")["revision"] == 0


def test_reviewed_research_rejects_settings_changed_since_review(desk):
    service, broker = desk
    revision = service.state(compact=True)["config_revision"]
    service.save_config({"name": "Changed after workload review"})
    with pytest.raises(ValueError, match="changed"):
        service.start_run(["S499"], expected_revision=revision)
    assert service.state()["runs"] == []
    assert broker.submitted == []


def test_compact_state_falls_back_to_latest_when_selected_run_was_removed(desk):
    service, _ = desk
    service.store.data["runs"] = [{"id": "latest", "symbols": ["S499"],
        "status": "completed", "config": {}, "results": [{"symbol": "S499",
        "status": "completed", "reports": {}}]}]
    compact = service.state(compact=True, run_id="gone")
    assert compact["runs"][0]["results"][0]["symbol"] == "S499"
