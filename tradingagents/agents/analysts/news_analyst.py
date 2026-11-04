from datetime import date, timedelta

from langchain_core.messages import ToolMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from tradingagents.agents.analysts.turn import request_inputs, research_memory_guidance, take_turn
from tradingagents.agents.context import get_instrument_context_from_state, get_language_instruction
from tradingagents.agents.tools import (
    get_global_news,
    get_macro_indicators,
    get_news,
    get_prediction_markets,
    read_research_source,
    search_research_sources,
)

# The tools this analyst is offered; its tool node is built from the same tuple.
TOOLS = (
    get_news,
    get_global_news,
    get_macro_indicators,
    get_prediction_markets,
    read_research_source,
    search_research_sources,
)


def create_news_analyst(llm, tools=None, *, relevance_screen=None, workflow):
    tools = TOOLS if tools is None else tuple(tools)
    screened_news = {}

    def news_analyst_node(state):
        current_date = state["trade_date"]
        required = request_inputs(state, "news_report", [
            (get_news.name, {"start_date": (date.fromisoformat(current_date) - timedelta(days=7)).isoformat(), "end_date": current_date}),
            (get_global_news.name, {"curr_date": current_date}),
            (get_prediction_markets.name, {"topic": state["company_of_interest"]}),
            *[(get_macro_indicators.name, {"indicator": indicator, "curr_date": current_date})
              for indicator in ("cpi", "core_pce", "unemployment", "fed_funds_rate", "10y_treasury", "yield_curve", "real_gdp", "vix")
              if any(tool.name == get_macro_indicators.name for tool in tools)],
        ], required=(), workflow=workflow)
        if required:
            return required
        asset_type = state.get("asset_type", "stock")
        asset_label = "company" if asset_type == "stock" else "asset"
        instrument_context = get_instrument_context_from_state(state, workflow)
        if relevance_screen:
            # Replace only the prompt copy of each get_news reply; the saved
            # ToolMessage evidence stays complete.
            news_calls = {call["id"] for message in state["messages"]
                          for call in getattr(message, "tool_calls", ()) if call["name"] == get_news.name}
            screen = relevance_screen(state["company_of_interest"], instrument_context=instrument_context)
            messages = []
            for message in state["messages"]:
                if (isinstance(message, ToolMessage) and message.tool_call_id in news_calls
                        and isinstance(message.content, str)):
                    key = (state["company_of_interest"], current_date, message.tool_call_id)
                    if key not in screened_news:
                        screened_news[key] = screen(message.content)
                    message = message.model_copy(update={"content": screened_news[key]})
                messages.append(message)
            state = {**state, "messages": messages}

        system_message = (
            workflow.render('news_analyst', asset_label=asset_label, research_memory_guidance=research_memory_guidance(tools, workflow), get_language_instruction=get_language_instruction(workflow))
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    workflow.template('analyst_wrapper'),
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(tool_names=", ".join([tool.name for tool in tools]))
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(instrument_context=instrument_context)

        result, report = take_turn(prompt, llm, tools, state["messages"], workflow=workflow)

        return {
            "messages": [result],
            "news_report": report,
        }

    return news_analyst_node
