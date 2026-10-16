"""Run with installed adapter venv; uses real cached tokenizer, never model weights."""
import copy
from types import SimpleNamespace

import pytest
pytest.importorskip("laya_mcp", reason="Run with the installed Laya adapter environment")

from laya_mcp.core.context import cached_tokenizer, inspect_context
from laya_mcp.core.engine import DecisionEngine
from laya_mcp.core.settings import Settings

Q = {"q": {"type": "noul", "instructions": "Supported?"}}


@pytest.fixture(scope="module")
def tok():
    return cached_tokenizer()[0]


@pytest.mark.parametrize("size", [8191, 8192, 8193])
def test_real_tokenizer_exact_boundary(tok, size):
    overhead = inspect_context(tok, "", Q)["sequence_tokens"]["q"]
    # Each repeated word is one token for this real tokenizer; verify the premise.
    state = " yes" * (size - overhead)
    assert len(tok(state, add_special_tokens=False)["input_ids"]) == size - overhead
    budget = inspect_context(tok, state, Q)
    assert budget["sequence_tokens"]["q"] == size
    assert budget["questions_complete"]


@pytest.mark.parametrize("state", ["日本語 café 中文 العربية", {"quote": "日本語", "metadata": "x" * 300}])
def test_real_tokenizer_state_and_metadata(tok, state):
    from laya.agent import Agent
    from laya.common import build_sequence
    ids, _ = build_sequence(tok, state, Agent._to_internal(Q["q"]), 8192)
    assert inspect_context(tok, state, Q)["sequence_tokens"]["q"] == len(ids)


@pytest.mark.parametrize("part", ["instructions", "criteria"])
def test_real_tokenizer_rejects_clipped_question_and_option(tok, part):
    q = copy.deepcopy(Q)
    q["q"][part] = " yes" * 500 if part == "instructions" else {"true": " yes" * 100}
    assert inspect_context(tok, "short", q)["questions_complete"] is False


@pytest.mark.parametrize("state,questions", [(" yes" * 8192, Q), ("short", {"q": {"type": "noul", "instructions": " yes" * 500}})], ids=["state_overflow", "head_clipping"])
def test_engine_refuses_before_forward_and_restores_cfg(tok, state, questions):
    calls = []
    cfg = {"max_len": 1024}
    agent = SimpleNamespace(tok=tok, cfg=cfg,
        model=SimpleNamespace(encoder=SimpleNamespace(config=SimpleNamespace(max_position_embeddings=8192))),
        system_one=lambda *args: calls.append(args))
    engine = DecisionEngine(Settings())
    engine.load = lambda: SimpleNamespace(route=lambda *a, **kw: {"model": "multilingual"}, load=lambda *a: agent)
    with pytest.raises(Exception, match="decision model failed"):
        engine._run_blocking(state, questions, "multilingual")
    assert not calls
    assert agent.cfg is cfg
    engine.close = lambda: None


def test_engine_exact_sequence_reaches_forward(tok):
    calls = []
    cfg = {"max_len": 1024}
    def forward(state, questions):
        assert agent.cfg["max_len"] == 8192
        from laya.agent import Agent
        from laya.common import build_sequence
        ids, _ = build_sequence(tok, state, Agent._to_internal(questions["q"]), agent.cfg["max_len"])
        calls.append(ids)
        return {"answers": {}, "usage": {}}
    agent = SimpleNamespace(tok=tok,cfg=cfg,system_one=forward,
        model=SimpleNamespace(encoder=SimpleNamespace(config=SimpleNamespace(max_position_embeddings=8192))))
    engine = DecisionEngine(Settings())
    engine.load = lambda: SimpleNamespace(route=lambda *a, **kw: {"model": "multilingual"}, load=lambda *a: agent)
    result = engine._run_blocking(" yes" * 8000, Q, "multilingual")
    assert result["usage"]["context_budget"]["sequence_tokens"]["q"] == len(calls[0])
    assert agent.cfg is cfg


def test_busy_native_forward_rejects_new_requests_without_queue():
    from concurrent.futures import ThreadPoolExecutor
    import threading
    entered, release = threading.Event(), threading.Event()
    engine = DecisionEngine(Settings())
    def blocked(*args):
        entered.set()
        assert release.wait(3)
        return {}
    engine._infer_checked = blocked
    with ThreadPoolExecutor(max_workers=1) as pool:
        running = pool.submit(engine._run_blocking, "state", Q, "multilingual")
        assert entered.wait(2)
        try:
            with pytest.raises(Exception, match="busy"):
                engine._run_blocking("state", Q, "multilingual")
        finally:
            release.set()
        assert running.result(timeout=2) == {}
    assert engine._run_blocking("state", Q, "multilingual") == {}


def test_real_registered_preflight_tool_uses_same_lowering():
    import asyncio
    from laya_mcp.mcp_server.server import build_mcp_server
    server = build_mcp_server(engine=DecisionEngine(Settings()))
    async def run():
        tools = await server.list_tools()
        tool = next(t for t in tools if t.name == "count_context")
        assert "questions" in tool.input_schema["properties"]
        result = await server.call_tool("count_context", {"state": "日本語", "questions": {
            "q": {"kind": "yes_no", "instructions": "Supported?"}}, "model": "multilingual"})
        assert result.structured_content["questions_complete"] is True
        assert result.structured_content["effective_max_tokens"] == 8192
    asyncio.run(run())
