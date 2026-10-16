"""T-1.1 blue-team regression contract against disclosed pre-TDD drafts.

Gateway counts here are deliberately synthetic: these tests prove caller control
flow, not tokenizer accuracy or effective inference capacity. No backend calls.
"""
import copy
import hashlib
import json
from types import SimpleNamespace

import pytest

from tests.test_mcp_gateway import _allow_event_loop_pipe  # noqa: F401
from tradingagents.web import laya_review as review


SUMMARY = {
    "recommendation": "Hold",
    "supporting_evidence": "market_report: revenue rose 8%; quote $100 at 2026-10-15, delayed feed.",
    "counterarguments": "news_report disputes the growth claim; contradiction remains unresolved.",
    "unresolved_gaps": "fundamentals_report failed; no current cash-flow evidence.",
    "execution_conditions": "Research only, not permission to trade; manual approval and fresh quote required.",
    "source_references": "market_report https://example.test/filing; news_report https://example.test/news",
}
REPORTS = {"market_report": "Revenue rose 8%; https://example.test/filing",
           "news_report": "Growth disputed; https://example.test/news",
           "fundamentals_report": "ERROR: provider timeout"}
QUOTE = {"price": 100, "date": "2026-10-15", "feed": "delayed"}


def count(n=100):
    return {"model": "multilingual", "max_tokens": 8192,
            "questions_complete": True, "state_complete": True,
            "effective_max_tokens": 8192,
            "sequence_tokens": {name: n for name in review.QUESTIONS}}


class Gateway:
    def __init__(self, values=None, hook=lambda: None):
        self.values = list(values if values is not None else [count()])
        self.calls = []
        self.hook = hook

    def execute(self, domain, command, params):
        self.calls.append((domain, command, copy.deepcopy(params)))
        assert (domain, command) == ("laya", "count_context")
        self.hook()
        value = self.values.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


@pytest.fixture
def summaries(monkeypatch):
    calls = []

    def summarize(llm, source, *, compact=False):
        calls.append((copy.deepcopy(source), compact))
        return copy.deepcopy(SUMMARY)

    monkeypatch.setattr(review, "summarize", summarize)
    return calls


def prepare(gateway, cancelled=lambda: False):
    return review.prepare_review(gateway, object(), "META", "2026-10-15", "Hold",
                                 REPORTS, QUOTE, cancelled)


def test_budget_boundary_is_per_sequence_and_reserves_overhead(summaries):
    gateway = Gateway([count(8192 - review.RESERVE)])
    params, audit = prepare(gateway)
    assert sum(audit["token_budget"]["sequence_tokens"].values()) > 8192
    assert params["model"] == "multilingual"
    assert params["threshold"] == "high"
    assert audit["parameters"] == params
    assert audit["parameters"]["state"]["summary"] == SUMMARY
    assert audit["summary_attempts"] == 1
    source = summaries[0][0]
    assert source["reports"] == REPORTS
    expected = hashlib.sha256(json.dumps(source, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    assert params["state"]["source_sha256"] == expected
    assert gateway.calls[0][2]["state"] == params["state"]
    assert gateway.calls[0][2]["questions"] == params["questions"]


def test_one_token_over_reserve_causes_one_compaction(summaries):
    _, audit = prepare(Gateway([count(8192 - review.RESERVE + 1), count(100)]))
    assert [compact for _, compact in summaries] == [False, True]
    assert summaries[0][0] == summaries[1][0]  # resummarize original, not lossy summary
    assert audit["summary_attempts"] == 2


@pytest.mark.parametrize("tokens", [8192, 8193, 100000])
def test_overflow_stops_after_two_attempts(summaries, tokens):
    gateway = Gateway([count(tokens), count(tokens)])
    with pytest.raises(ValueError, match="budget"):
        prepare(gateway)
    assert len(gateway.calls) == len(summaries) == 2


@pytest.mark.parametrize("bad", [None, {}, {"success": False},
    {**count(), "model": "english"}, {**count(), "max_tokens": 1024},
    {**count(), "questions_complete": False}, {**count(), "sequence_tokens": {}},
    {**count(), "sequence_tokens": dict.fromkeys(review.QUESTIONS, True)},
    {**count(), "sequence_tokens": dict.fromkeys(review.QUESTIONS, -1)}])
def test_malformed_or_unverifiable_count_fails_without_retry(summaries, bad):
    gateway = Gateway([bad])
    with pytest.raises(ValueError):
        prepare(gateway)
    assert len(gateway.calls) == len(summaries) == 1


@pytest.mark.parametrize("change", [
    {"state_complete": False}, {"effective_max_tokens": 1024},
    {"state_complete": None}, {"effective_max_tokens": None},
])
def test_preflight_must_prove_state_complete_and_effective_capacity(summaries, change):
    with pytest.raises(ValueError):
        prepare(Gateway([{**count(), **change}]))


def test_cancellation_before_summary_is_immediate(summaries):
    gateway = Gateway()
    with pytest.raises(InterruptedError):
        prepare(gateway, lambda: True)
    assert summaries == gateway.calls == []


def test_cancellation_during_preflight_does_not_return_inference_request(summaries):
    stopped = []
    with pytest.raises(InterruptedError):
        prepare(Gateway(hook=lambda: stopped.append(True)), lambda: bool(stopped))


def test_preflight_timeout_propagates_without_retry(summaries):
    gateway = Gateway([TimeoutError("preflight deadline")])
    with pytest.raises(TimeoutError):
        prepare(gateway)
    assert len(summaries) == len(gateway.calls) == 1


class LLM:
    model_fields = {"timeout": object(), "request_timeout": object()}

    def __init__(self, response, error=None):
        self.response = response
        self.error = error
        self.calls = []
        self.updates = None

    def model_copy(self, *, update):
        self.updates = update
        return self

    async def ainvoke(self, messages):
        self.calls.append(messages)
        if self.error:
            raise self.error
        return SimpleNamespace(content=self.response)


@pytest.mark.parametrize("response", ["not json", "[]", "{}", json.dumps({**SUMMARY, "unresolved_gaps": ""}),
    json.dumps({**SUMMARY, "extra": "ignored"}), [{"text": "not JSON text"}]])
def test_malformed_summary_never_reaches_gateway(response):
    gateway = Gateway()
    with pytest.raises(ValueError):
        review.prepare_review(gateway, LLM(response), "META", "2026-10-15", "Hold", REPORTS, QUOTE)
    assert gateway.calls == []


def test_summary_timeout_is_native_bounded_and_not_retried():
    llm = LLM(None, TimeoutError("provider timeout"))
    gateway = Gateway()
    with pytest.raises(TimeoutError):
        review.prepare_review(gateway, llm, "META", "2026-10-15", "Hold", REPORTS, QUOTE)
    assert llm.updates == {"timeout": 60, "request_timeout": 60}
    assert len(llm.calls) == 1
    assert gateway.calls == []


def test_summary_cannot_change_exact_rating():
    gateway = Gateway()
    with pytest.raises(ValueError):
        review.prepare_review(gateway, LLM(json.dumps({**SUMMARY, "recommendation": "Strong Buy"})),
                              "META", "2026-10-15", "Hold", REPORTS, QUOTE)
    assert gateway.calls == []
