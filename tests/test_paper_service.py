"""Offline paper desk workflow tests; the fake never contacts a broker."""

from __future__ import annotations

import copy
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from tradingagents.integrations.maenifold import GatewayError
from tradingagents.web import store as store_module
from tradingagents.web.service import DeskService, normalize_quotes
from tradingagents.web.store import DeskStore


class BrokerFake:
    endpoint = "http://localhost:8080/mcp"

    def __init__(self):
        self.calls = []
        self.account = {
            "id": "paper-account",
            "status": "ACTIVE",
            "currency": "USD",
            "cash": "100000",
            "equity": "100000",
            "trading_blocked": False,
            "account_blocked": False,
            "trade_suspended_by_user": False,
        }
        self.positions = []
        self.orders = []
        self.open_orders = []
        self.receipts = {}
        self.errors = {}
        self.paper = "true"
        self.submit_error = None
        self.submitted = []
        self.laya_grade = "auto_execute"
        self.laya_value = True
        self.asset_tradable = True

    def discover(self, domain):
        assert domain in {"alpaca", "maenifold.memory", "laya", "maenifold.system"}
        return {}

    def execute(self, domain, command, parameters):
        self.calls.append((domain, command, copy.deepcopy(parameters)))
        if command in self.errors:
            raise self.errors[command]
        if domain == "maenifold.system" and command == "GetConfig":
            return {
                "mcpServers": {
                    "alpaca": {
                        "command": "uv",
                        "args": ["tool", "run", "alpaca-mcp-server"],
                        "gateway": True,
                        "env": {
                            "ALPACA_PAPER_TRADE": self.paper,
                            "ALPACA_API_KEY": "never-display",
                        },
                    }
                }
            }
        if domain == "laya" and command == "decide":
            return {
                "contract": {"grade": self.laya_grade},
                "answers": {
                    key: {"value": self.laya_value}
                    for key in ("evidence_complete", "decision_consistent")
                },
            }
        assert domain == "alpaca", (domain, command)
        if command == "get_account_info":
            return copy.deepcopy(self.account)
        if command == "get_all_positions":
            return copy.deepcopy(self.positions)
        if command == "get_orders":
            return copy.deepcopy(
                self.open_orders if parameters.get("status") == "open" else self.orders
            )
        if command == "get_order_by_client_id":
            if parameters["client_order_id"] not in self.receipts:
                raise GatewayError("Order not found")
            return copy.deepcopy(self.receipts[parameters["client_order_id"]])
        if command == "get_stock_snapshot":
            return {
                symbol: {
                    "latestTrade": {"p": 100, "t": datetime.now(UTC).isoformat()},
                    "latestQuote": {"bp": 100, "ap": 100, "t": datetime.now(UTC).isoformat()},
                    "prevDailyBar": {"c": 99},
                    "dailyBar": {"c": 100, "v": 10000},
                }
                for symbol in parameters["symbols"].split(",")
            }
        if command == "get_portfolio_history":
            return {"timestamp": [1, 2], "equity": [100000, 100000]}
        if command == "get_stock_bars":
            return {"bars": {}}
        if command == "get_clock":
            return {"is_open": True, "timestamp": datetime.now(UTC).isoformat()}
        if command == "get_asset":
            assert set(parameters) == {"symbol_or_asset_id"}
            return {"class": "us_equity", "tradable": self.asset_tradable}
        if command == "place_stock_order":
            # Shapes copied from the live Gateway schema; no numeric coercion.
            assert parameters["type"] == "limit"
            assert parameters["time_in_force"] == "day"
            assert parameters["extended_hours"] is False
            assert isinstance(parameters["qty"], str)
            assert isinstance(parameters["limit_price"], str)
            assert set(parameters) == {
                "symbol",
                "side",
                "qty",
                "limit_price",
                "client_order_id",
                "type",
                "time_in_force",
                "extended_hours",
            }
            self.submitted.append(copy.deepcopy(parameters))
            if self.submit_error:
                raise self.submit_error
            return {"id": "broker-order", "status": "accepted", **copy.deepcopy(parameters)}
        if command == "cancel_order_by_id":
            return {}
        raise AssertionError(f"Unexpected command: {domain}.{command}")


class ManualExecutor:
    """Control worker dispatch without sleeps or unobservable background errors."""

    def __init__(self):
        self.pending = []

    def submit(self, function, *args):
        self.pending.append((function, args))

    def run_next(self):
        function, args = self.pending.pop(0)
        return function(*args)

    def shutdown(self, **kwargs):
        pass


class ScriptedGraph:
    def __init__(self, **kwargs):
        self.propagator = SimpleNamespace(get_graph_args=lambda: {})
        self.recorded = []

    def create_run_state(self, symbol, date, portfolio):
        assert portfolio.cash == 100000
        return {"symbol": symbol, "date": date}

    def stream_run(self, initial, **kwargs):
        yield (
            [],
            {
                "market_report": "Current sourced market evidence.",
                "final_rating": "Buy",
                "final_trade_decision": "Rating: Buy",
            },
        )

    def record_decision(self, symbol, date, final):
        self.recorded.append((symbol, date, final))


@pytest.fixture
def desk(tmp_path):
    broker = BrokerFake()
    service = DeskService(tmp_path / "desk", gateway=broker, graph_factory=ScriptedGraph)
    service.executor.shutdown(wait=True)
    service.executor = ManualExecutor()
    service.save_config({"universe": ["AAPL"], "name": "Test"})
    yield service, broker
    service.close()


def complete_run(service):
    run_id = service.start_run(["AAPL"])["run_id"]
    service.executor.run_next()
    assert service.state()["runs"][0]["status"] == "completed"
    return run_id


def create_proposal(service):
    run_id = complete_run(service)
    proposal = service.propose(run_id)["proposals"][0]
    assert proposal["status"] == "proposed"
    return proposal


@pytest.mark.parametrize("value", ["", "2026-2-01", "2026-02-30", "2999-01-01", 20260101, True, [], {}])
def test_invalid_analysis_date_fails_before_provider_access(desk, monkeypatch, value):
    service, broker = desk
    broker.calls.clear()
    def unexpected(*args, **kwargs):
        pytest.fail("Invalid dates must not probe providers")
    monkeypatch.setattr(service, "readiness", unexpected)
    with pytest.raises(ValueError, match="date|YYYY-MM-DD"):
        service.start_run(["AAPL"], analysis_date=value)
    assert broker.calls == []
    assert service.executor.pending == []


def test_omitted_analysis_date_uses_new_york_today(desk):
    from tradingagents.web.service import today
    service, _ = desk
    run_id = service.start_run(["AAPL"])["run_id"]
    assert service._find_run(run_id)["trade_date"] == today()


def test_historical_analysis_preserves_date_and_labels_current_portfolio(desk):
    service, broker = desk
    observed = {}
    class DatedGraph(ScriptedGraph):
        def create_run_state(self, symbol, date, portfolio):
            observed["date"] = date
            return {**super().create_run_state(symbol, date, portfolio), "portfolio_context": "Cash: 100000"}

        def stream_run(self, initial, **kwargs):
            observed["portfolio_context"] = initial["portfolio_context"]
            yield from super().stream_run(initial, **kwargs)

        def record_decision(self, symbol, date, final):
            observed["recorded_date"] = date

    service.graph_factory = DatedGraph
    run_id = service.start_run(["AAPL"], analysis_date="2020-01-02")["run_id"]
    service.executor.run_next()
    run = service._find_run(run_id)
    assert run["status"] == "completed"
    assert run["trade_date"] == run["results"][0]["trade_date"] == "2020-01-02"
    assert observed["date"] == observed["recorded_date"] == "2020-01-02"
    assert run["account_context"]["basis"] == "current"
    assert run["account_context"]["captured_at"]
    assert "not a historical portfolio snapshot" in observed["portfolio_context"]
    assert "Cash: 100000" in observed["portfolio_context"]
    assert json.loads(service.store.path.read_text())["runs"][0]["trade_date"] == "2020-01-02"
    with pytest.raises(ValueError, match="Analysis date"):
        service.propose(run_id)
    assert broker.submitted == []


@pytest.mark.parametrize("historical", [False, True])
def test_consumed_portfolio_evidence_survives_refresh_restart_and_export(desk, historical):
    service, broker = desk
    broker.account.update(cash="12345.6789012345", currency="CAD")
    broker.positions = [
        {"symbol": "MSFT", "qty": "-2.125", "avg_entry_price": "301.123456789"},
        {"symbol": "AAPL", "qty": "3.75"},
    ]
    observed = {}

    class PortfolioGraph(ScriptedGraph):
        def create_run_state(self, symbol, date, portfolio):
            observed["portfolio"] = portfolio.model_dump(mode="json")
            observed["text"] = portfolio.render(symbol)
            return {"portfolio_context": observed["text"]}

        def stream_run(self, initial, **kwargs):
            observed["input"] = copy.deepcopy(initial)
            yield from super().stream_run(initial, **kwargs)

    service.graph_factory = PortfolioGraph
    run_id = service.start_run(["AAPL"], analysis_date="2020-01-02" if historical else None)["run_id"]
    accepted = copy.deepcopy(service._find_run(run_id))
    preflight = copy.deepcopy(service.executor.pending[0][1][1])
    assert accepted["portfolio_evidence"]["status"] == "unavailable"
    # Change the live snapshot even before worker dispatch; it must use its own preflight book.
    broker.account.update(id="later-account", cash="999", currency="EUR")
    broker.positions = []
    service.refresh()
    service.executor.run_next()
    run = service._find_run(run_id)
    assert run["status"] == "completed"
    evidence = copy.deepcopy(run["portfolio_evidence"])
    assert evidence["status"] == "recorded"
    context = evidence["context"]
    assert context["portfolio"] == observed["portfolio"] == {
        "cash": 12345.6789012345, "currency": "USD",  # Existing graph currency policy is unchanged.
        "positions": [{"ticker": "MSFT", "quantity": -2.125, "average_price": 301.123456789},
                      {"ticker": "AAPL", "quantity": 3.75, "average_price": None}],
    }
    assert context["account_id"] == preflight["account"]["id"] == accepted["account_id"]
    assert context["analysis_date"] == run["trade_date"]
    assert context["account_context"] == accepted["account_context"]
    assert context["account_context"]["captured_at"] == preflight["updated_at"]
    assert context["account_context"]["basis"] == "current"
    assert "not a historical portfolio snapshot" in context["account_context"]["description"]
    assert observed["input"]["portfolio_context"] == (
        f"{accepted['account_context']['description']} Captured at {preflight['updated_at']}.\n" + observed["text"]
    )
    artifact = evidence["artifact"]
    path = service.store.directory / artifact["path"]
    payload = path.read_bytes()
    assert json.loads(payload) == context
    assert hashlib.sha256(payload).hexdigest() == artifact["sha256"]
    assert len(payload) == artifact["bytes"]
    assert "never-display" not in payload.decode()
    service.refresh()
    # Repeated recording cannot replace the first consumed book.
    service.store.record_portfolio_context(run_id, {"portfolio": {"cash": 999}})
    assert service._find_run(run_id)["portfolio_evidence"] == evidence
    recovered = DeskStore(service.store.directory, {})
    assert recovered.snapshot()["runs"][0]["portfolio_evidence"] == evidence
    assert "context" not in recovered.snapshot(compact=True)["runs"][0]["portfolio_evidence"]
    assert path.read_bytes() == payload
    assert len(list(path.parent.glob("portfolio-context-*.json"))) == 1
    assert broker.submitted == []


def test_legacy_portfolio_is_unknown_not_reconstructed(desk):
    service, _ = desk
    run_id = complete_run(service)
    service._find_run(run_id).pop("portfolio_evidence")
    service.store.save()
    recovered = DeskStore(service.store.directory, {})
    evidence = recovered.snapshot()["runs"][0]["portfolio_evidence"]
    assert evidence["status"] == "unavailable"
    assert "unknown" in evidence["reason"]
    assert "context" not in evidence and "artifact" not in evidence


def test_portfolio_artifact_failure_preserves_consumed_context_in_journal(desk, monkeypatch):
    service, _ = desk
    original = service.store._write_json_artifact

    def fail_portfolio(run_id, kind, content):
        if kind == "portfolio-context":
            raise OSError("offline fixture")
        return original(run_id, kind, content)

    monkeypatch.setattr(service.store, "_write_json_artifact", fail_portfolio)
    run_id = complete_run(service)
    evidence = service._find_run(run_id)["portfolio_evidence"]
    assert evidence["status"] == "journal_only"
    assert evidence["context"]["portfolio"]["cash"] == 100000
    assert "artifact" not in evidence
    assert DeskStore(service.store.directory, {}).snapshot()["runs"][0]["portfolio_evidence"] == evidence


@pytest.mark.parametrize("fail", [False, True])
def test_run_measurements_capture_real_callbacks_and_terminal_artifact(desk, monkeypatch, fail):
    from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
    from langchain_core.messages import AIMessage
    from langchain_core.tools import tool

    service, _ = desk
    clock = [100.0]
    monkeypatch.setattr("tradingagents.web.service.time.monotonic", lambda: clock[0])

    @tool
    def source(fail: bool) -> str:
        """An isolated source fixture."""
        clock[0] += 2
        if fail:
            raise ValueError("private source error")
        return "private source result"

    class MeasuredGraph(ScriptedGraph):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.model = FakeMessagesListChatModel(
                responses=[AIMessage(content="private response", usage_metadata={
                    "input_tokens": 3, "output_tokens": 2, "total_tokens": 5,
                }), AIMessage(content="private response without usage")],
                callbacks=kwargs["callbacks"],
            )

        def stream_run(self, initial, **kwargs):
            config = kwargs["config"]
            # Same handler bound to model and graph must count each actual invocation once.
            self.model.invoke("private prompt", config=config)
            source.invoke({"fail": False}, config=config)
            self.model.invoke("private prompt", config=config)
            try:
                source.invoke({"fail": True}, config=config)
            except ValueError:
                if fail:
                    raise
            yield from super().stream_run(initial, **kwargs)

    service.graph_factory = MeasuredGraph
    run_id = service.start_run(["AAPL"])["run_id"]
    clock[0] += 7  # Observable queue delay, without sleeping.
    service.executor.run_next()
    run = service.run_detail(run_id)
    measurements = run["measurements"]
    assert run["status"] == measurements["status"] == ("failed" if fail else "completed")
    assert measurements["started_at"] <= measurements["ended_at"]
    assert measurements["elapsed_seconds"] == 11
    assert next(s for s in measurements["stages"] if s["stage"] == "queue")["elapsed_seconds"] == 7
    assert next(s for s in measurements["stages"] if s["stage"] == "analysis")["elapsed_seconds"] == 4
    callbacks = measurements["callbacks"]
    assert callbacks["logical_calls"]["llm"] == {"started": 2, "ended": 2, "errors": 0, "elapsed_seconds": 0}
    assert callbacks["logical_calls"]["tool"] == {"started": 2, "ended": 1, "errors": 1, "elapsed_seconds": 4}
    assert callbacks["usage"] == {"availability": "partial", "calls_with_usage": 1, "input_tokens": 3, "output_tokens": 2}
    assert callbacks["provider_internal_attempts"] is None
    receipt = run["measurement_artifact"]
    payload = (service.store.directory / receipt["path"]).read_bytes()
    assert hashlib.sha256(payload).hexdigest() == receipt["sha256"]
    assert len(payload) == receipt["bytes"]
    assert json.loads(payload) == measurements
    assert b"private" not in payload
    saved = json.loads(service.store.path.read_text())["runs"][0]
    assert saved["measurement_artifact"] == receipt
    assert saved["measurements"] == measurements


def test_measurement_artifacts_are_distinct_and_missing_usage_is_unavailable(desk):
    service, _ = desk
    first = service.run_detail(complete_run(service))
    first_path = service.store.directory / first["measurement_artifact"]["path"]
    original = first_path.read_bytes()
    second = service.run_detail(complete_run(service))
    assert first["measurement_artifact"]["path"] != second["measurement_artifact"]["path"]
    assert first_path.read_bytes() == original
    assert second["measurements"]["callbacks"]["usage"] == {
        "availability": "unavailable", "calls_with_usage": 0, "input_tokens": None, "output_tokens": None,
    }


def test_failed_setup_retains_terminal_measurements(desk):
    service, _ = desk
    def failed_graph(**kwargs):
        raise ValueError("offline setup failure")
    service.graph_factory = failed_graph
    run_id = service.start_run(["AAPL"])["run_id"]
    service.executor.run_next()
    run = service.run_detail(run_id)
    assert run["status"] == "failed"
    assert run["measurements"]["ended_at"]
    assert run["measurement_artifact"]["sha256"]
    assert run["results"][0]["elapsed_seconds"] >= 0


def test_measurement_export_failure_keeps_measurements_in_journal(desk, monkeypatch):
    service, _ = desk
    def failed_export(*args):
        raise OSError("fixture disk failure")
    monkeypatch.setattr(service.store, "write_measurements", failed_export)
    run = service.run_detail(complete_run(service))
    assert "measurement_export_error" in run
    assert "measurement_artifact" not in run
    saved = json.loads(service.store.path.read_text())["runs"][0]
    assert saved["measurements"]["ended_at"]


def test_stats_callback_error_and_deduplication_preserve_cli_statistics():
    from uuid import uuid4

    from cli.stats_handler import StatsCallbackHandler

    stats = StatsCallbackHandler()
    run_id = uuid4()
    stats.on_chat_model_start({}, [], run_id=run_id)
    stats.on_llm_start({}, [], run_id=run_id)
    stats.on_llm_error(ValueError("private error"), run_id=run_id)
    stats.on_llm_error(ValueError("private error"), run_id=run_id)
    assert stats.get_stats() == {"llm_calls": 1, "tool_calls": 0, "tokens_in": 0, "tokens_out": 0}
    assert stats.get_measurements()["logical_calls"]["llm"]["errors"] == 1
    assert "private" not in json.dumps(stats.get_measurements())


def test_scheduling_failure_is_durable_and_measured(desk, monkeypatch):
    service, _ = desk
    def reject(*args):
        raise RuntimeError("executor unavailable")
    monkeypatch.setattr(service.executor, "submit", reject)
    with pytest.raises(RuntimeError, match="executor unavailable"):
        service.start_run(["AAPL"])
    run = json.loads(service.store.path.read_text())["runs"][0]
    assert run["status"] == run["measurements"]["status"] == "failed"
    assert run["measurements"]["ended_at"]
    assert run["measurement_artifact"]["sha256"]


def test_recovered_interrupted_run_exports_only_known_measurements(desk):
    service, _ = desk
    run_id = service.start_run(["AAPL"])["run_id"]
    recovered = DeskStore(service.store.directory, service.store.data["config"])
    run = recovered.data["runs"][0]
    assert run["id"] == run_id
    assert run["status"] == run["measurements"]["status"] == "interrupted"
    assert run["measurements"]["ended_at"] is None
    assert run["measurements"]["elapsed_seconds"] is None
    assert run["measurements"]["recovery_observed_at"]
    assert "unavailable" in run["measurements"]["completeness"]
    assert (recovered.directory / run["measurement_artifact"]["path"]).is_file()


@pytest.mark.parametrize("status", ["completed", "failed", "cancelled"])
@pytest.mark.parametrize("gap", ["terminal_checkpoint", "artifact_before_reference"])
def test_terminal_measurement_interruption_recovery_is_idempotent(desk, monkeypatch, status, gap):
    from uuid import uuid4

    from cli.stats_handler import StatsCallbackHandler

    service, broker = desk
    run_id = service.start_run(["AAPL"])["run_id"]
    run = service._find_run(run_id)
    run["status"] = status
    stats = StatsCallbackHandler()
    call_id = uuid4()
    stats.on_llm_start({}, ["private prompt"], run_id=call_id)
    stats.on_llm_error(ValueError("private error"), run_id=call_id)
    save = service.store.save
    calls = [0]

    class ProcessStopped(BaseException):
        pass

    def crash_save():
        calls[0] += 1
        if calls[0] == 1:
            save()  # Analytical terminal state has reached disk.
            if gap == "terminal_checkpoint":
                raise ProcessStopped()
        else:
            raise ProcessStopped()  # Artifact is durable; its reference is not.

    with monkeypatch.context() as patch:
        patch.setattr(service.store, "save", crash_save)
        with pytest.raises(ProcessStopped):
            service._finish_measurements(run, stats, 0.0)

    journal_before = json.loads(service.store.path.read_text())["runs"][0]
    assert journal_before["status"] == status
    assert not journal_before.get("measurement_artifact")
    directory = service.store.directory / "reports" / run_id
    artifacts_before = {p.name: p.read_bytes() for p in directory.glob("measurements-*.json")}
    if gap == "artifact_before_reference":
        assert len(artifacts_before) == 1
        known_final = json.loads(next(iter(artifacts_before.values())))
    else:
        assert artifacts_before == {}
    broker_calls = copy.deepcopy(broker.calls)
    recovered = DeskStore(service.store.directory, service.store.data["config"])
    restored = recovered.data["runs"][0]
    assert restored["status"] == status  # Never turn a completed analysis into interrupted.
    assert restored["completed_at"] == journal_before["completed_at"]
    assert restored["measurements"]["started_at"] == journal_before["measurements"]["started_at"]
    if gap == "artifact_before_reference":
        assert restored["measurements"] == known_final
        assert restored["measurement_artifact"]["path"].endswith(next(iter(artifacts_before)))
        assert len(list(directory.glob("measurements-*.json"))) == 1
    else:
        assert restored["measurements"]["ended_at"] is None
        assert restored["measurements"]["elapsed_seconds"] is None
        assert restored["measurements"]["callbacks_final"] is False
        assert restored["measurements"]["callbacks"] == journal_before["measurements"]["callbacks"]
        assert restored["measurements"]["stages"] == journal_before["measurements"]["stages"]
    receipt = restored["measurement_artifact"]
    artifact = (recovered.directory / receipt["path"]).read_bytes()
    assert hashlib.sha256(artifact).hexdigest() == receipt["sha256"]
    assert json.loads(artifact) == restored["measurements"]
    after = {p.name: p.read_bytes() for p in directory.glob("measurements-*.json")}
    again = DeskStore(service.store.directory, service.store.data["config"])
    assert again.data["runs"][0] == restored
    assert {p.name: p.read_bytes() for p in directory.glob("measurements-*.json")} == after
    assert all(after[name] == payload for name, payload in artifacts_before.items())
    assert again.data["proposals"] == service.store.data["proposals"]
    assert broker.calls == broker_calls


def test_finalized_run_does_not_reexport_on_startup(desk):
    service, _ = desk
    run = service.run_detail(complete_run(service))
    directory = service.store.directory / "reports" / run["id"]
    artifacts = {p.name: p.read_bytes() for p in directory.glob("measurements-*.json")}
    reopened = DeskStore(service.store.directory, service.store.data["config"])
    assert reopened.data["runs"][0] == run
    assert {p.name: p.read_bytes() for p in directory.glob("measurements-*.json")} == artifacts


def test_stats_callback_parallel_calls_are_counted_once():
    from uuid import uuid4

    from cli.stats_handler import StatsCallbackHandler

    stats = StatsCallbackHandler()
    def invoke(_):
        run_id = uuid4()
        stats.on_tool_start({}, "private input", run_id=run_id)
        stats.on_tool_end("private output", run_id=run_id)
    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(invoke, range(20)))
    calls = stats.get_measurements()["logical_calls"]["tool"]
    assert (calls["started"], calls["ended"], calls["errors"]) == (20, 20, 0)


@pytest.mark.parametrize("output", ["date,close\n2020-01-02,123.45\n", {"price": 123.45}, b"source bytes"])
def test_router_source_evidence_preserves_output_fallback_and_partial_failure(desk, monkeypatch, caplog, output):
    from tradingagents.dataflows import router
    from tradingagents.dataflows.errors import VendorUnavailableError

    service, _ = desk
    observed = []
    def first(symbol, start_date, end_date, api_key=None):
        raise VendorUnavailableError("api_key=never-record-this")
    def second(symbol, start_date, end_date, api_key=None):
        return output
    monkeypatch.setitem(router.VENDOR_METHODS, "get_stock_data", {"first": first, "second": second})
    monkeypatch.setattr(router, "get_vendor", lambda *args: "first,second")

    class SourceGraph(ScriptedGraph):
        def stream_run(self, initial, **kwargs):
            observed.append(router.route_to_vendor("get_stock_data", "AAPL", "2020-01-01", "2020-01-02", api_key="never-record-this"))
            yield from super().stream_run(initial, **kwargs)
            raise RuntimeError("Later analytical failure")

    service.graph_factory = SourceGraph
    run_id = service.start_run(["AAPL"])["run_id"]
    service.executor.run_next()
    run = service.run_detail(run_id)
    assert run["status"] == "failed"
    assert observed[0] is output
    evidence = run["source_evidence"]
    assert evidence["capture_complete"] is True
    assert evidence["coverage"] == "router_functions_and_social_ohlcv_inputs"
    failed, success = evidence["attempts"]
    assert (failed["vendor"], success["vendor"]) == ("first", "second")
    assert failed["outcome"] == "error"
    assert failed["error_class"] == "VendorUnavailableError"
    assert "artifact" not in failed
    assert success["outcome"] == "success"
    assert success["function"].endswith(".second")
    assert success["arguments"] == {"symbol": "AAPL", "start_date": "2020-01-01", "end_date": "2020-01-02"}
    assert success["started_at"] <= success["ended_at"]
    assert success["elapsed_seconds"] >= 0
    receipt = success["artifact"]
    payload = (service.store.directory / receipt["path"]).read_bytes()
    assert len(payload) == receipt["bytes"]
    assert hashlib.sha256(payload).hexdigest() == receipt["sha256"]
    decoded = json.loads(payload) if isinstance(output, dict) else payload.decode() if isinstance(output, str) else payload
    assert decoded == output
    assert "never-record-this" not in json.dumps(evidence)
    assert "never-record-this" not in caplog.text
    saved = json.loads(service.store.path.read_text())["runs"][0]
    assert saved["source_evidence"] == evidence
    assert "attempts" not in service.state(compact=True)["runs"][0]["source_evidence"]
    # Outside the completed run, router calls do not leak into its evidence.
    router.route_to_vendor("get_stock_data", "META", "2020-01-01", "2020-01-02")
    assert service.run_detail(run_id)["source_evidence"] == evidence


@pytest.mark.parametrize("failure", ["disk", "sensitive", "oversized", "unsupported"])
def test_router_capture_gap_is_explicit_without_changing_result(desk, monkeypatch, failure):
    from tradingagents.dataflows import router

    service, _ = desk
    output = {"disk": "valid source", "sensitive": {"api_key": "do-not-persist"},
              "oversized": "x" * (8 * 1024 * 1024 + 1), "unsupported": object()}[failure]
    def source(symbol):
        return output
    monkeypatch.setitem(router.VENDOR_METHODS, "get_stock_data", {"yfinance": source})
    monkeypatch.setattr(router, "get_vendor", lambda *args: "yfinance")
    if failure == "disk":
        def write_failure(*args):
            raise OSError("sensitive filesystem detail")
        monkeypatch.setattr(service.store, "_write_source_result", write_failure)

    class SourceGraph(ScriptedGraph):
        def stream_run(self, initial, **kwargs):
            assert router.route_to_vendor("get_stock_data", "AAPL") is output
            yield from super().stream_run(initial, **kwargs)

    service.graph_factory = SourceGraph
    run = service.run_detail(complete_run(service))
    evidence = run["source_evidence"]
    assert evidence["capture_complete"] is False
    attempt = evidence["attempts"][0]
    assert attempt["outcome"] == "success"
    assert attempt["capture"] == "unavailable"
    assert "artifact" not in attempt
    assert "sensitive filesystem detail" not in json.dumps(evidence)
    assert not list((service.store.directory / "reports" / run["id"]).glob("source-*"))


def test_router_evidence_isolated_across_concurrent_graph_contexts(tmp_path, monkeypatch):
    import threading
    from typing import TypedDict
    from uuid import uuid4

    from langgraph.graph import END, START, StateGraph

    from tradingagents.dataflows import router
    from tradingagents.dataflows.config import run_config_context

    store = DeskStore(tmp_path / "evidence", {})
    barrier = threading.Barrier(2, timeout=5)
    def source(symbol):
        def acquire():
            barrier.wait()
            return f"source for {symbol}"
        return router.observe_source_call("social_fixture", "fixture", "http_response_bytes", acquire, symbol=symbol)
    monkeypatch.setitem(router.VENDOR_METHODS, "get_stock_data", {"yfinance": source})
    monkeypatch.setattr(router, "get_vendor", lambda *args: "yfinance")

    class State(TypedDict):
        symbol: str

    def acquire(state):
        router.route_to_vendor("get_stock_data", state["symbol"])
        return {}

    graph = StateGraph(State)
    graph.add_node("source", acquire)
    graph.add_edge(START, "source")
    graph.add_edge("source", END)
    compiled = graph.compile()
    ids = [str(uuid4()), str(uuid4())]
    for run_id in ids:
        store.data["runs"].append({"id": run_id, "status": "running", "source_evidence": {
            "coverage": "router_vendor_functions_only", "capture_complete": True, "attempts": [],
        }})
    def run(pair):
        run_id, symbol = pair
        with router.capture_vendor_evidence(lambda receipt, output: store.record_source_attempt(run_id, receipt, output)):
            # The production graph uses this context-copy boundary before its child tasks.
            context = run_config_context({})
            context.run(compiled.invoke, {"symbol": symbol})
    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(run, zip(ids, ["AAPL", "META"], strict=True)))
    paths = []
    for record, symbol in zip(store.data["runs"], ["AAPL", "META"], strict=True):
        attempts = record["source_evidence"]["attempts"]
        assert len(attempts) == 2
        assert attempts[1]["parent_attempt_id"] == attempts[0]["attempt_id"]
        assert attempts[1]["arguments"] == {"symbol": symbol}
        assert attempts[0]["arguments"] == {"symbol": symbol}
        path = store.directory / attempts[0]["artifact"]["path"]
        paths.append(path)
        assert path.read_text() == f"source for {symbol}"
    assert paths[0] != paths[1]


def test_router_journal_checkpoint_failure_remains_explicit(desk, monkeypatch):
    from tradingagents.dataflows import router

    service, _ = desk
    def source(symbol):
        return "bounded source response"
    monkeypatch.setitem(router.VENDOR_METHODS, "get_stock_data", {"yfinance": source})
    monkeypatch.setattr(router, "get_vendor", lambda *args: "yfinance")
    class SourceGraph(ScriptedGraph):
        def stream_run(self, initial, **kwargs):
            assert router.route_to_vendor("get_stock_data", "AAPL") == "bounded source response"
            yield from super().stream_run(initial, **kwargs)
    service.graph_factory = SourceGraph
    run_id = service.start_run(["AAPL"])["run_id"]
    save = service.store.save
    failed = []
    def checkpoint():
        if service._find_run(run_id)["source_evidence"]["attempts"] and not failed:
            failed.append(True)
            raise OSError("private filesystem error")
        save()
    monkeypatch.setattr(service.store, "save", checkpoint)
    service.executor.run_next()
    run = service.run_detail(run_id)
    assert run["status"] == "completed"
    evidence = run["source_evidence"]
    assert evidence["capture_complete"] is False
    assert "persistence_error" in evidence
    assert evidence["attempts"][0]["artifact"]["sha256"]
    assert "private filesystem error" not in json.dumps(evidence)
    assert json.loads(service.store.path.read_text())["runs"][0]["source_evidence"] == evidence


def test_consumed_frame_artifact_preserves_precision_dtypes_axes_and_missing_values(desk, monkeypatch):
    import struct

    import numpy as np
    import pandas as pd

    from tradingagents.dataflows import router

    service, _ = desk
    frame = pd.DataFrame({
        "Close": [np.nextafter(1.0, 2.0), -0.0, np.nan],
        "Small": np.array([np.nextafter(np.float32(1), np.float32(2)), -0.0, np.inf], dtype="float32"),
        "Volume": pd.Series([2**63 - 1, pd.NA, -1], dtype="Int64"),
        "When": pd.to_datetime(["2026-01-01T00:00:00.000000123Z", None, "2026-01-03T00:00:00Z"], format="mixed"),
        "Label": pd.Series([None, "exact text", float("nan")], dtype="object"),
    })
    frame.index = pd.date_range("2026-01-01T12:00:00.000000123", periods=3, tz="America/New_York", name="Date")
    frame.columns.name = "Fields"
    original = frame.copy(deep=True)
    run_id = service.start_run(["AAPL"])["run_id"]
    def acquire(symbol):
        return router.observe_source_call("ohlcv_history", "yfinance", "yahoo_sdk_dataframe", lambda: frame, symbol=symbol)
    monkeypatch.setitem(router.VENDOR_METHODS, "get_stock_data", {"yfinance": acquire})
    monkeypatch.setattr(router, "get_vendor", lambda *args: "yfinance")
    with router.capture_vendor_evidence(lambda receipt, output: service.store.record_source_attempt(run_id, receipt, output)):
        assert router.route_to_vendor("get_stock_data", "AAPL") is frame
    pd.testing.assert_frame_equal(frame, original)
    parent, child = service.run_detail(run_id)["source_evidence"]["attempts"]
    assert child["parent_attempt_id"] == parent["attempt_id"]
    assert child["origin"] == "yahoo_sdk_dataframe"
    assert parent["origin"] == "vendor_function_return"
    receipt = child["artifact"]
    assert receipt["format"] == "pandas-frame-v1-json"
    payload = (service.store.directory / receipt["path"]).read_bytes()
    assert hashlib.sha256(payload).hexdigest() == receipt["sha256"]
    encoded = json.loads(payload)

    def scalar(value):
        kind = value["type"]
        if kind == "numpy":
            return np.frombuffer(bytes.fromhex(value["hex"]), dtype=value["dtype"])[0]
        if kind == "float64":
            return struct.unpack(">d", bytes.fromhex(value["hex"]))[0]
        if kind == "int":
            return int(value["decimal"])
        if kind == "timestamp":
            timestamp = pd.Timestamp(int(value["nanoseconds"]), unit="ns")
            return timestamp.tz_localize("UTC").tz_convert(value["timezone"]) if value["timezone"] else timestamp
        if kind == "pd.NA":
            return pd.NA
        if kind == "pd.NaT":
            return pd.NaT
        return None if kind == "none" else value["value"]

    columns = [scalar(v) for v in encoded["columns"]["values"]]
    reconstructed = pd.DataFrame({name: pd.Series([scalar(row[i]) for row in encoded["data"]],
                                                 dtype=encoded["dtypes"][i]["name"])
                                  for i, name in enumerate(columns)})
    reconstructed.index = pd.DatetimeIndex([scalar(v) for v in encoded["index"]["values"]],
                                           name=scalar(encoded["index"]["name"]), freq=encoded["index"]["frequency"])
    reconstructed.columns.name = scalar(encoded["columns"]["name"])
    pd.testing.assert_frame_equal(reconstructed, original, check_exact=True)
    assert reconstructed["Close"].to_numpy().tobytes() == original["Close"].to_numpy().tobytes()
    assert reconstructed["Small"].to_numpy().tobytes() == original["Small"].to_numpy().tobytes()


@pytest.mark.parametrize("shape", ["multiindex", "category", "object", "attributes", "credentials"])
def test_unsupported_consumed_frames_are_explicit_gaps_without_mutation(desk, shape):
    import pandas as pd

    from tradingagents.dataflows.router import capture_vendor_evidence, observe_source_call

    service, _ = desk
    frame = pd.DataFrame({"Close": [1.0]})
    if shape == "multiindex":
        frame.index = pd.MultiIndex.from_tuples([("AAPL", 1)])
    elif shape == "category":
        frame["Close"] = frame["Close"].astype("category")
    elif shape == "object":
        frame["Close"] = [object()]
    elif shape == "credentials":
        frame["api_key"] = ["must-not-be-written"]
    else:
        frame.attrs["custom"] = "not silently dropped"
    original = frame.copy(deep=True)
    run_id = service.start_run(["AAPL"])["run_id"]
    with capture_vendor_evidence(lambda receipt, output: service.store.record_source_attempt(run_id, receipt, output)):
        assert observe_source_call("ohlcv_history", "yfinance", "yahoo_sdk_dataframe", lambda: frame) is frame
    pd.testing.assert_frame_equal(frame, original)
    evidence = service.run_detail(run_id)["source_evidence"]
    assert evidence["capture_complete"] is False
    assert evidence["attempts"][0]["capture"] == "unavailable"
    assert "artifact" not in evidence["attempts"][0]


@pytest.mark.parametrize("raw", [
    b'<rss>{&amp;quot;api_key&amp;quot;:&amp;quot;placeholder&amp;quot;}</rss>',
    b'<rss>{&#34;api_key&#34;:&#34;placeholder&#34;}</rss>',
    json.dumps({"body": json.dumps({"api_key": "placeholder"})}).encode(),
    b'{"\\u0061pi_key":"placeholder"}',
    b'not-utf8-\xff',
    b'&amp;amp;amp;amp;amp;amp;amp;quot;too deep',
])
def test_encoded_unsafe_or_unsupported_response_is_a_gap_without_changing_result(desk, raw):
    from tradingagents.dataflows.router import capture_vendor_evidence, observe_source_call

    service, _ = desk
    run_id = service.start_run(["AAPL"])["run_id"]
    calls = []
    def read_response():
        calls.append(1)
        return raw
    with capture_vendor_evidence(lambda receipt, output: service.store.record_source_attempt(run_id, receipt, output)):
        assert observe_source_call("rss_fixture", "fixture", "http_response_bytes", read_response) is raw
    evidence = service.run_detail(run_id)["source_evidence"]
    assert calls == [1]
    assert evidence["capture_complete"] is False
    assert evidence["attempts"][0]["outcome"] == "success"
    assert evidence["attempts"][0]["capture"] == "unavailable"
    assert "artifact" not in evidence["attempts"][0]
    assert not list((service.store.directory / "reports" / run_id).glob("source-*"))


@pytest.mark.parametrize("raw", [
    b'<rss>&amp;quot;AAPL &amp;amp; META&amp;quot;</rss>',
    json.dumps({"body": json.dumps({"company": 'AAPL "quoted"', "close": 123.45})}).encode(),
])
def test_decoded_screening_keeps_safe_original_bytes_and_hash(desk, raw):
    from tradingagents.dataflows.router import capture_vendor_evidence, observe_source_call

    service, _ = desk
    run_id = service.start_run(["AAPL"])["run_id"]
    calls = []
    def read_response():
        calls.append(1)
        return raw
    with capture_vendor_evidence(lambda receipt, output: service.store.record_source_attempt(run_id, receipt, output)):
        assert observe_source_call("social_fixture", "fixture", "http_response_bytes", read_response) is raw
    receipt = service.run_detail(run_id)["source_evidence"]["attempts"][0]["artifact"]
    assert (service.store.directory / receipt["path"]).read_bytes() == raw
    assert receipt["sha256"] == hashlib.sha256(raw).hexdigest()
    assert receipt["bytes"] == len(raw)
    assert calls == [1]


@pytest.mark.parametrize("axis_name", ["index", "columns"])
@pytest.mark.parametrize("dtype, bits", [
    ("float32", [0x7f800001, 0x80000000, 0x7fc00005, 0x3f800001]),
    ("float64", [0x7ff0000000000001, 0x8000000000000000, 0x7ff8000000000005, 0x3ff0000000000001]),
    ("uint64", [0, 2**53 + 1, 2**63 + 1, 2**64 - 1]),
])
def test_numeric_frame_axes_preserve_scalar_bits(axis_name, dtype, bits):
    import numpy as np
    import pandas as pd

    values = np.array(bits, dtype="uint32" if dtype == "float32" else "uint64").view(dtype)
    axis = pd.Index(values, name="numeric")
    frame = (pd.DataFrame({"Close": range(len(values))}, index=axis) if axis_name == "index"
             else pd.DataFrame([range(len(values))], columns=axis))
    before = getattr(frame, axis_name).to_numpy(copy=True).tobytes()
    encoded = DeskStore._frame_evidence(frame)[axis_name]
    assert encoded["dtype"]["name"] == dtype
    assert all(value["type"] == "numpy" for value in encoded["values"])
    recovered = b"".join(bytes.fromhex(value["hex"]) for value in encoded["values"])
    assert recovered == before == values.tobytes()
    assert getattr(frame, axis_name).to_numpy().tobytes() == before


def test_nullable_numeric_axis_keeps_missing_distinct_from_integer():
    import pandas as pd

    frame = pd.DataFrame({"Close": [1, 2]}, index=pd.Index(pd.array([2**63 - 1, pd.NA], dtype="Int64")))
    encoded = DeskStore._frame_evidence(frame)["index"]
    assert encoded["dtype"]["name"] == "Int64"
    assert encoded["values"][0]["type"] == "numpy"
    assert encoded["values"][1] == {"type": "pd.NA"}


def test_refresh_normalizes_actual_snapshot_and_never_exposes_config_secrets(desk):
    service, broker = desk
    state = service.refresh()
    assert state["connection"]["paper_verified"] is True
    assert state["account"]["id"] == "paper-account"
    assert state["quotes"]["AAPL"]["price"] == 100
    assert "never-display" not in json.dumps(state)
    assert "paper_account_id" not in state
    assert broker.submitted == []


@pytest.mark.parametrize(
    "failed_command,source",
    [
        ("get_account_info", "account"),
        ("get_all_positions", "positions"),
        ("get_orders", "orders"),
        ("get_stock_snapshot", "quotes"),
    ],
)
def test_failed_refresh_cannot_use_stale_account_or_treat_failed_book_as_empty(
    desk, failed_command, source
):
    service, broker = desk
    service.refresh()
    broker.errors[failed_command] = GatewayError("source unavailable")
    state = service.refresh()
    assert any(error["source"] == source for error in state["errors"])
    with pytest.raises(ValueError, match="complete broker data"):
        service._book()
    if source == "account":
        assert state["account"] is None
    assert broker.submitted == []


@pytest.mark.parametrize("paper", ["false", "", "1"])
def test_nonpaper_connection_never_starts_analysis_or_submits(desk, paper):
    service, broker = desk
    broker.paper = paper
    with pytest.raises(ValueError, match="verified paper"):
        service.start_run(["AAPL"])
    assert broker.submitted == []


def test_changed_broker_account_is_blocked_and_original_pin_persists(desk):
    service, broker = desk
    proposal = create_proposal(service)
    broker.account["id"] = "other-account"
    with pytest.raises(ValueError, match="verified paper"):
        service.submit(proposal["id"])
    assert service.store.data["paper_account_id"] == "paper-account"
    assert service.state()["connection"]["paper_verified"] is False
    assert broker.submitted == []


def test_run_collects_reports_and_laya_gate_without_broker_mutation(desk):
    service, broker = desk
    complete_run(service)
    result = service.state()["runs"][0]["results"][0]
    assert result["rating"] == "Buy"
    assert result["laya"]["auto_execute"] is True
    assert result["reports"]["market_report"]
    assert broker.submitted == []


@pytest.mark.parametrize(
    "grade,value", [("ask_human", True), ("auto_execute", False), ("auto_execute", "true")]
)
def test_laya_requires_auto_grade_and_actual_boolean_yes_answers(desk, grade, value):
    service, broker = desk
    broker.laya_grade, broker.laya_value = grade, value
    run_id = complete_run(service)
    assert service.state()["runs"][0]["results"][0]["laya"]["auto_execute"] is False
    assert service.propose(run_id)["proposals"][0]["status"] == "blocked"


def test_submit_uses_exact_stock_order_schema_and_duplicate_submit_is_rejected(desk):
    service, broker = desk
    proposal = create_proposal(service)
    receipt = service.submit(proposal["id"])
    assert receipt["order"]["id"] == "broker-order"
    assert len(broker.submitted) == 1
    assert broker.submitted[0]["client_order_id"] == proposal["client_order_id"]
    with pytest.raises(ValueError, match="unknown|proposed"):
        service.submit(proposal["id"])
    assert len(broker.submitted) == 1


def test_unknown_submission_is_persisted_and_never_retried(desk):
    service, broker = desk
    proposal = create_proposal(service)
    broker.submit_error = TimeoutError("lost receipt")
    with pytest.raises(ValueError, match="unknown"):
        service.submit(proposal["id"])
    assert service.store.snapshot()["proposals"][0]["status"] == "unknown"
    persisted = json.loads(service.store.path.read_text(encoding="utf-8"))
    assert persisted["proposals"][0]["status"] == "unknown"
    with pytest.raises(ValueError, match="unknown|proposed"):
        service.submit(proposal["id"])
    assert len(broker.submitted) == 1


def test_simultaneous_duplicate_submission_sends_at_most_one_broker_request(desk):
    service, broker = desk
    proposal = create_proposal(service)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(service.submit, proposal["id"]) for _ in range(2)]
        outcomes = []
        for future in futures:
            try:
                outcomes.append(future.result())
            except ValueError as exc:
                outcomes.append(exc)
    assert sum(isinstance(outcome, dict) for outcome in outcomes) == 1
    assert sum(isinstance(outcome, ValueError) for outcome in outcomes) == 1
    assert len(broker.submitted) == 1


def test_unknown_submission_blocks_other_proposals_and_new_plans(desk):
    service, broker = desk
    first = create_proposal(service)
    second = create_proposal(service)
    third_run = complete_run(service)
    broker.submit_error = TimeoutError("lost receipt")
    with pytest.raises(ValueError, match="unknown"):
        service.submit(first["id"])
    with pytest.raises(ValueError, match="unknown"):
        service.submit(second["id"])
    with pytest.raises(ValueError, match="unknown"):
        service.propose(third_run)
    assert len(broker.submitted) == 1


def test_unknown_receipt_outside_recent_orders_reconciles_by_exact_client_id(desk):
    service, broker = desk
    proposal = create_proposal(service)
    broker.submit_error = TimeoutError("lost receipt")
    with pytest.raises(ValueError):
        service.submit(proposal["id"])
    broker.receipts[proposal["client_order_id"]] = {
        "id": "late-receipt",
        "client_order_id": proposal["client_order_id"],
        "status": "filled",
        "filled_qty": "49",
    }
    service.refresh()
    updated = service.state()["proposals"][0]
    assert updated["status"] == "filled"
    assert updated["broker_order_id"] == "late-receipt"
    assert len(broker.submitted) == 1


def test_recent_orders_reconcile_unknown_without_resubmitting(desk):
    service, broker = desk
    proposal = create_proposal(service)
    service.store.data["proposals"][0]["status"] = "unknown"
    broker.orders = [
        {
            "id": "known",
            "client_order_id": proposal["client_order_id"],
            "status": "filled",
            "filled_qty": "49",
            "filled_avg_price": "100",
        }
    ]
    service.refresh()
    assert service.state()["proposals"][0]["status"] == "filled"
    assert broker.submitted == []


def test_settings_change_expires_existing_proposals(desk):
    service, broker = desk
    proposal = create_proposal(service)
    service.save_config({"max_order_notional": 1000})
    assert service.state()["proposals"][0]["status"] == "expired"
    with pytest.raises(ValueError):
        service.submit(proposal["id"])
    assert broker.submitted == []


def test_invalid_settings_leave_journal_unchanged(desk):
    service, _ = desk
    previous = service.store.path.read_bytes()
    with pytest.raises(ValueError):
        service.save_config({"allocation_pct": 95, "reserve_pct": 20})
    assert service.store.path.read_bytes() == previous


def test_one_active_run_blocks_second_run_and_settings_changes(desk):
    service, _ = desk
    service.start_run(["AAPL"])
    with pytest.raises(ValueError, match="already running"):
        service.start_run(["AAPL"])
    with pytest.raises(ValueError, match="current analysis"):
        service.save_config({"name": "Changed"})


def test_cancel_queued_run_does_not_start_graph_or_laya(desk):
    service, broker = desk
    run_id = service.start_run(["AAPL"])["run_id"]
    service.cancel_run(run_id)
    service.executor.run_next()
    assert service.state()["runs"][0]["status"] == "cancelled"
    assert not any(domain == "laya" for domain, _, _ in broker.calls)


def test_cancel_running_analysis_stops_at_next_graph_step(desk):
    service, broker = desk
    run_id = service.start_run(["AAPL"])["run_id"]

    class CancelGraph(ScriptedGraph):
        def stream_run(self, initial, **kwargs):
            service.cancel_run(run_id)
            yield [], {"final_rating": "Buy"}

    service.graph_factory = CancelGraph
    service.executor.run_next()
    run = service.state()["runs"][0]
    assert run["status"] == "cancelled"
    assert run["results"][0]["status"] == "cancelled"
    assert not any(domain == "laya" for domain, _, _ in broker.calls)


def test_malformed_account_does_not_leave_run_stuck_running(desk):
    service, broker = desk
    broker.account.pop("cash")
    try:
        service.start_run(["AAPL"])
    except ValueError:
        assert not service.state()["runs"]
        return
    service.executor.run_next()
    assert service.state()["runs"][0]["status"] == "failed"


def test_boolean_account_balance_is_not_valid_numeric_context(desk):
    service, broker = desk
    broker.account["cash"] = True
    with pytest.raises(ValueError, match="invalid"):
        service.start_run(["AAPL"])
    assert not service.state()["runs"]


def test_boolean_quote_price_cannot_be_coerced_to_one_dollar():
    quotes = normalize_quotes(
        {"AAPL": {"latestTrade": {"p": True, "t": datetime.now(UTC).isoformat()}}}
    )
    assert quotes["AAPL"]["price"] is None


def test_graph_failure_is_terminal_and_cannot_produce_an_order_plan(desk):
    service, broker = desk

    class FailingGraph(ScriptedGraph):
        def stream_run(self, initial, **kwargs):
            raise RuntimeError("Source unavailable")
            yield  # pragma: no cover -- retain the stream generator contract.

    service.graph_factory = FailingGraph
    run_id = service.start_run(["AAPL"])["run_id"]
    service.executor.run_next()
    run = service.state()["runs"][0]
    assert run["status"] == "failed"
    assert run["results"][0]["status"] == "failed"
    assert "Source unavailable" in run["results"][0]["error"]
    with pytest.raises(ValueError, match="fresh analysis"):
        service.propose(run_id)
    assert broker.submitted == []


def test_pause_prevents_new_submission_and_untradable_asset_is_rejected(desk):
    service, broker = desk
    proposal = create_proposal(service)
    service.pause(True)
    with pytest.raises(ValueError, match="paused"):
        service.submit(proposal["id"])
    service.pause(False)
    broker.asset_tradable = False
    with pytest.raises(ValueError, match="tradable"):
        service.submit(proposal["id"])
    assert broker.submitted == []


def test_stale_proposal_does_not_submit(desk):
    service, broker = desk
    proposal = create_proposal(service)
    service.store.data["proposals"][0]["created_at"] = (
        datetime.now(UTC) - timedelta(minutes=16)
    ).isoformat()
    with pytest.raises(ValueError, match="15 minutes"):
        service.submit(proposal["id"])
    assert broker.submitted == []


def test_cannot_cancel_an_order_not_created_by_this_workspace(desk):
    service, broker = desk
    with pytest.raises(ValueError, match="workspace"):
        service.cancel_order("someone-elses-order")
    assert not any(command == "cancel_order_by_id" for _, command, _ in broker.calls)


@pytest.mark.parametrize("command", ["get_stock_snapshot", "get_all_positions", "get_orders"])
def test_cancel_owned_order_survives_unrelated_source_outage(desk, command):
    service, broker = desk
    proposal = create_proposal(service)
    service.submit(proposal["id"])
    broker.errors[command] = GatewayError("Source unavailable")
    assert service.cancel_order("broker-order")["status"] == "cancel_requested"
    assert any(c == "cancel_order_by_id" for _, c, _ in broker.calls)


@pytest.mark.parametrize("domain", ["laya", "maenifold.memory"])
def test_cancel_owned_order_does_not_depend_on_research_domains(desk, monkeypatch, domain):
    service, broker = desk
    proposal = create_proposal(service)
    service.submit(proposal["id"])
    discover = broker.discover

    def broken_research(selected):
        if selected == domain:
            raise GatewayError("Research domain unavailable")
        return discover(selected)

    monkeypatch.setattr(broker, "discover", broken_research)
    assert service.cancel_order("broker-order")["status"] == "cancel_requested"
    assert any(c == "cancel_order_by_id" for _, c, _ in broker.calls)


@pytest.mark.parametrize("condition", ["changed", "live", "unavailable"])
def test_cancel_owned_order_still_requires_current_paper_account(desk, condition):
    service, broker = desk
    proposal = create_proposal(service)
    service.submit(proposal["id"])
    if condition == "changed":
        broker.account["id"] = "different-account"
    elif condition == "live":
        broker.paper = "false"
    else:
        broker.errors["get_account_info"] = GatewayError("Account unavailable")
    with pytest.raises(ValueError, match="paper account"):
        service.cancel_order("broker-order")
    assert not any(c == "cancel_order_by_id" for _, c, _ in broker.calls)


def test_displayed_provider_overrides_hidden_tier_environment(desk, monkeypatch):
    service, _ = desk
    for tier in ("QUICK", "DEEP"):
        monkeypatch.setenv(f"TRADINGAGENTS_{tier}_THINK_PROVIDER", "anthropic")
        monkeypatch.setenv(f"TRADINGAGENTS_{tier}_THINK_BACKEND_URL", "http://hidden.invalid")
    service.save_config({"llm_provider": "openai", "backend_url": None})
    observed = []

    class CapturingGraph(ScriptedGraph):
        def __init__(self, **kwargs):
            observed.append(kwargs["config"])
            super().__init__(**kwargs)

    service.graph_factory = CapturingGraph
    complete_run(service)
    for tier in ("quick", "deep"):
        assert observed[0][f"{tier}_think_provider"] == "openai"
        assert observed[0][f"{tier}_think_backend_url"] is None


@pytest.mark.parametrize(
    ("endpoint", "api_version", "expected_missing"),
    [(None, None, "OPENAI_API_VERSION"),
     ("https://example.openai.azure.com", None, "OPENAI_API_VERSION"),
     (None, "2025-03-01-preview", "AZURE_OPENAI_ENDPOINT")],
)
def test_azure_readiness_requires_endpoint_and_api_version(
    desk, monkeypatch, endpoint, api_version, expected_missing
):
    service, _ = desk
    service.graph_factory = None
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
    monkeypatch.delenv("OPENAI_API_VERSION", raising=False)
    if api_version:
        monkeypatch.setenv("OPENAI_API_VERSION", api_version)
    readiness = service.readiness({"llm_provider": "azure", "backend_url": endpoint})
    assert readiness["ready"] is False
    assert expected_missing in readiness["message"]


@pytest.mark.parametrize("from_environment", [True, False])
def test_azure_readiness_accepts_complete_endpoint_configuration(desk, monkeypatch, from_environment):
    service, _ = desk
    service.graph_factory = None
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_API_VERSION", "2025-03-01-preview")
    monkeypatch.delenv("AZURE_OPENAI_DEPLOYMENT_NAME", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
    config = {"llm_provider": "azure", "backend_url": None}
    if from_environment:
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    else:
        config["backend_url"] = "https://example.openai.azure.com"
    assert service.readiness(config)["ready"] is True


def test_azure_readiness_rejects_hidden_deployment_override(desk, monkeypatch):
    service, _ = desk
    service.graph_factory = None
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_API_VERSION", "2025-03-01-preview")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT_NAME", "actual-deployment")
    config = {"llm_provider": "azure", "backend_url": "https://example.openai.azure.com",
              "quick_think_llm": "shown-quick", "deep_think_llm": "shown-deep"}
    assert service.readiness(config)["ready"] is False
    config.update(quick_think_llm="actual-deployment", deep_think_llm="actual-deployment")
    assert service.readiness(config)["ready"] is True


def test_chatgpt_readiness_uses_account_without_api_key_and_caches_polling(desk, monkeypatch):
    from tradingagents.llm_clients import chatgpt_client

    service, _ = desk
    service.graph_factory = None
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    calls = []
    monkeypatch.setattr(chatgpt_client, "check_chatgpt_account", lambda **kw: calls.append(kw))
    config = {"llm_provider": "chatgpt"}
    assert service.readiness(config)["ready"] is True
    assert service.readiness(config)["ready"] is True
    assert calls == [{"timeout": 10}]

    def signed_out(**kwargs):
        raise RuntimeError("Sign in with ChatGPT using codex login.")

    monkeypatch.setattr(chatgpt_client, "check_chatgpt_account", signed_out)
    # Starting research must recheck even if a recent state poll was ready.
    assert service.readiness(config, refresh=True) == {
        "ready": False, "message": "Sign in with ChatGPT using codex login."
    }


def test_state_reads_never_probe_codex_or_gateway_even_after_cache_expiry(desk, monkeypatch):
    from tradingagents.llm_clients import chatgpt_client

    service, broker = desk
    service.graph_factory = None
    probes = []
    monkeypatch.setattr(chatgpt_client, "check_chatgpt_account", lambda **kw: probes.append(kw))
    service.save_config({"llm_provider": "chatgpt"})
    assert service.state()["readiness"]["ready"] is None
    service.account_status = (0, {"ready": True, "message": "Cached status"})
    for _ in range(50):
        assert service.state(compact=True)["readiness"]["message"] == "Cached status"
    assert probes == []
    assert broker.calls == []


def test_chatgpt_account_timeout_is_actionable_and_blocks_research(desk, monkeypatch):
    from tradingagents.llm_clients import chatgpt_client

    service, _ = desk
    service.graph_factory = None
    service.save_config({"llm_provider": "chatgpt"})

    def unavailable(**kwargs):
        raise TimeoutError("Codex account check timed out.")

    monkeypatch.setattr(chatgpt_client, "check_chatgpt_account", unavailable)
    with pytest.raises(ValueError, match="account check timed out"):
        service.start_run(["AAPL"])
    assert service.store.snapshot()["runs"] == []


def test_journal_recovers_interrupted_runs_and_submissions_without_retry(tmp_path):
    defaults = {"name": "Test"}
    store = DeskStore(tmp_path, defaults)
    store.data["runs"] = [{"id": "r", "status": "running"}]
    store.data["proposals"] = [{"id": "p", "status": "submitting", "client_order_id": "durable-id"}]
    store.save()
    recovered = DeskStore(tmp_path, defaults).snapshot()
    assert recovered["runs"][0]["status"] == "interrupted"
    assert recovered["proposals"][0]["status"] == "unknown"
    assert recovered["proposals"][0]["client_order_id"] == "durable-id"


def test_journal_snapshot_cannot_mutate_persistent_state(tmp_path):
    store = DeskStore(tmp_path, {"name": "Test"})
    detached = store.snapshot()
    detached["config"]["name"] = "Mutated"
    assert store.snapshot()["config"]["name"] == "Test"


def test_invalid_journal_is_preserved_for_recovery(tmp_path):
    path = tmp_path / "desk.json"
    path.write_text("not json", encoding="utf-8")
    with pytest.raises(ValueError):
        DeskStore(tmp_path, {})
    assert path.read_text(encoding="utf-8") == "not json"


def test_journal_retries_only_transient_local_replace_error(tmp_path, monkeypatch):
    store = DeskStore(tmp_path, {"name": "Before"})
    original_replace = store_module.os.replace
    attempts = []

    def locked_once(source, target):
        attempts.append((source, target))
        if len(attempts) == 1:
            raise PermissionError("temporary sharing violation")
        return original_replace(source, target)

    monkeypatch.setattr(store_module.os, "replace", locked_once)
    monkeypatch.setattr(store_module.time, "sleep", lambda duration: None)
    store.data["config"]["name"] = "After"
    store.save()
    assert len(attempts) == 2
    assert json.loads(store.path.read_text(encoding="utf-8"))["config"]["name"] == "After"


def test_persistent_replace_error_is_bounded_and_preserves_previous_journal(tmp_path, monkeypatch):
    store = DeskStore(tmp_path, {"name": "Before"})
    before = store.path.read_bytes()
    attempts = []

    def always_locked(source, target):
        attempts.append((source, target))
        raise PermissionError("persistent sharing violation")

    monkeypatch.setattr(store_module.os, "replace", always_locked)
    monkeypatch.setattr(store_module.time, "sleep", lambda duration: None)
    store.data["config"]["name"] = "After"
    with pytest.raises(PermissionError):
        store.save()
    assert len(attempts) == 3
    assert store.path.read_bytes() == before
