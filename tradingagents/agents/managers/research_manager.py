"""Research Manager: turns the bull/bear debate into a structured investment plan for the trader."""

from __future__ import annotations

from tradingagents.agents.prompt_evidence import EvidencePrompt
from tradingagents.agents.context import (
    get_desk_execution_policy,
    get_instrument_context_from_state,
    get_language_instruction,
    get_portfolio_context_from_state,
    get_verified_market_context_from_state,
)
from tradingagents.agents.schemas import DeskResearchPlan, ResearchPlan, render_research_plan
from tradingagents.agents.structured import (
    bind_structured,
    invoke_structured_or_freetext,
)


def create_research_manager(llm, *, workflow):
    structured_llm = bind_structured(llm, ResearchPlan, 'Research Manager', workflow=workflow)

    def research_manager_node(state) -> dict:
        instrument_context = get_instrument_context_from_state(state, workflow)
        policy = get_desk_execution_policy(state)
        history = state["investment_debate_state"].get("history", "")

        investment_debate_state = state["investment_debate_state"]

        evidence = EvidencePrompt(workflow)
        prompt = workflow.render('research_manager_desk' if policy else 'research_manager', instrument_context=instrument_context, get_verified_market_context_from_state=get_verified_market_context_from_state(state, workflow), get_portfolio_context_from_state=get_portfolio_context_from_state(state, workflow), policy=policy, evidence_debate_history=evidence.add('debate history', history), NO_EXTERNAL_TOOLS=workflow.text('no_external_tools')) + get_language_instruction(workflow)

        investment_plan = invoke_structured_or_freetext(
            bind_structured(llm, DeskResearchPlan, 'Research Manager', workflow=workflow) if policy else structured_llm,
            llm,
            evidence.messages(prompt),
            render_research_plan,
            "Research Manager",
        )

        new_investment_debate_state = {
            "history": investment_debate_state.get("history", ""),
            "bear_history": investment_debate_state.get("bear_history", ""),
            "bull_history": investment_debate_state.get("bull_history", ""),
            "current_response": investment_plan,
            "count": investment_debate_state["count"],
        }

        return {
            "investment_debate_state": new_investment_debate_state,
            "investment_plan": investment_plan,
        }

    return research_manager_node
