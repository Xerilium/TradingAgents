from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from tradingagents.agents.analysts.turn import _as_text, request_inputs, research_memory_guidance, take_turn
from tradingagents.agents.context import get_instrument_context_from_state, get_language_instruction
from tradingagents.agents.tools import (
    get_balance_sheet,
    get_cashflow,
    get_fundamentals,
    get_income_statement,
    get_insider_transactions,
    read_research_source,
)

# The tools this analyst is offered; its tool node is built from the same tuple.
TOOLS = (
    get_fundamentals,
    get_balance_sheet,
    get_cashflow,
    get_income_statement,
    get_insider_transactions,
    read_research_source,
)


def create_fundamentals_analyst(llm, tools=None):
    tools = TOOLS if tools is None else tuple(tools)
    def fundamentals_analyst_node(state):
        current_date = state["trade_date"]
        required = request_inputs(state, "fundamentals_report", [
            *((tool.name, {} if tool is get_insider_transactions else {"curr_date": current_date})
            for tool in TOOLS if tool is not read_research_source
            ),
            (get_income_statement.name, {"freq": "annual", "curr_date": current_date}),
        ])
        if required:
            return required
        instrument_context = get_instrument_context_from_state(state)

        system_message = (
            "You are a researcher tasked with analyzing fundamental information over the past week about a company. Please write a comprehensive report of the company's fundamental information such as financial documents, company profile, basic company financials, and company financial history to gain a full view of the company's fundamental information to inform traders. Make sure to include as much detail as possible. Provide specific, actionable insights with supporting evidence to help traders make informed decisions."
            + " Make sure to append a Markdown table at the end of the report to organize key points in the report, organized and easy to read."
            + " Use the available tools: `get_fundamentals` for comprehensive company analysis, `get_balance_sheet`, `get_cashflow`, and `get_income_statement` for specific financial statements, and `get_insider_transactions` for recent insider buying and selling."
            + " Read filing notes and cash-flow reconciliations before calling an earnings or funding gap unexplained. Use read_research_source to resolve material missing context from primary sources. Distinguish parent equity from consolidated equity and GAAP from adjusted measures; compare matching fiscal periods."
            + " State total liabilities and reconcile total assets to liabilities plus consolidated equity. Explain material cash-flow and financing bridges, including partner distributions; distinguish company-adjusted free cash flow from simple operating cash flow less capital spending."
            + " SEC statement tools supply the full quarterly and annual filings, including all statements and notes. Do not spend a source-reading call reopening the same filing. Follow material references to issuer releases or other primary documents when reconciliation is still missing."
            + research_memory_guidance(tools)
            + get_language_instruction()
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful AI assistant, collaborating with other assistants."
                    " Use the provided tools to progress towards answering the question."
                    " If you are unable to fully answer, that's OK; another assistant with different tools"
                    " will help where you left off. Execute what you can to make progress."
                    " Report what your tools support; another agent decides the trade."
                    " You have access to the following tools: {tool_names}."
                    " Today's date is {current_date}; treat it as 'now' for all analysis and tool-call date ranges. {instrument_context}\n"
                    "{system_message}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(tool_names=", ".join([tool.name for tool in tools]))
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(instrument_context=instrument_context)

        result, report = take_turn(prompt, llm, tools, state["messages"])
        if report:
            review = HumanMessage("Verify and correct this report against the supplied complete filings before publication. Check every material number, fiscal period, unit and attribution, especially quarter versus year-to-date non-operating charges. Extract annual comparisons from the supplied annual statements; do not claim complete filings are missing excerpts. Reconcile the income and balance-sheet figures. Return only the corrected complete report; do not add unsupported claims.")
            result = (prompt.partial(tool_names="none; review the supplied source evidence") | llm).invoke(_as_text([*state["messages"], result, review]))
            report = result.content

        return {
            "messages": [result],
            "fundamentals_report": report,
        }

    return fundamentals_analyst_node
