"""Measured context planning for local research models.

Notes are derived summaries, not source quotations. Original messages remain intact.
"""

import hashlib
import json
import re
import math

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage


def budget_limits(total, payload):
    extra = payload.get("extra_body") or {}
    requested = [value for value in (payload.get("max_tokens"), payload.get("max_completion_tokens"),
                                      extra.get("max_tokens"), extra.get("max_completion_tokens"))
                 if value is not None]
    output = min(requested) if requested else total // 4
    buffer = math.ceil(total / 100)
    available = total - output - buffer
    if output <= 0 or available <= 0:
        raise ValueError(f"Context budget cannot fit the output reserve: total={total}, output={output}, buffer={buffer}.")
    return output, buffer, available


def set_output_limit(payload, output):
    payload.pop("max_tokens", None)
    extra = payload.get("extra_body")
    if extra:
        extra = dict(extra)
        extra.pop("max_tokens", None)
        extra.pop("max_completion_tokens", None)
        payload["extra_body"] = extra
    payload["max_completion_tokens"] = output


async def _chunks(text, limit, count):
    """Split at measured character offsets; every original character is covered."""
    start = 0
    while start < len(text):
        low, high = start + 1, len(text)
        best = start
        while low <= high:
            middle = (low + high) // 2
            size = await count(text[start:middle])
            if size <= limit:
                best = middle
                low = middle + 1
            else:
                high = middle - 1
        if best == start:
            raise ValueError("Context budget cannot fit a single evidence character.")
        yield start, best, text[start:best]
        start = best


async def plan(messages, payload, total, count_text, count_payload, summarize, emit, cache, cache_key):
    output, buffer, available = budget_limits(total, payload)
    eligible = []
    for index, message in enumerate(messages):
        marked = isinstance(message, HumanMessage) and message.additional_kwargs.get("research_evidence") is True
        if isinstance(message, ToolMessage) or marked:
            if not isinstance(message.content, str):
                continue
            source = (message.additional_kwargs.get("research_evidence_source") or message.additional_kwargs.get("source_id") or
                      getattr(message, "tool_call_id", None) or str(index))
            label = (message.additional_kwargs.get("source_label") or
                     message.additional_kwargs.get("research_evidence_source") or
                     getattr(message, "name", None) or "evidence")
            eligible.append((index, message, str(source), str(label)))

    # Measure source text first, before asking the server to render a request that
    # may already exceed its own context limit.
    raw_sizes = {index: await count_text(message.content) for index, message, _, _ in eligible}
    scaffold = [message.model_copy(update={"content": "[Evidence omitted for scaffold measurement]"})
                if index in raw_sizes else message for index, message in enumerate(messages)]
    fixed_raw = sum([await count_text(message.content) for index, message in enumerate(messages)
                     if index not in raw_sizes and isinstance(message.content, str)])
    tools_raw = await count_text(json.dumps(payload.get("tools", []), ensure_ascii=False))
    try:
        scaffold_count = await count_payload(scaffold)
    except RuntimeError as exc:
        raise RuntimeError(f"Could not render fixed scaffold (measured raw tokens={fixed_raw + tools_raw}, available={available}): {exc}") from None
    if scaffold_count > available:
        raise ValueError(f"Fixed instructions and schema exceed context budget: input={scaffold_count}, available={available}, output={output}, buffer={buffer}.")
    if sum(raw_sizes.values()) + scaffold_count <= total - buffer:
        actual = await count_payload(messages)
        if actual <= available:
            await emit({"stage": "request", "input_tokens": actual, "output_reserved": output, "buffer": buffer})
            return messages, actual, output
    if not eligible:
        raise ValueError(f"Request exceeds context budget and has no marked evidence: scaffold={scaffold_count}, available={available}, output={output}, buffer={buffer}.")

    compacted = list(messages)
    coverage = []
    # Keep small messages intact. Select the largest sources until there is room
    # for notes as well as the evidence that stays verbatim.
    ordered = sorted(eligible, key=lambda item: raw_sizes[item[0]], reverse=True)
    remaining = sum(raw_sizes.values())
    room = available - scaffold_count
    selected = []
    for item in ordered:
        selected.append(item)
        remaining -= raw_sizes[item[0]]
        if remaining <= room // 2:
            break
    chunk_limit = max(1, available // 2)
    source_chunks = {}
    for index, message, source, label in selected:
        source_chunks[index] = [chunk async for chunk in _chunks(message.content, chunk_limit, count_text)]
    chunk_count = sum(len(chunks) for chunks in source_chunks.values())
    note_room = room - remaining
    if chunk_count == 0 or note_room <= 0:
        raise ValueError("No context space remains for derived evidence notes.")
    # Reserve room for labels/framing as well as generated notes.
    target = min(output, max(1, note_room // (chunk_count * 2)))
    for index, message, source, label in selected:
        text = message.content
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        urls = list(dict.fromkeys(re.findall(r"(?m)^Source:\s*(https?://[^\s<>\"']+)", text)))
        notes = []
        ranges = []
        for chunk_index, (start, end, chunk) in enumerate(source_chunks[index], 1):
            item = {"source_id": source, "source_label": label, "sha256": digest,
                    "characters": len(text), "ranges": [[start, end]],
                    "chunk_index": chunk_index, "chunk_count": len(source_chunks[index])}
            key = (cache_key, digest, start, end, label, tuple(urls))
            note = cache.get(key)
            cached = note is not None and await count_text(note) <= target
            if not cached:
                prompt = [SystemMessage(content=(
                    "Produce concise derived research notes for the supplied source segment. Preserve material facts, "
                    "figures, units, fiscal periods, citations, note explanations and contradictions. "
                    "Identify uncertainty and omissions; do not invent facts or present notes as direct quotes. "
                    f"Keep the notes within the requested output limit of {target} tokens.")),
                    HumanMessage(content=f"Source: {label}; source URLs: {', '.join(urls) or 'not supplied'}; segment characters {start}-{end} of {len(text)}.\n\n{chunk}")]
                note = await summarize(prompt, output)
                if not note.strip():
                    raise ValueError("Context compaction returned empty notes; original evidence was retained.")
                cache[key] = note
            notes.append(f"Segment {start}-{end}:\n{note}")
            ranges.append([start, end])
            await emit({"stage": "chunk", "summary_tokens": await count_text(note), **item})
        derived = f"[Derived notes; source={label}; id={source}; sha256={digest}; original characters={len(text)}; source URLs: {', '.join(urls) or 'not supplied'}]\n" + "\n\n".join(notes)
        if await count_text(derived) >= raw_sizes[index]:
            raise ValueError(f"Context compaction did not reduce evidence for source {source}; original retained.")
        compacted[index] = message.model_copy(update={"content": derived})
        coverage.append({"source_id": source, "source_label": label, "sha256": digest,
                         "characters": len(text), "ranges": ranges})
    # Ensure no oversized final payload reaches the rendering endpoint.
    compact_raw = sum([await count_text(compacted[index].content) for index, *_ in eligible])
    if compact_raw + scaffold_count > total - buffer:
        raise ValueError(f"Derived evidence may exceed the server context limit: measured evidence={compact_raw}, scaffold={scaffold_count}, total={total}.")
    actual = await count_payload(compacted)
    if actual > available:
        raise ValueError(f"Rendered request exceeds context budget: input={actual}, available={available}, output={output}, buffer={buffer}.")
    await emit({"stage": "request", "input_tokens": actual, "output_reserved": output, "buffer": buffer, "sources": coverage})
    return compacted, actual, output
