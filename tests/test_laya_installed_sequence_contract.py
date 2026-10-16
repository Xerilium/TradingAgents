"""Offline characterization of installed Laya's *actual* sequence functions.

Only the four pure functions are AST-loaded, avoiding model/torch initialization.
The fake tokenizer makes clipping observable; it does NOT prove multilingual
token counts. Set LAYA_ADAPTER_ROOT to use another installed adapter checkout.
"""
import ast
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Union

import pytest


ROOT = Path(os.environ.get("LAYA_ADAPTER_ROOT", "C:/Users/brett/maenifold/laya-mcp"))


@pytest.fixture
def builder():
    common = ROOT / ".venv/Lib/site-packages/laya/common.py"
    assert common.is_file(), f"Installed Laya source required: {common}"
    tree = ast.parse(common.read_text(encoding="utf-8"))
    names = {"serialize_state", "render_criterion", "render_options", "build_sequence"}
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert {n.name for n in nodes} == names
    namespace = {"json": json, "Dict": Dict, "List": List, "Optional": Optional, "Union": Union}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(common), "exec"), namespace)
    return namespace


class ObservableTokenizer:
    """One token per Unicode character. Deliberately not a model tokenizer."""
    cls_token_id, sep_token_id, mask_token_id = 1, 2, 3
    mask_token = "[MASK]"

    def __call__(self, text, *, add_special_tokens=False):
        assert not add_special_tokens
        return {"input_ids": [ord(c) + 10 for c in text]}


Q = {"t": "noul", "ins": "Consistent?", "crit": {"true": "supported", "false": "unsupported"}}


def test_installed_builder_includes_metadata_options_and_special_tokens(builder):
    tok = ObservableTokenizer()
    state = {"summary": "日本語 café", "symbol": "META", "source_sha256": "a" * 64}
    ids, markers = builder["build_sequence"](tok, state, Q, max_len=8192)
    overhead = len(tok("noul question: Consistent?")["input_ids"])
    overhead += sum(1 + len(tok(" " + s)["input_ids"]) for s in builder["render_options"](Q))
    overhead += 4  # CLS plus three SEP
    assert len(ids) == overhead + len(tok(builder["serialize_state"](state))["input_ids"])
    assert ids[0] == tok.cls_token_id and ids[-1] == tok.sep_token_id
    assert len(markers) == 2 and all(ids[m] == tok.mask_token_id for m in markers)
    assert len(ids) > len(state["summary"])


@pytest.mark.parametrize("size", [8191, 8192, 8193])
def test_installed_builder_clips_state_at_complete_sequence_limit(builder, size):
    tok = ObservableTokenizer()
    empty, _ = builder["build_sequence"](tok, "", Q, max_len=8192)
    state = "x" * (size - len(empty))
    full, _ = builder["build_sequence"](tok, state, Q, max_len=20000)
    bounded, _ = builder["build_sequence"](tok, state, Q, max_len=8192)
    assert len(full) == size
    assert len(bounded) == min(size, 8192)
    assert (bounded == full) is (size <= 8192)


@pytest.mark.parametrize("part", ["question", "options"])
def test_installed_builder_silently_loses_question_or_options_even_with_8192(builder, part):
    tok = ObservableTokenizer()
    q = {**Q, "crit": dict(Q["crit"])}
    if part == "question":
        q["ins"] = "q" * 500 + "Ω"
    else:
        q["crit"]["true"] = "c" * 100 + "Ω"
    ids, _ = builder["build_sequence"](tok, "short state", q, max_len=8192)
    assert len(ids) < 8192
    assert ord("Ω") + 10 not in ids  # Characterization, not desired safe-adapter behavior.


def test_adapter_exposes_preflight_for_the_draft_callers_gateway_command():
    """RED until actual MCP adapter supplies the contract used by caller drafts."""
    source = ROOT / "src/laya_mcp/mcp_server/server.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    functions = [n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    assert "count_context" in functions, "Draft calls laya.count_context but installed server has no such function"
