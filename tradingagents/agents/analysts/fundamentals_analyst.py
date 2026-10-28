from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from tradingagents.agents.analysts.turn import _as_text, request_inputs, research_memory_guidance, take_turn
from tradingagents.agents.context import get_instrument_context_from_state, get_language_instruction
from tradingagents.agents.tools import (
    get_balance_sheet,
    get_cashflow,
    get_fundamentals,
    get_fund_data,
    get_income_statement,
    get_insider_transactions,
    read_research_source,
)

# The tools this analyst is offered; its tool node is built from the same tuple.
TOOLS = (
    get_fund_data,
    get_fundamentals,
    get_balance_sheet,
    get_cashflow,
    get_income_statement,
    get_insider_transactions,
    read_research_source,
)


def create_fundamentals_analyst(llm, tools=None, *, workflow):
    tools = TOOLS if tools is None else tuple(tools)
    def fundamentals_analyst_node(state):
        current_date = state["trade_date"]
        is_fund = state.get("asset_type") == "etf"
        company_tools = {get_fundamentals.name, get_balance_sheet.name, get_cashflow.name,
                         get_income_statement.name, get_insider_transactions.name}
        excluded = company_tools if is_fund else {get_fund_data.name}
        active_tools = tuple(tool for tool in tools if tool.name not in excluded)
        calls = [(get_fund_data.name, {"curr_date": current_date})] if is_fund else [
            *((tool.name, {} if tool is get_insider_transactions else {"curr_date": current_date})
            for tool in TOOLS if tool not in (read_research_source, get_fund_data)
            ),
            (get_income_statement.name, {"freq": "annual", "curr_date": current_date}),
        ]
        required = request_inputs(state, "fundamentals_report", calls, workflow=workflow)
        if required:
            return required
        instrument_context = get_instrument_context_from_state(state, workflow)

        system_message = (
            workflow.render('fundamentals_analyst', research_memory_guidance=research_memory_guidance(tools, workflow), get_language_instruction=get_language_instruction(workflow))
        )
        if is_fund:
            system_message = (
                workflow.render('fundamentals_analyst_etf', research_memory_guidance=research_memory_guidance(active_tools, workflow), get_language_instruction=get_language_instruction(workflow))
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
        prompt = prompt.partial(tool_names=", ".join([tool.name for tool in active_tools]))
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(instrument_context=instrument_context)

        result, report = take_turn(prompt, llm, active_tools, state["messages"], workflow=workflow)
        if report:
            review = HumanMessage(
                workflow.render('fundamentals_review_etf')
                if is_fund else
                workflow.render('fundamentals_review_stock'))
            result = (prompt.partial(tool_names=workflow.text('fundamentals_review_tools')) | llm).invoke(_as_text([*state["messages"], result, review], workflow))
            report = result.content

        return {
            "messages": [result],
            "fundamentals_report": report,
        }

    return fundamentals_analyst_node
