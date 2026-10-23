"""One turn of a tool-using analyst, and its last turn once its tool rounds are spent."""

import json

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

WRAP_UP = (
    "You have used every tool round this report allows. Write your final report "
    "now from the tool results above, and say which data you could not retrieve."
)


def research_memory_guidance(tools):
    names = {tool.name for tool in tools}
    guidance = [
        " Use prior company, project or domain knowledge only when relevant to this research."
        " During tool-enabled research, make a small, proportionate retrieval pass; stop if results are irrelevant."
        " Follow the available tools' schemas. Once tool rounds are exhausted, or during tool-free review,"
        " do not call tools; use only retained results and disclose unperformed checks.",
    ]
    for name, instruction in (
        ("maenifold_graph__BuildContext", "Use only a relevant existing concept returned by retrieval, with depth=1, maxEntities=5, includeContent=true. On CONCEPT_NOT_FOUND, resolve the anchor once with FindSimilarConcepts if available; never retry the missing anchor or mutate the corpus to make retrieval succeed."),
        ("maenifold_graph__FindSimilarConcepts", "Before BuildContext, discover an existing anchor using conceptName and maxResults=5. Use only a directly relevant returned concept; if none exists or resolution fails, disclose no relevant memory and continue primary-source research. Never invent an anchor or force an unrelated match; similarity is not evidence."),
        ("maenifold_memory__SearchMemories", "Search relevant company or domain notes, especially when graph context is unavailable; avoid indiscriminate retrieval."),
        ("maenifold_memory__ReadMemory", "Read the strongest directly relevant source notes returned by retrieval before relying on them."),
        ("maenifold_thinking__SequentialThinking", "Use concise persistent reasoning for nontrivial research steps: record material assumptions, source-linked evidence, decisions and unresolved gaps; complete each reasoning session using its returned session ID and nextThoughtNeeded=false."),
    ):
        if name in names:
            guidance.append(f" Use {name}: {instruction}")
    if "maenifold_graph__BuildContext" not in names:
        guidance.append(" Graph context retrieval is unavailable in this tool set; use available memory retrieval proportionately.")
    if not names.intersection({"maenifold_memory__SearchMemories", "maenifold_memory__ReadMemory", "maenifold_graph__BuildContext"}):
        guidance.append(" Prior-memory retrieval is unavailable in this tool set; continue primary-source research under the existing coverage requirements.")
    guidance.append(
        " In the report, state which relevant prior notes influenced the analysis and cite their memory:// sources,"
        " or state that none were found, retrieval was unavailable, or no retrieval was performed, as actually observed."
        " Separate dated memory and its original sources from current primary evidence; check availability as of the analysis date"
        " and never treat old prices as current. Report tool failures and unresolved gaps without inventing calls or citations."
        " Do not promote unsourced conclusions to verified durable knowledge. Existing required-data and report-format rules still apply."
    )
    return "".join(guidance)


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
