"""Offline allocation contract: research advises; configured policy sizes proposals."""
import importlib
import json

import pytest

from tests.test_paper_service import desk, ScriptedGraph  # noqa: F401
from tests.test_paper_engine import inputs  # noqa: F401
from tradingagents.paper import engine


def test_service_injects_actual_policy_for_full_configured_universe(desk):
    service, broker = desk
    captured = []

    class Capture(ScriptedGraph):
        def stream_run(self, initial, **kwargs):
            captured.append(initial)
            yield from super().stream_run(initial, **kwargs)

    service.graph_factory = Capture
    service.save_config({"universe": ["AAPL", "MSFT", "META", "NVDA"],
                         "allocation_pct": 64, "max_position_pct": 19,
                         "reserve_pct": 23, "max_order_notional": 4321,
                         "price_buffer_bps": 17})
    service.start_run(["AAPL"])
    service.executor.run_next()
    assert service.state()["runs"][0]["status"] == "completed"
    policy = captured[0].get("desk_execution_policy", "")
    assert policy, "DeskService must inject the saved policy into stream_run input"
    for value in ("64", "19", "23", "4321", "17", "4", "16", "12"):
        assert value in policy, f"Missing configured or derived policy number: {value}"
    for term in ("Buy", "Overweight", "Underweight", "Sell", "Hold", "whole", "manual", "quote"):
        assert term.lower() in policy.lower()
    assert not broker.submitted


def test_policy_survives_real_langgraph_state_projection():
    from langgraph.graph import StateGraph, START, END
    from tradingagents.agents.state import AgentState

    seen = []
    graph = StateGraph(AgentState)
    graph.add_node("consume", lambda state: seen.append(state.get("desk_execution_policy")) or {})
    graph.add_edge(START, "consume")
    graph.add_edge("consume", END)
    graph.compile().invoke({"desk_execution_policy": "EXACT_POLICY_MARKER"})
    assert seen == ["EXACT_POLICY_MARKER"], "Undeclared state keys disappear before agent consumption"


NODES = [
    ("managers.research_manager", "create_research_manager"),
    ("managers.portfolio_manager", "create_portfolio_manager"),
    ("trader.trader", "create_trader"),
    ("risk_mgmt.aggressive_debator", "create_aggressive_debator"),
    ("risk_mgmt.conservative_debator", "create_conservative_debator"),
    ("risk_mgmt.neutral_debator", "create_neutral_debator"),
]


@pytest.mark.parametrize("module,factory", NODES)
def test_downstream_prompt_consumes_policy_without_invented_sizing(module, factory):
    from langchain_core.messages import AIMessage
    prompts = []

    class Model:
        def with_structured_output(self, *args, **kwargs):
            raise NotImplementedError

        def invoke(self, prompt):
            prompts.append(prompt if isinstance(prompt, str) else json.dumps(prompt))
            return AIMessage("Rating: Hold\nNo change.")

    state = {"company_of_interest": "AAPL", "trade_date": "2026-10-15",
             "asset_type": "stock", "instrument_context": "", "market_report": "Technical evidence",
             "sentiment_report": "S", "news_report": "N", "fundamentals_report": "F",
             "investment_plan": "Research", "trader_investment_plan": "Trader", "past_context": "",
             "portfolio_context": "Cash 100000", "desk_execution_policy": "EXACT_POLICY_MARKER",
             "investment_debate_state": {"history": "", "count": 0},
             "risk_debate_state": {"history": "", "latest_speaker": "", "count": 0,
                                   "aggressive_history": "", "conservative_history": "", "neutral_history": "",
                                   "current_aggressive_response": "", "current_conservative_response": "",
                                   "current_neutral_response": ""}}
    getattr(importlib.import_module("tradingagents.agents." + module), factory)(Model())(state)
    prompt = "\n".join(prompts)
    assert "EXACT_POLICY_MARKER" in prompt
    for obsolete in ("sized by how decisively it wins", "sized against a standard allocation",
                     "sized by how strong the case is", "**Position Sizing**: when you can state them"):
        assert obsolete not in prompt


@pytest.mark.parametrize("rating,expected", [("Buy", 100), ("Overweight", 75), ("Underweight", 10), ("Sell", 20)])
def test_proposal_quantity_remains_policy_derived_despite_advisory_prose(inputs, rating, expected):
    inputs["config"].update(allocation_pct=20, max_position_pct=15, max_order_notional=20000, price_buffer_bps=0)
    inputs["results"][0].update(rating=rating)
    inputs["results"][1].update(rating="Hold")
    if rating in ("Underweight", "Sell"):
        inputs["positions"] = [{"symbol": "AAPL", "qty": "20"}]
    baseline = engine.plan_orders(**inputs)[0]
    inputs["results"][0]["reports"] = {"final_trade_decision": "Invented 0.05x standard starter allocation"}
    actual = engine.plan_orders(**inputs)[0]
    assert actual == baseline
    assert actual["qty"] == expected
    assert actual["status"] == "proposed"
