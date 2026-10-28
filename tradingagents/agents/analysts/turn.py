"""One turn of a tool-using analyst, and its last turn once its tool rounds are spent."""

import json
import hashlib
import re

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage




def research_memory_guidance(tools, workflow):
    names = {tool.name for tool in tools}
    guidance = [
        workflow.text('shared_memory_base'),
        workflow.text('shared_memory_tools'),
    ]
    for name, instruction in (
        ("maenifold_graph__BuildContext", workflow.text('shared_memory_build_context')),
        ("maenifold_graph__FindSimilarConcepts", workflow.text('shared_memory_find_similar')),
        ("maenifold_memory__SearchMemories", workflow.text('shared_memory_search')),
        ("maenifold_memory__ReadMemory", workflow.text('shared_memory_read')),
        ("maenifold_thinking__SequentialThinking", workflow.text('shared_memory_thinking')),
    ):
        if name in names:
            guidance.append(workflow.render('shared_memory_tool_instruction', name=name, instruction=instruction))
    if "maenifold_graph__BuildContext" not in names:
        guidance.append(workflow.text('shared_memory_no_graph'))
    if not names.intersection({"maenifold_memory__SearchMemories", "maenifold_memory__ReadMemory", "maenifold_graph__BuildContext"}):
        guidance.append(workflow.text('shared_memory_unavailable'))
    guidance.append(
        workflow.text('shared_memory_final')
    )
    return "".join(guidance)


def request_inputs(state, report_key, calls, *, required=None, workflow):
    required = {name for name, _ in calls} if required is None else set(required)
    message_id = f"required-{report_key}-inputs"
    requested = next((message for message in state["messages"] if getattr(message, "id", None) == message_id), None)
    if requested is not None:
        replies = {message.tool_call_id: message for message in state["messages"] if isinstance(message, ToolMessage)}
        missing = [call["name"] for call in requested.tool_calls if call["id"] not in replies
                   or call["name"] in required and (
                       getattr(replies[call["id"]], "status", None) == "error"
                       or str(replies[call["id"]].content).lstrip().startswith(("DATA_UNAVAILABLE", "NO_DATA_AVAILABLE", "DATA_PARTIAL:", "Error:")))]
        if missing:
            raise ValueError(f"Research inputs incomplete for {report_key}: {', '.join(sorted(set(missing)))}")
        return None
    return {"messages": [AIMessage(content=workflow.text('shared_request_inputs'), id=message_id, tool_calls=[
        {"name": name, "args": args, "id": f"{message_id}-{index}"}
        for index, (name, args) in enumerate(calls)
    ])], report_key: ""}


def project_history(messages, workflow):
    """Keep each identical filing once without changing saved tool evidence."""
    seen, projected = {}, []
    for message in messages:
        if isinstance(message, ToolMessage) and isinstance(message.content, str):
            starts = list(re.finditer(r"(?m)^# [^\n]+ complete [^\n]+ filing: period [^\n]+\nSource: [^\n]+\n", message.content))
            if starts:
                parts = [message.content[:starts[0].start()]]
                for index, start in enumerate(starts):
                    end = starts[index + 1].start() if index + 1 < len(starts) else len(message.content)
                    filing = message.content[start.start():end]
                    digest = hashlib.sha256(filing.encode("utf-8")).hexdigest()
                    if digest in seen:
                        parts.append(start.group() + workflow.render('shared_duplicate_filing', response_id=seen[digest], digest=digest))
                    else:
                        seen[digest] = message.tool_call_id
                        parts.append(filing)
                message = message.model_copy(update={"content": "".join(parts)})
        projected.append(message)
    return projected


def take_turn(prompt, llm, tools, messages, *, workflow):
    """The analyst's reply and its report, which stays empty while it calls tools.

    Told to wrap up, it answers without tools: a model offered tools may call one
    whatever it is told. Its earlier calls and their results reach it as text,
    since a provider may refuse a history holding tool calls when none are bound.
    """
    messages = project_history(messages, workflow)
    if messages and isinstance(messages[-1], HumanMessage) and messages[-1].content == workflow.text('wrap_up'):
        # The prompt lists the tools it offers; a model told of tools it cannot
        # call may still try, and some providers then answer with nothing.
        prompt = prompt.partial(tool_names=workflow.text('shared_tools_spent'))
        result = (prompt | llm).invoke(_as_text(messages, workflow))
        return result, result.content
    result = (prompt | llm.bind_tools(tools)).invoke(messages)
    return result, "" if result.tool_calls else result.content


def _as_text(messages, workflow):
    """The history with its tool calls and tool results written out as plain messages."""
    written = []
    for message in project_history(messages, workflow):
        if isinstance(message, AIMessage) and message.tool_calls:
            said = message.content if isinstance(message.content, str) else ""
            calls = "; ".join(f"{c['name']}({json.dumps(c['args'], default=str)})" for c in message.tool_calls)
            written.append(AIMessage(content=workflow.render('shared_called_tools', said=said, calls=calls).strip()))
        elif isinstance(message, ToolMessage):
            written.append(HumanMessage(content=workflow.render('shared_tool_returned', name=message.name or 'Tool', response_id=message.tool_call_id)))
            written.append(HumanMessage(content=message.content,
                additional_kwargs={"research_evidence": True, "research_evidence_source": message.tool_call_id,
                                   "source_label": message.name or "Tool"}))
        else:
            written.append(message)
    return written
