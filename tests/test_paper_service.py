"""Offline paper desk workflow tests; the fake never contacts a broker."""

from __future__ import annotations

import copy
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
