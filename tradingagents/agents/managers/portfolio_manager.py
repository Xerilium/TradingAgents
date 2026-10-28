"""Portfolio Manager: synthesises the risk-analyst debate into the final decision.

Uses LangChain's ``with_structured_output`` so the LLM produces a typed
``PortfolioDecision`` directly, in a single call. Its rating is the run's
``final_rating``, and the decision is rendered to markdown as
``final_trade_decision`` for the memory log, CLI display and saved reports.
When a provider does not expose structured output, the agent falls back to
free-text generation and the rating is read from that text.
"""

from __future__ import annotations

from tradingagents.agents.prompt_evidence import EvidencePrompt
from tradingagents.agents.context import (
    get_desk_execution_policy,
    get_instrument_context_from_state,
    get_language_instruction,
    get_portfolio_context_from_state,
    get_verified_market_context_from_state,
)
from tradingagents.agents.rating import parse_rating
from tradingagents.agents.schemas import (
    DeskPortfolioDecision,
    PortfolioDecision,
    render_pm_decision,
)
from tradingagents.agents.structured import bind_structured, invoke_structured
from tradingagents.dataflows.router import observe_source_call


def create_portfolio_manager(llm, *, workflow):
    structured_llm = bind_structured(llm, PortfolioDecision, 'Portfolio Manager', workflow=workflow)

    def portfolio_manager_node(state) -> dict:
        instrument_context = get_instrument_context_from_state(state, workflow)
        portfolio_context = get_portfolio_context_from_state(state, workflow)
        policy = get_desk_execution_policy(state)

        history = state["risk_debate_state"]["history"]
        risk_debate_state = state["risk_debate_state"]
        research_plan = state["investment_plan"]
        trader_plan = state["trader_investment_plan"]

        past_context = state.get("past_context", "")
        observe_source_call(
            "memory_context", "local", "pm_memory_input",
            lambda: {
                "past_context": {"present": "past_context" in state, "value": past_context,
                                 "included_in_prompt": bool(past_context)},
                "memory_note": {"present": "memory_note" in state, "value": state.get("memory_note"),
                                "included_in_prompt": False},
                "scope": "Portfolio Manager state-read boundary; not proof of provider execution.",
            },
            symbol=state.get("company_of_interest"), trade_date=state.get("trade_date"),
        )
        evidence = EvidencePrompt(workflow)
        lessons_line = (
            workflow.render('portfolio_lessons', evidence=evidence.add('prior decisions and outcomes', past_context))
            if past_context
            else ""
        )

        prompt = workflow.render('portfolio_manager_desk' if policy else 'portfolio_manager', instrument_context=instrument_context, get_verified_market_context_from_state=get_verified_market_context_from_state(state, workflow), portfolio_context=portfolio_context, evidence_research_manager_investment_plan=evidence.add('research manager investment plan', research_plan), evidence_trader_transaction_proposal=evidence.add('trader transaction proposal', trader_plan), lessons_line=lessons_line, evidence_debate_history=evidence.add('debate history', history), NO_EXTERNAL_TOOLS=workflow.text('no_external_tools'), get_language_instruction=get_language_instruction(workflow))

        # The typed rating is the decision; the rendered text only carries it.
        # Read back from text, a rating the thesis quotes could replace it.
        decision = invoke_structured(bind_structured(llm, DeskPortfolioDecision, 'Portfolio Manager', workflow=workflow) if policy else structured_llm,
                                     evidence.messages(prompt), "Portfolio Manager")
        if decision is not None:
            final_trade_decision = render_pm_decision(decision)
            final_rating = decision.rating.value
        else:
            final_trade_decision = llm.invoke(evidence.messages(prompt)).content
            final_rating = parse_rating(final_trade_decision)

        new_risk_debate_state = {
            "history": risk_debate_state["history"],
            "aggressive_history": risk_debate_state["aggressive_history"],
            "conservative_history": risk_debate_state["conservative_history"],
            "neutral_history": risk_debate_state["neutral_history"],
            "latest_speaker": "Judge",
            "current_aggressive_response": risk_debate_state["current_aggressive_response"],
            "current_conservative_response": risk_debate_state["current_conservative_response"],
            "current_neutral_response": risk_debate_state["current_neutral_response"],
            "count": risk_debate_state["count"],
        }

        return {
            "risk_debate_state": new_risk_debate_state,
            "final_trade_decision": final_trade_decision,
            "final_rating": final_rating,
        }

    return portfolio_manager_node
