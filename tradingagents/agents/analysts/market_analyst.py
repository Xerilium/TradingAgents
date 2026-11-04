from datetime import date, timedelta

from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from tradingagents.agents.analysts.turn import request_inputs, research_memory_guidance, take_turn
from tradingagents.agents.context import get_instrument_context_from_state, get_language_instruction
from tradingagents.agents.tools import get_indicators, get_stock_data, get_verified_market_snapshot
from tradingagents.dataflows.vendors.yahoo.snapshot import DEFAULT_SNAPSHOT_INDICATORS

# The tools this analyst is offered; its tool node is built from the same tuple.
TOOLS = (
    get_stock_data,
    get_indicators,
    get_verified_market_snapshot,
)


def create_market_analyst(llm, tools=None, *, workflow):
    tools = TOOLS if tools is None else tuple(tools)
    if get_verified_market_snapshot not in tools:
        raise ValueError("Market analyst requires the verified market snapshot tool")

    def market_analyst_node(state):
        current_date = state["trade_date"]
        required = request_inputs(state, "market_report", [
            (get_stock_data.name, {"start_date": (date.fromisoformat(current_date) - timedelta(days=365)).isoformat(), "end_date": current_date}),
            (get_indicators.name, {"indicator": ",".join(DEFAULT_SNAPSHOT_INDICATORS), "curr_date": current_date}),
        ], workflow=workflow)
        if required:
            return required
        snapshot = next(
            (message for message in state["messages"] if isinstance(message, HumanMessage)
             and message.id == "required-market-snapshot"), None
        )
        snapshot_messages = []
        if snapshot is None:
            snapshot = HumanMessage(
                content=get_verified_market_snapshot.func(
                    state["company_of_interest"], current_date, trade_date=current_date
                ),
                id="required-market-snapshot",
            )
            snapshot_messages.append(snapshot)
        if not isinstance(snapshot.content, str) or not snapshot.content.startswith(
            f"## Verified market data snapshot for {state['company_of_interest'].upper()}\n"
        ) or f"- Requested analysis date: {current_date}" not in snapshot.content.splitlines():
            raise RuntimeError("Market analyst cannot complete: verified market data snapshot unavailable")
        instrument_context = get_instrument_context_from_state(state, workflow)

        system_message = (
            workflow.render('market_analyst', research_memory_guidance=research_memory_guidance(tools, workflow), get_language_instruction=get_language_instruction(workflow))
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

        result, report = take_turn(prompt, llm, tools, [*state["messages"], *snapshot_messages], workflow=workflow)

        return {
            "messages": [*snapshot_messages, result],
            "market_report": report,
            "verified_market_snapshot": snapshot.content,
        }

    return market_analyst_node
