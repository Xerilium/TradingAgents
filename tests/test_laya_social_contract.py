"""T-1.10 acceptance: social classification is evidence, never trade authority.

All gateways and brokers below are local fakes. No model inference or order is sent.
"""
# ruff: noqa: F811 -- imported pytest fixture is intentionally injected by name
from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from tests.test_mcp_gateway import _allow_event_loop_pipe  # noqa: F401
from tests.test_paper_service import complete_run, desk  # noqa: F401
from tradingagents.agents import post_screen
from tradingagents.integrations.maenifold import GatewayCommand, GatewayTimeout
from tradingagents.paper import engine


def answer(about=.95, stance="bullish", probability=.8, confidence=.9):
    probabilities = {name: (probability if name == stance else (1-probability)/2)
                     for name in ("bullish", "bearish", "neutral")}
    return {"contract": {"grade": "reconsider"}, "answers": {
        "about": {"kind": "yes_no", "value": about >= .5,
                  "grade": "auto_execute" if max(about, 1-about) >= .8 else "reconsider",
                  "probabilities": {"true": about, "false": 1-about},
                  "raw": {"type": "noul", "noul": about}},
        "stance": {"kind": "choice", "value": stance,
                   "grade": "auto_execute" if confidence >= .8 else "reconsider",
                   "confidence": confidence, "probabilities": probabilities,
                   "raw": {"type": "choice", "choice": stance,
                           "probabilities": probabilities, "confidence": confidence}},
    }}


class SocialGateway:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []
        self.discoveries = []
        self.active = 0
        self.peak = 0

    def discover(self, domain):
        self.discoveries.append(domain)
        return {name: GatewayCommand(domain, name, "fixture", {"type": "object"})
                for name in ("decide", "count_context")}

    def execute(self, domain, command, parameters, *, on_dispatch=None):
        if on_dispatch:
            on_dispatch()
        self.calls.append((domain, command, deepcopy(parameters)))
        if command == "count_context":
            from tests.test_laya_review_budget import count
            result = count()
            result["sequence_tokens"] = dict.fromkeys(parameters["questions"], 100)
            return result
        assert (domain, command) == ("laya", "decide")
        self.active += 1
        self.peak = max(self.peak, self.active)
        try:
            result = self.responses.pop(0)
            if isinstance(result, BaseException):
                raise result
            return deepcopy(result)
        finally:
            self.active -= 1

    @property
    def decisions(self):
        return [call for call in self.calls if call[1] == "decide"]


def screen(gateway, **kwargs):
    factory = getattr(post_screen, "laya_screen", None)
    assert callable(factory), "Missing Maenifold per-post Laya screening hook"
    return factory("META", gateway, **kwargs)


@pytest.fixture(autouse=True)
def reset_inference_cooldown(monkeypatch):
    monkeypatch.setattr(post_screen, "_LAYA_UNCERTAIN_UNTIL", 0.0, raising=False)
    monkeypatch.setattr(post_screen, "resolve_instrument_identity", lambda ticker: pytest.fail("Social screening must reuse identity, not fetch it"))


def test_social_screen_uses_gateway_raw_individual_posts_and_no_typesafe_key(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    gateway = SocialGateway(answer(), answer(stance="bearish"))
    posts = ["I buy META because I expect a rise.", "I short META expecting a fall."]
    keep, note = screen(gateway)(posts)
    assert keep == [True, True]
    assert "Laya" in note and "1 bullish" in note and "1 bearish" in note
    assert len(gateway.decisions) == 2
    assert gateway.peak == 1
    for call, post in zip(gateway.decisions, posts, strict=True):
        parameters = call[2]
        assert parameters["state"]["post"] == post
        assert "META" in parameters["state"]["instrument"]
        assert set(parameters["questions"]) == {"about", "stance"}
        assert parameters["model"] == "multilingual"
        relevance = parameters["questions"]["about"]
        assert relevance["kind"] == "yes_no"
        assert set(relevance["criteria"]) == {"true", "false"}
        assert "different company" in relevance["criteria"]["false"]


def test_saved_neutral_failure_is_not_relabelled_as_a_success():
    import json
    from pathlib import Path
    receipt = json.loads(Path(__file__).with_name("laya_social_neutral_relevance_failure.json").read_text())
    result = next(call["result"] for call in receipt["calls"] if call["command"] == "decide")
    assert receipt["expected_relevant"] is True and receipt["observed_keep"] == [False]
    assert result["answers"]["about"]["probabilities"]["true"] == .1214
    assert result["answers"]["about"]["grade"] == "auto_execute"
    assert result["answers"]["stance"]["value"] == "neutral"
    # The failed prompt lacked the negative criterion; restoring it does not
    # retroactively alter the model output or establish semantic success.
    assert set(receipt["calls"][0]["parameters"]["questions"]["about"]["criteria"]) == {"true"}


def test_uncertain_stance_contract_overrides_high_winning_probability():
    callback = screen(SocialGateway(answer(probability=.8, confidence=.01)))
    keep, note = callback(["META up"])
    assert keep == [True]
    assert "1 unclear" in note and "0 bullish" in note
    assert callback.evidence["posts"][0]["raw_prediction"] == "bullish"
    assert callback.evidence["posts"][0]["stance_grade"] == "reconsider"


def test_only_clearly_irrelevant_posts_are_removed_and_uncertain_stance_is_retained():
    gateway = SocialGateway(answer(about=.1), answer(about=.45, probability=.4),
                            answer(stance="neutral"))
    keep, note = screen(gateway)(["Spam", "Not sure about META", "META reports tomorrow"])
    assert keep == [False, True, True]
    assert "1 unclear" in note and "1 neutral" in note and "0 bullish" in note


def test_actual_bullish_receipt_retains_uncertain_relevance():
    import json
    from pathlib import Path
    receipt = json.loads(Path(__file__).with_name("laya_social_bullish_receipt.json").read_text())
    callback = screen(SocialGateway(receipt["result"]))
    keep, note = callback([receipt["post"]])
    assert keep == [True] and "1 bullish" in note
    assert "1 retained posts have uncertain relevance" in note
    row = callback.evidence["posts"][0]
    assert row["about_probability"] == .2156
    assert row["stance_probability"] == .9781
    assert row["relevance_uncertain"] is True and row["relevance_grade"] == "reconsider"
    assert row["result"] == receipt["result"]


def test_missing_relevance_contract_never_discards_post():
    result = answer(about=.05)
    result["answers"]["about"].pop("grade")
    keep, _ = screen(SocialGateway(result))(["post"])
    assert keep == [True]


@pytest.mark.parametrize("bad", [None, {}, {"answers": {}},
    answer(probability=float("nan")), answer(probability=1.2)])
def test_malformed_or_nonfinite_answers_never_silently_remove_posts(bad):
    keep, note = screen(SocialGateway(bad))(["META source text"])
    assert keep == [True]
    assert "unscreened" in note.lower() or "unclear" in note.lower()


def test_timeout_is_not_replayed_and_remaining_posts_are_retained():
    gateway = SocialGateway(GatewayTimeout("inference outcome unknown"), answer())
    keep, note = screen(gateway)(["first", "second"])
    assert keep == [True, True]
    assert len(gateway.decisions) == 1
    assert "unscreened" in note.lower()


def test_configured_post_budget_retains_unprocessed_posts_with_honest_note():
    gateway = SocialGateway(answer(), answer())
    keep, note = screen(gateway, max_posts=2)(["one", "two", "three", "four"])
    assert keep == [True] * 4
    assert len(gateway.decisions) == 2
    assert "2" in note and "unscreened" in note.lower()


def test_empty_social_feed_does_not_call_inference():
    gateway = SocialGateway()
    keep, _ = screen(gateway)([])
    assert keep == [] and gateway.decisions == []


def test_oversize_post_is_not_truncated_or_sent_to_inference():
    gateway = SocialGateway(answer())
    original = gateway.execute
    def execute(domain, command, parameters, **kwargs):
        result = original(domain, command, parameters, **kwargs)
        if command == "count_context":
            result["sequence_tokens"]["about"] = 8193
        return result
    gateway.execute = execute
    callback = screen(gateway)
    posts = ["original post" * 100]
    keep, note = callback(posts)
    assert keep == [True] and not gateway.decisions
    assert callback.evidence["posts"][0]["text"] == posts[0]
    assert "1 unscreened" in note


def test_budget_shared_between_sources_caps_total_posts():
    gateway = SocialGateway(answer(), answer())
    budget = {"remaining": 1, "deadline": None}
    first = screen(gateway, budget=budget, source="stocktwits")
    second = screen(gateway, budget=budget, source="reddit")
    first(["first"])
    keep, note = second(["second"])
    assert keep == [True] and "1 unscreened" in note
    assert len(gateway.decisions) == 1
    assert second.evidence["status"] == "deferred"
    assert second.evidence["stop_reason"] == "post_budget_exhausted"
    assert second.evidence["classified_count"] == 0
    assert second.evidence["retained_count"] == 1
    assert "not a source failure" in note
    assert "Unscreened is not neutral" in note


def test_classifier_coverage_and_user_tags_are_distinguished_in_prompt():
    from tradingagents.agents.analysts.sentiment_analyst import _build_system_message
    prompt = _build_system_message(ticker="META", start_date="2026-10-08", end_date="2026-10-15",
                                   news_block="news", stocktwits_block="1 bearish, 19 unscreened", reddit_block="posts", subreddits=["stocks"])
    assert "Different totals or labels between classifier output and user tags are not a data-quality inconsistency" in prompt
    assert "one Laya bearish post plus 19 unscreened" in prompt
    assert "own numerator and denominator" in prompt
    assert "not a source outage" in prompt


def test_other_batch_cannot_dispatch_while_lock_held():
    gateway = SocialGateway(answer())
    with post_screen._LAYA_LOCK:
        keep, note = screen(gateway)(["post"])
    assert keep == [True] and "1 unscreened" in note and not gateway.calls


def test_timeout_prevents_next_source_from_dispatching():
    gateway = SocialGateway(GatewayTimeout("unknown"), answer())
    screen(gateway)(["first"])
    keep, note = screen(gateway)(["second"])
    assert keep == [True] and "1 unscreened" in note
    assert len(gateway.decisions) == 1


def test_cancelled_batch_does_not_dispatch():
    gateway = SocialGateway(answer())
    assert screen(gateway, cancelled=lambda: True)(["post"])[0] == [True]
    assert not gateway.calls


def test_async_gateway_has_effective_outer_deadline():
    import asyncio
    import time
    class SlowGateway:
        async def aexecute(self, *args, **kwargs):
            await asyncio.sleep(5)
    callback = screen(SlowGateway(), budget={"remaining": 1, "deadline": time.monotonic() + .05})
    started = time.monotonic()
    keep, note = callback(["post"])
    assert time.monotonic() - started < 1
    assert keep == [True] and "1 unscreened" in note
    assert callback.evidence["error_class"] == "TimeoutError"
    assert callback.evidence["stop_reason"] == "time_budget_exhausted"
    assert "time budget expired" in callback.evidence["error"]
    assert "will not be replayed" in callback.evidence["error"]


def test_social_explicit_rate_limit_allows_three_bounded_retries(monkeypatch):
    import asyncio

    from tradingagents.integrations.maenifold import MaenifoldGateway
    original_sleep = asyncio.sleep
    async def no_wait(delay):
        assert 0 <= delay <= 60
        gateway._limited_until = 0
        await original_sleep(0)
    monkeypatch.setattr("tradingagents.integrations.maenifold.asyncio.sleep", no_wait)
    class Transport:
        attempts = 0
        async def call_tool(self, name, arguments, *, on_dispatch=None):
            if on_dispatch:
                on_dispatch()
            command = arguments.get("command")
            if name == "GatewayIndex":
                return ({"domains": [{"name": "laya"}]} if not arguments else
                        {"commands": [{"name": key, "schema": {"type": "object"}}
                                      for key in ("decide", "count_context")]})
            if command == "count_context":
                return {"model": "multilingual", "max_tokens": 8192, "effective_max_tokens": 8192,
                        "state_complete": True, "questions_complete": True,
                        "sequence_tokens": {"about": 100, "stance": 100}}
            self.attempts += 1
            if self.attempts <= 3:
                return {"error": {"code": 429, "retry_after": 1}}
            return answer()
    transport = Transport()
    gateway = MaenifoldGateway(transport=transport)
    keep, note = screen(gateway)(["post"])
    assert keep == [True] and "1 bullish" in note
    assert transport.attempts == 4


def test_sentiment_node_uses_distinct_source_callbacks(monkeypatch):
    from langchain_core.messages import AIMessage

    from tradingagents.agents.analysts import sentiment_analyst
    seen = []
    callbacks = {"stocktwits": object(), "reddit": object()}
    def factory(ticker, source, *, instrument_context):
        assert ticker == "META"
        assert "Company: Meta Platforms" in instrument_context
        return callbacks[source]
    monkeypatch.setattr(sentiment_analyst.get_news, "func", lambda *a: "news")
    monkeypatch.setattr(sentiment_analyst, "jev_screen", lambda *a: pytest.fail("Jev must not run in the desk"))
    for name in ("fetch_stocktwits_messages", "fetch_reddit_posts"):
        monkeypatch.setattr(sentiment_analyst, name, lambda *a, screen=None, **kw: seen.append(screen) or "source")
    class LLM:
        def with_structured_output(self, *a, **kw):
            raise NotImplementedError
        def invoke(self, *a, **kw):
            return AIMessage(content="report")
    node = sentiment_analyst.create_sentiment_analyst(LLM(), screen_factory=factory)
    node({"company_of_interest": "META", "trade_date": "2026-10-15", "messages": [], "instrument_context": "Company: Meta Platforms"})
    assert seen == [callbacks["stocktwits"], callbacks["reddit"]]


@pytest.fixture
def paper_inputs(monkeypatch):
    stamp = datetime(2026, 10, 15, 18, tzinfo=UTC)
    monkeypatch.setattr(engine, "_now", lambda: stamp)
    return {"config": {"universe": ["META"], "max_order_notional": 5000,
                       "allocation_pct": 70, "max_position_pct": 15, "reserve_pct": 20},
            "account": {"status": "ACTIVE", "currency": "USD", "equity": "100000", "cash": "100000"},
            "positions": [], "open_orders": [],
            "quotes": {"META": {"price": 100, "timestamp": stamp.isoformat()}},
            "results": [{"symbol": "META", "status": "completed", "rating": "Buy",
                         "trade_date": "2026-10-15"}], "run_id": "social-role-test"}


@pytest.mark.parametrize("legacy", [None, {"auto_execute": False}, {"auto_execute": True}])
def test_proposal_does_not_depend_on_historical_laya_research_opinion(paper_inputs, legacy):
    paper_inputs["results"][0]["laya"] = legacy
    proposal = engine.plan_orders(**paper_inputs)[0]
    assert proposal["status"] == "proposed"
    assert Decimal(proposal["notional"]) <= 5000


def test_stale_quote_still_blocks_without_laya_gate(paper_inputs):
    paper_inputs["quotes"]["META"]["timestamp"] = "2026-10-15T17:00:00+00:00"
    proposal = engine.plan_orders(**paper_inputs)[0]
    assert proposal["status"] == "blocked" and "stale" in proposal["reason"]


def test_cash_reserve_still_prevents_buy_without_laya_gate(paper_inputs):
    paper_inputs["account"]["cash"] = "20000"
    proposal = engine.plan_orders(**paper_inputs)[0]
    assert proposal["status"] == "skipped" and proposal["qty"] == 0


def test_completed_research_neither_calls_final_laya_nor_places_orders(desk):
    service, broker = desk
    service.refresh()
    run_id = complete_run(service)
    assert not [call for call in broker.calls if call[0] == "laya"]
    proposal = service.propose(run_id)["proposals"][0]
    assert proposal["status"] == "proposed"
    assert broker.submitted == []


def test_service_social_factory_persists_source_evidence_and_gateway_receipts(desk, monkeypatch):
    from tests.test_paper_service import ScriptedGraph
    service, broker = desk
    social = SocialGateway(answer(), answer(stance="bearish"))
    original = broker.execute
    def execute(domain, command, parameters, **kwargs):
        return (social.execute(domain, command, parameters, **kwargs) if domain == "laya"
                else original(domain, command, parameters, **kwargs))
    monkeypatch.setattr(broker, "execute", execute)
    class SocialGraph(ScriptedGraph):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.factory = kwargs["social_screen_factory"]
        def stream_run(self, initial, **kwargs):
            self.factory("AAPL", "stocktwits", instrument_context="Company: Apple Inc.\nExchange: NASDAQ")(["AAPL buying"])
            self.factory("AAPL", "reddit")(["AAPL selling"])
            yield from super().stream_run(initial, **kwargs)
    service.graph_factory = SocialGraph
    run_id = complete_run(service)
    detail = service.run_detail(run_id)
    social_evidence = detail["results"][0]["social_sentiment"]
    assert social_evidence["sources"]["stocktwits"]["counts"]["bullish"] == 1
    assert social_evidence["sources"]["reddit"]["counts"]["bearish"] == 1
    assert "excerpt" in social_evidence["sources"]["reddit"]["posts"][0]["provenance"]
    assert any(a["purpose"] == "social_sentiment" for a in detail["gateway_evidence"]["attempts"])
    assert detail["results"][0]["laya"] is None and broker.submitted == []
    assert social.decisions[0][2]["state"]["instrument"] == "Apple Inc. (AAPL)"


def test_pause_and_paper_identity_remain_enforced(desk):
    service, broker = desk
    service.refresh()
    run_id = complete_run(service)
    proposal = service.propose(run_id)["proposals"][0]
    service.pause(True)
    with pytest.raises(ValueError, match="paused"):
        service.submit(proposal["id"])
    service.pause(False)
    broker.paper = "false"
    with pytest.raises(ValueError):
        service.submit(proposal["id"])
    assert broker.submitted == []
