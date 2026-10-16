"""Verify consumed schema selection, not just free-text fallback prompts."""
import importlib
import json
from types import SimpleNamespace

import pytest


@pytest.mark.parametrize("module,factory,base,desk,payload", [
    ("managers.research_manager", "create_research_manager", "ResearchPlan", "DeskResearchPlan",
     {"recommendation": "Hold", "rationale": "Evidence balanced", "strategic_actions": "Review policy"}),
    ("trader.trader", "create_trader", "TraderProposal", "DeskTraderProposal",
     {"action": "Hold", "reasoning": "Balanced"}),
    ("managers.portfolio_manager", "create_portfolio_manager", "PortfolioDecision", "DeskPortfolioDecision",
     {"rating": "Hold", "executive_summary": "Policy owns quantities", "investment_thesis": "Balanced"}),
])
@pytest.mark.parametrize("is_desk", [False, True])
def test_actual_structured_invocation_uses_caller_specific_schema(module, factory, base, desk, payload, is_desk):
    called = []
    class Model:
        def with_structured_output(self, schema):
            def invoke(prompt):
                called.append((schema, prompt))
                return schema(**payload)
            return SimpleNamespace(invoke=invoke)
        def invoke(self, prompt):
            pytest.fail("Structured path unexpectedly fell back")
    state = {"company_of_interest": "META", "market_report": "technical evidence",
             "investment_plan": "plan", "trader_investment_plan": "opinion",
             "portfolio_context": "cash and holdings", "past_context": "",
             "investment_debate_state": {"history": "", "count": 0},
             "risk_debate_state": {"history": "", "count": 0, "aggressive_history": "",
                 "conservative_history": "", "neutral_history": "", "current_aggressive_response": "",
                 "current_conservative_response": "", "current_neutral_response": ""}}
    if is_desk:
        state["desk_execution_policy"] = "POLICY_CONSUMED_MARKER"
    getattr(importlib.import_module("tradingagents.agents." + module), factory)(Model())(state)
    assert len(called) == 1
    schema, prompt = called[0]
    assert schema.__name__ == (desk if is_desk else base)
    if is_desk:
        assert "POLICY_CONSUMED_MARKER" in str(prompt)
        descriptor = json.dumps(schema.model_json_schema())
        assert "including sizing guidance relative to a standard allocation" not in descriptor
        assert "sized by how decisively it wins" not in descriptor
        assert "A concise action plan covering entry strategy, position sizing" not in descriptor
        if desk == "DeskTraderProposal":
            assert schema.model_json_schema()["properties"]["position_sizing"]["type"] == "null"
