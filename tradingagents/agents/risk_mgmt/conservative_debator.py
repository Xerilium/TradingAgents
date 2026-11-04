from tradingagents.agents.prompt_evidence import EvidencePrompt
from tradingagents.agents.context import (
    get_instrument_context_from_state,
    get_language_instruction,
    get_portfolio_context_from_state,
    get_verified_market_context_from_state,
    opponent_argument_or_opening,
    report_or_absent,
)


def create_conservative_debator(llm, *, workflow):
    def conservative_node(state) -> dict:
        risk_debate_state = state["risk_debate_state"]
        history = risk_debate_state.get("history", "")
        conservative_history = risk_debate_state.get("conservative_history", "")

        current_aggressive_response = opponent_argument_or_opening(
            risk_debate_state.get("current_aggressive_response", ""), "aggressive analyst"
        , workflow)
        current_neutral_response = opponent_argument_or_opening(
            risk_debate_state.get("current_neutral_response", ""), "neutral analyst"
        , workflow)

        market_research_report = report_or_absent(state["market_report"], "market", workflow)
        sentiment_report = report_or_absent(state["sentiment_report"], "sentiment", workflow)
        news_report = report_or_absent(state["news_report"], "news", workflow)
        fundamentals_report = report_or_absent(state["fundamentals_report"], "fundamentals", workflow)
        instrument_context = get_instrument_context_from_state(state, workflow)
        portfolio_context = get_portfolio_context_from_state(state, workflow)

        trader_decision = state["trader_investment_plan"]

        evidence = EvidencePrompt(workflow)
        prompt = workflow.render('conservative_debator', evidence_trader_investment_plan=evidence.add('trader investment plan', trader_decision), instrument_context=instrument_context, portfolio_context=portfolio_context, get_verified_market_context_from_state=get_verified_market_context_from_state(state, workflow), evidence_market_research_report=evidence.add('market research report', market_research_report), evidence_sentiment_report=evidence.add('sentiment report', sentiment_report), evidence_news_report=evidence.add('news report', news_report), evidence_fundamentals_report=evidence.add('fundamentals report', fundamentals_report), evidence_debate_history=evidence.add('debate history', history), evidence_aggressive_analyst_latest_argument=evidence.add('aggressive analyst latest argument', current_aggressive_response), evidence_neutral_analyst_latest_argument=evidence.add('neutral analyst latest argument', current_neutral_response)) + get_language_instruction(workflow)

        response = llm.invoke(evidence.messages(prompt))

        argument = f"Conservative Analyst: {response.content}"

        new_risk_debate_state = {
            "history": history + "\n" + argument,
            "aggressive_history": risk_debate_state.get("aggressive_history", ""),
            "conservative_history": conservative_history + "\n" + argument,
            "neutral_history": risk_debate_state.get("neutral_history", ""),
            "latest_speaker": "Conservative",
            "current_aggressive_response": risk_debate_state.get(
                "current_aggressive_response", ""
            ),
            "current_conservative_response": argument,
            "current_neutral_response": risk_debate_state.get(
                "current_neutral_response", ""
            ),
            "count": risk_debate_state["count"] + 1,
        }

        return {"risk_debate_state": new_risk_debate_state}

    return conservative_node
