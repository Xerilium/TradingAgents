"""One turn of a tool-using analyst, and its last turn once its tool rounds are spent."""

import json

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

WRAP_UP = (
    "You have used every tool round this report allows. Write your final report "
    "now from the tool results above, and say which data you could not retrieve."
)


def request_inputs(state, report_key, calls):
    message_id = f"required-{report_key}-inputs"
    requested = next((message for message in state["messages"] if getattr(message, "id", None) == message_id), None)
    if requested is not None:
        replies = {message.tool_call_id: message for message in state["messages"] if isinstance(message, ToolMessage)}
        missing = [call["name"] for call in requested.tool_calls if call["id"] not in replies
                   or getattr(replies[call["id"]], "status", None) == "error"
                   or str(replies[call["id"]].content).lstrip().startswith(("DATA_UNAVAILABLE", "NO_DATA_AVAILABLE", "DATA_PARTIAL:", "Error:"))]
        if missing:
            raise ValueError(f"Research inputs incomplete for {report_key}: {', '.join(sorted(set(missing)))}")
        return None
    return {"messages": [AIMessage(content="", id=message_id, tool_calls=[
        {"name": name, "args": args, "id": f"{message_id}-{index}"}
        for index, (name, args) in enumerate(calls)
    ])], report_key: ""}


def take_turn(prompt, llm, tools, messages):
    """The analyst's reply and its report, which stays empty while it calls tools.

    Told to wrap up, it answers without tools: a model offered tools may call one
    whatever it is told. Its earlier calls and their results reach it as text,
    since a provider may refuse a history holding tool calls when none are bound.
    """
    # Multiple statement tools may return the same complete filing. Keep it once
    # in the model input; every original response remains in saved source evidence.
    seen, unique = {}, []
    for message in messages:
        if (isinstance(message, ToolMessage) and isinstance(message.content, str)
                and message.name in {"get_balance_sheet", "get_cashflow", "get_income_statement"}
                and "All statements, notes and management discussion follow;" in message.content):
            if message.content in seen:
                message = message.model_copy(update={"content": f"Identical source content to tool response {seen[message.content]}; read that full response above."})
            else:
                seen[message.content] = message.tool_call_id
        unique.append(message)
    messages = unique
    if messages and isinstance(messages[-1], HumanMessage) and messages[-1].content == WRAP_UP:
        # The prompt lists the tools it offers; a model told of tools it cannot
        # call may still try, and some providers then answer with nothing.
        prompt = prompt.partial(tool_names="none; your tool rounds are spent")
        result = (prompt | llm).invoke(_as_text(messages))
        return result, result.content
    result = (prompt | llm.bind_tools(tools)).invoke(messages)
    return result, "" if result.tool_calls else result.content


def _as_text(messages):
    """The history with its tool calls and tool results written out as plain messages."""
    written = []
    for message in messages:
        if isinstance(message, AIMessage) and message.tool_calls:
            said = message.content if isinstance(message.content, str) else ""
            calls = "; ".join(f"{c['name']}({json.dumps(c['args'], default=str)})" for c in message.tool_calls)
            written.append(AIMessage(content=f"{said}\n[Called {calls}]".strip()))
        elif isinstance(message, ToolMessage):
            written.append(HumanMessage(content=f"[{message.name or 'Tool'} returned]\n{message.content}"))
        else:
            written.append(message)
    return written
