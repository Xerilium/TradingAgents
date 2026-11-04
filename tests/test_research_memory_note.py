"""The desk mirrors each completed per-symbol research narrative into Maenifold memory.

Covers the Maenifold note builder and the gateway write unit in tradingagents.web.service
without starting servers: a recording fake gateway captures execute() arguments.
"""

import inspect
import json
import types
import unittest

from tradingagents.web import service as service_module
from tradingagents.web.evidence_requirements import RESEARCH_REPORTS
from tradingagents.web.service import DeskService, build_research_note

REPORT_TEXTS = {
    "market_report": "MARKET REPORT BODY TEXT",
    "sentiment_report": "SENTIMENT REPORT BODY TEXT",
    "news_report": "NEWS REPORT BODY TEXT",
    "fundamentals_report": "FUNDAMENTALS REPORT BODY TEXT",
    "investment_plan": "INVESTMENT PLAN BODY TEXT",
    "trader_investment_plan": "TRADER PLAN BODY TEXT",
    "final_trade_decision": "FINAL DECISION BODY TEXT",
}

INVESTMENT_DEBATE = {
    "bull_history": "BULL TURN ONE",
    "bear_history": "BEAR TURN ONE",
    "history": "COMBINED DEBATE HISTORY",
    "current_response": "LATEST DEBATE RESPONSE",
    "count": 2,
}

RISK_DEBATE = {
    "aggressive_history": "AGGRESSIVE TURN",
    "conservative_history": "CONSERVATIVE TURN",
    "neutral_history": "NEUTRAL TURN",
    "history": "RISK DEBATE HISTORY",
    "latest_speaker": "Neutral Analyst",
    "current_aggressive_response": "LATEST AGGRESSIVE",
    "current_conservative_response": "LATEST CONSERVATIVE",
    "current_neutral_response": "LATEST NEUTRAL",
    "count": 3,
}


def completed_result():
    return {
        "symbol": "AAPL",
        "status": "completed",
        "trade_date": "2026-11-04",
        "rating": "Buy",
        "completed_at": "2026-11-04T20:00:00+00:00",
        "reports": {
            **REPORT_TEXTS,
            "investment_debate_state": json.dumps(INVESTMENT_DEBATE),
            "risk_debate_state": json.dumps(RISK_DEBATE),
            "source_coverage": "COVERAGE LIMITATIONS TEXT",
        },
        "coverage_gaps": [{"source": "reddit", "vendor": "Laya", "operation": "get_reddit_posts", "status": "limited"}],
        "revision": 9,
    }


class RecordingGateway:
    def __init__(self, error=None):
        self.calls = []
        self.error = error

    def execute(self, domain, command, parameters, *, on_dispatch=None):
        self.calls.append((domain, command, parameters))
        if self.error is not None:
            raise self.error
        return {"success": True}


class ResearchMemoryNoteTests(unittest.TestCase):
    def setUp(self):
        self.result = completed_result()
        self.run = {"id": "run-77", "trade_date": "2026-11-04"}

    def publish(self, gateway):
        receiver = types.SimpleNamespace(_desk_gateway=lambda: gateway, _event=lambda *args: None)
        DeskService._publish_research_note(receiver, self.run, self.result)

    def test_completed_symbol_writes_exactly_one_replacing_note(self):
        gateway = RecordingGateway()
        self.publish(gateway)
        self.assertEqual(len(gateway.calls), 1)
        domain, command, parameters = gateway.calls[0]
        self.assertEqual((domain, command), ("maenifold.memory", "WriteMemory"))
        self.assertEqual(set(parameters), {"title", "folder", "content", "overwrite", "tags"})
        self.assertEqual(parameters["title"], "report")
        self.assertEqual(parameters["folder"], "research/AAPL/2026/11/04")
        self.assertIs(parameters["overwrite"], True)

    def test_note_carries_every_report(self):
        content = build_research_note(self.run, self.result)
        self.assertIn("# AAPL research 2026-11-04", content)
        self.assertIn("Recommendation: Buy", content)
        self.assertIn("Run ID: run-77", content)
        for key in RESEARCH_REPORTS:
            self.assertIn(f"## {key.replace('_', ' ').capitalize()}", content)
            self.assertIn(REPORT_TEXTS[key], content)
        self.assertIn("## Evidence gaps", content)
        self.assertIn("get_reddit_posts", content)

    def test_decision_assets_without_run_rating_omit_recommendation_header(self):
        self.result.pop("rating")
        for asset in ("trader_investment_plan", "final_trade_decision"):
            with self.subTest(asset=asset):
                result = {**self.result, "reports": {asset: "**Rating**: Underweight"}}
                content = build_research_note(self.run, result)
                self.assertNotIn("Recommendation:", content)
                self.assertIn("**Rating**: Underweight", content)

    def test_debates_render_as_readable_turns(self):
        content = build_research_note(self.run, self.result)
        self.assertIn("## Investment debate", content)
        self.assertIn("## Risk debate", content)
        for turn in ("BULL TURN ONE", "BEAR TURN ONE", "COMBINED DEBATE HISTORY",
                     "AGGRESSIVE TURN", "CONSERVATIVE TURN", "NEUTRAL TURN"):
            self.assertIn(turn, content)

    def test_malformed_debate_state_is_embedded_verbatim_in_a_fenced_block(self):
        self.result["reports"]["investment_debate_state"] = "bull said {{{ not json"
        content = build_research_note(self.run, self.result)
        self.assertIn("```text\nbull said {{{ not json\n```", content)

    def test_gateway_failure_never_changes_completion_status(self):
        gateway = RecordingGateway(error=ConnectionRefusedError("gateway is not running"))
        self.publish(gateway)  # Must not raise.
        self.assertEqual(self.result["status"], "completed")
        self.assertEqual(self.result["rating"], "Buy")

    def test_call_site_publishes_only_completed_symbols_after_persistence(self):
        source = inspect.getsource(DeskService._run_with_evidence)
        persisted = source.index("self.store.save_research()\n                if result[\"status\"] == \"completed\":")
        self.assertIn("self._publish_research_note(run, result)", source[persisted:])


if __name__ == "__main__":
    unittest.main()
