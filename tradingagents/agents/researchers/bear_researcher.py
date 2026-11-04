from tradingagents.agents.prompt_evidence import EvidencePrompt
from tradingagents.agents.context import (
    get_instrument_context_from_state,
    get_language_instruction,
    get_verified_market_context_from_state,
    opponent_argument_or_opening,
    report_or_absent,
)


def create_bear_researcher(llm, *, workflow):
    def bear_node(state) -> dict:
        investment_debate_state = state["investment_debate_state"]
        history = investment_debate_state.get("history", "")
        bear_history = investment_debate_state.get("bear_history", "")

        current_response = opponent_argument_or_opening(
            investment_debate_state.get("current_response", ""), "bull analyst"
        , workflow)
        market_research_report = report_or_absent(state["market_report"], "market", workflow)
        sentiment_report = report_or_absent(state["sentiment_report"], "sentiment", workflow)
        news_report = report_or_absent(state["news_report"], "news", workflow)
        fundamentals_report = report_or_absent(state["fundamentals_report"], "fundamentals", workflow)
        instrument_context = get_instrument_context_from_state(state, workflow)
        asset_type = state.get("asset_type", "stock")
        target_label = "stock" if asset_type == "stock" else "asset"
        fundamentals_label = (
            "Company fundamentals report"
            if asset_type == "stock"
            else "Asset fundamentals report (may be unavailable for crypto)"
        )

        evidence = EvidencePrompt(workflow)
        prompt = workflow.render('bear_researcher', target_label=target_label, instrument_context=instrument_context, get_verified_market_context_from_state=get_verified_market_context_from_state(state, workflow), evidence_market_research_report=evidence.add('market research report', market_research_report), evidence_sentiment_report=evidence.add('sentiment report', sentiment_report), evidence_news_report=evidence.add('news report', news_report), fundamentals_label=fundamentals_label, evidence_fundamentals_report=evidence.add('fundamentals report', fundamentals_report), evidence_debate_history=evidence.add('debate history', history), evidence_opposing_analyst_latest_argument=evidence.add('opposing analyst latest argument', current_response), target_label_2=target_label) + get_language_instruction(workflow)

        response = llm.invoke(evidence.messages(prompt))

        argument = f"Bear Analyst: {response.content}"

        new_investment_debate_state = {
            "history": history + "\n" + argument,
            "bear_history": bear_history + "\n" + argument,
            "bull_history": investment_debate_state.get("bull_history", ""),
            "current_response": argument,
            "count": investment_debate_state["count"] + 1,
        }

        return {"investment_debate_state": new_investment_debate_state}

    return bear_node
