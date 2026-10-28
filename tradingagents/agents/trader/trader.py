"""Trader: turns the Research Manager's investment plan into a concrete transaction proposal."""

from __future__ import annotations

from langchain_core.messages import AIMessage

from tradingagents.agents.prompt_evidence import EvidencePrompt
from tradingagents.agents.context import (
    get_desk_execution_policy,
    get_instrument_context_from_state,
    get_language_instruction,
    get_portfolio_context_from_state,
    get_verified_market_context_from_state,
)
from tradingagents.agents.schemas import DeskTraderProposal, TraderProposal, render_trader_proposal
from tradingagents.agents.structured import (
    bind_structured,
    invoke_structured_or_freetext,
)


def create_trader(llm, *, workflow):
    structured_llm = bind_structured(llm, TraderProposal, 'Trader', workflow=workflow)

    def trader_node(state):
        company_name = state["company_of_interest"]
        instrument_context = get_instrument_context_from_state(state, workflow)
        investment_plan = state["investment_plan"]
        # The research plan digests the debate but loses exact price structure;
        # give the Trader the technical market report so entry/stop levels are
        # grounded in real ATR / support-resistance / current price (#1167). The
        # report is empty when the user did not select the market analyst, so
        # only offer it (and the grounding instruction) when it has content.
        market_report = (state["market_report"] or "").strip()
        portfolio_context = get_portfolio_context_from_state(state, workflow)
        policy = get_desk_execution_policy(state)

        evidence = EvidencePrompt(workflow)
        if market_report:
            grounding = (
                workflow.render('trader_grounding_desk' if policy else 'trader_grounding')
            )
            report_section = workflow.render('trader_report_section', evidence=evidence.add('technical market report', market_report))
        else:
            grounding = ""
            report_section = ""

        messages = [
            {
                "role": "system",
                "content": (
                    workflow.render('trader_system_desk' if policy else 'trader_system', grounding=grounding, NO_EXTERNAL_TOOLS=workflow.text('no_external_tools'), get_language_instruction=get_language_instruction(workflow))
                ),
            },
            {
                "role": "user",
                "content": (
                    workflow.render('trader_user_desk' if policy else 'trader_user', company_name=company_name, instrument_context=instrument_context, get_verified_market_context_from_state=get_verified_market_context_from_state(state, workflow), report_section=report_section, portfolio_context=portfolio_context, evidence_research_investment_plan=evidence.add('research investment plan', investment_plan))
                ),
            },
        ]

        trader_plan = invoke_structured_or_freetext(
            bind_structured(llm, DeskTraderProposal, 'Trader', workflow=workflow) if policy else structured_llm,
            llm,
            [*messages, *evidence.messages("")[1:]],
            render_trader_proposal,
            "Trader",
        )

        return {
            "messages": [AIMessage(content=trader_plan)],
            "trader_investment_plan": trader_plan,
        }

    return trader_node
