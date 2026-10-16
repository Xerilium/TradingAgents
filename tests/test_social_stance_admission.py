"""Independent admission regressions; fake gateway only, no inference or broker."""
from copy import deepcopy

import pytest

from tests.test_laya_social_contract import SocialGateway, answer
from tradingagents.agents import post_screen


@pytest.mark.parametrize("grade", ["reconsider", "escalate", "ask_human", None, "unknown"])
def test_uncertain_stance_is_unclear_without_losing_raw_prediction(grade, monkeypatch):
    monkeypatch.setattr(post_screen, "_LAYA_UNCERTAIN_UNTIL", 0)
    response = answer(stance="bearish", probability=.8475)
    response["answers"]["stance"].pop("grade", None)
    if grade is not None:
        response["answers"]["stance"]["grade"] = grade
    original = deepcopy(response)
    callback = post_screen.laya_screen("META", SocialGateway(response))
    keep, note = callback(["META post without a supported price view"])
    row = callback.evidence["posts"][0]
    assert keep == [True]
    assert row["stance"] == "unclear"
    assert callback.evidence["counts"]["bearish"] == 0
    assert callback.evidence["counts"]["unclear"] == 1
    assert "1 unclear" in note
    assert row["stance_probability"] == .8475
    assert row["result"] == original
    assert row["result"]["answers"]["stance"]["value"] == "bearish"


def test_decisive_stance_retains_existing_label_and_probability(monkeypatch):
    monkeypatch.setattr(post_screen, "_LAYA_UNCERTAIN_UNTIL", 0)
    response = answer(stance="bullish", probability=.98)
    response["answers"]["stance"]["grade"] = "auto_execute"
    callback = post_screen.laya_screen("META", SocialGateway(response))
    keep, _ = callback(["I buy META because I expect its stock to rise"])
    assert keep == [True]
    assert callback.evidence["counts"]["bullish"] == 1
    assert callback.evidence["posts"][0]["stance_probability"] == .98
